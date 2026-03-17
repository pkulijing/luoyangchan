# 洛阳铲 - 项目说明

全国重点文物保护单位地图浏览工具。用户可在地图上探索 5000+ 文保单位，按省份、类型、时代筛选，查看详情。

## 技术栈

### 前端

- **Next.js 16** (App Router) + **React 19** + **TypeScript 5**
- **Tailwind CSS v4** 样式
- **shadcn/ui** 组件库（Button、Badge、Card、Select、Input 等）
- **高德地图 JS API 2.0**（`@amap/amap-jsapi-loader`）：地图渲染、MarkerCluster 聚合
- `coordtransform`：WGS-84 ↔ GCJ-02 坐标系转换（Wikipedia 数据为 WGS-84，高德地图使用 GCJ-02）

### 数据库

- **Supabase**（本地 Docker 开发，通过 Supabase CLI 管理）
- PostgreSQL + **PostGIS** 扩展（空间查询）
- 本地连接：`http://127.0.0.1:54321`，Studio：`http://127.0.0.1:54323`

### 数据采集（Python 脚本）

- **Python 3.12** + **uv** 管理依赖（不使用 pip/pip3）
- `requests` + `beautifulsoup4`
- `scripts/scrape_wikipedia.py`：从中文 Wikipedia 爬取文保单位列表
- `scripts/fetch_coordinates.py`：通过 Wikipedia API `prop=coordinates` 批量获取坐标
- `scripts/seed_supabase.py`：将数据导入本地 Supabase

## 目录结构

```
src/
├── app/
│   ├── page.tsx              # 首页（Server Component，fetch 全量数据）
│   └── site/[id]/page.tsx    # 详情页（Server Component）
├── components/
│   ├── MapView.tsx           # 地图主视图（Client Component）
│   ├── map/                  # AMapContainer、SiteMap
│   ├── filters/              # FilterPanel
│   └── site/                 # BackButton
├── hooks/
│   └── useFilters.ts         # 筛选逻辑（省份/类型/时代/搜索）
└── lib/
    ├── supabase/
    │   ├── client.ts         # 浏览器端 Supabase 客户端
    │   ├── server.ts         # 服务端 Supabase 客户端
    │   └── queries.ts        # getAllSites()、getSiteById()
    ├── types.ts              # HeritageSite、SiteListItem、FilterState 等
    ├── constants.ts          # 类别颜色、省份列表、批次年份、地图默认中心
    └── amap.ts               # AMap 加载单例

scripts/
├── scrape_wikipedia.py
├── fetch_coordinates.py
└── seed_supabase.py

supabase/
├── config.toml
└── migrations/
    └── 20240101000000_create_heritage_sites.sql
```

## 本地开发

```bash
# 启动本地 Supabase（需 Docker）
supabase start

# 启动前端
npm run dev

# 数据采集（首次或更新数据时）
cd scripts
uv run python scrape_wikipedia.py
uv run python fetch_coordinates.py
uv run python seed_supabase.py --url http://127.0.0.1:54321 --key <service_role_key>
```

## 环境变量

`.env.local`（不提交到 git）：

```
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<publishable key>
SUPABASE_SERVICE_ROLE_KEY=<secret key>
NEXT_PUBLIC_AMAP_KEY=<高德地图 JS API Key>
NEXT_PUBLIC_AMAP_SECRET=<高德地图安全密钥>
```

## 数据现状

- 文保单位总数：4303 条（第 1-8 批）
- 有坐标（来自 Wikipedia）：约 710 条（16%）
- 待补充：通过高德地理编码 API 补全剩余约 3600 条的坐标
