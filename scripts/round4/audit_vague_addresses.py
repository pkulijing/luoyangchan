"""
Task E: 全量排查模糊/低精度地址

检测标准:
  - address 为空或只到县/区级（无乡镇/街道/村级细节）
  - _geocode_method 为已知低精度方法
  - _geocode_reliability < 5

用法: uv run python round4/audit_vague_addresses.py
"""

import json
import re
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND4_DIR = DATA_DIR / "round4"

# 已知低精度 geocode 方法
LOW_PREC_METHODS = {"geocode", "kept_original"}


def is_vague_address(address: str, province: str, city: str) -> bool:
    """判断地址是否只到县/区级。

    从左往右：去掉省（自治区）和市，找到第一个"区"或"县"字，
    如果后面还有内容就是精确地址，没有就是模糊的。
    """
    if not address:
        return True

    s = address
    # 去掉省/自治区
    if province and s.startswith(province):
        s = s[len(province):]
    # 去掉市
    if city and s.startswith(city):
        s = s[len(city):]

    # 找第一个"区"、"县"或"市"（县级市）
    for i, ch in enumerate(s):
        if ch in "区县市":
            return len(s[i + 1:]) == 0

    # 没有区/县字，看整个地址去掉省市后有没有内容
    return len(s) == 0


def main():
    with open(MAIN_FILE, encoding="utf-8") as f:
        records = json.load(f)

    ROUND4_DIR.mkdir(parents=True, exist_ok=True)

    flagged = []
    for rec in records:
        if rec.get("_is_parent"):
            continue

        reasons = []
        address = rec.get("address") or ""
        district = rec.get("district") or ""
        method = rec.get("_geocode_method") or ""
        reliability = rec.get("_geocode_reliability")

        province = rec.get("province") or ""
        city = rec.get("city") or ""

        if not address:
            reasons.append("地址为空")
        elif is_vague_address(address, province, city):
            reasons.append("地址只到县/区级")

        if method in LOW_PREC_METHODS:
            reasons.append(f"低精度方法({method})")

        if reliability is not None and reliability < 5:
            reasons.append(f"可靠度低({reliability})")

        if reasons:
            flagged.append({
                "release_id": rec["release_id"],
                "name": rec["name"],
                "province": rec.get("province", ""),
                "city": rec.get("city", ""),
                "district": district,
                "address": address,
                "_geocode_method": method,
                "_geocode_reliability": reliability,
                "reasons": reasons,
            })

    # 按省份排序
    flagged.sort(key=lambda r: (r["province"], r["release_id"]))

    # 写 JSON
    output_json = ROUND4_DIR / "audit_vague_addresses.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(flagged, f, ensure_ascii=False, indent=2)

    # 写汇总报告
    by_province = Counter(r["province"] for r in flagged)
    by_method = Counter(r["_geocode_method"] for r in flagged)
    by_reason = Counter()
    for r in flagged:
        for reason in r["reasons"]:
            by_reason[reason.split("(")[0]] += 1

    output_md = ROUND4_DIR / "audit_vague_addresses_summary.md"
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# 模糊地址审计报告\n\n")
        f.write(f"**总计**: {len(flagged)} 条记录\n\n")

        f.write("## 按原因分类\n\n")
        f.write("| 原因 | 数量 |\n|------|------|\n")
        for reason, count in by_reason.most_common():
            f.write(f"| {reason} | {count} |\n")

        f.write("\n## 按省份分布\n\n")
        f.write("| 省份 | 数量 |\n|------|------|\n")
        for prov, count in by_province.most_common():
            f.write(f"| {prov or '(空)'} | {count} |\n")

        f.write("\n## 按 geocode 方法\n\n")
        f.write("| 方法 | 数量 |\n|------|------|\n")
        for method, count in by_method.most_common():
            f.write(f"| {method or '(空)'} | {count} |\n")

    print(f"模糊地址审计完成: {len(flagged)} 条")
    print(f"  → {output_json.name}")
    print(f"  → {output_md.name}")
    print(f"\n按原因:")
    for reason, count in by_reason.most_common():
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
