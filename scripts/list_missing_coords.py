"""
列出 heritage_sites_geocoded.json 中缺少坐标的条目，保存到 data/missing_coords.json。

用法:
  uv run python list_missing_coords.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT = DATA_DIR / "missing_coords.json"

with open(INPUT, encoding="utf-8") as f:
    sites = json.load(f)

missing = [
    {
        "release_id": s.get("release_id"),
        "name": s.get("name"),
        "batch": s.get("batch"),
        "category": s.get("category"),
        "release_address": s.get("release_address"),
    }
    for s in sites
    if not (s.get("latitude") and s.get("longitude"))
]

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(missing, f, ensure_ascii=False, indent=2)

print(f"共 {len(missing)} 条缺坐标记录，已保存到 {OUTPUT}")
for s in missing:
    print(f"  [{s['release_id']:10s}] {s['name'][:24]:24s} | {s['release_address'] or ''}")
