"""
第三轮数据清洗 - Phase 2: 生成 geocoding 优化 Gemini prompt

直接从 heritage_sites_geocoded.json 实时推导需要重新 geocoding 的记录，
不依赖静态的 needs_regeocode.json。

这样可以在多地址拆分（Phase 1）完成后直接重跑本脚本，
自动包含新增的子记录、自动排除已变为父记录的条目。

Gemini 的任务：为每条记录提供精确地址（address_for_geocoding），
用于腾讯地图地理编码 API 获取高精度坐标。

产出：
  data/round3/gemini_prompt_geocode.md     — prompt 正文
  data/round3/gemini_geocode_input.json    — 附件（传给 Gemini）

Gemini 保存结果到：
  data/round3/gemini_geocode_result.json

用法:
  uv run python generate_gemini_prompt_geocode.py
"""

import json
from collections import defaultdict
from pathlib import Path

from geocode_utils import extract_expected_province, is_province_ok

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ROUND3_DIR = DATA_DIR / "round3"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_PROMPT = ROUND3_DIR / "gemini_prompt_geocode.md"
OUTPUT_INPUT = ROUND3_DIR / "gemini_geocode_input.json"


def collect_targets(records: list[dict]) -> list[dict]:
    """
    从主数据文件实时推导需要 geocoding 的记录。
    每次运行都反映当前数据状态，多地址拆分后重跑结果自动更新。
    """
    # 找出重复坐标组（用于标记 poi_duplicate）
    coord_groups: dict[tuple, list] = defaultdict(list)
    for rec in records:
        if rec.get("_is_parent") or rec.get("latitude") is None:
            continue
        coord_groups[(rec["latitude"], rec["longitude"])].append(rec["release_id"])
    dup_coord_ids: set[str] = {
        rid for rids in coord_groups.values() if len(rids) > 1 for rid in rids
    }

    targets = []
    seen: set[str] = set()

    for rec in records:
        if rec.get("_is_parent"):
            continue  # 父记录无需 geocoding
        rid = rec["release_id"]
        if rid in seen:
            continue
        seen.add(rid)

        method = rec.get("_geocode_method")
        problems = []

        # 无坐标子记录（Phase 1 拆分后新增）
        if rec.get("_parent_release_id") and rec.get("latitude") is None:
            problems.append("no_coords_child")

        # geocode fallback（精度低）
        elif method == "geocode":
            problems.append("geocode_fallback")

        # POI 省份不匹配
        if method and "poi" in method and "no_coords_child" not in problems:
            expected = extract_expected_province(rec.get("release_address", ""))
            actual = rec.get("province")
            if not is_province_ok(expected, actual):
                problems.append("poi_province_mismatch")

        # POI 重复坐标（且不是纯 geocode 造成的）
        if rid in dup_coord_ids and method and "poi" in method and "poi_province_mismatch" not in problems:
            problems.append("poi_duplicate")

        if not problems:
            continue

        targets.append({
            "release_id": rid,
            "name": rec["name"],
            "release_address": rec.get("release_address"),
            "province": rec.get("province"),
            "city": rec.get("city"),
            "district": rec.get("district"),
            "latitude": rec.get("latitude"),
            "longitude": rec.get("longitude"),
            "_geocode_method": method,
            "problem_types": problems,
        })

    return targets


