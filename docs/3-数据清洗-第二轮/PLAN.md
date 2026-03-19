# 数据清洗第二轮 - 实现方案

## 背景

本轮清洗解决两个问题：

1. **中文乱码**：数据中存在生僻字，部分在原始通知里就已是乱码（字符编码问题）
2. **经纬度精度**：现有地理编码使用 `release_address`（地址只精确到县市级），导致大量坐标落在政府大楼位置，而非文保单位实际位置。应改用 `name` 字段做 POI 模糊搜索。

---

## 问题一：中文乱码排查

### 发现情况

通过扫描 Unicode 代码点，发现以下 8 条可疑记录（含 CJK Extension A/B/C 等超出常用范围的字符）：

| release_id | 当前 name | 可疑字符 | 地址 |
|---|---|---|---|
| 4-137 | 䌽衣堂 | 䌽 (U+433D, CJK-A) | 江苏省常熟市 |
| 4-218 | 𥒚州灯塔 | 𥒚 (U+2549A, CJK-B) | 广东省湛江市 |
| 6-188 | 巄 𭖂 图山城址 | 𭖂 (U+2D582, CJK-C) + 空格 | 云南省巍山彝族回族自治县 |
| 7-210 | 𰻮 阳城遗址 | 𰻮 (U+30EEE, CJK-F) + 空格 | 江西省九江市都昌县 |
| 7-576 | 赵孟𫖯墓 | 𫖯 (U+2B5AF, CJK-B) | 浙江省湖州市德清县 |
| 7-1012 | 㹧 𱮒 湖避塘 | 㹧 (U+3E67) + 𱮒 (U+31B92) + 空格 | 浙江省绍兴市绍兴县 |
| 7-1895 | 尚稽陈玉𤩱祠 | 𤩱 (U+24A71, CJK-B) | 贵州省遵义市遵义县 |
| 8-418 | 石 𱵄 村冯氏祠堂 | 𱵄 (U+31D44) + 空格 | 海南省澄迈县 |

**注意**：名字中有空格的（6-188、7-210、7-1012、8-418）极有可能是乱码，因为正常中文名称不包含空格。其余几条使用的生僻字可能是正确的（如赵孟頫名字里的生僻字）。

### 实现方案

**脚本**：`scripts/find_encoding_issues.py`

- 扫描 `data/heritage_sites_geocoded.json`
- 输出 `data/encoding_issues.json`（含可疑记录详情 + 正确名称建议）
- 按问题严重程度排序（有空格的优先）

**人工修复**：由用户对照国务院原始通知逐条核查后，直接编辑 `data/heritage_sites_geocoded.json` 中对应条目的 `name` 字段。

---

## 问题二：按名称重新地理编码

### 问题分析

现有 `geocode_amap.py` 以 `release_address` 为主要输入，该字段仅精确到县/市，高德地理编码会将坐标落在行政区中心（通常是政府大楼）。

### 新策略

改用 **高德 POI 关键词搜索**（`/v3/place/text`）以 `name` 字段为主要搜索词，`release_address` 仅用于缩小搜索范围（city hint），从而获得更精确的文保单位坐标。

| 步骤 | 方法 | 说明 |
|---|---|---|
| 1 | POI 搜索（按名称） | `keywords=name`, `city=省/市` |
| 2 | 名称相似度校验 | difflib ≥ 0.5（比原来 0.4 更严格） |
| 3 | fallback：地理编码（按地址） | 仅在 POI 搜索失败时使用 release_address |
| 4 | 最终 fallback：不更新 | 两种方式都失败时，保留原坐标 |

### 全量刷新原则

- **全部 5060 条**重新走 POI 搜索，不跳过已有坐标的记录（因旧坐标普遍不准）
- 只有两种方法都失败时，才保留原始坐标（即结果可能退化）
- 新增字段 `_geocode_method`（`poi_search` / `geocode` / `kept_original`）用于追踪

### 实现

**脚本**：`scripts/regeocode_by_name.py`

```
用法:
  uv run python regeocode_by_name.py          # 全量处理
  uv run python regeocode_by_name.py --test   # 仅测试前 5 条
  uv run python regeocode_by_name.py --limit 100  # 只处理前 N 条（调试用）
```

- 输入：`data/heritage_sites_geocoded.json`（或 `--input` 指定）
- 输出：`data/heritage_sites_geocoded.json`（原地覆盖）
- 断点续传：`data/regeocode_checkpoint.json`（记录已处理 release_id 集合）
- 每 50 条保存一次
- 请求间隔 200ms（保守 5 QPS）

---

## 执行顺序

```bash
cd scripts

# Step 1: 生成乱码清单（供用户核查）
uv run python find_encoding_issues.py

# Step 2: 用户手动修复 data/encoding_issues.json 列出的条目
# （直接编辑 data/heritage_sites_geocoded.json）

# Step 3: 按名称重新地理编码（运行时间较长，约 30 分钟）
uv run python regeocode_by_name.py

# Step 4: 导入数据库
uv run python seed_supabase.py --clear
```

---

## 关键文件

| 文件 | 说明 |
|---|---|
| `scripts/find_encoding_issues.py` | 扫描并输出乱码可疑条目清单 |
| `scripts/regeocode_by_name.py` | 按名称 POI 搜索刷新全部坐标 |
| `data/encoding_issues.json` | 乱码条目列表（供用户人工核查） |
| `data/heritage_sites_geocoded.json` | 最终数据文件（人工修复 + 重新编码后的结果） |
| `data/regeocode_checkpoint.json` | 断点记录（中断后可续跑） |
