"""
修复重复GPS坐标：用高德地理编码 API 对重复坐标组重新编码。

每组中地址最精确的记录保留不动，其余记录用高德 geocoding 重新编码。
高德 geocoding（非 POI 搜索）不消耗 POI 配额。

用法: cd scripts && uv run python round4/fix_duplicate_coords.py
"""

import json
import os
import time
from pathlib import Path

import requests
from coordTransform import gcj02_to_wgs84

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
AUDIT_FILE = DATA_DIR / "round4" / "audit_duplicate_coords.json"
OUTPUT_FILE = DATA_DIR / "round4" / "amap_geocode_results.json"

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
REQUEST_INTERVAL = 0.25


def load_env_key() -> str | None:
    env_file = Path(__file__).parent.parent.parent / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("AMAP_GEOCODING_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("AMAP_GEOCODING_KEY")


def geocode(address: str, api_key: str) -> dict | None:
    """调用高德地理编码 API，返回解析结果或 None。"""
    try:
        resp = requests.get(
            AMAP_GEOCODE_URL,
            params={"address": address, "key": api_key, "output": "JSON"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    请求失败: {e}")
        return None

    if data.get("status") != "1" or data.get("count", "0") == "0":
        return None

    geo = data["geocodes"][0]
    loc = geo.get("location", "")

    try:
        lng_str, lat_str = loc.split(",")
        lng_gcj = float(lng_str)
        lat_gcj = float(lat_str)
    except (ValueError, AttributeError):
        return None

    # GCJ-02 → WGS-84
    lng_wgs, lat_wgs = gcj02_to_wgs84(lng_gcj, lat_gcj)

    province = geo.get("province") or None
    city = geo.get("city") or None
    if isinstance(city, list):
        city = province
    district = geo.get("district") or None
    if isinstance(district, list):
        district = None
    formatted_address = geo.get("formatted_address") or None
    level = geo.get("level", "")

    return {
        "province": province,
        "city": city,
        "district": district,
        "address": formatted_address,
        "longitude": round(lng_wgs, 6),
        "latitude": round(lat_wgs, 6),
        "_geocode_level": level,
    }


def main():
    api_key = load_env_key()
    if not api_key:
        print("错误：未找到 AMAP_GEOCODING_KEY")
        return

    with open(AUDIT_FILE, encoding="utf-8") as f:
        groups = json.load(f)

    # 收集所有需要重新编码的记录
    all_members = []
    for g in groups:
        for m in g["members"]:
            all_members.append(m)

    print(f"重复坐标组: {len(groups)}, 涉及记录: {len(all_members)} 条")
    print(f"对所有 {len(all_members)} 条用高德 geocoding 重新编码\n")

    results = []
    for i, member in enumerate(all_members, 1):
        rid = member["release_id"]
        name = member["name"]
        addr = member["address"]

        print(f"  [{i}/{len(all_members)}] {rid} {name}")
        print(f"    地址: {addr}")

        # 策略1: 用现有地址 geocode
        geo = geocode(addr, api_key)
        time.sleep(REQUEST_INTERVAL)

        # 策略2: 地址失败时用名称 geocode
        if not geo:
            province = member.get("province", "")
            geo = geocode(f"{province}{name}", api_key)
            time.sleep(REQUEST_INTERVAL)

        if geo:
            print(f"    → ({geo['latitude']}, {geo['longitude']}) level={geo['_geocode_level']}")
            results.append({
                "release_id": rid,
                "name": name,
                "old_address": addr,
                "new_address": geo["address"],
                "new_latitude": geo["latitude"],
                "new_longitude": geo["longitude"],
                "new_province": geo["province"],
                "new_city": geo["city"],
                "new_district": geo["district"],
                "geocode_level": geo["_geocode_level"],
                "changed": True,
            })
        else:
            print(f"    → 编码失败")
            results.append({
                "release_id": rid,
                "name": name,
                "old_address": addr,
                "changed": False,
            })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    success = sum(1 for r in results if r["changed"])
    print(f"\n完成: 成功 {success}/{len(results)} 条")
    print(f"结果已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
