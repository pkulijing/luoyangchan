"""
Task C: 百度百科 + DeepSeek 补全低精度记录

分4步执行：
  Step 1 (identify): 扫描 result 文件识别低精度记录
  Step 2 (baike):    百度百科查询位置信息
  Step 3 (deepseek): DeepSeek 合成精确地址
  Step 4 (geocode):  腾讯地图 geocoding 写回主数据

用法:
  uv run python round4/baike_address_refine.py --step identify
  uv run python round4/baike_address_refine.py --step baike
  uv run python round4/baike_address_refine.py --step deepseek
  uv run python round4/baike_address_refine.py --step geocode
  uv run python round4/baike_address_refine.py              # 全部步骤
  uv run python round4/baike_address_refine.py --dry-run    # 每步只处理前5条
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
ROUND3_BATCH_DIR = DATA_DIR / "round3" / "geocode_batches"
ROUND4_DIR = DATA_DIR / "round4"

LOW_PREC_FILE = ROUND4_DIR / "low_precision_records.json"
BAIKE_FILE = ROUND4_DIR / "baike_results.json"
REFINED_FILE = ROUND4_DIR / "refined_addresses.json"

# 低精度识别关键词
LOW_PREC_KEYWORDS = ["未能", "未找到", "无法", "仅能", "县级", "区级", "市级"]

# 百度百科位置相关的 card key
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
# Step 1: 识别低精度记录
# ---------------------------------------------------------------------------

def step_identify(dry_run: bool = False):
    print("=== Step 1: 识别低精度记录 ===")

    with open(MAIN_FILE, encoding="utf-8") as f:
        main_data = json.load(f)
    main_by_id = {r["release_id"]: r for r in main_data}

    low_prec = []
    for i in range(1, 19):
        path = ROUND3_BATCH_DIR / f"result_{i:03d}.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
        for r in records:
            notes = r.get("notes", "") or ""
            if not any(kw in notes for kw in LOW_PREC_KEYWORDS):
                continue
            main_rec = main_by_id.get(r["release_id"], {})
            if main_rec.get("_is_parent"):
                continue
            low_prec.append({
                "release_id": r["release_id"],
                "name": main_rec.get("name", ""),
                "result_addr": r.get("address_for_geocoding", ""),
                "release_address": main_rec.get("release_address", ""),
                "province": main_rec.get("province", ""),
                "notes": notes,
            })

    ROUND4_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOW_PREC_FILE, "w", encoding="utf-8") as f:
        json.dump(low_prec, f, ensure_ascii=False, indent=2)

    print(f"识别到 {len(low_prec)} 条低精度记录 → {LOW_PREC_FILE.name}")


# ---------------------------------------------------------------------------
# Step 2: 百度百科查询
# ---------------------------------------------------------------------------

def step_baike(dry_run: bool = False):
    print("=== Step 2: 百度百科查询 ===")

    # 动态导入 BaiduBaikeClient
    baike_path = _ROOT / "skills" / "baidu-baike" / "scripts"
    sys.path.insert(0, str(baike_path))
    from baidu_baike import BaiduBaikeClient

    api_key = load_env_key("BAIDU_API_KEY")
    if not api_key:
        print("错误: BAIDU_API_KEY 未配置")
        return
    client = BaiduBaikeClient(api_key)

    with open(LOW_PREC_FILE, encoding="utf-8") as f:
        records = json.load(f)

    if dry_run:
        records = records[:5]
        print(f"  [dry-run] 只处理前 {len(records)} 条")

    results = []
    for i, rec in enumerate(records):
        name = rec["name"]
        print(f"  [{i+1}/{len(records)}] {rec['release_id']} {name}")

        baike_info = {}
        abstract = ""
        try:
            content = client.get_lemma_content("lemmaTitle", name)
            if content:
                abstract = content.get("abstract_plain", "") or ""
                if content.get("card"):
                    for card_item in content["card"]:
                        card_name = card_item.get("name", "")
                        if card_name in LOCATION_KEYS:
                            values = card_item.get("value", [])
                            if values:
                                baike_info[card_name] = values[0] if len(values) == 1 else values
                # 从摘要中提取"位于XXX"模式的地址
                if not baike_info and abstract:
                    import re
                    m = re.search(r"位于(.{5,40}?)[，。,]", abstract)
                    if m:
                        baike_info["摘要位置"] = m.group(1)
            if baike_info:
                print(f"    百科命中: {baike_info}")
            else:
                print(f"    百科未找到位置信息")
        except Exception as e:
            print(f"    百科查询失败: {e}")

        results.append({
            **rec,
            "baike_location": baike_info,
            "baike_hit": bool(baike_info),
        })
        time.sleep(0.5)  # 限流

    with open(BAIKE_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    hit_count = sum(1 for r in results if r["baike_hit"])
    print(f"\n百度百科命中: {hit_count}/{len(results)} → {BAIKE_FILE.name}")


# ---------------------------------------------------------------------------
# Step 3: DeepSeek 地址合成
# ---------------------------------------------------------------------------

def step_deepseek(dry_run: bool = False):
    print("=== Step 3: DeepSeek 地址合成 ===")

    from openai import OpenAI
    from ddgs import DDGS

    api_key = load_env_key("DEEPSEEK_API_KEY")
    base_url = load_env_key("DEEPSEEK_BASEURL") or "https://api.deepseek.com"
    if not api_key:
        print("错误: DEEPSEEK_API_KEY 未配置")
        return
    client = OpenAI(api_key=api_key, base_url=base_url)

    with open(BAIKE_FILE, encoding="utf-8") as f:
        records = json.load(f)

    if dry_run:
        records = records[:5]
        print(f"  [dry-run] 只处理前 {len(records)} 条")

    def search_web(query: str) -> str:
        try:
            results = DDGS().text(query, region="cn-zh", max_results=5)
            if not results:
                return "No results found."
            parts = []
            for r in results:
                parts.append(f"[{r.get('title', '')}]\n{r.get('body', '')}")
            return "\n\n---\n\n".join(parts)
        except Exception as e:
            return f"Search failed: {e}"

    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "搜索网络获取文物保护单位的位置信息",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                    "required": ["query"],
                },
            },
        }
    ]

    system_prompt = """你是中国文化遗产和历史地理专家。你的任务是为文保单位生成精确地址（精确到乡镇/街道/村级），用于地图地理编码。

