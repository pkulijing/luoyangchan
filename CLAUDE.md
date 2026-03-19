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

数据采集流程见 `docs/1-DataCollect/PLAN.md`。

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

- Git 提交规范: 由 AI 协助完成的提交，commit message 末尾必须包含 `Co-authored-by` trailer：

  ```
  Co-authored-by: Claude Sonnet <noreply@anthropic.com>
  Co-authored-by: GitHub Copilot <github-copilot[bot]@users.noreply.github.com>
  ```

- **docs 文件夹组织规范**：每次开发任务在 `docs/` 下创建独立文件夹，用数字前缀+中文描述便于排序（如 `0-初始灵感`、`1-数据收集与清洗`）。每个文件夹包含：
  - `PROMPT.md`：最初的用户手写的需求文档（如有）
  - `PLAN.md`：AI 生成的实现计划文档
  - `SUMMARY.md`: 本次开发总结
    - 背景
      - 针对BUG：BUG的表现和影响
      - 针对正向开发：希望解决的问题或实现的功能
    - 实现方案
      - 关键设计
        - 针对BUG：最终发现的关键问题
        - 针对正向开发：设计方案中的关键点（简要概括，详细方案在PLAN.md里）
      - 开发内容概括
      - 额外产物：除核心代码外的额外贡献，如测试用例、调试脚本、样例文件
    - 局限性：当前方案的遗留问题
    - 后续TODO：可以针对上面的遗留问题，也可以是发现的新问题、启发的新方向
  - `assets/`：相关图片或其他资源（如有）
  - 其他补充文档（如数据库设计、API 说明等）
  - **所有文档一律用中文撰写**

- **`/example/*` 调试页面惯例**：遇到第三方 API（尤其是高德地图）不确定的用法时，先在 `src/app/example/<功能名>/page.tsx` 下创建最小化 demo 页面验证，再移植到业务组件。demo 页面应包含右侧实时日志面板，便于观察执行步骤和返回类型。这些页面仅用于开发调试，不对外暴露功能入口。
