# 开发总结：Schema 升级——支持一个文保单位多个地址

## 开发项背景

### 希望解决的问题

全国重点文物保护单位中存在"一个单位、多个物理地点"的情况。以长城（第五批，5-442）为例，官方公告列出了 8 个子条目（齐长城遗址、秦长城遗址、燕长城遗址、司马台段等），之前的处理方案是将它们拆成 8 条完全独立的记录，既没有父记录，也没有任何关联关系。同时发现 scraper 存在 off-by-one bug：处理有子条目的行时未自增序号，导致第五批从 5-442 开始的约 76 个独立记录的 release_id 全部偏小 1。

## 实现方案

### 关键设计

采用**自引用 parent_id 外键**方案，在 `heritage_sites` 表加一列，不拆两张表。

三种记录类型：
- **父记录**：代表官方文保单位（如"长城"），无坐标，`parent_id = NULL`
- **子记录**：代表实际物理地点（如"长城-齐长城遗址"），有坐标，`parent_id` 指向父记录
- **独立记录**：`parent_id = NULL` 且无子记录，即 95% 的普通条目，完全不受影响

前端地图层只查有坐标的记录（`latitude IS NOT NULL`），父记录自然被过滤，无需额外处理。

### 开发内容概括

| 文件 | 改动内容 |
|------|---------|
| `scripts/scrape_wikisource.py` | 修复 off-by-one bug（`else` 分支补加 `seq += 1`）；新增父记录输出（`_is_parent`）和子记录标记（`_parent_release_id`） |
| `data/heritage_sites_geocoded.json` | 插入长城父记录（5-442）；8 个子记录加 `_parent_release_id`；原错位的 5-442~5-517 全部 +1（76 条） |
| `supabase/migrations/20240103000000_add_parent_child.sql` | 新增 `parent_id UUID` 自引用外键 + 索引 |
| `scripts/geocode_amap.py` | 地理编码跳过 `_is_parent: true` 记录（父记录无独立地址） |
| `scripts/seed_supabase.py` | 重构为两阶段插入：先父/独立记录，再查 UUID 填入子记录的 `parent_id` |
| `src/lib/types.ts` | `province` 改为 nullable；`HeritageSite` 加 `parent_id`；新增 `SiteWithRelations` 接口 |
| `src/lib/supabase/queries.ts` | `getAllSites` 增加 `latitude IS NOT NULL` 过滤；`getSiteById` 返回含父/兄弟/子关系的完整数据 |
| `src/app/site/[id]/page.tsx` | 父记录页显示"包含分段(N)"列表；子记录页显示"所属文保单位"和"其他分段"导航 |

### 额外产物

无（改动均为核心逻辑）

## 局限性

1. **只有长城做了实际关联**：唐代帝陵、西汉帝陵等约 40 个多地址单位在 JSON 数据中仍是单条记录（没有拆子条目），schema 已支持但数据层面待处理
2. **长城子记录的 release_address 不完全准确**：齐长城遗址的 `province` 字段被地理编码为北京市（POI 搜索匹配到了通州的一处遗址），与官方地址（山东省）不符，属于地理编码质量问题
3. **父记录无法从地图直接访问**：父记录无坐标，只能通过子记录详情页的"所属文保单位"链接导航到，搜索框也不会返回父记录

## 后续 TODO

1. **数据清洗第三轮**：对唐代帝陵、西汉帝陵等多地址单位进行实际拆分，补充子条目数据
2. **长城子条目地理编码质量**：部分子条目坐标偏差较大（如齐长城遗址定位在北京），可考虑人工校正或用 `release_address` 重新编码
3. **全文搜索支持父记录**：搜索框目前基于 `latitude IS NOT NULL` 过滤，父记录无法被搜到，未来可考虑在搜索逻辑中特殊处理