def main():
    with open(MAIN_FILE, encoding="utf-8") as f:
        all_records: list[dict] = json.load(f)

    needs_regeocode = collect_targets(all_records)

    print(f"需要 geocoding 的记录总数: {len(needs_regeocode)}")
    from collections import Counter
    type_count = Counter(pt for r in needs_regeocode for pt in r.get("problem_types", []))
    for pt, cnt in sorted(type_count.items()):
        print(f"  - {pt}: {cnt} 条")

    # 构建 Gemini 输入附件（精简字段，减小附件大小）
    gemini_input = []
    for rec in needs_regeocode:
        problems = rec.get("problem_types", [])
        release_address = rec.get("release_address", "")

        # expected_province 必须从 release_address 提取，而非 province 字段
        # 原因：对于 poi_province_mismatch 记录，province 字段存的是 POI 搜错的结果，
        # 用它做 expected 会误导 Gemini（如"周家宅院"的官方地址在云南，
        # 但 province 字段因 POI 错误写成了上海）
        addr_province = extract_expected_province(release_address)

        item = {
            "release_id": rec["release_id"],
            "name": rec["name"],
            "official_address": release_address,
            "problem_types": problems,
        }
        if addr_province:
            item["expected_province"] = addr_province
        # expected_city 只在省份可信时才包含（poi_province_mismatch 的 city 也是错的）
        if "poi_province_mismatch" not in problems and rec.get("city"):
            item["expected_city"] = rec["city"]

        gemini_input.append(item)

    with open(OUTPUT_INPUT, "w", encoding="utf-8") as f:
        json.dump(gemini_input, f, ensure_ascii=False, indent=2)
    print(f"\n已写出附件: {OUTPUT_INPUT}（{len(gemini_input)} 条）")

    # 构建 prompt
    prompt = f"""# 全国重点文物保护单位精确地址研究

## 背景

我在构建全国重点文物保护单位地图数据库，需要为每个文保单位获取精确的地理坐标。
目前有 {len(gemini_input)} 条记录存在定位问题：
- `geocode_fallback`：原始 POI 搜索失败，仅有区县级精度坐标
- `poi_province_mismatch`：POI 搜索返回了省份不正确的结果（如"天一阁"搜到了北京而非浙江宁波）
- `poi_duplicate`：多条不同文保单位被搜索到了同一个地点
- `no_coords_child`：多地址拆分后的子条目，尚无坐标

## 你的任务

请为附件 JSON 中的每条记录提供：

1. **address_for_geocoding**（必填）：用于地图定位的精确地址字符串。
   - 格式要求：省 + 市 + 县/区 + 乡镇/街道 + 具体地点名称
   - 示例："湖南省湘潭市韶山市韶山冲上屋场"、"浙江省宁波市海曙区天一街10号"
   - 如果文保单位是一个景区/博物馆，请用景区/博物馆的地址
   - 如果是遗址，请用遗址所在村庄/地块的地址

2. **poi_name**（选填）：在地图 POI 搜索中最可能找到的名称（如与官方名称不同）

3. **notes**（选填）：影响定位的重要说明（如已改名、已拆除、需要区分同名地点等）

## 输出格式

请输出 JSON 数组（不要包含其他文字，直接输出 JSON）：

```json
[
  {{
    "release_id": "2-31",
    "address_for_geocoding": "浙江省宁波市海曙区天一街10号",
    "poi_name": "天一阁博物院",
    "notes": "原 POI 搜索误匹配到北京天一阁，应为宁波"
  }},
  {{
    "release_id": "1-4",
    "address_for_geocoding": "湖南省湘潭市韶山市韶山冲上屋场",
    "poi_name": "毛泽东故居",
    "notes": null
  }}
]
```

## 注意事项

- `release_id` 字段必须与输入完全一致（不要修改）
- `official_address` 是官方公告中的地址，可作为参考，但不一定精确
- `expected_province`/`expected_city` 是预期所在省市，**请确保你提供的地址在这个省市范围内**
- 对于拿不准的记录，宁可提供到县级地址（确保省份正确），也不要猜测具体地点
- 信息来源建议：百度百科、中文维基百科、国家文物局官网、各省市文物局官网

## 待处理记录

附件文件：`gemini_geocode_input.json`（{len(gemini_input)} 条）

请处理全部 {len(gemini_input)} 条记录并输出完整 JSON。
"""

    with open(OUTPUT_PROMPT, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"已写出 prompt: {OUTPUT_PROMPT}")

    print(f"\n【操作步骤】")
    print(f"1. 打开 {OUTPUT_PROMPT.name}，复制 prompt 内容")
    print(f"2. 将 {OUTPUT_INPUT.name} 作为附件传给 Gemini")
    print(f"3. 将 Gemini 返回的 JSON 保存到:")
    print(f"   data/round3/gemini_geocode_result.json")
    print(f"4. 运行 geocode_tencent.py --test 测试")
    print(f"5. 运行 geocode_tencent.py --resume 执行全量 geocoding")


if __name__ == "__main__":
    main()
