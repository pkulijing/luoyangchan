"""
Phase 3: 使用 DeepSeek API 为文保单位生成描述和标签。

用法:
  uv run python round5/enrich_descriptions.py                    # 全量处理
  uv run python round5/enrich_descriptions.py --dry-run          # 只处理第一组(5条)
  uv run python round5/enrich_descriptions.py --resume           # 从 checkpoint 续跑
  uv run python round5/enrich_descriptions.py --workers 3        # 3 组并发
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND5_DIR = DATA_DIR / "round5"
WIKI_FILE = ROUND5_DIR / "wikipedia_extracts.json"
BAIKE_FILE = ROUND5_DIR / "baike_data.json"
OUTPUT_FILE = ROUND5_DIR / "enrichment_results.json"
CHECKPOINT_FILE = ROUND5_DIR / "enrichment_checkpoint.json"

GROUP_SIZE = 5
MAX_RETRIES = 2
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是中国文化遗产和历史地理专家。你的任务是为"全国重点文物保护单位"生成简要描述和关键词标签。

对于每条输入记录，请根据提供的基本信息和参考资料生成：

1. description（150-300字）：简要描述该文保单位的历史背景、文化意义和主要特征。内容应准确、客观、信息密度高。
2. tags（10-20个关键词）：覆盖以下维度的关键词标签：
   - 相关历史人物（如"李世民"、"武则天"）
   - 相关历史事件（如"鸦片战争"、"安史之乱"）
   - 朝代/时代（如"唐代"、"北宋"、"抗日战争时期"）
   - 建筑风格/类型（如"木结构"、"砖石塔"、"石窟"、"牌坊"）
   - 宗教/文化（如"佛教"、"道教"、"儒学"、"伊斯兰教"）
   - 功能/用途（如"祭祀"、"防御"、"陵墓"、"书院"、"桥梁"）
   - 其他显著特征（如"世界遗产"、"壁画"、"彩塑"、"碑刻"）

注意：
- 如果参考资料为空或不相关，请基于名称、类别、时代等已知信息合理推断，但不要编造具体历史细节。
- tags 中不要重复基本信息中已有的省份、城市名称。
- 每个 tag 应简洁（2-6个字），不要写成句子。

输出：严格输出 JSON 数组，数组长度等于输入记录数。每个元素包含 release_id、description、tags 三个字段。
不要输出任何其他内容，不要用 markdown 代码块包裹。"""


def load_env() -> tuple[str, str]:
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    base_url = os.environ.get("DEEPSEEK_BASEURL", "https://api.deepseek.com")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    return api_key, base_url


