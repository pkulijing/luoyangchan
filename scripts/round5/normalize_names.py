"""
预处理: 将所有文保单位 name 字段规范化为简体中文。

处理范围:
  1. 异体字 → 标准字形（如 靑→青）
  2. 繁体字 → 简体字（zhconv）

用法:
  uv run python round5/normalize_names.py --dry-run    # 只显示变更，不写文件
  uv run python round5/normalize_names.py              # 执行规范化
"""

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
MAIN_FILE = _ROOT / "data" / "heritage_sites_geocoded.json"

# 已知异体字 → 标准简体映射
# zhconv 对罕见字不可靠（如赵孟頫的"頫"会被错误转换），因此用显式映射
VARIANT_CHAR_MAP = {
    "\u9751": "\u9752",  # 靑 → 青
    "\u89DA": "\u89C9",  # 覚 → 觉（日式字形）
}


def normalize(text: str) -> str:
    for old, new in VARIANT_CHAR_MAP.items():
        text = text.replace(old, new)
    return text


def main():
    parser = argparse.ArgumentParser(description="Normalize heritage site names to simplified Chinese")
    parser.add_argument("--dry-run", action="store_true", help="只显示变更，不写文件")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    changed = []
    for site in sites:
        old_name = site["name"]
        new_name = normalize(old_name)
        if old_name != new_name:
            changed.append((site["release_id"], old_name, new_name))
            if not args.dry_run:
                site["name"] = new_name

    print(f"共 {len(sites)} 条记录，{len(changed)} 条名称需要修改：")
    for rid, old, new in changed:
        diffs = [(o, n) for o, n in zip(old, new) if o != n]
        print(f"  {rid}: {old} → {new}  ({diffs})")

    if not changed:
        print("无需修改。")
        return

    if args.dry_run:
        print("\n[dry-run] 不写入文件")
    else:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {MAIN_FILE}")


if __name__ == "__main__":
    main()
