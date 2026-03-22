"""
通过 OpenRouter LLM（支持 web search 工具）为文保单位查找精确地址。

用法：
    uv run llm_geocode.py                  # 处理所有未完成记录
    uv run llm_geocode.py --limit 100      # 每次只处理 100 条（应对 API 日限额）
    uv run llm_geocode.py --dry-run        # 只打印第一条，不保存
    uv run llm_geocode.py --delay 5        # 设置请求间隔秒数（默认 3）

输出：
    data/round3/llm_geocode_result.json    — 最终结果（累积追加，安全可重跑）
    data/round3/llm_geocode_checkpoint.json — 进度存档（按 release_id 索引）
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

from duckduckgo_search import DDGS
from openai import OpenAI

# 加载 .env.local（脚本从 scripts/ 目录运行，.env.local 在项目根目录）
_env_file = Path(__file__).parent.parent.parent / ".env.local"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# ── 路径 ──────────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = _ROOT / "data/round3/gemini_geocode_input.json"
RESULT_FILE = _ROOT / "data/round3/llm_geocode_result.json"
CHECKPOINT_FILE = _ROOT / "data/round3/llm_geocode_checkpoint.json"

# ── 模型 ──────────────────────────────────────────────────────────────────────

MODEL = "minimax/minimax-m2.5:free"
MAX_TOOL_ROUNDS = 4   # 最多允许几轮 web_search

# ── OpenRouter 客户端 ─────────────────────────────────────────────────────────

def make_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("请设置 OPENROUTER_API_KEY 环境变量")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

# ── Web Search 工具 ────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "在互联网上搜索文保单位的准确地址、位置信息。"
                "当对文保单位的具体位置不确定时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，例如：韶山冲毛主席旧居地址、天一阁博物院位置 宁波",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


def web_search(query: str, max_results: int = 5) -> str:
    """执行 DuckDuckGo 搜索，返回格式化的搜索结果文本。"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "未找到相关搜索结果。"
        lines = []
        for r in results:
            lines.append(f"【{r['title']}】\n{r['body']}\n{r['href']}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"搜索出错：{e}"


# ── Prompt 构建 ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是中国文物保护单位地址研究专家。我会提供一个文保单位的基本信息，你需要给出：

1. address_for_geocoding（必填）：用于地图定位的精确地址字符串。
   格式：省 + 市 + 县/区 + 乡镇/街道 + 具体地点名称
   示例："湖南省湘潭市韶山市韶山冲上屋场"、"浙江省宁波市海曙区天一街10号"

2. poi_name（选填）：地图 POI 搜索中最可能命中的名称（与官方名称不同时才填）

3. notes（选填）：影响定位的重要说明（已改名、已拆除、需区分同名地点等）

注意：
- 如果对具体地点不确定，请调用 web_search 工具搜索。
- 最终请只输出 JSON，不要包含其他文字：
  {"address_for_geocoding": "...", "poi_name": "...", "notes": "..."}
- 省份必须与 expected_province 一致，不要提供错误省份的地址。
"""

PROBLEM_DESC = {
    "geocode_fallback": "原 POI 搜索失败，仅获得区县级精度坐标",
    "poi_province_mismatch": "原 POI 搜索返回了错误省份的结果",
    "poi_duplicate": "多个不同文保单位被定位到了同一坐标",
    "no_coords_child": "多地址拆分后的子条目，尚无坐标",
}


def build_user_message(record: dict) -> str:
    parts = [
        f"文保单位：{record['name']}",
        f"官方公告地址：{record['official_address']}",
    ]
    if record.get("expected_province"):
        parts.append(f"预期省份：{record['expected_province']}")
    if record.get("expected_city"):
        parts.append(f"预期城市：{record['expected_city']}")
    problems = [PROBLEM_DESC.get(p, p) for p in record.get("problem_types", [])]
    if problems:
        parts.append(f"问题描述：{'; '.join(problems)}")
    return "\n".join(parts)


# ── LLM 调用（带工具循环） ────────────────────────────────────────────────────

def call_model(client: OpenAI, record: dict) -> str | None:
    """调用 LLM，处理工具调用循环，返回最终文本响应。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(record)},
    ]

    for round_idx in range(MAX_TOOL_ROUNDS + 1):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1,
        )
        choice = response.choices[0]

        # 模型请求调用工具
        if choice.finish_reason == "tool_calls":
            if round_idx >= MAX_TOOL_ROUNDS:
                # 超过工具轮次限制，强制要求直接回答
                messages.append(choice.message)
                messages.append({
                    "role": "user",
                    "content": "请根据已有信息直接给出 JSON 结果，不要再搜索。",
                })
                continue

            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                query = args.get("query", "")
                search_result = web_search(query)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": search_result,
                })
        else:
            # 正常文本回答
            return choice.message.content

    return None


