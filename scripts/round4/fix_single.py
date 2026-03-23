"""
单条/多条文保单位地址修复工具

流程: 数据源(百度百科/百度搜索) → DeepSeek地址合成 → Geocoding(高德/腾讯) → 写回主数据

用法:
  # 默认：百度百科 + 高德
  uv run python round4/fix_single.py 7-817

  # 百度搜索 + 高德
  uv run python round4/fix_single.py 7-817 --source search

  # 百度百科 + 腾讯
  uv run python round4/fix_single.py 7-817 --geocoder tencent

  # 多条一起修
  uv run python round4/fix_single.py 7-817 6-478 8-594

  # 只查询不写入
  uv run python round4/fix_single.py 7-817 --dry-run

  # 跳过 DeepSeek，手动指定地址直接 geocode
  uv run python round4/fix_single.py 7-817 --address "山西省运城市绛县陈村镇东荆下村"
"""

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"

LOCATION_KEYS = ["地理位置", "位置", "所在地", "地点", "所在地点", "地址", "所处位置", "出土地点"]


def load_env_key(name: str) -> str | None:
    val = os.environ.get(name)
    if val:
        return val
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return None


# ---------------------------------------------------------------------------
# 数据源: 百度百科
# ---------------------------------------------------------------------------

def fetch_baike(name: str, province: str) -> dict:
    """查百度百科，返回 {location_info: str, raw: dict}。"""
    baike_path = _ROOT / "skills" / "baidu-baike" / "scripts"
    sys.path.insert(0, str(baike_path))
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
    import requests

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
    """用 DeepSeek 合成精确地址。返回 {address_for_geocoding, poi_name, notes} 或 None。"""
    from openai import OpenAI

    api_key = load_env_key("DEEPSEEK_API_KEY")
    base_url = load_env_key("DEEPSEEK_BASEURL") or "https://api.deepseek.com"
    if not api_key:
        print("  错误: DEEPSEEK_API_KEY 未配置")
        return None

    client = OpenAI(api_key=api_key, base_url=base_url)

    source_label = "百度百科" if source_type == "baike" else "百度搜索"

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
# Geocoding
# ---------------------------------------------------------------------------

def geocode_amap(address: str) -> dict | None:
    """高德 geocoding，返回 GCJ-02 坐标（与腾讯一致，直接存储不转换）。"""
    sys.path.insert(0, str(Path(__file__).parent.parent / "round1"))
    from geocode_amap import geocode, load_env_key as load_amap_key

    api_key = load_amap_key()
    if not api_key:
        print("  错误: AMAP_GEOCODING_KEY 未配置")
        return None

    result = geocode(address, api_key)
    if not result or not result.get("latitude") or not result.get("longitude"):
        return None

    # 高德返回 GCJ-02，直接存储，不做坐标转换
    result["_geocode_method"] = "amap_geocode"
    result["_geocode_reliability"] = None
    return result


def geocode_tencent(address: str) -> dict | None:
    """腾讯 geocoding，返回 WGS-84 坐标（腾讯本身就是 WGS-84）。"""
    sys.path.insert(0, str(Path(__file__).parent.parent / "round3"))
    from geocode_tencent import geocode_by_address, load_env_keys

    api_key, sk = load_env_keys()
    if not api_key:
        print("  错误: TENCENT_MAP_KEY 未配置")
        return None

    result = geocode_by_address(address, api_key, sk)
    if not result:
        return None

    result["_geocode_method"] = "tencent_geocode"
    return result


# ---------------------------------------------------------------------------
# Main
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
    else:
        # Step 1: 数据源查询
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

        # Step 2: DeepSeek 合成
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

    # Step 3: Geocoding
    print(f"\n  --- Geocoding ({args.geocoder}) ---")
    if args.geocoder == "amap":
        geo = geocode_amap(address)
    else:
        geo = geocode_tencent(address)

    if not geo:
        print(f"  Geocoding 失败")
        return None

    # 省份验证
    sys.path.insert(0, str(Path(__file__).parent.parent / "round3"))
    from geocode_utils import extract_expected_province, is_province_ok

    expected_province = extract_expected_province(rec.get("release_address", "")) or province
    if not is_province_ok(expected_province, geo.get("province")):
        print(f"  省份不匹配: 预期={expected_province}, 实际={geo.get('province')}")
        return None

    method_suffix = f"_{args.source}" if not args.address else ""
    geo["_geocode_method"] = f"{args.geocoder}_geocode_deepseek{method_suffix}" if not args.address else f"{args.geocoder}_geocode_manual"
    geo["address"] = address

    print(f"  结果: ({geo['latitude']}, {geo['longitude']})")
    print(f"  level/reliability: {geo.get('_geocode_level', geo.get('_geocode_reliability', '?'))}")
    print(f"  方法标签: {geo['_geocode_method']}")

    return geo


def main():
    parser = argparse.ArgumentParser(
        description="单条/多条文保单位地址修复",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  uv run python round4/fix_single.py 7-817
  uv run python round4/fix_single.py 7-817 6-478 --source search
  uv run python round4/fix_single.py 7-817 --geocoder tencent
  uv run python round4/fix_single.py 7-817 --address "山西省运城市绛县陈村镇"
  uv run python round4/fix_single.py 7-817 --dry-run""",
    )
    parser.add_argument("release_ids", nargs="+", help="文保单位 release_id")
    parser.add_argument("--source", choices=["baike", "search"], default="baike",
                        help="数据源 (default: baike)")
    parser.add_argument("--geocoder", choices=["amap", "tencent"], default="amap",
                        help="地理编码服务 (default: amap)")
    parser.add_argument("--address", help="直接指定地址，跳过数据源和 DeepSeek")
    parser.add_argument("--dry-run", action="store_true", help="只查询不写入")
    args = parser.parse_args()

    if args.address and len(args.release_ids) > 1:
        print("错误: --address 模式只支持单条 release_id")
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
                       "_geocode_method", "_geocode_reliability"]:
            if field in geo:
                rec[field] = geo[field]
        rec.pop("_geocode_score", None)
        rec.pop("_geocode_matched_name", None)

        updated += 1
        print(f"\n  已更新: ({old_lat}, {old_lng}) → ({rec['latitude']}, {rec['longitude']})")

    if updated > 0 and not args.dry_run:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {updated} 条到 {MAIN_FILE.name}")
    elif args.dry_run and updated > 0:
        print(f"\n[dry-run] {updated} 条可更新，未写入")
    else:
        print(f"\n无更新")


if __name__ == "__main__":
    main()
