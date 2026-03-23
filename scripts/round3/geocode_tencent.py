"""
第三轮数据清洗 - Phase 2: 腾讯地图批量 geocoding

使用腾讯地图 Web 服务 API，对 needs_regeocode.json 中的记录重新地理编码。

策略（优先级从高到低）：
  1. LLM 提供的 address_for_geocoding → 腾讯地理编码（高配额）
  2. 腾讯 POI 搜索（配额 200/天，仅在1失败时使用）
  3. 保留原坐标（最终 fallback）

核心改进：省份验证
  每次 geocoding 后验证结果省份与预期省份是否匹配，
  防止搜到同名但省份不对的地点（Round 2 的主要问题）。

所需环境变量：TENCENT_MAP_KEY（设置在 .env.local）

用法:
  uv run python geocode_tencent.py --test        # 测试前 1 条（不写入）
  uv run python geocode_tencent.py --limit 100   # 处理前 N 条
  uv run python geocode_tencent.py               # 全量处理
  uv run python geocode_tencent.py --resume      # 从断点续跑
"""

import argparse
import difflib
import hashlib
import json
import os
import time
import urllib.parse
from pathlib import Path

import requests

from geocode_utils import extract_expected_province, is_province_ok

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND3_DIR = DATA_DIR / "round3"
BATCH_DIR = ROUND3_DIR / "geocode_batches"
GEMINI_HINTS = ROUND3_DIR / "gemini_geocode_result.json"
CHECKPOINT_FILE = ROUND3_DIR / "tencent_checkpoint.json"

TENCENT_GEOCODE_URL = "https://apis.map.qq.com/ws/geocoder/v1/"
TENCENT_SEARCH_URL = "https://apis.map.qq.com/ws/place/v1/search"

REQUEST_INTERVAL = 1.0        # 1s，1 QPS
CHECKPOINT_EVERY = 50
POI_SIMILARITY_THRESHOLD = 0.4

# POI 搜索每日配额追踪
POI_DAILY_LIMIT = 180         # 保留 20 次余量
POI_COUNT_FILE = ROUND3_DIR / "poi_daily_count.json"


# ---------------------------------------------------------------------------
# API key 加载
# ---------------------------------------------------------------------------

def load_env_keys() -> tuple[str | None, str | None]:
    """加载 API Key 和签名密钥。"""
    key = os.environ.get("TENCENT_MAP_KEY")
    sk = os.environ.get("TENCENT_MAP_SIGN_SECRET_KEY")
    if key:
        return key, sk
    env_file = Path(__file__).parent.parent.parent / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TENCENT_MAP_KEY="):
                key = line.split("=", 1)[1].strip()
            elif line.startswith("TENCENT_MAP_SIGN_SECRET_KEY="):
                sk = line.split("=", 1)[1].strip()
    return key, sk


