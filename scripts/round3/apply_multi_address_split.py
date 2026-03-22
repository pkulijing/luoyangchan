"""
第三轮数据清洗 - Phase 1: 执行多地址拆分

读取 Gemini 返回的 gemini_multi_address_result.json，
对 needs_splitting == true 的条目执行父子记录拆分。

操作：
  - 原记录 → 父记录（_is_parent: true，清空坐标和地址字段）
  - 生成子记录（_parent_release_id 指向父，release_id 格式 {parent_id}-{i}）
  - 子记录暂无坐标，待 geocode_tencent.py 处理

用法:
  uv run python apply_multi_address_split.py           # dry-run（只预览）
  uv run python apply_multi_address_split.py --apply   # 执行写入（自动备份）
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND3_DIR = DATA_DIR / "round3"
GEMINI_RESULT = ROUND3_DIR / "gemini_multi_address_result.json"
BACKUP_DIR = ROUND3_DIR / "backup"


def main():
    parser = argparse.ArgumentParser(description="执行多地址拆分")
    parser.add_argument("--apply", action="store_true", help="实际执行写入（默认 dry-run）")
    args = parser.parse_args()

    if not GEMINI_RESULT.exists():
        print(f"错误: 找不到 {GEMINI_RESULT}")
        print("请先运行 generate_gemini_prompt_multi_address.py，跑 Gemini，")
        print("将结果保存为 data/round3/gemini_multi_address_result.json")
        sys.exit(1)

    with open(GEMINI_RESULT, encoding="utf-8") as f:
        gemini_data: list[dict] = json.load(f)

    with open(MAIN_FILE, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    # 索引：release_id → 记录
    records_by_id: dict[str, dict] = {r["release_id"]: r for r in records}

    needs_split = [g for g in gemini_data if g.get("needs_splitting")]
    skip_list = [g for g in gemini_data if not g.get("needs_splitting")]

    print(f"Gemini 结果: {len(gemini_data)} 条")
    print(f"  需要拆分: {len(needs_split)} 条")
    print(f"  不需要拆分: {len(skip_list)} 条")
    print()

    to_remove: list[str] = []        # 要从原列表删除的 release_id
    to_add: list[dict] = []          # 要追加的新记录（父 + 子）

    for item in needs_split:
        rid = item["release_id"]
        children = item.get("children", [])

        if rid not in records_by_id:
            print(f"  ⚠ 找不到记录: {rid}，跳过")
            continue

        if not children:
            print(f"  ⚠ {rid} 标记需拆分但未提供子条目，跳过")
            continue

        original = records_by_id[rid]
        print(f"  拆分: {rid} {original['name']} → {len(children)} 个子条目")

        # 构建父记录
        parent = dict(original)
        parent["_is_parent"] = True
        parent["latitude"] = None
        parent["longitude"] = None
        parent["province"] = None
        parent["city"] = None
        parent["district"] = None
        parent["address"] = None
        parent["_geocode_method"] = None
        # 清除 Round 2 的 geocode 调试字段
        for key in ("_geocode_score", "_geocode_matched_name", "_geocode_level"):
            parent.pop(key, None)
        to_add.append(parent)

        # 构建子记录
        for i, child_info in enumerate(children, start=1):
            child_rid = f"{rid}-{i}"
            # 检查是否已存在（避免重复拆分）
            if child_rid in records_by_id:
                print(f"    ⚠ 子记录 {child_rid} 已存在，跳过")
                continue

            child = {
                "release_id": child_rid,
                "name": child_info["name"],
                "era": original.get("era"),
                "category": original.get("category"),
                "batch": original.get("batch"),
                "batch_year": original.get("batch_year"),
                "release_address": child_info.get("address_for_geocoding") or original.get("release_address"),
                "province": child_info.get("province"),
                "city": child_info.get("city"),
                "district": child_info.get("district"),
                "address": None,
                "latitude": None,
                "longitude": None,
                "wikipedia_url": None,
                "description": None,
                "image_url": None,
                "_parent_release_id": rid,
                "_geocode_method": None,
            }
            print(f"    + 子记录 {child_rid}: {child['name']}")
            to_add.append(child)

        to_remove.append(rid)

    print()
    print(f"摘要:")
    print(f"  将删除原记录: {len(to_remove)} 条")
    child_count = sum(1 for r in to_add if r.get("_parent_release_id"))
    parent_count = sum(1 for r in to_add if r.get("_is_parent"))
    print(f"  将新增父记录: {parent_count} 条")
    print(f"  将新增子记录: {child_count} 条（暂无坐标，待 geocode_tencent.py 处理）")

    if not args.apply:
        print()
        print("=== DRY-RUN 模式，未写入任何文件 ===")
        print("用 --apply 参数执行实际写入")
        return

    # 执行写入
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"heritage_sites_geocoded_{timestamp}.json"
    shutil.copy2(MAIN_FILE, backup_file)
    print(f"\n已备份原文件到: {backup_file}")

    # 构建新记录列表
    remove_set = set(to_remove)
    new_records = [r for r in records if r["release_id"] not in remove_set]
    new_records.extend(to_add)

    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(new_records, f, ensure_ascii=False, indent=2)

    print(f"已写入 {MAIN_FILE.name}: {len(new_records)} 条记录（原 {len(records)} 条）")
    print(f"  变化: -{len(to_remove)} 原记录，+{parent_count} 父记录，+{child_count} 子记录")


if __name__ == "__main__":
    main()
