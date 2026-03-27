-- 更新 handle_new_user 函数，自动从邮箱生成用户名
-- 规则：取邮箱 @ 前的部分，只保留小写字母、数字、下划线
-- 如果重复，则添加数字后缀（如 abc1, abc2）

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
  -- 从邮箱提取用户名基础部分
  -- 1. 取 @ 前面的部分
  -- 2. 转小写
  -- 3. 只保留字母、数字、下划线
  base_username := lower(regexp_replace(
    split_part(NEW.email, '@', 1),
    '[^a-z0-9_]', '', 'g'
  ));

  -- 如果为空（比如邮箱前缀全是特殊字符），使用 'user' 作为基础
  IF base_username = '' OR base_username IS NULL THEN
    base_username := 'user';
  END IF;

  -- 限制长度（为后缀留空间）
  IF length(base_username) > 15 THEN
    base_username := substring(base_username, 1, 15);
  END IF;

  -- 尝试找到一个不重复的用户名
  final_username := base_username;
  WHILE EXISTS (SELECT 1 FROM public.profiles WHERE username = final_username) LOOP
    suffix := suffix + 1;
    final_username := base_username || suffix::TEXT;
  END LOOP;

  -- 插入 profile
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

-- 添加注释
COMMENT ON FUNCTION public.handle_new_user IS '新用户注册时自动创建 profile，从邮箱生成唯一用户名';
