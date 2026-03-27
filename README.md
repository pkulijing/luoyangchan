# 洛阳铲

全国重点文物保护单位地图浏览工具。在地图上探索 5000+ 国保单位，按省市县、类型筛选，查看详情，标记你去过的地方。

## 功能

- **地图浏览**：基于 Leaflet + 天地图的交互式地图，MarkerCluster 聚合，按类别显示图标
- **多维筛选**：省/市/县三级联动、类型筛选、关键词搜索、标记状态筛选
- **详情展示**：侧边面板查看文保单位信息、图片、位置
- **用户系统**：登录后可标记"想去/去过"，查看个人主页和成就统计

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js 16 (App Router) + React 19 + TypeScript 5 |
| 样式 | Tailwind CSS v4 + shadcn/ui |
| 地图 | Leaflet 1.9 + leaflet.markercluster，天地图 WMTS 底图 |
| 坐标 | 数据库存 GCJ-02，前端通过 `coordtransform` 转 WGS-84 显示 |
| 后端 | Supabase (PostgreSQL + Auth + Storage) |
| 数据采集 | Python 3.12 + uv，Wikipedia/百度百科抓取，高德/腾讯地图 geocoding，DeepSeek 描述生成 |

## 快速开始

### 前置依赖

- Node.js 20+
- Docker（运行本地 Supabase）
- [Supabase CLI](https://supabase.com/docs/guides/cli)
- Python 3.12 + [uv](https://docs.astral.sh/uv/)（仅数据采集脚本需要）

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env.local
```

按注释填写各项 Key，至少需要 Supabase 和天地图的配置。

### 3. 启动本地 Supabase

```bash
supabase start
```

启动后：API `http://127.0.0.1:54321`，Studio `http://127.0.0.1:54323`

### 4. 导入数据

```bash
cd scripts
uv run python db/seed_heritage_sites.py
```

### 5. 启动前端

```bash
npm run dev
```

访问 http://localhost:3000

## 目录结构

```
src/
  app/
    page.tsx              # 首页（地图）
    site/[releaseId]/     # 文保单位详情页
    user/[username]/      # 用户个人主页
    settings/profile/     # 个人设置
    api/                  # API Routes
  components/
    map/                  # 地图相关组件 (Leaflet)
    filters/              # 筛选面板
    site/                 # 文保单位详情组件
    user/                 # 用户相关组件
    achievements/         # 成就徽章
  lib/                    # 工具函数、类型、Supabase 客户端
scripts/
  db/                     # 数据导入/更新脚本
  round1~7/              # 各轮数据采集脚本
supabase/
  migrations/             # 数据库迁移
docs/                     # 开发文档（需求、计划、总结）
```

## 开发方式

本项目采用人类 + AI 协作开发模式。`docs/` 目录下按开发轮次记录了每轮的需求 (`PROMPT.md`)、计划 (`PLAN.md`) 和总结 (`SUMMARY.md`)。

## License

MIT
