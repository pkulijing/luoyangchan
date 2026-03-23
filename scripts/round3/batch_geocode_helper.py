"""
批量 geocoding 辅助脚本：拆分、合并、状态查看。

用法：
    uv run scripts/round3/batch_geocode_helper.py split          # 拆分为批次
    uv run scripts/round3/batch_geocode_helper.py status         # 查看处理状态
    uv run scripts/round3/batch_geocode_helper.py merge          # 合并结果
    uv run scripts/round3/batch_geocode_helper.py validate       # 验证合并结果
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = _ROOT / "data/round3/gemini_geocode_input.json"
BATCH_DIR = _ROOT / "data/round3/geocode_batches"
MERGED_FILE = _ROOT / "data/round3/geocode_result_merged.json"
FINAL_FILE = _ROOT / "data/round3/gemini_geocode_result.json"

BATCH_SIZE = 100


def cmd_split():
    with open(INPUT_FILE) as f:
        records = json.load(f)

    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    total = len(records)
    batch_num = 0
    for i in range(0, total, BATCH_SIZE):
        batch_num += 1
        batch = records[i : i + BATCH_SIZE]
        out = BATCH_DIR / f"batch_{batch_num:03d}.json"
        with open(out, "w") as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        print(f"  {out.name}: {len(batch)} records")

    print(f"\nTotal: {total} records → {batch_num} batches in {BATCH_DIR}")


def cmd_status():
    if not BATCH_DIR.exists():
        print("No batches directory. Run 'split' first.")
        return

    batch_files = sorted(BATCH_DIR.glob("batch_*.json"))
    result_files = {f"result_{f.stem.split('_')[1]}.json" for f in BATCH_DIR.glob("result_*.json")}

    done = 0
    total_input = 0
    total_output = 0
    for bf in batch_files:
        num = bf.stem.split("_")[1]
        rf_name = f"result_{num}.json"
        with open(bf) as f:
            count = len(json.load(f))
        total_input += count

        if rf_name in result_files:
            rf = BATCH_DIR / rf_name
            with open(rf) as f:
                result_count = len(json.load(f))
            total_output += result_count
            status = f"DONE ({result_count}/{count})"
            done += 1
        else:
            status = "PENDING"

        print(f"  {bf.name} ({count}) → {status}")

    print(f"\nProgress: {done}/{len(batch_files)} batches, {total_output}/{total_input} records")


def cmd_merge():
    if not BATCH_DIR.exists():
        print("No batches directory.")
        return

    all_results = []
    result_files = sorted(BATCH_DIR.glob("result_*.json"))
    for rf in result_files:
        with open(rf) as f:
            all_results.extend(json.load(f))

    with open(MERGED_FILE, "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"Merged {len(all_results)} records from {len(result_files)} files → {MERGED_FILE}")

    # Also generate the final file compatible with downstream geocode_tencent.py
    final = []
    for r in all_results:
        entry = {
            "release_id": r["release_id"],
            "poi_keywords": [r["poi_name"]] if r.get("poi_name") else [],
            "precise_address": r.get("address_for_geocoding", ""),
        }
        if r.get("notes"):
            entry["notes"] = r["notes"]
        final.append(entry)

    with open(FINAL_FILE, "w") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"Final output: {len(final)} records → {FINAL_FILE}")


def cmd_validate():
    with open(INPUT_FILE) as f:
        input_ids = {r["release_id"] for r in json.load(f)}

    if not MERGED_FILE.exists():
        print("No merged file. Run 'merge' first.")
        return

    with open(MERGED_FILE) as f:
        results = json.load(f)

    result_ids = {r["release_id"] for r in results}
    missing = input_ids - result_ids
    extra = result_ids - input_ids
    no_addr = [r["release_id"] for r in results if not r.get("address_for_geocoding")]

    print(f"Input: {len(input_ids)}, Output: {len(results)}")
    if missing:
        print(f"MISSING ({len(missing)}): {sorted(missing)[:10]}...")
    if extra:
        print(f"EXTRA ({len(extra)}): {sorted(extra)[:10]}...")
    if no_addr:
        print(f"NO ADDRESS ({len(no_addr)}): {no_addr[:10]}...")
    if not missing and not extra and not no_addr:
        print("ALL OK!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["split", "status", "merge", "validate"])
    args = parser.parse_args()

    {"split": cmd_split, "status": cmd_status, "merge": cmd_merge, "validate": cmd_validate}[args.command]()
