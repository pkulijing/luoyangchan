"""
Phase 2: 通过 Wikidata SPARQL 查询 P18 (image) 属性，
获取全国重点文物保护单位 (Q916583) 的 Wikimedia Commons 图片。

单次 SPARQL 查询即可拿到所有结果，然后按中文名与本地数据匹配。

用法:
  uv run python round6/fetch_wikidata_images.py
"""

import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import unquote, quote

import requests

_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = _ROOT / "data"
MAIN_FILE = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT_DIR = DATA_DIR / "round6"
OUTPUT_FILE = OUTPUT_DIR / "wikidata_images.json"

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"

SPARQL_QUERY = """
SELECT ?item ?itemLabel ?image WHERE {
  ?item wdt:P1435 wd:Q1188574 .
  ?item wdt:P18 ?image .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "zh,zh-hans,zh-cn,en" . }
}
"""


def commons_file_to_thumb_url(file_url: str, width: int = 600) -> str:
    """将 Commons file URL 转换为缩略图直链。

    file_url 格式: http://commons.wikimedia.org/wiki/Special:FilePath/Example.jpg
    返回: https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Example.jpg/600px-Example.jpg
    """
    # 提取文件名
    filename = file_url.rsplit("/", 1)[-1]
    filename = unquote(filename).replace(" ", "_")

    # 计算 MD5
    md5 = hashlib.md5(filename.encode("utf-8")).hexdigest()
    a, ab = md5[0], md5[:2]

    # 编码文件名用于 URL（保留 Unicode 字符不编码不行，得 quote）
    encoded = quote(filename)

    # 原图 URL
    original = f"https://upload.wikimedia.org/wikipedia/commons/{a}/{ab}/{encoded}"
    # 缩略图 URL
    thumb = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{a}/{ab}/{encoded}/{width}px-{encoded}"

    return original


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 加载本地数据
    with open(MAIN_FILE, encoding="utf-8") as f:
        sites = json.load(f)

    # 建立名称索引（name → release_id），用于匹配
    name_to_rid: dict[str, str] = {}
    for s in sites:
        name_to_rid[s["name"]] = s["release_id"]

    print(f"本地数据: {len(sites)} 条站点\n")

    # 执行 SPARQL 查询
    print("执行 Wikidata SPARQL 查询...")
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    resp = session.get(
        SPARQL_ENDPOINT,
        params={"query": SPARQL_QUERY, "format": "json"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    bindings = data["results"]["bindings"]
    print(f"Wikidata 返回 {len(bindings)} 条有 P18 图片的全国重点文保")

    # 匹配
    results: list[dict] = []
    matched = 0
    unmatched_names: list[str] = []

    for b in bindings:
        label = b["itemLabel"]["value"]
        file_url = b["image"]["value"]
        image_url = commons_file_to_thumb_url(file_url)

        rid = name_to_rid.get(label)
        if rid:
            results.append({
                "release_id": rid,
                "image_url": image_url,
                "source": "wikidata_p18",
                "wikidata_label": label,
            })
            matched += 1
        else:
            unmatched_names.append(label)

    print(f"\n匹配结果: {matched} 条命中本地数据")
    print(f"未匹配: {len(unmatched_names)} 条（Wikidata 标签与本地名称不一致）")

    if unmatched_names[:10]:
        print("未匹配样例:")
        for n in unmatched_names[:10]:
            print(f"  {n}")

    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n已保存 {len(results)} 条到 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
