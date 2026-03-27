"""
初始化 heritage_sites 表：清空后全量插入。

仅在空库或需要完全重建时使用。正常更新数据请用 update_heritage_sites.py。

用法:
  uv run python db/seed_heritage_sites.py
"""

import json
import os
from pathlib import Path

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
DEFAULT_INPUT = DATA_DIR / "heritage_sites_geocoded.json"


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


def clear_table(supabase_url: str, headers: dict):
    resp = requests.delete(
        f"{supabase_url}/rest/v1/heritage_sites?id=neq.00000000-0000-0000-0000-000000000000",
        headers={**headers, "Prefer": "return=minimal"},
        timeout=30,
    )
    if resp.status_code in (200, 204):
        print("表已清空")
    else:
        print(f"清空表失败: {resp.status_code} {resp.text[:200]}")
        raise RuntimeError("清空表失败")


def insert_batch(rows: list[dict], supabase_url: str, headers: dict, batch_size: int) -> tuple[int, int]:
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
        print(f"  {progress}/{len(rows)} ({inserted} inserted, {errors} errors)")
    return inserted, errors


def fetch_release_id_to_uuid(supabase_url: str, headers: dict, release_ids: list[str]) -> dict[str, str]:
    if not release_ids:
        return {}
    ids_param = "(" + ",".join(release_ids) + ")"
    resp = requests.get(
        f"{supabase_url}/rest/v1/heritage_sites",
        params={"select": "id,release_id", "release_id": f"in.{ids_param}"},
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        return {}
    return {row["release_id"]: row["id"] for row in resp.json()}


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
        "baike_image_url": site.get("baike_image_url"),
        "tags": site.get("tags"),
        "release_id": site.get("release_id"),
        "release_address": site.get("release_address"),
        "parent_id": parent_id,
    }


def main():
    url, key = get_config()
    if not key:
        print("Error: SUPABASE_SERVICE_ROLE_KEY not found")
        return

    with open(DEFAULT_INPUT, encoding="utf-8") as f:
        sites = json.load(f)
    print(f"Loaded {len(sites)} sites")

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # 确认
    print("⚠️  此操作会清空 heritage_sites 表后全量插入。")
    confirm = input("确认执行？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    clear_table(url, headers)

    # 阶段一：父记录和独立记录
    phase1 = [make_row(s) for s in sites if not s.get("_parent_release_id")]
    print(f"\n阶段一：插入 {len(phase1)} 条父/独立记录")
    cnt1, err1 = insert_batch(phase1, url, headers, 100)

    # 阶段二：子记录
    children = [s for s in sites if s.get("_parent_release_id")]
    cnt2, err2 = 0, 0
    if children:
        parent_ids = list({s["_parent_release_id"] for s in children})
        id_map = fetch_release_id_to_uuid(url, headers, parent_ids)
        print(f"\n阶段二：插入 {len(children)} 条子记录")
        phase2 = [make_row(s, parent_id=id_map.get(s["_parent_release_id"])) for s in children]
        cnt2, err2 = insert_batch(phase2, url, headers, 100)

    print(f"\nDone: {cnt1 + cnt2} inserted, {err1 + err2} errors")


if __name__ == "__main__":
    main()
