-- 创建 profiles 表，存储用户扩展信息
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username TEXT UNIQUE,           -- 用户名（用于个人主页 URL，如 /user/zhangsan）
  display_name TEXT,              -- 显示昵称
  avatar_url TEXT,                -- 头像 URL
  bio TEXT,                       -- 个人简介
  visited_count INTEGER DEFAULT 0,  -- 去过的文保单位数量（缓存字段，提高查询性能）
  wishlist_count INTEGER DEFAULT 0, -- 想去的文保单位数量（缓存字段）
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建 username 索引，加速查询
CREATE INDEX idx_profiles_username ON profiles(username);

-- 启用 RLS（Row Level Security）
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- RLS 策略：所有人可以查看 profiles
CREATE POLICY "profiles_select_policy" ON profiles
  FOR SELECT USING (true);

-- RLS 策略：用户只能更新自己的 profile
CREATE POLICY "profiles_update_policy" ON profiles
  FOR UPDATE USING (auth.uid() = id);

-- RLS 策略：用户只能删除自己的 profile（实际上不太会用到）
CREATE POLICY "profiles_delete_policy" ON profiles
  FOR DELETE USING (auth.uid() = id);

-- RLS 策略：允许插入（由触发器完成，需要 service_role）
-- 注意：触发器使用 security definer，所以不需要单独的 insert 策略
CREATE POLICY "profiles_insert_policy" ON profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

-- 创建函数：当新用户注册时自动创建 profile
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.profiles (id, display_name, avatar_url)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
    NEW.raw_user_meta_data->>'avatar_url'
  );
  RETURN NEW;
END;
$$;

-- 创建触发器：在 auth.users 插入新记录后触发
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 创建函数：自动更新 updated_at 字段
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- 创建触发器：更新 profile 时自动更新 updated_at
CREATE TRIGGER update_profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- 添加注释
COMMENT ON TABLE profiles IS '用户扩展信息表，与 auth.users 一对一关联';
COMMENT ON COLUMN profiles.username IS '用户名，用于个人主页 URL';
COMMENT ON COLUMN profiles.display_name IS '显示昵称';
COMMENT ON COLUMN profiles.avatar_url IS '头像 URL';
COMMENT ON COLUMN profiles.bio IS '个人简介';
COMMENT ON COLUMN profiles.visited_count IS '去过的文保单位数量（缓存）';
COMMENT ON COLUMN profiles.wishlist_count IS '想去的文保单位数量（缓存）';
