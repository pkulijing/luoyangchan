# 实现计划

## 坐标重合可视化

在 `LeafletContainer` 的 `updateMarkers` 逻辑中，对 `validSites` 按原始 GCJ-02 坐标（`longitude,latitude` 字符串 key）分组：

- **单条数据**：沿用现有的彩色圆形标记
- **多条共用坐标**：渲染一个橙色方块标记，显示条数；点击展开 popup，列出所有条目名称、类型、时代及详情链接，顶部标注"N 条数据共用此坐标"

## 聚合半径联动

将 `maxClusterRadius` 从固定值改为随 zoom 动态计算：

1. 在地图初始化时绑定 `zoomend` 事件，更新 React state `zoom`
2. `zoom` 变化触发 `updateMarkers` effect，以新 radius 重建 MarkerClusterGroup
3. 公式：`zoom <= CLUSTER_FULL_ZOOM` 时取最大半径，`zoom >= CLUSTER_ZERO_AT_ZOOM` 时取 0，中间线性插值
4. 关键常量（便于调整）：
   - `CLUSTER_MAX_RADIUS = 40`
   - `CLUSTER_FULL_ZOOM = 4`
   - `CLUSTER_ZERO_AT_ZOOM = 8`（约省级视野，可按需调整）

## fitBounds 保护

调整 clusterRadius/zoom 触发重建时不应重置地图视角。用 `prevSitesRef` 记录上一次 `sites` 引用，只有 `sites` 真正变化时才调用 `fitBounds`。
