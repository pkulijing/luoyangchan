-- 修复 RLS 策略性能问题
-- 将 auth.uid() 改为 (select auth.uid()) 避免每行重复计算

-- ============================================
-- profiles 表的 RLS 策略
-- ============================================
DROP POLICY IF EXISTS "profiles_update_policy" ON profiles;
DROP POLICY IF EXISTS "profiles_delete_policy" ON profiles;
DROP POLICY IF EXISTS "profiles_insert_policy" ON profiles;

CREATE POLICY "profiles_update_policy" ON profiles
  FOR UPDATE USING ((select auth.uid()) = id);

CREATE POLICY "profiles_delete_policy" ON profiles
  FOR DELETE USING ((select auth.uid()) = id);

CREATE POLICY "profiles_insert_policy" ON profiles
  FOR INSERT WITH CHECK ((select auth.uid()) = id);

-- ============================================
-- user_site_marks 表的 RLS 策略
-- ============================================
DROP POLICY IF EXISTS "user_site_marks_insert_policy" ON user_site_marks;
DROP POLICY IF EXISTS "user_site_marks_update_policy" ON user_site_marks;
DROP POLICY IF EXISTS "user_site_marks_delete_policy" ON user_site_marks;

CREATE POLICY "user_site_marks_insert_policy" ON user_site_marks
  FOR INSERT WITH CHECK ((select auth.uid()) = user_id);

CREATE POLICY "user_site_marks_update_policy" ON user_site_marks
  FOR UPDATE USING ((select auth.uid()) = user_id);

CREATE POLICY "user_site_marks_delete_policy" ON user_site_marks
  FOR DELETE USING ((select auth.uid()) = user_id);
