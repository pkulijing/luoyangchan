"""
将政府官方数据与 Wikipedia 数据合并。

输入:
  - data/heritage_sites_gov.json       政府数据（release_id/name/era/release_address/category/batch）
  - data/heritage_sites_with_coords.json  Wikipedia 数据（含坐标/wikipedia_url/province/city）

输出:
  - data/heritage_sites_merged.json    合并后的完整数据集
  - data/reconciliation_report.txt     匹配质量报告

用法:
  uv run python reconcile_data.py
"""

import difflib
import json
import re
from pathlib import Path

import zhconv

DATA_DIR = Path(__file__).parent.parent / "data"
GOV_FILE = DATA_DIR / "heritage_sites_gov.json"
WIKI_FILE = DATA_DIR / "heritage_sites_with_coords.json"
MERGED_FILE = DATA_DIR / "heritage_sites_merged.json"
REPORT_FILE = DATA_DIR / "reconciliation_report.txt"


def to_simplified(text: str) -> str:
    """将繁体字转为简体（使用 zhconv 库）。"""
    return zhconv.convert(text, "zh-hans")


def strip_wiki_annotations(name: str) -> str:
    """去除 Wikipedia 名称中的脚注标记，如 [注1]、[註 1]、[注 A]。"""
    return re.sub(r"\[(?:注|註)\s*[0-9A-Za-z]+\]", "", name).strip()


def normalize_name(name: str) -> str:
    """
    规范化名称用于匹配：
    - 去除 Wikipedia 脚注标记 [注X]
    - 去除括号内内容（含省份、别名等）
    - 去除空格
    - 繁→简转换
    """
    name = strip_wiki_annotations(name)
    # 去除中文全角括号内容 （...）
    name = re.sub(r"（[^）]*）", "", name)
    # 去除英文括号内容 (...)，包含省份标记如 (广东省)
    name = re.sub(r"\([^)]*\)", "", name)
    # 去除方括号内容（如 [注1] 残余）
    name = re.sub(r"\[[^\]]*\]", "", name)
    # 去除空格
    name = name.replace(" ", "").replace("\u3000", "")
    # 繁→简
    name = to_simplified(name)
    return name.strip()


def extract_province(address: str | None) -> str | None:
    """从地址字符串中提取省份/直辖市。"""
    if not address:
        return None
    direct_cities = ["北京市", "天津市", "上海市", "重庆市"]
    for city in direct_cities:
        if address.startswith(city):
            return city
    m = re.match(r"^(.{2,4}?[省自治区])", address)
    if m:
        return m.group(1)
    return None


def build_wiki_index(wiki_sites: list[dict]) -> dict:
    """
    构建 Wikipedia 数据的索引结构：
      key: (normalized_name, batch) -> list of wiki records
    """
    index = {}
    for site in wiki_sites:
        norm = normalize_name(site.get("name", ""))
        batch = site.get("batch")
        key = (norm, batch)
        index.setdefault(key, []).append(site)
    return index


def match_exact(gov: dict, wiki_index: dict) -> dict | None:
    """轮次1：(normalized_name, batch) 精确匹配。"""
    norm = normalize_name(gov["name"])
    batch = gov.get("batch")
    candidates = wiki_index.get((norm, batch), [])
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # 多个候选，尝试用省份进一步区分
        gov_prov = extract_province(gov.get("release_address"))
        for c in candidates:
            wiki_prov = c.get("province") or extract_province(c.get("address"))
            if gov_prov and wiki_prov and gov_prov == wiki_prov:
                return c
        # 无法区分，返回第一个
        return candidates[0]
    return None


def match_fuzzy_name(gov: dict, wiki_index: dict) -> dict | None:
    """
    轮次2：原始名称（去括号）精确匹配。
    例如政府数据"安济桥（大石桥）"→"安济桥"，Wikipedia 数据可能就叫"安济桥"
    """
    norm_gov = normalize_name(gov["name"])
    # 如果 normalize 后的名字与原始名字不同，说明有括号被去掉，再试一次
    if norm_gov == gov["name"].strip():
        return None
    batch = gov.get("batch")
    candidates = wiki_index.get((norm_gov, batch), [])
    if candidates:
        return candidates[0]
    return None


def match_difflib(gov: dict, wiki_sites: list[dict]) -> tuple[dict | None, float]:
    """
    轮次3：同 batch 内 difflib 相似度匹配（阈值 0.85）。
    返回 (最佳匹配记录, 相似度分数)
    """
    batch = gov.get("batch")
    gov_prov = extract_province(gov.get("release_address"))
    norm_gov = normalize_name(gov["name"])

    # 只在同批次（且如果能匹配省份则同省份）内搜索
    candidates = [
        s for s in wiki_sites
        if s.get("batch") == batch
    ]
    if gov_prov:
        prov_candidates = [
            s for s in candidates
            if (s.get("province") or extract_province(s.get("address"))) == gov_prov
        ]
        if prov_candidates:
            candidates = prov_candidates

    if not candidates:
        return None, 0.0

    norm_candidates = [(normalize_name(s.get("name", "")), s) for s in candidates]
    best_score = 0.0
    best_match = None

    for norm_name, site in norm_candidates:
        score = difflib.SequenceMatcher(None, norm_gov, norm_name).ratio()
        if score > best_score:
            best_score = score
            best_match = site

    if best_score >= 0.85:
        return best_match, best_score
    return None, best_score


