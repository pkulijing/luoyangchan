"""
共享工具函数：省份提取与验证

供 analyze_data_quality.py、generate_gemini_prompt_geocode.py、
geocode_tencent.py、verify_round3.py 共同使用。
"""

ALL_PROVINCES = [
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省",
    "山东省", "河南省", "湖北省", "湖南省", "广东省",
    "广西壮族自治区", "海南省", "四川省", "贵州省", "云南省",
    "西藏自治区", "陕西省", "甘肃省", "青海省",
    "宁夏回族自治区", "新疆维吾尔自治区", "内蒙古自治区",
    "台湾省", "香港特别行政区", "澳门特别行政区",
]

# 已知行政区划变更（允许两侧省份视为匹配）
ADMIN_BOUNDARY_OK = {
    frozenset(["四川省", "重庆市"]),      # 1997 重庆直辖
    frozenset(["河北省", "天津市"]),
    frozenset(["河北省", "北京市"]),
    frozenset(["江苏省", "上海市"]),
    frozenset(["广东省", "海南省"]),      # 1988 海南建省
    frozenset(["四川省", "西藏自治区"]),
}

# 地址前缀特殊映射（历史名称、缩写、特殊行政单位等）
# key: release_address 前缀，value: 对应的标准省份名
ADDRESS_PREFIX_MAP = [
    ("广西僮族自治区", "广西壮族自治区"),       # 历史旧名（1965年前）
    ("新疆维吾尔自区", "新疆维吾尔自治区"),     # 数据录入缺字（5-191）
    ("新疆生产建设兵团", "新疆维吾尔自治区"),   # 兵团地址格式
]


def extract_expected_province(release_address: str) -> str | None:
    """
    从 release_address 中提取预期省份。

    优先级：
    1. 精确前缀匹配（完整省份名）
    2. 特殊前缀映射（历史名、缩写、特殊单位）
    3. 返回 None（无法判断，不报错）
    """
    if not release_address:
        return None
    # 优先：完整省份名匹配
    for p in ALL_PROVINCES:
        if release_address.startswith(p):
            return p
    # 特殊前缀映射
    for prefix, province in ADDRESS_PREFIX_MAP:
        if release_address.startswith(prefix):
            return province
    return None


def normalize_province(province: str | None) -> str | None:
    """规范化省份名（处理历史名称变更）。"""
    if not province:
        return None
    ALIASES = {"广西僮族自治区": "广西壮族自治区"}
    return ALIASES.get(province, province)


def is_province_ok(expected: str | None, actual: str | None) -> bool:
    """
    判断省份是否匹配（允许已知的行政区划变更）。
    expected/actual 均为 None 时返回 True（无法判断，不报错）。
    """
    if not expected or not actual:
        return True
    expected = normalize_province(expected)
    actual = normalize_province(actual)
    if expected == actual:
        return True
    return frozenset([expected, actual]) in ADMIN_BOUNDARY_OK
