---
name: fix-heritage-site
description: 修复单个文保单位的地址和坐标数据。支持从百度百科、百度搜索或用户提供的额外信息中提取地址，通过 DeepSeek 合成精确地址，使用高德/腾讯地图 geocoding 获取坐标，保存到 JSON 并刷新 Supabase 数据库。
metadata: { "openclaw": { "emoji": "🔧", "requires": { "bins": ["python3", "uv"] } } }
---

# 文保单位数据修复 Skill

修复单个文保单位的地址和坐标数据。

## 使用场景

1. **修复坐标**: 当用户发现某个文保单位的地址或坐标有误时
2. **多地址拆分**: 当一个文保单位有多个地点（如茶马古道），需要拆分成父记录 + 多个子记录

## 工作流程

### 步骤 1: 确定待修复条目

根据用户的自然语言描述，从 JSON 数据中搜索并确定唯一的待修复条目。

**搜索方式**:
- 按 `release_id` 精确匹配（如 "7-817", "6-478"）
- 按 `name` 模糊搜索
- 按省份+名称组合搜索

**确认信息**（展示给用户确认）:
- release_id
- name
- province / city / district
- 当前 address
- 当前坐标 (latitude, longitude)
- _geocode_method

```bash
cd /home/jing/Developer/luoyangchan/skills/fix-heritage-site/scripts

# 按 release_id 精确搜索
uv run python search.py --id 7-817

# 按名称模糊搜索
uv run python search.py --name "某遗址"

# 按省份+名称组合搜索
uv run python search.py --province 山西 --name "某"

# 显示详细信息
uv run python search.py --id 7-817 --verbose
```

### 步骤 2: 收集信息

根据用户意图选择数据源。优先级：**用户提供的信息 > 百度百科 > 百度搜索**

#### 场景 A: 用户未提供额外信息

直接使用 fix.py 自动查询百度百科或搜索：
```bash
uv run python fix.py <release_id> --source baike   # 百度百科（默认）
uv run python fix.py <release_id> --source search  # 百度搜索
```

#### 场景 B: 用户提供了额外信息

**B1. 用户提供 URL**:
- 使用 WebFetch 工具获取页面内容
- 提取位置相关信息后，使用 `--context` 参数传入

**B2. 用户提供文本**:
```bash
uv run python fix.py <release_id> --context "该遗址位于山西省运城市绛县陈村镇"
```

**B3. 用户直接给出地址**:
```bash
uv run python fix.py <release_id> --address "山西省运城市绛县陈村镇东荆下村"
```

### 步骤 3: DeepSeek 地址合成

fix.py 会自动调用 DeepSeek API 分析收集到的信息，合成精确地址。

**输出格式**:
```json
{
  "address_for_geocoding": "省+市+区县+乡镇/街道+村/具体位置",
  "poi_name": "用于搜索的关键词",
  "notes": "地址来源说明",
  "improved": true
}
```

### 步骤 4: Geocoding

使用高德或腾讯地图 API 将地址转换为坐标。**优先使用高德**，高德失败自动 fallback 到腾讯。

**省份验证**: 结果省份必须与预期省份匹配，否则拒绝。

**坐标系说明**:
- 高德和腾讯都返回 **GCJ-02** 坐标
- 直接存入 JSON，**不做任何坐标转换**
- 前端展示时再转换为 WGS-84

### 步骤 5: 保存到 JSON

更新 `data/heritage_sites_geocoded.json` 中对应记录的字段:
- province, city, district
- address
- latitude, longitude
- _geocode_method（标记为 `amap_geocode_deepseek_baike` 等）
- _geocode_reliability（腾讯）或 _geocode_level（高德）

### 步骤 6: 同步到 Supabase

**增量同步**（推荐，只更新修改的记录）：
```bash
uv run python sync.py 7-703
uv run python sync.py 7-703 7-817 6-478  # 多条
```

**全量重导**（清空后重新导入所有记录）：
```bash
cd /home/jing/Developer/luoyangchan/scripts
uv run python db/seed_supabase.py --clear
```

