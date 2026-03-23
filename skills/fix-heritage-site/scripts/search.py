#!/usr/bin/env python3
"""
在文保单位数据中搜索记录。

用法:
  # 按 release_id 精确搜索
  uv run python search.py --id 7-817

  # 按名称模糊搜索
  uv run python search.py --name "某遗址"

  # 按省份+名称搜索
  uv run python search.py --province 山西 --name "某"

  # 显示详细信息
  uv run python search.py --id 7-817 --verbose
"""

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"


def search(data: list[dict], release_id: str = None, name: str = None, province: str = None) -> list[dict]:
    """搜索匹配的记录。"""
    matches = data

    if release_id:
        matches = [r for r in matches if r.get("release_id") == release_id]

    if name:
        matches = [r for r in matches if name in r.get("name", "")]

    if province:
        matches = [r for r in matches if province in (r.get("province") or "")]

    return matches


def print_record(rec: dict, verbose: bool = False):
    """打印单条记录。"""
    print(f"release_id: {rec.get('release_id')}")
    print(f"name: {rec.get('name')}")
    print(f"province: {rec.get('province')} / city: {rec.get('city')} / district: {rec.get('district')}")
    print(f"address: {rec.get('address')}")
    print(f"coords: ({rec.get('latitude')}, {rec.get('longitude')})")
    print(f"method: {rec.get('_geocode_method')}")

    if verbose:
        print(f"era: {rec.get('era')}")
        print(f"category: {rec.get('category')}")
        print(f"batch: {rec.get('batch')} ({rec.get('batch_year')})")
        print(f"release_address: {rec.get('release_address')}")
        print(f"wikipedia_url: {rec.get('wikipedia_url')}")
        if rec.get("_geocode_reliability"):
            print(f"reliability: {rec.get('_geocode_reliability')}")
        if rec.get("_geocode_level"):
            print(f"level: {rec.get('_geocode_level')}")

    print("---")


def main():
    parser = argparse.ArgumentParser(description="搜索文保单位数据")
    parser.add_argument("--id", dest="release_id", help="按 release_id 精确搜索")
    parser.add_argument("--name", "-n", help="按名称模糊搜索")
    parser.add_argument("--province", "-p", help="按省份筛选")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    parser.add_argument("--limit", "-l", type=int, default=10, help="最多显示条数 (default: 10)")
    args = parser.parse_args()

    if not args.release_id and not args.name and not args.province:
        parser.print_help()
        return

    with open(MAIN_FILE, encoding="utf-8") as f:
        data = json.load(f)

    matches = search(data, args.release_id, args.name, args.province)

    print(f"找到 {len(matches)} 条匹配记录" + (f"（显示前 {args.limit} 条）" if len(matches) > args.limit else ""))
    print()

    for rec in matches[:args.limit]:
        print_record(rec, args.verbose)


if __name__ == "__main__":
    main()
