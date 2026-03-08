# Bugfix Requirements Document

## Introduction

本文檔針對 Discord 釣魚遊戲插件中的多個系統性問題進行修復，主要包括：
1. **圖片渲染高度計算錯誤** - 所有圖片渲染指令（背包、商店、裝備等）在物品數量較多時，生成的圖片高度不足導致內容被裁剪
2. **遊戲數值平衡性問題** - 魚竿、飾品、道具、魚餌的數值設定可能存在不合理之處
3. **指令系統冗餘問題** - 存在過多獨立指令，部分功能重複或可合併
4. **操作指南同步問題** - 釣魚幫助文檔未能實時反映當前功能狀態

這些問題影響了玩家體驗，特別是圖片裁剪問題會導致玩家無法看到完整的物品信息。

## Bug Analysis

### Current Behavior (Defect)

#### 1. 圖片渲染問題

1.1 WHEN 背包中物品數量較多時 THEN 系統生成的背包圖片高度不足，底部物品被裁剪無法顯示

1.2 WHEN 使用任何圖片渲染類指令（商店、裝備、狀態、魚塘等）且內容較多時 THEN 系統生成的圖片底部內容被截斷

1.3 WHEN 背包中有多個魚竿或飾品時 THEN 卡片可能重疊或文字位置擠壓變形

1.4 WHEN 物品描述文字過長時 THEN 文字可能超出卡片邊界或被截斷

1.5 WHEN 計算圖片高度時 THEN 系統未正確考慮所有內容區域的實際高度需求

#### 2. 數值平衡性問題（需調查）

1.6 WHEN 檢查魚竿數據時 THEN 可能存在某些魚竿的屬性加成過高或過低，導致遊戲平衡性問題

1.7 WHEN 檢查飾品數據時 THEN 可能存在某些飾品效果重複或數值不合理

1.8 WHEN 檢查魚餌數據時 THEN 可能存在某些魚餌的效果與成本不匹配

1.9 WHEN 檢查道具數據時 THEN 可能存在某些道具的實際作用與描述不符或效果過強/過弱

#### 3. 指令系統問題（需調查）

1.10 WHEN 查看所有指令列表時 THEN 存在過多功能相似的獨立指令，增加玩家學習成本

1.11 WHEN 使用某些指令時 THEN 需要多次操作才能完成簡單任務，操作流程冗餘

1.12 WHEN 新玩家學習指令時 THEN 指令數量過多且分類不清晰，難以快速上手

#### 4. 操作指南問題

1.13 WHEN 使用 /釣魚幫助 指令時 THEN 顯示的幫助內容可能與當前實際功能不一致

1.14 WHEN 新增或修改功能後 THEN 幫助文檔未能同步更新，導致玩家獲取錯誤信息

### Expected Behavior (Correct)

#### 1. 圖片渲染修復

2.1 WHEN 背包中物品數量較多時 THEN 系統 SHALL 正確計算所需圖片高度，確保所有物品完整顯示

2.2 WHEN 使用任何圖片渲染類指令時 THEN 系統 SHALL 動態計算內容高度，確保圖片底部不被截斷

2.3 WHEN 背包中有多個魚竿或飾品時 THEN 系統 SHALL 正確佈局卡片位置，避免重疊和文字擠壓

2.4 WHEN 物品描述文字過長時 THEN 系統 SHALL 自動截斷或換行處理，確保文字在卡片邊界內

2.5 WHEN 計算圖片高度時 THEN 系統 SHALL 準確累加所有區域高度（標題欄、各分類區域、底部提示、間距等）

#### 2. 數值平衡性優化

2.6 WHEN 檢查魚竿數據時 THEN 系統 SHALL 確保各稀有度魚竿的屬性加成呈合理遞增關係

2.7 WHEN 檢查飾品數據時 THEN 系統 SHALL 確保飾品效果不重複且數值與稀有度匹配

2.8 WHEN 檢查魚餌數據時 THEN 系統 SHALL 確保魚餌效果與成本成正比，且消耗型與永久型魚餌平衡

2.9 WHEN 檢查道具數據時 THEN 系統 SHALL 確保道具實際作用與描述一致，且效果強度合理

#### 3. 指令系統優化

2.10 WHEN 查看所有指令列表時 THEN 系統 SHALL 提供精簡且分類清晰的指令集，減少冗餘指令

2.11 WHEN 使用常見功能時 THEN 系統 SHALL 提供簡化的操作流程，減少不必要的步驟

2.12 WHEN 新玩家學習指令時 THEN 系統 SHALL 提供清晰的指令分類和使用說明，降低學習門檻

#### 4. 操作指南同步

2.13 WHEN 使用 /釣魚幫助 指令時 THEN 系統 SHALL 顯示與當前功能完全一致的幫助內容

2.14 WHEN 新增或修改功能後 THEN 系統 SHALL 同步更新幫助文檔，確保玩家獲取準確信息

### Unchanged Behavior (Regression Prevention)

#### 1. 圖片渲染功能保持

3.1 WHEN 物品數量較少時 THEN 系統 SHALL CONTINUE TO 正常生成圖片，不出現多餘空白

3.2 WHEN 使用圖片渲染指令時 THEN 系統 SHALL CONTINUE TO 保持現有的視覺風格和配色方案

3.3 WHEN 生成背包圖片時 THEN 系統 SHALL CONTINUE TO 正確顯示物品的所有屬性信息（稀有度、ID、屬性加成等）

3.4 WHEN 渲染卡片時 THEN 系統 SHALL CONTINUE TO 保持圓角、陰影、邊框等視覺效果

#### 2. 遊戲核心機制保持

3.5 WHEN 使用魚竿釣魚時 THEN 系統 SHALL CONTINUE TO 正確應用魚竿的屬性加成

3.6 WHEN 裝備飾品時 THEN 系統 SHALL CONTINUE TO 正確疊加飾品的各項效果

3.7 WHEN 使用魚餌時 THEN 系統 SHALL CONTINUE TO 正確應用魚餌的特殊效果

3.8 WHEN 使用道具時 THEN 系統 SHALL CONTINUE TO 正確執行道具的功能效果

#### 3. 指令功能保持

3.9 WHEN 使用現有指令時 THEN 系統 SHALL CONTINUE TO 執行相同的功能邏輯

3.10 WHEN 玩家使用別名指令時 THEN 系統 SHALL CONTINUE TO 正確識別並執行對應功能

3.11 WHEN 執行管理員指令時 THEN 系統 SHALL CONTINUE TO 正確驗證權限並執行操作

#### 4. 數據完整性保持

3.12 WHEN 修改數值配置時 THEN 系統 SHALL CONTINUE TO 保持現有玩家的裝備和道具數據完整性

3.13 WHEN 優化指令系統時 THEN 系統 SHALL CONTINUE TO 保持玩家的遊戲進度和資產不受影響

3.14 WHEN 更新幫助文檔時 THEN 系統 SHALL CONTINUE TO 保持其他功能模組正常運作
