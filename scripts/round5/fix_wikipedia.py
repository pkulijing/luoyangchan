"""
修复 Wikipedia 采集结果：
1. 把已有内容转为简体中文
2. 对失败的条目用新策略重试（Accept-Language: zh-cn、去括号、简体标题）

用法:
  uv run python round5/fix_wikipedia.py --dry-run    # 只看统计
  uv run python round5/fix_wikipedia.py              # 执行修复
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from difflib import SequenceMatcher

import requests
import zhconv

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND5_DIR = DATA_DIR / "round5"
INPUT_FILE = ROUND5_DIR / "wikipedia_extracts.json"
OUTPUT_FILE = INPUT_FILE  # 覆盖写回

WIKI_REST_API = "https://zh.wikipedia.org/api/rest_v1/page/summary"
WIKI_SEARCH_API = "https://zh.wikipedia.org/w/api.php"
USER_AGENT = "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
REQUEST_INTERVAL = 0.3
SIMILARITY_THRESHOLD = 0.6


def to_simplified(text: str) -> str:
    if not text:
        return text
    return zhconv.convert(text, "zh-cn")


def fetch_summary(title: str, session: requests.Session) -> dict | None:
    """调用 Wikipedia REST API 获取简体中文摘要。"""
    url = f"{WIKI_REST_API}/{title}"
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        extract = data.get("extract", "")
        description = data.get("description", "")
        if extract:
            return {
                "wikipedia_extract": to_simplified(extract),
                "wikipedia_description": to_simplified(description),
            }
        return None
    except requests.RequestException as e:
        print(f"  [error] {title}: {e}", file=sys.stderr)
        return None


def retry_failed(release_id: str, wikipedia_url: str, name: str, session: requests.Session) -> dict | None:
    """用多种策略重试失败的条目。"""
    path = urlparse(wikipedia_url).path
    title = unquote(path.split("/wiki/", 1)[-1]) if "/wiki/" in path else ""
    if not title:
        return None

    # 策略 1: 原标题（已有 Accept-Language: zh-cn）
    result = fetch_summary(title, session)
    if result:
        return result
    time.sleep(REQUEST_INTERVAL)

    # 策略 2: 去括号
    bare_title = re.sub(r"[（(].+?[）)]", "", title).strip()
    if bare_title and bare_title != title:
        print(f"  [retry-bare] {title} -> {bare_title}")
        result = fetch_summary(bare_title, session)
        if result:
            return result
        time.sleep(REQUEST_INTERVAL)

    # 策略 3: 下划线变体（Wikipedia 用下划线替代空格）
    if "_" in title:
        no_underscore = title.replace("_", "")
        result = fetch_summary(no_underscore, session)
        if result:
            return result
        time.sleep(REQUEST_INTERVAL)

    # 策略 4: Wikipedia 搜索 API，找最相似的词条
    search_title = search_wikipedia(title, name, session)
    if search_title:
        print(f"  [retry-search] {title} -> {search_title}")
        result = fetch_summary(search_title, session)
        if result:
            return result
        time.sleep(REQUEST_INTERVAL)

    return None


def search_wikipedia(title: str, name: str, session: requests.Session) -> str | None:
    """用 MediaWiki 搜索 API 查找最匹配的词条标题。"""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name or title,
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

        # 找相似度最高的标题
        best_title = None
        best_score = 0
        compare_name = to_simplified(name or title)
        for r in results:
            candidate = to_simplified(r["title"])
            score = SequenceMatcher(None, compare_name, candidate).ratio()
            if score > best_score:
                best_score = score
                best_title = r["title"]

        if best_score >= SIMILARITY_THRESHOLD:
            return best_title
        return None
    except requests.RequestException:
        return None


def main():
    parser = argparse.ArgumentParser(description="Fix Wikipedia extracts: convert to simplified & retry failures")
    parser.add_argument("--dry-run", action="store_true", help="只看统计，不写文件")
    args = parser.parse_args()

    with open(INPUT_FILE, encoding="utf-8") as f:
        extracts = json.load(f)
    print(f"已有 {len(extracts)} 条记录")

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)
    site_map = {s["release_id"]: s for s in sites}

    # Step 1: 转简体
    converted = 0
    for item in extracts:
        old_extract = item.get("wikipedia_extract", "")
        old_desc = item.get("wikipedia_description", "")
        if old_extract:
            new_extract = to_simplified(old_extract)
            new_desc = to_simplified(old_desc)
            if new_extract != old_extract or new_desc != old_desc:
                item["wikipedia_extract"] = new_extract
                item["wikipedia_description"] = new_desc
                converted += 1
    print(f"简体转换: {converted} 条内容有变化")

    # Step 2: 重试失败条目
    failed = [item for item in extracts if not item.get("wikipedia_extract")]
    print(f"失败条目: {len(failed)} 条，开始重试...\n")

    if args.dry_run:
        print("[dry-run] 跳过重试")
    else:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        session.headers["Accept-Language"] = "zh-cn"

        retried = 0
        recovered = 0
        for i, item in enumerate(failed):
            rid = item["release_id"]
            site = site_map.get(rid)
            if not site or not site.get("wikipedia_url"):
                continue

            result = retry_failed(rid, site["wikipedia_url"], site["name"], session)
            if result:
                item.update(result)
                recovered += 1
                print(f"  [recovered] {rid}: {site['name']}")

            retried += 1
            if (retried) % 50 == 0:
                print(f"  重试进度: {retried}/{len(failed)} (恢复 {recovered})")

        print(f"\n重试完成: {retried} 条中恢复 {recovered} 条")

    # 写回
    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(extracts, f, ensure_ascii=False, indent=2)
        print(f"已写入 {OUTPUT_FILE}")

    # 最终统计
    non_empty = sum(1 for r in extracts if r.get("wikipedia_extract"))
    print(f"\n最终统计: 摘要非空 {non_empty}/{len(extracts)} ({non_empty*100//max(len(extracts),1)}%)")


if __name__ == "__main__":
    main()
