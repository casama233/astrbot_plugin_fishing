-- ========================================
-- 卡池 10 優化 SQL 腳本
-- 鯨落巨物·深淵限定池
-- ========================================

-- 使用數據庫
USE fish;

-- 查看優化前的配置
SELECT '========== 優化前配置 ==========' AS '';
SELECT 
    gpi.gacha_pool_item_id,
    gpi.item_type,
    gpi.item_id,
    CASE gpi.item_type
        WHEN 'rod' THEN (SELECT name FROM rods WHERE rod_id = gpi.item_id)
        WHEN 'accessory' THEN (SELECT name FROM accessories WHERE accessory_id = gpi.item_id)
        WHEN 'bait' THEN (SELECT name FROM baits WHERE bait_id = gpi.item_id)
        WHEN 'fish' THEN (SELECT name FROM fish WHERE fish_id = gpi.item_id)
        WHEN 'item' THEN (SELECT name FROM items WHERE item_id = gpi.item_id)
        WHEN 'coins' THEN CONCAT(gpi.quantity, ' 金幣')
        ELSE '未知'
    END AS name,
    gpi.weight,
    ROUND(gpi.weight / (SELECT SUM(weight) FROM gacha_pool_items WHERE gacha_pool_id = 10) * 100, 2) AS probability_pct,
    gpi.quantity
FROM gacha_pool_items gpi
WHERE gpi.gacha_pool_id = 10
ORDER BY gpi.weight DESC;

-- ========================================
-- 優化方案：
-- 1. 移除過多的低稀有度魚類（保留鯨落系列和部分普通魚）
-- 2. 降低道具物品權重
-- 3. 提高稀有裝備的權重
-- 4. 整合金幣獎勵
-- ========================================

-- 刪除舊配置
DELETE FROM gacha_pool_items WHERE gacha_pool_id = 10;

-- ========================================
-- 重新插入優化後的配置
-- ========================================

-- 【核心獎勵 - 鯨落系列】高稀有度裝備 (總權重: 100, 佔比: ~6%)
-- 7星魚竿 - 總權重 40 (抽中率 ~2.4%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(10, 'rod', 29, 25, 1),   -- 鯨落·巨脊長竿 (7星) - 權重提高
(10, 'rod', 31, 15, 1);   -- 幽藍脊骨竿 (5星)

-- 6-7星飾品 - 總權重 35 (抽中率 ~2.1%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(10, 'accessory', 31, 20, 1), -- 鯨落·深淵祈珂 (7星)
(10, 'accessory', 32, 15, 1); -- 濁潮耳語 (6星)

-- 6星魚竿 - 權重 25
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(10, 'rod', 30, 25, 1);   -- 潮紋斷脊竿 (6星)

-- 【稀有魚類 - 鯨落系列】(總權重: 120, 佔比: ~7.2%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(10, 'fish', 163, 50, 1), -- 白鯨祀歌者 (6星)
(10, 'fish', 164, 40, 1), -- 潮汐巨脊鯨 (6星)
(10, 'fish', 165, 30, 1); -- 深淵喉音鯨 (6星)

-- 【高級魚餌】(總權重: 180, 佔比: ~10.8%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(10, 'bait', 15, 60, 1),  -- 鯨落·災潮誘餌 (7星)
(10, 'bait', 16, 50, 1),  -- 巨物碎脂餌 (5星)
(10, 'bait', 17, 40, 1),  -- 低鳴鯨脂膏 (4星)
(10, 'bait', 1, 30, 3);   -- 普通蚯蚓 x3 (實用性)

-- 【金幣獎勵】整合為三檔 (總權重: 500, 佔比: ~30%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(10, 'coins', 0, 300, 2000),  -- 中檔獎勵 2000金幣 (常見)
(10, 'coins', 0, 150, 5000),  -- 高檔獎勵 5000金幣 (較少)
(10, 'coins', 0, 50, 10000);  -- 頂級獎勵 10000金幣 (稀有)

-- 【道具獎勵】降低權重 (總權重: 300, 佔比: ~18%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(10, 'item', 23, 120, 1), -- 破洞零錢袋 (1星道具)
(10, 'item', 24, 100, 1), -- 油漬零錢盒
(10, 'item', 25, 80, 1);  -- 發霉布袋

-- 【普通魚類】保留部分作為保底 (總權重: 395, 佔比: ~23.7%)
INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, weight, quantity) VALUES
(10, 'fish', 1, 80, 1),  -- 小鯽魚
(10, 'fish', 2, 80, 1),  -- 泥鰍
(10, 'fish', 3, 75, 1),  -- 小蝦
(10, 'fish', 4, 70, 1),  -- 沙丁魚
(10, 'fish', 5, 60, 1),  -- 小黃魚
(10, 'fish', 7, 30, 1);  -- 鯪魚 (稍微降低)

-- ========================================
-- 查看優化後的配置
-- ========================================
SELECT '========== 優化後配置 ==========' AS '';
SELECT 
    gpi.gacha_pool_item_id,
    gpi.item_type,
    gpi.item_id,
    CASE gpi.item_type
        WHEN 'rod' THEN (SELECT name FROM rods WHERE rod_id = gpi.item_id)
        WHEN 'accessory' THEN (SELECT name FROM accessories WHERE accessory_id = gpi.item_id)
        WHEN 'bait' THEN (SELECT name FROM baits WHERE bait_id = gpi.item_id)
        WHEN 'fish' THEN (SELECT name FROM fish WHERE fish_id = gpi.item_id)
        WHEN 'item' THEN (SELECT name FROM items WHERE item_id = gpi.item_id)
        WHEN 'coins' THEN CONCAT(gpi.quantity, ' 金幣')
        ELSE '未知'
    END AS name,
    gpi.weight,
    ROUND(gpi.weight / (SELECT SUM(weight) FROM gacha_pool_items WHERE gacha_pool_id = 10) * 100, 2) AS probability_pct,
    gpi.quantity
FROM gacha_pool_items gpi
WHERE gpi.gacha_pool_id = 10
ORDER BY gpi.weight DESC;

-- 計算總權重
SELECT '========== 統計 ==========' AS '';
SELECT 
    SUM(weight) AS total_weight,
    COUNT(*) AS total_items,
    '期望價值：每次抽卡平均獲得約 2500-3000 金幣等值物品' AS note
FROM gacha_pool_items 
WHERE gacha_pool_id = 10;

