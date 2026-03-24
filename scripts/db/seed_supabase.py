"""
将爬取的文保单位数据导入 Supabase 数据库。

用法:
  uv run python seed_supabase.py --url YOUR_SUPABASE_URL --key YOUR_SERVICE_ROLE_KEY [--clear]

注意: 使用 service_role key (非 anon key) 以绕过 RLS。
"""

import json
import os
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "heritage_sites_geocoded.json"


def load_env() -> dict[str, str]:
    """从 .env.local 读取环境变量（不覆盖已有的系统环境变量）。"""
    env: dict[str, str] = {}
    env_file = Path(__file__).parent.parent.parent / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def clear_table(supabase_url: str, service_key: str):
    """清空 heritage_sites 表中的所有记录。"""
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    resp = requests.delete(
        f"{supabase_url}/rest/v1/heritage_sites?id=neq.00000000-0000-0000-0000-000000000000",
        headers=headers,
        timeout=30,
    )
    if resp.status_code in (200, 204):
        print("表已清空")
    else:
        print(f"清空表失败: {resp.status_code} {resp.text[:200]}")
        raise RuntimeError("清空表失败，终止导入")


def insert_batch(rows: list[dict], supabase_url: str, headers: dict, batch_size: int) -> tuple[int, int]:
    """分批 POST 插入，返回 (inserted, errors)。"""
    inserted = 0
    errors = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        resp = requests.post(
            f"{supabase_url}/rest/v1/heritage_sites",
            json=batch,
            headers={**headers, "Prefer": "return=representation"},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            inserted += len(batch)
        else:
            print(f"  Error at batch {i}: {resp.status_code} {resp.text[:200]}")
            errors += 1
        progress = min(i + batch_size, len(rows))
        print(f"  Progress: {progress}/{len(rows)} ({inserted} inserted, {errors} errors)")
    return inserted, errors


def fetch_release_id_to_uuid(supabase_url: str, headers: dict, release_ids: list[str]) -> dict[str, str]:
    """批量查询 release_id → UUID 映射（用于建立父子关联）。"""
    if not release_ids:
        return {}
    # PostgREST in 过滤：release_id=in.(id1,id2,...)
    ids_param = "(" + ",".join(release_ids) + ")"
    resp = requests.get(
        f"{supabase_url}/rest/v1/heritage_sites",
        params={"select": "id,release_id", "release_id": f"in.{ids_param}"},
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"  查询父记录 UUID 失败: {resp.status_code} {resp.text[:200]}")
        return {}
    return {row["release_id"]: row["id"] for row in resp.json()}


def seed(supabase_url: str, service_key: str, input_file: str, batch_size: int = 100, do_clear: bool = False):
    """两阶段批量插入：先插父/独立记录，再插子记录（填入 parent_id）。"""
    with open(input_file, encoding="utf-8") as f:
        sites = json.load(f)

    print(f"Loaded {len(sites)} sites from {input_file}")

    if do_clear:
        print("清空现有数据...")
        clear_table(supabase_url, service_key)

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    def make_row(site: dict, parent_id: str | None = None) -> dict:
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
            "tags": site.get("tags"),
            "release_id": site.get("release_id"),
            "release_address": site.get("release_address"),
            "parent_id": parent_id,
        }

    # 阶段一：插入父记录和独立记录（无 parent_id 依赖）
    phase1_rows = [make_row(s) for s in sites if not s.get("_parent_release_id")]
    print(f"\n阶段一：插入 {len(phase1_rows)} 条父/独立记录")
    ins1, err1 = insert_batch(phase1_rows, supabase_url, headers, batch_size)

    # 阶段二：查出父记录的 UUID，插入子记录
    child_sites = [s for s in sites if s.get("_parent_release_id")]
    if child_sites:
        parent_release_ids = list({s["_parent_release_id"] for s in child_sites})
        release_id_map = fetch_release_id_to_uuid(supabase_url, headers, parent_release_ids)
        print(f"\n阶段二：插入 {len(child_sites)} 条子记录")
        phase2_rows = [
            make_row(s, parent_id=release_id_map.get(s["_parent_release_id"]))
            for s in child_sites
        ]
        ins2, err2 = insert_batch(phase2_rows, supabase_url, headers, batch_size)
    else:
        ins2, err2 = 0, 0

    print(f"\nDone: {ins1 + ins2} inserted, {err1 + err2} batch errors")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed heritage sites into Supabase")
    dotenv = load_env()
    parser.add_argument(
        "--url",
        default=os.environ.get("SUPABASE_URL")
            or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
            or dotenv.get("SUPABASE_URL")
            or dotenv.get("NEXT_PUBLIC_SUPABASE_URL"),
        help="Supabase project URL",
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or dotenv.get("SUPABASE_SERVICE_ROLE_KEY"),
        help="Supabase service role key",
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--clear",
        action="store_true",
        help="导入前清空 heritage_sites 表中所有现有数据",
    )
    args = parser.parse_args()

    if not args.url or not args.key:
        print("Error: Supabase URL and service role key are required.")
        print("  Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars, or use --url and --key flags.")
        return

    seed(args.url, args.key, args.input, args.batch_size, do_clear=args.clear)


if __name__ == "__main__":
    main()
