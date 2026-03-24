-- 新增 tags 和 baike_url 字段，支持数据富化和搜索
ALTER TABLE heritage_sites ADD COLUMN tags TEXT[];
ALTER TABLE heritage_sites ADD COLUMN baike_url TEXT;

-- GIN 索引加速 tags 数组查询
CREATE INDEX idx_heritage_sites_tags ON heritage_sites USING GIN(tags);
