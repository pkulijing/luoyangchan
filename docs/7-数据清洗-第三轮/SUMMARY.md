# 第三轮数据清洗开发总结

## 开发项背景

### 希望解决的问题

第二轮数据清洗后，数据库中约 1712 条记录（占总量约 34%）仍存在以下问题：

1. **低精度坐标**（geocode fallback）：地理编码失败后回退到县城中心点，1015 条
2. **POI 省份不匹配**：高德搜到同名但不同省份的 POI，导致坐标点在错误省份，约 276 条
3. **重复坐标组**：276 组（643 条）记录聚在完全相同的坐标点，主要由上述两类问题叠加造成
4. **多地址条目**：单条记录的 release_address 包含多个跨省市地址，无法单点定位，约 30 条

### 目标

将 1712 条问题记录的坐标精度提升到乡镇/村级，并将多地址条目正确拆分为独立子记录。

---

## 实现方案

### 关键设计

**Phase 1：多地址拆分（Gemini）**
- 识别 release_address 含多个独立地点的条目，通过 Gemini 判断是否需要拆分
- 拆分结果：36 条父记录中 26 条实际拆分，生成 89 条子记录（另有长城 8 条子记录已在前期处理）
- 父记录设 `_is_parent: true`，子记录通过 `_parent_release_id` 关联父记录

**Phase 2：LLM 地址生成 + 腾讯地图 Geocoding（核心）**

原计划用 Gemini 一次性生成地址，因数据量大（1712 条）和工具调用限制放弃，改为：
- **DeepSeek API**（`deepseek-chat`）+ **DuckDuckGo 搜索**：按 100 条分批，每组 10 条并发调用，生成精确到乡镇/村级的地址字符串
- **腾讯地图 Web Service API**：接收 DeepSeek 生成的地址，进行地理编码，加省份验证防止跨省错匹配
- 省份验证是核心改进：geocoding 结果省份与预期省份不匹配则直接拒绝，避免 Round 2 的主要错误

**批处理管道设计**
- 18 个批次（每批 100 条，最后一批 12 条），按阶段流水线处理
- DeepSeek 批次间并行（3 workers），腾讯地图批次间串行（写同一文件）
- checkpoint 机制支持断点续跑
- `--workers N` 参数支持组内并发，实测 3 workers 效果最优

### 开发内容概括

| 新增文件 | 说明 |
|---------|------|
| `scripts/round3/deepseek_geocode.py` | DeepSeek + DuckDuckGo 批量生成精确地址，支持并发、断点续跑 |
| `scripts/round3/geocode_multi_address.py` | 对多地址拆分子记录进行腾讯地图 geocoding 并写入主数据文件 |
| `scripts/round3/batch_geocode_helper.py` | 批次管理辅助工具（分批/合并/状态查看） |

| 修改文件 | 说明 |
|---------|------|
| `scripts/round3/geocode_tencent.py` | 新增 `--batch N` 参数、腾讯 API 签名（SK）、移除无效策略3 |
| `data/heritage_sites_geocoded.json` | 新增 89 条子记录，更新 1679 条坐标和地址 |
| `scripts/pyproject.toml` | 新增依赖：`duckduckgo-search`、`ddgs`、`openai` |

### 额外产物

- `data/round3/geocode_batches/result_001.json ~ result_018.json`：18 批 DeepSeek 生成的精确地址，可复用
- `docs/7-数据清洗-第三轮/GEOCODE_PROGRESS.md`：两阶段进度追踪表

---

## 最终数据情况

| 指标 | 数值 |
|------|------|
| 总记录数 | 5150（含 89 条拆分子记录） |
| 有坐标 | 5149 |
| 本轮新增/更新坐标 | 1679 条（`tencent_geocode_gemini`） |
| 父记录（`_is_parent`） | 26 条 |
| 子记录（`_parent_release_id`） | 97 条 |

---

## 局限性

1. **约 120 条记录地址精度仍只到县级**：DeepSeek + DuckDuckGo 搜索对偏远遗址（西北荒漠、少数民族地区）查找效果差，返回了"未能查到精确乡镇/村级地址"的结果。腾讯地图用县级地址仍能定位，但坐标精度低于预期。

2. **DuckDuckGo 对中文内容索引不足**：Bing 系搜索引擎对百度百科等中文权威来源收录少，部分明显可以在百度百科找到的地址（如"磨沟遗址"）却搜不到。

3. **批次 result 文件 geocode_method 标签历史遗留**：`geocode_tencent.py` 输出的 `_geocode_method` 值为 `tencent_geocode_gemini`，实际地址来源是 DeepSeek，标签存在歧义（不影响功能）。

---

## 过程反思

本次开发整体较为混乱，记录三个主要教训：

### 1. 没有充分实验就推进全量

1712 条记录体量较大，但没有针对 LLM 地址生成这个核心步骤做足够的小规模验证，就直接启动了全量流程。结果过程中陆续暴露问题：Sonnet 配额紧张、Haiku 性能不足以完成复杂任务、Agent 工具调用总次数限制等，导致部分批次结果质量不稳定，需要反复检查和补跑，浪费了大量时间。

**正确做法**：对于每个关键步骤（LLM 生成地址、腾讯地图 geocoding），都应先用 10–20 条样本完整跑通并人工验收，确认质量达标后再扩大到全量。

### 2. 没有原子化拆分问题，导致遗漏

多地址条目拆分（Phase 1）和批量 geocoding（Phase 2）的目标不同、工具不同，但被混在同一个大流程里推进。multi-address 子记录识别出来后，正确做法是立即生成并写入 heritage_sites_geocoded.json，然后再跟其他记录一起进入 geocoding 流程。但实际上拖到最后才想起这批子记录还没有入库，需要单独补。

**正确做法**：每个子问题解决后立即验证产出、落库，不要积累到最后一起处理。小步提交，每步可验证。

### 3. 没有提前评估工具质量，选型偏差

LLM 地址生成这一步的核心需求是：查找偏远、冷门文物遗址的精确地理位置。这是一个强依赖中文权威信息源的任务，百度百科对绝大多数全国重点文物保护单位都有收录，第一段摘要或信息卡片通常就能给出精确到乡镇的地址。

然而整个流程直到快结束时才引入百度百科 API，前期用的是 Claude Code Agent WebSearch（工具调用限制多、quota 消耗快）和 DuckDuckGo（中文覆盖差）。如果一开始就以百度百科为主要信息源，精确率会显著更高，整体耗时也会大幅减少。

**正确做法**：在方案设计阶段就评估各信息源对目标任务的覆盖质量，优先选择最权威的中文来源，而不是默认用通用搜索引擎。

---

## 后续 TODO

1. **百度百科补全低精度记录**：引入 `skills/baidu-baike` 工具（`BAIDU_API_KEY` 已配置），为约 120 条精度不足的记录重新生成精确地址并补跑腾讯地图。流程：
   - 扫描所有 `result_NNN.json`，识别 notes 含"未能查到"或地址只到县级的记录
   - DeepSeek 优先调用 `fetch_baidu_baike`（`lemmaTitle`），提取 `card` 属性中的位置信息
   - 百科无结果再 fallback 到 DuckDuckGo
   - 对有变动的批次重新跑腾讯地图 geocoding

2. **`_geocode_method` 标签规范化**：将 `tencent_geocode_gemini` 重命名为 `tencent_geocode_deepseek` 以准确反映来源

3. **父记录坐标处理**：当前多地址父记录坐标为 null，可考虑取子记录地理中心作为聚合展示坐标
