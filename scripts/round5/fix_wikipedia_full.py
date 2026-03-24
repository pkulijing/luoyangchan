"""
为所有没有 Wikipedia 内容的记录补采：包括没有 wikipedia_url 的 1627 条和之前失败的 142 条。

策略：直接构造 URL 访问 → Wikipedia 搜索 API + 相似度校验。

用法:
  uv run python round5/fix_wikipedia_full.py --dry-run    # 只处理前 10 条
  uv run python round5/fix_wikipedia_full.py              # 全量处理
  uv run python round5/fix_wikipedia_full.py --resume     # 断点续跑
"""

import argparse
import json
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, unquote

import requests
import zhconv

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND5_DIR = DATA_DIR / "round5"
WIKI_FILE = ROUND5_DIR / "wikipedia_extracts.json"
CHECKPOINT_FILE = ROUND5_DIR / "wikipedia_full_checkpoint.json"

WIKI_REST_API = "https://zh.wikipedia.org/api/rest_v1/page/summary"
WIKI_SEARCH_API = "https://zh.wikipedia.org/w/api.php"
USER_AGENT = "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
REQUEST_INTERVAL = 0.5
SIMILARITY_THRESHOLD = 0.85
CHECKPOINT_INTERVAL = 100


def to_simplified(text: str) -> str:
    if not text:
        return text
    return zhconv.convert(text, "zh-cn")


def fetch_summary(title: str, session: requests.Session) -> dict | None:
    """调用 Wikipedia REST API 获取简体中文摘要。"""
    url = f"{WIKI_REST_API}/{quote(title, safe='')}"
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        extract = data.get("extract", "")
        if extract:
            return {
                "wikipedia_extract": to_simplified(extract),
                "wikipedia_description": to_simplified(data.get("description", "")),
            }
    except requests.RequestException:
        pass
    return None


def search_wikipedia(name: str, session: requests.Session) -> str | None:
    """用 MediaWiki 搜索 API 查找最匹配的词条标题。"""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srlimit": 5,
        "format": "json",
        "utf8": 1,
    }
    try:
        resp = session.get(WIKI_SEARCH_API, params=params, timeout=30)
        resp.raise_for_status()
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return None

        bare_name = re.sub(r"[（(].+?[）)]", "", name).strip()
        for r in results:
            candidate = to_simplified(r["title"])
            score = max(
                SequenceMatcher(None, name, candidate).ratio(),
                SequenceMatcher(None, bare_name, candidate).ratio(),
            )
            if score >= SIMILARITY_THRESHOLD:
                return r["title"]
    except requests.RequestException:
        pass
    return None


def find_wikipedia(name: str, session: requests.Session) -> dict | None:
    """三级策略查找 Wikipedia 内容。"""
    # 策略 1: 直接用名称作为标题
    result = fetch_summary(name, session)
    if result:
        return result
    time.sleep(REQUEST_INTERVAL)

    # 策略 2: 去括号
    bare_name = re.sub(r"[（(].+?[）)]", "", name).strip()
    if bare_name != name:
        result = fetch_summary(bare_name, session)
        if result:
            return result
        time.sleep(REQUEST_INTERVAL)

    # 策略 3: 搜索 API
    search_title = search_wikipedia(name, session)
    if search_title:
        result = fetch_summary(search_title, session)
        if result:
            return result
        time.sleep(REQUEST_INTERVAL)

    return None


def main():
    parser = argparse.ArgumentParser(description="Supplement Wikipedia extracts for all missing records")
    parser.add_argument("--dry-run", action="store_true", help="只处理前 10 条")
    parser.add_argument("--resume", action="store_true", help="断点续跑")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    # 加载已有 Wikipedia 数据
    wiki_map: dict[str, dict] = {}
    if WIKI_FILE.exists():
        with open(WIKI_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                wiki_map[item["release_id"]] = item

    # 找出没有 Wikipedia 内容的记录
    missing = []
    for s in sites:
        rid = s["release_id"]
        wiki = wiki_map.get(rid, {})
        if not wiki.get("wikipedia_extract"):
            missing.append(s)

    print(f"总记录: {len(sites)}, 已有 Wikipedia 内容: {len(sites) - len(missing)}, 缺失: {len(missing)}")

    # 加载 checkpoint
    done_ids: set[str] = set()
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done_ids.add(item["release_id"])
                wiki_map[item["release_id"]] = item
        print(f"从 checkpoint 恢复: {len(done_ids)} 条已处理")

    pending = [s for s in missing if s["release_id"] not in done_ids]
    if args.dry_run:
        pending = pending[:10]
        print(f"[dry-run] 只处理前 {len(pending)} 条")

    print(f"待处理: {len(pending)} 条\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.headers["Accept-Language"] = "zh-cn"

    recovered = 0
    checkpoint_data = []

    for i, site in enumerate(pending):
        rid = site["release_id"]
        name = site["name"]

        result = find_wikipedia(name, session)
        if result:
            wiki_map[rid] = {"release_id": rid, **result}
            recovered += 1
            preview = result["wikipedia_extract"][:50]
            print(f"  [recovered] {rid}: {name} -> {preview}...")
        else:
            # 确保有空记录
            if rid not in wiki_map:
                wiki_map[rid] = {"release_id": rid, "wikipedia_extract": "", "wikipedia_description": ""}
            print(f"  [miss] {rid}: {name}")

        checkpoint_data.append(wiki_map[rid])

        if (i + 1) % 50 == 0 or i == len(pending) - 1:
            print(f"  进度: {i+1}/{len(pending)} (恢复 {recovered})")

        if not args.dry_run and (i + 1) % CHECKPOINT_INTERVAL == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            print(f"  [checkpoint] 已保存")

        time.sleep(REQUEST_INTERVAL)

    # 写回
    if not args.dry_run:
        all_results = list(wiki_map.values())
        with open(WIKI_FILE, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()

        non_empty = sum(1 for r in all_results if r.get("wikipedia_extract"))
        print(f"\n完成！恢复 {recovered} 条")
        print(f"最终 Wikipedia 覆盖: {non_empty}/{len(all_results)} ({non_empty*100//len(all_results)}%)")
    else:
        print(f"\n[dry-run] 恢复 {recovered}/{len(pending)}")


if __name__ == "__main__":
    main()
