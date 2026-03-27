"""
将 4 种历史分类映射到 6 种现代分类，原始值保存到 original_category。

用法:
  uv run python round7/migrate_category.py              # 执行迁移
  uv run python round7/migrate_category.py --dry-run    # 只显示统计
"""

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
MAIN_FILE = _ROOT / "data" / "heritage_sites_geocoded.json"

CATEGORY_MAP = {
    "革命遗址及革命纪念建筑物": "近现代重要史迹及代表性建筑",
    "古建筑及历史纪念建筑物": "古建筑",
    "石窟寺": "石窟寺及石刻",
    "石刻及其他": "石窟寺及石刻",
}


def main():
    parser = argparse.ArgumentParser(description="Migrate historical categories")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    migrated = 0
    by_old = {}
    for site in sites:
        cat = site.get("category", "")
        if cat in CATEGORY_MAP:
            site["original_category"] = cat
            site["category"] = CATEGORY_MAP[cat]
            migrated += 1
            by_old[cat] = by_old.get(cat, 0) + 1
        else:
            if "original_category" not in site:
                site["original_category"] = None

    print(f"总记录: {len(sites)}")
    print(f"需迁移: {migrated}")
    for old, count in by_old.items():
        print(f"  {old} → {CATEGORY_MAP[old]}: {count} 条")

    if not args.dry_run:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {MAIN_FILE}")
    else:
        print("\n[dry-run] 未写入")


if __name__ == "__main__":
    main()
