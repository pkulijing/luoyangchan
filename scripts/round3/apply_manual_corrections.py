"""
第三轮数据清洗 - Phase 3: 应用人工修正坐标

从 data/round3/manual_corrections.json 读取手动修正的坐标，
写入 heritage_sites_geocoded.json。

manual_corrections.json 格式：
[
  {
    "release_id": "1-4",
    "latitude": 27.914,
    "longitude": 112.492,
    "province": "湖南省",   // 可选
    "city": "湘潭市",       // 可选
    "district": "韶山市",   // 可选
    "address": "湖南省湘潭市韶山市韶山冲上屋场",  // 可选
    "_geocode_method": "manual",
    "source": "百度地图"    // 可选，说明坐标来源
  }
]

注意：坐标应为 GCJ-02 格式（高德/腾讯坐标系）。
      如从百度地图获取（BD-09），需先转换。
      如从 Google Maps/OpenStreetMap 获取（WGS-84），需先转换。

用法:
  uv run python apply_manual_corrections.py           # dry-run（只预览）
  uv run python apply_manual_corrections.py --apply   # 执行写入
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
CORRECTIONS_FILE = ROUND3_DIR / "manual_corrections.json"
BACKUP_DIR = ROUND3_DIR / "backup"


def main():
    parser = argparse.ArgumentParser(description="应用人工修正坐标")
    parser.add_argument("--apply", action="store_true", help="实际执行写入（默认 dry-run）")
    parser.add_argument("--input", default=str(CORRECTIONS_FILE), help="修正文件路径")
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.exists():
        print(f"找不到修正文件: {input_file}")
        print(f"请创建 {CORRECTIONS_FILE} 并填写要修正的记录")
        print("格式: [{\"release_id\": \"...\", \"latitude\": ..., \"longitude\": ..., ...}]")
        sys.exit(1)

    with open(input_file, encoding="utf-8") as f:
        corrections: list[dict] = json.load(f)

    with open(MAIN_FILE, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    records_by_id = {r["release_id"]: r for r in records}

    print(f"要修正的记录数: {len(corrections)}")
    print()

    applied = []
    not_found = []

    for corr in corrections:
        rid = corr.get("release_id")
        if not rid:
            print(f"  ⚠ 缺少 release_id，跳过: {corr}")
            continue

        if rid not in records_by_id:
            print(f"  ⚠ 找不到记录: {rid}")
            not_found.append(rid)
            continue

        rec = records_by_id[rid]
        old_lat = rec.get("latitude")
        old_lng = rec.get("longitude")
        new_lat = corr.get("latitude")
        new_lng = corr.get("longitude")

        if new_lat is None or new_lng is None:
            print(f"  ⚠ {rid} 缺少坐标，跳过")
            continue

        source = corr.get("source", "人工修正")
        print(f"  {rid} {rec['name']}")
        print(f"    旧坐标: ({old_lat}, {old_lng}) [{rec.get('_geocode_method')}]")
        print(f"    新坐标: ({new_lat}, {new_lng}) [来源: {source}]")

        applied.append((rec, corr))

    print()
    print(f"摘要: {len(applied)} 条将被修正，{len(not_found)} 条找不到")

    if not args.apply:
        print("\n=== DRY-RUN 模式，未写入任何文件 ===")
        print("用 --apply 参数执行实际写入")
        return

    # 执行写入
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"heritage_sites_geocoded_{timestamp}.json"
    shutil.copy2(MAIN_FILE, backup_file)
    print(f"\n已备份原文件到: {backup_file}")

    updatable_fields = ["latitude", "longitude", "province", "city", "district", "address", "_geocode_method"]
    for rec, corr in applied:
        for field in updatable_fields:
            if field in corr:
                rec[field] = corr[field]
        # 清除旧的 geocode 元信息
        for meta in ("_geocode_score", "_geocode_matched_name", "_geocode_level", "_geocode_reliability"):
            rec.pop(meta, None)
        # 记录来源
        if corr.get("source"):
            rec["_manual_correction_source"] = corr["source"]

    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"已写入 {MAIN_FILE.name}，修正 {len(applied)} 条记录")
    print("下一步: uv run python verify_round3.py")


if __name__ == "__main__":
    main()
