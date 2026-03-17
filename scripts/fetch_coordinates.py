"""
通过 Wikipedia API 和 Wikidata 获取全国重点文物保护单位的经纬度坐标。

策略：
1. 对有 Wikipedia URL 的条目，通过 Wikipedia API 的 coordinates 属性批量查询
   (一次最多 50 个标题)
2. 对无法通过 Wikipedia 获取坐标的，后续可通过高德地理编码 API 补充

Wikipedia API: https://zh.wikipedia.org/w/api.php?action=query&prop=coordinates
"""

import json
import time
from pathlib import Path
from urllib.parse import unquote

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_FILE = DATA_DIR / "heritage_sites.json"
OUTPUT_FILE = DATA_DIR / "heritage_sites_with_coords.json"

WIKI_API = "https://zh.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
}


def extract_wiki_title(url: str) -> str | None:
    """从 Wikipedia URL 中提取页面标题"""
    if "/wiki/" in url:
        title = url.split("/wiki/", 1)[1]
        return unquote(title)
    return None


def batch_query_wiki_coords(titles: list[str]) -> dict[str, tuple[float, float]]:
    """
    通过 Wikipedia API 批量查询坐标。
    每次最多 50 个标题。
    返回 {title: (lat, lng)} 字典。
    """
    if not titles:
        return {}

    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "coordinates",
        "format": "json",
    }

    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        coords = {}
        for page in data.get("query", {}).get("pages", {}).values():
            title = page.get("title", "")
            page_coords = page.get("coordinates", [])
            if page_coords:
                lat = page_coords[0]["lat"]
                lon = page_coords[0]["lon"]
                coords[title] = (lat, lon)

        # 处理重定向：Wikipedia API 会返回 normalized/redirects 信息
        normalized = {
            n["from"]: n["to"]
            for n in data.get("query", {}).get("normalized", [])
        }
        redirects = {
            r["from"]: r["to"]
            for r in data.get("query", {}).get("redirects", [])
        }

        # 将坐标也映射回原始标题
        for original, norm in normalized.items():
            final = redirects.get(norm, norm)
            if final in coords and original not in coords:
                coords[original] = coords[final]
        for original, target in redirects.items():
            if target in coords and original not in coords:
                coords[original] = coords[target]

        return coords
    except Exception as e:
        print(f"  Wiki API error: {e}")
        return {}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch coordinates for heritage sites")
    parser.add_argument("--input", default=str(INPUT_FILE))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        sites = json.load(f)

    print(f"Loaded {len(sites)} sites")

    # 提取所有有 Wikipedia URL 的条目的标题
    title_to_indices: dict[str, list[int]] = {}
    for i, site in enumerate(sites):
        if site.get("wikipedia_url"):
            title = extract_wiki_title(site["wikipedia_url"])
            if title:
                title_to_indices.setdefault(title, []).append(i)

    unique_titles = list(title_to_indices.keys())
    print(f"Sites with Wikipedia URL: {len(unique_titles)}")

    # 分批查询，每批 50 个
    batch_size = 50
    all_coords: dict[str, tuple[float, float]] = {}

    for i in range(0, len(unique_titles), batch_size):
        batch = unique_titles[i:i+batch_size]
        batch_coords = batch_query_wiki_coords(batch)
        all_coords.update(batch_coords)

        progress = min(i + batch_size, len(unique_titles))
        print(f"  Progress: {progress}/{len(unique_titles)} queried, {len(all_coords)} coords found")
        time.sleep(0.5)  # 礼貌性延迟

    # 将坐标写入 sites
    matched = 0
    for title, indices in title_to_indices.items():
        coord = all_coords.get(title)
        if coord:
            for idx in indices:
                sites[idx]["latitude"] = round(coord[0], 6)
                sites[idx]["longitude"] = round(coord[1], 6)
                matched += 1

    print(f"\nMatched via Wikipedia: {matched}/{len(sites)} ({matched*100//len(sites)}%)")

    # 保存结果
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)

    total_with_coords = sum(1 for s in sites if s.get("latitude"))
    without_coords = len(sites) - total_with_coords
    print(f"Total with coordinates: {total_with_coords}/{len(sites)}")
    print(f"Without coordinates: {without_coords}")
    print(f"Saved to {output_path}")

    # 打印无坐标的条目统计
    no_coord_provinces: dict[str, int] = {}
    for s in sites:
        if not s.get("latitude"):
            p = s.get("province") or "未知"
            no_coord_provinces[p] = no_coord_provinces.get(p, 0) + 1

    if no_coord_provinces:
        print(f"\n=== 无坐标条目按省份统计 ===")
        for p, c in sorted(no_coord_provinces.items(), key=lambda x: -x[1])[:10]:
            print(f"  {p}: {c}")


if __name__ == "__main__":
    main()
