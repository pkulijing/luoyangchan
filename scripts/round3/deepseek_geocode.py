"""
使用 DeepSeek API + DuckDuckGo 搜索为文保单位批次生成精确地址。

用法：
    uv run scripts/round3/deepseek_geocode.py --batch 4
    uv run scripts/round3/deepseek_geocode.py --batch 4 --force            # 覆盖已有结果
    uv run scripts/round3/deepseek_geocode.py --batch 4 --dry-run          # 只处理第一组(10条)，不写文件
    uv run scripts/round3/deepseek_geocode.py --batch 4 --resume           # 从checkpoint断点续跑
    uv run scripts/round3/deepseek_geocode.py --batch 4 --workers 3        # 3个组并发处理
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ddgs import DDGS
from openai import OpenAI

_ROOT = Path(__file__).parent.parent.parent
BATCH_DIR = _ROOT / "data/round3/geocode_batches"
GROUP_SIZE = 10
MAX_TOOL_ROUNDS = 12  # 每组最多工具调用轮次
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是中国文化遗产和历史地理专家。你的任务是为"全国重点文物保护单位"生成用于地图地理编码的精确地址。

对于每条输入记录，你需要提供：
1. address_for_geocoding：精确到乡镇/街道/村级的完整地址（例如"山东省滕州市官桥镇北辛村"），用于腾讯地图地理编码 API。地址越精确越好，县级精度太低。
2. poi_name（可选）：该遗址在地图上可能使用的 POI 名称（例如"北辛遗址"、"某某博物馆"），用于 POI 搜索兜底。
3. notes（可选）：备注，如有行政区划变更或特殊情况可说明。

注意事项：
- 地址省份必须与记录中的 expected_province 一致
- 行政区划以当前（2024年）为准
- 搜索策略：先尝试用自身知识回答，对于你熟悉的著名遗址直接给出精确地址，不要搜索。只在真正不确定精确位置（乡镇/村级）时才使用 search_web。每次搜索尽量一次命中，不要多次搜索同一条记录。
- 所有10条记录都需要给出精确地址（乡镇/村级），不能只给县级。

输出：严格输出 JSON 数组，数组长度等于输入记录数，字段为 release_id / address_for_geocoding / poi_name / notes。不要输出任何其他内容，不要用 markdown 代码块包裹。"""


def load_env() -> tuple[str, str]:
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
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


def search_web(query: str) -> str:
    """DuckDuckGo 搜索，返回前5条结果摘要。"""
    try:
        results = DDGS().text(query, region="cn-zh", max_results=5)
        if not results:
            return "No results found."
        parts = []
        for r in results:
            parts.append(f"[{r.get('title', '')}]\n{r.get('body', '')}\nURL: {r.get('href', '')}")
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"Search failed: {e}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索网络获取文物保护单位的位置信息。当你对某处文物的精确地址不确定时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，例如'北辛遗址 地址 山东'",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


def _parse_json_response(content: str) -> list[dict] | None:
    """去除 markdown 包裹并解析 JSON 数组，失败返回 None。"""
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


def process_group(client: OpenAI, records: list[dict]) -> list[dict]:
    """用 DeepSeek + 工具调用处理一组（≤10条）记录，返回结果列表。"""
    user_content = json.dumps(records, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请为以下 {len(records)} 条记录生成精确地址：\n\n{user_content}"},
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
        )

        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=False))

        # 没有工具调用 → 这是最终回复，尝试解析
        if not msg.tool_calls:
            content = (msg.content or "").strip()
            parsed = _parse_json_response(content)
            if parsed is not None:
                return parsed
            # JSON 解析失败，要求重新输出（最多重试一次）
            print(f"  [warn] JSON parse failed, requesting retry. Response: {content[:200]}")
            messages.append({
                "role": "user",
                "content": "你的输出不是有效的 JSON 数组，请只输出 JSON 数组，不要任何其他内容。",
            })
            continue

        # 执行工具调用
        tool_results = []
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            if fn_name == "search_web":
                query = args["query"]
                print(f"  [search] {query}")
                result = search_web(query)
                time.sleep(0.5)  # DuckDuckGo 限流保护
            else:
                result = f"Unknown tool: {fn_name}"

            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        messages.extend(tool_results)

    # 搜索轮次耗尽后，强制要求最终输出（禁用工具）
    print(f"  [info] Search rounds exhausted, requesting final answer...")
    messages.append({
        "role": "user",
        "content": "搜索轮次已结束，请基于已获取的信息输出 JSON 数组，只输出 JSON，不要任何其他内容。",
    })
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tool_choice="none",
        temperature=0,
    )
    content = (response.choices[0].message.content or "").strip()
    parsed = _parse_json_response(content)
    if parsed is not None:
        return parsed
    print(f"  [error] Final forced response failed to parse: {content[:300]}")
    return []


def _make_group_input(group: list[dict]) -> list[dict]:
    return [
        {
            "release_id": r["release_id"],
            "name": r["name"],
            "official_address": r.get("official_address", ""),
            "expected_province": r.get("expected_province", ""),
        }
        for r in group
    ]


