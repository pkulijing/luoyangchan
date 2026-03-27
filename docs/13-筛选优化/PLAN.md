# 第13轮：筛选优化 - 实现计划

## Context

FilterPanel 有三个问题：类别选项暴露了 4 种已废弃的历史分类、省份筛选粒度太粗、年代筛选因数据格式混乱几乎不可用。本轮在 schema 层面统一类别，将省份下拉改为地址搜索，删除年代筛选。

## 需求 1：类别 schema 迁移

### 数据层

**新建迁移文件** `supabase/migrations/20240105000000_normalize_category.sql`：
- `ALTER TABLE heritage_sites ADD COLUMN original_category TEXT`
- `UPDATE` 4 种历史类别：把原值写入 `original_category`，`category` 改为对应现代类别
- 映射：革命遗址→近现代、古建筑及历史纪念建筑物→古建筑、石窟寺→石窟寺及石刻、石刻及其他→石窟寺及石刻

**Python 脚本** `scripts/round7/migrate_category.py`：
- 对 `data/heritage_sites_geocoded.json` 执行同样的迁移
- 新增 `original_category` 字段
- 映射 `category` 到 6 种现代分类

**刷新数据库**：`seed_supabase.py --clear`

### 前端

**`src/lib/types.ts`**：`SiteCategory` 类型删除 4 种历史分类，只保留 6 种

**`src/lib/constants.ts`**：
- `SITE_CATEGORIES`：删除 4 种历史分类
- `CATEGORY_COLORS`：删除 4 种历史分类的颜色映射

**`src/components/map/LeafletContainer.tsx`**：`CATEGORY_ICONS` 删除 4 种历史分类的图标映射

## 需求 2：地址搜索替换省份下拉

### 思路

将省份 `<Select>` 替换为 `<Input>`，用户输入文字后：
1. **本地匹配**（即时，无 API）：在 sites 数据中搜索 province/city/name 包含输入文字的记录，匹配到则筛选数据
2. **天地图 geocoding**（本地无匹配时）：调用 `http://api.tianditu.gov.cn/geocoder?ds={"keyWord":"..."}&tk=...`，获取坐标后地图 flyTo 该位置（不筛选数据，只移动视角）

### 改动

**`src/lib/types.ts`**：
- `FilterState` 改为 `{ search: string; category: SiteCategory | null; location: string }`
- 删除 `province` 和 `era` 字段，新增 `location` 字段

**`src/hooks/useFilters.ts`**：
- 删除 province 和 era 筛选逻辑
- `location` 筛选：本地匹配 province/city/district 包含 location 文字的记录
- 导出未匹配标记，供 FilterPanel 判断是否需要调 geocoding

**`src/components/filters/FilterPanel.tsx`**：
- 删除省份 `<Select>` 和年代 `<Input>`
- 新增 location `<Input>`（placeholder "输入省市县或地址..."）
- 添加防抖（300ms）
- 当本地无匹配时，调天地图 geocoding 并通知地图移动

**`src/components/MapView.tsx`**：
- 新增 `onFlyTo(lat, lng, zoom)` 回调传给 FilterPanel
- 传给 LeafletContainer 实现 flyTo

**`src/components/map/LeafletContainer.tsx`**：
- 新增 `flyTo` prop：`{ lat: number; lng: number; zoom: number } | null`
- 当 flyTo 变化时调用 `map.flyTo()`

**`src/lib/constants.ts`**：删除 `PROVINCES` 数组（不再需要）

## 需求 3：删除年代筛选

已包含在需求 2 的改动中（FilterState 删除 era，FilterPanel 删除年代输入框）。

## 涉及文件

| 文件 | 操作 |
|---|---|
| `supabase/migrations/20240105000000_normalize_category.sql` | 新增 |
| `scripts/round7/migrate_category.py` | 新增 |
| `src/lib/types.ts` | 修改 |
| `src/lib/constants.ts` | 修改 |
| `src/hooks/useFilters.ts` | 修改 |
| `src/components/filters/FilterPanel.tsx` | 修改 |
| `src/components/MapView.tsx` | 修改 |
| `src/components/map/LeafletContainer.tsx` | 修改 |

## 验证

1. `npx tsc --noEmit` 编译通过
2. `npm run dev` 启动后：
   - 类别下拉只显示 6 个选项
   - 选择类别能正确筛选（原属历史分类的站点归入对应现代分类）
   - 输入"成都"能筛选出成都的站点并定位
   - 输入"王府井大街"等非省市名，本地无匹配时调 geocoding 定位
   - 年代筛选已消失
3. Supabase 数据库中 `original_category` 字段有值的记录应为第 1-2 批的历史分类站点
