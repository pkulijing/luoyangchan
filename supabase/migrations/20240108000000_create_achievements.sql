-- 创建成就定义表
CREATE TABLE achievement_definitions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT UNIQUE NOT NULL,      -- 成就代码，用于前端展示和识别
  name TEXT NOT NULL,             -- 成就名称
  description TEXT NOT NULL,      -- 成就描述
  icon TEXT,                      -- 成就图标（emoji 或图标名称）
  rarity TEXT NOT NULL CHECK (rarity IN ('common', 'rare', 'epic', 'legendary')),
  condition_type TEXT NOT NULL CHECK (condition_type IN (
    'province_count',      -- 省份进度：去过某省 N 个
    'province_complete',   -- 省份全通：去过某省全部
    'city_complete',       -- 城市全通：去过某市全部
    'district_complete',   -- 区县全通：去过某区县全部
    'category_count',      -- 类别进度：去过某类别 N 个
    'total_count'          -- 总数进度：总共去过 N 个
  )),
  condition_value JSONB NOT NULL, -- 条件参数，如 {"province": "河南省", "count": 10}
  points INTEGER DEFAULT 10,      -- 成就积分
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_achievement_definitions_code ON achievement_definitions(code);
CREATE INDEX idx_achievement_definitions_condition_type ON achievement_definitions(condition_type);
CREATE INDEX idx_achievement_definitions_rarity ON achievement_definitions(rarity);

-- 创建用户成就表
CREATE TABLE user_achievements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  achievement_id UUID NOT NULL REFERENCES achievement_definitions(id) ON DELETE CASCADE,
  unlocked_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, achievement_id)
);

-- 创建索引
CREATE INDEX idx_user_achievements_user_id ON user_achievements(user_id);
CREATE INDEX idx_user_achievements_achievement_id ON user_achievements(achievement_id);
CREATE INDEX idx_user_achievements_unlocked_at ON user_achievements(unlocked_at);

-- 启用 RLS
ALTER TABLE achievement_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_achievements ENABLE ROW LEVEL SECURITY;

-- RLS 策略：所有人可以查看成就定义
CREATE POLICY "achievement_definitions_select_policy" ON achievement_definitions
  FOR SELECT USING (true);

-- RLS 策略：所有人可以查看用户成就（公开展示）
CREATE POLICY "user_achievements_select_policy" ON user_achievements
  FOR SELECT USING (true);

-- RLS 策略：用户成就只能由系统插入（通过函数）
-- 使用 service_role 或 security definer 函数来插入

-- 创建函数：检查并授予成就
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
  -- 获取用户的总去过数量
  SELECT COUNT(*) INTO user_visited_count
  FROM public.user_site_marks
  WHERE user_id = p_user_id AND mark_type = 'visited';

  -- 遍历所有成就定义
  FOR ad IN SELECT * FROM public.achievement_definitions LOOP
    -- 检查用户是否已经拥有该成就
    IF EXISTS (
      SELECT 1 FROM public.user_achievements
      WHERE user_id = p_user_id AND achievement_id = ad.id
    ) THEN
      CONTINUE;
    END IF;

    -- 根据条件类型检查是否满足
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
        -- 获取该省总数
        SELECT COUNT(*) INTO province_total
        FROM public.heritage_sites WHERE province = condition_province;
        -- 获取用户去过的该省数量
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
        -- 获取该市总数
        SELECT COUNT(*) INTO city_total
        FROM public.heritage_sites WHERE province = condition_province AND city = condition_city;
        -- 获取用户去过的该市数量
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
        -- 获取该区县总数
        SELECT COUNT(*) INTO district_total
        FROM public.heritage_sites
        WHERE province = condition_province AND city = condition_city AND district = condition_district;
        -- 获取用户去过的该区县数量
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

-- 创建触发器：当用户标记变化时自动检查成就
CREATE OR REPLACE FUNCTION public.trigger_check_achievements()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  -- 仅在标记为 visited 时检查成就
  IF NEW.mark_type = 'visited' THEN
    PERFORM public.check_and_grant_achievements(NEW.user_id);
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER check_achievements_on_mark
  AFTER INSERT OR UPDATE ON user_site_marks
  FOR EACH ROW EXECUTE FUNCTION public.trigger_check_achievements();

-- 添加注释
COMMENT ON TABLE achievement_definitions IS '成就定义表';
COMMENT ON COLUMN achievement_definitions.code IS '成就代码，用于前端识别';
COMMENT ON COLUMN achievement_definitions.rarity IS '稀有度：common/rare/epic/legendary';
COMMENT ON COLUMN achievement_definitions.condition_type IS '条件类型';
COMMENT ON COLUMN achievement_definitions.condition_value IS '条件参数 JSON';

COMMENT ON TABLE user_achievements IS '用户已解锁的成就';
COMMENT ON FUNCTION public.check_and_grant_achievements IS '检查并授予用户满足条件的成就';
