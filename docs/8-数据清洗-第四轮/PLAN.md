# 第四轮数据清洗实现计划

## 任务列表与执行顺序

```
Task A: _geocode_method 标签规范化        ──┐
Task B: 父记录坐标填充（子记录质心）        ──┤── 简单修复，先行
Task C: 百度百科补全低精度记录              ──┤── 核心任务
Task D: 地址字符串规范化（补全行政层级）     ──┘── 新增需求
Task E: 全量排查 - 模糊地址               ──┐── 审计（只读）
Task F: 全量排查 - 重复GPS坐标            ──┘── 审计（只读）
```

A/B 无依赖可并行 → C（修改坐标）→ D（修改地址字符串）→ E/F（只读审计，输出报告供人类决策）

## Task A: `_geocode_method` 标签规范化

**脚本**: `scripts/round4/fix_geocode_method_label.py`

将 `heritage_sites_geocoded.json` 中所有 `_geocode_method == "tencent_geocode_gemini"` 替换为 `"tencent_geocode_deepseek"`。纯 JSON 读写，无 API 调用。

## Task B: 父记录坐标填充

**脚本**: `scripts/round4/fill_parent_centroids.py`

- 找到所有 `_is_parent: true` 的记录（26条）
- 通过 `_parent_release_id` 找到其子记录
- 计算子记录 lat/lng 的算术平均值作为父记录坐标
- 设 `_geocode_method` 为 `"centroid"`

## Task C: 百度百科补全低精度记录

**脚本**: `scripts/round4/baike_address_refine.py`

分4步执行，支持 `--step` 参数分步运行：

### Step 1: 识别低精度记录
- 扫描 `data/round3/geocode_batches/result_*.json`
- 标记 notes 含"未能"/"未找到"/"县级"等关键词，或地址长度 ≤12 字符的记录
- 与主数据文件交叉对比，仅保留当前仍为低精度的记录
- 输出 `data/round4/low_precision_records.json`

### Step 2: 百度百科查询
- 用 `skills/baidu-baike/scripts/baidu_baike.py` 的 `BaiduBaikeClient` 查询每条记录
- 提取 `card` 中的 `地理位置`/`位置`/`所在地` 等属性
- 输出 `data/round4/baike_results.json`

### Step 3: DeepSeek 地址合成
- 将百科数据喂给 DeepSeek，生成精确到乡镇/村级的地址
- 无百科结果的 fallback 到 DuckDuckGo 搜索
- 复用 `deepseek_geocode.py` 的 tool-calling 模式
- 输出 `data/round4/refined_addresses.json`

### Step 4: 腾讯地图 geocoding
- 复用 `geocode_tencent.py` 的 `geocode_by_address()` + 省份验证
- 设 `_geocode_method` 为 `"tencent_geocode_deepseek_baike"`
- 写回 `heritage_sites_geocoded.json`

**关键复用**:
- `scripts/round3/geocode_tencent.py` → `geocode_by_address()`, `compute_sig()`
- `scripts/round3/geocode_utils.py` → `extract_expected_province()`, `is_province_ok()`
- `skills/baidu-baike/scripts/baidu_baike.py` → `BaiduBaikeClient`

## Task D: 地址字符串规范化

**脚本**: `scripts/round4/normalize_address.py`

**问题**: 很多 `address` 字段缺少中间行政层级，如"山东省滕州市官桥镇北辛村"缺"枣庄市"。但 `province`/`city`/`district` 结构化字段已有 99.98% 的填充率。

**方案**: 纯规则匹配，不需要大模型或 API 调用：
1. 构建标准前缀: `{province}{city}{district}`
2. 从原 `address` 中去掉已有的行政层级前缀（省/市/区/县/自治州等）
3. 将标准前缀 + 剩余地址细节拼接为新地址
4. 特殊处理：
   - 直辖市（北京/上海/天津/重庆）：省级和市级同名，不重复
   - `city` 和 `district` 可能相同（如县级市），避免重复
   - 保留原地址中标准前缀之后的细节部分（街道/乡镇/村/门牌号等）

## Task E: 全量排查 - 模糊地址

**脚本**: `scripts/round4/audit_vague_addresses.py`

**检测标准**:
- `address` 为空或只到县/区级（无乡镇/街道/村级细节）
- `_geocode_method` 为 `"geocode"` 或 `"kept_original"`（已知低精度）
- `_geocode_reliability` < 5

**输出**:
- `data/round4/audit_vague_addresses.json` — 按省份排序的问题记录
- `data/round4/audit_vague_addresses_summary.md` — 汇总报告

## Task F: 全量排查 - 重复GPS坐标

**脚本**: `scripts/round4/audit_duplicate_coords.py`

**检测**: 按 `(latitude, longitude)` 分组（6位小数精度），排除父记录，标记 ≥2 条的组。

**输出**:
- `data/round4/audit_duplicate_coords.json` — 重复组详情
- `data/round4/audit_duplicate_coords_summary.md` — 汇总

## 文件结构

```
scripts/round4/
  fix_geocode_method_label.py    # Task A
  fill_parent_centroids.py       # Task B
  baike_address_refine.py        # Task C
  normalize_address.py           # Task D
  audit_vague_addresses.py       # Task E
  audit_duplicate_coords.py      # Task F

data/round4/                     # 中间产物和审计输出

docs/8-数据清洗-第四轮/
  PROMPT.md
  PLAN.md
  SUMMARY.md
```

## 验证方式

1. Task A: `grep -c "tencent_geocode_gemini" data/heritage_sites_geocoded.json` 应为 0
2. Task B: 检查所有 `_is_parent: true` 记录的 lat/lng 不为 null
3. Task C: 对比修改前后低精度记录数量下降
4. Task D: 抽查 10 条地址确认格式为 `{省}{市}{区/县}{细节}`
5. Task E/F: 审计报告生成后由人类审阅决定后续动作
