# 需求：Vercel 部署准备

## 背景

项目核心功能开发完成，需要部署上线供用户使用。

## 需求

1. 梳理部署所需的外部服务（Supabase Cloud、邮件服务、Vercel）
2. 明确 Vercel 环境变量配置方式（区别于本地 `.env.local`）
3. 实现 GitHub master 分支 push 自动部署
4. 输出完整的部署检查清单，方便后续操作

## 约束

- 先用 Vercel 部署，后续考虑迁回国内
- 暂无自定义域名，使用 Vercel 默认域名
- 邮件服务用于 Supabase Auth 发送登录验证码
