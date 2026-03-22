"""
第三轮数据清洗 - Phase 3: 验证数据质量

对 heritage_sites_geocoded.json 进行全面质量检查，
与第三轮清洗前的问题对比，输出改善情况。

产出：
  data/round3/verification_report.json  — 详细报告
  data/round3/still_problematic.json    — 仍有问题的记录（供人工处理）

用法:
  uv run python verify_round3.py
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

from geocode_utils import extract_expected_province, is_province_ok

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND3_DIR = DATA_DIR / "round3"
ORIGINAL_NEEDS = ROUND3_DIR / "needs_regeocode.json"
OUTPUT_REPORT = ROUND3_DIR / "verification_report.json"
OUTPUT_STILL_BAD = ROUND3_DIR / "still_problematic.json"


def main():
    with open(MAIN_FILE, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    original_count = len(records)
    print(f"总记录数: {original_count}")

    # --- geocode method 分布 ---
    method_count = Counter(r.get("_geocode_method") for r in records)
    print("\n【geocode method 分布】")
    for method, cnt in sorted(method_count.items(), key=lambda x: -x[1]):
        print(f"  {method}: {cnt}")

    # --- 省份不匹配 ---
    mismatch = []
    for rec in records:
        if rec.get("_is_parent"):
            continue
        method = rec.get("_geocode_method", "")
        if not method or "tencent" not in method and "poi" not in method:
            continue
        expected = extract_expected_province(rec.get("release_address", ""))
        actual = rec.get("province")
        if expected and not is_province_ok(expected, actual):
            mismatch.append({
                "release_id": rec["release_id"],
                "name": rec["name"],
                "expected_province": expected,
                "actual_province": actual,
                "_geocode_method": method,
                "release_address": rec.get("release_address"),
            })
    print(f"\n【省份不匹配】: {len(mismatch)} 条")
    for rec in mismatch[:10]:
        print(f"  {rec['release_id']} {rec['name']}: 预期={rec['expected_province']}, 实际={rec['actual_province']}")

    # --- 重复坐标 ---
    coord_groups: dict[tuple, list] = defaultdict(list)
    for rec in records:
        if rec.get("_is_parent") or rec.get("latitude") is None:
            continue
        coord_groups[(rec["latitude"], rec["longitude"])].append(rec)

    dup_groups = {k: v for k, v in coord_groups.items() if len(v) > 1}
    dup_records = sum(len(v) for v in dup_groups.values())
    dup_poi_groups = sum(
        1 for v in dup_groups.values()
        if any(r.get("_geocode_method") and "poi" in r.get("_geocode_method", "") for r in v)
    )
    print(f"\n【重复坐标】: {len(dup_groups)} 组（{dup_records} 条记录）")
    print(f"  其中含 POI 方法的可疑重复组: {dup_poi_groups} 组")

    # 展示 POI 重复组（更需要关注）
    poi_dup_examples = [
        (k, v) for k, v in dup_groups.items()
        if any(r.get("_geocode_method") and "poi" in r.get("_geocode_method", "") for r in v)
    ]
    if poi_dup_examples:
        print("  POI 重复组示例（前5组）:")
        for (lat, lng), members in sorted(poi_dup_examples, key=lambda x: -len(x[1]))[:5]:
            print(f"    ({lat}, {lng}) × {len(members)}:")
            for m in members:
                print(f"      {m['release_id']} {m['name']} [{m.get('_geocode_method')}]")

    # --- 无坐标记录（非父记录）---
    no_coords = [
        r for r in records
        if not r.get("_is_parent") and r.get("latitude") is None
    ]
    print(f"\n【无坐标记录（非父）】: {len(no_coords)} 条")
    for r in no_coords[:10]:
        print(f"  {r['release_id']} {r['name']}")

    # --- 父子关系一致性 ---
    parent_ids = {r["release_id"] for r in records if r.get("_is_parent")}
    orphan_children = [
        r for r in records
        if r.get("_parent_release_id") and r["_parent_release_id"] not in parent_ids
    ]
    parents_with_children = {r["_parent_release_id"] for r in records if r.get("_parent_release_id")}
    childless_parents = [r for r in records if r.get("_is_parent") and r["release_id"] not in parents_with_children]
    print(f"\n【父子关系一致性】")
    print(f"  父记录数: {len(parent_ids)}")
    print(f"  孤儿子记录（找不到父）: {len(orphan_children)}")
    print(f"  无子女的父记录: {len(childless_parents)}")
    for r in childless_parents:
        print(f"    {r['release_id']} {r['name']}")

    # --- 对比原始问题清单 ---
    if ORIGINAL_NEEDS.exists():
        with open(ORIGINAL_NEEDS, encoding="utf-8") as f:
            original_needs: list[dict] = json.load(f)
        original_ids = {r["release_id"] for r in original_needs}
        # 检查原来有问题的记录现在是否改善
        improved = 0
        still_bad = []
        for orig in original_needs:
            rid = orig["release_id"]
            if rid not in {r["release_id"] for r in records}:
                continue  # 记录可能已被替换（父子拆分）
            rec = next((r for r in records if r["release_id"] == rid), None)
            if not rec:
                continue
            new_method = rec.get("_geocode_method", "")
            if "tencent" in new_method or new_method in ("manual",):
                improved += 1
            else:
                still_bad.append({
                    "release_id": rid,
                    "name": rec["name"],
                    "release_address": rec.get("release_address"),
                    "province": rec.get("province"),
                    "_geocode_method": new_method,
                    "original_problem_types": orig.get("problem_types", []),
                    "latitude": rec.get("latitude"),
                    "longitude": rec.get("longitude"),
                })

        print(f"\n【vs 清洗前】")
        print(f"  原问题记录: {len(original_needs)} 条")
        print(f"  已改善（使用腾讯/手动）: {improved} 条")
        print(f"  仍有问题（geocode/poi_search/kept）: {len(still_bad)} 条")

        with open(OUTPUT_STILL_BAD, "w", encoding="utf-8") as f:
            json.dump(still_bad, f, ensure_ascii=False, indent=2)
        print(f"  → 已写出 {OUTPUT_STILL_BAD.name}: {len(still_bad)} 条（供人工处理）")

    # --- 输出报告 ---
    report = {
        "total_records": original_count,
        "geocode_method_distribution": dict(method_count),
        "province_mismatch_count": len(mismatch),
        "province_mismatch_records": mismatch[:50],
        "duplicate_coord_groups": len(dup_groups),
        "duplicate_coord_records": dup_records,
        "duplicate_poi_groups": dup_poi_groups,
        "no_coords_non_parent": len(no_coords),
        "orphan_children": len(orphan_children),
        "childless_parents": len(childless_parents),
    }

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n已写出验证报告: {OUTPUT_REPORT.name}")

    # 简要结论
    print("\n【结论】")
    issues = []
    if len(mismatch) > 0:
        issues.append(f"{len(mismatch)} 条省份不匹配")
    if dup_poi_groups > 0:
        issues.append(f"{dup_poi_groups} 组 POI 重复坐标")
    if len(no_coords) > 0:
        issues.append(f"{len(no_coords)} 条无坐标")
    if issues:
        print(f"  仍有问题: {', '.join(issues)}")
        print(f"  请查看 still_problematic.json，考虑人工修正")
    else:
        print(f"  数据质量良好，可以 seed 数据库")


if __name__ == "__main__":
    main()
