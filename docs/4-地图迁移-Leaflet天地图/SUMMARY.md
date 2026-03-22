# 开发总结：地图迁移 Leaflet + 天地图

## 背景

高德地图 JS API 商业授权费用过高，无法用于正式上线。项目数据采集阶段已完成（使用高德 Web 服务 API 做地理编码，产出离线数据集），在线可视化层需要彻底替换为免费方案。

目标：用 **Leaflet 1.9.4**（开源地图框架）+ **天地图 WMTS**（国家测绘局免费底图）替代高德 JS API，规避商业授权问题，同时保持原有功能（5000+ 标记聚合展示、弹窗、筛选面板）。

## 实现方案

### 关键设计

**1. Vanilla Leaflet 而非 react-leaflet**

当前代码已是 `useEffect + useRef` 命令式模式（高德也是这样写的），替换时几乎 1:1 对应，改动最小。react-leaflet 的 MarkerCluster 封装（`react-leaflet-cluster`）维护较少且有版本兼容问题，Vanilla 模式避开了这一风险。5000+ 标记也不走 React 渲染树，性能更好。

**2. 前端实时坐标转换（GCJ-02 → WGS-84）**

数据库存储的是高德地理编码产出的 GCJ-02 坐标，天地图使用 WGS-84/CGCS2000。选择在前端渲染时用已安装的 `coordtransform` 包实时转换，不动数据库。好处是可逆、安全，等未来确认完全不需要高德坐标后再做 DB 迁移。

**3. Leaflet stacking context 隔离**

Leaflet 内部各 pane 的 z-index 最高达 1000，若祖先容器没有显式 z-index（不形成独立 stacking context），这些 z-index 会逃逸到根 stacking context，盖住筛选面板（`z-10`）。解决方案：在 MapView 中用 `absolute inset-0 z-0` 包裹 LeafletContainer，让 Leaflet 的内部 z-index 被隔离在这个 stacking context 内。

**4. Server Component 兼容**

`src/app/site/[id]/page.tsx` 是 Server Component，不能直接用 `dynamic(..., { ssr: false })`。方案：新增薄包装层 `SiteMapClient.tsx`（标记为 `"use client"`），在其中做 dynamic import，Server Component 改为引用这个包装层。

### 开发内容概括

| 操作 | 文件 |
|------|------|
| 删除 | `src/lib/amap.ts`、`src/types/amap.d.ts`、`src/components/map/AMapContainer.tsx` |
| 新增 | `src/lib/coordConvert.ts`（坐标转换封装） |
| 新增 | `src/types/coordtransform.d.ts`、`src/types/css.d.ts`（类型声明） |
| 新增 | `src/components/map/LeafletContainer.tsx`（主地图组件） |
| 新增 | `src/components/map/SiteMapClient.tsx`（Server Component 包装层） |
| 重写 | `src/components/map/SiteMap.tsx`（详情页单标记地图） |
| 修改 | `src/components/MapView.tsx`（切换组件 + stacking context 修复） |
| 修改 | `src/app/site/[id]/page.tsx`（改用 SiteMapClient） |
| 修改 | `src/components/filters/FilterPanel.tsx`（折叠/展开交互） |
| 新增 | `src/app/example/tianditu/page.tsx`（天地图瓦片验证 demo） |
| 重写 | `src/app/example/marker/page.tsx`、`src/app/example/markercluster/page.tsx` |
| 修改 | `CLAUDE.md`（更新技术栈说明和环境变量） |

### 额外产物

- `/example/tianditu`：天地图瓦片加载验证 demo，含右侧实时日志面板，包括 token 检测、图层加载事件监听、tileerror 捕获
- `/example/marker`、`/example/markercluster`：重写为 Leaflet 版，增加 GCJ-02 → WGS-84 转换日志输出，便于验证坐标偏移

## 局限性

**数据库坐标系未迁移**：数据库中存储的仍是 GCJ-02 坐标（高德地理编码产出），前端每次渲染都做实时转换。coordtransform 的转换为近似算法，精度约 10–30 米，对于文保单位定位完全够用，但从数据规范角度数据库理应存 WGS-84。

**天地图配额**：免费额度 10,000 次/天（vec_w + cva_w 各计一次，实际每个可见瓦片消耗 2 次）。开发阶段因 HMR 热更新和 React Strict Mode 双次挂载，配额消耗会虚高；生产环境有浏览器 HTTP 缓存兜底，实际消耗远低于限额。

## 后续 TODO

- **数据库坐标系迁移**：确认无其他模块依赖 GCJ-02 后，写一次 Supabase migration 将 `latitude`/`longitude` 批量转为 WGS-84，并移除前端的实时转换逻辑
- **天地图配额监控**：上线后观察实际日用量，必要时申请提额（教育/非商用配额可申请百万级）
- **筛选面板体验优化**：当前折叠态仅在有激活筛选时显示计数 badge，可考虑展示更丰富的激活状态摘要
