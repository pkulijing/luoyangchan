-- 修复函数的 search_path 安全警告
-- 为所有函数添加 SET search_path = ''

-- ============================================
-- 1. update_location 函数
-- ============================================
CREATE OR REPLACE FUNCTION update_location()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
    NEW.location = public.ST_SetSRID(public.ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
  ELSE
    NEW.location = NULL;
  END IF;
  RETURN NEW;
END;
$$;

-- ============================================
-- 2. update_updated_at 函数
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- ============================================
-- 3. get_sites_in_bounds 函数
-- ============================================
CREATE OR REPLACE FUNCTION get_sites_in_bounds(
  min_lat DOUBLE PRECISION,
  min_lng DOUBLE PRECISION,
  max_lat DOUBLE PRECISION,
  max_lng DOUBLE PRECISION,
  p_category TEXT DEFAULT NULL,
  p_era TEXT DEFAULT NULL,
  p_province TEXT DEFAULT NULL
)
RETURNS SETOF public.heritage_sites
LANGUAGE sql
STABLE
SET search_path = ''
AS $$
  SELECT * FROM public.heritage_sites
  WHERE latitude BETWEEN min_lat AND max_lat
    AND longitude BETWEEN min_lng AND max_lng
    AND (p_category IS NULL OR category = p_category)
    AND (p_era IS NULL OR era ILIKE '%' || p_era || '%')
    AND (p_province IS NULL OR province = p_province)
  LIMIT 500;
$$;

-- ============================================
-- 4. update_updated_at_column 函数
-- ============================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;
