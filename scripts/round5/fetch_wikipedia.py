"""
Phase 1: 从中文 Wikipedia 采集文保单位摘要内容。

用法:
  uv run python round5/fetch_wikipedia.py                # 全量采集
  uv run python round5/fetch_wikipedia.py --dry-run      # 只处理前 10 条
  uv run python round5/fetch_wikipedia.py --resume       # 从 checkpoint 续跑
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
import zhconv

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round5"
OUTPUT_FILE = OUTPUT_DIR / "wikipedia_extracts.json"
CHECKPOINT_FILE = OUTPUT_DIR / "wikipedia_checkpoint.json"

WIKI_REST_API = "https://zh.wikipedia.org/api/rest_v1/page/summary"
USER_AGENT = "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
CHECKPOINT_INTERVAL = 100
REQUEST_INTERVAL = 0.3  # ~200 req/min


def extract_title_from_url(url: str) -> str:
    """从 Wikipedia URL 中提取页面标题（URL 解码）。"""
    path = urlparse(url).path
    # /wiki/Title → Title
    title = path.split("/wiki/", 1)[-1] if "/wiki/" in path else path.rsplit("/", 1)[-1]
    return unquote(title)


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
        return {
            "wikipedia_extract": zhconv.convert(extract, "zh-cn"),
            "wikipedia_description": zhconv.convert(description, "zh-cn"),
        }
    except requests.RequestException as e:
        print(f"  [error] {title}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Fetch Wikipedia summaries for heritage sites")
    parser.add_argument("--dry-run", action="store_true", help="只处理前 10 条")
    parser.add_argument("--resume", action="store_true", help="从 checkpoint 续跑")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    # 筛选有 wikipedia_url 的记录
    targets = [s for s in sites if s.get("wikipedia_url")]
    print(f"共 {len(targets)} 条有 wikipedia_url 的记录")

    # 加载已完成的结果
    done: dict[str, dict] = {}
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done[item["release_id"]] = item
        print(f"从 checkpoint 恢复: {len(done)} 条已完成")

    pending = [s for s in targets if s["release_id"] not in done]
    if args.dry_run:
        pending = pending[:10]
        print(f"[dry-run] 只处理前 {len(pending)} 条")

    print(f"待处理: {len(pending)} 条\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.headers["Accept-Language"] = "zh-cn"

    results = list(done.values())
    success = 0
    fail = 0

    for i, site in enumerate(pending):
        release_id = site["release_id"]
        title = extract_title_from_url(site["wikipedia_url"])

        summary = fetch_summary(title, session)
        if summary:
            results.append({"release_id": release_id, **summary})
            success += 1
        else:
            results.append({
                "release_id": release_id,
                "wikipedia_extract": "",
                "wikipedia_description": "",
            })
            fail += 1

        # 进度
        total_done = len(done) + i + 1
        total = len(done) + len(pending)
        if (i + 1) % 50 == 0 or i == len(pending) - 1:
            print(f"  进度: {total_done}/{total} (成功 {success}, 失败 {fail})")

        # Checkpoint
        if not args.dry_run and (i + 1) % CHECKPOINT_INTERVAL == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  [checkpoint] 已保存 {len(results)} 条")

        time.sleep(REQUEST_INTERVAL)

    # 最终输出
    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
        print(f"\n完成！{len(results)} 条结果已保存到 {OUTPUT_FILE}")
    else:
        print(f"\n[dry-run] 完成。成功 {success}, 失败 {fail}")
        if results:
            print(json.dumps(results[-1], ensure_ascii=False, indent=2))

    # 统计
    non_empty = sum(1 for r in results if r.get("wikipedia_extract"))
    print(f"\n摘要非空: {non_empty}/{len(results)} ({non_empty*100//max(len(results),1)}%)")


if __name__ == "__main__":
    main()
