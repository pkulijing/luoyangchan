"""
修复 image_url 存储方案：
1. image_url 改为 Supabase Storage 相对路径（如 "1-1.jpg"），不含域名
2. 新增 baike_image_url 字段存百度 CDN 链接
3. 两个字段独立，前端通过配置决定是否 fallback 到百度 CDN

用法:
  uv run python round7/fix_image_urls.py              # 执行
  uv run python round7/fix_image_urls.py --dry-run    # 只显示统计
"""

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
BAIKE_IMAGES = DATA_DIR / "round6" / "baike_images.json"
UPLOAD_PROGRESS = DATA_DIR / "round6" / "upload_progress.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    # 加载百度百科图片映射
    baike_map: dict[str, str] = {}
    if BAIKE_IMAGES.exists():
        with open(BAIKE_IMAGES, encoding="utf-8") as f:
            for item in json.load(f):
                url = item.get("image_url")
                if url:
                    baike_map[item["release_id"]] = url
    print(f"百度百科图片: {len(baike_map)} 条")

    # 加载已上传到 Supabase Storage 的 release_id 列表
    uploaded: set[str] = set()
    if UPLOAD_PROGRESS.exists():
        with open(UPLOAD_PROGRESS, encoding="utf-8") as f:
            uploaded = set(json.load(f))
    print(f"Supabase Storage 已上传: {len(uploaded)} 条")

    # 合并三个 Wikimedia 数据源，确定每个 release_id 的文件扩展名
    wiki_sources = [
        DATA_DIR / "round6" / "wikipedia_images.json",
        DATA_DIR / "round6" / "wikidata_images.json",
        DATA_DIR / "round6" / "commons_images.json",
    ]
    wiki_map: dict[str, str] = {}  # release_id → original URL (for extension detection)
    for path in wiki_sources:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for item in json.load(f):
                url = item.get("image_url")
                if url and item["release_id"] not in wiki_map:
                    wiki_map[item["release_id"]] = url

    def get_ext(url: str) -> str:
        lower = url.lower()
        if lower.endswith(".png"):
            return "png"
        if lower.endswith(".gif"):
            return "gif"
        if lower.endswith(".webp"):
            return "webp"
        return "jpg"

    set_image = 0
    set_baike = 0
    cleared_image = 0

    for site in sites:
        rid = site.get("release_id")
        if not rid:
            continue

        # image_url: Supabase Storage 相对路径（仅已上传的）
        if rid in uploaded:
            ext = get_ext(wiki_map.get(rid, ""))
            site["image_url"] = f"{rid}.{ext}"
            set_image += 1
        else:
            site["image_url"] = None
            if site.get("image_url"):
                cleared_image += 1

        # baike_image_url: 百度 CDN 链接
        baike_url = baike_map.get(rid)
        site["baike_image_url"] = baike_url
        if baike_url:
            set_baike += 1

    print(f"\nimage_url (Supabase Storage): {set_image} 条")
    print(f"baike_image_url (百度 CDN): {set_baike} 条")
    print(f"两者并集: {len(uploaded | set(k for k, v in baike_map.items() if v))} 条有至少一种图片")

    if not args.dry_run:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {MAIN_FILE}")
    else:
        print("\n[dry-run] 未写入")


if __name__ == "__main__":
    main()
