# 第12轮：图片采集

## 背景

数据库中 5171 条文保单位目前 `image_url` 全部为空。详情面板和详情页缺少图片展示，用户无法直观了解站点外观。

## 需求

### 图片来源选择

初始尝试使用 Wikipedia `prop=pageimages` API 采集 Wikimedia Commons 图片，但发现 **`upload.wikimedia.org` 在中国大陆被墙**，图片无法加载。因此改用百度百科作为主要图片来源。

### Phase 1：百度百科图片采集

通过百度百科 BaikeLemmaCardApi 批量获取文保单位主图 URL：
- 图片托管在 `bkimg.cdn.bcebos.com`（百度云 CDN），国内秒开
- 5171 条记录全部有 `baike_url`，覆盖面完整
- 前端需要 `referrerPolicy="no-referrer"` 绕过百度 CDN 防盗链

### Phase 2：前端图片展示

采集到图片后，在前端展示：
- 侧边详情面板（SiteDetailPanel）顶部展示图片
- 独立详情页中，将原有的嵌入地图替换为图片展示
- 所有 `<img>` 标签添加 `referrerPolicy="no-referrer"`
