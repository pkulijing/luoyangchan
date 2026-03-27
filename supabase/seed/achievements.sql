-- 成就种子数据
-- 注意：此文件需要在 heritage_sites 数据导入后执行

-- 清空现有成就定义
TRUNCATE achievement_definitions CASCADE;

-- ===========================
-- 总数进度成就
-- ===========================
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('total_10', '初探文脉', '累计去过 10 个文保单位', '🏛️', 'common', 'total_count', '{"count": 10}', 10),
('total_50', '文化行者', '累计去过 50 个文保单位', '🎒', 'common', 'total_count', '{"count": 50}', 30),
('total_100', '文保达人', '累计去过 100 个文保单位', '🏆', 'rare', 'total_count', '{"count": 100}', 50),
('total_500', '文保大师', '累计去过 500 个文保单位', '👑', 'epic', 'total_count', '{"count": 500}', 200),
('total_1000', '文脉守护者', '累计去过 1000 个文保单位', '🌟', 'legendary', 'total_count', '{"count": 1000}', 500);

-- ===========================
-- 类别进度成就
-- ===========================
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
-- 古遗址
('category_ancient_site_10', '遗址探索者', '去过 10 个古遗址', '🏚️', 'common', 'category_count', '{"category": "古遗址", "count": 10}', 15),
('category_ancient_site_50', '遗址考察家', '去过 50 个古遗址', '🏚️', 'rare', 'category_count', '{"category": "古遗址", "count": 50}', 50),
-- 古墓葬
('category_tomb_10', '古墓探险家', '去过 10 个古墓葬', '⚱️', 'common', 'category_count', '{"category": "古墓葬", "count": 10}', 15),
('category_tomb_50', '墓葬研究者', '去过 50 个古墓葬', '⚱️', 'rare', 'category_count', '{"category": "古墓葬", "count": 50}', 50),
-- 古建筑
('category_building_10', '古建爱好者', '去过 10 个古建筑', '🏯', 'common', 'category_count', '{"category": "古建筑", "count": 10}', 15),
('category_building_50', '古建鉴赏家', '去过 50 个古建筑', '🏯', 'rare', 'category_count', '{"category": "古建筑", "count": 50}', 50),
('category_building_100', '古建大师', '去过 100 个古建筑', '🏯', 'epic', 'category_count', '{"category": "古建筑", "count": 100}', 100),
-- 石窟寺及石刻
('category_grotto_10', '石刻寻访者', '去过 10 个石窟寺及石刻', '🪨', 'common', 'category_count', '{"category": "石窟寺及石刻", "count": 10}', 15),
('category_grotto_30', '石窟守护者', '去过 30 个石窟寺及石刻', '🪨', 'rare', 'category_count', '{"category": "石窟寺及石刻", "count": 30}', 50),
-- 近现代
('category_modern_10', '近代史行者', '去过 10 个近现代重要史迹', '🏢', 'common', 'category_count', '{"category": "近现代重要史迹及代表性建筑", "count": 10}', 15),
('category_modern_50', '近代史研究者', '去过 50 个近现代重要史迹', '🏢', 'rare', 'category_count', '{"category": "近现代重要史迹及代表性建筑", "count": 50}', 50);

-- ===========================
-- 省份进度成就（示例：主要文保大省）
-- ===========================
-- 河南省
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_henan_10', '中原初探', '去过河南省 10 个文保单位', '🏛️', 'common', 'province_count', '{"province": "河南省", "count": 10}', 15),
('province_henan_50', '中原行者', '去过河南省 50 个文保单位', '🏛️', 'rare', 'province_count', '{"province": "河南省", "count": 50}', 50),
('province_henan_100', '中原通', '去过河南省 100 个文保单位', '🏛️', 'epic', 'province_count', '{"province": "河南省", "count": 100}', 100);

-- 陕西省
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_shaanxi_10', '三秦初探', '去过陕西省 10 个文保单位', '🏛️', 'common', 'province_count', '{"province": "陕西省", "count": 10}', 15),
('province_shaanxi_50', '三秦行者', '去过陕西省 50 个文保单位', '🏛️', 'rare', 'province_count', '{"province": "陕西省", "count": 50}', 50),
('province_shaanxi_100', '三秦通', '去过陕西省 100 个文保单位', '🏛️', 'epic', 'province_count', '{"province": "陕西省", "count": 100}', 100);