def _align_results(group: list[dict], results: list[dict], group_idx: int) -> list[dict]:
    """对齐 LLM 结果与输入，填充缺失项。"""
    result_map = {r["release_id"]: r for r in results}
    aligned = []
    for r in group:
        rid = r["release_id"]
        if rid in result_map:
            aligned.append(result_map[rid])
        else:
            print(f"  [warn] Missing result for {rid}")
            aligned.append({"release_id": rid, "address_for_geocoding": "", "poi_name": r.get("name", ""), "notes": "missing"})
    return aligned


def run_batch(batch_num: int, force: bool, dry_run: bool, resume: bool, workers: int = 1):
    batch_file = BATCH_DIR / f"batch_{batch_num:03d}.json"
    result_file = BATCH_DIR / f"result_{batch_num:03d}.json"
    checkpoint_file = BATCH_DIR / f"deepseek_checkpoint_{batch_num:03d}.json"

    if not batch_file.exists():
        print(f"ERROR: {batch_file} not found")
        sys.exit(1)

    if result_file.exists() and not force and not dry_run and not resume:
        print(f"result_{batch_num:03d}.json already exists. Use --force to overwrite or --resume to continue.")
        sys.exit(0)

    with open(batch_file) as f:
        all_records = json.load(f)

    print(f"Batch {batch_num:03d}: {len(all_records)} records, workers={workers}")

    # 加载已完成的结果（resume模式）
    done: dict[str, dict] = {}
    if resume and checkpoint_file.exists():
        with open(checkpoint_file) as f:
            done = {r["release_id"]: r for r in json.load(f)}
        print(f"  Resuming from checkpoint: {len(done)} records already done")

    api_key, base_url = load_env()
    client = OpenAI(api_key=api_key, base_url=base_url)

    # 过滤掉已完成的记录
    pending = [r for r in all_records if r["release_id"] not in done]

    if dry_run:
        pending = pending[:GROUP_SIZE]
        print(f"  [dry-run] Processing first {len(pending)} records only")

    # 切分成组
    groups = [pending[i : i + GROUP_SIZE] for i in range(0, len(pending), GROUP_SIZE)]

    # 并发处理：results_by_group[i] = aligned result list for groups[i]
    results_by_group: dict[int, list[dict]] = {}
    checkpoint_lock = threading.Lock()
    done_results: list[dict] = list(done.values())

    def process_one_group(idx: int, group: list[dict]) -> tuple[int, list[dict]]:
        g_start = idx * GROUP_SIZE + 1
        g_end = g_start + len(group) - 1
        print(f"\n  Group {idx + 1}: records {g_start}–{g_end} / {len(pending)}")
        raw = process_group(client, _make_group_input(group))
        if not raw:
            print(f"  [error] No results for group {idx + 1}, using empty placeholders")
            raw = [{"release_id": r["release_id"], "address_for_geocoding": "", "poi_name": r.get("name", ""), "notes": "deepseek failed"} for r in group]
        aligned = _align_results(group, raw, idx)
        for rec in aligned:
            addr = rec.get("address_for_geocoding", "")
            poi = rec.get("poi_name", "")
            print(f"    {rec['release_id']}: {addr}" + (f" | {poi}" if poi else ""))
        return idx, aligned

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_one_group, i, g): i for i, g in enumerate(groups)}
        for future in as_completed(futures):
            idx, aligned = future.result()
            results_by_group[idx] = aligned
            if not dry_run:
                # 写 checkpoint（保持顺序：已完成组 + done）
                ordered = list(done_results)
                for j in sorted(results_by_group):
                    ordered.extend(results_by_group[j])
                with checkpoint_lock:
                    with open(checkpoint_file, "w") as f:
                        json.dump(ordered, f, ensure_ascii=False, indent=2)

    if dry_run:
        print(f"\n[dry-run] Done. Results NOT saved.")
        return

    # 按原始顺序合并所有结果
    all_results = list(done_results)
    for i in sorted(results_by_group):
        all_results.extend(results_by_group[i])

    with open(result_file, "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    if checkpoint_file.exists():
        checkpoint_file.unlink()

    print(f"\nDone! {len(all_results)} records → {result_file}")
    missing_addr = [r["release_id"] for r in all_results if not r.get("address_for_geocoding")]
    if missing_addr:
        print(f"WARNING: {len(missing_addr)} records with empty address: {missing_addr[:10]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, required=True, help="批次编号（如 4 表示 batch_004.json）")
    parser.add_argument("--force", action="store_true", help="覆盖已有 result 文件")
    parser.add_argument("--dry-run", action="store_true", help="只处理第一组(10条)，不写文件")
    parser.add_argument("--resume", action="store_true", help="从 checkpoint 断点续跑")
    parser.add_argument("--workers", type=int, default=1, help="并发处理的组数（默认1，建议3-5）")
    args = parser.parse_args()

    run_batch(args.batch, args.force, args.dry_run, args.resume, args.workers)
