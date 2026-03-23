"""
拆分茶马古道 (7-516) 为 21 个地级市子记录

数据来源: 维基百科茶马古道词条
坐标来源: 维基百科表格中的 WGS-84 坐标（每个地级市选一个有文保标志牌的代表点，无标志则取第一个有坐标的点）

用法:
  uv run python round4/split_chamagudao.py           # 执行拆分
  uv run python round4/split_chamagudao.py --dry-run  # 只预览不写入
"""

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
MAIN_FILE = _ROOT / "data" / "heritage_sites_geocoded.json"

PARENT_ID = "7-516"

# 21 个地级市子记录
# lat/lng 来自维基百科，WGS-84 坐标
CHILDREN = [
    # --- 四川省 (7个) ---
    {
        "suffix": 1,
        "name": "茶马古道-成都段",
        "province": "四川省", "city": "成都市", "district": "邛崃市",
        "address": "四川省成都市邛崃市平乐镇骑龙山古道",
        "rep_name": "平乐骑龙山古道",
        "lat": 30.34683, "lng": 103.34392,
    },
    {
        "suffix": 2,
        "name": "茶马古道-自贡段",
        "province": "四川省", "city": "自贡市", "district": "自流井区",
        "address": "四川省自贡市自流井区张家沱富台山彙柴口古盐道",
        "rep_name": "彙柴口古盐道",
        "lat": 29.34678, "lng": 104.76019,
    },
    {
        "suffix": 3,
        "name": "茶马古道-泸州段",
        "province": "四川省", "city": "泸州市", "district": "泸县",
        "address": "四川省泸州市泸县福集镇工矿社区光明古道",
        "rep_name": "光明古道",
        "lat": 29.12306, "lng": 105.40806,
    },
    {
        "suffix": 4,
        "name": "茶马古道-雅安段",
        "province": "四川省", "city": "雅安市", "district": "雨城区",
        "address": "四川省雅安市雨城区县前街106号观音阁",
        "rep_name": "观音阁",
        "lat": 29.990694, "lng": 102.990333,
    },
    {
        "suffix": 5,
        "name": "茶马古道-阿坝段",
        "province": "四川省", "city": "阿坝藏族羌族自治州", "district": "理县",
        "address": "四川省阿坝藏族羌族自治州理县甘堡乡百丈房古栈道",
        "rep_name": "百丈房古栈道",
        "lat": 31.46848, "lng": 103.17883,
    },
    {
        "suffix": 6,
        "name": "茶马古道-甘孜段",
        "province": "四川省", "city": "甘孜藏族自治州", "district": "泸定县",
        "address": "四川省甘孜藏族自治州泸定县兴隆镇化林坪茶马古道",
        "rep_name": "化林坪茶马古道",
        "lat": 29.715528, "lng": 102.304056,
    },
    {
        "suffix": 7,
        "name": "茶马古道-凉山段",
        "province": "四川省", "city": "凉山彝族自治州", "district": "甘洛县",
        "address": "四川省凉山彝族自治州甘洛县坪坝乡清溪峡古道",
        "rep_name": "甘洛清溪峡古道",
        "lat": 29.135278, "lng": 102.577083,
    },
    # --- 云南省 (10个) ---
    {
        "suffix": 8,
        "name": "茶马古道-大理段",
        "province": "云南省", "city": "大理白族自治州", "district": "祥云县",
        "address": "云南省大理白族自治州祥云县云南驿镇云南驿村",
        "rep_name": "云南驿茶马古道",
        "lat": 25.42480, "lng": 100.69050,
    },
    {
        "suffix": 9,
        "name": "茶马古道-普洱段",
        "province": "云南省", "city": "普洱市", "district": "思茅区",
        "address": "云南省普洱市思茅区思茅街道三家村社区斑鸠坡路段遗址",
        "rep_name": "斑鸠坡路段遗址",
        "lat": 22.83272, "lng": 100.99092,
    },
    {
        "suffix": 10,
        "name": "茶马古道-西双版纳段",
        "province": "云南省", "city": "西双版纳傣族自治州", "district": "勐腊县",
        "address": "云南省西双版纳傣族自治州勐腊县易武镇",
        "rep_name": "勐腊段",
        "lat": 22.05802, "lng": 101.48465,
    },
    {
        "suffix": 11,
        "name": "茶马古道-迪庆段",
        "province": "云南省", "city": "迪庆藏族自治州", "district": "德钦县",
        "address": "云南省迪庆藏族自治州德钦县升平镇阿墩子古城",
        "rep_name": "阿墩子段",
        "lat": 28.49045, "lng": 98.90955,
    },
    {
        "suffix": 12,
        "name": "茶马古道-临沧段",
        "province": "云南省", "city": "临沧市", "district": "凤庆县",
        "address": "云南省临沧市凤庆县鲁史镇金马村茶马古道鲁史段",
        "rep_name": "茶马古道鲁史段",
        "lat": 24.84339, "lng": 99.99771,
    },
    {
        "suffix": 13,
        "name": "茶马古道-怒江段",
        "province": "云南省", "city": "怒江傈僳族自治州", "district": "兰坪白族普米族自治县",
        "address": "云南省怒江傈僳族自治州兰坪白族普米族自治县金顶街道箐门村委会老姆井村",
        "rep_name": "兰坪段",
        "lat": 26.35926, "lng": 99.37622,
    },
    {
        "suffix": 14,
        "name": "茶马古道-保山段",
        "province": "云南省", "city": "保山市", "district": "隆阳区",
        "address": "云南省保山市隆阳区水寨乡水寨村老街子水寨铺古街道",
        "rep_name": "水寨铺古街道及马店",
        "lat": 25.26225, "lng": 99.33771,
    },
    {
        "suffix": 15,
        "name": "茶马古道-德宏段",
        "province": "云南省", "city": "德宏傣族景颇族自治州", "district": "陇川县",
        "address": "云南省德宏傣族景颇族自治州陇川县护国乡杉木笼村",
        "rep_name": "杉木笼山北坡古道",
        "lat": 24.53543, "lng": 98.09442,
    },
    {
        "suffix": 16,
        "name": "茶马古道-丽江段",
        "province": "云南省", "city": "丽江市", "district": "古城区",
        "address": "云南省丽江市古城区七河镇共和村委会西关村邱塘关茶马古道段",
        "rep_name": "邱塘关茶马古道段",
        "lat": 26.77876, "lng": 100.26344,
    },
    # --- 贵州省 (5个) ---
    {
        "suffix": 17,
        "name": "茶马古道-黔西南段",
        "province": "贵州省", "city": "黔西南布依族苗族自治州", "district": "普安县",
        "address": "贵州省黔西南布依族苗族自治州普安县罐子窑镇崧岿村松岿寺",
        "rep_name": "松岿寺",
        "lat": 25.88015, "lng": 104.96867,
    },
    {
        "suffix": 18,
        "name": "茶马古道-安顺段",
        "province": "贵州省", "city": "安顺市", "district": "关岭布依族苗族自治县",
        "address": "贵州省安顺市关岭布依族苗族自治县关索街道大关村关索岭古道",
        "rep_name": "关索岭古道",
        "lat": 25.94947, "lng": 105.62156,
    },
    {
        "suffix": 19,
        "name": "茶马古道-贵阳段",
        "province": "贵州省", "city": "贵阳市", "district": "白云区",
        "address": "贵州省贵阳市白云区都拉乡黑石头村长坡岭森林公园长坡岭古道",
        "rep_name": "长坡岭古道",
        "lat": 26.65705, "lng": 106.66649,
    },
    {
        "suffix": 20,
        "name": "茶马古道-六盘水段",
        "province": "贵州省", "city": "六盘水市", "district": "盘州市",
        "address": "贵州省六盘水市盘州市旧营乡茶厅村查厅古道",
        "rep_name": "查厅古道",
        "lat": 25.83175, "lng": 104.86375,
    },
    {
        "suffix": 21,
        "name": "茶马古道-毕节段",
        "province": "贵州省", "city": "毕节市", "district": "金沙县",
        "address": "贵州省毕节市金沙县鼓场街道罗马路133号义盛隆商号",
        "rep_name": "义盛隆商号",
        "lat": 27.45981, "lng": 106.21434,
    },
]


