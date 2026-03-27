# 第11轮：前端优化 - 开发总结

## 开发项背景

用户在地图上通过筛选、缩放、平移找到感兴趣的站点后，点击"查看详情"会跳转到独立页面，导致地图视角和筛选条件全部丢失。返回后需要重新操作，严重影响探索式浏览体验。

同时，低缩放级别下所有标记都是小圆点，难以区分具体是哪个站点。

## 实现方案

### 关键设计

1. **缩放文字标签**：zoom >= 9 时，圆点标记自动切换为带站点名称的彩色文字标签（分类色背景 + 小三角箭头指向坐标点）
2. **类别图标标记**：zoom < 9 时，每种文保类别使用不同的 SVG 图标（古遗址/古墓葬/古建筑/石窟寺/近现代/其他），内嵌在 18px 彩色圆内，替代原有的纯色圆点
3. **侧边详情面板**：点击标记不再跳转页面，而是在右侧滑出 1/3 屏幕宽的详情面板（min-width 320px），地图状态完全保留
4. **用户自动定位**：进入页面时通过 Geolocation API 获取用户位置，在中国范围内定位到用户位置（zoom=11），否则定位到北京天安门。修复了定位与 fitBounds 之间的竞态 bug（通过 geoResolvedRef 延迟首次 fitBounds）
5. **事件委托桥接**：堆叠标记的 popup 使用原生 HTML，通过 `data-release-id` 属性 + container 级事件委托，将 popup 内链接点击桥接到 React 状态
6. **图片展示组件 SiteImage**：三级 fallback（自有图片 → 天地图卫星静态图 → "图片暂缺"占位 + 百度搜索链接）
7. **外部链接**：百度百科、搜索图片、高德导航（GCJ-02 坐标直传）
8. **详情页图片替换地图**：独立详情页中原有的嵌入式小地图替换为 SiteImage 组件

### 开发内容概括

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/app/api/site/[releaseId]/route.ts` | 新增 | 客户端获取站点详情的 API route |
| `src/components/site/SiteDetailPanel.tsx` | 新增 | 右侧滑出详情面板，含图片、badges、信息、导航链接、简介、子/父记录 |
| `src/components/site/SiteImage.tsx` | 新增 | 图片展示组件（三级 fallback：图片 → 天地图卫星图 → 占位） |
| `src/components/MapView.tsx` | 修改 | 集成 `selectedReleaseId` 状态和面板组件 |
| `src/components/map/LeafletContainer.tsx` | 修改 | 缩放文字标签、标记点击回调、popup 事件委托、定位竞态修复 |
| `src/app/site/[releaseId]/page.tsx` | 修改 | 嵌入地图替换为 SiteImage，添加 referrerPolicy |
| `src/lib/coordConvert.ts` | 修改 | 新增 gcj02ToBd09 转换函数 |

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

- 文字标签在密集区域可能重叠（zoom 9 阈值可调）
- Geolocation API 要求安全来源，本地开发需使用 `localhost` 而非 `127.0.0.1`
- 百度地图 direction URI API 无法正常工作（参数格式文档与实际行为不一致），已放弃百度导航功能

## 后续 TODO

- 移动端适配：面板可能需要改为底部抽屉
- 考虑用 URL search params 同步选中状态，支持分享链接
