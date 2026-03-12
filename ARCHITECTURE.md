# 架構說明

本文檔面向開發者，說明 `astrbot_plugin_fishing` 的整體架構設計與模塊職責。

## 架構概覽

```
┌─────────────────────────────────────────────────────────────────────┐
│                           main.py                                    │
│                    (插件入口 & 依賴注入容器)                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
       ▼                       ▼                       ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  handlers/  │         │   draw/     │         │  manager/   │
│ (命令處理層)  │         │ (圖片渲染)   │         │ (後台管理)   │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        core/services/                                │
│                          (業務邏輯層)                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │UserService  │ │FishingService│ │InventorySvc │ │MarketService│  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │ExchangeSvc  │ │GachaService │ │AchievementSvc│ │SicboService │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      core/repositories/                              │
│                         (數據訪問層)                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │MysqlUserRepo│ │MysqlInvRepo │ │MysqlLogRepo │ │MysqlGachaRepo│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │MysqlShopRepo│ │MysqlMarketRp│ │MysqlExchRepo│ │MysqlAchvRepo│  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      core/database/                                  │
│                      (數據庫連接管理)                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐                │
│  │MysqlConnectionManager│    │   schema_manager    │                │
│  └─────────────────────┘    └─────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

## 核心模塊說明

### 1. main.py - 插件入口

**職責：**
- 插件初始化與配置加載
- 依賴注入容器（組裝所有服務和倉儲）
- 命令路由（將用戶輸入分發到對應 Handler）
- 後台任務調度（定時任務、清理任務）

**重要方法：**
- `__init__`: 初始化所有服務和倉儲
- `fish_cmd`: 主命令路由
- `initialize`: 插件啟動時的初始化

### 2. handlers/ - 命令處理層

**職責：**
- 解析用戶輸入
- 調用服務層方法
- 格式化輸出結果

**主要 Handler：**
| 文件 | 職責 |
|------|------|
| `fishing_handlers.py` | 釣魚、自動釣魚、區域切換 |
| `inventory_handlers.py` | 背包、魚塘、裝備、精煉、出售 |
| `market_handlers.py` | 商店、市場、上架、購買 |
| `exchange_handlers.py` | 交易所開戶、買賣、持倉 |
| `common_handlers.py` | 註冊、簽到、狀態、幫助 |
| `admin_handlers.py` | 管理員命令（修改金幣、同步數據） |
| `aquarium_handlers.py` | 水族箱管理 |
| `sicbo_handlers.py` | 骰寶遊戲 |
| `gacha_handlers.py` | 抽卡系統 |
| `social_handlers.py` | 偷魚、紅包、排行 |
| `red_packet_handlers.py` | 紅包系統 |

### 3. core/services/ - 業務邏輯層

**職責：**
- 實現核心業務邏輯
- 協調多個倉儲層操作
- 處理事務和一致性

**主要 Service：**
| 服務 | 職責 |
|------|------|
| `UserService` | 用戶註冊、簽到、狀態管理 |
| `FishingService` | 釣魚邏輯、區域管理、自動釣魚 |
| `InventoryService` | 背包管理、裝備使用、精煉 |
| `MarketService` | 市場交易、上架購買 |
| `ExchangeService` | 交易所邏輯、價格波動 |
| `ShopService` | 商店購買、限購處理 |
| `GachaService` | 抽卡邏輯、卡池管理 |
| `AchievementService` | 成就檢測、稱號授予 |
| `SicboService` | 骰寶開莊、結算 |

### 4. core/repositories/ - 數據訪問層

**職責：**
- 封裝所有數據庫操作
- 提供抽象接口（AbstractRepository）
- 實現 MySQL 存儲

**設計模式：**
- Repository Pattern（倉儲模式）
- 每個聚合根對應一個 Repository

### 5. core/domain/ - 領域模型

**職責：**
- 定義領域實體（User, Item, Fish, Rod 等）
- 數據模型與業務規則

**主要實體：**
- `User`: 用戶實體
- `Item`, `Fish`, `Rod`, `Accessory`, `Bait`: 物品實體
- `MarketListing`: 市場上架
- `ExchangeHolding`: 交易所持倉

### 6. draw/ - 圖片渲染層

**職責：**
- 生成各種狀態圖片
- 背包圖片、市場圖片、交易所圖片

### 7. manager/ - 後台管理

**職責：**
- Web 管理界面
- 模板數據管理
- 配置管理

**主要組件：**
- `server.py`: Quart 應用入口，包含所有路由定義
- `templates/`: HTML 模板目錄
- `static/`: 靜態資源（CSS、JS）

**路由結構：**
- 認證路由：登入、登出、首頁
- 物品管理：魚類、魚竿、魚餌、飾品、道具
- 抽卡管理：卡池創建、編輯、物品管理
- 用戶管理：用戶列表、詳情、庫存
- 經濟系統：交易所、市場、商店
- 區域管理：釣魚區域 CRUD

## 工具模塊

### core/utils.py

**提供的函數：**
- `to_base36(n, prefix)`: 整數轉 Base36
- `from_base36(s)`: Base36 轉整數
- `parse_display_code(code)`: 解析顯示代碼
- `get_now()`: 獲取當前時間（UTC+8）
- `get_fish_template()`: 加權隨機選擇魚模板
- `calculate_after_refine()`: 計算精煉後數值

### core/constants.py

**提供的常量：**
- `ItemType`: 物品類型枚舉
- `FishQuality`: 魚品質枚舉
- `MarketListingType`: 市場上架類型枚舉
- `ExchangeCommodity`: 交易所商品枚舉
- `DEFAULT_SELL_PRICES`: 預設售價
- `REFINE_MULTIPLIER`: 精煉倍率
- `SUBCOMMAND_ALIAS_MAP`: 子命令別名映射

### core/database/schema_manager.py

**提供的函數：**
- `ensure_mysql_runtime_schema(config)`: 確保 MySQL 表結構正確

## 數據流

### 釣魚命令流程

```
用戶輸入: /釣魚
    │
    ▼