def main():
    parser = argparse.ArgumentParser(description="拆分茶马古道为地级市子记录")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写入")
    args = parser.parse_args()

    with open(MAIN_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Find the original record
    idx = next(i for i, r in enumerate(data) if r["release_id"] == PARENT_ID)
    original = data[idx]

    print(f"原记录: {original['name']} ({PARENT_ID})")
    print(f"  地址: {original['address']}")
    print(f"  坐标: ({original['latitude']}, {original['longitude']})")

    # Check if already split
    existing_children = [r for r in data if r.get("_parent_release_id") == PARENT_ID]
    if existing_children:
        print(f"\n已有 {len(existing_children)} 个子记录，跳过")
        return

    # Convert original to parent record
    original["_is_parent"] = True
    # Parent coords will be updated to centroid after children are added

    # Shared fields from parent
    shared = {
        "era": original["era"],
        "category": original["category"],
        "batch": original["batch"],
        "batch_year": original["batch_year"],
        "wikipedia_url": original.get("wikipedia_url"),
        "description": original.get("description"),
        "image_url": original.get("image_url"),
    }

    # Create child records
    new_records = []
    lat_sum = 0.0
    lng_sum = 0.0

    print(f"\n创建 {len(CHILDREN)} 个子记录:")
    for child in CHILDREN:
        rid = f"{PARENT_ID}-{child['suffix']}"
        rec = {
            "name": child["name"],
            **shared,
            "release_id": rid,
            "release_address": original["release_address"],
            "province": child["province"],
            "city": child["city"],
            "district": child["district"],
            "address": child["address"],
            "latitude": child["lat"],
            "longitude": child["lng"],
            "_geocode_method": "wikipedia_coords",
            "_parent_release_id": PARENT_ID,
        }
        new_records.append(rec)
        lat_sum += child["lat"]
        lng_sum += child["lng"]
        print(f"  {rid}: {child['name']} ({child['lat']}, {child['lng']})")

    # Update parent centroid
    n = len(CHILDREN)
    original["latitude"] = round(lat_sum / n, 6)
    original["longitude"] = round(lng_sum / n, 6)
    original["_geocode_method"] = "centroid"
    # Clear old bad address/city/district
    original["address"] = "四川省、云南省、贵州省"
    original["city"] = ""
    original["district"] = ""
    print(f"\n父记录质心坐标: ({original['latitude']}, {original['longitude']})")

    if args.dry_run:
        print(f"\n[dry-run] 预览完成，未写入")
        return

    # Insert children right after parent
    for i, rec in enumerate(new_records):
        data.insert(idx + 1 + i, rec)

    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n已写入: 1 个父记录 + {len(new_records)} 个子记录 (总记录数: {len(data)})")


if __name__ == "__main__":
    main()
