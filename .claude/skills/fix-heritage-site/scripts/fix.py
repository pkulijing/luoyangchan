#!/usr/bin/env python3
"""
文保单位地址修复工具

流程: 数据源(百度百科/百度搜索/用户上下文) → DeepSeek地址合成 → Geocoding(高德/腾讯) → 写回JSON

用法:
  # 默认：百度百科 + 高德
  uv run python fix.py 7-817

  # 百度搜索 + 高德
  uv run python fix.py 7-817 --source search

  # 使用腾讯 geocoding
  uv run python fix.py 7-817 --geocoder tencent

  # 直接指定地址（跳过数据源和 DeepSeek）
  uv run python fix.py 7-817 --address "山西省运城市绛县陈村镇东荆下村"

  # 使用用户提供的上下文
  uv run python fix.py 7-817 --context "该遗址位于山西省运城市绛县陈村镇"

  # 只查询不写入
  uv run python fix.py 7-817 --dry-run

  # 批量修复（仅自动模式）
  uv run python fix.py 7-817 6-478 8-594
"""

import argparse
import difflib
import json
import re
import time
from pathlib import Path

import requests

from utils import (
    load_env_key,
    extract_expected_province,
    is_province_ok,
    compute_tencent_sig,
)

_ROOT = Path(__file__).parent.parent.parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
BAIKE_SCRIPT = _ROOT / ".claude" / "skills" / "baidu-baike" / "scripts"

LOCATION_KEYS = ["地理位置", "位置", "所在地", "地点", "所在地点", "地址", "所处位置", "出土地点"]

# Geocoding API URLs
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
TENCENT_GEOCODE_URL = "https://apis.map.qq.com/ws/geocoder/v1/"


# ---------------------------------------------------------------------------
# 数据源: 百度百科
# ---------------------------------------------------------------------------

def fetch_baike(name: str, province: str) -> dict:
    """查百度百科，返回 {location_info: str, raw: dict}。"""
    import sys
    sys.path.insert(0, str(BAIKE_SCRIPT))
    from baidu_baike import BaiduBaikeClient

    api_key = load_env_key("BAIDU_API_KEY")
    if not api_key:
        return {"location_info": "", "raw": {}, "error": "BAIDU_API_KEY 未配置"}

    client = BaiduBaikeClient(api_key)
    try:
        content = client.get_lemma_content("lemmaTitle", name)
    except Exception as e:
        return {"location_info": "", "raw": {}, "error": str(e)}

    if not content:
        return {"location_info": "", "raw": {}, "error": "百科无此词条"}

    abstract = content.get("abstract_plain", "") or ""
    location_info = {}

    if content.get("card"):
        for card_item in content["card"]:
            card_name = card_item.get("name", "")
            if card_name in LOCATION_KEYS:
                values = card_item.get("value", [])
                if values:
                    location_info[card_name] = values[0] if len(values) == 1 else values

    if not location_info and abstract:
        m = re.search(r"位于(.{5,40}?)[，。,]", abstract)
        if m:
            location_info["摘要位置"] = m.group(1)

    info_text = "; ".join(f"{k}: {v}" for k, v in location_info.items()) if location_info else ""
    return {
        "location_info": info_text,
        "abstract": abstract[:300],
        "raw": location_info,
    }


# ---------------------------------------------------------------------------
# 数据源: 百度搜索
# ---------------------------------------------------------------------------