def compute_sig(path: str, params: dict, sk: str) -> str:
    """计算腾讯地图 API 签名。sig = MD5(path?sorted_params_no_encode + SK)"""
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    sig_raw = f"{path}?{query_string}{sk}"
    return hashlib.md5(sig_raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# POI 日配额管理
# ---------------------------------------------------------------------------

def load_poi_count() -> int:
    if POI_COUNT_FILE.exists():
        data = json.loads(POI_COUNT_FILE.read_text(encoding="utf-8"))
        from datetime import date
        if data.get("date") == str(date.today()):
            return data.get("count", 0)
    return 0


def save_poi_count(count: int):
    from datetime import date
    POI_COUNT_FILE.write_text(
        json.dumps({"date": str(date.today()), "count": count}, ensure_ascii=False),
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 腾讯地图 API 调用
# ---------------------------------------------------------------------------

def geocode_by_address(address: str, api_key: str, sk: str | None = None) -> dict | None:
    """腾讯地理编码：地址 → 坐标。"""
    try:
        params = {"address": address, "key": api_key, "output": "json"}
        if sk:
            params["sig"] = compute_sig("/ws/geocoder/v1/", params, sk)
        resp = requests.get(TENCENT_GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    地理编码请求失败: {e}")
        return None

    status = data.get("status")
    if status != 0:
        if status == 121:
            print(f"    ✗ 地理编码 API 今日配额已耗尽")
        elif status != 0:
            print(f"    ✗ 地理编码返回错误 status={status}: {data.get('message', '')}")
        return None

    result = data.get("result", {})
    location = result.get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    if not lat or not lng:
        return None

    addr_components = result.get("address_components", {})
    province = addr_components.get("province") or None
    city = addr_components.get("city") or None
    district = addr_components.get("district") or None
    formatted_address = result.get("address") or None
    reliability = result.get("reliability", 0)

    return {
        "province": province,
        "city": city,
        "district": district,
        "address": formatted_address,
        "longitude": round(float(lng), 6),
        "latitude": round(float(lat), 6),
        "_geocode_method": "tencent_geocode",
        "_geocode_reliability": reliability,
    }


def search_poi(name: str, city_hint: str | None, api_key: str, sk: str | None = None) -> dict | None:
    """腾讯 POI 关键词搜索。仅在地理编码失败且有配额时调用。"""
    params = {
        "keyword": name,
        "key": api_key,
        "page_size": 10,
        "page_index": 1,
        "output": "json",
    }
    if city_hint:
        params["boundary"] = f"region({city_hint},0)"
    if sk:
        params["sig"] = compute_sig("/ws/place/v1/search", params, sk)

    try:
        resp = requests.get(TENCENT_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    POI 搜索请求失败: {e}")
        return None

    status = data.get("status")
    if status != 0 or not data.get("data"):
        if status == 121:
            print(f"    ✗ POI 搜索 API 今日配额已耗尽")
        elif status and status != 0:
            print(f"    ✗ POI 搜索返回错误 status={status}: {data.get('message', '')}")
        return None

    best_poi = None
    best_score = 0.0
    for poi in data["data"]:
        poi_name = poi.get("title", "")
        score = difflib.SequenceMatcher(None, name, poi_name).ratio()
        if score > best_score:
            best_score = score
            best_poi = poi

    if best_score < POI_SIMILARITY_THRESHOLD or best_poi is None:
        return None

    location = best_poi.get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    if not lat or not lng:
        return None

    ad_info = best_poi.get("ad_info", {})
    province = ad_info.get("province") or None
    city = ad_info.get("city") or None
    district = ad_info.get("district") or None
    address = best_poi.get("address") or None
    formatted_address = "".join(filter(None, [province, city, district, address, best_poi.get("title")]))

    return {
        "province": province,
        "city": city,
        "district": district,
        "address": formatted_address,
        "longitude": round(float(lng), 6),
        "latitude": round(float(lat), 6),
        "_geocode_method": "tencent_poi",
        "_geocode_score": round(best_score, 3),
        "_geocode_matched_name": best_poi.get("title", ""),
    }


# ---------------------------------------------------------------------------
# 单条记录 geocoding 策略
# ---------------------------------------------------------------------------

def geocode_record(rec: dict, hint: dict | None, api_key: str, sk: str | None, poi_count: int) -> tuple[dict | None, int]:
    """
    对单条记录尝试 geocoding，返回 (结果, 更新后的poi_count)。
    结果为 None 表示失败（保留原坐标）。
    """
    name = rec["name"]
    release_address = rec.get("release_address", "")
    # expected_province 必须从 release_address 提取，不能用存储的 province 字段
    # 因为 poi_province_mismatch 记录的 province 字段是 POI 搜错的结果
    expected_province = extract_expected_province(release_address) or rec.get("province")
    # city_hint 同理：poi_province_mismatch 的 city 也是错的，优先从 release_address 提取省份作为区域限定
    problems = rec.get("problem_types", [])
    if "poi_province_mismatch" in problems:
        # 用 release_address 的省份作为 city_hint，防止在错误的省份里搜索
        city_hint = expected_province or (release_address[:6] if release_address else None)
    else:
        city_hint = rec.get("city") or (release_address[:9] if release_address else None)

    def validate(result: dict | None) -> dict | None:
        if result is None:
            return None
        actual_province = result.get("province")
        if not is_province_ok(expected_province, actual_province):
            print(f"    ✗ 省份不匹配: 预期={expected_province}, 实际={actual_province}，拒绝")
            return None
        return result

    # 策略1: Gemini 精确地址 → 腾讯地理编码（主策略，高配额）
    if hint and hint.get("address_for_geocoding"):
        precise_addr = hint["address_for_geocoding"]
        print(f"    → 策略1: 腾讯地理编码（Gemini 精确地址）: {precise_addr}")
        result = validate(geocode_by_address(precise_addr, api_key, sk))
        time.sleep(REQUEST_INTERVAL)
        if result:
            result["_geocode_method"] = "tencent_geocode_gemini"
            result["address"] = precise_addr  # API 不返回 address，用 LLM 精确地址
            return result, poi_count

    # 策略2: 腾讯 POI 搜索（限配额）
    keyword = hint.get("poi_name") if hint else None
    search_name = keyword or name
    if poi_count < POI_DAILY_LIMIT:
        print(f"    → 策略2: 腾讯 POI 搜索 ({poi_count+1}/{POI_DAILY_LIMIT}): {search_name}")
        result = validate(search_poi(search_name, city_hint, api_key, sk))
        poi_count += 1
        time.sleep(REQUEST_INTERVAL)
        if result:
            if keyword:
                result["_geocode_method"] = "tencent_poi_gemini"
            return result, poi_count
    else:
        print(f"    → 策略2: POI 搜索跳过（今日配额已用完 {poi_count}/{POI_DAILY_LIMIT}）")

    print(f"    ✗ 所有策略失败，保留原坐标")
    return None, poi_count


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="腾讯地图批量 geocoding")
    parser.add_argument("--test", action="store_true", help="仅测试前5条（不写入）")
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 条")
    parser.add_argument("--resume", action="store_true", help="从断点续跑")
    parser.add_argument("--batch", type=int, default=0,
                        help="仅处理指定批次（如 --batch 1 处理 batch_001）")
    args = parser.parse_args()

    api_key, sk = load_env_keys()
    if not api_key:
        print("错误: 找不到 TENCENT_MAP_KEY")
        print("请在 .env.local 中添加: TENCENT_MAP_KEY=your_key")
        return
    if sk:
        print(f"已加载签名密钥（TENCENT_MAP_SIGN_SECRET_KEY）")
    else:
        print("提示: 未配置 TENCENT_MAP_SIGN_SECRET_KEY，若 API 启用签名校验将失败")

    # 从主数据文件实时推导目标列表（不依赖静态 needs_regeocode.json）
    # 这样多地址拆分后直接重跑，自动包含新子记录、排除已变为父记录的条目
    from generate_gemini_prompt_geocode import collect_targets
    with open(MAIN_FILE, encoding="utf-8") as f:
        all_records: list[dict] = json.load(f)
    targets: list[dict] = collect_targets(all_records)

    # 加载 LLM hints（来自 batch result 文件或 gemini_geocode_result.json）
    hints_by_id: dict[str, dict] = {}
    batch_filter_ids: set[str] | None = None

    if args.batch:
        batch_num = f"{args.batch:03d}"
        batch_file = BATCH_DIR / f"batch_{batch_num}.json"
        result_file = BATCH_DIR / f"result_{batch_num}.json"

        if not batch_file.exists():
            print(f"错误: 批次文件不存在: {batch_file}")
            return
        with open(batch_file, encoding="utf-8") as f:
            batch_filter_ids = {r["release_id"] for r in json.load(f)}
        print(f"批次模式: batch_{batch_num}，目标 {len(batch_filter_ids)} 条")

        if result_file.exists():
            with open(result_file, encoding="utf-8") as f:
                for h in json.load(f):
                    hints_by_id[h["release_id"]] = h
            print(f"已加载 LLM hints: {len(hints_by_id)} 条（来自 result_{batch_num}.json）")
        else:
            print(f"警告: {result_file.name} 不存在，将不使用 LLM 精确地址")
    elif GEMINI_HINTS.exists():
        with open(GEMINI_HINTS, encoding="utf-8") as f:
            hints_raw = json.load(f)
        for h in hints_raw:
            hints_by_id[h["release_id"]] = h
        print(f"已加载 Gemini hints: {len(hints_by_id)} 条")
    else:
        print(f"提示: 无 hints 文件，将不使用 LLM 精确地址")
        print("  建议先运行 batch_geocode_helper.py 或使用 --batch N 指定批次")

    # 加载断点
    done_ids: set[str] = set()
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            done_ids = set(json.load(f))
        print(f"从断点恢复: 已完成 {len(done_ids)} 条")

    # 加载主数据
    with open(MAIN_FILE, encoding="utf-8") as f:
        records: list[dict] = json.load(f)
    records_by_id: dict[str, dict] = {r["release_id"]: r for r in records}

    # 加载 POI 日配额
    poi_count = load_poi_count()
    print(f"今日 POI 搜索已用: {poi_count}/{POI_DAILY_LIMIT}")

    # 确定处理目标
    process_targets = [t for t in targets if t["release_id"] not in done_ids]
    if batch_filter_ids is not None:
        process_targets = [t for t in process_targets if t["release_id"] in batch_filter_ids]
    if args.limit:
        process_targets = process_targets[:args.limit]
    if args.test:
        process_targets = process_targets[:1]
        print("=== TEST MODE（只处理1条，不写入）===")

    print(f"待处理: {len(process_targets)} 条")

    updated: dict[str, dict] = {}  # release_id → 更新字段
    success = 0
    failed = 0

    for i, target in enumerate(process_targets):
        rid = target["release_id"]
        name = target["name"]
        hint = hints_by_id.get(rid)

        print(f"[{i+1}/{len(process_targets)}] {rid} {name}")
        if hint and hint.get("address_for_geocoding"):
            print(f"    Gemini: {hint['address_for_geocoding']}")

        result, poi_count = geocode_record(target, hint, api_key, sk, poi_count)

        if result:
            updated[rid] = result
            success += 1
            print(f"    ✓ {result['_geocode_method']}: ({result['latitude']}, {result['longitude']}) {result.get('province', '')}{result.get('city', '')}")
        else:
            failed += 1

        done_ids.add(rid)

        # 保存断点
        if (i + 1) % CHECKPOINT_EVERY == 0:
            save_poi_count(poi_count)
            if not args.test:
                CHECKPOINT_FILE.write_text(
                    json.dumps(list(done_ids), ensure_ascii=False),
                    encoding="utf-8"
                )
                # 应用更新到主数据文件（增量保存）
                _apply_updates(records, records_by_id, updated, MAIN_FILE)
                updated.clear()
                print(f"  [断点] 已保存 checkpoint（{i+1} 条）")

    # 最终保存
    save_poi_count(poi_count)
    if not args.test:
        CHECKPOINT_FILE.write_text(
            json.dumps(list(done_ids), ensure_ascii=False),
            encoding="utf-8"
        )
        if updated:
            # 重新加载（可能已被增量更新）
            with open(MAIN_FILE, encoding="utf-8") as f:
                records = json.load(f)
            records_by_id = {r["release_id"]: r for r in records}
            _apply_updates(records, records_by_id, updated, MAIN_FILE)

    print(f"\n=== 完成 ===")
    print(f"  成功: {success} 条")
    print(f"  失败（保留原坐标）: {failed} 条")
    print(f"  今日 POI 搜索总计: {poi_count}/{POI_DAILY_LIMIT}")

    if args.test:
        print("\n（TEST MODE：未写入任何文件）")
    else:
        print(f"\n已更新 {MAIN_FILE.name}")
        print("下一步: uv run python verify_round3.py")


def _apply_updates(records: list[dict], records_by_id: dict[str, dict],
                   updated: dict[str, dict], output_file: Path):
    """将 updated 字典中的字段更新到 records，写回文件。"""
    fields_to_update = [
        "province", "city", "district", "address",
        "latitude", "longitude", "_geocode_method",
        "_geocode_reliability", "_geocode_score", "_geocode_matched_name",
    ]
    for rid, result in updated.items():
        if rid in records_by_id:
            rec = records_by_id[rid]
            for field in fields_to_update:
                if field in result:
                    rec[field] = result[field]
                elif field in ("_geocode_score", "_geocode_matched_name", "_geocode_reliability"):
                    rec.pop(field, None)  # 清除不再适用的字段
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
