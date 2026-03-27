"""
通过百度百科 BaikeLemmaCardApi 批量采集文保单位主图 URL。

图片在 bkimg.cdn.bcebos.com（百度云 CDN），国内可直接访问。
前端展示时需要 referrerPolicy="no-referrer" 绕过防盗链。

采用多策略提升命中率：
  1. 用 baike_url 中的词条名查询
  2. 用站点原名查询（可能与百科词条名不同）
  3. 去掉常见后缀（遗址/旧址/故居/会址）重试

用法:
  uv run python round6/fetch_baike_images.py                # 全量采集
  uv run python round6/fetch_baike_images.py --dry-run      # 只处理前 50 条
  uv run python round6/fetch_baike_images.py --resume       # 从 checkpoint 续跑
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round6"
OUTPUT_FILE = OUTPUT_DIR / "baike_images.json"
CHECKPOINT_FILE = OUTPUT_DIR / "baike_images_checkpoint.json"

BAIKE_API = "https://baike.baidu.com/api/openapi/BaikeLemmaCardApi"
USER_AGENT = "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
CHECKPOINT_INTERVAL = 200
REQUEST_INTERVAL = 0.3

# 可尝试去掉的后缀
SUFFIXES = ["遗址", "旧址", "故居", "会址", "地址", "墓地", "墓园", "故城"]


def extract_name_from_baike_url(url: str) -> str:
    """从百度百科 URL 中提取词条名称。"""
    path = urlparse(url).path
    parts = path.split("/item/", 1)
    if len(parts) < 2:
        return ""
    name_part = parts[1].split("/")[0]
    return unquote(name_part)


def query_api(name: str, session: requests.Session) -> str | None:
    """单次 API 查询，返回图片 URL 或 None。"""
    params = {
        "appid": "379020",
        "bk_key": name,
        "bk_length": "50",
    }
    try:
        resp = session.get(BAIKE_API, params=params, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        image_url = data.get("image")
        if image_url and "bkimg.cdn.bcebos.com" in image_url:
            return image_url
        return None
    except (requests.RequestException, ValueError):
        return None


def fetch_baike_image(
    baike_name: str, site_name: str, session: requests.Session
) -> str | None:
    """多策略尝试获取图片 URL。"""
    # 收集候选查询名称（去重保序）
    candidates: list[str] = []
    for name in [baike_name, site_name]:
        if name and name not in candidates:
            candidates.append(name)
        # 去后缀变体
        for suffix in SUFFIXES:
            if name and name.endswith(suffix) and len(name) > len(suffix) + 2:
                short = name[: -len(suffix)]
                if short not in candidates:
                    candidates.append(short)

    for name in candidates:
        image_url = query_api(name, session)
        if image_url:
            return image_url
        time.sleep(REQUEST_INTERVAL)

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Baidu Baike images for heritage sites"
    )
    parser.add_argument("--dry-run", action="store_true", help="只处理前 50 条")
    parser.add_argument("--resume", action="store_true", help="从 checkpoint 续跑")
    parser.add_argument("--retry-missing", action="store_true",
                        help="只重试已有结果中无图的记录（用于多轮累积）")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    targets = []
    for s in sites:
        baike_url = s.get("baike_url")
        if baike_url:
            targets.append({
                "release_id": s["release_id"],
                "name": s["name"],
                "baike_name": extract_name_from_baike_url(baike_url) or s["name"],
            })
    print(f"共 {len(targets)} 条有 baike_url 的记录")

    # 加载已完成的结果
    done: dict[str, dict] = {}

    # --retry-missing: 从已有输出中加载，只重试无图的
    if args.retry_missing and OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done[item["release_id"]] = item
        has_img = sum(1 for v in done.values() if v.get("image_url"))
        no_img = len(done) - has_img
        print(f"从已有结果加载: {len(done)} 条 (有图 {has_img}, 无图 {no_img})")
        # 把无图的从 done 中移除，让它们重新进入 pending
        done = {k: v for k, v in done.items() if v.get("image_url")}
        print(f"保留有图 {len(done)} 条，{no_img} 条将重试")

    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done[item["release_id"]] = item
        print(f"从 checkpoint 恢复: {len(done)} 条已完成")

    pending = [t for t in targets if t["release_id"] not in done]
    if args.dry_run:
        pending = pending[:50]
        print(f"[dry-run] 只处理前 {len(pending)} 条")

    print(f"待处理: {len(pending)} 条\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    results = list(done.values())
    success = 0
    fail = 0

    for i, item in enumerate(pending):
        release_id = item["release_id"]
        image_url = fetch_baike_image(item["baike_name"], item["name"], session)

        results.append({
            "release_id": release_id,
            "image_url": image_url,
        })

        if image_url:
            success += 1
        else:
            fail += 1

        # 进度
        total_done = len(done) + i + 1
        total = len(done) + len(pending)
        if (i + 1) % 100 == 0 or i == len(pending) - 1:
            print(
                f"  进度: {total_done}/{total} "
                f"(有图 {success}, 无图 {fail}, "
                f"命中率 {success * 100 // max(success + fail, 1)}%)"
            )

        # Checkpoint
        if not args.dry_run and (i + 1) % CHECKPOINT_INTERVAL == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  [checkpoint] 已保存 {len(results)} 条")

    # 最终输出
    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
        print(f"\n完成！{len(results)} 条结果已保存到 {OUTPUT_FILE}")
    else:
        print(f"\n[dry-run] 完成。有图 {success}, 无图 {fail}")
        samples = [r for r in results if r.get("image_url")][:3]
        for s in samples:
            print(json.dumps(s, ensure_ascii=False, indent=2))

    hit_rate = success * 100 // max(success + fail, 1)
    print(f"\n最终命中率: {success}/{success + fail} ({hit_rate}%)")


if __name__ == "__main__":
    main()
