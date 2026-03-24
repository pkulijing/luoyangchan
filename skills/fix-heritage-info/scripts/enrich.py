#!/usr/bin/env python3
"""
单条文保单位信息富化：获取百科内容 → DeepSeek 生成描述和标签 → 写入 JSON → 同步 Supabase。

用法:
  uv run python enrich.py 1-29                          # 自动获取百科 + DeepSeek 富化
  uv run python enrich.py 1-29 --context "额外参考信息"   # 附加用户提供的上下文
  uv run python enrich.py 1-29 --dry-run                 # 只展示结果，不写入
  uv run python enrich.py 1-29 1-164 3-32                # 批量处理
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import requests
from openai import OpenAI

_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"

WIKI_REST_API = "https://zh.wikipedia.org/api/rest_v1/page/summary"
WIKI_SEARCH_API = "https://zh.wikipedia.org/w/api.php"
BAIKE_BASE = "https://baike.baidu.com/item"
USER_AGENT = "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
DEEPSEEK_MODEL = "deepseek-chat"

BAIKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

SYSTEM_PROMPT = """你是中国文化遗产和历史地理专家。请根据以下信息，为这个全国重点文物保护单位生成描述和标签。

输出 JSON 对象，包含两个字段：
1. description（150-300字）：简要描述历史背景、文化意义和主要特征。准确、客观、信息密度高。
2. tags（10-20个关键词）：覆盖相关历史人物、历史事件、朝代、建筑风格、宗教文化、功能用途等维度。每个 tag 2-6个字。

