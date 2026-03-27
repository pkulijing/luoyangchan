"""
批量更新 heritage_sites 表：按 release_id 匹配，只更新字段值，不清空不重建。

UUID 不变，不影响 user_site_marks 等关联数据。日常数据更新使用此脚本。

用法:
  uv run python db/update_heritage_sites.py              # 更新全部字段
  uv run python db/update_heritage_sites.py --fields image_url,baike_image_url  # 只更新指定字段
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


def upsert_batch(rows: list[dict], supabase_url: str, headers: dict, batch_size: int) -> tuple[int, int]:
    upserted = 0
    errors = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        resp = requests.post(
            f"{supabase_url}/rest/v1/heritage_sites?on_conflict=release_id",
            json=batch,
            headers={
                **headers,
                "Prefer": "resolution=merge-duplicates,return=representation",
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


def main():
    import argparse

    parser = argparse.ArgumentParser(description="批量更新 heritage_sites 表")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--fields",
        help="只更新指定字段（逗号分隔），默认更新全部。例：--fields image_url,baike_image_url",
    )
    args = parser.parse_args()

    url, key = get_config()
    if not key:
        print("Error: SUPABASE_SERVICE_ROLE_KEY not found")
        return

    with open(args.input, encoding="utf-8") as f:
        sites = json.load(f)
    print(f"Loaded {len(sites)} sites")

    # 确定要更新的字段
    if args.fields:
        fields = [f.strip() for f in args.fields.split(",")]
        invalid = [f for f in fields if f not in ALL_FIELDS]
        if invalid:
            print(f"Error: 未知字段 {invalid}，可用字段: {ALL_FIELDS}")
            return
    else:
        fields = ALL_FIELDS

    print(f"更新字段: {', '.join(fields)}")

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # 构造 upsert 行：release_id（匹配键）+ 要更新的字段
    rows = []
    for site in sites:
        rid = site.get("release_id")
        if not rid:
            continue
        row = {"release_id": rid}
        for field in fields:
            row[field] = site.get(field)
        rows.append(row)

    print(f"待更新: {len(rows)} 条\n")
    cnt, errs = upsert_batch(rows, url, headers, args.batch_size)
    print(f"\nDone: {cnt} updated, {errs} errors")


if __name__ == "__main__":
    main()
