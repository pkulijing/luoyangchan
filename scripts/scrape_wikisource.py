"""
从维基文库解析国务院历次公布的全国重点文物保护单位通知，提取完整列表。

数据源：中文维基文库收录的8批国务院通知原文
输出：  data/heritage_sites_gov.json

页面结构（全部8批一致）：
- 页面含若干 <table>，最大的是主数据表，末尾小表是合并项目（跳过）
- 主数据表中：
    - 单格 colspan 行 = 分类标题，如 "（一）革命遗址及革命纪念建筑物（共33处）"
    - 列顺序：(编/序号, 分类号/编号, 名称, 时代, 地址[, 备注])
      → 名称始终在索引 2，时代在 3，地址在 4
- 子行处理（如第5批"长城"下的8个分段）：
    父行序号非空，子行序号空、第二列为 （1）（2）...
    → 父条目不单独输出，拆分为子条目：
      name="长城-齐长城遗址", release_id="5-442-1"

用法:
  uv run python scrape_wikisource.py
  uv run python scrape_wikisource.py --test 5   # 仅解析第5批，打印前20条
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "heritage_sites_gov.json"

BATCH_YEARS = {
    1: 1961,
    2: 1982,
    3: 1988,
    4: 1996,
    5: 2001,
    6: 2006,
    7: 2013,
    8: 2019,
}

BATCH_URLS = {
    1: "https://zh.wikisource.org/wiki/国务院关于公布第一批全国重点文物保护单位名单的通知",
    2: "https://zh.wikisource.org/wiki/国务院关于公布第二批全国重点文物保护单位的通知",
    3: "https://zh.wikisource.org/wiki/国务院关于公布第三批全国重点文物保护单位的通知",
    4: "https://zh.wikisource.org/wiki/国务院关于公布第四批全国重点文物保护单位的通知",
    5: "https://zh.wikisource.org/wiki/国务院关于公布第五批全国重点文物保护单位和与现有全国重点文物保护单位合并项目的通知",
    6: "https://zh.wikisource.org/wiki/国务院关于核定并公布第六批全国重点文物保护单位的通知",
    7: "https://zh.wikisource.org/wiki/国务院关于核定并公布第七批全国重点文物保护单位的通知",
    8: "https://zh.wikisource.org/wiki/国务院关于核定并公布第八批全国重点文物保护单位的通知",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_category_name(text: str) -> str:
    """
    从分类标题行提取纯分类名称。
    "（一）革命遗址及革命纪念建筑物（共33处）" → "革命遗址及革命纪念建筑物"
    "一、古遗址（共计167处）"                   → "古遗址"
    """
    text = text.strip()
    text = re.sub(r"[（(]共[计計]?\s*\d+\s*处[）)]", "", text)
    text = re.sub(r"^[（(][一二三四五六七八九十百]+[）)][、，\s]*", "", text)
    text = re.sub(r"^[一二三四五六七八九十百]+[、，\s]+", "", text)
    return text.strip()


def is_category_row(cells: list[Tag]) -> bool:
    """单格且带 colspan>=3 的行 = 分类标题行。"""
    if len(cells) != 1:
        return False
    colspan = cells[0].get("colspan")
    return colspan is not None and int(colspan) >= 3


def is_column_header_row(cells: list[Tag]) -> bool:
    """含"名称"关键字（去全角空格后）的行 = 列标题行，跳过。"""
    text = "".join(c.get_text(strip=True) for c in cells)
    normalized = re.sub(r"[\s\u3000]+", "", text)
    return "名称" in normalized


def _make_entry(
    release_id: str,
    name: str,
    era: str | None,
    release_address: str | None,
    category: str | None,
    batch: int,
) -> dict:
    return {
        "release_id": release_id,
        "name": name,
        "era": era or None,
        "release_address": release_address or None,
        "category": category,
        "batch": batch,
        "batch_year": BATCH_YEARS[batch],
    }


def parse_data_table(table: Tag, batch: int) -> list[dict]:
    """
    解析单张数据表格（可能包含多个分类段）。

    处理逻辑：
    1. 先将所有行分组：每组 = (父行cells, [子行cells列表], 分类名)
    2. 无子行 → 正常条目，release_id = "{batch}-{seq}"（全局递增）
    3. 有子行 → 父条目不单独输出，拆分为子条目：
         name = "{父名}-{子名}"，release_id = "{batch}-{父序号}-{i}"
    """
    # --- 第一遍：收集分组 ---
    groups: list[tuple[list[Tag], list[list[Tag]], str | None]] = []
    current_category: str | None = None
    pending_parent: list[Tag] | None = None
    pending_subs: list[list[Tag]] = []
    pending_category: str | None = None

    def flush():
        nonlocal pending_parent, pending_subs
        if pending_parent is not None:
            groups.append((pending_parent, list(pending_subs), pending_category))
        pending_parent = None
        pending_subs = []

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        if is_category_row(cells):
            flush()
            text = cells[0].get_text(" ", strip=True)
            if "合并" in text:
                # 遇到合并章节（理论上已用最大表策略排除，保险起见）
                break
            current_category = extract_category_name(text)
            continue

        if is_column_header_row(cells):
            continue

        if len(cells) < 5 or current_category is None:
            continue

        if not cells[0].get_text(strip=True):
            # 子行（序号列为空）
            if pending_parent is not None:
                pending_subs.append(cells)
            continue

        # 新父行
        flush()
        pending_parent = cells
        pending_subs = []
        pending_category = current_category

    flush()

    # --- 第二遍：emit ---
    sites: list[dict] = []
    seq = 0

    for parent_cells, sub_cells_list, category in groups:
        parent_name = parent_cells[2].get_text(" ", strip=True)
        if not parent_name:
            continue
        parent_era = parent_cells[3].get_text(" ", strip=True) or None
        parent_address = parent_cells[4].get_text(" ", strip=True) or None
        # 父行原始序号（用于子条目 ID）
        parent_seq_raw = re.sub(r"[.\s]+$", "", parent_cells[0].get_text(strip=True))

        if not sub_cells_list:
            seq += 1
            sites.append(_make_entry(
                f"{batch}-{seq}", parent_name, parent_era, parent_address, category, batch
            ))
        else:
            # 父行也占一个序号（修复：之前未自增导致后续条目 release_id 全部偏小 1）
            seq += 1
            parent_release_id = f"{batch}-{seq}"
            # 输出父记录（无独立地址/坐标，geocode 阶段会跳过）
            parent_entry = _make_entry(
                parent_release_id, parent_name, parent_era, parent_address, category, batch
            )
            parent_entry["_is_parent"] = True
            sites.append(parent_entry)
            # 输出子记录
            for i, sub_cells in enumerate(sub_cells_list, 1):
                sub_name = sub_cells[2].get_text(" ", strip=True)
                if not sub_name:
                    continue
                sub_era = sub_cells[3].get_text(" ", strip=True) or parent_era
                sub_address = sub_cells[4].get_text(" ", strip=True) or parent_address
                child_entry = _make_entry(
                    f"{batch}-{seq}-{i}",
                    f"{parent_name}-{sub_name}",
                    sub_era,
                    sub_address,
                    category,
                    batch,
                )
                child_entry["_parent_release_id"] = parent_release_id
                sites.append(child_entry)

    return sites


def parse_batch(html: str, batch: int) -> list[dict]:
    """
    从页面 HTML 中提取所有原始新增条目，跳过合并项目表。
    策略：取行数最多的那张 table（始终是主数据表，合并表行数远少于主表）。
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []
    main_table = max(tables, key=lambda t: len(t.find_all("tr")))
    return parse_data_table(main_table, batch)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="从维基文库解析全国重点文保单位列表")
    parser.add_argument(
        "--test",
        type=int,
        metavar="BATCH",
        help="仅解析指定批次（1-8），打印前20条，不写文件",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help="输出 JSON 文件路径",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    batches = [args.test] if args.test else list(range(1, 9))
    all_sites: list[dict] = []

    for batch in batches:
        url = BATCH_URLS[batch]
        print(f"\n第 {batch} 批：获取页面...", end=" ", flush=True)
        try:
            html = fetch_page(url)
        except Exception as e:
            print(f"失败: {e}")
            continue

        sites = parse_batch(html, batch)
        print(f"解析到 {len(sites)} 条")

        if args.test:
            for s in sites[:20]:
                print(
                    f"  [{s['release_id']:10s}] {s['name'][:22]:22s} | "
                    f"{(s['era'] or ''):12s} | {s['category']:18s} | "
                    f"{s['release_address'] or ''}"
                )
            if len(sites) > 20:
                print(f"  ... 共 {len(sites)} 条")
        else:
            all_sites.extend(sites)
            time.sleep(1)

    if not args.test:
        _print_stats(all_sites)
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_sites, f, ensure_ascii=False, indent=2)
        print(f"\n已保存到: {output_path}")


def _print_stats(all_sites: list[dict]):
    batch_counts: dict[int, int] = {}
    category_counts: dict[str, int] = {}
    for s in all_sites:
        b = s["batch"]
        batch_counts[b] = batch_counts.get(b, 0) + 1
        c = s.get("category") or "（空）"
        category_counts[c] = category_counts.get(c, 0) + 1

    print(f"\n{'='*60}")
    print(f"总计: {len(all_sites)} 条")
    print("\n按批次:")
    for b in sorted(batch_counts):
        print(f"  第 {b} 批: {batch_counts[b]} 条")
    print("\n按分类:")
    for c, cnt in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {c}: {cnt} 条")


if __name__ == "__main__":
    main()
