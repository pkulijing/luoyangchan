# 洛阳铲个性化功能实现计划

## 概述

为洛阳铲项目添加用户系统和个性化功能，包括：
- 用户登录（邮箱验证码 + Google OAuth）
- 用户信息维护（头像、昵称、简介、个人主页）
- 标记去过/想去
- 成就系统

## 技术方案

### 认证方案
| 场景 | 方案 | 说明 |
|------|------|------|
| 海外用户 | Google OAuth | Supabase 原生支持 |
| 国内用户 | 邮箱验证码 | Supabase Magic Link/OTP |
| 通用 | 邮箱验证码 | 无需第三方资质，体验较好 |

### 关键技术点
- 使用 `@supabase/ssr` 进行 Next.js App Router 集成
- 创建独立的 `profiles` 表扩展用户信息
- 数据库触发器自动创建用户 profile
- RLS 策略保护用户数据

---

## 数据库设计

### 1. profiles 表
```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username TEXT UNIQUE,           -- 用户名（个人主页 URL）
  display_name TEXT,              -- 显示昵称
  avatar_url TEXT,                -- 头像 URL
  bio TEXT,                       -- 个人简介
  visited_count INTEGER DEFAULT 0,
  wishlist_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2. user_site_marks 表
```sql
CREATE TABLE user_site_marks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  site_id UUID NOT NULL REFERENCES heritage_sites(id) ON DELETE CASCADE,
  mark_type TEXT NOT NULL CHECK (mark_type IN ('visited', 'wishlist')),
  visited_at DATE,
  visited_note TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, site_id)
);
```

### 3. 成就相关表
- `achievement_definitions`: 成就定义（按省份/类别/总数）
- `user_achievements`: 用户已解锁成就

---

## 实现步骤

### 阶段一：基础设施

#### 1.1 数据库迁移
- [x] 创建 `profiles` 表及自动创建触发器
- [x] 创建 `user_site_marks` 表
- [x] 创建成就相关表
- [x] 配置 RLS 策略

**文件**:
- `supabase/migrations/20240106000000_create_profiles.sql`
- `supabase/migrations/20240107000000_create_user_marks.sql`
- `supabase/migrations/20240108000000_create_achievements.sql`

#### 1.2 认证配置
- [x] 配置 Google OAuth (config.toml)
- [x] 启用 Supabase Email OTP
- [x] 创建 OAuth 回调路由

**文件**:
- `supabase/config.toml` - 添加 Google OAuth 配置
- `src/app/auth/callback/route.ts` - OAuth 回调处理
- `src/app/auth/confirm/route.ts` - Email OTP 确认

#### 1.3 全局认证状态
- [x] 创建 `AuthProvider` 组件
- [x] 创建 `useAuth` hook
- [x] 在 `layout.tsx` 中添加 Provider

**文件**:
- `src/components/auth/AuthProvider.tsx`
- `src/app/layout.tsx` - 包装 AuthProvider

---

### 阶段二：登录功能

#### 2.1 登录组件
- [x] 创建 `LoginDialog` 组件（邮箱输入 + Google 按钮）
- [x] 创建 `UserMenu` 头像下拉菜单
- [ ] 实现地区检测逻辑（智能显示登录选项顺序）【暂缓】

**文件**:
- `src/components/auth/LoginDialog.tsx`
- `src/components/auth/UserMenu.tsx`
- `src/lib/auth/detectRegion.ts`

#### 2.2 集成到主界面
- [x] 在 FilterPanel 或 MapView 中添加登录入口
- [x] 处理登录状态变化

**文件**:
- `src/components/MapView.tsx` - 添加 UserMenu

---

### 阶段三：标记功能

#### 3.1 标记组件
- [x] 创建 `SiteMarkButton` 组件（去过/想去按钮）
- [x] 创建 `SiteMarkStats` 组件（N人去过统计）

**文件**:
- `src/components/site/SiteMarkButton.tsx`
- `src/components/site/SiteMarkStats.tsx`

#### 3.2 集成到详情面板
- [x] 在 `SiteDetailPanel` 中添加标记按钮
- [x] 显示标记统计

**文件**:
- `src/components/site/SiteDetailPanel.tsx` - 集成标记组件

#### 3.3 地图标记状态（可选）
- [ ] 在地图标记上显示用户标记状态（小圆点指示）

**文件**:
- `src/components/map/LeafletContainer.tsx`

---

### 阶段四：个人主页

#### 4.1 个人主页
- [x] 创建 `/user/[username]` 路由
- [x] 用户信息头部（头像、昵称、简介）
- [x] 统计卡片（省份分布、类别分布）
- [x] 去过/想去列表

**文件**:
- `src/app/user/[username]/page.tsx`
- `src/components/user/UserProfileHeader.tsx`
- `src/components/user/UserStatsGrid.tsx`

#### 4.2 设置页面
- [x] 创建 `/settings/profile` 路由
- [x] 头像上传（Supabase Storage）
- [x] 用户名、昵称、简介编辑

**文件**:
- `src/app/settings/profile/page.tsx`
- `src/components/settings/ProfileForm.tsx`

---

### 阶段五：成就系统

#### 5.1 成就数据
- [x] 设计成就定义，包含以下类型：
  - **进度型**：每省 10/50/100、每类别 20/50、总数 100/500/1000
  - **完成型**：某省全去过、某市全去过、某县全去过
- [x] 插入成就数据
- [x] 实现成就检查函数（需动态计算各地区总数）

**成就类型设计**:
| 类型 | 条件 JSON 示例 | 说明 |
|------|----------------|------|
| 省份进度 | `{"type":"province","province":"河南省","count":10}` | 去过河南省 10 个 |
| 省份全通 | `{"type":"province_complete","province":"河南省"}` | 去过河南省全部 |
| 城市全通 | `{"type":"city_complete","province":"河南省","city":"洛阳市"}` | 去过洛阳市全部 |
| 区县全通 | `{"type":"district_complete","province":"河南省","city":"洛阳市","district":"偃师区"}` | 去过偃师区全部 |
| 类别进度 | `{"type":"category","category":"古遗址","count":20}` | 去过 20 个古遗址 |
| 总数进度 | `{"type":"total","count":100}` | 总共去过 100 个 |

**文件**:
- `supabase/seed/achievements.sql`

#### 5.2 成就展示
- [x] 创建 `AchievementBadge` 组件
- [x] 在个人主页展示成就
- [x] 新成就解锁 Toast 提示组件
- [x] "全通"成就特殊展示（金色徽章）

**文件**:
- `src/components/achievements/AchievementBadge.tsx`
- `src/components/user/UserAchievements.tsx`

#### 5.3 成就稀有度设计
| 稀有度 | 颜色 | 典型成就 |
|--------|------|----------|
| common | 灰色 | 去过某省 10 个 |
| rare | 蓝色 | 去过某省 50 个、某县全通 |
| epic | 紫色 | 去过某省 100 个、某市全通 |
| legendary | 金色 | 某省全通、总数 1000 |

---

## 关键文件清单

### 需要修改的现有文件
| 文件 | 修改内容 |
|------|----------|
| `supabase/config.toml` | 添加 Google OAuth 配置 |
| `src/app/layout.tsx` | 添加 AuthProvider |
| `src/components/MapView.tsx` | 添加 UserMenu |
| `src/components/site/SiteDetailPanel.tsx` | 集成标记按钮 |
| `src/lib/types.ts` | 添加 Profile、Mark 等类型 |
| `.env.example` | 添加 Google OAuth 环境变量 |

### 需要创建的新文件
```
src/
├── app/
│   ├── auth/
│   │   ├── callback/route.ts      # OAuth 回调
│   │   └── confirm/route.ts       # Email 确认
│   ├── user/[username]/page.tsx   # 个人主页
│   └── settings/profile/page.tsx  # 设置页面
├── components/
│   ├── auth/
│   │   ├── AuthProvider.tsx
│   │   ├── LoginDialog.tsx
│   │   └── UserMenu.tsx
│   ├── site/
│   │   ├── SiteMarkButton.tsx
│   │   └── SiteMarkStats.tsx
│   ├── user/
│   │   ├── UserProfileHeader.tsx
│   │   ├── UserStatsGrid.tsx
│   │   └── UserAchievements.tsx
│   └── achievements/
│       └── AchievementBadge.tsx
└── lib/
    └── auth/
        └── detectRegion.ts

