# 第三轮数据清洗实现计划

## 问题规模（分析阶段确认）

| 问题类型 | 数量 | 说明 |
|----------|------|------|
| 低精度坐标（geocode fallback） | 1015 条 | 区县中心精度 |
| POI 省份不匹配 | 待分析确认 | 高德搜到同名但不同省的 POI |
| 重复坐标组 | 276 组（643 条） | 大部分由 geocode fallback 造成 |
| 多地址候选（待拆分） | ~56 条（含误判） | 实际需拆分预计 20-30 条 |

## 约束

- 高德 API 配额已耗尽，本轮全部使用**腾讯地图 Web 服务 API**（GCJ-02，与现有数据坐标系一致）
- 环境变量 `TENCENT_MAP_KEY`
- Gemini 一次性处理全量数据（传 JSON 附件），无需分批

## 整体工作流

```
Phase 0: 分析诊断
Phase 1: 多地址拆分（Gemini 判断 → 脚本执行）
Phase 2: 腾讯地图批量 geocoding（Gemini 优化搜索词 → 腾讯 API）
Phase 3: 验证 + 残余人工修复
Phase 4: 更新 fallback 列表 + 重新 seed 数据库
```

---

## Phase 0: 数据问题全面诊断

### `scripts/analyze_data_quality.py`

**输入**：`data/heritage_sites_geocoded.json`
**输出目录**：`data/round3/`

| 产出文件 | 内容 |
|----------|------|
| `needs_regeocode.json` | 需要重新编码的记录，含 `problem_type`（`geocode_fallback` / `poi_province_mismatch` / `poi_duplicate`） |
| `multi_address_candidates.json` | 多地址候选，含 `confidence`（`strong` / `borderline`）和解析出的地点列表 |
| `duplicate_coord_groups.json` | 276 组重复坐标，含成员和 geocode method 分布 |
| `quality_summary.txt` | 汇总统计 |

**省份不匹配检测逻辑**：
- 从 `release_address` 提取预期省份（正则匹配第一个省级地名）
- 与记录中的 `province` 字段对比
- 排除已知行政区划变更：四川↔重庆、河北↔天津/北京、江苏↔上海等

**多地址候选检测逻辑**（避免"中山西路"误判为"山西省"）：
- 对 `release_address` 按 `、` 分割
- 每段必须以地名后缀结尾（省/自治区/市/县/区/旗/盟）才算独立地点
- 短段（≤3字）不算独立地点（如"西、南、中沙群岛"）
- 分类：多省份 → `strong`；同省 ≥3 县 → `strong`；其余 → `borderline`

---

## Phase 1: 多地址条目拆分

### Step 1.1: 生成 Gemini prompt

**`scripts/generate_gemini_prompt_multi_address.py`**

- 读取 `multi_address_candidates.json`
- 输出 `data/round3/gemini_prompt_multi_address.md` 和附件 `data/round3/gemini_multi_address_input.json`
- prompt 指导 Gemini 判断是否需要拆分，并提供子条目信息

**Gemini 输出格式**（保存到 `data/round3/gemini_multi_address_result.json`）：
```json
[
  {
    "release_id": "5-184",
    "needs_splitting": true,
    "reason": "该单位包含18座帝陵，分布在6个县",
    "children": [
      {
        "name": "唐代帝陵-唐献陵",
        "address_for_geocoding": "陕西省渭南市富平县吕村镇",
        "province": "陕西省",
        "city": "渭南市",
        "district": "富平县"
      }
    ]
  }
]
```

### Step 1.2: 执行拆分

**`scripts/apply_multi_address_split.py`**

- 读取 `gemini_multi_address_result.json`
- 对 `needs_splitting == true` 的条目：
  - 原记录 → 父记录（`_is_parent: true`，坐标清空）
  - 生成子记录（`_parent_release_id` 指向父，`release_id` 格式 `{parent_id}-{i}`）
  - 子记录暂无坐标，等待 Phase 2
- `--dry-run` 预览（默认），`--apply` 写入
- `--apply` 前自动备份到 `data/round3/backup/heritage_sites_geocoded_{timestamp}.json`

---

## Phase 2: 腾讯地图批量 geocoding

### Step 2.1: 生成 Gemini geocoding prompt（一次性，不分批）

**`scripts/generate_gemini_prompt_geocode.py`**

- 读取 `needs_regeocode.json` + Phase 1 新增的无坐标子记录
- 输出：
  - `data/round3/gemini_prompt_geocode.md` — prompt 正文（指导 Gemini 任务）
  - `data/round3/gemini_geocode_input.json` — 附件（全量问题记录，传给 Gemini）
- Gemini 一次处理全部记录，返回每条记录的推荐搜索词和精确地址

