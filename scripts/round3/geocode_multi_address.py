"""
为 gemini_multi_address_result.json 里拆分出的子记录做腾讯地图 geocoding，
并追加到 heritage_sites_geocoded.json。

用法：
    uv run round3/geocode_multi_address.py          # 处理全部未完成的子记录
    uv run round3/geocode_multi_address.py --test   # 只处理前3条
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

import requests

_ROOT = Path(__file__).parent.parent.parent
MULTI_ADDR_FILE = _ROOT / "data/round3/gemini_multi_address_result.json"
GEOCODED_FILE = _ROOT / "data/heritage_sites_geocoded.json"
REQUEST_INTERVAL = 1.0

PROVINCE_MAP = {
    "北京": "北京市", "天津": "天津市", "上海": "上海市", "重庆": "重庆市",
    "河北": "河北省", "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "海南": "海南省",
    "四川": "四川省", "贵州": "贵州省", "云南": "云南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省", "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区", "西藏": "西藏自治区", "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
}


def load_env() -> tuple[str, str]:
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    key = os.environ.get("TENCENT_MAP_KEY", "")
    sk = os.environ.get("TENCENT_MAP_SIGN_SECRET_KEY", "")
    if not key:
        print("ERROR: TENCENT_MAP_KEY not set", file=sys.stderr)
        sys.exit(1)
    return key, sk


def compute_sig(path: str, params: dict, sk: str) -> str:
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    sig_raw = f"{path}?{query_string}{sk}"
    return hashlib.md5(sig_raw.encode("utf-8")).hexdigest()


def normalize_province(text: str) -> str:
    if not text:
        return ""
    for short, full in PROVINCE_MAP.items():
        if text.startswith(short) or text.startswith(full):
            return full
    return text


def geocode_address(address: str, api_key: str, sk: str) -> dict | None:
    path = "/ws/geocoder/v1/"
    params = {"address": address, "key": api_key}
    if sk:
        params["sig"] = compute_sig(path, params, sk)
    try:
        resp = requests.get(
            f"https://apis.map.qq.com{path}",
            params={k: v for k, v in params.items() if k != "sig"},
            timeout=10,
        )
        # 重新构造带 sig 的请求
        if sk:
            full_params = dict(params)
            resp = requests.get(f"https://apis.map.qq.com{path}", params=full_params, timeout=10)
        data = resp.json()
        if data.get("status") == 0:
            loc = data["result"]["location"]
            addr_comp = data["result"].get("address_components", {})
            return {
                "latitude": loc["lat"],
                "longitude": loc["lng"],
                "province": addr_comp.get("province", ""),
                "city": addr_comp.get("city", ""),
                "district": addr_comp.get("district", ""),
                "address": address,
            }
    except Exception as e:
        print(f"  geocode error: {e}")
    return None


def search_poi(name: str, city_hint: str, api_key: str, sk: str) -> dict | None:
    path = "/ws/place/v1/search"
    params = {"keyword": name, "boundary": f"region({city_hint},0)", "key": api_key, "page_size": "1"}
    if sk:
        params["sig"] = compute_sig(path, params, sk)
    try:
        resp = requests.get(f"https://apis.map.qq.com{path}", params=params, timeout=10)
        data = resp.json()
        if data.get("status") == 0 and data.get("data"):
            item = data["data"][0]
            loc = item["location"]
            addr = item.get("address", "")
            province = normalize_province(addr)
            return {
                "latitude": loc["lat"],
                "longitude": loc["lng"],
                "province": province,
                "city": item.get("ad_info", {}).get("city", ""),
                "district": item.get("ad_info", {}).get("district", ""),
                "address": addr,
            }
    except Exception as e:
        print(f"  poi search error: {e}")
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="只处理前3条")
    args = parser.parse_args()

    api_key, sk = load_env()

    with open(MULTI_ADDR_FILE) as f:
        multi_data = json.load(f)

    with open(GEOCODED_FILE) as f:
        geocoded = json.load(f)

    geocoded_map = {r["release_id"]: i for i, r in enumerate(geocoded)}

    # 收集需要新增的子记录
    pending = []
    for parent in multi_data:
        if not parent.get("needs_splitting"):
            continue
        pid = parent["release_id"]
        parent_rec = geocoded[geocoded_map[pid]] if pid in geocoded_map else {}
        for i, child in enumerate(parent["children"], 1):
            cid = f"{pid}-{i}"
            if cid in geocoded_map:
                print(f"  skip {cid} (already exists)")
                continue
            pending.append({
                "_child_id": cid,
                "_parent_id": pid,
                "_parent_rec": parent_rec,
                "_child_data": child,
            })

    if args.test:
        pending = pending[:3]
        print(f"[test] Processing first 3 records only")

    print(f"待处理子记录: {len(pending)}")
    print()

    success = 0
    failed = []

    for idx, item in enumerate(pending):
        cid = item["_child_id"]
        pid = item["_parent_id"]
        child = item["_child_data"]
        parent_rec = item["_parent_rec"]

        name = child["name"]
        address = child["address_for_geocoding"]
        expected_province = child.get("province", "")

        print(f"[{idx+1}/{len(pending)}] {cid} {name}")
        print(f"  地址: {address}")

        result = None

        # 策略1：腾讯地理编码
        geo_result = geocode_address(address, api_key, sk)
        time.sleep(REQUEST_INTERVAL)

        if geo_result:
            got_province = normalize_province(geo_result["province"])
            exp_province = normalize_province(expected_province)
            if not exp_province or got_province == exp_province:
                result = geo_result
                result["_geocode_method"] = "tencent_geocode_gemini"
                print(f"  ✓ 地理编码: ({result['latitude']:.6f}, {result['longitude']:.6f}) {got_province}")
            else:
                print(f"  ✗ 省份不匹配: 期望={exp_province}, 得到={got_province}")

        # 策略2：POI 搜索
        if not result:
            city_hint = child.get("city") or child.get("province") or expected_province or "全国"
            poi_result = search_poi(name, city_hint, api_key, sk)
            time.sleep(REQUEST_INTERVAL)
            if poi_result:
                got_province = normalize_province(poi_result["province"])
                exp_province = normalize_province(expected_province)
                if not exp_province or got_province == exp_province:
                    result = poi_result
                    result["_geocode_method"] = "poi_search"
                    print(f"  ✓ POI搜索: ({result['latitude']:.6f}, {result['longitude']:.6f})")
                else:
                    print(f"  ✗ POI省份不匹配")

        if not result:
            print(f"  ✗ 失败，跳过")
            failed.append(cid)
            continue

        # 构建子记录，继承父记录的基础字段
        child_rec = {
            "name": name,
            "era": parent_rec.get("era"),
            "category": parent_rec.get("category"),
            "batch": parent_rec.get("batch"),
            "batch_year": parent_rec.get("batch_year"),
            "release_id": cid,
            "release_address": address,
            "province": result.get("province") or child.get("province"),
            "city": result.get("city") or child.get("city"),
            "district": result.get("district") or child.get("district"),
            "address": result.get("address"),
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "wikipedia_url": None,
            "description": None,
            "image_url": None,
            "_geocode_method": result["_geocode_method"],
            "_parent_release_id": pid,
        }

        geocoded.append(child_rec)
        geocoded_map[cid] = len(geocoded) - 1
        success += 1

    # 写回
    if not args.test:
        with open(GEOCODED_FILE, "w") as f:
            json.dump(geocoded, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {GEOCODED_FILE}")

    print(f"\n=== 完成 ===")
    print(f"  成功: {success}")
    print(f"  失败: {len(failed)}")
    if failed:
        print(f"  失败列表: {failed}")


if __name__ == "__main__":
    main()
