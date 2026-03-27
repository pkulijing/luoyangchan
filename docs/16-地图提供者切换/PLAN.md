# 实现计划：地图提供者切换

## 架构设计

通过环境变量 `NEXT_PUBLIC_MAP_PROVIDER`（`amap` | `tianditu`）控制地图提供者。两套实现共存，保持相同的组件 Props 接口，通过 `next/dynamic` 动态加载对应实现。

```
src/lib/mapProvider.ts          # 提供者配置
src/lib/amap.ts                 # 高德 JS API 加载器
src/types/amap.d.ts             # 高德类型声明
src/components/map/
  ├── AMapContainer.tsx         # 高德主地图（新建）
  ├── LeafletContainer.tsx      # 天地图主地图（保留）
  ├── SiteMap.tsx               # 详情页地图（改为按提供者分发）
  └── SiteMapClient.tsx         # SSR 包装层（不变）
```

## 关键决策

### 1. 坐标系处理
- 高德 JS API 原生使用 GCJ-02，和数据库一致，无需坐标转换
- 天地图路径仍走 `coordtransform` 的 GCJ-02→WGS-84 转换
- `coordConvert.ts` 保留

### 2. 高德 MarkerCluster
- 使用 `AMap.MarkerCluster` 的 `renderMarker` / `renderClusterMarker` 回调自定义标记外观
- `gridSize: 60` 固定值（高德不支持动态聚合半径）
- `maxZoom: 16` 等效 Leaflet 的 `disableClusteringAtZoom: 17`

### 3. 底图样式
- 高德使用标准样式（默认）
- 天地图使用 vec_w + cva_w 矢量底图+注记

### 4. 依赖管理
- 新增 `@amap/amap-jsapi-loader`
- 保留所有 Leaflet 依赖（两套共存）

## 实现步骤

1. 安装 `@amap/amap-jsapi-loader`，更新 `.env.example`
2. 创建 `mapProvider.ts`、`amap.ts`、`amap.d.ts`
3. 创建 `/example/amap` 验证页
4. 创建 `AMapContainer.tsx`（核心，完整复现 LeafletContainer 全部功能）
5. `MapView.tsx` 根据 `MAP_PROVIDER` 动态导入
6. `SiteMap.tsx` 支持双提供者
7. `SiteImage.tsx` 静态图 fallback 支持双提供者
8. 更新 `CLAUDE.md` 文档

## 功能对照表

| 功能 | Leaflet + 天地图 | 高德 JS API |
|------|-----------------|-------------|
| 底图 | WMTS vec_w + cva_w | 内置底图 |
| 坐标 | GCJ-02→WGS-84 | 直接 GCJ-02 |
| 聚合 | markercluster + 动态半径 | MarkerCluster + gridSize:60 |
| 标记图标 | L.divIcon HTML | Marker.content HTML |
| 弹窗 | L.popup | AMap.InfoWindow |
| 地理定位 | navigator.geolocation | AMap.Geolocation |
| fitBounds | cluster.getBounds() | map.setFitView() |

## 环境变量

```env
NEXT_PUBLIC_MAP_PROVIDER=amap          # amap | tianditu
NEXT_PUBLIC_AMAP_KEY=xxx               # 高德 JS API Key
NEXT_PUBLIC_AMAP_SECRET=xxx            # 高德安全密钥
NEXT_PUBLIC_TIANDITU_TK=xxx            # 天地图 Token
```