# ── 结果解析 ──────────────────────────────────────────────────────────────────

def parse_result(content: str | None, release_id: str) -> dict | None:
    """从模型输出中提取 JSON 结果。"""
    if not content:
        return None
    # 优先匹配完整 JSON 对象
    match = re.search(
        r'\{\s*"address_for_geocoding"\s*:.+?\}',
        content,
        re.DOTALL,
    )
    if match:
        try:
            data = json.loads(match.group())
            data["release_id"] = release_id
            return data
        except json.JSONDecodeError:
            pass
    # 回退：尝试整体解析
    try:
        data = json.loads(content.strip())
        if isinstance(data, dict) and "address_for_geocoding" in data:
            data["release_id"] = release_id
            return data
    except json.JSONDecodeError:
        pass
    return None


# ── Checkpoint 工具 ────────────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(checkpoint: dict) -> None:
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def save_results(checkpoint: dict) -> None:
    """将 checkpoint 中有效结果写入最终结果文件。"""
    results = [v for v in checkpoint.values() if v.get("address_for_geocoding")]
    with open(RESULT_FILE, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  → 已写入 {len(results)} 条有效结果到 {RESULT_FILE}")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM 辅助文保单位地址查找")
    parser.add_argument("--limit", type=int, default=None, help="本次最多处理 N 条（适合日限额管理）")
    parser.add_argument("--delay", type=float, default=3.0, help="请求间隔秒数（默认 3）")
    parser.add_argument("--dry-run", action="store_true", help="只处理第 1 条，打印结果，不保存")
    args = parser.parse_args()

    client = make_client()

    with open(INPUT_FILE) as f:
        records = json.load(f)

    checkpoint = load_checkpoint()
    done_ids = set(checkpoint.keys())
    todo = [r for r in records if r["release_id"] not in done_ids]

    print(f"总计 {len(records)} 条，已完成 {len(done_ids)} 条，剩余 {len(todo)} 条")

    if args.dry_run:
        todo = todo[:1]
        print(f"[dry-run] 只处理第 1 条")

    if args.limit is not None:
        todo = todo[: args.limit]
        print(f"[limit] 本次处理 {len(todo)} 条")

    ok_count = 0
    fail_count = 0

    for i, record in enumerate(todo):
        rid = record["release_id"]
        name = record["name"]
        print(f"[{i + 1}/{len(todo)}] {rid} {name} ...", end=" ", flush=True)

        try:
            content = call_model(client, record)
            parsed = parse_result(content, rid)

            if parsed:
                print(f"OK  {parsed['address_for_geocoding'][:40]}")
                if args.dry_run:
                    print("\n── 完整响应 ──")
                    print(content)
                    print("── 解析结果 ──")
                    print(json.dumps(parsed, ensure_ascii=False, indent=2))
                    return
                checkpoint[rid] = parsed
                ok_count += 1
                # 只有成功才写 checkpoint（失败的下次自动重试）
                save_checkpoint(checkpoint)
            else:
                snippet = (content or "")[:60].replace("\n", " ")
                print(f"FAIL  无法解析: {snippet}")
                fail_count += 1

        except Exception as e:
            print(f"ERROR  {e}")
            fail_count += 1

        if i < len(todo) - 1:
            time.sleep(args.delay)

    print(f"\n本次完成：成功 {ok_count} 条，失败 {fail_count} 条")
    save_results(checkpoint)


if __name__ == "__main__":
    main()
