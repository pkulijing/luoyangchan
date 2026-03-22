-- 支持一个文保单位包含多个物理地点（父子关系）
-- 父记录：代表官方文保单位（如"长城"），可无坐标，_is_parent=true
-- 子记录：代表实际物理地点（如"长城-齐长城遗址"），parent_id 指向父记录
-- 独立记录：parent_id IS NULL，即现有 95% 的普通条目，完全不受影响

ALTER TABLE heritage_sites
  ADD COLUMN parent_id UUID REFERENCES heritage_sites(id) ON DELETE SET NULL;

CREATE INDEX idx_heritage_sites_parent_id ON heritage_sites (parent_id);
