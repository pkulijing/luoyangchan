"""
按文保单位名称重新进行 POI 搜索，刷新全部 5060 条记录的经纬度。

背景：
  原始地理编码使用 release_address（行政区地址），精度仅到县市级，
  导致坐标落在政府大楼位置。改用 name 字段做 POI 关键词搜索，
  精度更高，可直接定位到文保单位。

策略：
  1. 优先：高德 POI 关键词搜索（keywords=name, city=省/市）
  2. fallback：高德地理编码（address=release_address）
  3. 最终 fallback：保留原坐标不变

全量刷新：所有 5060 条均重新搜索，不跳过已有坐标的条目。

用法:
  uv run python regeocode_by_name.py           # 全量处理
  uv run python regeocode_by_name.py --test    # 测试前 5 条（不写入）
  uv run python regeocode_by_name.py --limit 100  # 只处理前 N 条（调试）
  uv run python regeocode_by_name.py --resume  # 从断点继续（跳过已处理）
"""

import argparse
import difflib
import json
import os
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "heritage_sites_geocoded.json"
DEFAULT_OUTPUT = DATA_DIR / "heritage_sites_geocoded.json"
CHECKPOINT_FILE = DATA_DIR / "regeocode_checkpoint.json"

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_SEARCH_URL = "https://restapi.amap.com/v3/place/text"

REQUEST_INTERVAL = 0.2   # 200ms，保守 5 QPS
CHECKPOINT_EVERY = 50
POI_SIMILARITY_THRESHOLD = 0.5  # POI 名称相似度阈值


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def load_env_key() -> str | None:
    for env_name in ("AMAP_GEOCODING_KEY", "AMAP_KEY"):
        key = os.environ.get(env_name)
        if key:
            return key
    env_file = Path(__file__).parent.parent.parent / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            for prefix in ("AMAP_GEOCODING_KEY=", "AMAP_KEY="):
                if line.startswith(prefix):
                    return line.split("=", 1)[1].strip()
    return None


