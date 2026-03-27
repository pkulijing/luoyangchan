# 第12轮：图片采集 - 实现计划

## 方案演变

### 初始方案：Wikipedia pageimages（已放弃）

使用 MediaWiki API `prop=pageimages` 批量获取文章主图，命中率 43%（1698/3920）。
**放弃原因**：`upload.wikimedia.org` 在中国大陆被墙，图片无法加载。

### 中间方案：百度百科单一来源（已迭代）

使用百度百科 BaikeLemmaCardApi 获取词条主图，命中率 69%（3569/5171）。
问题：百度 CDN 依赖 `referrerPolicy="no-referrer"` 绕过防盗链，存在被封风险。

### 最终方案：双来源 + 4 级优先级

- 数据层分离：`image_url`（自托管 Supabase Storage）和 `baike_image_url`（百度 CDN）
- 前端按优先级展示：自托管 → 百度（可配置关闭）→ 天地图卫星 → 占位提示

## 数据层改动

### 新增 `baike_image_url` 列

**迁移文件**：`supabase/migrations/20240109000000_add_baike_image_url.sql`

```sql
ALTER TABLE heritage_sites ADD COLUMN baike_image_url TEXT;
```

### 修复 JSON 数据

**脚本**：`scripts/round6/fix_image_urls.py`

1. 从 `data/round6/baike_images.json` 恢复百度图片 URL 到 `baike_image_url` 字段
2. 将 `image_url` 中的绝对 localhost URL 转为相对存储路径：
   - `http://127.0.0.1:54321/storage/v1/object/public/site-images/1-1.jpg` → `site-images/1-1.jpg`

### 更新 seed 脚本

`seed_supabase.py` 的 `make_row()` 增加 `baike_image_url` 字段。

## 前端改动

### 类型定义

`src/lib/types.ts`：`HeritageSite` 增加 `baike_image_url: string | null`

### SiteImage 组件

`src/components/site/SiteImage.tsx`：

接收 `imageUrl`（自托管相对路径）和 `baikeImageUrl`（百度 CDN URL），按优先级展示：

1. `imageUrl` 非空 → 拼接 `NEXT_PUBLIC_SUPABASE_URL` 构造完整 URL
2. `baikeImageUrl` 非空且 `NEXT_PUBLIC_USE_BAIKE_IMAGES !== 'false'` → 使用百度 CDN（需 `referrerPolicy="no-referrer"`）
3. 有坐标 → 天地图卫星静态图
4. 占位提示

所有情况下均显示百度搜索图片链接（不仅限于占位时）。

### 使用方

- `SiteDetailPanel.tsx`：传递 `baikeImageUrl={site.baike_image_url}`
- `site/[releaseId]/page.tsx`：同上

### 环境变量

`.env.example` 新增：
```
NEXT_PUBLIC_USE_BAIKE_IMAGES=true
```

## 验证

1. `npx tsc --noEmit` 编译通过
2. 有 Supabase 图片的站点优先显示自托管图片
3. 无 Supabase 图片但有百度图片的站点显示百度 CDN 图片
4. 设置 `NEXT_PUBLIC_USE_BAIKE_IMAGES=false` 后，百度图片被跳过
5. 两者都无时显示天地图卫星图
6. 完全无图无坐标时显示占位提示
7. 所有情况下均显示百度搜索图片链接
