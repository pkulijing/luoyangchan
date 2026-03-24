"""
审计 DeepSeek 富化结果的质量。

检查项：
1. 描述长度分布（过短 < 100 字可能质量低）
2. 标签数量分布（过少 < 5 个覆盖不足）
3. 空描述/空标签的记录
4. 标签是否只是重复已有字段（省份、城市）
5. 有百科参考 vs 无参考的质量对比
6. 各类别的抽样输出

用法:
  uv run python round5/audit_enrichment.py
  uv run python round5/audit_enrichment.py --samples 5    # 每级别抽样数
"""

import argparse
import json
import random
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND5_DIR = DATA_DIR / "round5"
ENRICHMENT_FILE = ROUND5_DIR / "enrichment_results.json"
WIKI_FILE = ROUND5_DIR / "wikipedia_extracts.json"
BAIKE_FILE = ROUND5_DIR / "baike_data.json"


def main():
    parser = argparse.ArgumentParser(description="Audit enrichment quality")
    parser.add_argument("--samples", type=int, default=3, help="每级别抽样数")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)
    site_map = {s["release_id"]: s for s in sites}

    with open(ENRICHMENT_FILE, encoding="utf-8") as f:
        enrichments = json.load(f)
    enrich_map = {e["release_id"]: e for e in enrichments}

    # 加载参考数据覆盖信息
    wiki_has = set()
    if WIKI_FILE.exists():
        with open(WIKI_FILE, encoding="utf-8") as f:
            for w in json.load(f):
                if w.get("wikipedia_extract"):
                    wiki_has.add(w["release_id"])

    baike_has = set()
    if BAIKE_FILE.exists():
        with open(BAIKE_FILE, encoding="utf-8") as f:
            for b in json.load(f):
                if b.get("baike_abstract"):
                    baike_has.add(b["release_id"])

    # === 基础统计 ===
    total = len(enrichments)
    empty_desc = []
    empty_tags = []
    short_desc = []  # < 100 字
    few_tags = []    # < 5 个
    good = []
    low_quality_tags = []  # 标签只是重复已有字段

    for e in enrichments:
        rid = e["release_id"]
        desc = e.get("description", "")
        tags = e.get("tags", [])
        site = site_map.get(rid, {})

        if not desc:
            empty_desc.append(rid)
            continue
        if not tags:
            empty_tags.append(rid)

        desc_len = len(desc)
        tag_count = len(tags)

        if desc_len < 100:
            short_desc.append((rid, desc_len))
        if tag_count < 5:
            few_tags.append((rid, tag_count))

        # 检查标签是否只是重复已有字段
        existing_values = {
            site.get("province", ""), site.get("city", ""),
            site.get("district", ""), site.get("category", ""),
        }
        existing_values.discard("")
        existing_values.discard(None)
        unique_tags = [t for t in tags if t not in existing_values]
        if len(unique_tags) < len(tags) * 0.5:
            low_quality_tags.append(rid)

        if desc_len >= 100 and tag_count >= 5:
            good.append(rid)

    print("=" * 60)
    print("富化结果质量审计报告")
    print("=" * 60)

    print(f"\n总记录: {total}")
    print(f"  有描述: {total - len(empty_desc)} ({(total - len(empty_desc))*100//total}%)")
    print(f"  有标签: {total - len(empty_tags)} ({(total - len(empty_tags))*100//total}%)")
    print(f"  空描述: {len(empty_desc)}")
    print(f"  空标签: {len(empty_tags)}")

    # 描述长度分布
    desc_lens = [len(e.get("description", "")) for e in enrichments if e.get("description")]
    if desc_lens:
        print(f"\n描述长度分布:")
        print(f"  最短: {min(desc_lens)} 字")
        print(f"  最长: {max(desc_lens)} 字")
        print(f"  平均: {sum(desc_lens)//len(desc_lens)} 字")
        print(f"  < 100 字: {len(short_desc)} 条")
        print(f"  100-200 字: {sum(1 for l in desc_lens if 100 <= l < 200)} 条")
        print(f"  200-300 字: {sum(1 for l in desc_lens if 200 <= l < 300)} 条")
        print(f"  > 300 字: {sum(1 for l in desc_lens if l >= 300)} 条")

    # 标签数量分布
    tag_counts = [len(e.get("tags", [])) for e in enrichments if e.get("tags")]
    if tag_counts:
        print(f"\n标签数量分布:")
        print(f"  最少: {min(tag_counts)} 个")
        print(f"  最多: {max(tag_counts)} 个")
        print(f"  平均: {sum(tag_counts)//len(tag_counts)} 个")
        print(f"  < 5 个: {len(few_tags)} 条")
        print(f"  5-10 个: {sum(1 for c in tag_counts if 5 <= c < 10)} 条")
        print(f"  10-15 个: {sum(1 for c in tag_counts if 10 <= c < 15)} 条")
        print(f"  ≥ 15 个: {sum(1 for c in tag_counts if c >= 15)} 条")

    # 标签质量
    print(f"\n标签质量:")
    print(f"  低质量（>50% 重复已有字段）: {len(low_quality_tags)} 条")

    # 有参考 vs 无参考对比
    with_ref = [e for e in enrichments if e["release_id"] in wiki_has or e["release_id"] in baike_has]
    without_ref = [e for e in enrichments if e["release_id"] not in wiki_has and e["release_id"] not in baike_has]

    def avg_len(items):
        lens = [len(e.get("description", "")) for e in items if e.get("description")]
        return sum(lens) // max(len(lens), 1) if lens else 0

    def avg_tags(items):
        counts = [len(e.get("tags", [])) for e in items if e.get("tags")]
        return sum(counts) // max(len(counts), 1) if counts else 0

    print(f"\n有百科参考 ({len(with_ref)} 条) vs 无参考 ({len(without_ref)} 条):")
    print(f"  平均描述长度: {avg_len(with_ref)} 字 vs {avg_len(without_ref)} 字")
    print(f"  平均标签数: {avg_tags(with_ref)} 个 vs {avg_tags(without_ref)} 个")

    # === 抽样输出 ===
    n = args.samples

    def print_samples(label, rids):
        sample = random.sample(rids, min(n, len(rids)))
        print(f"\n--- {label} (抽样 {len(sample)} 条) ---")
        for rid in sample:
            e = enrich_map.get(rid, {})
            site = site_map.get(rid, {})
            name = site.get("name", "?")
            desc = e.get("description", "")[:120]
            tags = e.get("tags", [])[:8]
            has_wiki = "W" if rid in wiki_has else " "
            has_baike = "B" if rid in baike_has else " "
            print(f"\n  [{rid}] {name} [{has_wiki}{has_baike}]")
            print(f"    描述({len(e.get('description', ''))}字): {desc}...")
            print(f"    标签({len(e.get('tags', []))}个): {tags}")

    if empty_desc:
        print(f"\n{'='*60}")
        print(f"空描述记录 ({len(empty_desc)} 条):")
        for rid in empty_desc:
            name = site_map.get(rid, {}).get("name", "?")
            print(f"  {rid}: {name}")

    if short_desc:
        print_samples(f"短描述 (<100字, 共{len(short_desc)}条)", [r for r, _ in short_desc])

    if good:
        print_samples(f"优质记录 (≥100字 + ≥5标签, 共{len(good)}条)", good)

    # 无参考资料的抽样
    no_ref_rids = [e["release_id"] for e in without_ref if e.get("description")]
    if no_ref_rids:
        print_samples(f"无百科参考 (共{len(no_ref_rids)}条有描述)", no_ref_rids)

    # 知名遗址检查
    famous = ["1-30", "1-33", "1-36", "1-37", "1-164", "2-21", "3-1"]
    famous_names = {"1-30": "天安门", "1-33": "云冈石窟", "1-36": "莫高窟",
                    "1-37": "麦积山石窟", "1-164": "秦始皇陵", "2-21": "灵岩寺", "3-1": "故宫"}
    print(f"\n--- 知名遗址检查 ---")
    for rid in famous:
        e = enrich_map.get(rid, {})
        name = famous_names.get(rid, site_map.get(rid, {}).get("name", "?"))
        desc = e.get("description", "(空)")[:150]
        tags = e.get("tags", [])
        print(f"\n  [{rid}] {name}")
        print(f"    描述: {desc}...")
        print(f"    标签: {tags}")


if __name__ == "__main__":
    main()
