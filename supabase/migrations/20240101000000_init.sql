-- =============================================
-- 洛阳铲 - 数据库初始化
-- 全国重点文物保护单位地图浏览工具
-- =============================================

-- PostGIS 扩展
CREATE EXTENSION IF NOT EXISTS postgis;

-- =============================================
-- 1. 文保单位主表
-- =============================================

CREATE TABLE heritage_sites (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  province        TEXT,
  city            TEXT,
  district        TEXT,
  address         TEXT,
  category        TEXT NOT NULL,
  era             TEXT,
  batch           INTEGER,
  batch_year      INTEGER,
  latitude        DOUBLE PRECISION,
  longitude       DOUBLE PRECISION,
  location        GEOGRAPHY(POINT, 4326),
  description     TEXT,
  wikipedia_url   TEXT,
  baike_url       TEXT,
  image_url       TEXT,                  -- 自托管图片相对路径（如 site-images/1-1.jpg）
  baike_image_url TEXT,                  -- 百度百科 CDN 图片 URL
  tags            TEXT[],
  original_category TEXT,                -- 历史分类原始值（迁移前）
  is_open         BOOLEAN DEFAULT NULL,
  release_id      TEXT,                  -- 官方编号（如 1-1）
  release_address TEXT,                  -- 官方原始地址
  parent_id       UUID REFERENCES heritage_sites(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- release_id 唯一约束（用于 upsert）
ALTER TABLE heritage_sites ADD CONSTRAINT heritage_sites_release_id_unique UNIQUE (release_id);

-- 索引
CREATE INDEX idx_heritage_sites_location ON heritage_sites USING GIST (location);
CREATE INDEX idx_heritage_sites_province ON heritage_sites (province);
CREATE INDEX idx_heritage_sites_category ON heritage_sites (category);
CREATE INDEX idx_heritage_sites_era ON heritage_sites (era);
CREATE INDEX idx_heritage_sites_batch ON heritage_sites (batch);
CREATE INDEX idx_heritage_sites_name ON heritage_sites (name);
CREATE INDEX idx_heritage_sites_parent_id ON heritage_sites (parent_id);
CREATE INDEX idx_heritage_sites_tags ON heritage_sites USING GIN(tags);

-- 自动更新 location（search_path 需包含 extensions 以访问 PostGIS 类型）
CREATE OR REPLACE FUNCTION update_location()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, extensions
AS $$
BEGIN
  IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
    NEW.location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
  ELSE
    NEW.location = NULL;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_update_location
  BEFORE INSERT OR UPDATE ON heritage_sites
  FOR EACH ROW EXECUTE FUNCTION update_location();

-- 自动更新 updated_at
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

CREATE TRIGGER trg_update_updated_at
  BEFORE UPDATE ON heritage_sites
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS: 公开可读
ALTER TABLE heritage_sites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON heritage_sites
  FOR SELECT USING (true);

-- 按地图视窗查询的 RPC 函数
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

-- =============================================
-- 2. 用户 profile 表
-- =============================================

CREATE TABLE profiles (
  id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username        TEXT UNIQUE,
  display_name    TEXT,
  avatar_url      TEXT,
  bio             TEXT,
  visited_count   INTEGER DEFAULT 0,
  wishlist_count  INTEGER DEFAULT 0,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_profiles_username ON profiles(username);

-- RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "profiles_select_policy" ON profiles
  FOR SELECT USING (true);
CREATE POLICY "profiles_update_policy" ON profiles
  FOR UPDATE USING ((select auth.uid()) = id);
CREATE POLICY "profiles_delete_policy" ON profiles
  FOR DELETE USING ((select auth.uid()) = id);
CREATE POLICY "profiles_insert_policy" ON profiles
  FOR INSERT WITH CHECK ((select auth.uid()) = id);

-- 通用 updated_at 触发器函数
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

CREATE TRIGGER update_profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- 新用户注册自动创建 profile（从邮箱生成唯一用户名）
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  base_username TEXT;
  final_username TEXT;
  suffix INTEGER := 0;
BEGIN
  base_username := lower(regexp_replace(
    split_part(NEW.email, '@', 1),
    '[^a-z0-9_]', '', 'g'
  ));

  IF base_username = '' OR base_username IS NULL THEN
    base_username := 'user';
  END IF;

  IF length(base_username) > 15 THEN
    base_username := substring(base_username, 1, 15);
  END IF;

  final_username := base_username;
  WHILE EXISTS (SELECT 1 FROM public.profiles WHERE username = final_username) LOOP
    suffix := suffix + 1;
    final_username := base_username || suffix::TEXT;
  END LOOP;

  INSERT INTO public.profiles (id, username, display_name, avatar_url)
  VALUES (
    NEW.id,
    final_username,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
    NEW.raw_user_meta_data->>'avatar_url'
  );

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

COMMENT ON TABLE profiles IS '用户扩展信息表，与 auth.users 一对一关联';

-- =============================================
-- 3. 用户标记表（去过/想去）
-- =============================================

CREATE TABLE user_site_marks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  site_id     UUID NOT NULL REFERENCES heritage_sites(id) ON DELETE CASCADE,
  mark_type   TEXT NOT NULL CHECK (mark_type IN ('visited', 'wishlist')),
  visited_at  DATE,
  visited_note TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, site_id)
);

CREATE INDEX idx_user_site_marks_user_id ON user_site_marks(user_id);
CREATE INDEX idx_user_site_marks_site_id ON user_site_marks(site_id);
CREATE INDEX idx_user_site_marks_mark_type ON user_site_marks(mark_type);
CREATE INDEX idx_user_site_marks_user_type ON user_site_marks(user_id, mark_type);

-- RLS
ALTER TABLE user_site_marks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_site_marks_select_policy" ON user_site_marks
  FOR SELECT USING (true);
CREATE POLICY "user_site_marks_insert_policy" ON user_site_marks
  FOR INSERT WITH CHECK ((select auth.uid()) = user_id);
CREATE POLICY "user_site_marks_update_policy" ON user_site_marks
  FOR UPDATE USING ((select auth.uid()) = user_id);
CREATE POLICY "user_site_marks_delete_policy" ON user_site_marks
  FOR DELETE USING ((select auth.uid()) = user_id);

CREATE TRIGGER update_user_site_marks_updated_at
  BEFORE UPDATE ON user_site_marks
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- 更新 profile 统计缓存
CREATE OR REPLACE FUNCTION public.update_profile_mark_counts()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  target_user_id UUID;
BEGIN
  IF TG_OP = 'DELETE' THEN
    target_user_id := OLD.user_id;
  ELSE
    target_user_id := NEW.user_id;
  END IF;

  UPDATE public.profiles
  SET
    visited_count = (
      SELECT COUNT(*) FROM public.user_site_marks
      WHERE user_id = target_user_id AND mark_type = 'visited'
    ),
    wishlist_count = (
      SELECT COUNT(*) FROM public.user_site_marks
      WHERE user_id = target_user_id AND mark_type = 'wishlist'
    ),
    updated_at = NOW()
  WHERE id = target_user_id;

  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER update_profile_counts_on_mark_change
  AFTER INSERT OR UPDATE OR DELETE ON user_site_marks
  FOR EACH ROW EXECUTE FUNCTION public.update_profile_mark_counts();

-- 标记统计视图
CREATE VIEW site_mark_stats
WITH (security_invoker = true)
AS
SELECT
  site_id,
  COUNT(*) FILTER (WHERE mark_type = 'visited') AS visited_count,
  COUNT(*) FILTER (WHERE mark_type = 'wishlist') AS wishlist_count
FROM user_site_marks
GROUP BY site_id;

COMMENT ON TABLE user_site_marks IS '用户对文保单位的标记（去过/想去）';
COMMENT ON VIEW site_mark_stats IS '文保单位标记统计（去过/想去人数）';

-- =============================================
-- 4. 成就系统
-- =============================================

CREATE TABLE achievement_definitions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code            TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  description     TEXT NOT NULL,
  icon            TEXT,
  rarity          TEXT NOT NULL CHECK (rarity IN ('common', 'rare', 'epic', 'legendary')),
  condition_type  TEXT NOT NULL CHECK (condition_type IN (
    'province_count', 'province_complete', 'city_complete',
    'district_complete', 'category_count', 'total_count'
  )),
  condition_value JSONB NOT NULL,
  points          INTEGER DEFAULT 10,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_achievement_definitions_code ON achievement_definitions(code);
CREATE INDEX idx_achievement_definitions_condition_type ON achievement_definitions(condition_type);
CREATE INDEX idx_achievement_definitions_rarity ON achievement_definitions(rarity);

CREATE TABLE user_achievements (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  achievement_id  UUID NOT NULL REFERENCES achievement_definitions(id) ON DELETE CASCADE,
  unlocked_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, achievement_id)
);

