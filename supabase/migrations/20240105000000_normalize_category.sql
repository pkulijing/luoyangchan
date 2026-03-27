-- 添加 original_category 字段保存历史分类原始值
ALTER TABLE heritage_sites ADD COLUMN IF NOT EXISTS original_category TEXT;

-- 迁移 4 种历史分类到现代分类
UPDATE heritage_sites SET original_category = category, category = '近现代重要史迹及代表性建筑'
WHERE category = '革命遗址及革命纪念建筑物';

UPDATE heritage_sites SET original_category = category, category = '古建筑'
WHERE category = '古建筑及历史纪念建筑物';

UPDATE heritage_sites SET original_category = category, category = '石窟寺及石刻'
WHERE category = '石窟寺';

UPDATE heritage_sites SET original_category = category, category = '石窟寺及石刻'
WHERE category = '石刻及其他';