只输出 JSON 对象，不要其他内容，不要 markdown 代码块。"""


def load_env_key(name: str) -> str | None:
    val = __import__("os").environ.get(name)
    if val:
        return val
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return None


def load_sites() -> list[dict]:
    with open(MAIN_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_sites(sites: list[dict]):
    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)


def find_site(sites: list[dict], release_id: str) -> dict | None:
    for s in sites:
        if s["release_id"] == release_id:
            return s
    return None


# --- Wikipedia ---

def fetch_wikipedia(name: str, existing_url: str | None = None) -> dict:
    """获取 Wikipedia 摘要。返回 {url, extract}。"""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.headers["Accept-Language"] = "zh-cn"

    result = {"url": existing_url, "extract": ""}

    # 尝试已有 URL
    if existing_url:
        path = urlparse(existing_url).path
        title = unquote(path.split("/wiki/", 1)[-1]) if "/wiki/" in path else ""
        if title:
            data = _wiki_summary(title, session)
            if data:
                result["extract"] = data
                return result

    # 直接用名称
    data = _wiki_summary(quote(name, safe=""), session)
    if data:
        result["url"] = f"https://zh.wikipedia.org/wiki/{quote(name, safe='')}"
        result["extract"] = data
        return result

    # 去括号
    bare = re.sub(r"[（(].+?[）)]", "", name).strip()
    if bare != name:
        data = _wiki_summary(quote(bare, safe=""), session)
        if data:
            result["url"] = f"https://zh.wikipedia.org/wiki/{quote(bare, safe='')}"
            result["extract"] = data
            return result

    # 搜索 API
    title = _wiki_search(name, session)
    if title:
        data = _wiki_summary(quote(title, safe=""), session)
        if data:
            result["url"] = f"https://zh.wikipedia.org/wiki/{quote(title, safe='')}"
            result["extract"] = data
            return result

    return result


def _wiki_summary(title: str, session: requests.Session) -> str:
    try:
        resp = session.get(f"{WIKI_REST_API}/{title}", timeout=15)
        if resp.status_code == 200:
            import zhconv
            return zhconv.convert(resp.json().get("extract", ""), "zh-cn")
    except Exception:
        pass
    return ""


def _wiki_search(name: str, session: requests.Session) -> str | None:
    from difflib import SequenceMatcher
    try:
        resp = session.get(WIKI_SEARCH_API, params={
            "action": "query", "list": "search", "srsearch": name,
            "srlimit": 5, "format": "json", "utf8": 1,
        }, timeout=15)
        if resp.status_code == 200:
            results = resp.json().get("query", {}).get("search", [])
            for r in results:
                if SequenceMatcher(None, name, r["title"]).ratio() >= 0.85:
                    return r["title"]
    except Exception:
        pass
    return None


# --- 百度百科 ---

def fetch_baike(name: str) -> dict:
    """直接构造 URL 获取百度百科内容。返回 {url, abstract}。"""
    result = {"url": None, "abstract": ""}

    url, abstract = _baike_direct(name)
    if url:
        result["url"] = url
        result["abstract"] = abstract
        return result

    # 去括号
    bare = re.sub(r"[（(].+?[）)]", "", name).strip()
    if bare != name:
        url, abstract = _baike_direct(bare)
        if url:
            result["url"] = url
            result["abstract"] = abstract
            return result

    return result


def _baike_direct(name: str) -> tuple[str | None, str]:
    from bs4 import BeautifulSoup
    try:
        url = f"{BAIKE_BASE}/{name}"
        resp = requests.get(url, headers=BAIKE_HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code == 200 and "/item/" in resp.url:
            soup = BeautifulSoup(resp.text, "html.parser")
            summary = soup.select_one(".lemma-summary, .J-summary, .lemmaSummary")
            if summary:
                text = re.sub(r"\[\d+\]", "", summary.get_text(strip=True))
                return resp.url, text
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                return resp.url, meta["content"].strip()
            return resp.url, ""
    except Exception:
        pass
    return None, ""


# --- DeepSeek ---

def enrich_with_deepseek(site: dict, wiki_extract: str, baike_abstract: str, extra_context: str) -> dict:
    """调用 DeepSeek 生成 description 和 tags。"""
    api_key = load_env_key("DEEPSEEK_API_KEY")
    base_url = load_env_key("DEEPSEEK_BASEURL") or "https://api.deepseek.com"
    if not api_key:
        print("  错误: DEEPSEEK_API_KEY 未配置")
        return {"description": "", "tags": []}

    client = OpenAI(api_key=api_key, base_url=base_url)

    input_data = {
        "name": site["name"],
        "category": site["category"],
        "era": site.get("era", ""),
        "province": site.get("province", ""),
        "city": site.get("city", ""),
        "address": site.get("address", ""),
        "batch": site.get("batch"),
        "batch_year": site.get("batch_year"),
    }

    refs = []
    if wiki_extract:
        refs.append(f"【Wikipedia摘要】{wiki_extract}")
    if baike_abstract:
        refs.append(f"【百度百科摘要】{baike_abstract}")
    if extra_context:
        refs.append(f"【用户提供信息】{extra_context}")
    if refs:
        input_data["reference"] = "\n".join(refs)

    user_content = json.dumps(input_data, ensure_ascii=False, indent=2)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"请为以下文保单位生成描述和标签：\n\n{user_content}"},
                ],
                temperature=0,
            )
            content = (response.choices[0].message.content or "").strip()
            # 去除 markdown 包裹
            if content.startswith("```"):
                lines = content.splitlines()
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                content = "\n".join(lines[1:end]).strip()
            result = json.loads(content)
            return {
                "description": result.get("description", ""),
                "tags": result.get("tags", []),
            }
        except (json.JSONDecodeError, Exception) as e:
            print(f"  [retry {attempt + 1}] {e}")
            time.sleep(1)

    return {"description": "", "tags": []}


# --- 同步到 Supabase ---

def sync_to_supabase(site: dict):
    """增量同步单条记录到 Supabase。"""
    from pathlib import Path
    import os

    env = {}
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("  Supabase 未配置，跳过同步")
        return

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # 查 UUID
    resp = requests.get(
        f"{url}/rest/v1/heritage_sites",
        params={"select": "id", "release_id": f"eq.{site['release_id']}"},
        headers=headers, timeout=10,
    )
    if resp.status_code != 200 or not resp.json():
        print("  Supabase 中未找到该记录")
        return

    uuid = resp.json()[0]["id"]
    updates = {
        "description": site.get("description"),
        "tags": site.get("tags"),
        "wikipedia_url": site.get("wikipedia_url"),
        "baike_url": site.get("baike_url"),
    }

    resp = requests.patch(
        f"{url}/rest/v1/heritage_sites?id=eq.{uuid}",
        json=updates,
        headers={**headers, "Prefer": "return=minimal"},
        timeout=10,
    )
    if resp.status_code in (200, 204):
        print("  已同步到 Supabase")
    else:
        print(f"  Supabase 同步失败: {resp.status_code}")


# --- 主流程 ---

def enrich_single(release_id: str, extra_context: str, dry_run: bool, sites: list[dict]):
    """富化单条记录。"""
    site = find_site(sites, release_id)
    if not site:
        print(f"[{release_id}] 未找到")
        return False

    print(f"\n{'='*60}")
    print(f"[{release_id}] {site['name']}")
    print(f"  类别: {site['category']} | 时代: {site.get('era', '未知')}")
    print(f"  地址: {site.get('province', '')} {site.get('city', '')} {site.get('address', '')}")

    # Step 1: 获取 Wikipedia
    print("\n  [1/4] 获取 Wikipedia...")
    wiki = fetch_wikipedia(site["name"], site.get("wikipedia_url"))
    if wiki["extract"]:
        print(f"    URL: {wiki['url']}")
        print(f"    摘要: {wiki['extract'][:80]}...")
    else:
        print(f"    未找到")

    # Step 2: 获取百度百科
    print("  [2/4] 获取百度百科...")
    baike = fetch_baike(site["name"])
    if baike["url"]:
        print(f"    URL: {baike['url']}")
        print(f"    摘要: {baike['abstract'][:80]}...")
    else:
        print(f"    未找到")

    # Step 3: DeepSeek 富化
    print("  [3/4] DeepSeek 生成描述和标签...")
    enrichment = enrich_with_deepseek(site, wiki["extract"], baike["abstract"], extra_context)
    print(f"    描述: {enrichment['description'][:80]}...")
    print(f"    标签: {enrichment['tags']}")

    if dry_run:
        print("\n  [dry-run] 不写入")
        return True

    # Step 4: 写入
    print("  [4/4] 写入数据...")
    if wiki["url"] and not site.get("wikipedia_url"):
        site["wikipedia_url"] = wiki["url"]
    if baike["url"]:
        site["baike_url"] = baike["url"]
    if enrichment["description"]:
        site["description"] = enrichment["description"]
    if enrichment["tags"]:
        site["tags"] = enrichment["tags"]

    save_sites(sites)
    print("    JSON 已更新")

    sync_to_supabase(site)
    return True


def main():
    parser = argparse.ArgumentParser(description="单条文保单位信息富化")
    parser.add_argument("release_ids", nargs="+", help="要富化的 release_id")
    parser.add_argument("--context", "-c", default="", help="用户提供的额外参考信息")
    parser.add_argument("--dry-run", action="store_true", help="只展示结果，不写入")
    args = parser.parse_args()

    sites = load_sites()

    success = 0
    for rid in args.release_ids:
        if enrich_single(rid, args.context, args.dry_run, sites):
            success += 1

    print(f"\n完成: {success}/{len(args.release_ids)}")


if __name__ == "__main__":
    main()