**Gemini 输出格式**（保存到 `data/round3/gemini_geocode_result.json`）：
```json
[
  {
    "release_id": "1-4",
    "poi_keywords": ["韶山毛泽东故居", "韶山冲毛主席旧居"],
    "city_hint": "湘潭市",
    "precise_address": "湖南省湘潭市韶山市韶山冲上屋场"
  }
]
```

### Step 2.2: 腾讯地图 geocoding 核心脚本

**`scripts/geocode_tencent.py`**

**API 端点**：
- POI 搜索：`https://apis.map.qq.com/ws/place/v1/search`
- 地址编码：`https://apis.map.qq.com/ws/geocoder/v1/`

**搜索策略**（每条记录依次尝试，直到命中）：
1. Gemini 推荐关键词 + 城市限定 POI 搜索（如有 hints）
2. 原始 name + city hint POI 搜索
3. Gemini 的 precise_address 地址编码（如有）
4. release_address 地址编码（最终 fallback）

**核心改进——省份验证**：
- 每次 geocoding 后，验证结果省份 vs 预期省份
- 不匹配则拒绝，尝试下一策略
- 这是比 Round 2 最关键的改进，防止跨省 POI 错匹配

**实现细节**：
- 速率：0.2s/请求（5 QPS，远低于 10,000/天限额）
- checkpoint：每 50 条保存到 `data/round3/tencent_checkpoint.json`
- difflib 相似度阈值：0.5（Gemini 推荐词）/ 0.5（原始名）
- 新 `_geocode_method` 值：`tencent_poi_gemini` / `tencent_poi` / `tencent_geocode`
- CLI 选项：`--test`（前 5 条）、`--limit N`、`--resume`

---

## Phase 3: 验证与残余修复

### Step 3.1: 验证

**`scripts/verify_round3.py`**

- 省份不匹配重新扫描（应接近 0）
- 重复坐标重新扫描（应大幅减少）
- geocode method 分布前后对比
- 父子关系一致性检查
- 输出 `data/round3/verification_report.json` + `data/round3/still_problematic.json`

### Step 3.2: 人工修正入口

**`scripts/apply_manual_corrections.py`**

- 读取 `data/round3/manual_corrections.json`
- 格式：`[{"release_id": "...", "latitude": ..., "longitude": ..., "province": ..., "_geocode_method": "manual"}]`
- `--dry-run` / `--apply`

---

## Phase 4: 收尾

1. **`scripts/update_fallback_list.py`** — 重新生成 `data/geocode_fallback_list.json`（记录所有仍为低精度的条目）
2. **`seed_supabase.py`**（无需修改）— 重新入库，已支持父子记录

---

## 新增文件

```
scripts/
  analyze_data_quality.py          # Phase 0
  generate_gemini_prompt_multi_address.py  # Phase 1.1
  apply_multi_address_split.py     # Phase 1.2
  generate_gemini_prompt_geocode.py  # Phase 2.1
  geocode_tencent.py               # Phase 2.2
  verify_round3.py                 # Phase 3.1
  apply_manual_corrections.py      # Phase 3.2
  update_fallback_list.py          # Phase 4

data/round3/           # 中间产物（加入 .gitignore）
  gemini_prompt_multi_address.md
  gemini_multi_address_input.json
  gemini_multi_address_result.json   # 用户填写
  needs_regeocode.json
  gemini_prompt_geocode.md
  gemini_geocode_input.json
  gemini_geocode_result.json         # 用户填写
  tencent_checkpoint.json
  verification_report.json
  still_problematic.json
  manual_corrections.json            # 用户填写（如有）
  backup/                            # 自动备份

docs/7-数据清洗-第三轮/
  PROMPT.md  PLAN.md  SUMMARY.md
```

**修改文件**：
- `.env.example` — 新增 `TENCENT_MAP_KEY`
- `data/heritage_sites_geocoded.json` — 最终更新
- `data/geocode_fallback_list.json` — 重新生成

## 参考实现

- `scripts/regeocode_by_name.py` — geocode_tencent.py 的架构参考（checkpoint/resume、difflib、city hint）
- `scripts/apply_name_corrections.py` — dry-run/apply 模式参考

## 执行节奏

| 阶段 | 人类操作 | Agent 操作 |
|------|---------|-----------|
| Phase 0 | 无 | 写脚本 → 运行分析 |
| Phase 1 | 跑 Gemini（1次，传 multi_address_input.json） | 写脚本 → 执行拆分 |
| Phase 2 | 注册腾讯 API Key，TENCENT_MAP_KEY 写入 .env.local；跑 Gemini（1次，传 geocode_input.json） | 写脚本 → 运行 geocoding |
| Phase 3 | 跑 Gemini（少量）/ 人工校正 | 写脚本 → 运行验证 |
| Phase 4 | 无 | 更新列表 → 重新 seed |
