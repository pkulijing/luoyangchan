# 洛阳铲 - 项目说明

全国重点文物保护单位地图浏览工具。用户可在地图上探索 5000+ 文保单位，按省份、类型、时代筛选，查看详情。

详细介绍：

@docs/0-初始灵感/PROMPT.md

## 核心开发模式

人类开发者与 Coding Agent 合作，分为需求 - 计划 - 执行 - 总结四步

### 开发模式详解

- 需求：结合当前现状，针对一个待解决的问题，给出明确详细的开发需求。人类主导，提供需求内容
- 计划：结合项目现状，分析需求，给出可行的详细计划。Agent 主导，人类 Review，在 Plan 模式下输出。
- 执行：按照计划，完成开发。Agent 主导，人类适当干预辅助。**执行前必须先完成 PROMPT.md 和 PLAN.md 的撰写并确认，再开始写代码。**
- 总结：开发完成后，总结开发项，输出总结文档，Agent 主导。包含以下内容：
  - 开发项背景
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

### 文档记录规范

基于以上开发模式，每个由人类发起的开发需求，都要在 `docs` 文件夹下做文档记录。具体规范如下：

- **所有文档一律用中文撰写**
- 文件夹名称：用数字前缀+中文描述便于排序（如 `0-初始灵感`、`1-数据收集与清洗`），数字代表开发的轮次，文字简要描述开发内容。
- 文件夹内容：
  - `PROMPT.md`：需求文档，如果人类直接提供了，就直接使用，否则生成一个简要的文档描述。
  - `PLAN.md`：Agent 生成的实现计划
  - `SUMMARY.md`: Agent 生成的开发总结
  - 其他补充文档：如数据库设计、API 设计等后续需要参考的重要信息
  - 如果需要图片等资源辅助，把图片放到 `assets` 文件夹下

## 开发指南

### 技术栈

- **Next.js 16** (App Router) + **React 19** + **TypeScript 5**
- **Tailwind CSS v4** + **shadcn/ui**
- **Leaflet 1.9.4** + **leaflet.markercluster**：地图渲染、MarkerCluster 聚合（`vanilla` 模式，非 react-leaflet）
- **天地图 WMTS**：底图瓦片服务（矢量底图 `vec_w` + 中文注记 `cva_w`），坐标系 WGS-84/CGCS2000
- `coordtransform`：GCJ-02 → WGS-84 坐标转换（数据库存 GCJ-02，Leaflet/天地图需要 WGS-84）

### 坐标系规则（重要）

- **数据库/JSON 统一存储 GCJ-02 坐标**。所有 geocoding 结果（高德、腾讯）均返回 GCJ-02，直接存储，**不做任何坐标转换**。
- **前端展示时转换**：Leaflet + 天地图使用 WGS-84，前端读取数据后通过 `coordtransform` 的 `gcj02_to_wgs84()` 转换。
- **维基百科等外部来源的 WGS-84 坐标**必须先通过 `wgs84_to_gcj02()` 转换为 GCJ-02 后再存入数据库。
- **绝对禁止**在 Python 数据清洗脚本中对 geocoding 结果做 GCJ-02→WGS-84 转换后存入 JSON。
- 高德 Web 服务 API（仅用于数据采集 Python 脚本，前端不使用高德任何 SDK）
- **Supabase**（本地 Docker 开发，通过 Supabase CLI 管理），本地地址 `http://127.0.0.1:54321`，Studio `http://127.0.0.1:54323`
- **Python 3.12** + **uv** 管理依赖（不使用 pip/pip3）

### 本地开发

```bash
supabase start   # 启动本地 Supabase（需 Docker）
npm run dev      # 启动前端
```

### 数据导入 Supabase

数据清洗/修复后，需要将 `data/heritage_sites_geocoded.json` 重新导入本地 Supabase：

```bash
cd scripts
uv run python db/seed_supabase.py --clear   # --clear 会先清空表再导入
```

### 环境变量

`.env.local`（不提交到 git）：

```
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<publishable key>
SUPABASE_SERVICE_ROLE_KEY=<secret key>
AMAP_GEOCODING_KEY=<高德 Web 服务 Key，用于地理编码脚本>
NEXT_PUBLIC_TIANDITU_TK=<天地图应用TK>
```

新增、删除、改名环境变量时，需要在 .env.example 中做相同处理，以便开发者参考。

## 项目约定

### git 规则

- `.gitignore` 按目录拆分：每个目录维护自己的 `.gitignore`，不要把子目录的忽略规则写到根目录的 `.gitignore` 里。

- commit message: 由 AI 协助完成的提交，commit message 末尾必须包含 `Co-authored-by` trailer：

  ```
  Co-authored-by: Claude Sonnet <noreply@anthropic.com>
  Co-authored-by: GitHub Copilot <github-copilot[bot]@users.noreply.github.com>
  ```

  commit message的内容遵循 semantic commit message 规则

### 调试页面惯例

- **`/example/*` **：遇到第三方 API（Leaflet、天地图等）不确定的用法时，先在 `src/app/example/<功能名>/page.tsx` 下创建最小化 demo 页面验证，再移植到业务组件。demo 页面应包含右侧实时日志面板，便于观察执行步骤和返回类型。这些页面仅用于开发调试，不对外暴露功能入口。
