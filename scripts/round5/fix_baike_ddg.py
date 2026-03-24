"""
直接构造百度百科 URL + 爬取页面，补全未命中的记录。

策略：直接访问 https://baike.baidu.com/item/{名称}，如果 404 则去括号重试，
最后 DuckDuckGo 搜索兜底。绕开百度 API 的每日 1000 次限制。

用法:
  uv run python round5/fix_baike_ddg.py --dry-run    # 只处理前 10 条
  uv run python round5/fix_baike_ddg.py              # 全量处理
  uv run python round5/fix_baike_ddg.py --resume     # 断点续跑
"""

import argparse
import json
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

SIMILARITY_THRESHOLD = 0.4

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
ROUND5_DIR = DATA_DIR / "round5"
BAIKE_FILE = ROUND5_DIR / "baike_data.json"
CHECKPOINT_FILE = ROUND5_DIR / "baike_ddg_checkpoint.json"

CHECKPOINT_INTERVAL = 50
SEARCH_INTERVAL = 1.0  # DuckDuckGo 间隔
FETCH_INTERVAL = 0.5   # 爬取百科页面间隔

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def try_direct_url(name: str) -> tuple[str | None, str]:
    """直接构造百度百科 URL 访问，返回 (final_url, abstract)。"""
    url = f"https://baike.baidu.com/item/{name}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code == 200 and "/item/" in resp.url:
            abstract = scrape_abstract_from_html(resp.text)
            return resp.url, abstract
    except Exception:
        pass
    return None, ""


def search_baike_ddg(name: str) -> str | None:
    """DuckDuckGo 搜索兜底，带标题相似度校验。"""
    try:
        results = DDGS().text(f"{name} 百度百科 site:baike.baidu.com", region="cn-zh", max_results=5)
        if not results:
            return None

        bare_name = re.sub(r"[（(].+?[）)]", "", name).strip()

        for r in results:
            url = r.get("href", "")
            if "baike.baidu.com/item/" not in url:
                continue
            path = urlparse(url).path
            if "/item/" in path:
                baike_title = unquote(path.split("/item/")[1].split("/")[0])
                score = max(
                    SequenceMatcher(None, name, baike_title).ratio(),
                    SequenceMatcher(None, bare_name, baike_title).ratio(),
                )
                if score >= SIMILARITY_THRESHOLD:
                    return url
    except Exception:
        pass
    return None


def find_baike(name: str) -> tuple[str | None, str]:
    """三级策略查找百度百科：直接 URL → 去括号 URL → DuckDuckGo 搜索。"""
    # 策略 1: 直接构造 URL
    url, abstract = try_direct_url(name)
    if url:
        return url, abstract

    # 策略 2: 去括号后重试
    bare_name = re.sub(r"[（(].+?[）)]", "", name).strip()
    if bare_name != name:
        url, abstract = try_direct_url(bare_name)
        if url:
            return url, abstract

    # 策略 3: DuckDuckGo 搜索兜底
    ddg_url = search_baike_ddg(name)
    if ddg_url:
        abstract = scrape_baike_abstract(ddg_url)
        return ddg_url, abstract

    return None, ""


def scrape_abstract_from_html(html: str) -> str:
    """从百度百科页面 HTML 中提取摘要文本。"""
    soup = BeautifulSoup(html, "html.parser")

    # 百度百科摘要在 .lemma-summary 或 .J-summary 中
    summary_div = soup.select_one(".lemma-summary, .J-summary, .lemmaSummary")
    if summary_div:
        text = summary_div.get_text(strip=True)
        text = re.sub(r"\[\d+\]", "", text)
        return text.strip()

    # 备用：找 meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()

    return ""


def scrape_baike_abstract(url: str) -> str:
    """爬取百度百科页面，提取摘要文本。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return ""
        return scrape_abstract_from_html(resp.text)
    except Exception as e:
        print(f"  [scrape-error] {url}: {e}", file=sys.stderr)
        return ""


def main():
    parser = argparse.ArgumentParser(description="Fix Baidu Baike via DuckDuckGo search + page scraping")
    parser.add_argument("--dry-run", action="store_true", help="只处理前 10 条")
    parser.add_argument("--resume", action="store_true", help="断点续跑")
    args = parser.parse_args()

    with open(BAIKE_FILE, encoding="utf-8") as f:
        all_data = json.load(f)
    data_map = {d["release_id"]: d for d in all_data}

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)
    name_map = {s["release_id"]: s["name"] for s in sites}

    # 找出未命中的条目
    failed_ids = [d["release_id"] for d in all_data if not d.get("baike_hit")]
    print(f"总记录: {len(all_data)}, 未命中: {len(failed_ids)}")

    # 加载 checkpoint
    done_ids: set[str] = set()
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            checkpoint = json.load(f)
            for item in checkpoint:
                done_ids.add(item["release_id"])
                data_map[item["release_id"]].update(item)
        print(f"从 checkpoint 恢复: {len(done_ids)} 条已处理")

    pending = [rid for rid in failed_ids if rid not in done_ids]
    if args.dry_run:
        pending = pending[:10]
        print(f"[dry-run] 只处理前 {len(pending)} 条")

    print(f"待处理: {len(pending)} 条\n")

    recovered = 0
    recovered_with_abstract = 0
    checkpoint_data = []

    for i, rid in enumerate(pending):
        name = name_map.get(rid, rid)

        baike_url, abstract = find_baike(name)
        time.sleep(FETCH_INTERVAL)

        if baike_url:

            data_map[rid]["baike_url"] = baike_url
            data_map[rid]["baike_hit"] = True
            if abstract:
                data_map[rid]["baike_abstract"] = abstract
                recovered_with_abstract += 1
            recovered += 1
            print(f"  [recovered] {rid}: {name} -> {baike_url[:60]}... ({len(abstract)} chars)")
        else:
            print(f"  [miss] {rid}: {name}")

        checkpoint_data.append({
            "release_id": rid,
            "baike_url": data_map[rid].get("baike_url"),
            "baike_hit": data_map[rid].get("baike_hit", False),
            "baike_abstract": data_map[rid].get("baike_abstract", ""),
            "baike_card": data_map[rid].get("baike_card", {}),
        })

        if (i + 1) % 50 == 0 or i == len(pending) - 1:
            print(f"  进度: {i+1}/{len(pending)} (恢复 {recovered}, 含摘要 {recovered_with_abstract})")

        if not args.dry_run and (i + 1) % CHECKPOINT_INTERVAL == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            print(f"  [checkpoint] 已保存")

    # 写回
    if not args.dry_run:
        result_list = list(data_map.values())
        with open(BAIKE_FILE, "w", encoding="utf-8") as f:
            json.dump(result_list, f, ensure_ascii=False, indent=2)
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()

        total_hit = sum(1 for d in result_list if d.get("baike_hit"))
        print(f"\n完成！恢复 {recovered} 条 (含摘要 {recovered_with_abstract})")
        print(f"最终命中率: {total_hit}/{len(result_list)} ({total_hit*100//len(result_list)}%)")
    else:
        print(f"\n[dry-run] 恢复 {recovered} 条 (含摘要 {recovered_with_abstract})")


if __name__ == "__main__":
    main()
