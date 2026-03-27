# 第12轮：图片采集 - 实现计划

## 方案演变

### 初始方案：Wikipedia pageimages（已放弃）

使用 MediaWiki API `prop=pageimages` 批量获取文章主图，命中率 43%（1698/3920）。
**放弃原因**：`upload.wikimedia.org` 在中国大陆被墙，图片无法加载。

### 最终方案：百度百科 BaikeLemmaCardApi

使用百度百科半官方 API 获取词条主图，图片在百度云 CDN，国内可直接访问。

## Phase 1：百度百科图片批量抓取

### API 方案

```
GET https://baike.baidu.com/api/openapi/BaikeLemmaCardApi?appid=379020&bk_key=故宫&bk_length=50
```

响应中 `image` 字段即为主图 URL（`bkimg.cdn.bcebos.com`）。

### 多策略提升命中率

BaikeLemmaCardApi 命中率不稳定，采用多策略查询：
1. 用 `baike_url` 中提取的词条名查询
2. 用站点原名（`name` 字段）查询
3. 去掉常见后缀（遗址/旧址/故居/会址等）重试

### 脚本设计

**文件**：`scripts/round6/fetch_baike_images.py`

**约定**：
- 支持 `--dry-run`（前 50 条）和 `--resume`
- 每次请求间隔 0.3 秒
- 每 200 条保存 checkpoint

### 合并策略

**文件**：`scripts/round6/apply_images.py`

- 有百度百科图片 → 写入 `image_url`
- 无百度百科图片 → 清空 `image_url`（不保留不可访问的 Wikipedia 图片）

## Phase 2：前端图片展示

### 侧边详情面板

修改 `src/components/site/SiteDetailPanel.tsx`：
- 在面板内容区顶部（badges 之前）添加图片
- 有 `image_url` 时显示全宽图片（h-48 object-cover）
- 添加 `referrerPolicy="no-referrer"` 绕过百度 CDN 防盗链

### 独立详情页

修改 `src/app/site/[releaseId]/page.tsx`：
- 将原有"位置"卡片（嵌入 SiteMapClient 地图）替换为"图片"卡片
- 添加 `referrerPolicy="no-referrer"`
- 移除 SiteMapClient 导入依赖