CREATE INDEX idx_user_achievements_user_id ON user_achievements(user_id);
CREATE INDEX idx_user_achievements_achievement_id ON user_achievements(achievement_id);
CREATE INDEX idx_user_achievements_unlocked_at ON user_achievements(unlocked_at);

-- RLS
ALTER TABLE achievement_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_achievements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "achievement_definitions_select_policy" ON achievement_definitions
  FOR SELECT USING (true);
CREATE POLICY "user_achievements_select_policy" ON user_achievements
  FOR SELECT USING (true);

-- 检查并授予成就
CREATE OR REPLACE FUNCTION public.check_and_grant_achievements(p_user_id UUID)
RETURNS TABLE(achievement_id UUID, achievement_code TEXT, achievement_name TEXT)
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  ad RECORD;
  user_visited_count INTEGER;
  condition_count INTEGER;
  condition_province TEXT;
  condition_city TEXT;
  condition_district TEXT;
  condition_category TEXT;
  province_total INTEGER;
  city_total INTEGER;
  district_total INTEGER;
  user_province_count INTEGER;
  user_city_count INTEGER;
  user_district_count INTEGER;
  user_category_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO user_visited_count
  FROM public.user_site_marks
  WHERE user_id = p_user_id AND mark_type = 'visited';

  FOR ad IN SELECT * FROM public.achievement_definitions LOOP
    IF EXISTS (
      SELECT 1 FROM public.user_achievements
      WHERE user_id = p_user_id AND achievement_id = ad.id
    ) THEN
      CONTINUE;
    END IF;

    CASE ad.condition_type
      WHEN 'total_count' THEN
        condition_count := (ad.condition_value->>'count')::INTEGER;
        IF user_visited_count >= condition_count THEN
          INSERT INTO public.user_achievements (user_id, achievement_id)
          VALUES (p_user_id, ad.id);
          achievement_id := ad.id;
          achievement_code := ad.code;
          achievement_name := ad.name;
          RETURN NEXT;
        END IF;

      WHEN 'province_count' THEN
        condition_province := ad.condition_value->>'province';
        condition_count := (ad.condition_value->>'count')::INTEGER;
        SELECT COUNT(*) INTO user_province_count
        FROM public.user_site_marks m
        JOIN public.heritage_sites s ON m.site_id = s.id
        WHERE m.user_id = p_user_id AND m.mark_type = 'visited' AND s.province = condition_province;
        IF user_province_count >= condition_count THEN
          INSERT INTO public.user_achievements (user_id, achievement_id)
          VALUES (p_user_id, ad.id);
          achievement_id := ad.id;
          achievement_code := ad.code;
          achievement_name := ad.name;
          RETURN NEXT;
        END IF;

      WHEN 'province_complete' THEN
        condition_province := ad.condition_value->>'province';
        SELECT COUNT(*) INTO province_total
        FROM public.heritage_sites WHERE province = condition_province;
        SELECT COUNT(*) INTO user_province_count
        FROM public.user_site_marks m
        JOIN public.heritage_sites s ON m.site_id = s.id
        WHERE m.user_id = p_user_id AND m.mark_type = 'visited' AND s.province = condition_province;
        IF province_total > 0 AND user_province_count >= province_total THEN
          INSERT INTO public.user_achievements (user_id, achievement_id)
          VALUES (p_user_id, ad.id);
          achievement_id := ad.id;
          achievement_code := ad.code;
          achievement_name := ad.name;
          RETURN NEXT;
        END IF;

      WHEN 'city_complete' THEN
        condition_province := ad.condition_value->>'province';
        condition_city := ad.condition_value->>'city';
        SELECT COUNT(*) INTO city_total
        FROM public.heritage_sites WHERE province = condition_province AND city = condition_city;
        SELECT COUNT(*) INTO user_city_count
        FROM public.user_site_marks m
        JOIN public.heritage_sites s ON m.site_id = s.id
        WHERE m.user_id = p_user_id AND m.mark_type = 'visited'
          AND s.province = condition_province AND s.city = condition_city;
        IF city_total > 0 AND user_city_count >= city_total THEN
          INSERT INTO public.user_achievements (user_id, achievement_id)
          VALUES (p_user_id, ad.id);
          achievement_id := ad.id;
          achievement_code := ad.code;
          achievement_name := ad.name;
          RETURN NEXT;
        END IF;

      WHEN 'district_complete' THEN
        condition_province := ad.condition_value->>'province';
        condition_city := ad.condition_value->>'city';
        condition_district := ad.condition_value->>'district';
        SELECT COUNT(*) INTO district_total
        FROM public.heritage_sites
        WHERE province = condition_province AND city = condition_city AND district = condition_district;
        SELECT COUNT(*) INTO user_district_count
        FROM public.user_site_marks m
        JOIN public.heritage_sites s ON m.site_id = s.id
        WHERE m.user_id = p_user_id AND m.mark_type = 'visited'
          AND s.province = condition_province AND s.city = condition_city AND s.district = condition_district;
        IF district_total > 0 AND user_district_count >= district_total THEN
          INSERT INTO public.user_achievements (user_id, achievement_id)
          VALUES (p_user_id, ad.id);
          achievement_id := ad.id;
          achievement_code := ad.code;
          achievement_name := ad.name;
          RETURN NEXT;
        END IF;

      WHEN 'category_count' THEN
        condition_category := ad.condition_value->>'category';
        condition_count := (ad.condition_value->>'count')::INTEGER;
        SELECT COUNT(*) INTO user_category_count
        FROM public.user_site_marks m
        JOIN public.heritage_sites s ON m.site_id = s.id
        WHERE m.user_id = p_user_id AND m.mark_type = 'visited' AND s.category = condition_category;
        IF user_category_count >= condition_count THEN
          INSERT INTO public.user_achievements (user_id, achievement_id)
          VALUES (p_user_id, ad.id);
          achievement_id := ad.id;
          achievement_code := ad.code;
          achievement_name := ad.name;
          RETURN NEXT;
        END IF;

    END CASE;
  END LOOP;

  RETURN;
END;
$$;

-- 标记变化时自动检查成就
CREATE OR REPLACE FUNCTION public.trigger_check_achievements()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  IF NEW.mark_type = 'visited' THEN
    PERFORM public.check_and_grant_achievements(NEW.user_id);
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER check_achievements_on_mark
  AFTER INSERT OR UPDATE ON user_site_marks
  FOR EACH ROW EXECUTE FUNCTION public.trigger_check_achievements();

COMMENT ON TABLE achievement_definitions IS '成就定义表';
COMMENT ON TABLE user_achievements IS '用户已解锁的成就';
COMMENT ON FUNCTION public.check_and_grant_achievements IS '检查并授予用户满足条件的成就';
