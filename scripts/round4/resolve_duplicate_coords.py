"""
对重复坐标组中的记录，用高德地理编码尝试区分坐标。

高德 geocoding 返回 GCJ-02 坐标，需转换为 WGS-84。

用法:
  uv run python round4/resolve_duplicate_coords.py              # 执行
  uv run python round4/resolve_duplicate_coords.py --dry-run    # 只查询不写入
"""

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
DUPES_FILE = DATA_DIR / "round4" / "audit_duplicate_coords.json"
RESULT_FILE = DATA_DIR / "round4" / "resolve_duplicate_coords_result.json"

sys.path.insert(0, str(Path(__file__).parent.parent / "round1"))
sys.path.insert(0, str(Path(__file__).parent.parent / "round3"))


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    """GCJ-02 → WGS-84 坐标转换（简易公式，精度约1-2米）。"""
    import math
    a = 6378245.0
    ee = 0.00669342162296594323

    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret

    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return round(lng - dlng, 6), round(lat - dlat, 6)


def main():
    parser = argparse.ArgumentParser(description="高德 geocoding 解决重复坐标")
    parser.add_argument("--dry-run", action="store_true", help="只查询不写入")
    args = parser.parse_args()

    from geocode_amap import geocode, load_env_key
    from geocode_utils import extract_expected_province, is_province_ok

    api_key = load_env_key()
    if not api_key:
        print("错误: AMAP_GEOCODING_KEY 未配置")
        return

    with open(DUPES_FILE, encoding="utf-8") as f:
        dupe_groups = json.load(f)
    with open(MAIN_FILE, encoding="utf-8") as f:
        main_data = json.load(f)
    main_by_id = {r["release_id"]: r for r in main_data}

    results = []
    updated = 0

    for gi, group in enumerate(dupe_groups):
        print(f"\n组 {gi+1}/{len(dupe_groups)}: ({group['latitude']}, {group['longitude']}) — {group['count']} 条")

        for member in group["members"]:
            rid = member["release_id"]
            name = member["name"]
            main_rec = main_by_id.get(rid)
            if not main_rec:
                continue

            address = main_rec.get("address", "")
            print(f"  {rid} {name}: {address}")

            # 用高德地理编码
            result = geocode(address, api_key)
            time.sleep(0.2)

            if result and result.get("latitude") and result.get("longitude"):
                # GCJ-02 → WGS-84
                wgs_lng, wgs_lat = gcj02_to_wgs84(result["longitude"], result["latitude"])
                old_lat, old_lng = main_rec.get("latitude"), main_rec.get("longitude")

                # 省份验证
                expected_province = extract_expected_province(main_rec.get("release_address", "")) or main_rec.get("province")
                if not is_province_ok(expected_province, result.get("province")):
                    print(f"    ✗ 省份不匹配: 预期={expected_province}, 实际={result.get('province')}")
                    results.append({"release_id": rid, "name": name, "status": "province_mismatch"})
                    continue

                # 检查坐标是否有变化（距离>100m 认为有意义）
                import math
                dlat = abs(wgs_lat - old_lat) if old_lat else 999
                dlng = abs(wgs_lng - old_lng) if old_lng else 999
                dist_approx = math.sqrt(dlat**2 + dlng**2) * 111000  # 粗略距离(米)

                level = result.get("_geocode_level", "")
                print(f"    高德: ({wgs_lat}, {wgs_lng}) level={level} dist={dist_approx:.0f}m")

                if dist_approx > 100:
                    if not args.dry_run:
                        main_rec["latitude"] = wgs_lat
                        main_rec["longitude"] = wgs_lng
                        main_rec["_geocode_method"] = "amap_geocode"
                    updated += 1
                    print(f"    ✓ 已更新（偏移 {dist_approx:.0f}m）")
                    results.append({"release_id": rid, "name": name, "status": "updated",
                                    "old": [old_lat, old_lng], "new": [wgs_lat, wgs_lng],
                                    "dist_m": round(dist_approx), "level": level})
                else:
                    print(f"    — 坐标差异不大，保持原样")
                    results.append({"release_id": rid, "name": name, "status": "unchanged", "dist_m": round(dist_approx)})
            else:
                print(f"    ✗ 高德未找到结果")
                results.append({"release_id": rid, "name": name, "status": "not_found"})

    # 保存结果
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if not args.dry_run and updated > 0:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(main_data, f, ensure_ascii=False, indent=2)

    print(f"\n完成: {updated} 条坐标已更新 → {RESULT_FILE.name}")
    if args.dry_run:
        print("（dry-run 模式，未写入主数据文件）")


if __name__ == "__main__":
    main()