def fetch_search(name: str, province: str) -> dict:
    """百度搜索，返回 {location_info: str, raw: list}。"""
    api_key = load_env_key("BAIDU_API_KEY")
    if not api_key:
        return {"location_info": "", "raw": [], "error": "BAIDU_API_KEY 未配置"}

    url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Appbuilder-From": "openclaw",
        "Content-Type": "application/json",
    }
    query = f"{name} {province} 具体位置 地理位置 在哪里"
    body = {
        "messages": [{"content": query, "role": "user"}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": 5}],
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "code" in data:
            return {"location_info": "", "raw": [], "error": data["message"]}
        refs = data.get("references", [])
    except Exception as e:
        return {"location_info": "", "raw": [], "error": str(e)}

    snippets = []
    for hit in refs[:5]:
        title = hit.get("title", "")
        content = hit.get("content", "")[:500]
        snippets.append(f"[{title}] {content}")

    return {
        "location_info": "\n".join(snippets),
        "raw": refs[:5],
    }


# ---------------------------------------------------------------------------
# DeepSeek 地址合成
# ---------------------------------------------------------------------------

def deepseek_synthesize(rec: dict, source_info: str, source_type: str) -> dict | None:
    """用 DeepSeek 合成精确地址。返回 {address_for_geocoding, poi_name, notes, improved} 或 None。"""
    from openai import OpenAI

    api_key = load_env_key("DEEPSEEK_API_KEY")
    base_url = load_env_key("DEEPSEEK_BASEURL") or "https://api.deepseek.com"
    if not api_key:
        print("  错误: DEEPSEEK_API_KEY 未配置")
        return None

    client = OpenAI(api_key=api_key, base_url=base_url)

    source_labels = {"baike": "百度百科", "search": "百度搜索", "context": "用户提供的上下文"}
    source_label = source_labels.get(source_type, source_type)

    system_prompt = f"""你是中国文化遗产和历史地理专家。根据提供的{source_label}信息，为文保单位生成精确地址（精确到乡镇/街道/村级），用于地图地理编码。

输出一个 JSON 对象（不是数组），包含:
- address_for_geocoding: 精确地址（省+市+区县+乡镇/街道+村/具体位置）
- poi_name: 用于搜索的关键词
- notes: 简要说明地址来源
- improved: boolean，是否比当前地址更精确

如果信息不足以改善地址，improved 设为 false，address_for_geocoding 填当前地址。"""

    user_content = {
        "release_id": rec["release_id"],
        "name": rec["name"],
        "province": rec.get("province", ""),
        "city": rec.get("city", ""),
        "district": rec.get("district", ""),
        "current_address": rec.get("address", ""),
        "release_address": rec.get("release_address", ""),
        f"{source_label}信息": source_info,
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False, indent=2)},
    ]

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tool_choice="none",
                temperature=0,
            )
            content = (response.choices[0].message.content or "").strip()
            if content.startswith("```"):
                lines = content.splitlines()
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                content = "\n".join(lines[1:end]).strip()
            result = json.loads(content)
            if isinstance(result, list):
                result = result[0] if result else None
            return result
        except Exception as e:
            print(f"  DeepSeek attempt {attempt+1} 失败: {e}")
            if attempt < 2:
                messages.append({"role": "user", "content": "请只输出一个 JSON 对象"})

    return None


# ---------------------------------------------------------------------------
# Geocoding: 高德
# ---------------------------------------------------------------------------

