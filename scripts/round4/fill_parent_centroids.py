"""
Task B: 为父记录填充子记录坐标质心

找到所有 _is_parent: true 的记录，计算其子记录坐标的算术平均值作为父记录坐标。

用法: uv run python round4/fill_parent_centroids.py
"""

import json
from pathlib import Path

MAIN_FILE = Path(__file__).parent.parent.parent / "data" / "heritage_sites_geocoded.json"


def main():
    with open(MAIN_FILE, encoding="utf-8") as f:
        records = json.load(f)

    # 建立 parent_release_id → [child records] 映射
    children_map: dict[str, list[dict]] = {}
    for rec in records:
        pid = rec.get("_parent_release_id")
        if pid:
            children_map.setdefault(pid, []).append(rec)

    updated = 0
    for rec in records:
        if not rec.get("_is_parent"):
            continue

        rid = rec["release_id"]
        children = children_map.get(rid, [])
        coords = [
            (c["latitude"], c["longitude"])
            for c in children
            if c.get("latitude") is not None and c.get("longitude") is not None
        ]

        if not coords:
            print(f"  警告: {rid} {rec['name']} 无有效子记录坐标，跳过")
            continue

        avg_lat = round(sum(c[0] for c in coords) / len(coords), 6)
        avg_lng = round(sum(c[1] for c in coords) / len(coords), 6)

        rec["latitude"] = avg_lat
        rec["longitude"] = avg_lng
        rec["_geocode_method"] = "centroid"
        updated += 1
        print(f"  {rid} {rec['name']}: {len(coords)} 个子记录 → ({avg_lat}, {avg_lng})")

    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\n已更新 {updated} 条父记录的坐标")


if __name__ == "__main__":
    main()
