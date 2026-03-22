"""
扫描 heritage_sites_geocoded.json，找出名称中含有生僻字或乱码的可疑条目。

判断标准：
  1. 名称含空格（中文文保单位名称正常情况下不含空格）
  2. 含 CJK Extension B 及更高（U+20000+），这类字符在大多数系统上不能正常显示
  3. 含 CJK Extension A（U+3400-U+4DBF），相对少见，作为参考信息

输出：data/encoding_issues.json
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
INPUT = DATA_DIR / "heritage_sites_geocoded.json"
OUTPUT = DATA_DIR / "encoding_issues.json"


def classify_char(ch: str) -> str | None:
    cp = ord(ch)
    if cp >= 0x30000:
        return "CJK-F/G (U+30000+, 极罕见)"
    if cp >= 0x20000:
        return "CJK Extension B/C/D/E (U+20000+, 罕见)"
    if 0x3400 <= cp <= 0x4DBF:
        return "CJK Extension A (U+3400-U+4DBF, 少见)"
    return None


def analyze_name(name: str) -> dict:
    has_space = " " in name
    rare_chars = []
    for ch in name:
        label = classify_char(ch)
        if label:
            rare_chars.append({"char": ch, "codepoint": hex(ord(ch)), "type": label})

    severity = "正常"
    if has_space and rare_chars:
        severity = "高（含空格+生僻字，极可能乱码）"
    elif has_space:
        severity = "中（含空格，可能乱码）"
    elif any("CJK Extension B" in c["type"] or "CJK-F" in c["type"] for c in rare_chars):
        severity = "中（含超出常用范围的生僻字）"
    elif rare_chars:
        severity = "低（含 CJK Extension A 生僻字，可能正确）"

    return {
        "has_space": has_space,
        "rare_chars": rare_chars,
        "severity": severity,
    }


def main():
    with open(INPUT, encoding="utf-8") as f:
        sites = json.load(f)

    issues = []
    for site in sites:
        name = site.get("name", "")
        analysis = analyze_name(name)
        if analysis["severity"] == "正常":
            continue

        issues.append({
            "release_id": site.get("release_id", ""),
            "name": name,
            "severity": analysis["severity"],
            "has_space": analysis["has_space"],
            "rare_chars": analysis["rare_chars"],
            "release_address": site.get("release_address", ""),
            "era": site.get("era", ""),
            "category": site.get("category", ""),
            "corrected_name": "",  # 留空，供用户填写正确名称
        })

    # 按严重程度排序
    severity_order = {
        "高（含空格+生僻字，极可能乱码）": 0,
        "中（含空格，可能乱码）": 1,
        "中（含超出常用范围的生僻字）": 2,
        "低（含 CJK Extension A 生僻字，可能正确）": 3,
    }
    issues.sort(key=lambda x: severity_order.get(x["severity"], 9))

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(issues, f, ensure_ascii=False, indent=2)

    print(f"扫描完成，共 {len(sites)} 条记录")
    print(f"发现可疑条目: {len(issues)} 条")
    print()
    for issue in issues:
        rare_strs = [f'{c["char"]}({c["codepoint"]})' for c in issue["rare_chars"]]
        print(f"  [{issue['severity']}] {issue['release_id']}: {issue['name']}")
        if rare_strs:
            print(f"    生僻字: {', '.join(rare_strs)}")
        print(f"    地址: {issue['release_address']}")
    print()
    print(f"详细结果已保存至: {OUTPUT}")
    print("请在该文件的 corrected_name 字段填入正确名称，然后运行 apply_name_corrections.py 应用修复。")


if __name__ == "__main__":
    main()
