# 数据库 Schema 设计

## 概览

数据库使用 **PostgreSQL**（通过 Supabase 托管），启用了 **PostGIS** 扩展以支持地理空间查询。目前只有一张核心业务表 `heritage_sites`。

---

## 核心表：`heritage_sites`

### 字段说明

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `UUID` | PRIMARY KEY, DEFAULT `gen_random_uuid()` | 主键，由数据库自动生成 |
| `name` | `TEXT` | NOT NULL | 文保单位名称 |
| `province` | `TEXT` | | 所在省/自治区/直辖市，如 `广东省`、`北京市` |
| `city` | `TEXT` | | 所在城市，如 `广州市` |
| `district` | `TEXT` | | 所在区县（目前数据中较少填充） |
| `address` | `TEXT` | | 原始地址字符串，直接来自 Wikipedia 列表 |
| `category` | `TEXT` | NOT NULL | 文保类型，取值见下方枚举 |
| `era` | `TEXT` | | 时代，如 `明`、`清`、`1841年`（自由文本，不规范） |
| `batch` | `INTEGER` | | 公布批次，1-8 |
| `batch_year` | `INTEGER` | | 批次对应年份，1961/1982/1988/1996/2001/2006/2013/2019 |
| `latitude` | `DOUBLE PRECISION` | | 纬度（GCJ-02 坐标系，来自 Wikipedia API） |
| `longitude` | `DOUBLE PRECISION` | | 经度（GCJ-02 坐标系） |
| `location` | `GEOGRAPHY(POINT, 4326)` | | PostGIS 空间点，由触发器根据 lat/lng 自动计算 |
| `description` | `TEXT` | | 简介（当前大多为 NULL，预留后续 LLM 填充） |
| `wikipedia_url` | `TEXT` | | 对应中文 Wikipedia 页面 URL |
| `image_url` | `TEXT` | | 图片 URL（预留字段，当前为空） |
| `is_open` | `BOOLEAN` | DEFAULT NULL | 是否对外开放（预留字段，当前为空） |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | 记录创建时间 |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | 记录最后更新时间，由触发器维护 |

### `category` 枚举值

| 值 | 说明 |
|----|------|
| `古遗址` | 史前及历史时期遗址 |
| `古墓葬` | 帝王陵寝、贵族及平民墓地 |
| `古建筑` | 宫殿、寺庙、民居、桥梁等传统建筑 |
| `石窟寺及石刻` | 石窟、摩崖石刻、碑刻等 |
| `近现代重要史迹及代表性建筑` | 近现代革命遗址、纪念建筑等 |
| `其他` | 不属于以上类型的文保单位 |

---

## 索引

```sql
-- 空间索引（用于地理范围查询）
CREATE INDEX idx_heritage_sites_location ON heritage_sites USING GIST (location);

-- 普通 B-Tree 索引（用于筛选）
CREATE INDEX idx_heritage_sites_province ON heritage_sites (province);
CREATE INDEX idx_heritage_sites_category ON heritage_sites (category);
CREATE INDEX idx_heritage_sites_era      ON heritage_sites (era);
CREATE INDEX idx_heritage_sites_batch    ON heritage_sites (batch);
CREATE INDEX idx_heritage_sites_name     ON heritage_sites (name);
```

`location` 使用 GiST 索引而非普通 B-Tree，因为地理坐标点不是线性可排序的数据，GiST 支持"包含于"、"相交"等空间谓词的高效查询。

---

## 触发器

### `trg_update_location`

每次 INSERT 或 UPDATE 时，根据 `latitude`/`longitude` 自动计算并写入 `location` 字段，无需应用层手动维护：

```sql
CREATE OR REPLACE FUNCTION update_location()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
    NEW.location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
  ELSE
    NEW.location = NULL;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

注意参数顺序：`ST_MakePoint(longitude, latitude)`，PostGIS 遵循 X(经度)/Y(纬度) 的数学惯例，与日常说法（纬度/经度）相反。

### `trg_update_updated_at`

每次 UPDATE 时自动刷新 `updated_at` 时间戳，无需应用层传入。

---

## 安全策略（RLS）

表启用了 Row Level Security，当前策略：**全部行对任何人可读，无写入权限**。

```sql
ALTER TABLE heritage_sites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access"
  ON heritage_sites FOR SELECT USING (true);
```

这意味着前端可以直接用 `anon key` 查询，不需要登录。写入（INSERT/UPDATE/DELETE）只能通过 `service_role key`（绕过 RLS），用于数据导入脚本。

---

## RPC 函数

### `get_sites_in_bounds()`

按地图视窗的经纬度边界范围查询，支持附加筛选条件：

```sql
SELECT * FROM get_sites_in_bounds(
  min_lat   => 22.0,
  min_lng   => 112.0,
  max_lat   => 24.5,
  max_lng   => 115.0,
  p_category => '古建筑',   -- 可选
  p_era      => '明',        -- 可选，ILIKE 模糊匹配
  p_province => '广东省'    -- 可选
);
```

该函数目前暂未使用（前端采用一次性全量加载、客户端筛选的策略），预留给数据量增大后的按需加载场景。

---

## 数据样例

以下是数据库中的一条真实记录（`三元里平英团遗址`，第一批文保单位）：

```json
{
  "id": "fee7202c-9af2-4a2e-8f4d-8e45f8768aac",
  "name": "三元里平英团遗址",
  "province": "广东省",
  "city": "广州市",
  "district": null,
  "address": "广东省广州市",
  "category": "近现代重要史迹及代表性建筑",
  "era": "1841年",
  "batch": 1,
  "batch_year": 1961,
  "latitude": 23.163426,
  "longitude": 113.254704,
  "location": "0101000020E6100000448A01124D505C40EC504D49D6293740",
  "description": null,
  "wikipedia_url": "https://zh.wikipedia.org/wiki/三元里平英团遗址",
  "image_url": null,
  "is_open": null,
  "created_at": "2026-03-17T16:27:05.08812+00:00",
  "updated_at": "2026-03-17T16:27:05.08812+00:00"
}
```

几点说明：
- `location` 字段存储的是 WKB（Well-Known Binary）十六进制编码，是 PostGIS 内部格式，应用层通常不直接使用这个值。
- `era` 是自由文本，直接取自 Wikipedia 原文，格式不统一（有的是朝代名如 `明`，有的是具体年份如 `1841年`）。
- `district`、`description`、`image_url`、`is_open` 目前大多为 `null`，是预留的扩展字段。
