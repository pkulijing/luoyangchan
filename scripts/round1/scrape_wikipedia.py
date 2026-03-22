"""
从中文 Wikipedia 的"全国重点文物保护单位列表"页面爬取全部文保单位数据。

该页面按类型分为多个表格，每个表格格式统一：名称、时代、地址、批次。
表格前的 section 标题对应文保单位的类型。

来源页面: https://zh.wikipedia.org/wiki/全国重点文物保护单位列表
"""

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

WIKI_API = "https://zh.wikipedia.org/w/api.php"
PAGE_TITLE = "全国重点文物保护单位列表"

BATCH_YEARS = {1: 1961, 2: 1982, 3: 1988, 4: 1996, 5: 2001, 6: 2006, 7: 2013, 8: 2019}

# Wikipedia section 标题 -> 标准化类型
SECTION_TO_CATEGORY = {
    "革命遗址及革命纪念建筑物": "近现代重要史迹及代表性建筑",
    "石窟寺": "石窟寺及石刻",
    "古建筑及历史纪念建筑物": "古建筑",
    "石刻及其他": "石窟寺及石刻",
    "古遗址": "古遗址",
    "古墓葬": "古墓葬",
    "古建筑": "古建筑",
    "石窟寺及石刻": "石窟寺及石刻",
    "近现代重要史迹及代表性建筑": "近现代重要史迹及代表性建筑",
    "其他": "其他",
}

# 跳过的 section（归并名单不是独立的文保单位）
SKIP_SECTIONS = {"归并名单"}


def fetch_page() -> tuple[str, list[dict]]:
    """获取页面 HTML 和 section 信息"""
    params = {
        "action": "parse",
        "page": PAGE_TITLE,
        "format": "json",
        "prop": "text|sections",
        "utf8": 1,
        "redirects": 1,
    }
    headers = {
        "User-Agent": "LuoyangchanBot/1.0 (Heritage Sites Map Project; educational use)"
    }
    resp = requests.get(WIKI_API, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    html = data["parse"]["text"]["*"]
    sections = data["parse"]["sections"]
    return html, sections


DIRECT_MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}

def extract_province_city(address: str) -> tuple[str | None, str | None]:
    """从地址字符串中提取省份和城市"""
    province = None
    city = None

    # 先匹配直辖市
    for dm in DIRECT_MUNICIPALITIES:
        if address.startswith(dm):
            province = dm
            city = dm
            return province, city

    # 匹配省/自治区
    prov_match = re.match(
        r"([\u4e00-\u9fa5]+(?:省|自治区))", address
    )
    if prov_match:
        province = prov_match.group(1)

    # 匹配城市（省份/自治区之后的市/州/盟/地区）
    if province:
        rest = address[len(province):]
        city_match = re.match(
            r"([\u4e00-\u9fa5]+(?:市|州|盟|地区))", rest
        )
        if city_match:
            city = city_match.group(1)

    return province, city


def parse_batch(batch_text: str) -> int | None:
    """从批次文本中提取批次号"""
    # 处理 "第X批" 格式
    match = re.search(r"第\s*(\d+)\s*批", batch_text)
    if match:
        return int(match.group(1))

    # 处理中文数字
    cn_nums = "一二三四五六七八九十"
    for i, cn in enumerate(cn_nums, 1):
        if f"第{cn}批" in batch_text:
            return i

    # 纯数字
    match = re.search(r"(\d+)", batch_text)
    if match:
        n = int(match.group(1))
        if 1 <= n <= 8:
            return n

    return None


