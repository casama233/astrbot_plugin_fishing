-- ========================================
-- 全面卡池平衡優化 SQL 腳本
-- ========================================

USE fish;
SET NAMES utf8mb4;

-- ========================================
-- 卡池 1：稀有魚竿池 (成本 6000 金幣)
-- 適合中級玩家，提供 3-5 星魚竿
-- ========================================
DELETE FROM gacha_pool_items WHERE gacha_pool_id = 1;

-- 高級魚竿 (總權重 40, 約 10%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(1, 'rod', 4, 20, 1),  -- 星辰釣者 (4星)
(1, 'rod', 5, 15, 1),  -- 海神之賜 (4星)
(1, 'rod', 6, 5, 1);   -- 潮汐復合竿 (3星)

-- 中級魚竿 (總權重 60, 約 15%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(1, 'rod', 3, 30, 1),  -- 碳素纖維竿 (3星)
(1, 'rod', 7, 20, 1),  -- 追風競技竿 (4星)
(1, 'rod', 8, 10, 1);  -- 深海諧振竿 (4星)

-- 金幣保底 (總權重 200, 約 50%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(1, 'coins', 0, 120, 2000),  -- 2000 金幣
(1, 'coins', 0, 60, 4000),   -- 4000 金幣
(1, 'coins', 0, 20, 8000);   -- 8000 金幣

-- 魚餌補充 (總權重 100, 約 25%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(1, 'bait', 1, 40, 3),
(1, 'bait', 2, 35, 3),
(1, 'bait', 3, 25, 3);

-- ========================================
-- 卡池 2：珍貴飾品池 (成本 9000 金幣)
-- 適合高級玩家，提供 3-5 星飾品
-- ========================================
DELETE FROM gacha_pool_items WHERE gacha_pool_id = 2;

-- 高級飾品 (總權重 35, 約 12%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(2, 'accessory', 4, 15, 1),  -- 海洋之心 (5星)
(2, 'accessory', 7, 10, 1),  -- 海皇徽記 (5星)
(2, 'accessory', 8, 10, 1);  -- 深淵王冠碎片 (6星)

-- 中級飾品 (總權重 55, 約 18%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(2, 'accessory', 3, 25, 1),  -- 豐收號角 (4星)
(2, 'accessory', 6, 20, 1),  -- 遠航羅盤 (4星)
(2, 'accessory', 11, 10, 1); -- 潮鳴耳墜 (4星)

-- 金幣保底 (總權重 150, 約 50%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(2, 'coins', 0, 80, 3000),
(2, 'coins', 0, 50, 6000),
(2, 'coins', 0, 20, 12000);

-- 魚餌補充 (總權重 60, 約 20%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(2, 'bait', 4, 25, 2),
(2, 'bait', 5, 20, 2),
(2, 'bait', 6, 15, 2);

-- ========================================
-- 卡池 3：每日補給池 (免費)
-- 提供基礎物資
-- ========================================
DELETE FROM gacha_pool_items WHERE gacha_pool_id = 3;

-- 魚餌 (總權重 150, 約 50%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(3, 'bait', 1, 50, 5),
(3, 'bait', 2, 50, 5),
(3, 'bait', 3, 30, 5),
(3, 'bait', 4, 20, 3);

-- 小額金幣 (總權重 100, 約 33%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(3, 'coins', 0, 60, 500),
(3, 'coins', 0, 30, 1000),
(3, 'coins', 0, 10, 2000);

-- 基礎道具 (總權重 50, 約 17%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(3, 'item', 1, 30, 1),  -- 小錢袋
(3, 'item', 2, 20, 1);  -- 幸運藥水

-- ========================================
-- 卡池 10：鯨落巨物·深淵限定池 (成本 22000 金幣)
-- 高級限定池，提供 6-7 星裝備和鯨落系列
-- ========================================
-- 已在上面優化

-- ========================================
-- 卡池 11：鯨落巨物·創意裝備池 (成本 26000 金幣)
-- 最高級池，提供 5-7 星裝備
-- ========================================
DELETE FROM gacha_pool_items WHERE gacha_pool_id = 11;

-- 頂級裝備 (總權重 30, 約 5%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(11, 'rod', 29, 12, 1),     -- 鯨落·巨脊長竿 (7星)
(11, 'rod', 31, 8, 1),      -- 幽藍脊骨竿 (5星)
(11, 'accessory', 31, 10, 1); -- 鯨落·深淵祈珂 (7星)

-- 高級裝備 (總權重 60, 約 10%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(11, 'rod', 30, 20, 1),     -- 潮紋斷脊竿 (6星)
(11, 'accessory', 32, 15, 1), -- 濁潮耳語 (6星)
(11, 'accessory', 33, 15, 1), -- 鯨落鳴石 (5星)
(11, 'rod', 20, 10, 1);     -- 霧隱航標竿 (6星)

-- 稀有魚類 (總權重 150, 約 25%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(11, 'fish', 163, 40, 1), -- 白鯨祀歌者 (6星)
(11, 'fish', 164, 35, 1), -- 潮汐巨脊鯨 (6星)
(11, 'fish', 165, 30, 1), -- 深淵喉音鯨 (6星)
(11, 'fish', 166, 25, 1), -- 鯨落守護者 (5星)
(11, 'fish', 167, 20, 1); -- 裂潮鯨影 (5星)

-- 高級魚餌 (總權重 100, 約 17%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(11, 'bait', 15, 40, 1), -- 鯨落·災潮誘餌 (7星)
(11, 'bait', 16, 35, 1), -- 巨物碎脂餌 (5星)
(11, 'bait', 17, 25, 1); -- 低鳴鯨脂膏 (4星)

-- 金幣獎勵 (總權重 180, 約 30%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(11, 'coins', 0, 100, 3000),
(11, 'coins', 0, 50, 6000),
(11, 'coins', 0, 30, 10000);

-- 道具 (總權重 80, 約 13%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(11, 'item', 24, 35, 1),
(11, 'item', 25, 25, 1),
(11, 'item', 26, 20, 1);

-- ========================================
-- 顯示優化結果
-- ========================================
SELECT '========== 卡池優化完成 ==========' AS '';

SELECT 
    '池 1 - 稀有魚竿池' AS pool_name,
    COUNT(*) AS item_count,
    SUM(weight) AS total_weight,
    '6000金幣/次，3-5星魚竿為主' AS description
FROM gacha_pool_items WHERE gacha_pool_id = 1
UNION ALL
SELECT 
    '池 2 - 珍貴飾品池',
    COUNT(*),
    SUM(weight),
    '9000金幣/次，3-6星飾品為主'
FROM gacha_pool_items WHERE gacha_pool_id = 2
UNION ALL
SELECT 
    '池 3 - 每日補給池',
    COUNT(*),
    SUM(weight),
    '免費，基礎物資'
FROM gacha_pool_items WHERE gacha_pool_id = 3
UNION ALL
SELECT 
    '池 10 - 鯨落深淵池',
    COUNT(*),
    SUM(weight),
    '22000金幣/次，6-7星裝備+鯨落系列'
FROM gacha_pool_items WHERE gacha_pool_id = 10
UNION ALL
SELECT 
    '池 11 - 鯨落裝備池',
    COUNT(*),
    SUM(weight),
    '26000金幣/次，5-7星頂級裝備'
FROM gacha_pool_items WHERE gacha_pool_id = 11;

