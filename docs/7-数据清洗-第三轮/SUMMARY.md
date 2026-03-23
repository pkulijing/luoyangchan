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

## 后续 TODO

1. **百度百科补全低精度记录**：引入 `skills/baidu-baike` 工具（`BAIDU_API_KEY` 已配置），为约 120 条精度不足的记录重新生成精确地址并补跑腾讯地图。流程：
   - 扫描所有 `result_NNN.json`，识别 notes 含"未能查到"或地址只到县级的记录
   - DeepSeek 优先调用 `fetch_baidu_baike`（`lemmaTitle`），提取 `card` 属性中的位置信息
   - 百科无结果再 fallback 到 DuckDuckGo
   - 对有变动的批次重新跑腾讯地图 geocoding

2. **`_geocode_method` 标签规范化**：将 `tencent_geocode_gemini` 重命名为 `tencent_geocode_deepseek` 以准确反映来源

3. **父记录坐标处理**：当前多地址父记录坐标为 null，可考虑取子记录地理中心作为聚合展示坐标
