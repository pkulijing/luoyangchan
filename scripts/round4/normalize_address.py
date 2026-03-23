"""
Task D: 地址字符串规范化 — 补全缺失的行政层级

问题：很多 address 字段缺少中间行政层级，如"山东省滕州市官桥镇北辛村"缺"枣庄市"。
方案：利用已有的 province/city/district 结构化字段，纯规则拼接。

用法:
  uv run python round4/normalize_address.py             # 执行
  uv run python round4/normalize_address.py --dry-run   # 只检测不写入
"""

import argparse
import json
import re
from pathlib import Path

MAIN_FILE = Path(__file__).parent.parent.parent / "data" / "heritage_sites_geocoded.json"

# 直辖市：province 和 city 同名（或 city 就是 "市辖区"），不重复写
MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}

# 行政区划后缀 pattern，用于从地址中剥离行政前缀
ADMIN_SUFFIXES = re.compile(
    r"^(?:.*?(?:省|市|自治区|自治州|地区|盟|特别行政区|林区|县|区|旗))"
)


def build_standard_prefix(province: str, city: str, district: str) -> str:
    """构建标准行政前缀，避免重复层级。"""
    parts = []

    if province:
        parts.append(province)

    if city:
        # 直辖市：city 可能是 "市辖区" 或与 province 同名
        if province in MUNICIPALITIES:
            if city != "市辖区" and city != province:
                parts.append(city)
        else:
            parts.append(city)

    if district:
        # 避免 district 与 city 同名（县级市）
        if district != city:
            parts.append(district)

    return "".join(parts)


def strip_all_admin_names(address: str, province: str, city: str, district: str) -> str:
    """从地址中去掉所有行政区划名称的出现，保留纯细节部分。

    反复扫描，直到开头不再是已知行政名称为止。
    """
    if not address:
        return ""

    # 要剥离的行政名称列表（按长度降序，优先匹配长的）
    admin_names = sorted(
        [n for n in [province, city, district] if n],
        key=len, reverse=True,
    )

    changed = True
    while changed:
        changed = False
        for name in admin_names:
            if address.startswith(name):
                address = address[len(name):]
                changed = True
                break  # 从头再扫

    return address


def normalize_record(rec: dict) -> str | None:
    """规范化单条记录的 address 字段，返回新地址或 None（无需修改）。"""
    address = rec.get("address") or ""
    province = rec.get("province") or ""
    city = rec.get("city") or ""
    district = rec.get("district") or ""

    # 缺少结构化字段的记录跳过
    if not province:
        return None

    # 构建标准前缀
    standard_prefix = build_standard_prefix(province, city, district)

    # 从原地址中剥离所有行政前缀，提取纯细节部分
    detail = strip_all_admin_names(address, province, city, district)

    # 拼接新地址
    new_address = standard_prefix + detail

    if new_address == address:
        return None

    return new_address


def main():
    parser = argparse.ArgumentParser(description="地址字符串规范化")
    parser.add_argument("--dry-run", action="store_true", help="只检测不写入")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        records = json.load(f)

    modified = 0
    samples = []
    for rec in records:
        if rec.get("_is_parent"):
            continue
        new_address = normalize_record(rec)
        if new_address is not None:
            if len(samples) < 20:
                samples.append({
                    "release_id": rec["release_id"],
                    "name": rec["name"],
                    "old": rec.get("address", ""),
                    "new": new_address,
                })
            if not args.dry_run:
                rec["address"] = new_address
            modified += 1

    if not args.dry_run:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"需修改: {modified} 条")
    if samples:
        print("\n示例修改:")
        for s in samples:
            print(f"  {s['release_id']} {s['name']}:")
            print(f"    旧: {s['old']}")
            print(f"    新: {s['new']}")

    if args.dry_run:
        print("\n（dry-run 模式，未写入文件）")
    else:
        print(f"\n已更新 {MAIN_FILE.name}")


if __name__ == "__main__":
    main()