main.py: fish_cmd()
    │
    ▼
handlers/fishing_handlers.py: fish()
    │
    ▼
services/fishing_service.py: fish()
    │
    ├─► repositories/user_repo: 扣除金幣
    ├─► repositories/inventory_repo: 消耗魚餌
    ├─► 釣魚邏輯計算
    ├─► repositories/inventory_repo: 添加魚到魚塘
    └─► repositories/log_repo: 記錄釣魚日誌
    │
    ▼
返回結果給用戶
```

### 交易所買入流程

```
用戶輸入: /交易所 買入 魚骨 100
    │
    ▼
main.py: fish_cmd() -> exchange_handlers.py
    │
    ▼
handlers/exchange_handlers.py: exchange_buy()
    │
    ▼
services/exchange_service.py: buy_commodity()
    │
    ├─► repositories/user_repo: 扣除金幣
    ├─► repositories/exchange_repo: 創建持倉
    └─► repositories/log_repo: 記錄交易
    │
    ▼
返回結果給用戶
```

## 設計原則

### 1. 分層架構

項目採用經典的三層架構：
- **表現層**: handlers/ 處理用戶交互
- **業務層**: services/ 實現業務邏輯
- **數據層**: repositories/ 封裝數據訪問

### 2. 依賴注入

所有服務和倉儲在 `main.py` 的 `FishingPlugin.__init__` 中組裝，通過構造函數注入依賴。

### 3. 單一職責

每個模塊只負責一個特定領域：
- Handler 只處理輸入解析和輸出格式化
- Service 只處理業務邏輯
- Repository 只處理數據訪問

### 4. 配置外部化

所有可配置項都在配置文件中，避免硬編碼。

## 擴展指南

### 添加新命令

1. 在 `handlers/` 中創建或修改對應的 Handler
2. 在 `main.py` 中添加命令路由
3. 在 `draw/help.py` 中更新幫助文檔

### 添加新服務

1. 在 `core/services/` 中創建新的服務類
2. 在 `main.py` 中注入依賴
3. 在 Handler 中調用服務方法

### 添加新的數據表

1. 在 `core/domain/models.py` 中定義實體
2. 在 `core/repositories/` 中創建對應的 Repository
3. 在 `core/database/schema_manager.py` 中添加表結構
4. 在 `main.py` 中注入 Repository

## 性能優化建議

### 1. 避免 N+1 查詢

在批量查詢時，使用 `IN` 查詢替代循環查詢：

```python
# 壞的寫法
for item in items:
    template = repo.get_by_id(item.id)

# 好的寫法
ids = [item.id for item in items]
templates = repo.get_by_ids(ids)
```

### 2. 使用批量操作

對於批量更新，使用批量 SQL 語句：

```python
# 壞的寫法
for item in items:
    repo.update(item)

# 好的寫法
repo.batch_update(items)
```

### 3. 圖片生成緩存

對於相同數據的圖片，考慮使用緩存避免重複生成。

## 測試建議

### 單元測試

- 測試 `core/utils.py` 中的工具函數
- 測試 `core/services/` 中的業務邏輯
- Mock Repository 依賴

### 集成測試

- 測試完整的命令流程
- 測試數據庫操作

## 常見問題

### Q: 如何添加新的物品類型？

1. 在 `core/constants.py` 的 `ItemType` 枚舉中添加新類型
2. 在 `core/domain/models.py` 中定義新的實體類
3. 在對應的 Repository 中實現數據訪問方法
4. 在 Handler 和 Service 中處理新類型

### Q: 如何添加新的交易所商品？

1. 在 `core/constants.py` 的 `ExchangeCommodity` 枚舉中添加
2. 在配置文件中設置初始價格、波動率、保質期
3. 在 `schema_manager.py` 中插入默認商品數據

### Q: 如何修改精煉倍率？

修改 `core/constants.py` 中的 `REFINE_MULTIPLIER` 字典。

---

*本架構文檔將隨項目演進持續更新。*
