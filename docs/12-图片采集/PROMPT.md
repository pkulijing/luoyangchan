# 第12轮：图片采集

## 背景

数据库中 5171 条文保单位目前 `image_url` 全部为空。详情面板和详情页缺少图片展示，用户无法直观了解站点外观。

## 需求

### 图片来源与优先级

前端展示采用 4 级优先级策略：

1. **维基图片**（自托管）：从 Wikimedia Commons 下载到 Supabase Storage，存储为相对路径 `site-images/{release_id}.jpg`。国内无法直接访问 `upload.wikimedia.org`，因此必须自托管。
2. **百度百科图片**（外链，配置控制）：百度百科 BaikeLemmaCardApi 获取的图片 URL，托管在 `bkimg.cdn.bcebos.com`（百度云 CDN），国内可直接访问。通过环境变量 `NEXT_PUBLIC_USE_BAIKE_IMAGES` 控制是否启用，默认启用。需 `referrerPolicy="no-referrer"` 绕过防盗链。
3. **天地图卫星图**：有坐标时，调用天地图静态图 API 生成卫星图作为兜底。
4. **图片暂缺提示**：无任何图片来源时，显示占位提示。

> 无论使用哪级图片来源，百度搜索图片链接始终显示，方便用户查看更多图片。

### 数据模型

- `image_url`：自托管图片的相对存储路径（如 `site-images/1-1.jpg`），前端拼接 Supabase URL
- `baike_image_url`：百度百科 CDN 图片的完整 URL，独立存储

### Phase 1：百度百科图片采集

通过百度百科 BaikeLemmaCardApi 批量获取文保单位主图 URL：
- 图片托管在 `bkimg.cdn.bcebos.com`（百度云 CDN），国内秒开
- 5171 条记录全部有 `baike_url`，覆盖面完整
- 前端需要 `referrerPolicy="no-referrer"` 绕过百度 CDN 防盗链

### Phase 2：Wikimedia 图片下载到 Supabase Storage

从 Wikimedia Commons 下载图片到 Supabase Storage `site-images` bucket，彻底摆脱对外部 CDN 的依赖。

### Phase 3：前端图片展示

`SiteImage` 组件按优先级链展示图片，支持配置控制百度图片开关。
