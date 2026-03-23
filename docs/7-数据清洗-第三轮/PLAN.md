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

### Step 2.1: LLM 生成精确地址（Claude Code Agent 批处理）

原计划用 Gemini 一次性处理 1712 条，因数据量过大放弃。改为 Claude Code 内用 Agent 子代理 + WebSearch 批量处理。

**辅助脚本**：`scripts/round3/batch_geocode_helper.py`（split / merge / status / validate）

**批次文件**：
- 输入：`data/round3/geocode_batches/batch_001.json` ~ `batch_018.json`（每批 100 条，最后一批 12 条）
- 结果：`data/round3/geocode_batches/result_001.json` ~ `result_018.json`

**结果格式**：
```json
[
  {
    "release_id": "1-4",
    "address_for_geocoding": "湖南省湘潭市韶山市韶山冲",
    "poi_name": "毛泽东同志故居",
    "notes": null
  }
]
```

**当前进度**：batch_001–011 完成（1100 条），012–018 待处理。详见 `GEOCODE_PROGRESS.md`。

### Step 2.2: 腾讯地图 geocoding 核心脚本

**`scripts/round3/geocode_tencent.py`**

**API 端点**：
- 地址编码：`https://apis.map.qq.com/ws/geocoder/v1/`（配额充足，10,000/天）
- POI 搜索：`https://apis.map.qq.com/ws/place/v1/search`（配额紧张，200/天）

**搜索策略**（优先级从高到低）：
1. LLM 精确地址 → 腾讯地理编码（主策略，高配额）
2. 腾讯 POI 搜索（配额有限，仅在 1 失败时使用）
3. 原始 release_address → 腾讯地理编码（最终 fallback）

**核心改进——省份验证**：
- 每次 geocoding 后，验证结果省份 vs 预期省份
- 不匹配则拒绝，尝试下一策略
- 这是比 Round 2 最关键的改进，防止跨省 POI 错匹配

**实现细节**：
- 速率：0.25s/请求（4 QPS）
- checkpoint：每 50 条保存
- POI 搜索日配额管理：跟踪今日已用次数，超额则自动跳过
- difflib 相似度阈值：0.4
- 新 `_geocode_method` 值：`tencent_geocode_gemini` / `tencent_poi_gemini` / `tencent_poi` / `tencent_geocode`
- CLI 选项：`--test`（前 5 条）、`--limit N`、`--resume`、**`--batch N`（仅处理指定批次）**

### Step 2.2 试点：batch_001 先行验证

在全量处理前，先用 batch_001 的 100 条记录跑通整个 pipeline，验证：
- 腾讯地图 API 的命中率和精度
- 省份验证逻辑是否正常
- LLM 提供的 address_for_geocoding 质量
- POI 搜索配额消耗情况

```bash
# 试点运行（仅 batch_001 的 100 条）
cd scripts/round3
uv run python geocode_tencent.py --batch 1 --test   # 先测 5 条
uv run python geocode_tencent.py --batch 1           # 跑全部 100 条
```

`--batch N` 模式：
- 从 `geocode_batches/batch_N.json` 读取目标 release_id 列表
- 从 `geocode_batches/result_N.json` 加载 LLM hints
- 仅处理该批次内的记录，不影响其他数据

试点通过后再扩大到 batch_001–011（1100 条），最后处理剩余 012–018。

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
scripts/round3/
  analyze_data_quality.py          # Phase 0
  generate_gemini_prompt_multi_address.py  # Phase 1.1
  apply_multi_address_split.py     # Phase 1.2
  generate_gemini_prompt_geocode.py  # Phase 2.1
  batch_geocode_helper.py          # Phase 2.1 辅助（split/merge/status/validate）
  geocode_tencent.py               # Phase 2.2
  geocode_utils.py                 # 共享工具（省份提取/验证）
  verify_round3.py                 # Phase 3.1
  apply_manual_corrections.py      # Phase 3.2
  update_fallback_list.py          # Phase 4

data/round3/
  gemini_geocode_input.json        # 1712 条待处理记录
  geocode_batches/                 # 批次目录
    batch_001.json ~ batch_018.json  # 每批 100 条输入
    result_001.json ~ result_018.json # LLM 处理结果
  tencent_checkpoint.json
  verification_report.json
  still_problematic.json
  manual_corrections.json          # 用户填写（如有）
  backup/                          # 自动备份

docs/7-数据清洗-第三轮/
  PROMPT.md  PLAN.md  GEOCODE_PROGRESS.md  SUMMARY.md
```

**修改文件**：
- `.env.example` — 新增 `TENCENT_MAP_KEY`
- `data/heritage_sites_geocoded.json` — 最终更新
- `data/geocode_fallback_list.json` — 重新生成

## 执行节奏

| 阶段 | 人类操作 | Agent 操作 |
|------|---------|-----------|
| Phase 0 | 无 | 写脚本 → 运行分析 |
| Phase 1 | 跑 Gemini（1次，传 multi_address_input.json） | 写脚本 → 执行拆分 |
| Phase 2.1 | 无 | Claude Code Agent 批量处理（WebSearch + 模型知识）|
| Phase 2.2 试点 | TENCENT_MAP_KEY 写入 .env.local | `geocode_tencent.py --batch 1` 验证 pipeline |
| Phase 2.2 全量 | 确认试点结果 | 逐批扩大到 001–011，再处理 012–018 |
| Phase 3 | 人工校正（少量） | 写脚本 → 运行验证 |
| Phase 4 | 无 | 更新列表 → 重新 seed |
