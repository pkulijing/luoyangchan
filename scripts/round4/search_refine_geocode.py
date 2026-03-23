"""
百度搜索 + DeepSeek + 高德 geocoding 补全模糊地址

三步流程：
  Step 1 (search):   百度搜索获取位置线索
  Step 2 (deepseek): DeepSeek 合成精确地址
  Step 3 (geocode):  高德 geocoding 写回主数据

用法:
  uv run python round4/search_refine_geocode.py --step search
  uv run python round4/search_refine_geocode.py --step deepseek
  uv run python round4/search_refine_geocode.py --step geocode
  uv run python round4/search_refine_geocode.py   # 全部步骤
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND4_DIR = DATA_DIR / "round4"

VAGUE_FILE = ROUND4_DIR / "audit_vague_addresses.json"
SEARCH_FILE = ROUND4_DIR / "search_results_r3.json"
REFINED_FILE = ROUND4_DIR / "refined_addresses_r3.json"
GEOCODE_RESULT_FILE = ROUND4_DIR / "geocode_results_r3.json"


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


def baidu_search(api_key: str, query: str, count: int = 5) -> list[dict]:
    """调用百度 AI Search API。"""
    import requests
    url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Appbuilder-From": "openclaw",
        "Content-Type": "application/json",
    }
    body = {
        "messages": [{"content": query, "role": "user"}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": count}],
    }
    resp = requests.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "code" in data:
        raise Exception(data["message"])
    return data.get("references", [])


# ---------------------------------------------------------------------------
# Step 1: 百度搜索
# ---------------------------------------------------------------------------

def step_search():
    print("=== Step 1: 百度搜索位置信息 ===", flush=True)

    api_key = load_env_key("BAIDU_API_KEY")
    if not api_key:
        print("错误: BAIDU_API_KEY 未配置")
        return

    with open(VAGUE_FILE, encoding="utf-8") as f:
        records = json.load(f)

    results = []
    for i, rec in enumerate(records):
        rid = rec["release_id"]
        name = rec["name"]
        province = rec.get("province", "")
        query = f"{name} {province} 具体位置 地理位置 在哪里"
        print(f"  [{i+1}/{len(records)}] {rid} {name}: {query}", flush=True)

        search_hits = []
        try:
            search_hits = baidu_search(api_key, query, count=5)
            # 提取有用信息
            snippets = []
            for hit in search_hits:
                title = hit.get("title", "")
                content = hit.get("content", "")
                url = hit.get("url", "")
                snippets.append({"title": title, "content": content[:500], "url": url})
            print(f"    搜索到 {len(snippets)} 条结果", flush=True)
        except Exception as e:
            print(f"    搜索失败: {e}", flush=True)
            snippets = []

        results.append({
            **rec,
            "search_results": snippets,
            "search_hit": len(snippets) > 0,
        })
        time.sleep(0.5)

    ROUND4_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEARCH_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    hit_count = sum(1 for r in results if r["search_hit"])
    print(f"\n搜索完成: {hit_count}/{len(results)} 有结果 → {SEARCH_FILE.name}", flush=True)


# ---------------------------------------------------------------------------
# Step 2: DeepSeek 地址合成
# ---------------------------------------------------------------------------

def step_deepseek():
    print("=== Step 2: DeepSeek 地址合成 ===", flush=True)

    from openai import OpenAI

    api_key = load_env_key("DEEPSEEK_API_KEY")
    base_url = load_env_key("DEEPSEEK_BASEURL") or "https://api.deepseek.com"
    if not api_key:
        print("错误: DEEPSEEK_API_KEY 未配置")
        return
    client = OpenAI(api_key=api_key, base_url=base_url)

    with open(SEARCH_FILE, encoding="utf-8") as f:
        records = json.load(f)

    system_prompt = """你是中国文化遗产和历史地理专家。你的任务是为全国重点文物保护单位生成尽可能精确的地址（精确到乡镇/街道/村级），用于地图地理编码。

对于每条记录，我会提供：
1. 文保单位名称、省份、当前地址
2. 百度搜索结果（标题和内容摘要）

请基于搜索结果中的地理位置信息，生成精确地址。

重要规则：
- 地址格式必须是：省+市+区/县+乡镇/街道+村/具体位置
- 如果搜索结果中完全没有更精确的位置信息，保持原地址不变，并在notes中说明
- 对于分布范围广的遗址（长城段、烽燧群、墓群等），如果能找到代表性地点也行
- poi_name 字段用于高德 geocoding 的关键词搜索备选

