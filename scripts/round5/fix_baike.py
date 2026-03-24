"""
修复百度百科采集：对未命中的条目用百度搜索兜底重试（加大限流间隔）。

用法:
  uv run python round5/fix_baike.py --dry-run    # 只看统计
  uv run python round5/fix_baike.py              # 执行修复
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
ROUND5_DIR = DATA_DIR / "round5"
BAIKE_FILE = ROUND5_DIR / "baike_data.json"
CHECKPOINT_FILE = ROUND5_DIR / "baike_fix_checkpoint.json"

SEARCH_INTERVAL = 1.5  # 加大间隔避免 429
CHECKPOINT_INTERVAL = 50


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


def search_baike(api_key: str, name: str) -> dict | None:
    """百度搜索找百度百科 URL 和摘要。"""
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
        if resp.status_code == 429:
            # 限流，等待后重试一次
            time.sleep(5)
            resp = requests.post(url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        results = resp.json()
        refs = results.get("references", [])
        for ref in refs:
            ref_url = ref.get("url", "")
            if "baike.baidu.com/item/" in ref_url:
                return {"baike_url": ref_url, "baike_hit": True}
    except Exception as e:
        print(f"  [error] {name}: {e}", file=sys.stderr)
    return None


def try_get_content(client, baike_url: str) -> dict:
    """尝试从百度百科 API 获取完整内容。"""
    try:
        path = urlparse(baike_url).path
        if "/item/" in path:
            title = unquote(path.split("/item/")[1].split("/")[0])
            content = client.get_lemma_content("lemmaTitle", title)
            if content:
                abstract = content.get("abstract_plain", "")
                # 提取 card
                card = {}
                useful_keys = {"地理位置", "位置", "所在地", "建造年代", "始建时间",
                               "保护级别", "所属年代", "所处时代", "占地面积"}
                for item in content.get("card", []):
                    key = item.get("name", "")
                    value = item.get("value", "")
                    if isinstance(key, list):
                        key = "".join(str(k) for k in key)
                    if isinstance(value, list):
                        parts = []
                        for v in value:
                            if isinstance(v, dict):
                                parts.append(v.get("text", str(v)))
                            else:
                                parts.append(str(v))
                        value = "".join(parts)
                    key = key.strip()
                    value = value.strip()
                    if key in useful_keys and value:
                        card[key] = value
                return {"baike_abstract": abstract, "baike_card": card}
    except Exception:
        pass
    return {"baike_abstract": "", "baike_card": {}}


def main():
    parser = argparse.ArgumentParser(description="Fix Baidu Baike: retry failed with search fallback")
    parser.add_argument("--dry-run", action="store_true", help="只看统计")
    args = parser.parse_args()

    # 导入 BaiduBaikeClient
    baike_path = _ROOT / "skills" / "baidu-baike" / "scripts"
    sys.path.insert(0, str(baike_path))
    from baidu_baike import BaiduBaikeClient

    api_key = load_env_key("BAIDU_API_KEY")
    if not api_key:
        print("错误: BAIDU_API_KEY 未配置", file=sys.stderr)
        sys.exit(1)
    client = BaiduBaikeClient(api_key)

    with open(BAIKE_FILE, encoding="utf-8") as f:
        all_data = json.load(f)
    data_map = {d["release_id"]: d for d in all_data}

    # 找出未命中的条目
    failed = [d for d in all_data if not d.get("baike_hit")]
    print(f"总记录: {len(all_data)}, 未命中: {len(failed)}")

    # 加载 checkpoint
    done_ids: set[str] = set()
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for item in json.load(f):
                done_ids.add(item["release_id"])
                data_map[item["release_id"]].update(item)
        print(f"从 checkpoint 恢复: {len(done_ids)} 条已处理")

    pending = [d for d in failed if d["release_id"] not in done_ids]

    if args.dry_run:
        print(f"[dry-run] 待重试: {len(pending)} 条")
        return

    print(f"待重试: {len(pending)} 条\n")

    # 需要 name → 从主数据获取
    with open(DATA_DIR / "heritage_sites_geocoded.json", encoding="utf-8") as f:
        sites = json.load(f)
    name_map = {s["release_id"]: s["name"] for s in sites}

    recovered = 0
    checkpoint_data = []

    for i, item in enumerate(pending):
        rid = item["release_id"]
        name = name_map.get(rid, rid)

        result = search_baike(api_key, name)
        if result:
            # 搜索到了 baike URL，尝试获取完整内容
            content = try_get_content(client, result["baike_url"])
            item.update(result)
            item.update(content)
            recovered += 1
            print(f"  [recovered] {rid}: {name} -> {result['baike_url']}")

        checkpoint_data.append({"release_id": rid, **{k: item[k] for k in ["baike_url", "baike_abstract", "baike_card", "baike_hit"]}})

        if (i + 1) % 50 == 0 or i == len(pending) - 1:
            print(f"  进度: {i+1}/{len(pending)} (恢复 {recovered})")

        if (i + 1) % CHECKPOINT_INTERVAL == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)

        time.sleep(SEARCH_INTERVAL)

    # 写回
    result_list = list(data_map.values())
    with open(BAIKE_FILE, "w", encoding="utf-8") as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()

    total_hit = sum(1 for d in result_list if d.get("baike_hit"))
    print(f"\n完成！恢复 {recovered} 条")
    print(f"最终命中率: {total_hit}/{len(result_list)} ({total_hit*100//len(result_list)}%)")


if __name__ == "__main__":
    main()
