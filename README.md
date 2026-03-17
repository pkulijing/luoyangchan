# 洛阳铲

全国重点文物保护单位地图浏览工具。

用户可在地图上探索文保单位，按省份、类型、时代筛选，并查看详情页。

## 功能概览

- 地图浏览全国文保单位
- 按省份、类型、时代、关键词筛选
- 点击地图点位查看信息卡片与详情页
- 详情页展示单个文保单位信息与位置

## 技术栈

### 前端

- Next.js 16（App Router）
- React 19 + TypeScript 5
- Tailwind CSS v4
- shadcn/ui
- 高德地图 JS API 2.0（@amap/amap-jsapi-loader）

### 数据与后端

- Supabase（PostgreSQL + PostGIS）
- Supabase CLI + Docker 本地开发

### 数据采集脚本

- Python 3.12
- uv（依赖与执行）
- requests + beautifulsoup4

## 快速开始

### 1. 安装前端依赖

```bash
npm install
```

### 2. 配置环境变量

复制 .env.example 为 .env.local，并填写以下变量：

- NEXT_PUBLIC_SUPABASE_URL
- NEXT_PUBLIC_SUPABASE_ANON_KEY
- SUPABASE_SERVICE_ROLE_KEY
- NEXT_PUBLIC_AMAP_KEY
- NEXT_PUBLIC_AMAP_SECRET

### 3. 启动本地 Supabase

```bash
supabase start
```

默认地址：

- API: http://127.0.0.1:54321
- Studio: http://127.0.0.1:54323

### 4. 启动前端开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

## 数据采集与导入

在 scripts 目录下执行：

```bash
cd scripts
uv run python scrape_wikipedia.py
uv run python fetch_coordinates.py
uv run python seed_supabase.py --url http://127.0.0.1:54321 --key <service_role_key>
```

## 常用命令

```bash
npm run dev
npm run lint
npm run build
```

## 目录结构

```text
src/
  app/
    page.tsx
    site/[id]/page.tsx
  components/
    MapView.tsx
    map/AMapContainer.tsx
    map/SiteMap.tsx
    filters/FilterPanel.tsx
  hooks/useFilters.ts
  lib/
    amap.ts
    constants.ts
    types.ts
    supabase/
      queries.ts
      server.ts
      client.ts
scripts/
  scrape_wikipedia.py
  fetch_coordinates.py
  seed_supabase.py
supabase/
  migrations/
```

## 当前状态

- 文保单位数据已入库
- 地图点位支持筛选与点击查看
- 地图渲染采用客户端加载，避免服务端渲染冲突