输出：JSON 数组，每个元素包含 release_id, address_for_geocoding, poi_name, notes, improved (boolean，是否比原地址更精确)。
不要输出其他内容。"""

    # 分组处理（每组8条，搜索结果文本量大）
    group_size = 8
    all_results = []
    groups = [records[i:i + group_size] for i in range(0, len(records), group_size)]

    for gi, group in enumerate(groups):
        print(f"\n  Group {gi+1}/{len(groups)}: {len(group)} 条", flush=True)

        user_content = []
        for rec in group:
            entry = {
                "release_id": rec["release_id"],
                "name": rec["name"],
                "province": rec.get("province", ""),
                "current_address": rec.get("address", ""),
            }
            if rec.get("search_hit"):
                # 只取前3条最相关的搜索结果
                entry["search_results"] = rec["search_results"][:3]
            user_content.append(entry)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请为以下 {len(group)} 条记录生成精确地址：\n\n" + json.dumps(user_content, ensure_ascii=False, indent=2)},
        ]

        max_retries = 3
        parsed = None
        for attempt in range(max_retries):
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
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    break
            except Exception as e:
                print(f"    [attempt {attempt+1}] 错误: {e}", flush=True)
                if attempt < max_retries - 1:
                    messages.append({"role": "user", "content": "请只输出 JSON 数组"})

        if parsed is None:
            print(f"    [error] JSON parse failed for group {gi+1}", flush=True)
            parsed = []

        for rec in parsed:
            improved = rec.get("improved", False)
            marker = "✓" if improved else "—"
            print(f"    {marker} {rec.get('release_id', '?')}: {rec.get('address_for_geocoding', '')}", flush=True)
        all_results.extend(parsed)

    with open(REFINED_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    improved_count = sum(1 for r in all_results if r.get("improved"))
    print(f"\n地址合成完成: {len(all_results)} 条, {improved_count} 条有改善 → {REFINED_FILE.name}", flush=True)


# ---------------------------------------------------------------------------
# Step 3: 高德 geocoding
# ---------------------------------------------------------------------------

def step_geocode():
    print("=== Step 3: 高德 geocoding ===", flush=True)

    sys.path.insert(0, str(Path(__file__).parent.parent / "round1"))
    sys.path.insert(0, str(Path(__file__).parent.parent / "round3"))
    from geocode_amap import geocode, load_env_key as load_amap_key
    from geocode_utils import extract_expected_province, is_province_ok

    import math

    api_key = load_amap_key()
    if not api_key:
        print("错误: AMAP_GEOCODING_KEY 未配置")
        return

    with open(REFINED_FILE, encoding="utf-8") as f:
        refined = json.load(f)
    with open(MAIN_FILE, encoding="utf-8") as f:
        main_data = json.load(f)
    main_by_id = {r["release_id"]: r for r in main_data}

    # 只处理标记为 improved 的记录
    to_geocode = [r for r in refined if r.get("improved", False)]
    print(f"待 geocoding: {len(to_geocode)} 条（已过滤 improved=true）", flush=True)

    def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
        a = 6378245.0
        ee = 0.00669342162296594323

        def transform_lat(x, y):
            ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
            ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
            ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
            ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
            return ret

        def transform_lng(x, y):
            ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
            ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
            ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
            ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
            return ret

        dlat = transform_lat(lng - 105.0, lat - 35.0)
        dlng = transform_lng(lng - 105.0, lat - 35.0)
        radlat = lat / 180.0 * math.pi
        magic = math.sin(radlat)
        magic = 1 - ee * magic * magic
        sqrtmagic = math.sqrt(magic)
        dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
        dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
        return round(lng - dlng, 6), round(lat - dlat, 6)

    results = []
    success = 0
    failed = 0

    for i, rec in enumerate(to_geocode):
        rid = rec["release_id"]
        addr = rec.get("address_for_geocoding", "")
        poi_name = rec.get("poi_name", "")
        main_rec = main_by_id.get(rid)
        if not main_rec or not addr:
            failed += 1
            results.append({"release_id": rid, "status": "skip"})
            continue

        print(f"  [{i+1}/{len(to_geocode)}] {rid} {main_rec['name']}: {addr}", flush=True)

        result = geocode(addr, api_key)
        time.sleep(0.3)

        if result and result.get("latitude") and result.get("longitude"):
            # GCJ-02 → WGS-84
            wgs_lng, wgs_lat = gcj02_to_wgs84(result["longitude"], result["latitude"])

            # 省份验证
            expected_province = extract_expected_province(main_rec.get("release_address", "")) or main_rec.get("province")
            if not is_province_ok(expected_province, result.get("province")):
                print(f"    ✗ 省份不匹配: 预期={expected_province}, 实际={result.get('province')}", flush=True)
                results.append({"release_id": rid, "status": "province_mismatch"})
                failed += 1
                continue

            level = result.get("_geocode_level", "")

            # 更新主数据
            main_rec["latitude"] = wgs_lat
            main_rec["longitude"] = wgs_lng
            main_rec["address"] = addr
            if result.get("province"):
                main_rec["province"] = result["province"]
            if result.get("city"):
                main_rec["city"] = result["city"]
            if result.get("district"):
                main_rec["district"] = result["district"]
            main_rec["_geocode_method"] = "amap_geocode_deepseek_search"
            main_rec["_geocode_reliability"] = None  # 高德不返回 reliability
            main_rec.pop("_geocode_score", None)
            main_rec.pop("_geocode_matched_name", None)

            success += 1
            print(f"    ✓ ({wgs_lat}, {wgs_lng}) level={level}", flush=True)
            results.append({"release_id": rid, "status": "updated", "lat": wgs_lat, "lng": wgs_lng, "level": level})
        else:
            print(f"    ✗ 高德未找到结果", flush=True)
            results.append({"release_id": rid, "status": "not_found"})
            failed += 1

    # 保存结果记录
    with open(GEOCODE_RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 写回主数据
    if success > 0:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2)

    print(f"\n成功: {success}, 失败: {failed} → {GEOCODE_RESULT_FILE.name}", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="百度搜索+DeepSeek+高德geocoding补全模糊地址")
    parser.add_argument("--step", choices=["search", "deepseek", "geocode"],
                        help="只执行指定步骤")
    args = parser.parse_args()

    steps = {
        "search": step_search,
        "deepseek": step_deepseek,
        "geocode": step_geocode,
    }

    if args.step:
        steps[args.step]()
    else:
        for name, fn in steps.items():
            fn()


if __name__ == "__main__":
    main()
