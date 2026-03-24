"""
Phase 2: 从百度百科采集文保单位 URL 和摘要内容。

用法:
  uv run python round5/fetch_baike.py                # 全量采集
  uv run python round5/fetch_baike.py --dry-run      # 只处理前 10 条
  uv run python round5/fetch_baike.py --resume       # 从 checkpoint 续跑
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round5"
OUTPUT_FILE = OUTPUT_DIR / "baike_data.json"
CHECKPOINT_FILE = OUTPUT_DIR / "baike_checkpoint.json"

CHECKPOINT_INTERVAL = 50
REQUEST_INTERVAL = 0.5  # 0.5s/req

# 百度百科信息框中与文保单位相关的 key
USEFUL_CARD_KEYS = {
    "地理位置", "位置", "所在地", "地点", "所在地点", "地址", "所处位置",
    "建造年代", "始建时间", "建筑年代", "创建时间", "建成时间",
    "保护级别", "文物级别",
    "所属年代", "所处时代", "时代",
    "占地面积", "建筑面积",
    "开放时间",
    "类别", "类型",
}


def load_env_key(name: str) -> str | None:
    val = os.environ.get(name)
    if val:
        return val
    env_file = _ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return None


def extract_card(card_list: list[dict]) -> dict[str, str]:
    """从百度百科 card 数组中提取有用的键值对。"""
    result = {}
    for item in card_list:
        key = item.get("name", "")
        if isinstance(key, list):
            key = "".join(str(k) for k in key)
        key = key.strip()

        value = item.get("value", "")
        if isinstance(value, list):
            # value 可能是 [{"text": "xxx"}, ...] 或 ["xxx", ...]
            parts = []
            for v in value:
                if isinstance(v, dict):
                    parts.append(v.get("text", str(v)))
                else:
                    parts.append(str(v))
            value = "".join(parts)
        value = value.strip()

        if key in USEFUL_CARD_KEYS and value:
            result[key] = value
    return result


def _parse_baike_content(content: dict) -> dict:
    """从百度百科 API 响应中提取结构化结果。"""
    card = extract_card(content.get("card", []))
    return {
        "baike_url": content.get("url"),
        "baike_abstract": content.get("abstract_plain", ""),
        "baike_card": card,
        "baike_hit": True,
    }


EMPTY_RESULT = {"baike_url": None, "baike_abstract": "", "baike_card": {}, "baike_hit": False}


def search_baike_url(api_key: str, name: str) -> str | None:
    """通过百度搜索查找百度百科 URL。"""
    url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Appbuilder-From": "openclaw",
        "Content-Type": "application/json",
    }
    body = {
        "messages": [{"content": f"{name} 全国重点文物保护单位 百度百科", "role": "user"}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": 5}],
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        results = resp.json()
        refs = results.get("references", [])
        for ref in refs:
            ref_url = ref.get("url", "")
            if "baike.baidu.com/item/" in ref_url:
                return ref_url
    except Exception as e:
        print(f"  [search-error] {name}: {e}", file=sys.stderr)
    return None


def fetch_baike(client, api_key: str, name: str) -> dict:
    """查询百度百科：先按名称直查，失败则规范化重试，最后百度搜索兜底。"""
    # 策略 1: 原始名称直查
    try:
        content = client.get_lemma_content("lemmaTitle", name)
        if content:
            return _parse_baike_content(content)
    except RuntimeError:
        pass
    except Exception as e:
        print(f"  [error] {name}: {e}", file=sys.stderr)

    # 策略 2: 去掉括号内容重试（如 "安济桥（大石桥）" → "安济桥"）
    bare_name = re.sub(r"[（(].+?[）)]", "", name).strip()
    if bare_name != name:
        try:
            content = client.get_lemma_content("lemmaTitle", bare_name)
            if content:
                return _parse_baike_content(content)
        except (RuntimeError, Exception):
            pass

    # 策略 4: 百度搜索兜底
    baike_url = search_baike_url(api_key, name)
    if baike_url:
        print(f"  [search-hit] {name} -> {baike_url}")
        # 从搜索到的 URL 中提取词条名，尝试用 API 获取内容
        result = dict(EMPTY_RESULT)
        result["baike_url"] = baike_url
        result["baike_hit"] = True
        # 尝试用 lemmaTitle 获取搜索到的词条的完整内容
        try:
            # 从 URL 提取标题: baike.baidu.com/item/xxx → xxx
            from urllib.parse import unquote, urlparse
            path = urlparse(baike_url).path
            if "/item/" in path:
                title = unquote(path.split("/item/")[1].split("/")[0])
                content = client.get_lemma_content("lemmaTitle", title)
                if content:
                    return _parse_baike_content(content)
        except (RuntimeError, Exception):
            pass
        return result

    return dict(EMPTY_RESULT)


def main():
    parser = argparse.ArgumentParser(description="Fetch Baidu Baike data for heritage sites")
    parser.add_argument("--dry-run", action="store_true", help="只处理前 10 条")
    parser.add_argument("--resume", action="store_true", help="从 checkpoint 续跑")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 导入 BaiduBaikeClient
    baike_path = _ROOT / "skills" / "baidu-baike" / "scripts"
    sys.path.insert(0, str(baike_path))
    from baidu_baike import BaiduBaikeClient

    api_key = load_env_key("BAIDU_API_KEY")
    if not api_key:
        print("错误: BAIDU_API_KEY 未配置", file=sys.stderr)
        sys.exit(1)
    client = BaiduBaikeClient(api_key)

    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    print(f"共 {len(sites)} 条记录")

    # 加载已完成的结果
    done: dict[str, dict] = {}
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done[item["release_id"]] = item
        print(f"从 checkpoint 恢复: {len(done)} 条已完成")

    pending = [s for s in sites if s["release_id"] not in done]
    if args.dry_run:
        pending = pending[:10]
        print(f"[dry-run] 只处理前 {len(pending)} 条")

    print(f"待处理: {len(pending)} 条\n")

    results = list(done.values())
    hit = 0
    miss = 0

    for i, site in enumerate(pending):
        release_id = site["release_id"]
        name = site["name"]

        data = fetch_baike(client, api_key, name)
        results.append({"release_id": release_id, **data})

        if data["baike_hit"]:
            hit += 1
        else:
            miss += 1

        # 进度
        total_done = len(done) + i + 1
        total = len(done) + len(pending)
        if (i + 1) % 50 == 0 or i == len(pending) - 1:
            print(f"  进度: {total_done}/{total} (命中 {hit}, 未命中 {miss})")

        # Checkpoint
        if not args.dry_run and (i + 1) % CHECKPOINT_INTERVAL == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"  [checkpoint] 已保存 {len(results)} 条")

        time.sleep(REQUEST_INTERVAL)

    # 最终输出
    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
        print(f"\n完成！{len(results)} 条结果已保存到 {OUTPUT_FILE}")
    else:
        print(f"\n[dry-run] 完成。命中 {hit}, 未命中 {miss}")
        if results:
            print(json.dumps(results[-1], ensure_ascii=False, indent=2))

    # 统计
    total_hit = sum(1 for r in results if r.get("baike_hit"))
    with_url = sum(1 for r in results if r.get("baike_url"))
    with_abstract = sum(1 for r in results if r.get("baike_abstract"))
    print(f"\n命中率: {total_hit}/{len(results)} ({total_hit*100//max(len(results),1)}%)")
    print(f"有 URL: {with_url}, 有摘要: {with_abstract}")


if __name__ == "__main__":
    main()