def load_reference_data() -> tuple[dict[str, dict], dict[str, dict]]:
    """加载 Wikipedia 和百度百科的参考数据，返回 release_id → data 的映射。"""
    wiki_map: dict[str, dict] = {}
    baike_map: dict[str, dict] = {}

    if WIKI_FILE.exists():
        with open(WIKI_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                wiki_map[item["release_id"]] = item
        print(f"已加载 Wikipedia 数据: {len(wiki_map)} 条")

    if BAIKE_FILE.exists():
        with open(BAIKE_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                baike_map[item["release_id"]] = item
        print(f"已加载百度百科数据: {len(baike_map)} 条")

    return wiki_map, baike_map


def build_group_input(sites: list[dict], wiki_map: dict, baike_map: dict) -> str:
    """构建一组记录的 LLM 输入文本。"""
    records = []
    for site in sites:
        rid = site["release_id"]
        record = {
            "release_id": rid,
            "name": site["name"],
            "category": site["category"],
            "era": site.get("era", ""),
            "province": site.get("province", ""),
            "city": site.get("city", ""),
            "address": site.get("address", ""),
            "batch": site.get("batch"),
            "batch_year": site.get("batch_year"),
        }

        # 附加参考资料
        refs = []
        wiki = wiki_map.get(rid, {})
        if wiki.get("wikipedia_extract"):
            refs.append(f"【Wikipedia摘要】{wiki['wikipedia_extract']}")

        baike = baike_map.get(rid, {})
        if baike.get("baike_abstract"):
            refs.append(f"【百度百科摘要】{baike['baike_abstract']}")
        if baike.get("baike_card"):
            card_str = "、".join(f"{k}: {v}" for k, v in baike["baike_card"].items())
            refs.append(f"【百度百科信息框】{card_str}")

        if refs:
            record["reference"] = "\n".join(refs)

        records.append(record)

    return json.dumps(records, ensure_ascii=False, indent=2)


def _parse_json_response(content: str) -> list[dict] | None:
    """去除 markdown 包裹并解析 JSON 数组。"""
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        content = "\n".join(lines[1:end]).strip()
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    return None


def process_group(client: OpenAI, group_input: str, group_size: int) -> list[dict]:
    """调用 DeepSeek 处理一组记录，返回结果列表。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请为以下 {group_size} 条文保单位生成描述和标签：\n\n{group_input}"},
    ]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0,
            )
            content = (response.choices[0].message.content or "").strip()
            parsed = _parse_json_response(content)
            if parsed is not None:
                return parsed

            # JSON 解析失败，要求重新输出
            if attempt < MAX_RETRIES:
                print(f"  [warn] JSON parse failed, retrying... Response: {content[:200]}")
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": "你的输出不是有效的 JSON 数组，请只输出 JSON 数组，不要任何其他内容。",
                })
        except Exception as e:
            print(f"  [error] API call failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    return []


def align_results(group: list[dict], results: list[dict]) -> list[dict]:
    """对齐 LLM 结果与输入，填充缺失项。"""
    result_map = {r["release_id"]: r for r in results}
    aligned = []
    for site in group:
        rid = site["release_id"]
        if rid in result_map:
            item = result_map[rid]
            # 确保字段存在
            item.setdefault("description", "")
            item.setdefault("tags", [])
            aligned.append(item)
        else:
            print(f"  [warn] Missing result for {rid} ({site['name']})")
            aligned.append({
                "release_id": rid,
                "description": "",
                "tags": [],
            })
    return aligned


def main():
    parser = argparse.ArgumentParser(description="Generate descriptions and tags using DeepSeek")
    parser.add_argument("--dry-run", action="store_true", help="只处理第一组(5条)，不写文件")
    parser.add_argument("--resume", action="store_true", help="从 checkpoint 续跑")
    parser.add_argument("--workers", type=int, default=1, help="并发处理的组数（默认1）")
    args = parser.parse_args()

    ROUND5_DIR.mkdir(parents=True, exist_ok=True)

    api_key, base_url = load_env()
    client = OpenAI(api_key=api_key, base_url=base_url)

    with open(MAIN_FILE, encoding="utf-8") as f:
        all_sites = json.load(f)

    # 排除 parent 记录（无坐标的）
    sites = [s for s in all_sites if s.get("latitude") is not None]
    print(f"共 {len(sites)} 条需要富化的记录")

    wiki_map, baike_map = load_reference_data()

    # 加载已完成的结果
    done: dict[str, dict] = {}
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done[item["release_id"]] = item
        print(f"从 checkpoint 恢复: {len(done)} 条已完成")

    pending = [s for s in sites if s["release_id"] not in done]
    if args.dry_run:
        pending = pending[:GROUP_SIZE]
        print(f"[dry-run] 只处理前 {len(pending)} 条")

    print(f"待处理: {len(pending)} 条, workers={args.workers}\n")

    # 切分成组
    groups = [pending[i:i + GROUP_SIZE] for i in range(0, len(pending), GROUP_SIZE)]

    results_by_group: dict[int, list[dict]] = {}
    checkpoint_lock = threading.Lock()
    done_results = list(done.values())

    def process_one_group(idx: int, group: list[dict]) -> tuple[int, list[dict]]:
        g_start = idx * GROUP_SIZE + 1
        g_end = g_start + len(group) - 1
        names = ", ".join(s["name"] for s in group)
        print(f"  Group {idx + 1}/{len(groups)}: records {g_start}-{g_end} [{names}]")

        group_input = build_group_input(group, wiki_map, baike_map)
        raw = process_group(client, group_input, len(group))
        if not raw:
            print(f"  [error] No results for group {idx + 1}")
            raw = []
        aligned = align_results(group, raw)

        for rec in aligned:
            desc_preview = (rec.get("description") or "")[:50]
            tags_preview = ", ".join((rec.get("tags") or [])[:5])
            print(f"    {rec['release_id']}: {desc_preview}... | tags: [{tags_preview}...]")

        return idx, aligned

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one_group, i, g): i for i, g in enumerate(groups)}
        for future in as_completed(futures):
            idx, aligned = future.result()
            results_by_group[idx] = aligned

            if not args.dry_run:
                # 写 checkpoint
                ordered = list(done_results)
                for j in sorted(results_by_group):
                    ordered.extend(results_by_group[j])
                with checkpoint_lock:
                    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                        json.dump(ordered, f, ensure_ascii=False, indent=2)

    # 合并结果
    all_results = list(done_results)
    for i in sorted(results_by_group):
        all_results.extend(results_by_group[i])

    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
        print(f"\n完成！{len(all_results)} 条结果已保存到 {OUTPUT_FILE}")
    else:
        print(f"\n[dry-run] 完成。")
        if all_results:
            print(json.dumps(all_results[-1], ensure_ascii=False, indent=2))

    # 统计
    with_desc = sum(1 for r in all_results if r.get("description"))
    with_tags = sum(1 for r in all_results if r.get("tags"))
    avg_tags = sum(len(r.get("tags", [])) for r in all_results) / max(len(all_results), 1)
    print(f"\n有描述: {with_desc}/{len(all_results)}")
    print(f"有标签: {with_tags}/{len(all_results)}, 平均标签数: {avg_tags:.1f}")


if __name__ == "__main__":
    main()
