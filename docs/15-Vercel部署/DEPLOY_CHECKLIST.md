# 部署检查清单

## 一、Supabase Cloud 设置

- [x] 在 https://supabase.com 创建新项目（选择合适的 Region）
- [x] 记录以下凭据：
  - [x] Project URL (`NEXT_PUBLIC_SUPABASE_URL`)
  - [x] Anon Public Key (`NEXT_PUBLIC_SUPABASE_ANON_KEY`)
  - [x] Service Role Key (`SUPABASE_SERVICE_ROLE_KEY`)
- [x] 本地关联远程项目：
  ```bash
  supabase link --project-ref <your-project-ref>
  ```
- [x] 推送数据库 schema：
  ```bash
  supabase db push
  ```
- [x] 导入文保单位数据：
  ```bash
  cd scripts
  # 设置环境变量指向云端数据库，或修改脚本配置
  cd scripts
  env $(grep -v '^#' ../.env.cloud | xargs) uv run python db/seed_supabase.py
  ```
- [x] 创建 Storage bucket `site-images`（public, 5MiB limit, 仅图片类型）
- [x] 上传自托管图片到云端 Storage（2107 张 Wikimedia 图片）：
  ```bash
  cd scripts
  env $(grep -v '^#' ../.env.cloud | xargs) uv run python round6/download_to_supabase.py --from-local
  ```

## 二、Supabase Auth 配置

- [x] Dashboard → Authentication → URL Configuration：
  - Site URL: `https://<your-project>.vercel.app`
  - Redirect URLs: 添加 `https://<your-project>.vercel.app/**`
- [x] Dashboard → Authentication → Email Templates：检查验证码邮件模板
- [x] Dashboard → Authentication → SMTP Settings（如需自定义邮件）：
  - 启用 Custom SMTP
  - Host: `smtp.resend.com`
  - Port: `465`
  - Username: `resend`
  - Password: Resend API Key
  - Sender email: `noreply@resend.dev`（或自定义域名邮箱）
  - Sender name: `洛阳铲`

> 注意：不配置自定义 SMTP 时，Supabase 内置邮件限制为 4 封/小时。
> 生产环境建议配置 Resend SMTP。

## 三、Resend 邮件服务（可选但推荐）

- [x] 注册 https://resend.com
- [x] 获取 API Key
- [-] （可选）如有自定义域名，在 Resend 验证域名以获得更好的邮件送达率
- [x] 将 API Key 填入上方 Supabase SMTP 配置

## 四、Vercel 部署

- [x] 登录 https://vercel.com
- [x] New Project → Import Git Repository → 选择 `luoyangchan` 仓库
- [x] Framework Preset 确认为 Next.js
- [x] 配置 Environment Variables（Production 环境）：

  | 变量名                          | 值来源             |
  | ------------------------------- | ------------------ |
  | `NEXT_PUBLIC_SUPABASE_URL`      | Supabase Dashboard |
  | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase Dashboard |
  | `SUPABASE_SERVICE_ROLE_KEY`     | Supabase Dashboard |
  | `NEXT_PUBLIC_AMAP_KEY`          | 高德 JS API Key    |
  | `NEXT_PUBLIC_AMAP_SECRET`       | 高德安全密钥       |
  | `NEXT_PUBLIC_TIANDITU_TK`       | 天地图控制台       |
  | `NEXT_PUBLIC_USE_BAIKE_IMAGES`  | `true`             |

- [x] 点击 Deploy，等待首次构建完成
- [x] 记录 Vercel 分配的域名（`<project>.vercel.app`）

## 五、部署后验证

- [ ] 访问生产 URL，确认地图正常加载（天地图瓦片 + 文保单位标记）
- [ ] 测试筛选功能（省市县、类型、批次）
- [ ] 测试文保单位详情页
- [ ] 测试邮箱登录：发送验证码 → 收到邮件 → 输入验证码 → 登录成功
- [ ] 登录后测试：用户标记（想去/已去）、个人主页
- [ ] 检查百度百科图片加载是否正常

## 六、后续（可选）

- [ ] 绑定自定义域名（Vercel → Domains）
- [ ] 更新 Supabase Auth 的 Site URL 和 Redirect URLs 为自定义域名
- [ ] 在 Resend 验证自定义域名，更新发件地址
- [ ] 配置 Google OAuth 的回调 URL（如启用）
