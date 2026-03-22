"""
第三轮数据清洗 - Phase 4: 更新 fallback 列表

重新生成 data/geocode_fallback_list.json，
列出所有仍为低精度坐标的记录（geocode/kept_original 方法）。

用法:
  uv run python update_fallback_list.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_FILE = DATA_DIR / "geocode_fallback_list.json"

# 视为低精度的 geocode 方法
LOW_PRECISION_METHODS = {"geocode", "kept_original", "kept_original_r3", "tencent_geocode"}


def main():
    with open(MAIN_FILE, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    fallback = []
    for rec in records:
        if rec.get("_is_parent"):
            continue
        method = rec.get("_geocode_method", "")
        if method in LOW_PRECISION_METHODS or rec.get("latitude") is None:
            fallback.append({
                "release_id": rec["release_id"],
                "name": rec["name"],
                "release_address": rec.get("release_address"),
                "province": rec.get("province"),
                "city": rec.get("city"),
                "latitude": rec.get("latitude"),
                "longitude": rec.get("longitude"),
                "_geocode_method": method,
            })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(fallback, f, ensure_ascii=False, indent=2)

    print(f"已更新 {OUTPUT_FILE.name}: {len(fallback)} 条低精度记录")

    from collections import Counter
    method_dist = Counter(r["_geocode_method"] for r in fallback)
    for method, cnt in sorted(method_dist.items(), key=lambda x: -x[1]):
        print(f"  {method}: {cnt}")


if __name__ == "__main__":
    main()
