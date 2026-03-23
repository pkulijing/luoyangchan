"""
Task F: 全量排查重复GPS坐标

按 (latitude, longitude) 分组，标记 ≥2 条的组。

用法: uv run python round4/audit_duplicate_coords.py
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND4_DIR = DATA_DIR / "round4"


def main():
    with open(MAIN_FILE, encoding="utf-8") as f:
        records = json.load(f)

    ROUND4_DIR.mkdir(parents=True, exist_ok=True)

    # 按坐标分组（排除父记录和无坐标记录）
    coord_groups: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for rec in records:
        if rec.get("_is_parent"):
            continue
        lat = rec.get("latitude")
        lng = rec.get("longitude")
        if lat is None or lng is None:
            continue
        key = (round(lat, 6), round(lng, 6))
        coord_groups[key].append(rec)

    # 筛选重复组
    duplicates = []
    for (lat, lng), members in coord_groups.items():
        if len(members) < 2:
            continue
        duplicates.append({
            "latitude": lat,
            "longitude": lng,
            "count": len(members),
            "members": [
                {
                    "release_id": m["release_id"],
                    "name": m["name"],
                    "province": m.get("province", ""),
                    "address": m.get("address", ""),
                    "_geocode_method": m.get("_geocode_method", ""),
                }
                for m in members
            ],
        })

    # 按组大小降序排序
    duplicates.sort(key=lambda g: -g["count"])

    # 写 JSON
    output_json = ROUND4_DIR / "audit_duplicate_coords.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(duplicates, f, ensure_ascii=False, indent=2)

    # 统计
    total_records = sum(g["count"] for g in duplicates)
    size_counter = Counter(g["count"] for g in duplicates)

    # 方法组合统计
    method_combos = Counter()
    for g in duplicates:
        methods = tuple(sorted(set(m["_geocode_method"] for m in g["members"])))
        method_combos[methods] += 1

    # 写汇总报告
    output_md = ROUND4_DIR / "audit_duplicate_coords_summary.md"
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# 重复坐标审计报告\n\n")
        f.write(f"**重复组数**: {len(duplicates)}\n")
        f.write(f"**涉及记录**: {total_records} 条\n\n")

        f.write("## 按组大小分布\n\n")
        f.write("| 组大小 | 组数 |\n|--------|------|\n")
        for size, count in sorted(size_counter.items()):
            f.write(f"| {size} 条 | {count} |\n")

        f.write("\n## 按 geocode 方法组合\n\n")
        f.write("| 方法组合 | 组数 |\n|----------|------|\n")
        for methods, count in method_combos.most_common():
            f.write(f"| {', '.join(methods)} | {count} |\n")

        f.write("\n## 最大的 10 组\n\n")
        for i, g in enumerate(duplicates[:10]):
            f.write(f"### 第{i+1}组 ({g['count']} 条) — ({g['latitude']}, {g['longitude']})\n\n")
            f.write("| release_id | 名称 | 省份 | 方法 |\n|------------|------|------|------|\n")
            for m in g["members"]:
                f.write(f"| {m['release_id']} | {m['name']} | {m['province']} | {m['_geocode_method']} |\n")
            f.write("\n")

    print(f"重复坐标审计完成: {len(duplicates)} 组，{total_records} 条记录")
    print(f"  → {output_json.name}")
    print(f"  → {output_md.name}")
    print(f"\n按组大小:")
    for size, count in sorted(size_counter.items()):
        print(f"  {size} 条: {count} 组")


if __name__ == "__main__":
    main()
