"""
通过高德地理编码 API 补全文保单位的地址信息。

填充字段：province, city, district, address（格式化地址）, longitude, latitude

输入:  data/heritage_sites_merged.json（或其他包含 release_address 的 JSON）
输出:  data/heritage_sites_geocoded.json
断点:  data/geocode_checkpoint.json（可随时中断，下次续跑）

用法:
  # 单条测试（用第一条缺坐标的记录验证 API）
  uv run python geocode_amap.py --test

  # 批量处理
  uv run python geocode_amap.py

  # 指定输入文件
  uv run python geocode_amap.py --input ../data/heritage_sites_merged.json

  # 直接传 key（否则读 .env.local 或环境变量）
  uv run python geocode_amap.py --key YOUR_KEY
"""

import difflib
import json
import os
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "heritage_sites_geocoded.json"
DEFAULT_OUTPUT = DATA_DIR / "heritage_sites_geocoded.json"

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_SEARCH_URL = "https://restapi.amap.com/v3/place/text"

# 高德免费 QPS 限制约 50，这里保守设 5 QPS（200ms 间隔）
REQUEST_INTERVAL = 0.2
# 每处理多少条保存一次输出文件（防止中途崩溃丢失进度）
CHECKPOINT_EVERY = 50


def load_env_key() -> str | None:
    """
    从 .env.local 或环境变量读取高德 Web 服务 API key。

    注意：高德 JS API Key（NEXT_PUBLIC_AMAP_KEY）不能用于 Web Service 接口。
    需要在高德控制台单独创建平台为「Web 服务」的 Key，
    存入 .env.local 的 AMAP_GEOCODING_KEY 变量。
    """
    # 优先读 Web 服务专用 key
    for env_name in ("AMAP_GEOCODING_KEY", "AMAP_KEY"):
        key = os.environ.get(env_name)
        if key:
            return key
    # 再试 .env.local
    env_file = Path(__file__).parent.parent / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            for prefix in ("AMAP_GEOCODING_KEY=", "AMAP_KEY="):
                if line.startswith(prefix):
                    return line.split("=", 1)[1].strip()
    return None


