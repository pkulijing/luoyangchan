# 第12轮：图片采集 - 开发总结

## 开发项背景

数据库中 5171 条文保单位的 `image_url` 全部为空，详情面板和详情页无法展示站点图片。需要批量采集图片 URL 填充该字段。

## 方案演变

### Wikipedia 方案（已放弃）

初始使用 Wikipedia `prop=pageimages` API，命中率 43%（1698/3920）。但发现 **`upload.wikimedia.org` 在中国大陆被墙**，图片无法加载，方案不可行。

### 百度百科方案（最终采用）

改用百度百科 BaikeLemmaCardApi，图片托管在 `bkimg.cdn.bcebos.com`（百度云 CDN），国内可直接访问。通过多策略查询（词条名 + 站点名 + 去后缀变体）将命中率从 40% 提升到 69%。

## 实现方案

### 关键设计

1. **多策略查询**：依次尝试百科词条名、站点原名、去常见后缀变体，最大化命中率
2. **防盗链绕过**：百度 CDN 使用 Referer 防盗链，空 Referer 放行。前端 `<img>` 标签添加 `referrerPolicy="no-referrer"`
3. **完全替换**：有百度图片的用百度图片，无百度图片的清空 `image_url`（不保留不可访问的 Wikipedia 图片）

### 开发内容

| 文件 | 操作 | 说明 |
|---|---|---|
| `scripts/round6/fetch_baike_images.py` | 新增 | 百度百科图片批量抓取脚本（多策略查询） |
| `scripts/round6/fetch_wikipedia_images.py` | 新增 | Wikipedia 图片抓取脚本（已弃用） |
| `scripts/round6/apply_images.py` | 新增 | 合并图片 URL 到主数据文件 |
| `data/round6/baike_images.json` | 生成 | 百度百科图片中间结果（5171 条） |
| `data/heritage_sites_geocoded.json` | 更新 | 3569 条记录写入百度百科 `image_url` |
| `src/components/site/SiteDetailPanel.tsx` | 修改 | 面板顶部添加图片 + referrerPolicy |
| `src/app/site/[releaseId]/page.tsx` | 修改 | 地图替换为图片卡片 + referrerPolicy |

### 抓取结果

| 指标 | 百度百科 | Wikipedia（已弃用） |
|---|---|---|
| 查询记录数 | 5171 | 3920 |
| 成功获取主图 | 3569 (69%) | 1698 (43%) |
| 总数据覆盖率 | 69% | 32% |
| 国内可访问 | 是 | 否（被墙） |

### 调研额外产出

对百度百科图片防盗链机制、BaikeLemmaCardApi、以及多种开放图片源（Wikimedia Commons、Wikidata、Openverse、Flickr 等）进行了详细调研。

## 局限性

- BaikeLemmaCardApi 是非官方接口，无 SLA 保证，可能随时失效
- 31% 的站点（1602 条）仍无图片，主要是冷门站点在百度百科也无配图
- 百度 CDN 防盗链依赖 `referrerPolicy="no-referrer"`，若百度改为也拦截空 Referer 则图片会失效

## 后续 TODO

- **图片尺寸优化**：百度 CDN 支持 `x-bce-process` 参数控制缩略图大小，可优化加载速度
- **自有存储兜底**：将图片下载到 Supabase Storage，彻底摆脱对外部 CDN 的依赖
