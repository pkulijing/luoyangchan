# 开发总结：地图提供者切换（高德 / 天地图）

## 背景

天地图 WMTS 瓦片服务日限额 10,000 次，每次缩放/拖动加载 12-20 个瓦片（vec_w + cva_w 各计一次），开发阶段频繁 HMR 热更新导致配额耗尽，无法正常测试。

高德 JS API 2.0 个人认证开发者免费额度 150 万次/月，且按**地图初始化**计数（非瓦片请求），实际可用量高出数个数量级。

## 实现方案

### 关键设计

**1. 双提供者共存，环境变量切换**

通过 `NEXT_PUBLIC_MAP_PROVIDER`（`amap` | `tianditu`，默认 `amap`）控制地图提供者。两套实现保持相同的组件 Props 接口，`MapView.tsx` 通过 `next/dynamic` 动态加载对应实现。Leaflet 相关依赖全部保留，两套可随时切换。

**2. 高德 JS API 原生 GCJ-02 坐标**

高德 JS API 使用 GCJ-02 坐标系，与数据库存储一致，高德模式下前端无需坐标转换。天地图模式仍走 `coordtransform` 的 GCJ-02→WGS-84 转换。

**3. 动态聚合半径对齐 Leaflet**

高德 `AMap.MarkerCluster` 不支持动态 `gridSize`，通过在 `zoomend` 事件中销毁重建 cluster 实现等效效果：
- zoom ≤ 4 → gridSize=80（最大聚合）
- zoom 4~8 → 线性衰减
- zoom ≥ 8 → 通过设置 `maxZoom = currentZoom - 1` 强制禁用聚合

**4. 浏览器原生地理定位**

AMap.Geolocation 插件在本地开发环境不稳定（IP 定位失败），改用 `navigator.geolocation`，与 Leaflet 版本一致。

**5. 静态卫星图统一用天地图**

高德静态地图 API 需要 Web 服务 Key（非 JS API Key），且默认不提供卫星图。静态卫星图 fallback 统一使用天地图 API，单次请求不消耗太多配额。

### 开发内容概括

| 操作 | 文件 |
|------|------|
| 新增 | `src/lib/mapProvider.ts`（提供者配置） |
| 新增 | `src/lib/amap.ts`（高德 JS API 加载器） |
| 新增 | `src/types/amap.d.ts`（高德类型声明） |
| 新增 | `src/components/map/AMapContainer.tsx`（高德主地图组件） |
| 新增 | `src/app/example/amap/page.tsx`（高德验证 demo） |
| 重写 | `src/components/map/SiteMap.tsx`（详情页地图，双提供者分发） |
| 修改 | `src/components/MapView.tsx`（动态导入切换） |
| 修改 | `src/components/map/SiteMapClient.tsx`（更新注释） |
| 修改 | `src/app/example/page.tsx`（索引页增加 AMap 入口） |
| 修改 | `CLAUDE.md`（技术栈、坐标系规则、环境变量） |
| 修改 | `.env.example`（增加 MAP_PROVIDER / AMAP_KEY / AMAP_SECRET） |
| 修改 | `package.json`（增加 @amap/amap-jsapi-loader） |

### 额外产物

- `/example/amap`：高德 JS API 2.0 验证 demo，含 MarkerCluster 测试、堆叠标记测试、renderMarker 回调计数、右侧实时日志面板

## 局限性

- **高德 MarkerCluster 性能**：每次 zoom 变化都销毁重建 cluster（5000+ 数据点），比 Leaflet 的原生动态半径机制开销更大，但目前未观察到明显卡顿
- **高德非官方瓦片不可用**：调研发现高德瓦片 URL（`webrd0{s}.is.autonavi.com`）是非官方无鉴权接口，不适合生产使用，因此不能用 Leaflet + 高德瓦片的方案
- **浏览器地理定位依赖 Google 服务**：在中国网络环境下容易超时失败，fitView 兜底机制正常工作
- **堆叠标记计数差异**：12 组坐标重合的站点（共 24 条）被合并为 12 个数据点，聚合气泡显示的是标记数（5159）而非站点总数（5171），与 Leaflet 版本行为一致

## 后续 TODO

- **管理员配置切换**：当前通过环境变量控制提供者，后续可扩展为管理员面板配置
- **开发/生产分治**：考虑开发环境默认用高德（配额充裕），生产环境用天地图（有浏览器缓存兜底）
- **天地图提额申请**：如果后续以机构身份申请，天地图可提额到百万级
- **聚合性能优化**：如果 zoom 变化时重建 cluster 出现性能问题，可考虑只在跨越关键 zoom 阈值（4、8、9）时重建
