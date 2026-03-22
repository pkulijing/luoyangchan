# 开发总结

## 开发项背景

数据库中约 1015 条文保单位记录因地理编码精度不足，坐标仅精确到行政区中心点，导致多条数据在地图上完全重叠，视觉上只能看到一个标记，无法感知数据质量问题，不利于后续排查和修复。

同时，原有固定聚合半径（60px）在全国视野下标记密集，放大后仍过度聚合，体验不佳。

## 实现方案

### 关键设计

**坐标重合分组**：在标记渲染前，以 `longitude,latitude` 字符串为 key 对所有有效数据分组。对 count > 1 的组，渲染一个区别于普通标记的"堆叠标记"，避免数据静默丢失。

**zoom 联动聚合半径**：将 `maxClusterRadius` 改为由 zoom 动态计算的值，而非固定常量。在地图初始化时绑定 `zoomend` 事件更新 React state，state 变化触发 `updateMarkers` effect 重建聚合层。为避免缩放调整时视角重置，用 `prevSitesRef` 保护 `fitBounds` 只在 `sites` 数据真正变化时触发。

### 开发内容概括

- `LeafletContainer.tsx`：
  - 新增 `buildStackedPopupHtml`：为坐标重合点生成列表式 popup
  - 新增坐标分组逻辑，重合点渲染橙色方块标记（显示条数）
  - 新增 `zoom` state + `zoomend` 监听
  - 新增 `calcClusterRadius(zoom)` 线性插值函数及三个可调常量
  - 新增 `prevSitesRef` 保护 `fitBounds` 逻辑
  - 新增 zoom 变化时的 console.log，便于调试阈值
- `MapView.tsx`：移除手动聚合半径滑块（功能由自动联动替代）

### 额外产物

无

## 局限性

- 坐标重合的堆叠标记与普通标记共用同一个 MarkerClusterGroup，在低缩放级别下堆叠标记会被进一步聚合进普通 cluster，不影响功能但视觉上无法区分
- zoom 变化时需完整重建 MarkerClusterGroup（约 5000+ 标记），在低端设备上可能有轻微卡顿
- `CLUSTER_ZERO_AT_ZOOM = 8` 为经验值，实际对应的地理范围因屏幕尺寸和分辨率略有差异，需结合使用感受调整

## 后续 TODO

- [ ] 进一步清洗 1015 条精度不足的坐标数据（终极目标），坐标重合可视化是临时 debug 工具
- [ ] 考虑将聚合常量暴露为 URL 参数或 localStorage，便于持久化个人偏好设置
- [ ] 评估是否需要对 updateMarkers 加防抖，避免快速连续缩放时的重复重建
