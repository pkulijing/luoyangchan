# 部署计划：Vercel + Supabase Cloud

## 整体架构

```
用户 → Vercel (Next.js 前端+API) → Supabase Cloud (数据库+Auth+Storage)
                                  → 天地图 (底图瓦片)
```

## 需要的外部服务

| 服务 | 用途 | 费用 |
|------|------|------|
| Supabase Cloud | 数据库 + Auth + Storage | 免费计划：500MB DB, 1GB Storage, 50K MAU |
| Vercel | 前端托管 + 边缘部署 | 免费计划：100GB 带宽/月 |
| Resend | SMTP 邮件（登录验证码） | 免费：3000 封/月 |

## 部署步骤

### 1. Supabase Cloud

1. 创建项目，获取 URL / anon key / service role key
2. `supabase link` 关联远程项目
3. `supabase db push` 推送 migrations
4. 运行 seed 脚本导入数据
5. Dashboard 配置 Auth（Site URL、Redirect URLs）
6. Dashboard 配置 SMTP（Resend）
7. 创建 `site-images` storage bucket

### 2. Resend 邮件

- 注册 Resend，获取 API Key
- 在 Supabase Dashboard → Auth → SMTP Settings 配置：
  - Host: `smtp.resend.com`, Port: `465`
  - User: `resend`, Password: API Key
  - Sender: `noreply@resend.dev`（无自定义域名时用共享域名）

### 3. Vercel 部署

- Vercel Dashboard 导入 GitHub 仓库
- master 分支 push 自动部署（Vercel 默认行为）
- 在 Environment Variables 面板配置生产环境变量

### 4. Vercel 环境变量

**必需（Production）**：
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `NEXT_PUBLIC_TIANDITU_TK`

**可选**：
- `NEXT_PUBLIC_USE_BAIKE_IMAGES=true`

**不需要配到 Vercel**（仅本地脚本）：
- `AMAP_GEOCODING_KEY`、`TENCENT_MAP_KEY`、`DEEPSEEK_API_KEY` 等

## 代码改动

- 更新 `.env.example` 注释，区分部署必需 vs 仅本地脚本
- 无前端代码改动（已确认无 localhost 硬编码）
