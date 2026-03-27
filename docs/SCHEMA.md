# 数据库 Schema

本文档描述 Supabase (PostgreSQL) 数据库的表结构。随 schema 演进持续更新。

## heritage_sites - 文保单位主表

存储全国重点文物保护单位基础数据，约 5171 条。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | UUID | PK | 自动生成 |
| name | TEXT | 是 | 站点名称 |
| province | TEXT | | 省份 |
| city | TEXT | | 城市 |
| district | TEXT | | 区县 |
| address | TEXT | | 详细地址 |
| category | TEXT | 是 | 类别（6 种现代分类） |
| original_category | TEXT | | 历史分类原始值（仅早期批次有值） |
| era | TEXT | | 时代（格式不统一，如"唐"、"唐至清"、"1841年"） |
| batch | INTEGER | | 公布批次（1-8） |
| batch_year | INTEGER | | 公布年份 |
| latitude | DOUBLE PRECISION | | 纬度（GCJ-02 坐标系） |
| longitude | DOUBLE PRECISION | | 经度（GCJ-02 坐标系） |
| location | GEOGRAPHY(POINT) | | PostGIS 地理字段（由触发器自动维护） |
| description | TEXT | | 简介 |
| tags | TEXT[] | | 关键词标签 |
| wikipedia_url | TEXT | | 中文维基百科链接 |
| baike_url | TEXT | | 百度百科链接 |
| image_url | TEXT | | 图片 URL（Supabase Storage 相对路径或外部 CDN） |
| is_open | BOOLEAN | | 是否开放 |
| release_id | TEXT | UNIQUE | 官方编号（如 "7-708"，批次-序号） |
| release_address | TEXT | | 官方原始地址 |
| parent_id | UUID | FK | 父记录 ID（用于多地点文保的子记录） |
| created_at | TIMESTAMPTZ | | 创建时间 |
| updated_at | TIMESTAMPTZ | | 更新时间（触发器自动维护） |

### 类别枚举（category）

| 类别 | 说明 |
|---|---|
| 古遗址 | |
| 古墓葬 | |
| 古建筑 | |
| 石窟寺及石刻 | |
| 近现代重要史迹及代表性建筑 | |
| 其他 | |

早期批次（1-2 批）使用过"革命遗址及革命纪念建筑物"等历史分类名，已迁移到现代分类，原始值保存在 `original_category`。

### 父子关系

约 95% 为独立记录（`parent_id IS NULL`）。少数大型文保（如长城）拆分为父记录（无坐标）+ 多个子记录（有坐标）。

### 坐标系

数据库统一存储 **GCJ-02** 坐标。前端展示时通过 `coordtransform` 转为 WGS-84（天地图/Leaflet）。绝对禁止在数据入库前做坐标转换。

### 索引

- `location` GIST 空间索引
- `province`, `category`, `era`, `batch`, `name` B-tree 索引
- `release_id` UNIQUE 约束
- `tags` GIN 索引

## profiles - 用户资料表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | UUID | PK/FK | 关联 auth.users |
| username | TEXT | UNIQUE | 用户名（用于 /user/xxx 路由） |
| display_name | TEXT | | 显示昵称 |
| avatar_url | TEXT | | 头像 URL |
| bio | TEXT | | 个人简介 |
| visited_count | INTEGER | | 已访问数（触发器维护） |
| wishlist_count | INTEGER | | 想去数（触发器维护） |
| created_at | TIMESTAMPTZ | | |
| updated_at | TIMESTAMPTZ | | |

## user_site_marks - 用户标记表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK | 关联 auth.users |
| site_id | UUID | FK | 关联 heritage_sites |
| mark_type | TEXT | 是 | "visited" 或 "wishlist" |
| visited_at | TIMESTAMPTZ | | 访问时间 |
| visited_note | TEXT | | 访问备注 |
| created_at | TIMESTAMPTZ | | |
| updated_at | TIMESTAMPTZ | | |

UNIQUE 约束：`(user_id, site_id, mark_type)`

## achievement_definitions - 成就定义表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | UUID | PK | |
| code | TEXT | UNIQUE | 成就代码 |
| name | TEXT | 是 | 成就名称 |
| description | TEXT | | 说明 |
| icon | TEXT | | 图标 |
| rarity | TEXT | | common/rare/epic/legendary |
| condition_type | TEXT | | 触发条件类型 |
| condition_value | JSONB | | 触发条件参数 |
| points | INTEGER | | 积分 |
| created_at | TIMESTAMPTZ | | |

## user_achievements - 用户成就表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK | |
| achievement_id | UUID | FK | |
| unlocked_at | TIMESTAMPTZ | | 解锁时间 |

UNIQUE 约束：`(user_id, achievement_id)`

## Supabase Storage

| Bucket | 用途 | 公开 |
|---|---|---|
| site-images | 文保单位图片（Wikimedia Commons CC 许可缩略图） | 是 |
