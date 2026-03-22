# 实施计划：高德地图 → Leaflet + 天地图

## 背景

高德地图 JS API 商业授权费用过高。项目已完成数据采集（高德地理编码 API 离线数据集），在线版本只需解决可视化问题，迁移到 Leaflet + 天地图可彻底规避商业授权。

分支：`feat/leaflet-tianditu`

## 关键决策

### Vanilla Leaflet 1.9.4（非 react-leaflet）

- 当前代码已是 useEffect + useRef 命令式模式，改动最小
- 5000+ 标记性能更好（不走 React 树）
- MarkerCluster 无版本兼容问题（react-leaflet-cluster 维护较少）

### 前端实时坐标转换

数据库存 GCJ-02（高德地理编码产出），天地图使用 WGS-84（CGCS2000）。
使用已安装的 `coordtransform` 包在渲染时做 `gcj02towgs84()` 转换，不动数据库。

### 环境变量

`TIANDITU_TK` → `NEXT_PUBLIC_TIANDITU_TK`（Next.js 客户端访问必须加 NEXT_PUBLIC_ 前缀）

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 删除 | `src/lib/amap.ts` |
| 删除 | `src/types/amap.d.ts` |
| 删除 | `src/components/map/AMapContainer.tsx` |
| 创建 | `src/lib/coordConvert.ts` |
| 创建 | `src/types/coordtransform.d.ts` |
| 创建 | `src/types/leaflet-markercluster.d.ts` |
| 创建 | `src/components/map/LeafletContainer.tsx` |
| 重写 | `src/components/map/SiteMap.tsx` |
| 修改 | `src/components/MapView.tsx` |
| 修改 | `src/app/site/[id]/page.tsx` |
| 创建 | `src/app/example/tianditu/page.tsx` |
| 重写 | `src/app/example/marker/page.tsx` |
| 重写 | `src/app/example/markercluster/page.tsx` |
| 修改 | `CLAUDE.md` |

## 功能对照

| AMap | Leaflet 替代 |
|------|-------------|
| `AMap.Map` | `L.map()` |
| `AMap.MarkerCluster`（data-driven）| `L.markerClusterGroup()` + `L.marker()` |
| `AMap.InfoWindow`（手动 open）| `marker.bindPopup()`（自动管理）|
| `AMap.Scale` | `L.control.scale()` |
| `AMap.ToolBar` | Leaflet 内置 zoom control |
| `setFitView()` | `map.fitBounds()` |
| `mapStyle: whitesmoke` | 天地图矢量底图 + 中文注记图层 |
| 坐标顺序 `[lng, lat]` | 坐标顺序 `[lat, lng]` ⚠️ |

## 注意事项

1. **坐标顺序**：AMap `[lng, lat]` vs Leaflet `[lat, lng]`，最易出 bug
2. **Leaflet CSS**：必须导入 `leaflet/dist/leaflet.css` 和 MarkerCluster CSS
3. **DivIcon className**：自定义图标必须设 `className: ''`，否则 Leaflet 加默认样式
4. **容器高度**：Leaflet 要求容器有明确高度
5. **SSR**：所有 Leaflet 组件需 `dynamic(..., { ssr: false })`
