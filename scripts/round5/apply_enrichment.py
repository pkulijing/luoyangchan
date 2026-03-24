"""
Phase 4a: 将富化结果合并入主数据文件。

用法:
  uv run python round5/apply_enrichment.py --dry-run    # 只统计，不写文件
  uv run python round5/apply_enrichment.py              # 执行合并
"""

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND5_DIR = DATA_DIR / "round5"
BAIKE_FILE = ROUND5_DIR / "baike_data.json"
ENRICHMENT_FILE = ROUND5_DIR / "enrichment_results.json"


def main():
    parser = argparse.ArgumentParser(description="Merge enrichment results into main data file")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)
    print(f"主数据文件: {len(sites)} 条记录")

    # 加载百度百科数据（baike_url）
    baike_map: dict[str, dict] = {}
    if BAIKE_FILE.exists():
        with open(BAIKE_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                baike_map[item["release_id"]] = item
        print(f"百度百科数据: {len(baike_map)} 条")
    else:
        print(f"警告: {BAIKE_FILE} 不存在，跳过 baike_url")

    # 加载 LLM 富化结果（description + tags）
    enrichment_map: dict[str, dict] = {}
    if ENRICHMENT_FILE.exists():
        with open(ENRICHMENT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                enrichment_map[item["release_id"]] = item
        print(f"富化结果: {len(enrichment_map)} 条")
    else:
        print(f"警告: {ENRICHMENT_FILE} 不存在，跳过 description/tags")

    # 合并
    updated_desc = 0
    updated_tags = 0
    updated_baike = 0

    for site in sites:
        rid = site["release_id"]

        # 合并 baike_url
        baike = baike_map.get(rid)
        if baike and baike.get("baike_url"):
            site["baike_url"] = baike["baike_url"]
            updated_baike += 1

        # 合并 description 和 tags（不覆盖已有非空值）
        enrichment = enrichment_map.get(rid)
        if enrichment:
            if enrichment.get("description") and not site.get("description"):
                site["description"] = enrichment["description"]
                updated_desc += 1
            if enrichment.get("tags") and not site.get("tags"):
                site["tags"] = enrichment["tags"]
                updated_tags += 1

    print(f"\n合并统计:")
    print(f"  description: {updated_desc}/{len(sites)}")
    print(f"  tags: {updated_tags}/{len(sites)}")
    print(f"  baike_url: {updated_baike}/{len(sites)}")

    if args.dry_run:
        print("\n[dry-run] 不写入文件")
        # 打印一个样本
        sample = next((s for s in sites if s.get("description")), None)
        if sample:
            print(f"\n样本 ({sample['name']}):")
            print(f"  description: {sample.get('description', '')[:100]}...")
            print(f"  tags: {sample.get('tags', [])[:10]}")
            print(f"  baike_url: {sample.get('baike_url', '')}")
    else:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {MAIN_FILE}")


if __name__ == "__main__":
    main()