def geocode(address: str, api_key: str) -> dict | None:
    """
    调用高德地理编码 API。
    返回解析后的字段字典，或 None（地址无法识别时）。
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
        print(f"    请求失败: {e}")
        return None

    if data.get("status") != "1" or data.get("count", "0") == "0":
        return None

    geo = data["geocodes"][0]
    loc = geo.get("location", "")  # "lng,lat" 格式，GCJ-02

    try:
        lng_str, lat_str = loc.split(",")
        longitude = round(float(lng_str), 6)
        latitude = round(float(lat_str), 6)
    except (ValueError, AttributeError):
        longitude = None
        latitude = None

    province = geo.get("province") or None
    city = geo.get("city") or None
    # 直辖市时 city 可能是 [] 或空，province 就是城市
    if isinstance(city, list) or city == "[]":
        city = province
    district = geo.get("district") or None
    if isinstance(district, list) or district == "[]":
        district = None
    formatted_address = geo.get("formatted_address") or None
    level = geo.get("level", "")  # 精度描述，如"兴趣点"/"道路"/"区县"

    return {
        "province": province,
        "city": city,
        "district": district,
        "address": formatted_address,
        "longitude": longitude,
        "latitude": latitude,
        "_geocode_level": level,
    }


def search_poi(name: str, city_hint: str | None, api_key: str) -> dict | None:
    """
    当 geocode 失败时，通过高德 POI 关键词搜索定位。
    用 difflib 对返回名称做相似度校验（阈值 0.4），避免错位。
    city_hint: 用于缩小搜索范围的城市/省份名，不强制限定（citylimit=false）。
    """
    params = {
        "keywords": name,
        "key": api_key,
        "output": "JSON",
        "offset": 5,  # 取前5条，挑最相似的
    }
    if city_hint:
        params["city"] = city_hint
        params["citylimit"] = "false"

    try:
        resp = requests.get(AMAP_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    POI搜索失败: {e}")
        return None

    if data.get("status") != "1" or not data.get("pois"):
        return None

    # 从前几条中挑相似度最高的
    best_poi = None
    best_score = 0.0
    for poi in data["pois"]:
        poi_name = poi.get("name", "")
        score = difflib.SequenceMatcher(None, name, poi_name).ratio()
        if score > best_score:
            best_score = score
            best_poi = poi

    if best_score < 0.4 or best_poi is None:
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
    address = best_poi.get("address") or None
    if isinstance(address, list):
        address = None
    formatted_address = "".join(filter(None, [province, city, district, address, best_poi.get("name")]))

    return {
        "province": province,
        "city": city,
        "district": district,
        "address": formatted_address,
        "longitude": longitude,
        "latitude": latitude,
        "_geocode_level": f"POI搜索(相似度{best_score:.2f})",
    }


def normalize_address(addr: str) -> str:
    """
    将地址中的历史行政区划名称替换为现行名称，提升地理编码命中率。
    （旧县/专区 → 现行市，直辖市简化等）
    """
    import re
    # 旧"XX县"→"XX市"（县改市改制，如桂平县→桂平市）
    # 仅对已知改制的情况做替换，避免误改真正的县
    replacements = [
        # 格式: (旧名, 新名)
        ("桂平县", "桂平市"),
        ("龙海县", "龙海市"),
        ("福清县", "福清市"),
        ("长乐县", "长乐市"),
        ("闽侯县", "闽侯县"),  # 保持原样
    ]
    for old, new in replacements:
        addr = addr.replace(old, new)

    # 去掉地址末尾的括号内容，如"北京市（原北平）"→"北京市"
    addr = re.sub(r"（[^）]*）", "", addr)
    addr = re.sub(r"\([^)]*\)", "", addr)

    return addr.strip()


def pick_address(site: dict) -> str | None:
    """选择最合适的地址文本用于地理编码。"""
    # 优先用官方地址（更规范）
    addr = site.get("release_address") or site.get("address")
    if addr:
        return normalize_address(addr.strip())
    # 再用 province+city 拼接
    parts = [p for p in [site.get("province"), site.get("city")] if p]
    return "".join(parts) or None


def run_test(sites: list[dict], api_key: str):
    """用第一条缺坐标的记录做验证测试。"""
    candidate = next(
        (s for s in sites if not s.get("latitude") and not s.get("longitude")),
        None,
    )
    if not candidate:
        print("所有记录都已有坐标，无需补充。")
        return

    addr = pick_address(candidate)
    print(f"\n测试记录: {candidate.get('name')} | 地址: {addr}")
    print(f"  release_address: {candidate.get('release_address')}")
    print(f"  address:         {candidate.get('address')}")
    print()

    result = geocode(addr, api_key)
    if result:
        print("高德返回结果:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    else:
        print("未找到结果（地址可能过于模糊）")
        print("请检查地址格式，或尝试更完整的地址字符串。")


def run_batch(
    sites: list[dict],
    api_key: str,
    output_path: Path,
):
    """批量地理编码，直接以 lat/lon 是否存在判断是否需要处理。"""
    need_geocode = [
        (i, s) for i, s in enumerate(sites)
        if not (s.get("latitude") and s.get("longitude"))
        and not s.get("_is_parent")  # 父记录无独立坐标，跳过
    ]
    already_has = len(sites) - len(need_geocode)

    print(f"\n总记录: {len(sites)}")
    print(f"已有坐标: {already_has}")
    print(f"待编码: {len(need_geocode)}")
    print()

    results = list(sites)  # 浅拷贝，直接修改
    success = 0
    failed = 0

    for count, (idx, site) in enumerate(need_geocode, 1):
        addr = pick_address(site)
        name = site.get("name", "?")

        geo = None
        if addr:
            geo = geocode(addr, api_key)
            time.sleep(REQUEST_INTERVAL)

        # 地理编码失败（或无地址）时，fallback 到 POI 关键词搜索
        if not geo:
            city_hint = site.get("city") or site.get("province")
            if not city_hint and addr:
                city_hint = addr[:9]
            geo = search_poi(name, city_hint, api_key)
            time.sleep(REQUEST_INTERVAL)

        if geo:
            results[idx].update({
                "province": geo["province"] or site.get("province"),
                "city": geo["city"] or site.get("city"),
                "district": geo["district"] or site.get("district"),
                "address": geo["address"],
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
            })
            level = geo.get("_geocode_level", "")
            print(f"  [{count}/{len(need_geocode)}] {name}: {geo['longitude']},{geo['latitude']} ({level})")
            success += 1
        else:
            addr_preview = addr[:40] if addr else "（无地址）"
            print(f"  [{count}/{len(need_geocode)}] {name}: 编码失败（地址: {addr_preview}）")
            failed += 1

        # 定期保存，防止中途崩溃丢失进度
        if count % CHECKPOINT_EVERY == 0:
            _save(results, output_path)
            print(f"  --- 已保存（{count}/{len(need_geocode)}）---")

    # 最终保存
    _save(results, output_path)

    print(f"\n{'='*60}")
    print(f"完成: 成功 {success} 条，失败/跳过 {failed} 条")
    print(f"结果已保存: {output_path}")


def _save(sites: list[dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="高德地理编码：补全文保单位地址信息")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="输入 JSON 文件")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出 JSON 文件")
    parser.add_argument("--key", default=None, help="高德 Web 服务 API Key")
    parser.add_argument("--test", action="store_true", help="仅测试一条记录，验证 API 可用性")
    args = parser.parse_args()

    api_key = args.key or load_env_key()
    if not api_key:
        print("错误：未找到高德 API Key。")
        print("  请在 .env.local 中设置 NEXT_PUBLIC_AMAP_KEY，或通过 --key 传入。")
        return

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：输入文件不存在: {input_path}")
        print("  请先运行 scrape_government.py 和 reconcile_data.py")
        return

    with open(input_path, encoding="utf-8") as f:
        sites = json.load(f)

    print(f"读取 {len(sites)} 条记录，来自: {input_path}")

    if args.test:
        run_test(sites, api_key)
    else:
        run_batch(
            sites,
            api_key,
            output_path=Path(args.output),
        )


if __name__ == "__main__":
    main()
