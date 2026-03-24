# 数据富化 - 开发总结

## 开发项背景

5171 条全国重点文保单位记录的 `description` 字段全部为空，缺乏结构化标签和百科链接。用户只能通过名称子字符串匹配和下拉框筛选来查找文保单位，无法支持自然语言搜索（如"山西省所有与唐太宗李世民有关的文物保护遗址"）。本轮开发为后续搜索系统奠定数据基础。

## 实现方案

### 关键设计

- **四阶段流水线**：名称规范化 → 百科内容采集 → LLM 描述/标签生成 → 数据合并
- **百度百科采集策略演进**：百度 API（41% 命中，每日 1000 次限制）→ 直接构造 URL + BeautifulSoup 爬取（99.96%）→ 子记录父记录兜底 + 手动补全（100%）
- **Wikipedia 采集策略演进**：REST API 直取（80%）→ 去括号/下划线重试（90%）→ 搜索 API + 相似度校验（95%）→ 全量补采含无 URL 记录（76% 全覆盖）
- **LLM 富化**：DeepSeek-V3，temperature=0，每组 5 条，8 workers 并发，checkpoint 断点续跑
- **单条修复工具**：新建 `fix-heritage-info` skill，集成百科爬取 + DeepSeek 生成 + JSON 写入 + Supabase 同步

### 开发内容概括

| 内容 | 说明 |
|------|------|
| 名称规范化 | 异体字修复（靑→青），用显式映射表而非 zhconv（避免赵孟頫的"頫"被误转） |
| Wikipedia 采集 | 3920/5171 条有内容（76%），全部转为简体中文 |
| 百度百科采集 | 5171/5171 条 URL（100%），直接爬取页面而非 API |
| DeepSeek 描述生成 | 5171/5171 条（100%），平均 210 字 |
| DeepSeek 标签生成 | 5171/5171 条（100%），平均 12 个标签 |
| 数据库 Schema | 新增 `tags TEXT[]`（GIN 索引）、`baike_url TEXT`，`release_id` 添加 UNIQUE 约束 |
| 前端路由重构 | `/site/[id]` → `/site/[releaseId]`，使用国务院编号替代 UUID |
| 新增页面 | `/site/[releaseId]/raw`（JSON 调试页）、`/example`（demo 索引页） |
| 新增 Skill | `fix-heritage-info`：单条信息富化工具 |

### 额外产物

| 文件 | 用途 |
|------|------|
| `scripts/round5/fetch_wikipedia.py` | Wikipedia 摘要批量采集 |
| `scripts/round5/fetch_baike.py` | 百度百科批量采集（API 版，已弃用） |
| `scripts/round5/fix_wikipedia.py` | Wikipedia 繁简转换 + 失败重试 |
| `scripts/round5/fix_wikipedia_full.py` | Wikipedia 全量补采（含无 URL 记录） |
| `scripts/round5/fix_baike_ddg.py` | 百度百科直接 URL 爬取补采 |
| `scripts/round5/enrich_descriptions.py` | DeepSeek 批量描述/标签生成 |
| `scripts/round5/apply_enrichment.py` | 富化结果合并到主数据文件 |
| `scripts/round5/normalize_names.py` | 名称异体字规范化 |
| `scripts/round5/audit_enrichment.py` | 富化结果质量审计 |
| `skills/fix-heritage-info/` | 单条信息富化 Skill |

## 局限性

1. **Wikipedia 覆盖率 76%**：1251 条记录没有 Wikipedia 词条，主要是第 6-8 批的小型文保单位
2. **DeepSeek 描述质量依赖参考资料**：有百科参考的记录平均描述 211 字，无参考的仅 170 字，内容可能较泛
3. **百度百科子记录使用父记录兜底**：46 条子记录（如茶马古道各段）使用父记录的百科 URL，内容不够具体
4. **标签覆盖维度不均**：建筑类遗址的标签较丰富（风格、材质、宗教），遗址类标签偏泛（朝代、考古）

## 后续 TODO

1. **构建搜索系统**：
   - Phase 2：LLM 查询理解 + PostgreSQL 全文搜索（`tsvector` + 中文分词）
   - Phase 3：向量语义搜索（`pgvector` + embedding）
   - 前端搜索交互组件
2. **标签质量提升**：对无百科参考的 ~150 条记录，用更强的模型（Claude Sonnet）重新生成
3. **百度百科内容深度利用**：目前只用了摘要，信息框数据（建造年代、占地面积等）可结构化存入数据库
