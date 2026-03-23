#!/usr/bin/env python3
"""
单条/多条记录同步到 Supabase

只更新指定的记录，不清空整个数据库。

用法:
  # 同步单条记录
  uv run python sync.py 7-703

  # 同步多条记录
  uv run python sync.py 7-703 7-817 6-478

  # 只查询不写入
  uv run python sync.py 7-703 --dry-run
"""

import argparse
import json
import os
from pathlib import Path

import requests

_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"


def load_env() -> dict[str, str]:
    """从 .env.local 读取环境变量。"""
    env: dict[str, str] = {}
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def get_supabase_config() -> tuple[str, str]:
    """获取 Supabase URL 和 service role key。"""
    dotenv = load_env()
    url = (os.environ.get("SUPABASE_URL")
           or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
           or dotenv.get("SUPABASE_URL")
           or dotenv.get("NEXT_PUBLIC_SUPABASE_URL"))
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or dotenv.get("SUPABASE_SERVICE_ROLE_KEY"))
    return url, key


def find_db_record(release_id: str, supabase_url: str, headers: dict) -> dict | None:
    """通过 release_id 查找数据库中的记录，返回其 UUID。"""
    resp = requests.get(
        f"{supabase_url}/rest/v1/heritage_sites",
        params={"select": "id,release_id", "release_id": f"eq.{release_id}"},
        headers=headers,
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data[0] if data else None


def update_record(uuid: str, updates: dict, supabase_url: str, headers: dict) -> bool:
    """更新单条记录。"""
    resp = requests.patch(
        f"{supabase_url}/rest/v1/heritage_sites?id=eq.{uuid}",
        json=updates,
        headers={**headers, "Prefer": "return=minimal"},
        timeout=10,
    )
    return resp.status_code in (200, 204)


def sync_records(release_ids: list[str], dry_run: bool = False):
    """同步指定的记录到 Supabase。"""
    supabase_url, service_key = get_supabase_config()
    if not supabase_url or not service_key:
        print("错误: 未配置 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
        return

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    # 加载 JSON 数据
    with open(MAIN_FILE, encoding="utf-8") as f:
        all_data = json.load(f)
    data_by_id = {r["release_id"]: r for r in all_data}

    success = 0
    failed = 0

    for rid in release_ids:
        if rid not in data_by_id:
            print(f"[{rid}] JSON 中未找到，跳过")
            failed += 1
            continue

        site = data_by_id[rid]
        print(f"[{rid}] {site['name']}")

        # 查找数据库中的记录
        db_record = find_db_record(rid, supabase_url, headers)
        if not db_record:
            print(f"  数据库中未找到，跳过（可能需要全量导入）")
            failed += 1
            continue

        uuid = db_record["id"]

        # 构建更新字段
        updates = {
            "name": site["name"],
            "province": site.get("province"),
            "city": site.get("city"),
            "district": site.get("district"),
            "address": site.get("address"),
            "latitude": site.get("latitude"),
            "longitude": site.get("longitude"),
            "category": site.get("category"),
            "era": site.get("era"),
            "batch": site.get("batch"),
            "batch_year": site.get("batch_year"),
            "description": site.get("description"),
            "wikipedia_url": site.get("wikipedia_url"),
            "image_url": site.get("image_url"),
            "release_address": site.get("release_address"),
        }

        if dry_run:
            print(f"  [dry-run] 将更新: lat={updates['latitude']}, lng={updates['longitude']}")
            print(f"            address={updates['address']}")
            success += 1
            continue

        if update_record(uuid, updates, supabase_url, headers):
            print(f"  已更新: ({updates['latitude']}, {updates['longitude']})")
            success += 1
        else:
            print(f"  更新失败")
            failed += 1

    print(f"\n完成: {success} 成功, {failed} 失败")


def main():
    parser = argparse.ArgumentParser(description="单条/多条记录同步到 Supabase")
    parser.add_argument("release_ids", nargs="+", help="要同步的 release_id")
    parser.add_argument("--dry-run", action="store_true", help="只查询不写入")
    args = parser.parse_args()

    sync_records(args.release_ids, args.dry_run)


if __name__ == "__main__":
    main()