def search_poi(name: str, city_hint: str | None, api_key: str) -> dict | None:
    """
    高德 POI 关键词搜索，以 name 为主搜索词。
    返回最佳匹配的坐标和地址字段，或 None。
    """
    params = {
        "keywords": name,
        "key": api_key,
        "output": "JSON",
        "offset": 10,  # 取前 10 条，从中挑最相似的
    }
    if city_hint:
        params["city"] = city_hint
        params["citylimit"] = "false"

    try:
        resp = requests.get(AMAP_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    POI 搜索请求失败: {e}")
        return None

    if data.get("status") != "1" or not data.get("pois"):
        return None

    # 对前 N 条按名称相似度排序，取最高分
    best_poi = None
    best_score = 0.0
    for poi in data["pois"]:
        poi_name = poi.get("name", "")
        score = difflib.SequenceMatcher(None, name, poi_name).ratio()
        if score > best_score:
            best_score = score
            best_poi = poi

    if best_score < POI_SIMILARITY_THRESHOLD or best_poi is None:
        return None

    loc = best_poi.get("location", "")
    try:
        lng_str, lat_str = loc.split(",")
        longitude = round(float(lng_str), 6)
        latitude = round(float(lat_str), 6)
    except (ValueError, AttributeError):
        return None

    province = best_poi.get("pname") or None
    city = best_poi.get("cityname") or None
    district = best_poi.get("adname") or None
    raw_address = best_poi.get("address") or None
    if isinstance(raw_address, list):
        raw_address = None
    formatted_address = "".join(filter(None, [province, city, district, raw_address, best_poi.get("name")]))

    return {
        "province": province,
        "city": city,
        "district": district,
        "address": formatted_address,
        "longitude": longitude,
        "latitude": latitude,
        "_geocode_method": "poi_search",
        "_geocode_score": round(best_score, 3),
        "_geocode_matched_name": best_poi.get("name", ""),
    }


def geocode_by_address(address: str, api_key: str) -> dict | None:
    """
    高德地理编码，以 release_address 为输入。作为 POI 搜索失败时的 fallback。
    """
    try:
        resp = requests.get(
            AMAP_GEOCODE_URL,
            params={"address": address, "key": api_key, "output": "JSON"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    地理编码请求失败: {e}")
        return None

    if data.get("status") != "1" or data.get("count", "0") == "0":
        return None

    geo = data["geocodes"][0]
    loc = geo.get("location", "")
    try:
        lng_str, lat_str = loc.split(",")
        longitude = round(float(lng_str), 6)
        latitude = round(float(lat_str), 6)
    except (ValueError, AttributeError):
        return None

    province = geo.get("province") or None
    city = geo.get("city") or None
    if isinstance(city, list) or city == "[]":
        city = province
    district = geo.get("district") or None
    if isinstance(district, list) or district == "[]":
        district = None
    formatted_address = geo.get("formatted_address") or None
    level = geo.get("level", "")

    return {
        "province": province,
        "city": city,
        "district": district,
        "address": formatted_address,
        "longitude": longitude,
        "latitude": latitude,
        "_geocode_method": "geocode",
        "_geocode_level": level,
    }


def extract_city_hint(site: dict) -> str | None:
    """从 release_address 提取省/市，用作 POI 搜索的城市提示。"""
    addr = site.get("release_address", "") or ""
    # 优先返回省份（高德支持省名缩窄搜索范围）
    if addr:
        # 取前 9 个字（通常包含省+市信息）
        return addr[:9]
    return site.get("province") or None


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def load_checkpoint() -> set[str]:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_checkpoint(done_ids: set[str]):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(done_ids), f, ensure_ascii=False)


def save_output(sites: list[dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run_test(sites: list[dict], api_key: str, n: int = 5):
    """测试前 n 条，打印结果但不写入文件。"""
    print(f"\n=== 测试模式：处理前 {n} 条 ===\n")
    for site in sites[:n]:
        name = site.get("name", "?")
        city_hint = extract_city_hint(site)
        print(f"[{site.get('release_id')}] {name} | city_hint={city_hint}")

        result = search_poi(name, city_hint, api_key)
        time.sleep(REQUEST_INTERVAL)

        if result:
            print(f"  POI 搜索成功: {result['longitude']},{result['latitude']}")
            print(f"  匹配名称: {result['_geocode_matched_name']} (相似度 {result['_geocode_score']})")
            print(f"  地址: {result['address']}")
        else:
            print("  POI 搜索失败，尝试地理编码...")
            addr = site.get("release_address", "")
            if addr:
                geo = geocode_by_address(addr, api_key)
                time.sleep(REQUEST_INTERVAL)
                if geo:
                    print(f"  地理编码成功: {geo['longitude']},{geo['latitude']} ({geo.get('_geocode_level')})")
                else:
                    print("  地理编码也失败")
            else:
                print("  无地址可用")
        print()


def run_batch(
    sites: list[dict],
    api_key: str,
    output_path: Path,
    limit: int | None = None,
    resume: bool = False,
):
    """批量重新地理编码。"""
    done_ids = load_checkpoint() if resume else set()
    if resume and done_ids:
        print(f"从断点继续，已处理 {len(done_ids)} 条")

    targets = sites if limit is None else sites[:limit]
    todo = [(i, s) for i, s in enumerate(targets) if s.get("release_id", "") not in done_ids]

    print(f"\n总记录: {len(sites)}")
    print(f"本次处理: {len(todo)} 条" + (f"（跳过已处理 {len(done_ids)} 条）" if done_ids else ""))
    print()

    results = list(sites)
    success_poi = 0
    success_geo = 0
    kept_original = 0

    for count, (idx, site) in enumerate(todo, 1):
        name = site.get("name", "?")
        city_hint = extract_city_hint(site)
        release_id = site.get("release_id", "")

        # Step 1: POI 搜索（按名称）
        geo = search_poi(name, city_hint, api_key)
        time.sleep(REQUEST_INTERVAL)

        # Step 2: fallback 地理编码（按地址）
        if not geo:
            addr = site.get("release_address", "")
            if addr:
                geo = geocode_by_address(addr, api_key)
                time.sleep(REQUEST_INTERVAL)

        if geo:
            method = geo.get("_geocode_method", "unknown")
            results[idx].update({
                "province": geo["province"] or site.get("province"),
                "city": geo["city"] or site.get("city"),
                "district": geo["district"] or site.get("district"),
                "address": geo["address"],
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "_geocode_method": method,
            })
            if method == "poi_search":
                score = geo.get("_geocode_score", 0)
                matched = geo.get("_geocode_matched_name", "")
                print(f"  [{count}/{len(todo)}] {name}: {geo['longitude']},{geo['latitude']} (POI 相似度 {score}, 匹配: {matched})")
                success_poi += 1
            else:
                level = geo.get("_geocode_level", "")
                print(f"  [{count}/{len(todo)}] {name}: {geo['longitude']},{geo['latitude']} (地理编码 {level})")
                success_geo += 1
        else:
            results[idx]["_geocode_method"] = "kept_original"
            print(f"  [{count}/{len(todo)}] {name}: 编码失败，保留原坐标")
            kept_original += 1

        done_ids.add(release_id)

        if count % CHECKPOINT_EVERY == 0:
            save_output(results, output_path)
            save_checkpoint(done_ids)
            print(f"  --- 已保存断点（{count}/{len(todo)}）---")

    save_output(results, output_path)
    save_checkpoint(done_ids)

    print(f"\n{'='*60}")
    print(f"完成: POI搜索成功 {success_poi} 条 | 地理编码成功 {success_geo} 条 | 保留原坐标 {kept_original} 条")
    print(f"结果已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="按名称 POI 搜索重新地理编码")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--key", default=None)
    parser.add_argument("--test", action="store_true", help="测试前 5 条（不写入）")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 条（调试用）")
    parser.add_argument("--resume", action="store_true", help="从断点继续（跳过已处理记录）")
    args = parser.parse_args()

    api_key = args.key or load_env_key()
    if not api_key:
        print("错误：未找到高德 API Key。")
        print("  请在 .env.local 中设置 AMAP_GEOCODING_KEY，或通过 --key 传入。")
        return

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：输入文件不存在: {input_path}")
        return

    with open(input_path, encoding="utf-8") as f:
        sites = json.load(f)

    print(f"读取 {len(sites)} 条记录，来自: {input_path}")

    if args.test:
        run_test(sites, api_key)
    else:
        run_batch(sites, api_key, Path(args.output), limit=args.limit, resume=args.resume)


if __name__ == "__main__":
    main()
