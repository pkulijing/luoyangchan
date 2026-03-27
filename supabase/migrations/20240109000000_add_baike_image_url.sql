-- 新增百度百科图片 URL 字段（独立于自托管 image_url）
ALTER TABLE heritage_sites ADD COLUMN baike_image_url TEXT;