def geocode_amap(address: str) -> dict | None:
    """高德 geocoding，返回 GCJ-02 坐标。"""
    api_key = load_env_key("AMAP_GEOCODING_KEY")
    if not api_key:
        print("  错误: AMAP_GEOCODING_KEY 未配置")
        return None

    try:
        resp = requests.get(
            AMAP_GEOCODE_URL,
            params={"address": address, "key": api_key, "output": "JSON"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    请求失败: {e}")
        return None

    if data.get("status") != "1" or data.get("count", "0") == "0":
        return None

    geo = data["geocodes"][0]
    loc = geo.get("location", "")

    try:
        lng_str, lat_str = loc.split(",")
        longitude = round(float(lng_str), 6)
        latitude = round(float(lat_str), 6)
    except (ValueError, AttributeError):
        return None

    province = geo.get("province") or None
    city = geo.get("city") or None
    if isinstance(city, list) or city == "[]":
        city = province
    district = geo.get("district") or None
    if isinstance(district, list) or district == "[]":
        district = None

    return {
        "province": province,
        "city": city,
        "district": district,
        "address": geo.get("formatted_address"),
        "longitude": longitude,
        "latitude": latitude,
        "_geocode_method": "amap_geocode",
        "_geocode_level": geo.get("level", ""),
    }


# ---------------------------------------------------------------------------
# Geocoding: 腾讯
# ---------------------------------------------------------------------------

def geocode_tencent(address: str) -> dict | None:
    """腾讯 geocoding，返回 GCJ-02 坐标。"""
    api_key = load_env_key("TENCENT_MAP_KEY")
    sk = load_env_key("TENCENT_MAP_SIGN_SECRET_KEY")
    if not api_key:
        print("  错误: TENCENT_MAP_KEY 未配置")
        return None

    try:
        params = {"address": address, "key": api_key, "output": "json"}
        if sk:
            params["sig"] = compute_tencent_sig("/ws/geocoder/v1/", params, sk)
        resp = requests.get(TENCENT_GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    请求失败: {e}")
        return None

    if data.get("status") != 0:
        return None

    result = data.get("result", {})
    location = result.get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    if not lat or not lng:
        return None

    addr_components = result.get("address_components", {})

    return {
        "province": addr_components.get("province") or None,
        "city": addr_components.get("city") or None,
        "district": addr_components.get("district") or None,
        "address": result.get("address") or None,
        "longitude": round(float(lng), 6),
        "latitude": round(float(lat), 6),
        "_geocode_method": "tencent_geocode",
        "_geocode_reliability": result.get("reliability", 0),
    }


# ---------------------------------------------------------------------------
# 核心处理逻辑
# ---------------------------------------------------------------------------

def process_one(rid: str, main_by_id: dict, args) -> dict | None:
    """处理单条记录，返回更新结果或 None。"""
    rec = main_by_id.get(rid)
    if not rec:
        print(f"\n[{rid}] 未找到该 release_id")
        return None

    name = rec["name"]
    province = rec.get("province", "")
    print(f"\n{'='*60}")
    print(f"[{rid}] {name}")
    print(f"  省份: {province} | 市: {rec.get('city', '')} | 区县: {rec.get('district', '')}")
    print(f"  当前地址: {rec.get('address', '')}")
    print(f"  当前坐标: ({rec.get('latitude', '?')}, {rec.get('longitude', '?')})")
    print(f"  当前方法: {rec.get('_geocode_method', '?')}")

    # 如果用户直接指定了地址，跳过数据源和 DeepSeek
    if args.address:
        address = args.address
        print(f"\n  [手动地址] {address}")
        source_type = "manual"
    elif args.context:
        # 用户上下文模式
        print(f"\n  --- 用户上下文模式 ---")
        print(f"  上下文: {args.context[:200]}{'...' if len(args.context) > 200 else ''}")

        print(f"\n  --- DeepSeek 地址合成 ---")
        ds_result = deepseek_synthesize(rec, args.context, "context")

        if not ds_result:
            print(f"  DeepSeek 合成失败")
            return None

        improved = ds_result.get("improved", False)
        address = ds_result.get("address_for_geocoding", "")
        notes = ds_result.get("notes", "")
        print(f"  地址: {address}")
        print(f"  notes: {notes}")
        print(f"  improved: {improved}")

        if not improved:
            print(f"  地址无改善，跳过 geocoding")
            return None
        source_type = "context"
    else:
        # 自动数据源模式
        print(f"\n  --- 查询数据源: {args.source} ---")
        if args.source == "baike":
            info = fetch_baike(name, province)
        else:
            info = fetch_search(name, province)

        if info.get("error"):
            print(f"  数据源错误: {info['error']}")
        elif not info.get("location_info"):
            print(f"  数据源未找到位置信息")
        else:
            preview = info["location_info"][:200]
            print(f"  数据源结果: {preview}")

        # DeepSeek 合成
        print(f"\n  --- DeepSeek 地址合成 ---")
        ds_result = deepseek_synthesize(rec, info.get("location_info", ""), args.source)

        if not ds_result:
            print(f"  DeepSeek 合成失败")
            return None

        improved = ds_result.get("improved", False)
        address = ds_result.get("address_for_geocoding", "")
        notes = ds_result.get("notes", "")
        print(f"  地址: {address}")
        print(f"  notes: {notes}")
        print(f"  improved: {improved}")

        if not improved:
            print(f"  地址无改善，跳过 geocoding")
            return None
        source_type = args.source

    # Geocoding
    print(f"\n  --- Geocoding ({args.geocoder}) ---")
    if args.geocoder == "amap":
        geo = geocode_amap(address)
        # 高德失败自动 fallback 到腾讯
        if not geo:
            print(f"  高德失败，尝试腾讯...")
            geo = geocode_tencent(address)
            if geo:
                args.geocoder = "tencent"
    else:
        geo = geocode_tencent(address)

    if not geo:
        print(f"  Geocoding 失败")
        return None

    # 省份验证
    expected_province = extract_expected_province(rec.get("release_address", "")) or province
    if not is_province_ok(expected_province, geo.get("province")):
        print(f"  省份不匹配: 预期={expected_province}, 实际={geo.get('province')}")
        return None

    # 标记方法
    if source_type == "manual":
        geo["_geocode_method"] = f"{args.geocoder}_geocode_manual"
    else:
        geo["_geocode_method"] = f"{args.geocoder}_geocode_deepseek_{source_type}"
    geo["address"] = address

    print(f"  结果: ({geo['latitude']}, {geo['longitude']})")
    level_info = geo.get('_geocode_level') or geo.get('_geocode_reliability', '?')
    print(f"  level/reliability: {level_info}")
    print(f"  方法标签: {geo['_geocode_method']}")

    return geo


def main():
    parser = argparse.ArgumentParser(
        description="文保单位地址修复",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  uv run python fix.py 7-817
  uv run python fix.py 7-817 --source search
  uv run python fix.py 7-817 --geocoder tencent
  uv run python fix.py 7-817 --address "山西省运城市绛县陈村镇"
  uv run python fix.py 7-817 --context "位于绛县陈村镇东荆下村"
  uv run python fix.py 7-817 --dry-run
  uv run python fix.py 7-817 6-478 8-594""",
    )
    parser.add_argument("release_ids", nargs="+", help="文保单位 release_id")
    parser.add_argument("--source", "-s", choices=["baike", "search"], default="baike",
                        help="数据源 (default: baike)")
    parser.add_argument("--geocoder", "-g", choices=["amap", "tencent"], default="amap",
                        help="地理编码服务 (default: amap)")
    parser.add_argument("--address", "-a", help="直接指定地址，跳过数据源和 DeepSeek")
    parser.add_argument("--context", "-c", help="用户提供的上下文信息")
    parser.add_argument("--dry-run", action="store_true", help="只查询不写入")
    args = parser.parse_args()

    if (args.address or args.context) and len(args.release_ids) > 1:
        print("错误: --address/--context 模式只支持单条 release_id")
        return

    with open(MAIN_FILE, encoding="utf-8") as f:
        main_data = json.load(f)
    main_by_id = {r["release_id"]: r for r in main_data}

    updated = 0
    for rid in args.release_ids:
        geo = process_one(rid, main_by_id, args)
        if geo is None:
            continue

        rec = main_by_id[rid]
        old_lat, old_lng = rec.get("latitude"), rec.get("longitude")

        for field in ["province", "city", "district", "address", "latitude", "longitude",
                       "_geocode_method", "_geocode_reliability", "_geocode_level"]:
            if field in geo:
                rec[field] = geo[field]
            elif field in ("_geocode_reliability", "_geocode_level"):
                rec.pop(field, None)
        rec.pop("_geocode_score", None)
        rec.pop("_geocode_matched_name", None)

        updated += 1
        print(f"\n  已更新: ({old_lat}, {old_lng}) → ({rec['latitude']}, {rec['longitude']})")

    if updated > 0 and not args.dry_run:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {updated} 条到 {MAIN_FILE.name}")
        print(f"\n下一步刷新数据库:")
        print(f"  cd {_ROOT}/scripts && uv run python db/seed_supabase.py --clear")
    elif args.dry_run and updated > 0:
        print(f"\n[dry-run] {updated} 条可更新，未写入")
    else:
        print(f"\n无更新")


if __name__ == "__main__":
    main()