def merge_record(gov: dict, wiki: dict | None) -> dict:
    """
    将政府数据和 Wikipedia 数据合并为一条记录。
    政府数据的 name/era/category/batch/batch_year/release_id/release_address 优先。
    Wikipedia 数据的 wikipedia_url/坐标/province/city/district/address/description 保留。
    """
    merged = {
        # 以政府数据为准
        "name": gov["name"],
        "era": gov.get("era"),
        "category": gov["category"],
        "batch": gov.get("batch"),
        "batch_year": gov.get("batch_year"),
        "release_id": gov.get("release_id"),
        "release_address": gov.get("release_address"),
        # 来自 Wikipedia（若有）
        "province": None,
        "city": None,
        "district": None,
        "address": None,
        "latitude": None,
        "longitude": None,
        "wikipedia_url": None,
        "description": None,
        "image_url": None,
    }

    if wiki:
        merged["province"] = wiki.get("province")
        merged["city"] = wiki.get("city")
        merged["district"] = wiki.get("district")
        merged["address"] = wiki.get("address")
        merged["latitude"] = wiki.get("latitude")
        merged["longitude"] = wiki.get("longitude")
        merged["wikipedia_url"] = wiki.get("wikipedia_url")
        merged["description"] = wiki.get("description")
        merged["image_url"] = wiki.get("image_url")

    return merged


