# 前端性能优化：引入 MarkerCluster 聚合标记

## 背景

5000+ 个文保单位原本全部以独立 `AMap.Marker` 实例渲染，每次加载或筛选切换时需逐一将 marker 添加到地图，导致页面初始化和筛选切换有数秒明显卡顿。目标是引入高德地图内置的 `AMap.MarkerCluster` 插件，将视野内邻近点聚合为气泡显示，大幅减少实际渲染节点数，消除卡顿。

## 实现方案

### 关键设计

**AMap JS API 2.0 数据驱动模式**：MarkerCluster 在 2.0 版本与 1.x 存在 breaking change——构造函数第二参数从 `AMap.Marker[]` 改为数据点数组 `{ lnglat: [lng, lat], ...自定义字段 }[]`，渲染完全由 `renderMarker` / `renderClusterMarker` 回调控制。传旧格式的 Marker 数组不会报错，但地图上什么都不显示，极难发现。

借助 `/example/*` 调试页面快速定位了该问题：在隔离环境中用最少代码复现，排除业务代码干扰，通过右侧实时日志面板确认 API 类型和执行顺序，再将正确用法移植到业务组件。

### 开发内容概括

- **`src/lib/amap.ts`**：plugins 列表增加 `"AMap.MarkerCluster"`，确保插件随 SDK 加载
- **`src/types/amap.d.ts`**：重写 MarkerCluster 相关类型声明，反映 2.0 数据驱动 API（`MarkerClusterDataOption`、`MarkerClusterRenderContext`、`renderMarker`/`renderClusterMarker` 回调、`Marker` 新增 `setContent`/`setOffset`/`setTitle`、`setFitView` 支持 `null`）
- **`src/components/map/AMapContainer.tsx`**：核心重构，`markersRef: AMap.Marker[]` → `clusterRef: AMap.MarkerCluster | null`；数据点挂业务字段 `{ lnglat, site }`；`renderMarker` 按 `CATEGORY_COLORS[site.category]` 渲染彩色圆点 pin 并绑定点击 → InfoWindow；`renderClusterMarker` 渲染白底数字气泡；cleanup 改为 `clusterRef.current?.setMap(null)`

### 额外产物

- **`src/app/example/marker/page.tsx`**：基础 `AMap.Marker` 验证页面（8 个固定城市坐标，含右侧日志面板）
- **`src/app/example/markercluster/page.tsx`**：`AMap.MarkerCluster` 数据驱动模式验证页面（10 个固定城市，每城市独立颜色，含日志面板）

## 局限性

- **聚合规则是纯像素距离**：`gridSize: 60`（60px 半径聚合）、`maxZoom: 16`（zoom > 16 停止聚合），无法按行政区划聚合；在中等缩放级别下同省的点可能与邻省的点聚到一起，在高缩放级别下却又不聚合
- **坐标精度不足**：现有数据中大量文保单位坐标由批量地理编码生成，落点在县城中心，多点完全重叠，放大后仍显示为单个 pin，点击只能访问其中一个

## 后续 TODO

1. **数据清洗第二轮**：为每条记录补充 `city`（地级市）和 `county`（区县）字段，为后续分级渲染提供数据基础
2. **按行政区划分级聚合**：利用 `city`/`county` 字段，在不同缩放级别实现省 → 市 → 县的层级展示，替代当前纯像素距离聚合（当前 MarkerCluster 不原生支持，需自定义实现）
