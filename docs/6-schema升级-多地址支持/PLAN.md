# 实现计划：Schema 升级——支持一个文保单位多个地址

## 方案选择

采用**自引用 parent_id**方案（在 heritage_sites 表加一列），不拆两张表。

理由：
- 改动量适中，向后兼容，95% 的单地点条目完全不受影响
- 既能处理长城这种已拆分的情况，也能处理唐代帝陵这种待拆分的情况
- 前端改动可控

三种记录类型：
- **父记录**：代表官方文保单位（如"长城"），可以没有坐标，作为逻辑容器
- **子记录**：代表实际物理地点（如"齐长城遗址"），有坐标，parent_id 指向父记录
- **独立记录**：parent_id = NULL 且没有子记录，即现有 95% 的普通条目，完全不受影响

## 实施步骤

### 步骤 1：修复 scraper off-by-one bug + 支持父记录输出

**文件**：`scripts/scrape_wikisource.py`（第 188-208 行）

**Bug 根因**：`else` 分支（有子条目时）没有 `seq += 1`，导致后续独立条目的 release_id 全部偏小 1。

修复后逻辑：
```python
if not sub_cells_list:
    seq += 1
    sites.append(_make_entry(...))
else:
    seq += 1  # 修复：父行也占一个序号
    parent_release_id = f"{batch}-{seq}"
    parent_entry = _make_entry(parent_release_id, parent_name, ...)
    parent_entry["_is_parent"] = True
    sites.append(parent_entry)
    for i, sub_cells in enumerate(sub_cells_list, 1):
        child_entry = _make_entry(f"{batch}-{seq}-{i}", f"{parent_name}-{sub_name}", ...)
        child_entry["_parent_release_id"] = parent_release_id
        sites.append(child_entry)
```

**影响**：
- 长城父记录获得 `release_id = "5-442"`
- 长城 8 个子记录保持 `5-442-1` ~ `5-442-8` 不变，新增 `_parent_release_id = "5-442"`
- "大观圣作之碑"从 `5-442` 修正为 `5-443`
- 后续约 76 条记录的 release_id 全部 +1 修正

### 步骤 2：手动更新 heritage_sites_geocoded.json

由于重跑完整 pipeline 需要重新调用高德 API，本次手动修改 JSON：
- 在长城子条目前插入父记录（无坐标，`_is_parent: true`）
- 长城 8 个子条目加 `_parent_release_id: "5-442"`
- 将 `release_id` 为 `"5-442"` ~ `"5-517"` 的独立条目全部 +1

### 步骤 3：Schema Migration

**新建** `supabase/migrations/20240103000000_add_parent_child.sql`

```sql
ALTER TABLE heritage_sites
  ADD COLUMN parent_id UUID REFERENCES heritage_sites(id) ON DELETE SET NULL;

CREATE INDEX idx_heritage_sites_parent_id ON heritage_sites (parent_id);
```

### 步骤 4：数据 Migration（仅本地开发库）

**新建** `supabase/migrations/20240104000000_seed_great_wall_parent.sql`

通过 SQL 插入长城父记录并关联 8 个子记录。由于 supabase db reset 会重跑所有 migrations 但 seed 数据来自 seed_supabase.py，这个 migration 主要用于文档记录，实际关联通过更新后的 seed 脚本完成。

### 步骤 5：更新 geocode_amap.py

跳过 `_is_parent: true` 的记录（无需地理编码）。

### 步骤 6：更新 seed_supabase.py

两阶段插入：
1. 先插父记录和独立记录
2. 再插子记录，通过 `_parent_release_id` 查找父记录 UUID 填入 parent_id

### 步骤 7：TypeScript 类型更新

**文件**：`src/lib/types.ts`

- `HeritageSite`：加 `parent_id: string | null`，`province` 改为 `string | null`
- `SiteListItem`：Pick 中加 `parent_id`
- 新增 `SiteWithRelations` 接口

### 步骤 8：查询层更新

**文件**：`src/lib/supabase/queries.ts`

- `getAllSites()`：select 加 `parent_id`，加 `.not("latitude", "is", null)` 排除父记录
- `getSiteById()`：返回 `SiteWithRelations`，并行查父记录、兄弟、子记录

### 步骤 9：详情页适配

**文件**：`src/app/site/[id]/page.tsx`

- 子记录：显示"所属文保单位"卡片（父名称链接 + 兄弟列表）
- 父记录：显示"包含分段 (N)"卡片（子记录列表），地图卡片自然隐藏

## 不需要改动的地方

- `LeafletContainer.tsx`：父记录无坐标，markerData 已有 null 过滤
- `useFilters.ts`：搜索和筛选逻辑天然兼容
- `get_sites_in_bounds` RPC：WHERE latitude BETWEEN 自动排除 NULL 坐标

## 验证方式

1. `supabase db reset` 后验证父记录和子记录关联正确
2. 首页地图 marker 数量不变
3. 子记录详情页：显示"所属文保单位：长城"+ 7 个兄弟链接
4. 父记录详情页：无地图，显示"包含分段 (8)"列表
