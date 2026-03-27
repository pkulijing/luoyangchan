"""
Phase 1: 通过 Wikipedia MediaWiki API 批量采集文保单位主图 URL。

使用 prop=pageimages 接口，每次查询 50 个页面标题，总共约 80 次 API 调用。
图片来自 Wikimedia Commons (upload.wikimedia.org)，开放许可。

用法:
  uv run python round6/fetch_wikipedia_images.py                # 全量采集
  uv run python round6/fetch_wikipedia_images.py --dry-run      # 只处理前 100 条（2 批）
  uv run python round6/fetch_wikipedia_images.py --resume       # 从 checkpoint 续跑
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round6"
OUTPUT_FILE = OUTPUT_DIR / "wikipedia_images.json"
CHECKPOINT_FILE = OUTPUT_DIR / "wikipedia_images_checkpoint.json"

WIKI_API = "https://zh.wikipedia.org/w/api.php"
USER_AGENT = "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
BATCH_SIZE = 50  # Wikipedia API 单次最多 50 个标题
REQUEST_INTERVAL = 0.5  # 每批请求间隔


def extract_title_from_url(url: str) -> str:
    """从 Wikipedia URL 中提取页面标题（URL 解码）。"""
    path = urlparse(url).path
    title = path.split("/wiki/", 1)[-1] if "/wiki/" in path else path.rsplit("/", 1)[-1]
    return unquote(title)


def fetch_batch_images(titles: list[str], session: requests.Session) -> dict[str, str | None]:
    """批量查询页面主图，返回 {title: image_url} 映射。"""
    params = {
        "action": "query",
        "prop": "pageimages",
        "format": "json",
        "formatversion": "2",
        "piprop": "original",
        "titles": "|".join(titles),
    }
    try:
        resp = session.get(WIKI_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  [error] batch request failed: {e}", file=sys.stderr)
        return {t: None for t in titles}

    result: dict[str, str | None] = {}
    for page in data.get("query", {}).get("pages", []):
        title = page.get("title", "")
        original = page.get("original")
        result[title] = original["source"] if original else None

    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch Wikipedia page images for heritage sites")
    parser.add_argument("--dry-run", action="store_true", help="只处理前 2 批（100 条）")
    parser.add_argument("--resume", action="store_true", help="从 checkpoint 续跑")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    # 筛选有 wikipedia_url 的记录，建立 title → release_id 映射
    targets: list[dict] = []
    for s in sites:
        wiki_url = s.get("wikipedia_url")
        if wiki_url:
            targets.append({
                "release_id": s["release_id"],
                "title": extract_title_from_url(wiki_url),
            })
    print(f"共 {len(targets)} 条有 wikipedia_url 的记录")

    # 加载已完成的结果
    done: dict[str, dict] = {}
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done[item["release_id"]] = item
        print(f"从 checkpoint 恢复: {len(done)} 条已完成")

    pending = [t for t in targets if t["release_id"] not in done]
    if args.dry_run:
        pending = pending[:100]
        print(f"[dry-run] 只处理前 {len(pending)} 条")

    print(f"待处理: {len(pending)} 条\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    results = list(done.values())
    success = 0
    no_image = 0

    # 按 BATCH_SIZE 分批
    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    print(f"共 {len(batches)} 批请求\n")

    for batch_idx, batch in enumerate(batches):
        # 建立 title → release_id 映射（同一标题可能对应多条记录）
        title_to_ids: dict[str, list[str]] = {}
        for item in batch:
            title_to_ids.setdefault(item["title"], []).append(item["release_id"])

        unique_titles = list(title_to_ids.keys())
        images = fetch_batch_images(unique_titles, session)

        for title, release_ids in title_to_ids.items():
            # Wikipedia API 返回的 title 可能经过规范化（如空格替换下划线）
            # 用 images.get 时先尝试原始 title，再尝试替换下划线
            image_url = images.get(title) or images.get(title.replace("_", " "))

            for rid in release_ids:
                results.append({
                    "release_id": rid,
                    "image_url": image_url,
                })
                if image_url:
                    success += 1
                else:
                    no_image += 1

        processed = len(done) + (batch_idx + 1) * BATCH_SIZE
        total = len(done) + len(pending)
        print(f"  批次 {batch_idx + 1}/{len(batches)} 完成 "
              f"(累计: 有图 {success}, 无图 {no_image}, "
              f"进度 {min(processed, total)}/{total})")

        # Checkpoint 每 10 批保存一次
        if not args.dry_run and (batch_idx + 1) % 10 == 0:
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
        print(f"\n[dry-run] 完成。有图 {success}, 无图 {no_image}")
        # 打印几个有图的样例
        samples = [r for r in results if r.get("image_url")][:3]
        for s in samples:
            print(json.dumps(s, ensure_ascii=False, indent=2))

    hit_rate = success * 100 // max(success + no_image, 1)
    print(f"\n命中率: {success}/{success + no_image} ({hit_rate}%)")


if __name__ == "__main__":
    main()