---

## 多地址拆分流程

当一个文保单位有多个地点时（如茶马古道、长城等），需要拆分成父记录 + 多个子记录。

### 拆分步骤

1. **确定需要拆分的记录**（同步骤 1）

2. **收集子条目信息**: 通过百度百科、搜索或用户提供的信息，确定各个子地点

3. **执行拆分**:
```bash
uv run python split.py <release_id> --children '[
  {"name": "xxx遗址（A点）", "province": "山西省", "city": "运城市", "address": "详细地址"},
  {"name": "xxx遗址（B点）", "province": "山西省", "city": "太原市", "address": "详细地址"}
]'
```

4. **为每个子记录执行 geocoding**:
```bash
uv run python fix.py <release_id>-1
uv run python fix.py <release_id>-2
# ...
```

5. **刷新 Supabase**

### 拆分后的数据结构

```
原记录 7-1234 → 父记录 7-1234 (_is_parent: true, 无坐标)
              → 子记录 7-1234-1 (_parent_release_id: "7-1234")
              → 子记录 7-1234-2 (_parent_release_id: "7-1234")
```

### 子条目 JSON 格式

```json
{
  "name": "必填，子条目名称",
  "province": "必填，省份",
  "city": "必填，城市",
  "district": "可选，区县",
  "address": "可选，详细地址（用于后续 geocoding）"
}
```

---

## 完整命令参考

所有命令在 `skills/fix-heritage-site/scripts` 目录下执行：

```bash
cd /home/jing/Developer/luoyangchan/skills/fix-heritage-site/scripts

# 搜索
uv run python search.py --id 7-817
uv run python search.py --name "长春观" --verbose

# 默认：百度百科 + 高德
uv run python fix.py 7-817

# 百度搜索 + 高德
uv run python fix.py 7-817 --source search

# 使用腾讯 geocoding
uv run python fix.py 7-817 --geocoder tencent

# 直接指定地址（跳过数据源和 DeepSeek）
uv run python fix.py 7-817 --address "山西省运城市绛县陈村镇东荆下村"

# 使用用户提供的上下文
uv run python fix.py 7-817 --context "该遗址位于山西省运城市绛县陈村镇"

# 只查询不写入
uv run python fix.py 7-817 --dry-run

# 批量修复（仅自动模式）
uv run python fix.py 7-817 6-478 8-594

# 多地址拆分
uv run python split.py 7-1234 --children '[
  {"name": "A点", "province": "山西省", "city": "运城市"},
  {"name": "B点", "province": "山西省", "city": "太原市"}
]'
uv run python split.py 7-1234 --children '[...]' --dry-run

# 增量同步到 Supabase（推荐）
uv run python sync.py 7-703
uv run python sync.py 7-703 7-817 6-478  # 多条
uv run python sync.py 7-703 --dry-run
```

## 环境变量

需要在 `.env.local` 中配置:
- `BAIDU_API_KEY` - 百度百科和搜索 API
- `DEEPSEEK_API_KEY` - DeepSeek API
- `AMAP_GEOCODING_KEY` - 高德 Web 服务 API
- `TENCENT_MAP_KEY` - 腾讯地图 API（备用）

## 文件结构

```
skills/fix-heritage-site/
├── _meta.json
├── SKILL.md
└── scripts/
    ├── utils.py    # 工具函数（省份验证、环境变量加载等）
    ├── search.py   # 搜索文保单位
    ├── fix.py      # 主修复脚本
    ├── split.py    # 多地址拆分脚本
    └── sync.py     # 增量同步到 Supabase
```

## 数据文件位置

- 主数据文件: `data/heritage_sites_geocoded.json`

## 注意事项

1. **坐标系**: 数据库统一存储 GCJ-02 坐标，绝对禁止在 Python 脚本中做坐标转换
2. **省份验证**: geocoding 结果省份必须与预期省份匹配
3. **确认**: 修复前务必让用户确认待修复的条目是正确的
