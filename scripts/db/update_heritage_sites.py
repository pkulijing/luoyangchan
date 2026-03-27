"""
批量更新 heritage_sites 表：按 release_id 匹配，只更新字段值，不清空不重建。

UUID 不变，不影响 user_site_marks 等关联数据。日常数据更新使用此脚本。

用法:
  uv run python db/update_heritage_sites.py              # 全量 upsert（更新所有字段）
  uv run python db/update_heritage_sites.py --fields image_url,baike_image_url  # 只更新指定字段（逐条 PATCH）
"""

import json
import os
from pathlib import Path

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
DEFAULT_INPUT = DATA_DIR / "heritage_sites_geocoded.json"

# 所有可更新字段（不含 release_id 本身，它是匹配键）
ALL_FIELDS = [
    "name", "province", "city", "district", "address", "category", "era",
    "batch", "batch_year", "latitude", "longitude", "description",
    "wikipedia_url", "baike_url", "image_url", "baike_image_url",
    "tags", "release_address",
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def get_config() -> tuple[str, str]:
    dotenv = load_env()
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
           or dotenv.get("NEXT_PUBLIC_SUPABASE_URL")
           or "http://127.0.0.1:54321")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or dotenv.get("SUPABASE_SERVICE_ROLE_KEY")
           or "")
    return url, key


def make_row(site: dict) -> dict:
    """构造包含全部字段的行（用于全量 upsert）。"""
    return {
        "name": site["name"],
        "province": site.get("province"),
        "city": site.get("city"),
        "district": site.get("district"),
        "address": site.get("address"),
        "category": site["category"],
        "era": site.get("era"),
        "batch": site.get("batch"),
        "batch_year": site.get("batch_year"),
        "latitude": site.get("latitude"),
        "longitude": site.get("longitude"),
        "description": site.get("description"),
        "wikipedia_url": site.get("wikipedia_url"),
        "baike_url": site.get("baike_url"),
        "image_url": site.get("image_url"),
        "baike_image_url": site.get("baike_image_url"),
        "tags": site.get("tags"),
        "release_id": site.get("release_id"),
        "release_address": site.get("release_address"),
    }


def upsert_batch(rows: list[dict], supabase_url: str, headers: dict, batch_size: int) -> tuple[int, int]:
    """全量 upsert（按 release_id 匹配）。"""
    upserted = 0
    errors = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        resp = requests.post(
            f"{supabase_url}/rest/v1/heritage_sites?on_conflict=release_id",
            json=batch,
            headers={
                **headers,
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            upserted += len(batch)
        else:
            print(f"  Error at batch {i}: {resp.status_code} {resp.text[:200]}")
            errors += 1
        progress = min(i + batch_size, len(rows))
        print(f"  {progress}/{len(rows)} ({upserted} updated, {errors} errors)")
    return upserted, errors


def patch_by_field(sites: list[dict], fields: list[str], supabase_url: str, headers: dict) -> tuple[int, int]:
    """逐条 PATCH 指定字段（不碰其他字段）。"""
    updated = 0
    errors = 0
    total = len(sites)
    for i, site in enumerate(sites):
        rid = site.get("release_id")
        if not rid:
            continue
        body = {f: site.get(f) for f in fields}
        resp = requests.patch(
            f"{supabase_url}/rest/v1/heritage_sites?release_id=eq.{rid}",
            json=body,
            headers={**headers, "Prefer": "return=minimal"},
            timeout=10,
        )
        if resp.status_code in (200, 204):
            updated += 1
        else:
            print(f"  Error [{rid}]: {resp.status_code} {resp.text[:200]}")
            errors += 1

        if (i + 1) % 500 == 0 or i == total - 1:
            print(f"  {i+1}/{total} ({updated} updated, {errors} errors)")
    return updated, errors


def main():
    import argparse

    parser = argparse.ArgumentParser(description="批量更新 heritage_sites 表")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--fields",
        help="只更新指定字段（逗号分隔，逐条 PATCH）。不指定则全量 upsert。例：--fields image_url,baike_image_url",
    )
    args = parser.parse_args()

    url, key = get_config()
    if not key:
        print("Error: SUPABASE_SERVICE_ROLE_KEY not found")
        return

    with open(args.input, encoding="utf-8") as f:
        sites = json.load(f)
    print(f"Loaded {len(sites)} sites")

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    if args.fields:
        # 指定字段：逐条 PATCH（慢但只改指定字段，不碰其他）
        fields = [f.strip() for f in args.fields.split(",")]
        invalid = [f for f in fields if f not in ALL_FIELDS]
        if invalid:
            print(f"Error: 未知字段 {invalid}，可用字段: {ALL_FIELDS}")
            return
        print(f"模式: 逐条 PATCH")
        print(f"更新字段: {', '.join(fields)}\n")
        cnt, errs = patch_by_field(sites, fields, url, headers)
    else:
        # 全量 upsert
        print(f"模式: 全量 upsert\n")
        rows = [make_row(s) for s in sites if s.get("release_id")]
        cnt, errs = upsert_batch(rows, url, headers, args.batch_size)

    print(f"\nDone: {cnt} updated, {errs} errors")


if __name__ == "__main__":
    main()
