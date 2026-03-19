-- 添加官方数据来源字段
-- release_id: 官方编号，格式如 "1-1-105"（批次-序号-分类号）
-- release_address: 官方原始地址文本

ALTER TABLE heritage_sites ADD COLUMN release_id TEXT;
ALTER TABLE heritage_sites ADD COLUMN release_address TEXT;

CREATE INDEX idx_heritage_sites_release_id ON heritage_sites (release_id);
