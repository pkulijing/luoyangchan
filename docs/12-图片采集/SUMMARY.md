# 第12轮：图片采集 - 开发总结

## 开发项背景

数据库中 5171 条文保单位的 `image_url` 全部为空，详情面板和详情页无法展示站点图片。需要批量采集图片 URL 填充该字段。

## 方案演变

### Wikipedia 方案（已放弃）

初始使用 Wikipedia `prop=pageimages` API，命中率 43%（1698/3920）。但发现 **`upload.wikimedia.org` 在中国大陆被墙**，图片无法加载，方案不可行。

### 百度百科单一来源（中间方案）

改用百度百科 BaikeLemmaCardApi，图片托管在 `bkimg.cdn.bcebos.com`（百度云 CDN），国内可直接访问。通过多策略查询将命中率提升到 69%。但百度 CDN 依赖 `referrerPolicy="no-referrer"` 绕过防盗链，存在被封风险。

### 双来源 + 4 级优先级（最终方案）

将 Wikimedia Commons 图片下载到 Supabase Storage 自托管，同时保留百度百科 CDN 图片作为补充。前端按优先级展示：

1. **自托管图片**（`image_url`）：Supabase Storage 相对路径，40% 覆盖率
2. **百度百科图片**（`baike_image_url`）：百度 CDN URL，可通过 `NEXT_PUBLIC_USE_BAIKE_IMAGES` 配置关闭，69% 覆盖率
3. **天地图卫星图**：有坐标时的兜底方案
4. **占位提示**：无任何图片来源时显示

百度搜索图片链接在所有情况下始终显示。

两种来源合计覆盖 82%（4254/5171），仅 917 条站点完全无图。

## 实现方案

### 关键设计

1. **双字段分离**：`image_url`（自托管相对路径）和 `baike_image_url`（百度 CDN 完整 URL）独立存储，互不干扰
2. **相对路径存储**：`image_url` 存储为 `site-images/{release_id}.jpg` 格式，前端拼接 `NEXT_PUBLIC_SUPABASE_URL` 构造完整 URL，避免硬编码 localhost
3. **配置控制**：`NEXT_PUBLIC_USE_BAIKE_IMAGES` 环境变量控制百度图片开关，默认启用
4. **防盗链绕过**：百度 CDN 图片使用 `referrerPolicy="no-referrer"`
5. **始终显示搜索链接**：无论使用哪级图片来源，百度搜索图片链接始终显示

### 开发内容

| 文件 | 操作 | 说明 |
|---|---|---|
| `supabase/migrations/20240109000000_add_baike_image_url.sql` | 新增 | 百度百科图片 URL 列 |
| `scripts/round6/fix_image_urls.py` | 新增 | 修复 JSON 数据：恢复百度 URL + 修正 Supabase 相对路径 |
| `scripts/round6/fetch_baike_images.py` | 已有 | 百度百科图片批量抓取脚本 |
| `scripts/round6/download_to_supabase.py` | 已有 | Wikimedia 图片下载到 Supabase Storage |
| `scripts/db/seed_supabase.py` | 修改 | make_row 增加 baike_image_url 字段 |
| `src/lib/types.ts` | 修改 | HeritageSite 增加 baike_image_url |
| `src/components/site/SiteImage.tsx` | 重写 | 4 级优先级 + 始终显示搜索链接 |
| `src/components/site/SiteDetailPanel.tsx` | 修改 | 传递 baikeImageUrl prop |
| `src/app/site/[releaseId]/page.tsx` | 修改 | 传递 baikeImageUrl prop |
| `.env.example` | 修改 | 新增 NEXT_PUBLIC_USE_BAIKE_IMAGES |
| `docs/12-图片采集/PROMPT.md` | 更新 | 反映最终方案 |
| `docs/12-图片采集/PLAN.md` | 更新 | 反映最终方案 |

### 图片覆盖率

| 来源 | 数量 | 覆盖率 |
|---|---|---|
| Supabase 自托管 | 2107 | 40% |
| 百度百科 CDN | 3569 | 69% |
| 两者任一 | 4254 | 82% |
| 无图片 | 917 | 18% |

## 局限性

- BaikeLemmaCardApi 是非官方接口，无 SLA 保证
- 百度 CDN 防盗链依赖 `referrerPolicy="no-referrer"`，若百度改策略则失效
- 18% 的站点仍无图片，主要是冷门站点
- Supabase Storage 中的 Wikimedia 图片是一次性下载，新增图片需手动补充

## 后续 TODO

- 补充更多 Wikimedia Commons 图片（当前仅覆盖 40%）
- 百度 CDN 图片尺寸优化（`x-bce-process` 参数控制缩略图）
- 考虑将百度 CDN 图片也下载到自有存储，彻底摆脱外部依赖