def parse_table(table: Tag, category: str) -> list[dict]:
    """解析单个表格"""
    sites = []

    # 解析表头
    header_row = table.find("tr")
    if not header_row:
        return sites
    headers = [th.get_text().strip() for th in header_row.find_all(["th", "td"])]

    col_map = {}
    for i, h in enumerate(headers):
        if "名称" in h:
            col_map["name"] = i
        elif "时代" in h or "时期" in h or "年代" in h:
            col_map["era"] = i
        elif "地址" in h or "地点" in h or "所在" in h:
            col_map["address"] = i
        elif "批次" in h:
            col_map["batch"] = i

    if "name" not in col_map:
        return sites

    num_cols = len(headers)

    # 处理 rowspan：展开合并的单元格
    raw_rows = table.find_all("tr")[1:]
    rowspan_carry: dict[int, tuple[Tag, int]] = {}

    for row in raw_rows:
        cells = row.find_all(["td", "th"])
        expanded: list[Tag | None] = [None] * num_cols
        cell_idx = 0

        for col_idx in range(num_cols):
            if col_idx in rowspan_carry:
                carried_cell, remaining = rowspan_carry[col_idx]
                expanded[col_idx] = carried_cell
                if remaining > 1:
                    rowspan_carry[col_idx] = (carried_cell, remaining - 1)
                else:
                    del rowspan_carry[col_idx]
            else:
                if cell_idx < len(cells):
                    cell = cells[cell_idx]
                    expanded[col_idx] = cell
                    rs = int(cell.get("rowspan", 1))
                    if rs > 1:
                        rowspan_carry[col_idx] = (cell, rs - 1)
                    cell_idx += 1

        # 提取数据
        name_cell = expanded[col_map["name"]] if "name" in col_map else None
        if not name_cell:
            continue
        name = name_cell.get_text().strip()
        if not name:
            continue

        # Wikipedia 链接
        wiki_url = None
        link = name_cell.find("a")
        if link and link.get("href", "").startswith("/wiki/"):
            wiki_url = "https://zh.wikipedia.org" + link["href"]

        era = None
        if "era" in col_map and expanded[col_map["era"]]:
            era = expanded[col_map["era"]].get_text().strip()

        address = None
        if "address" in col_map and expanded[col_map["address"]]:
            address = expanded[col_map["address"]].get_text().strip()

        batch = None
        if "batch" in col_map and expanded[col_map["batch"]]:
            batch = parse_batch(expanded[col_map["batch"]].get_text())

        province, city = extract_province_city(address) if address else (None, None)

        sites.append({
            "name": name,
            "province": province,
            "city": city,
            "address": address,
            "category": category,
            "era": era,
            "batch": batch,
            "batch_year": BATCH_YEARS.get(batch) if batch else None,
            "wikipedia_url": wiki_url,
            "latitude": None,
            "longitude": None,
        })

    return sites


def scrape():
    """爬取全部文保单位数据"""
    print(f"Fetching page: {PAGE_TITLE}")
    html, sections = fetch_page()
    soup = BeautifulSoup(html, "html.parser")

    all_sites = []
    tables = soup.find_all("table", class_="wikitable")

    for table in tables:
        # 确定该表格属于哪个 section（类型）
        prev_heading = table.find_previous(["h3", "h2"])
        if not prev_heading:
            continue

        section_name = prev_heading.get_text().strip()
        # 清理 Wikipedia 的 [编辑] 链接文本
        section_name = re.sub(r"\[编辑\]", "", section_name).strip()

        if section_name in SKIP_SECTIONS:
            continue

        category = SECTION_TO_CATEGORY.get(section_name, "其他")
        sites = parse_table(table, category)
        print(f"  {section_name} ({category}): {len(sites)} sites")
        all_sites.extend(sites)

    return all_sites


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scrape heritage sites from Wikipedia")
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "heritage_sites.json"),
        help="Output JSON file path",
    )
    args = parser.parse_args()

    sites = scrape()
    print(f"\nTotal sites scraped: {len(sites)}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)

    print(f"Data saved to {output_path}")

    # 统计
    provinces_count: dict[str, int] = {}
    categories_count: dict[str, int] = {}
    for site in sites:
        p = site["province"] or "未知"
        provinces_count[p] = provinces_count.get(p, 0) + 1
        categories_count[site["category"]] = categories_count.get(site["category"], 0) + 1

    print(f"\n=== 按类型统计 ===")
    for cat, c in sorted(categories_count.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {c}")

    print(f"\n=== 按省份统计 (前10) ===")
    for p, c in sorted(provinces_count.items(), key=lambda x: -x[1])[:10]:
        print(f"  {p}: {c}")

    # 数据完整性
    total = len(sites)
    print(f"\n=== 数据完整性 ===")
    for field in ["province", "city", "address", "era", "batch", "wikipedia_url"]:
        has = sum(1 for s in sites if s.get(field))
        print(f"  {field}: {has}/{total} ({has*100//total}%)")


if __name__ == "__main__":
    main()
