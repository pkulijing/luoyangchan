# 第11轮：前端优化 - 开发总结

## 开发项背景

用户在地图上通过筛选、缩放、平移找到感兴趣的站点后，点击"查看详情"会跳转到独立页面，导致地图视角和筛选条件全部丢失。返回后需要重新操作，严重影响探索式浏览体验。

同时，低缩放级别下所有标记都是小圆点，难以区分具体是哪个站点。

## 实现方案

### 关键设计

1. **缩放文字标签**：zoom >= 13 时，圆点标记自动切换为带站点名称的彩色文字标签（分类色背景 + 小三角箭头指向坐标点）
2. **侧边详情面板**：点击标记不再跳转页面，而是在右侧滑出 400px 宽的详情面板，地图状态完全保留
3. **事件委托桥接**：堆叠标记的 popup 使用原生 HTML，通过 `data-release-id` 属性 + container 级事件委托，将 popup 内链接点击桥接到 React 状态

### 开发内容概括

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/app/api/site/[releaseId]/route.ts` | 新增 | 客户端获取站点详情的 API route |
| `src/components/site/SiteDetailPanel.tsx` | 新增 | 右侧滑出详情面板，含 badges、基本信息、简介、子/父记录导航 |
| `src/components/MapView.tsx` | 修改 | 集成 `selectedReleaseId` 状态和面板组件 |
| `src/components/map/LeafletContainer.tsx` | 修改 | 缩放文字标签、标记点击行为改为回调、popup 事件委托 |

### 数据流

```
标记点击 → onSiteClick(releaseId) → MapView.setSelectedReleaseId
                                          ↓
                                   SiteDetailPanel 渲染
                                          ↓
                                   fetch /api/site/{releaseId}
                                          ↓
                                   展示详情 / 面板内导航
```

## 局限性

- 面板内不包含小地图（判断用户已在地图上看到位置，无需重复）
- 面板宽度固定 400px / 85vw，未做响应式适配移动端
- 文字标签在密集区域可能重叠（zoom 13 阈值可调）

## 后续 TODO

- 移动端适配：面板可能需要改为底部抽屉
- 考虑用 URL search params 同步选中状态，支持分享链接
- 百度百科图片采集与展示（用户新需求，可作为下一轮开发）
