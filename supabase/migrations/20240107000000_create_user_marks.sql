-- 创建 user_site_marks 表，存储用户对文保单位的标记（去过/想去）
CREATE TABLE user_site_marks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  site_id UUID NOT NULL REFERENCES heritage_sites(id) ON DELETE CASCADE,
  mark_type TEXT NOT NULL CHECK (mark_type IN ('visited', 'wishlist')),
  visited_at DATE,                -- 去过的日期（仅 visited 类型使用）
  visited_note TEXT,              -- 备注
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, site_id)       -- 每个用户对每个文保单位只能有一个标记
);

-- 创建索引
CREATE INDEX idx_user_site_marks_user_id ON user_site_marks(user_id);
CREATE INDEX idx_user_site_marks_site_id ON user_site_marks(site_id);
CREATE INDEX idx_user_site_marks_mark_type ON user_site_marks(mark_type);
CREATE INDEX idx_user_site_marks_user_type ON user_site_marks(user_id, mark_type);

-- 启用 RLS
ALTER TABLE user_site_marks ENABLE ROW LEVEL SECURITY;

-- RLS 策略：所有人可以查看标记（用于显示"N人去过"）
CREATE POLICY "user_site_marks_select_policy" ON user_site_marks
  FOR SELECT USING (true);

-- RLS 策略：用户只能插入自己的标记
CREATE POLICY "user_site_marks_insert_policy" ON user_site_marks
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS 策略：用户只能更新自己的标记
CREATE POLICY "user_site_marks_update_policy" ON user_site_marks
  FOR UPDATE USING (auth.uid() = user_id);

-- RLS 策略：用户只能删除自己的标记
CREATE POLICY "user_site_marks_delete_policy" ON user_site_marks
  FOR DELETE USING (auth.uid() = user_id);

-- 创建触发器：更新 updated_at 字段
CREATE TRIGGER update_user_site_marks_updated_at
  BEFORE UPDATE ON user_site_marks
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- 创建函数：更新 profiles 中的统计缓存
CREATE OR REPLACE FUNCTION public.update_profile_mark_counts()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  target_user_id UUID;
BEGIN
  -- 确定要更新的用户 ID
  IF TG_OP = 'DELETE' THEN
    target_user_id := OLD.user_id;
  ELSE
    target_user_id := NEW.user_id;
  END IF;

  -- 更新统计缓存
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

-- 创建触发器：插入/更新/删除标记时更新统计
CREATE TRIGGER update_profile_counts_on_mark_change
  AFTER INSERT OR UPDATE OR DELETE ON user_site_marks
  FOR EACH ROW EXECUTE FUNCTION public.update_profile_mark_counts();

-- 创建视图：文保单位的标记统计（方便前端查询）
CREATE OR REPLACE VIEW site_mark_stats AS
SELECT
  site_id,
  COUNT(*) FILTER (WHERE mark_type = 'visited') AS visited_count,
  COUNT(*) FILTER (WHERE mark_type = 'wishlist') AS wishlist_count
FROM user_site_marks
GROUP BY site_id;

-- 添加注释
COMMENT ON TABLE user_site_marks IS '用户对文保单位的标记（去过/想去）';
COMMENT ON COLUMN user_site_marks.mark_type IS '标记类型：visited（去过）或 wishlist（想去）';
COMMENT ON COLUMN user_site_marks.visited_at IS '去过的日期，仅 visited 类型使用';
COMMENT ON COLUMN user_site_marks.visited_note IS '用户备注';
