"""
将爬取的文保单位数据导入 Supabase 数据库。

用法:
  uv run python seed_supabase.py --url YOUR_SUPABASE_URL --key YOUR_SERVICE_ROLE_KEY

注意: 使用 service_role key (非 anon key) 以绕过 RLS。
"""

import json
import os
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "heritage_sites_with_coords.json"


def seed(supabase_url: str, service_key: str, input_file: str, batch_size: int = 100):
    """批量插入数据到 Supabase"""
    with open(input_file, encoding="utf-8") as f:
        sites = json.load(f)

    print(f"Loaded {len(sites)} sites from {input_file}")

    # 准备数据：移除 None 值的经纬度（Supabase 不需要），移除不属于表结构的字段
    rows = []
    for site in sites:
        row = {
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
            "image_url": site.get("image_url"),
        }
        rows.append(row)

    # 分批插入
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    inserted = 0
    errors = 0

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        resp = requests.post(
            f"{supabase_url}/rest/v1/heritage_sites",
            json=batch,
            headers=headers,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            inserted += len(batch)
        else:
            print(f"  Error at batch {i}: {resp.status_code} {resp.text[:200]}")
            errors += 1

        progress = min(i + batch_size, len(rows))
        print(f"  Progress: {progress}/{len(rows)} ({inserted} inserted, {errors} errors)")

    print(f"\nDone: {inserted} inserted, {errors} batch errors")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed heritage sites into Supabase")
    parser.add_argument(
        "--url",
        default=os.environ.get("SUPABASE_URL"),
        help="Supabase project URL (or set SUPABASE_URL env var)",
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        help="Supabase service role key (or set SUPABASE_SERVICE_ROLE_KEY env var)",
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    if not args.url or not args.key:
        print("Error: Supabase URL and service role key are required.")
        print("  Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars, or use --url and --key flags.")
        return

    seed(args.url, args.key, args.input, args.batch_size)


if __name__ == "__main__":
    main()
