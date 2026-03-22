"""
第三轮数据清洗 - Phase 1: 生成多地址拆分 Gemini prompt

读取 analyze_data_quality.py 产出的 multi_address_candidates.json，
生成供 Gemini Deep Research 使用的 prompt 和 JSON 附件。

产出：
  data/round3/gemini_prompt_multi_address.md   — prompt 正文
  data/round3/gemini_multi_address_input.json  — 附件（传给 Gemini）

用法:
  uv run python generate_gemini_prompt_multi_address.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ROUND3_DIR = DATA_DIR / "round3"
INPUT_FILE = ROUND3_DIR / "multi_address_candidates.json"
OUTPUT_PROMPT = ROUND3_DIR / "gemini_prompt_multi_address.md"
OUTPUT_INPUT = ROUND3_DIR / "gemini_multi_address_input.json"


def main():
    if not INPUT_FILE.exists():
        print(f"错误: 请先运行 analyze_data_quality.py 生成 {INPUT_FILE.name}")
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        candidates: list[dict] = json.load(f)

    # 只取 strong 候选（borderline 通常是2地点，且在同省，不需要拆分）
    # 排除已拆分的记录（_is_parent: True 的记录在 analyze 时已被过滤，但保险起见再检查）
    strong = [c for c in candidates if c["confidence"] == "strong" and not c.get("_is_parent")]
    borderline = [c for c in candidates if c["confidence"] == "borderline" and not c.get("_is_parent")]

    print(f"Strong 候选: {len(strong)} 条（含跨省 {sum(1 for c in strong if c['cross_province'])} 条）")
    print(f"Borderline 候选: {len(borderline)} 条（borderline 不纳入 prompt，通常2地点同省无需拆分）")

    # 构建 Gemini 输入附件（仅 strong）
    gemini_input = []
    for c in strong:
        gemini_input.append({
            "release_id": c["release_id"],
            "name": c["name"],
            "release_address": c["release_address"],
            "parsed_segments": c["parsed_segments"],
            "cross_province": c["cross_province"],
        })

    with open(OUTPUT_INPUT, "w", encoding="utf-8") as f:
        json.dump(gemini_input, f, ensure_ascii=False, indent=2)
    print(f"已写出附件: {OUTPUT_INPUT}")

    # 构建 prompt
    prompt = f"""# 全国重点文物保护单位多地址拆分分析

## 背景

我在整理全国重点文物保护单位（文保单位）数据库，其中部分文保单位在官方公告中包含多个物理地点。
例如"唐代帝陵"实际上是分布在陕西省多个县的18座帝陵，"京杭大运河"则跨越6个省市。

我需要你帮我：
1. 判断每个候选条目是否确实需要拆分为多个子条目
2. 对需要拆分的条目，提供每个子条目的详细信息

## 判断原则

**需要拆分（needs_splitting: true）**：
- 文保单位包含多个在地理上明显分离的实体（如多座陵墓、多处遗址、多个廊桥）
- 每个子实体有独立的地理坐标

**不需要拆分（needs_splitting: false）**：
- 虽然地址跨多个行政区，但实际上是一个连续的线性遗址（如古驿道的某一段，但段内无明确子地点）
- 只是行政区划表述，实际位置在单一地点（如"XX县、YY县交界处"）
- 经充分调研后无法确定明确的子地点列表

## 输出格式

请输出 JSON 数组，每个条目格式如下：

```json
[
  {{
    "release_id": "5-184",
    "needs_splitting": true,
    "reason": "该单位包含18座唐代帝陵，分散在陕西省6个县，每座陵墓有独立地理位置",
    "children": [
      {{
        "name": "唐代帝陵-唐献陵（李渊）",
        "address_for_geocoding": "陕西省渭南市富平县吕村镇唐献陵",
        "province": "陕西省",
        "city": "渭南市",
        "district": "富平县"
      }},
      {{
        "name": "唐代帝陵-唐昭陵（李世民）",
        "address_for_geocoding": "陕西省咸阳市礼泉县烟霞镇唐昭陵",
        "province": "陕西省",
        "city": "咸阳市",
        "district": "礼泉县"
      }}
    ]
  }},
  {{
    "release_id": "7-516",
    "needs_splitting": false,
    "reason": "茶马古道是连续的线性遗址，虽跨越四川、云南、贵州，但无法拆分为独立的地点",
    "children": []
  }}
]
```

## 命名规范

- 子条目名称格式：`父名称-子名称`，如"唐代帝陵-唐献陵"
- 子名称应简洁但有区分度（包含核心识别信息，如陵墓名、地名等）
- `address_for_geocoding` 应尽量精确（到村镇、景区门牌级别），这个地址将用于地图定位

## 待分析条目

以下是附件 `gemini_multi_address_input.json` 中的 {len(gemini_input)} 个候选条目。
请针对每个条目做充分调研（可查阅中文维基百科、百度百科、国家文物局官网等），
然后输出完整的 JSON 结果。

注意：部分条目如"金界壕遗址"（金长城）、"茶马古道"等是线性遗址，请根据实际情况判断是否拆分。
"""

    with open(OUTPUT_PROMPT, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"已写出 prompt: {OUTPUT_PROMPT}")

    print(f"\n【操作步骤】")
    print(f"1. 将 {OUTPUT_PROMPT.name} 的内容作为 Gemini prompt")
    print(f"2. 将 {OUTPUT_INPUT.name} 作为附件上传给 Gemini")
    print(f"3. 将 Gemini 返回的 JSON 保存到:")
    print(f"   data/round3/gemini_multi_address_result.json")
    print(f"4. 运行 apply_multi_address_split.py --dry-run 预览")
    print(f"5. 运行 apply_multi_address_split.py --apply 执行拆分")

    # 预览候选列表
    print(f"\n【Strong 候选预览】")
    for c in strong:
        cross = " 【跨省】" if c["cross_province"] else ""
        print(f"  {c['release_id']}: {c['name']}{cross}")


if __name__ == "__main__":
    main()
