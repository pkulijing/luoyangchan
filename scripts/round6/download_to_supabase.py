"""
将 Wikimedia Commons 图片下载并上传到本地 Supabase Storage。

合并三个数据源（Wikipedia pageimages、Wikidata P18、Commons 搜索），
下载 600px 宽缩略图，上传到 Supabase Storage 的 site-images bucket，
最后更新主数据文件的 image_url 为 Supabase Storage 路径。

前置条件:
  - 本地 Supabase 已启动（supabase start）
  - site-images bucket 已在 config.toml 中声明
  - 能访问 upload.wikimedia.org（需要 VPN）

用法:
  uv run python round6/download_to_supabase.py                # 全量
  uv run python round6/download_to_supabase.py --dry-run      # 前 10 条
  uv run python round6/download_to_supabase.py --resume       # 续跑
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round6"
WIKI_IMAGES = OUTPUT_DIR / "wikipedia_images.json"
WIKIDATA_IMAGES = OUTPUT_DIR / "wikidata_images.json"
COMMONS_IMAGES = OUTPUT_DIR / "commons_images.json"
PROGRESS_FILE = OUTPUT_DIR / "upload_progress.json"

# Supabase Storage config
SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "http://127.0.0.1:54321")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BUCKET = "site-images"
THUMB_WIDTH = 600

# Wikimedia 新基础设施限额 15 req/s（未认证），2s 间隔留安全余量
REQUEST_INTERVAL = 2.0
MAX_RETRIES = 3


def image_url_to_thumb(url: str, width: int = THUMB_WIDTH) -> str:
    """将 Commons 原图 URL 转换为缩略图 URL。

    原图: https://upload.wikimedia.org/wikipedia/commons/a/ab/File.jpg
    缩略图: https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/File.jpg/600px-File.jpg
    """
    if "/commons/thumb/" in url:
        return url  # 已经是缩略图
    # 插入 thumb/ 并追加 /600px-filename
    parts = url.replace("/commons/", "/commons/thumb/", 1)
    filename = url.rsplit("/", 1)[-1]
    return f"{parts}/{width}px-{filename}"


def download_image(url: str, session: requests.Session) -> bytes | None:
    """下载图片，带重试和 429 退避。"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                return resp.content
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 30 * (attempt + 1)))
                print(f"  [429] 被限流，等待 {wait}s 后重试...", file=sys.stderr)
                time.sleep(wait)
                continue
            # 缩略图失败，回退到原图
            if "/thumb/" in url:
                original = url.replace("/commons/thumb/", "/commons/")
                original = original.rsplit("/", 1)[0]
                resp2 = session.get(original, timeout=30)
                if resp2.status_code == 200 and resp2.headers.get("content-type", "").startswith("image/"):
                    return resp2.content
                if resp2.status_code == 429:
                    wait = int(resp2.headers.get("Retry-After", 30 * (attempt + 1)))
                    time.sleep(wait)
                    continue
            return None
        except requests.RequestException as e:
            print(f"  [download error] {e}", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                time.sleep(3)
    return None


def upload_to_supabase(
    data: bytes, path: str, content_type: str, key: str, session: requests.Session
) -> bool:
    """上传文件到 Supabase Storage。"""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    try:
        resp = session.put(
            url,
            data=data,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            timeout=30,
        )
        return resp.status_code in (200, 201)
    except requests.RequestException as e:
        print(f"  [upload error] {path}: {e}", file=sys.stderr)
        return False


def guess_content_type(url: str) -> str:
    """根据 URL 猜测 content-type。"""
    lower = url.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def main():
    parser = argparse.ArgumentParser(description="Download Commons images to Supabase Storage")
    parser.add_argument("--dry-run", action="store_true", help="只处理前 10 条")
    parser.add_argument("--resume", action="store_true", help="跳过已上传的")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        # 尝试从 .env.local 读取
        env_file = _ROOT / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = line.split("=", 1)[1]
                    break
    supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supa_key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not found", file=sys.stderr)
        sys.exit(1)

    # 合并三个数据源
    merged: dict[str, str] = {}  # release_id → commons_url
    for path in [WIKI_IMAGES, WIKIDATA_IMAGES, COMMONS_IMAGES]:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for item in json.load(f):
                url = item.get("image_url")
                if url and item["release_id"] not in merged:
                    merged[item["release_id"]] = url

    print(f"合并后共 {len(merged)} 条有图片的记录")

    # 加载已上传进度
    uploaded: set[str] = set()
    if args.resume and PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            uploaded = set(json.load(f))
        print(f"已上传: {len(uploaded)} 条")

    # 筛选待处理
    pending = [(rid, url) for rid, url in merged.items() if rid not in uploaded]
    if args.dry_run:
        pending = pending[:10]
        print(f"[dry-run] 只处理前 {len(pending)} 条")
    print(f"待下载上传: {len(pending)} 条\n")

    session = requests.Session()
    session.headers["User-Agent"] = (
        "LuoyangchanBot/1.0 (https://github.com/luoyangchan; heritage sites map; educational)"
    )

    success = 0
    fail = 0
    uploaded_list = list(uploaded)

    for i, (rid, url) in enumerate(pending):
        # 下载缩略图
        thumb_url = image_url_to_thumb(url)
        data = download_image(thumb_url, session)

        if not data:
            fail += 1
            if (i + 1) % 50 == 0:
                print(f"  进度: {i+1}/{len(pending)} (成功 {success}, 失败 {fail})")
            time.sleep(REQUEST_INTERVAL)
            continue

        # 确定存储路径: site-images/{release_id}.jpg
        ext = "jpg"
        ct = guess_content_type(url)
        if "png" in ct:
            ext = "png"
        elif "gif" in ct:
            ext = "gif"
        elif "webp" in ct:
            ext = "webp"
        storage_path = f"{rid}.{ext}"

        # 上传
        ok = upload_to_supabase(data, storage_path, ct, supa_key, session)
        if ok:
            success += 1
            uploaded_list.append(rid)
        else:
            fail += 1

        if (i + 1) % 50 == 0 or i == len(pending) - 1:
            print(f"  进度: {i+1}/{len(pending)} (成功 {success}, 失败 {fail})")

        # 定期保存进度
        if not args.dry_run and (i + 1) % 100 == 0:
            with open(PROGRESS_FILE, "w") as f:
                json.dump(uploaded_list, f)

        time.sleep(REQUEST_INTERVAL)

    # 保存最终进度
    if not args.dry_run:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(uploaded_list, f)

    print(f"\n下载上传完成: 成功 {success}, 失败 {fail}")

    if not args.dry_run and success > 0:
        # 更新主数据文件
        print("\n更新主数据文件 image_url...")
        with open(MAIN_FILE, encoding="utf-8") as f:
            sites = json.load(f)

        storage_base = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}"
        updated = 0
        cleared = 0
        for site in sites:
            rid = site.get("release_id")
            if rid and rid in set(uploaded_list):
                # 确定文件扩展名
                original_url = merged.get(rid, "")
                ext = "jpg"
                ct = guess_content_type(original_url)
                if "png" in ct:
                    ext = "png"
                elif "gif" in ct:
                    ext = "gif"
                site["image_url"] = f"{storage_base}/{rid}.{ext}"
                updated += 1
            elif site.get("image_url"):
                site["image_url"] = None
                cleared += 1

        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, ensure_ascii=False, indent=2)

        print(f"已更新 {updated} 条 image_url，清除 {cleared} 条")
        print(f"最终覆盖率: {updated}/{len(sites)} ({updated * 100 // len(sites)}%)")


if __name__ == "__main__":
    main()