对于每条记录，我会提供百度百科的位置信息（如果有）。请基于百科信息生成精确地址。如果百科信息不足，可以使用 search_web 工具搜索。

输出：JSON 数组，每个元素包含 release_id, address_for_geocoding, poi_name, notes。不要输出其他内容。"""

    # 分组处理（每组10条）
    group_size = 10
    all_results = []
    groups = [records[i:i + group_size] for i in range(0, len(records), group_size)]

    for gi, group in enumerate(groups):
        print(f"\n  Group {gi+1}/{len(groups)}: {len(group)} 条")

        user_content = []
        for rec in group:
            entry = {
                "release_id": rec["release_id"],
                "name": rec["name"],
                "province": rec["province"],
                "release_address": rec["release_address"],
                "previous_address": rec["result_addr"],
            }
            if rec.get("baike_hit"):
                entry["baike_location"] = rec["baike_location"]
            user_content.append(entry)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请为以下 {len(group)} 条记录生成精确地址：\n\n" + json.dumps(user_content, ensure_ascii=False, indent=2)},
        ]

        max_rounds = 12
        parsed = None
        for round_num in range(max_rounds):
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0,
            )
            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_unset=False))

            if not msg.tool_calls:
                content = (msg.content or "").strip()
                if content.startswith("```"):
                    lines = content.splitlines()
                    end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                    content = "\n".join(lines[1:end]).strip()
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        break
                except json.JSONDecodeError:
                    messages.append({"role": "user", "content": "请只输出 JSON 数组"})
                    continue
                parsed = None
            else:
                tool_results = []
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    if tc.function.name == "search_web":
                        print(f"    [search] {args['query']}")
                        result = search_web(args["query"])
                        time.sleep(0.5)
                    else:
                        result = "Unknown tool"
                    tool_results.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                messages.extend(tool_results)

        if parsed is None:
            # 强制最终输出
            messages.append({"role": "user", "content": "请基于已有信息输出 JSON 数组"})
            response = client.chat.completions.create(
                model="deepseek-chat", messages=messages, tool_choice="none", temperature=0)
            content = (response.choices[0].message.content or "").strip()
            if content.startswith("```"):
                lines = content.splitlines()
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                content = "\n".join(lines[1:end]).strip()
            try:
                parsed = json.loads(content)
            except:
                print(f"    [error] JSON parse failed for group {gi+1}")
                parsed = []

        for rec in (parsed or []):
            addr = rec.get("address_for_geocoding", "")
            print(f"    {rec.get('release_id', '?')}: {addr}")
        all_results.extend(parsed or [])

    with open(REFINED_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n精确地址生成完成: {len(all_results)} 条 → {REFINED_FILE.name}")


# ---------------------------------------------------------------------------
# Step 4: 腾讯地图 geocoding
# ---------------------------------------------------------------------------

def step_geocode(dry_run: bool = False):
    print("=== Step 4: 腾讯地图 geocoding ===")

    sys.path.insert(0, str(Path(__file__).parent.parent / "round3"))
    from geocode_tencent import geocode_by_address, load_env_keys, compute_sig
    from geocode_utils import extract_expected_province, is_province_ok

    api_key, sk = load_env_keys()
    if not api_key:
        print("错误: TENCENT_MAP_KEY 未配置")
        return

    with open(REFINED_FILE, encoding="utf-8") as f:
        refined = json.load(f)
    with open(MAIN_FILE, encoding="utf-8") as f:
        main_data = json.load(f)
    main_by_id = {r["release_id"]: r for r in main_data}

    if dry_run:
        refined = refined[:5]
        print(f"  [dry-run] 只处理前 {len(refined)} 条")

    success = 0
    failed = 0
    for i, rec in enumerate(refined):
        rid = rec["release_id"]
        addr = rec.get("address_for_geocoding", "")
        main_rec = main_by_id.get(rid)
        if not main_rec or not addr:
            failed += 1
            continue

        print(f"  [{i+1}/{len(refined)}] {rid} {main_rec['name']}: {addr}")

        result = geocode_by_address(addr, api_key, sk)
        time.sleep(1.0)

        if result is None:
            print(f"    ✗ geocoding 失败")
            failed += 1
            continue

        expected_province = extract_expected_province(main_rec.get("release_address", "")) or main_rec.get("province")
        if not is_province_ok(expected_province, result.get("province")):
            print(f"    ✗ 省份不匹配: 预期={expected_province}, 实际={result.get('province')}")
            failed += 1
            continue

        # 检查是否比原来更精确（reliability 更高或地址更长）
        old_rel = main_rec.get("_geocode_reliability", 0)
        new_rel = result.get("_geocode_reliability", 0)

        result["_geocode_method"] = "tencent_geocode_deepseek_baike"
        result["address"] = addr

        for field in ["province", "city", "district", "address", "latitude", "longitude",
                       "_geocode_method", "_geocode_reliability"]:
            if field in result:
                main_rec[field] = result[field]
        # 清除不再适用的字段
        main_rec.pop("_geocode_score", None)
        main_rec.pop("_geocode_matched_name", None)

        success += 1
        print(f"    ✓ ({result['latitude']}, {result['longitude']}) rel={new_rel} (was {old_rel})")

    if not dry_run:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2)

    print(f"\n成功: {success}, 失败: {failed}")
    if dry_run:
        print("（dry-run 模式，未写入文件）")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="百度百科补全低精度记录")
    parser.add_argument("--step", choices=["identify", "baike", "deepseek", "geocode"],
                        help="只执行指定步骤")
    parser.add_argument("--dry-run", action="store_true", help="每步只处理前5条，不写主数据")
    args = parser.parse_args()

    steps = {
        "identify": step_identify,
        "baike": step_baike,
        "deepseek": step_deepseek,
        "geocode": step_geocode,
    }

    if args.step:
        steps[args.step](args.dry_run)
    else:
        for name, fn in steps.items():
            fn(args.dry_run)


if __name__ == "__main__":
    main()
