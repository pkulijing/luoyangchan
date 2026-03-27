# 第13轮：筛选优化 - 开发总结

## 开发项背景

FilterPanel 存在三个体验问题：类别选项暴露了 4 种已废弃的历史分类、省份筛选粒度太粗无法到市县、年代筛选因数据格式混乱几乎不可用。

## 实现方案

### 需求 1：类别 schema 迁移

**关键设计**：在数据层统一解决，而非前端做映射。

- 新增 `original_category` 字段保存历史分类原始值
- 360 条记录的 `category` 映射到 6 种现代分类
- 前端 `SiteCategory` 类型、`SITE_CATEGORIES`、`CATEGORY_COLORS`、`CATEGORY_ICONS` 全部删除历史分类条目

### 需求 2：省市县三级联动筛选

将省份下拉替换为省市县三级联动：选了省出现市下拉，选了市出现县下拉。选项从 sites 数据中动态提取。

- `FilterState` 改为 `{ search, category, province, city, district }`
- `useFilters` 新增 `provinces`/`cities`/`districts` 计算属性
- `SiteListItem` 新增 `district` 字段
- 删除 `PROVINCES` 硬编码常量

### 需求 3：删除年代筛选

从 `FilterState` 中移除 `era`，FilterPanel 中删除年代输入框。

### 开发内容

| 文件 | 操作 | 说明 |
|---|---|---|
| `scripts/round7/migrate_category.py` | 新增 | JSON 数据类别迁移脚本 |
| `supabase/migrations/20240105000000_normalize_category.sql` | 新增 | 数据库类别迁移 |
| `src/lib/types.ts` | 修改 | SiteCategory 精简为 6 类，FilterState 改为省市县，SiteListItem 加 district |
| `src/lib/constants.ts` | 修改 | 删除历史分类颜色、删除 PROVINCES 数组 |
| `src/lib/supabase/queries.ts` | 修改 | getAllSites select 加 district |
| `src/hooks/useFilters.ts` | 修改 | 省市县三级筛选逻辑 + 动态选项提取 |
| `src/components/filters/FilterPanel.tsx` | 修改 | 三级联动下拉 UI，删除年代输入 |
| `src/components/MapView.tsx` | 修改 | 传递 provinces/cities/districts 给 FilterPanel |
| `src/components/map/LeafletContainer.tsx` | 修改 | 删除历史分类图标 |

## 局限性

- 区县数据来自高德 geocoding，部分大型遗址可能跨区导致 district 不准
- 年代筛选暂时移除，后续需 LLM/RAG 方案

## 后续 TODO

- 年代智能筛选（LLM/RAG 方案）
- 图片存储方案修正（Supabase Storage + 百度 CDN 双字段 + 配置开关）
