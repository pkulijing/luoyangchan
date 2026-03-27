-- 修复 Supabase Security Advisor 报告的问题
-- 1. site_mark_stats 视图使用了 SECURITY DEFINER
-- 2. spatial_ref_sys 表（PostGIS）没有启用 RLS

-- ============================================
-- 修复 1: site_mark_stats 视图
-- 重新创建视图，显式设置 SECURITY INVOKER
-- ============================================
DROP VIEW IF EXISTS site_mark_stats;

CREATE VIEW site_mark_stats
WITH (security_invoker = true)
AS
SELECT
  site_id,
  COUNT(*) FILTER (WHERE mark_type = 'visited') AS visited_count,
  COUNT(*) FILTER (WHERE mark_type = 'wishlist') AS wishlist_count
FROM user_site_marks
GROUP BY site_id;

COMMENT ON VIEW site_mark_stats IS '文保单位标记统计（去过/想去人数）';

-- spatial_ref_sys 是 PostGIS 系统表，由扩展自身管理，不需要手动启用 RLS
