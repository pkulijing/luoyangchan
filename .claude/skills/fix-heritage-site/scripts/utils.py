"""
共享工具函数
"""

import hashlib
import os
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent.parent

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
    frozenset(["四川省", "重庆市"]),
    frozenset(["河北省", "天津市"]),
    frozenset(["河北省", "北京市"]),
    frozenset(["江苏省", "上海市"]),
    frozenset(["广东省", "海南省"]),
    frozenset(["四川省", "西藏自治区"]),
}

# 地址前缀特殊映射（历史名称、缩写等）
ADDRESS_PREFIX_MAP = [
    ("广西僮族自治区", "广西壮族自治区"),
    ("新疆维吾尔自区", "新疆维吾尔自治区"),
    ("新疆生产建设兵团", "新疆维吾尔自治区"),
]


def load_env_key(name: str) -> str | None:
    """从环境变量或 .env.local 加载配置。"""
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


def extract_expected_province(release_address: str) -> str | None:
    """从 release_address 中提取预期省份。"""
    if not release_address:
        return None
    for p in ALL_PROVINCES:
        if release_address.startswith(p):
            return p
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
    """判断省份是否匹配（允许已知的行政区划变更）。"""
    if not expected or not actual:
        return True
    expected = normalize_province(expected)
    actual = normalize_province(actual)
    if expected == actual:
        return True
    return frozenset([expected, actual]) in ADMIN_BOUNDARY_OK


def compute_tencent_sig(path: str, params: dict, sk: str) -> str:
    """计算腾讯地图 API 签名。"""
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    sig_raw = f"{path}?{query_string}{sk}"
    return hashlib.md5(sig_raw.encode("utf-8")).hexdigest()
