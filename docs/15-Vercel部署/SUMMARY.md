# 开发总结：Vercel 部署准备

## 开发项背景

项目核心功能开发完成，需要部署上线。采用 Vercel + Supabase Cloud 方案，通过 GitHub master 分支 push 自动部署。

## 实现方案

### 关键设计

- **架构**：Vercel（Next.js 前端+API）→ Supabase Cloud（数据库+Auth+Storage）→ 天地图（底图）
- **邮件系统**：不需要独立搭建，Supabase Auth 内置验证码功能，配置 Resend 作为 SMTP 即可
- **环境变量**：生产环境在 Vercel Dashboard 设置，不是 `.env.local`
- **自动部署**：Vercel 导入 GitHub 仓库后，master push 自动部署是默认行为

### 开发内容

1. **`.env.example` 更新**：按用途分组（前端部署必需 / 仅本地脚本 / 遗留变量），方便部署时快速识别需要配置的变量
2. **部署检查清单**（`DEPLOY_CHECKLIST.md`）：完整的分步操作指南，覆盖 Supabase Cloud、Resend 邮件、Vercel 部署、部署后验证

### 额外发现

- `.env.example` 中有遗留的高德 JS API 变量（`NEXT_PUBLIC_MAP_PROVIDER`、`NEXT_PUBLIC_AMAP_KEY`、`NEXT_PUBLIC_AMAP_SECRET`），对应代码 `src/lib/mapProvider.ts` 和 `src/lib/amap.ts` 已无引用，属于迁移天地图后的残留

## 局限性

- 本轮仅做准备工作（文档+配置），实际部署需要人工在各平台操作
- 未处理高德 JS API 遗留代码的清理
- Resend 无自定义域名时发件地址为 `noreply@resend.dev`，邮件送达率可能较低

## 后续 TODO

- [ ] 按检查清单执行实际部署
- [ ] 清理高德 JS API 遗留代码（`mapProvider.ts`、`amap.ts`）
- [ ] 获取自定义域名后更新 Supabase Auth URL 和 Resend 发件域名
- [ ] 考虑国内部署方案（迁回国内时的技术选型）
