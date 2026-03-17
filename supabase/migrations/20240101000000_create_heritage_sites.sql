-- 全国重点文物保护单位数据表
-- 用于 Supabase (PostgreSQL) 数据库

-- 启用 PostGIS 扩展 (Supabase 默认可用)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 文保单位主表
CREATE TABLE heritage_sites (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  province      TEXT,
  city          TEXT,
  district      TEXT,
  address       TEXT,
  category      TEXT NOT NULL,
  era           TEXT,
  batch         INTEGER,
  batch_year    INTEGER,
  latitude      DOUBLE PRECISION,
  longitude     DOUBLE PRECISION,
  location      GEOGRAPHY(POINT, 4326),
  description   TEXT,
  wikipedia_url TEXT,
  image_url     TEXT,
  is_open       BOOLEAN DEFAULT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 空间索引
CREATE INDEX idx_heritage_sites_location ON heritage_sites USING GIST (location);

-- 常用筛选索引
CREATE INDEX idx_heritage_sites_province ON heritage_sites (province);
CREATE INDEX idx_heritage_sites_category ON heritage_sites (category);
CREATE INDEX idx_heritage_sites_era ON heritage_sites (era);
CREATE INDEX idx_heritage_sites_batch ON heritage_sites (batch);
CREATE INDEX idx_heritage_sites_name ON heritage_sites (name);

-- 自动更新 location 字段的触发器
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

CREATE TRIGGER trg_update_location
  BEFORE INSERT OR UPDATE ON heritage_sites
  FOR EACH ROW
  EXECUTE FUNCTION update_location();

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_updated_at
  BEFORE UPDATE ON heritage_sites
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();

-- RLS: 第一阶段全部公开可读
ALTER TABLE heritage_sites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access"
  ON heritage_sites
  FOR SELECT
  USING (true);

-- 按地图视窗范围查询的 RPC 函数
CREATE OR REPLACE FUNCTION get_sites_in_bounds(
  min_lat DOUBLE PRECISION,
  min_lng DOUBLE PRECISION,
  max_lat DOUBLE PRECISION,
  max_lng DOUBLE PRECISION,
  p_category TEXT DEFAULT NULL,
  p_era TEXT DEFAULT NULL,
  p_province TEXT DEFAULT NULL
)
RETURNS SETOF heritage_sites AS $$
  SELECT * FROM heritage_sites
  WHERE latitude BETWEEN min_lat AND max_lat
    AND longitude BETWEEN min_lng AND max_lng
    AND (p_category IS NULL OR category = p_category)
    AND (p_era IS NULL OR era ILIKE '%' || p_era || '%')
    AND (p_province IS NULL OR province = p_province)
  LIMIT 500;
$$ LANGUAGE sql STABLE;