supabase/migrations/
├── 20240106000000_create_profiles.sql
├── 20240107000000_create_user_marks.sql
└── 20240108000000_create_achievements.sql
```

---

## 验证方案

### 功能测试
1. **登录流程**
   - 邮箱验证码登录（输入邮箱 → 收到验证码 → 验证成功）
   - Google OAuth 登录（点击按钮 → 跳转授权 → 回调成功）
   - 登出功能

2. **标记功能**
   - 未登录时点击标记 → 弹出登录框
   - 登录后点击"去过" → 按钮变绿、状态保存
   - 切换为"想去" → 状态更新
   - 取消标记 → 状态清除

3. **个人主页**
   - 访问 `/user/[username]` → 显示用户信息和统计
   - 编辑 profile → 信息更新

4. **成就系统**
   - 标记第 10 个河南省文保单位 → 触发成就解锁
   - 个人主页显示已解锁成就

### 本地测试命令
```bash
# 重置并启动 Supabase
supabase db reset
supabase start

# 导入数据
cd scripts && uv run python db/seed_supabase.py --clear

# 启动前端
npm run dev
```

---

## 注意事项

1. **坐标系规则不变**：用户标记不涉及坐标，继续遵守 GCJ-02 存储规则
2. **RLS 安全**：所有用户数据表必须启用 RLS，确保用户只能操作自己的数据
3. **性能考虑**：用户标记数据可能较大，考虑分页和缓存
4. **向后兼容**：不修改 heritage_sites 表结构
