-- 修复 check_and_grant_achievements 函数中 achievement_id 列名歧义
-- RETURNS TABLE 的输出列名与 user_achievements 表的列名冲突

DROP FUNCTION IF EXISTS public.check_and_grant_achievements(UUID);

CREATE OR REPLACE FUNCTION public.check_and_grant_achievements(p_user_id UUID)
RETURNS TABLE(out_achievement_id UUID, out_achievement_code TEXT, out_achievement_name TEXT)
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
      SELECT 1 FROM public.user_achievements ua
      WHERE ua.user_id = p_user_id AND ua.achievement_id = ad.id
    ) THEN
      CONTINUE;
    END IF;

    CASE ad.condition_type
      WHEN 'total_count' THEN
        condition_count := (ad.condition_value->>'count')::INTEGER;
        IF user_visited_count >= condition_count THEN
          INSERT INTO public.user_achievements (user_id, achievement_id)
          VALUES (p_user_id, ad.id);
          out_achievement_id := ad.id;
          out_achievement_code := ad.code;
          out_achievement_name := ad.name;
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
          out_achievement_id := ad.id;
          out_achievement_code := ad.code;
          out_achievement_name := ad.name;
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
          out_achievement_id := ad.id;
          out_achievement_code := ad.code;
          out_achievement_name := ad.name;
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
          out_achievement_id := ad.id;
          out_achievement_code := ad.code;
          out_achievement_name := ad.name;
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
          out_achievement_id := ad.id;
          out_achievement_code := ad.code;
          out_achievement_name := ad.name;
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
          out_achievement_id := ad.id;
          out_achievement_code := ad.code;
          out_achievement_name := ad.name;
          RETURN NEXT;
        END IF;

    END CASE;
  END LOOP;

  RETURN;
END;
$$;
