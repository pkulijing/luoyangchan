"""
Phase 3: 通过 Wikimedia Commons 搜索 API 按站点名称搜图。

只对前两步（Wikipedia pageimages + Wikidata P18）未覆盖的站点执行搜索。
使用 action=query&generator=search 在 File 命名空间搜索。

用法:
  uv run python round6/fetch_commons_images.py                # 全量
  uv run python round6/fetch_commons_images.py --dry-run      # 前 30 条
  uv run python round6/fetch_commons_images.py --resume       # 续跑
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round6"
WIKI_IMAGES = OUTPUT_DIR / "wikipedia_images.json"
WIKIDATA_IMAGES = OUTPUT_DIR / "wikidata_images.json"
OUTPUT_FILE = OUTPUT_DIR / "commons_images.json"
CHECKPOINT_FILE = OUTPUT_DIR / "commons_images_checkpoint.json"

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
CHECKPOINT_INTERVAL = 100
REQUEST_INTERVAL = 0.5


def filename_to_commons_url(filename: str) -> str:
    """将 Commons 文件名转换为原图直链。"""
    filename = filename.replace(" ", "_")
    md5 = hashlib.md5(filename.encode("utf-8")).hexdigest()
    a, ab = md5[0], md5[:2]
    encoded = quote(filename)
    return f"https://upload.wikimedia.org/wikipedia/commons/{a}/{ab}/{encoded}"


def search_commons(name: str, session: requests.Session) -> str | None:
    """在 Commons 按名称搜索，返回第一个图片文件的原图 URL。"""
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": name,
        "gsrnamespace": "6",  # File namespace
        "gsrlimit": "3",
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "format": "json",
        "formatversion": "2",
    }
    try:
        resp = session.get(COMMONS_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  [error] {name}: {e}", file=sys.stderr)
        return None

    pages = data.get("query", {}).get("pages", [])
    for page in pages:
        imageinfo = page.get("imageinfo", [{}])
        if imageinfo:
            mime = imageinfo[0].get("mime", "")
            if mime.startswith("image/"):
                url = imageinfo[0].get("url")
                if url:
                    return url
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Search Wikimedia Commons for heritage site images"
    )
    parser.add_argument("--dry-run", action="store_true", help="只处理前 30 条")
    parser.add_argument("--resume", action="store_true", help="从 checkpoint 续跑")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 加载数据
    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    # 加载已有图片的 release_id（不再重复搜索）
    covered: set[str] = set()
    for path in [WIKI_IMAGES, WIKIDATA_IMAGES]:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for item in json.load(f):
                    if item.get("image_url"):
                        covered.add(item["release_id"])

    print(f"已有图片: {len(covered)} 条")

    # 筛选需要搜索的站点
    targets = [
        {"release_id": s["release_id"], "name": s["name"]}
        for s in sites
        if s["release_id"] not in covered
    ]
    print(f"待搜索: {len(targets)} 条")

    # 加载已完成的结果
    done: dict[str, dict] = {}
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done[item["release_id"]] = item
        print(f"从 checkpoint 恢复: {len(done)} 条")

    pending = [t for t in targets if t["release_id"] not in done]
    if args.dry_run:
        pending = pending[:30]
        print(f"[dry-run] 只处理前 {len(pending)} 条")

    print(f"实际待处理: {len(pending)} 条\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    results = list(done.values())
    success = 0
    fail = 0

    for i, item in enumerate(pending):
        image_url = search_commons(item["name"], session)
        results.append({
            "release_id": item["release_id"],
            "image_url": image_url,
        })

        if image_url:
            success += 1
        else:
            fail += 1

        total_done = len(done) + i + 1
        total = len(done) + len(pending)
        if (i + 1) % 50 == 0 or i == len(pending) - 1:
            print(
                f"  进度: {total_done}/{total} "
                f"(有图 {success}, 无图 {fail})"
            )

        if not args.dry_run and (i + 1) % CHECKPOINT_INTERVAL == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  [checkpoint] 已保存 {len(results)} 条")

        time.sleep(REQUEST_INTERVAL)

    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
        print(f"\n完成！{len(results)} 条结果已保存到 {OUTPUT_FILE}")
    else:
        print(f"\n[dry-run] 完成。有图 {success}, 无图 {fail}")
        samples = [r for r in results if r.get("image_url")][:3]
        for s in samples:
            print(json.dumps(s, ensure_ascii=False, indent=2))

    hit_rate = success * 100 // max(success + fail, 1)
    print(f"\n命中率: {success}/{success + fail} ({hit_rate}%)")


if __name__ == "__main__":
    main()
