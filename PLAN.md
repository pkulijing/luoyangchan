# "洛阳铲" - 全国重点文物保护单位信息展示工具 - 第一阶段实现方案

## Context

用户是中国历史爱好者，每到一座城市都需要手动搜索当地文保单位、做旅行规划，且游览记录散落各处。本项目旨在构建一个地图驱动的文保单位信息展示平台，第一阶段目标是实现 **地图展示 + 基础筛选 + 详情页** 的 MVP。

## 技术栈

- **前端**: Next.js (App Router) + TypeScript + Tailwind CSS + shadcn/ui
- **地图**: 高德地图 JS API 2.0 (中国地图合规、国内CDN快、免费额度充足)
- **数据库**: Supabase (PostgreSQL + PostGIS)
- **部署**: Vercel + Supabase 免费 tier
- **数据采集脚本**: Python

## 实施步骤

### Step 1: 数据准备

**目标**: 获取全国 5000+ 文保单位的结构化数据和坐标

1. **编写 Wikipedia 爬虫** (`scripts/scrape_wikipedia.py`)
   - 解析中文 Wikipedia 各省份的文保单位列表页面 (共 8 批)
   - 提取字段: 编号、名称、类型、时代、地址、省份、城市、批次
   - 输出 JSON 文件

2. **获取坐标** (`scripts/fetch_coordinates.py`)
   - 优先: Wikidata SPARQL 查询 `P625` 坐标 (覆盖率约 40-60%)
   - 补充: 高德地理编码 API 将地址转坐标

3. **坐标系转换** (`scripts/transform_coords.py`)
   - WGS-84 (Wikipedia) -> GCJ-02 (高德地图)
   - 使用 `coordtransform` 或 Python `eviltransform` 库

4. **导入 Supabase** (`scripts/seed_supabase.py`)
   - MVP 先导入 **河南省 + 北京市** 数据 (~400条) 验证
   - 验证通过后导入全量数据

### Step 2: 数据库设计 (Supabase)

核心表 `heritage_sites`:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 主键 |
| code | TEXT UNIQUE | 编号 |
| name | TEXT | 名称 |
| province / city / district | TEXT | 行政区划 |
| address | TEXT | 详细地址 |
| category | TEXT | 类型 (古遗址/古墓葬/古建筑/石窟寺及石刻/近现代/其他) |
| era | TEXT | 时代 |
| batch / batch_year | INT | 公布批次和年份 |
| latitude / longitude | DOUBLE | GCJ-02 坐标 |
| location | GEOGRAPHY(POINT) | PostGIS 空间字段 |
| description | TEXT | 简介 (后续可由 LLM 生成丰富) |
| wikipedia_url / image_url | TEXT | 链接 |

辅助表: `eras` (朝代参考), `regions` (省市参考/统计缓存)

索引: 空间索引 (GIST), 省份/类型/时代索引, 全文搜索索引 (GIN)

RLS: 第一阶段全部公开可读

关键 RPC: `get_sites_in_bounds()` 按地图视窗范围+筛选条件查询

### Step 3: 项目骨架搭建

```bash
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --use-pnpm
pnpm add @supabase/supabase-js @supabase/ssr
pnpm add @amap/amap-jsapi-loader coordtransform
npx shadcn@latest init
npx shadcn@latest add button card dialog select command input badge
```

环境变量 (`.env.local`):
- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_AMAP_KEY` / `NEXT_PUBLIC_AMAP_SECRET`

### Step 4: 前端实现

**路由结构**:
- `/` - 首页: 全屏地图 + 左侧筛选面板
- `/site/[id]` - 文保单位详情页
- `/explore` - 列表浏览模式
- `/about` - 关于页面

**目录结构**:
```
src/
├── app/                      # 路由页面
├── components/
│   ├── map/                  # AMapContainer, SiteMarker, SiteInfoWindow
│   ├── filters/              # FilterPanel, ProvinceSelect, CategorySelect, EraSelect
│   ├── site/                 # SiteCard, SiteDetail
│   └── ui/                   # shadcn/ui 组件
├── lib/
│   ├── supabase/             # client.ts, server.ts
│   ├── amap.ts               # 地图加载工具
│   ├── types.ts              # 类型定义
│   └── constants.ts          # 常量
└── hooks/                    # useMap, useSites, useFilters
```

**关键技术决策**:
- **Marker Clustering**: 使用高德 `MarkerCluster` 插件，低缩放级别自动聚合标记
- **数据加载**: 首次加载所有站点精简数据 (~250KB, gzip 后 ~50KB)，前端筛选
- **URL 状态同步**: 筛选条件和地图位置编码到 URL query params，支持分享

### Step 5: 详情页

- 名称、编号、标签 (类型/时代/批次)
- 小地图显示位置
- 描述文字 + Wikipedia 链接
- 返回按钮 (保持地图视窗位置)

### Step 6: 部署

- Vercel 部署 (Next.js 原生支持)
- 配置环境变量
- 可选: 绑定自定义域名

## MVP 功能优先级

| 优先级 | 功能 |
|--------|------|
| P0 | 全屏高德地图 + 标记聚合 |
| P0 | 信息弹窗 (名称/类型/时代/地址) |
| P0 | 按省份、类型筛选 |
| P1 | 详情页 |
| P1 | 时代筛选 + 名称搜索 |
| P2 | 列表视图 + 移动端适配 |

## 后续阶段扩展点

- **第二阶段 (NLP 搜索)**: Supabase `pgvector` + embedding 语义搜索
- **第三阶段 (用户系统)**: Supabase Auth + `user_visits` 表
- **第四阶段 (旅行规划)**: PostGIS 空间查询 + 路径规划

## 验证方式

1. 运行数据采集脚本，确认河南+北京 ~400 条数据成功入库
2. 本地 `pnpm dev` 启动，地图正确加载并显示标记点
3. 筛选面板可按省份/类型过滤标记
4. 点击标记弹出信息窗口，点击"查看详情"跳转详情页
5. Vercel 部署成功，线上可访问
