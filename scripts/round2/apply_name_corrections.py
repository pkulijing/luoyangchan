"""
读取 data/encoding_issues.json 中用户填写的 corrected_name，
将修正后的名称写回 data/heritage_sites_geocoded.json。

用法:
  uv run python apply_name_corrections.py           # 预览（dry-run）
  uv run python apply_name_corrections.py --apply   # 实际写入
"""

import json
import argparse
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ISSUES_FILE = DATA_DIR / "encoding_issues.json"
GEOCODED_FILE = DATA_DIR / "heritage_sites_geocoded.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="实际写入修改（默认为 dry-run）")
    args = parser.parse_args()

    with open(ISSUES_FILE, encoding="utf-8") as f:
        issues = json.load(f)

    corrections = {
        item["release_id"]: item["corrected_name"].strip()
        for item in issues
        if item.get("corrected_name", "").strip()
    }

    if not corrections:
        print("encoding_issues.json 中没有填写任何 corrected_name，无需操作。")
        return

    print(f"待应用修正: {len(corrections)} 条")
    for rid, new_name in corrections.items():
        print(f"  {rid}: -> {new_name}")

    if not args.apply:
        print("\n（dry-run 模式，未写入文件。加 --apply 参数以实际写入）")
        return

    with open(GEOCODED_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    applied = 0
    for site in sites:
        rid = site.get("release_id", "")
        if rid in corrections:
            old_name = site["name"]
            site["name"] = corrections[rid]
            print(f"  已修正 {rid}: {old_name!r} -> {site['name']!r}")
            applied += 1

    with open(GEOCODED_FILE, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)

    print(f"\n完成：修正了 {applied} 条记录，已保存至 {GEOCODED_FILE}")


if __name__ == "__main__":
    main()
