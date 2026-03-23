"""
Task A: 将 _geocode_method 标签从 tencent_geocode_gemini 重命名为 tencent_geocode_deepseek

用法: uv run python round4/fix_geocode_method_label.py
"""

import json
from pathlib import Path

MAIN_FILE = Path(__file__).parent.parent.parent / "data" / "heritage_sites_geocoded.json"
OLD_LABEL = "tencent_geocode_gemini"
NEW_LABEL = "tencent_geocode_deepseek"


def main():
    with open(MAIN_FILE, encoding="utf-8") as f:
        records = json.load(f)

    count = 0
    for rec in records:
        if rec.get("_geocode_method") == OLD_LABEL:
            rec["_geocode_method"] = NEW_LABEL
            count += 1

    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"已将 {count} 条记录的 _geocode_method 从 '{OLD_LABEL}' 改为 '{NEW_LABEL}'")


if __name__ == "__main__":
    main()