-- 山西省
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_shanxi_10', '三晋初探', '去过山西省 10 个文保单位', '🏛️', 'common', 'province_count', '{"province": "山西省", "count": 10}', 15),
('province_shanxi_50', '三晋行者', '去过山西省 50 个文保单位', '🏛️', 'rare', 'province_count', '{"province": "山西省", "count": 50}', 50),
('province_shanxi_100', '三晋通', '去过山西省 100 个文保单位', '🏛️', 'epic', 'province_count', '{"province": "山西省", "count": 100}', 100);

-- 北京市
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_beijing_10', '京城初探', '去过北京市 10 个文保单位', '🏛️', 'common', 'province_count', '{"province": "北京市", "count": 10}', 15),
('province_beijing_50', '京城行者', '去过北京市 50 个文保单位', '🏛️', 'rare', 'province_count', '{"province": "北京市", "count": 50}', 50);

-- 浙江省
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_zhejiang_10', '吴越初探', '去过浙江省 10 个文保单位', '🏛️', 'common', 'province_count', '{"province": "浙江省", "count": 10}', 15),
('province_zhejiang_50', '吴越行者', '去过浙江省 50 个文保单位', '🏛️', 'rare', 'province_count', '{"province": "浙江省", "count": 50}', 50);

-- 江苏省
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_jiangsu_10', '江南初探', '去过江苏省 10 个文保单位', '🏛️', 'common', 'province_count', '{"province": "江苏省", "count": 10}', 15),
('province_jiangsu_50', '江南行者', '去过江苏省 50 个文保单位', '🏛️', 'rare', 'province_count', '{"province": "江苏省", "count": 50}', 50);

-- 四川省
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_sichuan_10', '巴蜀初探', '去过四川省 10 个文保单位', '🏛️', 'common', 'province_count', '{"province": "四川省", "count": 10}', 15),
('province_sichuan_50', '巴蜀行者', '去过四川省 50 个文保单位', '🏛️', 'rare', 'province_count', '{"province": "四川省", "count": 50}', 50);

-- 广东省
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_guangdong_10', '岭南初探', '去过广东省 10 个文保单位', '🏛️', 'common', 'province_count', '{"province": "广东省", "count": 10}', 15),
('province_guangdong_50', '岭南行者', '去过广东省 50 个文保单位', '🏛️', 'rare', 'province_count', '{"province": "广东省", "count": 50}', 50);

-- ===========================
-- 省份全通成就（示例）
-- ===========================
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('province_complete_beijing', '京城全通', '去过北京市所有文保单位', '🏅', 'legendary', 'province_complete', '{"province": "北京市"}', 500),
('province_complete_shanghai', '魔都全通', '去过上海市所有文保单位', '🏅', 'epic', 'province_complete', '{"province": "上海市"}', 200),
('province_complete_tianjin', '津门全通', '去过天津市所有文保单位', '🏅', 'epic', 'province_complete', '{"province": "天津市"}', 200);

-- ===========================
-- 城市全通成就（示例：文保单位较少的城市）
-- ===========================
INSERT INTO achievement_definitions (code, name, description, icon, rarity, condition_type, condition_value, points) VALUES
('city_complete_luoyang', '神都全通', '去过洛阳市所有文保单位', '🥇', 'epic', 'city_complete', '{"province": "河南省", "city": "洛阳市"}', 150),
('city_complete_xian', '长安全通', '去过西安市所有文保单位', '🥇', 'epic', 'city_complete', '{"province": "陕西省", "city": "西安市"}', 150),
('city_complete_nanjing', '金陵全通', '去过南京市所有文保单位', '🥇', 'epic', 'city_complete', '{"province": "江苏省", "city": "南京市"}', 150),
('city_complete_hangzhou', '临安全通', '去过杭州市所有文保单位', '🥇', 'epic', 'city_complete', '{"province": "浙江省", "city": "杭州市"}', 150),
('city_complete_kaifeng', '汴京全通', '去过开封市所有文保单位', '🥇', 'rare', 'city_complete', '{"province": "河南省", "city": "开封市"}', 100);

-- 提示：可以根据实际需求动态生成更多省份/城市/区县的成就
-- 例如通过 SQL 脚本读取 heritage_sites 表中的所有省份，自动生成成就定义
