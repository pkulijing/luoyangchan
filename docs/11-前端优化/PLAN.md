# 第11轮：前端优化 - 实现计划

## 整体方案

在 MapView 层新增"选中站点"状态，点击标记时通过回调传递 `release_id`，触发侧边面板滑出。面板通过 API route 获取站点详情数据，展示内容复用详情页的信息结构。

## 关键设计

### 数据流

```
标记点击 → LeafletContainer.onSiteClick(releaseId) → MapView.setSelectedId(releaseId)
                                                           ↓
                                                    SiteDetailPanel 渲染
                                                           ↓
                                                    fetch /api/site/{releaseId}
                                                           ↓
                                                    展示详情，支持关闭
```

### popup 内链接桥接

堆叠标记的 popup 使用原生 HTML，无法直接触发 React 状态。采用**事件委托**方案：

- popup 内链接改为 `<a href="#" data-release-id="xxx">`
- 在 map container 上监听 click 事件，匹配 `[data-release-id]` 选择器
- 命中后调用 `onSiteClick` 回调，关闭 popup

单条标记则直接去掉 popup，点击即打开面板。

### 面板设计

- 右侧固定定位，宽度 1/3 屏幕（min-width 320px），带 slide-in 动画（CSS transition）
- 展示内容：badges（分类/时代/批次）、地址、省份城市、百度百科链接、简介、子记录/父记录链接
- 不嵌入小地图（用户已经在地图上看到位置了）
- 底部保留"查看完整详情"链接（新窗口打开）
- 点击面板外区域或关闭按钮可收起

### 标记图标设计

每种文保类别使用不同的 SVG 图标（12x12 视口，白色线条），内嵌在 18px 彩色圆内：
- 古遗址：破墙轮廓
- 古墓葬：土丘曲线
- 古建筑：传统屋顶
- 石窟寺及石刻：墓碑形
- 近现代：五角星
- 其他：星号

### 用户定位

进入页面时通过 Geolocation API 获取用户位置：
- 在中国范围内：定位到用户位置，zoom=11
- 不在中国范围内：定位到北京天安门，zoom=11
- 定位失败：保持默认行为（fitBounds）

## 实现步骤

### 1. 创建 API route

新建 `src/app/api/site/[releaseId]/route.ts`，包装 `getSiteByReleaseId` 返回 JSON。

### 2. 创建 SiteDetailPanel 组件

新建 `src/components/site/SiteDetailPanel.tsx`：
- props: `releaseId: string | null`, `onClose: () => void`
- `releaseId` 非空时 fetch 数据并展示
- 使用 shadcn/ui 的 Badge、Card 等组件保持风格一致
- CSS transition 实现滑入/滑出动画

### 3. 改造 MapView

- 新增 `selectedReleaseId` 状态
- 传递 `onSiteClick` 回调给 LeafletContainer
- 条件渲染 SiteDetailPanel

### 4. 改造 LeafletContainer

- 单条标记：去掉 `bindPopup`，点击直接调用 `onSiteClick(release_id)`
- 堆叠标记：popup HTML 中的链接改为 `data-release-id` 属性
- 新增 popup HTML 中的单条标记 popup 也改为用 `data-release-id` 打开面板
- 在 map container 上添加事件委托监听 `[data-release-id]` 点击

## 涉及文件

| 文件 | 操作 |
|---|---|
| `src/app/api/site/[releaseId]/route.ts` | 新增 |
| `src/components/site/SiteDetailPanel.tsx` | 新增 |
| `src/components/MapView.tsx` | 修改 |
| `src/components/map/LeafletContainer.tsx` | 修改 |