def main():
    if not GOV_FILE.exists():
        print(f"错误：找不到政府数据文件 {GOV_FILE}")
        print("请先运行 scrape_government.py")
        return

    if not WIKI_FILE.exists():
        print(f"错误：找不到 Wikipedia 数据文件 {WIKI_FILE}")
        print("请先运行 fetch_coordinates.py")
        return

    with open(GOV_FILE, encoding="utf-8") as f:
        gov_sites = json.load(f)
    with open(WIKI_FILE, encoding="utf-8") as f:
        wiki_sites = json.load(f)

    print(f"政府数据: {len(gov_sites)} 条")
    print(f"Wikipedia 数据: {len(wiki_sites)} 条")

    wiki_index = build_wiki_index(wiki_sites)

    merged = []
    wiki_used = set()  # 记录已被匹配的 Wikipedia 记录索引

    stats = {"exact": 0, "normalized": 0, "fuzzy": 0, "new": 0}
    fuzzy_matches = []  # 供人工审查
    wiki_id_to_idx = {id(s): i for i, s in enumerate(wiki_sites)}

    for gov in gov_sites:
        wiki_match = None
        match_type = "new"
        match_score = None

        # 轮次1：精确匹配
        w = match_exact(gov, wiki_index)
        if w and id(w) not in wiki_used:
            wiki_match = w
            match_type = "exact"
            stats["exact"] += 1

        # 轮次2：去括号后精确匹配
        if not wiki_match:
            w = match_fuzzy_name(gov, wiki_index)
            if w and id(w) not in wiki_used:
                wiki_match = w
                match_type = "normalized"
                stats["normalized"] += 1

        # 轮次3：difflib 相似度匹配
        if not wiki_match:
            w, score = match_difflib(gov, wiki_sites)
            if w and id(w) not in wiki_used:
                wiki_match = w
                match_type = "fuzzy"
                match_score = score
                stats["fuzzy"] += 1
                fuzzy_matches.append({
                    "gov_name": gov["name"],
                    "wiki_name": w.get("name"),
                    "batch": gov.get("batch"),
                    "score": round(score, 3),
                })

        if wiki_match:
            wiki_used.add(id(wiki_match))
        else:
            stats["new"] += 1

        record = merge_record(gov, wiki_match)
        record["_match_type"] = match_type
        if match_score:
            record["_match_score"] = round(match_score, 3)
        merged.append(record)

    # 找出 Wikipedia 中未被匹配的记录
    unmatched_wiki = [s for s in wiki_sites if id(s) not in wiki_used]

    # 轮次4：反向匹配——对每条 Wikipedia 独有记录，
    # 在已合并的政府记录中查找最佳匹配（去注释+繁简归一后 difflib），
    # 找到则把 Wikipedia 的坐标/URL 补入政府记录，不生成新行。
    # 只剩真正无法匹配的才保留为独有。
    gov_merged_map = {id(r): r for r in merged}  # 用于回写坐标
    still_unmatched = []
    reverse_matched = 0

    for w in unmatched_wiki:
        w_norm = normalize_name(w.get("name", ""))
        w_batch = w.get("batch")
        w_prov = w.get("province") or extract_province(w.get("address"))

        best_score = 0.0
        best_gov_rec = None

        for gov_rec in merged:
            if gov_rec.get("batch") != w_batch:
                continue
            # 省份过滤（宽松：只有两边都有省份且不同才排除）
            g_prov = gov_rec.get("province") or extract_province(gov_rec.get("release_address"))
            if w_prov and g_prov and w_prov != g_prov:
                continue
            score = difflib.SequenceMatcher(
                None, w_norm, normalize_name(gov_rec.get("name", ""))
            ).ratio()
            if score > best_score:
                best_score = score
                best_gov_rec = gov_rec

        # 降级：若子串包含，也视为匹配（处理长城各段 wiki="秦长城遗址" gov="长城-秦长城遗址"）
        if best_score < 0.65 and best_gov_rec is None:
            for gov_rec in merged:
                if gov_rec.get("batch") != w_batch:
                    continue
                g_norm = normalize_name(gov_rec.get("name", ""))
                if w_norm and w_norm in g_norm:
                    best_gov_rec = gov_rec
                    best_score = 0.65
                    break

        if best_score >= 0.65 and best_gov_rec is not None:
            # 把 Wikipedia 的坐标/URL 补写入已有政府记录（若政府记录该字段为空）
            for field in ("province", "city", "district", "address",
                          "latitude", "longitude", "wikipedia_url",
                          "description", "image_url"):
                if not best_gov_rec.get(field) and w.get(field):
                    best_gov_rec[field] = w[field]
            reverse_matched += 1
        else:
            still_unmatched.append(w)

    unmatched_wiki = still_unmatched
    stats["reverse"] = reverse_matched

    print(f"\n匹配结果:")
    print(f"  精确匹配:    {stats['exact']} 条")
    print(f"  去括号匹配:  {stats['normalized']} 条")
    print(f"  模糊匹配:    {stats['fuzzy']} 条")
    print(f"  反向补充:    {stats.get('reverse', 0)} 条（Wikipedia→政府记录补坐标）")
    print(f"  新增记录:    {stats['new']} 条（来自政府数据，Wikipedia 无对应）")
    print(f"  Wikipedia 独有（仍未匹配）: {len(unmatched_wiki)} 条")

    # 对所有记录的文本字段统一转为简体
    _TEXT_FIELDS = ("name", "era", "category", "release_address", "address",
                    "province", "city", "district")

    def simplify_record(r: dict) -> dict:
        for f in _TEXT_FIELDS:
            if isinstance(r.get(f), str):
                r[f] = to_simplified(r[f])
        return r

    # 移除内部字段，写入最终文件
    final = []
    for r in merged:
        r.pop("_match_type", None)
        r.pop("_match_score", None)
        final.append(simplify_record(r))

    # 剩余 unmatched_wiki 已无法匹配到任何政府记录，直接丢弃，不追加到输出

    with open(MERGED_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\n合并结果已保存到: {MERGED_FILE}（共 {len(final)} 条）")

    # 写入报告
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# 数据合并报告\n\n")
        f.write(f"政府数据: {len(gov_sites)} 条\n")
        f.write(f"Wikipedia 数据: {len(wiki_sites)} 条\n")
        f.write(f"合并结果: {len(final)} 条\n\n")
        f.write(f"## 匹配统计\n")
        f.write(f"- 精确匹配:   {stats['exact']} 条\n")
        f.write(f"- 去括号匹配: {stats['normalized']} 条\n")
        f.write(f"- 模糊匹配:   {stats['fuzzy']} 条\n")
        f.write(f"- 反向补充:   {stats.get('reverse', 0)} 条\n")
        f.write(f"- 新增记录:   {stats['new']} 条\n")
        f.write(f"- Wikipedia 独有（仍未匹配）: {len(unmatched_wiki)} 条\n\n")

        if fuzzy_matches:
            f.write(f"## 模糊匹配列表（请人工核查）\n\n")
            for m in fuzzy_matches:
                f.write(
                    f"- [第{m['batch']}批] 政府:「{m['gov_name']}」↔ Wikipedia:「{m['wiki_name']}」"
                    f"（相似度 {m['score']}）\n"
                )
            f.write("\n")

        if unmatched_wiki:
            f.write(f"## Wikipedia 独有记录（政府数据无对应，已保留）\n\n")
            for s in unmatched_wiki[:100]:  # 最多列出100条
                f.write(f"- [第{s.get('batch')}批] {s.get('name')} ({s.get('province')})\n")
            if len(unmatched_wiki) > 100:
                f.write(f"  ...以及另外 {len(unmatched_wiki) - 100} 条\n")

    print(f"匹配报告已保存到: {REPORT_FILE}")


if __name__ == "__main__":
    main()
