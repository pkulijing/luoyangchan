"""
修复图片 URL 数据：
1. 从 baike_images.json 恢复百度图片 URL 到 baike_image_url 字段
2. 将 image_url 中的绝对 localhost URL 转为相对存储路径

用法:
  uv run python fix_image_urls.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
BAIKE_FILE = DATA_DIR / "round6" / "baike_images.json"

SUPABASE_PREFIX = "http://127.0.0.1:54321/storage/v1/object/public/"


def main():
    # 加载主数据
    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)
    print(f"Loaded {len(sites)} sites")

    # 加载百度图片数据
    baike_map: dict[str, str] = {}
    with open(BAIKE_FILE, encoding="utf-8") as f:
        baike_data = json.load(f)
    for item in baike_data:
        if item.get("image_url"):
            baike_map[item["release_id"]] = item["image_url"]
    print(f"Loaded {len(baike_map)} baike image URLs")

    # 统计
    fixed_supabase = 0
    restored_baike = 0

    for site in sites:
        rid = site.get("release_id", "")

        # 1. 修复 image_url：确保是 site-images/ 开头的相对路径
        img = site.get("image_url")
        if img:
            if img.startswith(SUPABASE_PREFIX):
                site["image_url"] = img[len(SUPABASE_PREFIX):]
                fixed_supabase += 1
            elif not img.startswith("site-images/") and not img.startswith("http"):
                site["image_url"] = f"site-images/{img}"
                fixed_supabase += 1

        # 2. 恢复 baike_image_url
        baike_url = baike_map.get(rid)
        site["baike_image_url"] = baike_url
        if baike_url:
            restored_baike += 1

    print(f"Fixed {fixed_supabase} Supabase URLs to relative paths")
    print(f"Restored {restored_baike} baike image URLs")

    # 统计覆盖率
    has_supabase = sum(1 for s in sites if s.get("image_url"))
    has_baike = sum(1 for s in sites if s.get("baike_image_url"))
    has_either = sum(1 for s in sites if s.get("image_url") or s.get("baike_image_url"))
    print(f"\nCoverage:")
    print(f"  Supabase (self-hosted): {has_supabase} ({has_supabase*100//len(sites)}%)")
    print(f"  Baike CDN:              {has_baike} ({has_baike*100//len(sites)}%)")
    print(f"  Either:                 {has_either} ({has_either*100//len(sites)}%)")
    print(f"  Neither:                {len(sites) - has_either}")

    # 写回
    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {MAIN_FILE}")


if __name__ == "__main__":
    main()
