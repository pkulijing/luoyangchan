# 洛阳铲 - 项目说明

全国重点文物保护单位地图浏览工具。用户可在地图上探索 5000+ 文保单位，按省份、类型、时代筛选，查看详情。

## 技术栈

- **Next.js 16** (App Router) + **React 19** + **TypeScript 5**
- **Tailwind CSS v4** + **shadcn/ui**
- **高德地图 JS API 2.0**（`@amap/amap-jsapi-loader`）：地图渲染、MarkerCluster 聚合
- `coordtransform`：WGS-84 ↔ GCJ-02 坐标系转换（Wikipedia 数据为 WGS-84，高德地图使用 GCJ-02）
- **Supabase**（本地 Docker 开发，通过 Supabase CLI 管理），本地地址 `http://127.0.0.1:54321`，Studio `http://127.0.0.1:54323`
- **Python 3.12** + **uv** 管理依赖（不使用 pip/pip3）

## 本地开发

```bash
supabase start   # 启动本地 Supabase（需 Docker）
npm run dev      # 启动前端
```

数据采集流程见 `docs/data-cleaning-plan.md`。

## 环境变量

`.env.local`（不提交到 git）：

```
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<publishable key>
SUPABASE_SERVICE_ROLE_KEY=<secret key>
NEXT_PUBLIC_AMAP_KEY=<高德地图 JS API Key>
NEXT_PUBLIC_AMAP_SECRET=<高德地图安全密钥>
AMAP_GEOCODING_KEY=<高德 Web 服务 Key，用于地理编码脚本>
```

## 项目约定

- `.gitignore` 按目录拆分：每个目录维护自己的 `.gitignore`，不要把子目录的忽略规则写到根目录的 `.gitignore` 里。

- 由 AI 协助完成的提交，commit message 末尾必须包含 `Co-authored-by` trailer：
  ```
  Co-authored-by: Claude Sonnet <noreply@anthropic.com>
  Co-authored-by: GitHub Copilot <github-copilot[bot]@users.noreply.github.com>
  ```
