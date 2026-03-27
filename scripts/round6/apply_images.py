"""
将百度百科图片 URL 合并到主数据文件，替换之前的 Wikipedia 图片。

策略：
  - 有百度百科图片 → 使用百度百科图片（国内可访问）
  - 无百度百科图片 → 清空 image_url（Wikipedia 图片在国内不可访问，不保留）

用法:
  uv run python round6/apply_images.py              # 合并并写入
  uv run python round6/apply_images.py --dry-run    # 只显示统计，不写入
"""

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
BAIKE_IMAGES_FILE = DATA_DIR / "round6" / "baike_images.json"


def main():
    parser = argparse.ArgumentParser(description="Apply Baike images to main data file")
    parser.add_argument("--dry-run", action="store_true", help="只显示统计，不写入文件")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    with open(BAIKE_IMAGES_FILE, encoding="utf-8") as f:
        baike_images = json.load(f)

    # 建立 release_id → image_url 映射
    baike_map: dict[str, str] = {}
    for item in baike_images:
        url = item.get("image_url")
        if url:
            baike_map[item["release_id"]] = url

    print(f"主数据文件: {len(sites)} 条记录")
    print(f"百度百科图片: {len(baike_images)} 条，其中有图 {len(baike_map)} 条")

    # 统计当前状态
    had_wiki = sum(1 for s in sites if s.get("image_url") and "wikimedia" in s.get("image_url", ""))
    had_other = sum(1 for s in sites if s.get("image_url") and "wikimedia" not in s.get("image_url", ""))
    print(f"\n当前 image_url 状态: Wikipedia {had_wiki} 条, 其他 {had_other} 条")

    updated = 0
    cleared = 0
    for site in sites:
        rid = site.get("release_id")
        if not rid:
            continue

        baike_url = baike_map.get(rid)
        if baike_url:
            site["image_url"] = baike_url
            updated += 1
        else:
            # 清除不可访问的 Wikipedia 图片
            if site.get("image_url"):
                site["image_url"] = None
                cleared += 1

    print(f"\n将设置百度百科图片: {updated} 条")
    print(f"将清除不可用图片: {cleared} 条")

    if not args.dry_run:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {MAIN_FILE}")
    else:
        print("\n[dry-run] 未写入文件")

    # 统计最终覆盖率
    if not args.dry_run:
        total_with_image = updated
    else:
        total_with_image = updated  # dry-run 下也是同样的数
    print(f"\n最终图片覆盖率: {total_with_image}/{len(sites)} ({total_with_image * 100 // len(sites)}%)")


if __name__ == "__main__":
    main()
