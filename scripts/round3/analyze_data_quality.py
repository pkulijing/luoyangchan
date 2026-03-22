"""
第三轮数据清洗 - Phase 0: 数据质量全面诊断

扫描 heritage_sites_geocoded.json，输出三类问题列表：
  1. needs_regeocode.json    — 需要重新 geocoding 的记录
  2. multi_address_candidates.json — 多地址候选（可能需要拆分的条目）
  3. duplicate_coord_groups.json   — 重复坐标分组
  4. quality_summary.txt           — 汇总统计

用法:
  uv run python analyze_data_quality.py
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from geocode_utils import ALL_PROVINCES, extract_expected_province, is_province_ok as is_province_match_ok

DATA_DIR = Path(__file__).parent.parent.parent / "data"
INPUT_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round3"


# ---------------------------------------------------------------------------
# 多地址候选检测
# ---------------------------------------------------------------------------

# 地名后缀（用于判断分段是否为独立地点）
LOCATION_SUFFIXES = re.compile(
    r"(省|自治区|市|县|区|旗|盟|州|镇|乡|村)$"
)

# 独立地名的常见模式（省/市/县/区/旗 结尾，或是已知省份名）
PROVINCE_SHORT = [p[:2] for p in ALL_PROVINCES]


def parse_location_segments(release_address: str) -> list[str]:
    """
    将 release_address 按 、 拆分，过滤掉非独立地名的短段。
    避免"西、南、中沙群岛"这类复合地名被误判。
    """
    if not release_address or "、" not in release_address:
        return []

    raw_segments = [s.strip() for s in release_address.split("、")]
    segments = []

    for seg in raw_segments:
        if not seg:
            continue
        # 短段（≤3字）且不以地名后缀结尾，可能是复合名的一部分
        if len(seg) <= 3 and not LOCATION_SUFFIXES.search(seg):
            continue
        segments.append(seg)

    return segments


def detect_multi_address(record: dict) -> dict | None:
    """
    检测是否为多地址候选。返回分析结果或 None。

    逻辑：
    - release_address 按 、 分割，每段检测是否以地名后缀结尾
    - 识别省份数、地点数
    - 按置信度分级：strong / borderline
    """
    release_address = record.get("release_address", "")
    if not release_address or "、" not in release_address:
        return None

    # 已是子记录或已拆分的父记录，不再检测
    if record.get("_parent_release_id"):
        return None
    if record.get("_is_parent"):
        return None

    segments = parse_location_segments(release_address)
    if len(segments) < 2:
        return None

    # 补全省份前缀：如 "陕西省富平县、蒲城县" 中，"蒲城县" 继承 "陕西省"
    provinces_found = set()
    last_province = None
    enriched_segments = []
    for seg in segments:
        seg_province = extract_expected_province(seg)
        if seg_province:
            last_province = seg_province
        if last_province:
            provinces_found.add(last_province)
        enriched_segments.append(seg)

    # 按置信度分级
    cross_province = len(provinces_found) >= 2
    location_count = len(enriched_segments)

    if cross_province:
        confidence = "strong"
    elif location_count >= 3:
        confidence = "strong"
    elif location_count == 2:
        confidence = "borderline"
    else:
        return None

    return {
        "release_id": record["release_id"],
        "name": record["name"],
        "release_address": release_address,
        "parsed_segments": enriched_segments,
        "location_count": location_count,
        "cross_province": cross_province,
        "provinces_found": sorted(provinces_found),
        "confidence": confidence,
        "_geocode_method": record.get("_geocode_method"),
        "_is_parent": record.get("_is_parent", False),
    }


# ---------------------------------------------------------------------------
# 重复坐标检测
# ---------------------------------------------------------------------------

def find_duplicate_coords(records: list[dict]) -> list[dict]:
    """找出所有经纬度完全相同的记录组。"""
    coord_groups: dict[tuple, list] = defaultdict(list)
    for rec in records:
        lat = rec.get("latitude")
        lng = rec.get("longitude")
        if lat is None or lng is None:
            continue
        if rec.get("_is_parent"):
            continue
        coord_groups[(lat, lng)].append(rec)

    result = []
    for (lat, lng), members in coord_groups.items():
        if len(members) < 2:
            continue
        methods = [m.get("_geocode_method", "unknown") for m in members]
        method_counts = dict(Counter(methods))
        all_geocode = all(m in ("geocode", "kept_original") for m in methods)
        has_poi = any(m and "poi" in m for m in methods)
        result.append({
            "latitude": lat,
            "longitude": lng,
            "count": len(members),
            "method_counts": method_counts,
            "all_geocode_fallback": all_geocode,
            "has_poi_method": has_poi,
            "members": [
                {
                    "release_id": m["release_id"],
                    "name": m["name"],
                    "province": m.get("province"),
                    "release_address": m.get("release_address"),
                    "_geocode_method": m.get("_geocode_method"),
                }
                for m in members
            ],
        })

    result.sort(key=lambda x: (-x["count"], x["has_poi_method"]))
    return result


# ---------------------------------------------------------------------------
# 需要重新 geocoding 的记录
# ---------------------------------------------------------------------------

def collect_needs_regeocode(records: list[dict], dup_groups: list[dict]) -> list[dict]:
    """
    收集所有需要重新 geocoding 的记录：
    1. _geocode_method == "geocode" (低精度 fallback)
    2. POI 省份不匹配
    3. 属于纯 geocode-fallback 的重复坐标组（不包含 poi_search 的组）
       注：has_poi_method 的重复组单独标记，但也纳入待修复
    """
    # 构建重复坐标集合
    dup_poi_release_ids: set[str] = set()
    dup_geocode_release_ids: set[str] = set()
    for group in dup_groups:
        for m in group["members"]:
            if group["has_poi_method"]:
                dup_poi_release_ids.add(m["release_id"])
            else:
                dup_geocode_release_ids.add(m["release_id"])

    result = []
    seen: set[str] = set()

    for rec in records:
        if rec.get("_is_parent"):
            continue
        rid = rec["release_id"]
        method = rec.get("_geocode_method")
        problems = []

        # 问题1: geocode fallback
        if method == "geocode":
            problems.append("geocode_fallback")

        # 问题2: POI 省份不匹配
        if method and "poi" in method:
            expected_prov = extract_expected_province(rec.get("release_address", ""))
            actual_prov = rec.get("province")
            if not is_province_match_ok(expected_prov, actual_prov):
                problems.append("poi_province_mismatch")

        # 问题3: 重复坐标（POI 搜到了同一个地方）
        if rid in dup_poi_release_ids and "poi_province_mismatch" not in problems:
            problems.append("poi_duplicate")

        if not problems:
            continue
        if rid in seen:
            continue
        seen.add(rid)

        result.append({
            "release_id": rid,
            "name": rec["name"],
            "release_address": rec.get("release_address"),
            "province": rec.get("province"),
            "city": rec.get("city"),
            "district": rec.get("district"),
            "latitude": rec.get("latitude"),
            "longitude": rec.get("longitude"),
            "_geocode_method": method,
            "problem_types": problems,
        })

    return result


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"读取数据: {INPUT_FILE}")
    with open(INPUT_FILE, encoding="utf-8") as f:
        records: list[dict] = json.load(f)
    print(f"共 {len(records)} 条记录")

    # --- 1. 多地址候选 ---
    print("\n--- 检测多地址候选 ---")
    multi_candidates = []
    for rec in records:
        result = detect_multi_address(rec)
        if result:
            multi_candidates.append(result)

    strong_count = sum(1 for c in multi_candidates if c["confidence"] == "strong")
    borderline_count = sum(1 for c in multi_candidates if c["confidence"] == "borderline")
    print(f"  多地址候选: {len(multi_candidates)} 条（strong: {strong_count}, borderline: {borderline_count}）")

    # --- 2. 重复坐标 ---
    print("\n--- 检测重复坐标 ---")
    dup_groups = find_duplicate_coords(records)
    dup_all_geocode = sum(1 for g in dup_groups if g["all_geocode_fallback"])
    dup_has_poi = sum(1 for g in dup_groups if g["has_poi_method"])
    dup_total_records = sum(g["count"] for g in dup_groups)
    print(f"  重复坐标组: {len(dup_groups)} 组（{dup_total_records} 条记录）")
    print(f"    - 全为 geocode fallback: {dup_all_geocode} 组")
    print(f"    - 含 poi_search（搜错了）: {dup_has_poi} 组")

    # --- 3. 需要重新 geocoding ---
    print("\n--- 收集需要重新 geocoding 的记录 ---")
    needs_regeocode = collect_needs_regeocode(records, dup_groups)

    by_type: dict[str, int] = Counter()
    for rec in needs_regeocode:
        for pt in rec["problem_types"]:
            by_type[pt] += 1
    print(f"  总计: {len(needs_regeocode)} 条")
    for pt, cnt in sorted(by_type.items()):
        print(f"    - {pt}: {cnt} 条")

    # 省份不匹配详情
    mismatch_records = [r for r in needs_regeocode if "poi_province_mismatch" in r["problem_types"]]
    if mismatch_records:
        print(f"\n  省份不匹配示例（前10条）:")
        for rec in mismatch_records[:10]:
            expected = extract_expected_province(rec.get("release_address", ""))
            print(f"    {rec['release_id']} {rec['name']}: 预期={expected}, 实际={rec['province']}")

    # --- 写出文件 ---
    print("\n--- 写出分析结果 ---")

    out_multi = OUTPUT_DIR / "multi_address_candidates.json"
    with open(out_multi, "w", encoding="utf-8") as f:
        json.dump(multi_candidates, f, ensure_ascii=False, indent=2)
    print(f"  {out_multi.name}: {len(multi_candidates)} 条")

    out_dup = OUTPUT_DIR / "duplicate_coord_groups.json"
    with open(out_dup, "w", encoding="utf-8") as f:
        json.dump(dup_groups, f, ensure_ascii=False, indent=2)
    print(f"  {out_dup.name}: {len(dup_groups)} 组")

    out_regeocode = OUTPUT_DIR / "needs_regeocode.json"
    with open(out_regeocode, "w", encoding="utf-8") as f:
        json.dump(needs_regeocode, f, ensure_ascii=False, indent=2)
    print(f"  {out_regeocode.name}: {len(needs_regeocode)} 条")

    # 汇总统计
    summary_lines = [
        "第三轮数据清洗 — 数据质量分析报告",
        "=" * 50,
        f"总记录数: {len(records)}",
        "",
        "【多地址候选】",
        f"  共 {len(multi_candidates)} 条候选（含误判）",
        f"  strong: {strong_count} 条（多省份或 ≥3 个子地点）",
        f"  borderline: {borderline_count} 条（同省 2 个子地点）",
        "",
        "【重复坐标】",
        f"  共 {len(dup_groups)} 组（{dup_total_records} 条记录）",
        f"  geocode fallback 导致（预期通过重新 geocoding 自动解决）: {dup_all_geocode} 组",
        f"  poi_search 错误（需专门修复）: {dup_has_poi} 组",
        "",
        "【需要重新 geocoding】",
        f"  总计: {len(needs_regeocode)} 条",
    ]
    for pt, cnt in sorted(by_type.items()):
        summary_lines.append(f"  - {pt}: {cnt} 条")
    summary_lines += [
        "",
        "【操作建议】",
        "1. 审查 multi_address_candidates.json，运行 generate_gemini_prompt_multi_address.py",
        "2. 将 Gemini 结果保存为 data/round3/gemini_multi_address_result.json",
        "3. 运行 apply_multi_address_split.py --apply 执行拆分",
        "4. 运行 generate_gemini_prompt_geocode.py 生成 geocoding prompt",
        "5. 将 Gemini 结果保存为 data/round3/gemini_geocode_result.json",
        "6. 运行 geocode_tencent.py 执行重新编码",
        "7. 运行 verify_round3.py 验证结果",
    ]

    out_summary = OUTPUT_DIR / "quality_summary.txt"
    out_summary.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"  {out_summary.name}: 汇总报告")

    print(f"\n所有文件已保存到 {OUTPUT_DIR}/")

    # 打印 strong 多地址候选供预览
    strong_candidates = [c for c in multi_candidates if c["confidence"] == "strong"]
    if strong_candidates:
        print(f"\n【Strong 多地址候选预览（{len(strong_candidates)} 条）】")
        for c in strong_candidates:
            cross = "（跨省）" if c["cross_province"] else ""
            print(f"  {c['release_id']}: {c['name']}{cross}")
            print(f"    地址: {c['release_address'][:80]}")


if __name__ == "__main__":
    main()
