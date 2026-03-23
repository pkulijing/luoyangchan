#!/usr/bin/env python3
"""
多地址文保单位拆分工具

将一个有多个地址的文保单位拆分成父记录 + 多个子记录。

用法:
  # 交互式拆分（需要提供子条目信息）
  uv run python split.py 7-1234 --children '[
    {"name": "xxx遗址（A点）", "province": "山西省", "city": "运城市", "address": "..."},
    {"name": "xxx遗址（B点）", "province": "山西省", "city": "太原市", "address": "..."}
  ]'

  # 只预览不写入
  uv run python split.py 7-1234 --children '[...]' --dry-run
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
BACKUP_DIR = DATA_DIR / "backup"


def split_record(rid: str, children: list[dict], main_data: list[dict], dry_run: bool = False) -> bool:
    """
    拆分单条记录为父记录 + 子记录。

    children 格式:
    [
        {
            "name": "子条目名称",
            "province": "省份",
            "city": "城市",
            "district": "区县",  # 可选
            "address": "详细地址用于geocoding"  # 可选
        },
        ...
    ]
    """
    records_by_id = {r["release_id"]: r for r in main_data}

    if rid not in records_by_id:
        print(f"错误: 找不到记录 {rid}")
        return False

    # 检查是否已经是父记录
    original = records_by_id[rid]
    if original.get("_is_parent"):
        print(f"错误: {rid} 已经是父记录，不能再次拆分")
        return False

    # 检查子记录是否已存在
    for i in range(1, len(children) + 1):
        child_rid = f"{rid}-{i}"
        if child_rid in records_by_id:
            print(f"错误: 子记录 {child_rid} 已存在")
            return False

    print(f"\n拆分: {rid} {original['name']} → {len(children)} 个子条目")

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
    for key in ("_geocode_score", "_geocode_matched_name", "_geocode_level", "_geocode_reliability"):
        parent.pop(key, None)

    print(f"  父记录: {rid} (清空坐标，标记 _is_parent: true)")

    # 构建子记录
    new_children = []
    for i, child_info in enumerate(children, start=1):
        child_rid = f"{rid}-{i}"
        child = {
            "release_id": child_rid,
            "name": child_info["name"],
            "era": original.get("era"),
            "category": original.get("category"),
            "batch": original.get("batch"),
            "batch_year": original.get("batch_year"),
            "release_address": child_info.get("address") or original.get("release_address"),
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
        new_children.append(child)
        print(f"  子记录: {child_rid} - {child['name']}")
        if child_info.get("address"):
            print(f"           地址: {child_info['address']}")

    if dry_run:
        print(f"\n[dry-run] 未写入")
        return True

    # 备份
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"heritage_sites_before_split_{rid}_{timestamp}.json"
    shutil.copy2(MAIN_FILE, backup_file)
    print(f"\n已备份到: {backup_file}")

    # 更新数据
    # 1. 找到原记录位置，替换为父记录
    for i, r in enumerate(main_data):
        if r["release_id"] == rid:
            main_data[i] = parent
            break

    # 2. 在父记录后面插入子记录
    insert_idx = next(i for i, r in enumerate(main_data) if r["release_id"] == rid) + 1
    for child in new_children:
        main_data.insert(insert_idx, child)
        insert_idx += 1

    # 3. 写入文件
    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2)

    print(f"\n已写入 {MAIN_FILE.name}")
    print(f"  新增 {len(new_children)} 个子记录，release_id: {rid}-1 ~ {rid}-{len(new_children)}")
    print(f"\n下一步: 为子记录执行 geocoding")
    for child in new_children:
        print(f"  uv run python fix.py {child['release_id']}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="多地址文保单位拆分",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  uv run python split.py 7-1234 --children '[
    {"name": "xxx遗址（A点）", "province": "山西省", "city": "运城市"},
    {"name": "xxx遗址（B点）", "province": "山西省", "city": "太原市"}
  ]'

子条目 JSON 格式:
  name: 必填，子条目名称
  province: 必填，省份
  city: 必填，城市
  district: 可选，区县
  address: 可选，详细地址（用于后续 geocoding）""",
    )
    parser.add_argument("release_id", help="要拆分的文保单位 release_id")
    parser.add_argument("--children", "-c", required=True,
                        help="子条目信息 JSON 数组")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写入")
    args = parser.parse_args()

    try:
        children = json.loads(args.children)
        if not isinstance(children, list) or len(children) < 2:
            print("错误: --children 必须是至少包含 2 个元素的 JSON 数组")
            return
        for i, c in enumerate(children):
            if not c.get("name"):
                print(f"错误: 子条目 {i+1} 缺少 name 字段")
                return
            if not c.get("province"):
                print(f"错误: 子条目 {i+1} 缺少 province 字段")
                return
    except json.JSONDecodeError as e:
        print(f"错误: --children JSON 解析失败: {e}")
        return

    with open(MAIN_FILE, encoding="utf-8") as f:
        main_data = json.load(f)

    split_record(args.release_id, children, main_data, args.dry_run)


if __name__ == "__main__":
    main()
