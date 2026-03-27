"""
将 Wikimedia Commons 图片下载到本地备份，并上传到 Supabase Storage。

合并三个数据源（Wikipedia pageimages、Wikidata P18、Commons 搜索），
下载 600px 宽缩略图。图片同时保存到 data/site-images/ 本地备份
和 Supabase Storage 的 site-images bucket。

前置条件:
  - 本地 Supabase 已启动（supabase start）
  - site-images bucket 已在 config.toml 中声明

用法:
  uv run python round6/download_to_supabase.py                # 从 Wikimedia 下载（需 VPN）
  uv run python round6/download_to_supabase.py --dry-run      # 前 10 条
  uv run python round6/download_to_supabase.py --resume       # 续跑
  uv run python round6/download_to_supabase.py --from-local   # 从本地备份上传到 Supabase（无需 VPN）
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round6"
LOCAL_IMAGES_DIR = DATA_DIR / "site-images"
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
    """将 Commons 原图 URL 转换为缩略图 URL。"""
    if "/commons/thumb/" in url:
        return url
    parts = url.replace("/commons/", "/commons/thumb/", 1)
    filename = url.rsplit("/", 1)[-1]
    return f"{parts}/{width}px-{filename}"


MAX_IMAGE_SIZE = 1024 * 1024  # 1MB


def download_image(url: str, session: requests.Session) -> bytes | None:
    """下载缩略图，带重试和 429 退避。不回退到原图（原图可达上百 MB）。"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                if len(resp.content) > MAX_IMAGE_SIZE:
                    print(f"  [skip] 文件过大 ({len(resp.content) // 1024}KB)，可能不是缩略图", file=sys.stderr)
                    return None
                return resp.content
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 30 * (attempt + 1)))
                print(f"  [429] 被限流，等待 {wait}s 后重试...", file=sys.stderr)
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


def guess_content_type(filename: str) -> str:
    """根据文件名猜测 content-type。"""
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def get_ext(url: str) -> str:
    """从 URL 猜测扩展名。"""
    ct = guess_content_type(url)
    if "png" in ct:
        return "png"
    if "gif" in ct:
        return "gif"
    if "webp" in ct:
        return "webp"
    return "jpg"


def detect_ext(data: bytes, fallback_url: str) -> str:
    """根据文件内容魔数检测实际格式，URL 仅作 fallback。"""
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:3] == b"GIF":
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:5] == b"<?xml" or data[:4] == b"<svg":
        return "svg"
    if data[:2] in (b"\xff\xd8",):
        return "jpg"
    return get_ext(fallback_url)


def load_supabase_key() -> str:
    """获取 Supabase service role key。"""
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        env_file = _ROOT / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                    key = line.split("=", 1)[1]
                    break
    return key


def upload_from_local(supa_key: str):
    """从 data/site-images/ 本地备份上传到 Supabase Storage。"""
    if not LOCAL_IMAGES_DIR.exists():
        print(f"本地备份目录不存在: {LOCAL_IMAGES_DIR}")
        sys.exit(1)

    files = sorted(LOCAL_IMAGES_DIR.iterdir())
    image_files = [f for f in files if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp")]
    print(f"本地备份: {len(image_files)} 张图片")

    session = requests.Session()
    success = 0
    fail = 0

    for i, path in enumerate(image_files):
        data = path.read_bytes()
        ct = guess_content_type(path.name)
        ok = upload_to_supabase(data, path.name, ct, supa_key, session)
        if ok:
            success += 1
        else:
            fail += 1

        if (i + 1) % 100 == 0 or i == len(image_files) - 1:
            print(f"  进度: {i+1}/{len(image_files)} (成功 {success}, 失败 {fail})")

    print(f"\n上传完成: 成功 {success}, 失败 {fail}")


def download_and_upload(args, supa_key: str):
    """从 Wikimedia 下载图片，保存本地备份，并上传到 Supabase。"""
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

    # 确保本地备份目录存在
    LOCAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # 加载已上传进度
    uploaded: set[str] = set()
    if args.resume and PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            uploaded = set(json.load(f))
        print(f"已处理: {len(uploaded)} 条")

    # 筛选待处理
    pending = [(rid, url) for rid, url in merged.items() if rid not in uploaded]
    if args.dry_run:
        pending = pending[:10]
        print(f"[dry-run] 只处理前 {len(pending)} 条")
    print(f"待下载: {len(pending)} 条\n")

    session = requests.Session()
    session.headers["User-Agent"] = (
        "LuoyangchanBot/1.0 (https://github.com/luoyangchan; heritage sites map; educational)"
    )

    success = 0
    fail = 0
    uploaded_list = list(uploaded)

    for i, (rid, url) in enumerate(pending):
        # 检查本地是否已有（任意扩展名）
        local_path = None
        for candidate_ext in ("jpg", "png", "gif", "webp", "svg"):
            p = LOCAL_IMAGES_DIR / f"{rid}.{candidate_ext}"
            if p.exists():
                local_path = p
                break

        if local_path:
            data = local_path.read_bytes()
            ext = local_path.suffix.lstrip(".")
        else:
            thumb_url = image_url_to_thumb(url)
            data = download_image(thumb_url, session)
            if not data:
                fail += 1
                if (i + 1) % 50 == 0:
                    print(f"  进度: {i+1}/{len(pending)} (成功 {success}, 失败 {fail})")
                time.sleep(REQUEST_INTERVAL)
                continue
            # 根据实际内容检测格式
            ext = detect_ext(data, url)
            # 跳过 SVG（浏览器兼容性差，且通常是示意图不是照片）
            if ext == "svg":
                fail += 1
                time.sleep(REQUEST_INTERVAL)
                continue
            # 保存本地备份
            local_path = LOCAL_IMAGES_DIR / f"{rid}.{ext}"
            local_path.write_bytes(data)

        # 上传到 Supabase
        ct = guess_content_type(f".{ext}")
        storage_path = f"{rid}.{ext}"
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

        # 只在实际下载时限速
        if not local_path.exists():
            time.sleep(REQUEST_INTERVAL)

    # 保存最终进度
    if not args.dry_run:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(uploaded_list, f)

    print(f"\n完成: 成功 {success}, 失败 {fail}")

    if not args.dry_run and success > 0:
        # 更新主数据文件 image_url（存为相对路径）
        print("\n更新主数据文件 image_url...")
        with open(MAIN_FILE, encoding="utf-8") as f:
            sites = json.load(f)

        uploaded_set = set(uploaded_list)
        updated = 0
        for site in sites:
            rid = site.get("release_id")
            if rid and rid in uploaded_set:
                ext = get_ext(merged.get(rid, ""))
                site["image_url"] = f"site-images/{rid}.{ext}"
                updated += 1

        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, ensure_ascii=False, indent=2)

        print(f"已更新 {updated} 条 image_url（相对路径）")


def main():
    parser = argparse.ArgumentParser(description="Download Commons images to Supabase Storage")
    parser.add_argument("--dry-run", action="store_true", help="只处理前 10 条")
    parser.add_argument("--resume", action="store_true", help="跳过已处理的")
    parser.add_argument("--from-local", action="store_true",
                        help="从 data/site-images/ 本地备份上传到 Supabase（无需 VPN）")
    args = parser.parse_args()

    supa_key = load_supabase_key()
    if not supa_key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not found", file=sys.stderr)
        sys.exit(1)

    if args.from_local:
        upload_from_local(supa_key)
    else:
        download_and_upload(args, supa_key)


if __name__ == "__main__":
    main()
