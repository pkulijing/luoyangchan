# 数据富化 - 实现计划

## 四阶段流水线

### Phase 1: Wikipedia 内容采集

**脚本**: `scripts/round5/fetch_wikipedia.py`

- 从 `wikipedia_url` 解码标题，调用 Wikipedia REST API `page/summary/{title}`
- 提取 `extract`（摘要）和 `description`（短描述）
- Rate limit: 200 req/min，Checkpoint 每 100 条
- 输出: `data/round5/wikipedia_extracts.json`

### Phase 2: 百度百科 URL 及内容采集

**脚本**: `scripts/round5/fetch_baike.py`

- 复用 `skills/baidu-baike/scripts/baidu_baike.py` 的 `BaiduBaikeClient`
- 全量 5171 条记录，提取 `url`、`abstract_plain`、`card`
- Rate limit: 0.5s/req，Checkpoint 每 50 条
- 输出: `data/round5/baike_data.json`

### Phase 3: DeepSeek 描述 & 标签生成

**脚本**: `scripts/round5/enrich_descriptions.py`

- 参考 `deepseek_geocode.py` 的分组 + checkpoint 模式
- 每组 5 条，DeepSeek `deepseek-chat`，temperature=0
- 输入: 结构化字段 + Wikipedia/百度百科内容
- 输出: `description`（150-300 字）+ `tags`（10-20 关键词）
- 支持 `--resume`、`--dry-run`、`--workers N`
- 输出: `data/round5/enrichment_results.json`

### Phase 4: 数据合并 & Schema 更新

- **4a**: `scripts/round5/apply_enrichment.py` 合并入主数据文件
- **4b**: Supabase Migration 新增 `tags TEXT[]`（GIN 索引）+ `baike_url TEXT`
- **4c**: 更新 `seed_supabase.py` 的 `make_row()` 映射
- **4d**: 更新 `src/lib/types.ts` 的 `HeritageSite` 接口

## 依赖

无需新增 Python 依赖。复用 `openai`、`requests`、`BaiduBaikeClient`。

## 执行顺序

Phase 1 + Phase 2 并行 → Phase 3 → Phase 4

## 验证

- Phase 1/2: 抽样检查摘要完整性和 URL 有效性
- Phase 3: 跨类别/朝代抽样 20 条，人工评估描述和标签质量
- Phase 4: 重新 seed 后在 Supabase Studio 验证
