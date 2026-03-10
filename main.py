import os
import json
import asyncio
import re

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter, MessageChain
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.permission import PermissionType

# ==========================================================
# 导入所有仓储层 & 服务层
# ==========================================================
from .core.repositories.mysql_user_repo import MysqlUserRepository
from .core.repositories.mysql_item_template_repo import MysqlItemTemplateRepository
from .core.repositories.mysql_user_buff_repo import MysqlUserBuffRepository
from .core.repositories.mysql_exchange_repo import MysqlExchangeRepository
from .core.repositories.mysql_gacha_repo import MysqlGachaRepository
from .core.repositories.mysql_shop_repo import MysqlShopRepository
from .core.repositories.mysql_log_repo import MysqlLogRepository
from .core.repositories.mysql_inventory_repo import MysqlInventoryRepository
from .core.repositories.mysql_achievement_repo import MysqlAchievementRepository
from .core.repositories.mysql_market_repo import MysqlMarketRepository
from .core.repositories.mysql_red_packet_repo import MysqlRedPacketRepository

from .core.services.data_setup_service import DataSetupService
from .core.services.item_template_service import ItemTemplateService
from .core.services.user_service import UserService
from .core.services.fishing_service import FishingService
from .core.services.inventory_service import InventoryService
from .core.services.shop_service import ShopService
from .core.services.market_service import MarketService
from .core.services.gacha_service import GachaService
from .core.services.achievement_service import AchievementService
from .core.services.game_mechanics_service import GameMechanicsService
from .core.services.effect_manager import EffectManager
from .core.services.fishing_zone_service import FishingZoneService
from .core.services.exchange_service import ExchangeService
from .core.services.sicbo_service import SicboService
from .core.services.red_packet_service import RedPacketService

from .core.database.mysql_connection_manager import MysqlConnectionManager

# ==========================================================
# 导入所有指令函数
# ==========================================================
from .handlers import (
    admin_handlers,
    common_handlers,
    inventory_handlers,
    fishing_handlers,
    market_handlers,
    social_handlers,
    gacha_handlers,
    aquarium_handlers,
    sicbo_handlers,
    red_packet_handlers,
)
from .handlers.fishing_handlers import FishingHandlers
from .handlers.exchange_handlers import ExchangeHandlers


class FishingPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        if config is None:
            config = getattr(context, "_config", {}) or {}
        if not hasattr(config, "get") or not config.get("external_sql"):
            config = self._load_config_fallback() or config
        tax_config = config.get("tax", {})
        self.is_tax = tax_config.get("is_tax", True)
        self.threshold = tax_config.get("threshold", 100000)
        self.step_coins = tax_config.get("step_coins", 100000)
        self.step_rate = tax_config.get("step_rate", 0.01)
        self.max_rate = tax_config.get("max_rate", 0.2)
        self.min_rate = tax_config.get("min_rate", 0.001)
        self.area2num = config.get("area2num", 2000)
        self.area3num = config.get("area3num", 500)
        self.plugin_id = "astrbot_plugin_fishing"

        try:
            self.data_dir = self.context.get_data_dir(self.plugin_id)
        except:
            self.data_dir = "data"

        self.tmp_dir = os.path.join(self.data_dir, "tmp")
        os.makedirs(self.tmp_dir, exist_ok=True)

        # 清理舊的臨時圖片文件（保留最近1小時的文件）
        self._cleanup_old_temp_files()

        db_path = os.path.join(self.data_dir, "fish.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path

        fishing_config = config.get("fishing", {})
        steal_config = config.get("steal", {})
        electric_fish_config = config.get("electric_fish", {})
        game_global_config = config.get("game", {})
        user_config = config.get("user", {})
        market_config = config.get("market", {})
        sell_prices_config = config.get("sell_prices", {})
        exchange_config = config.get("exchange", {})
        signin_config = config.get("signin", {})
        tips_config = config.get("tips", {})

        self.game_config = {
            "fishing": {
                "cost": config.get("fish_cost", 10),
                "cooldown_seconds": fishing_config.get("cooldown_seconds", 180),
            },
            "quality_bonus_max_chance": fishing_config.get(
                "quality_bonus_max_chance", 0.35
            ),
            "steal": {"cooldown_seconds": steal_config.get("cooldown_seconds", 14400)},
            "electric_fish": {
                "enabled": electric_fish_config.get("enabled", True),
                "cooldown_seconds": electric_fish_config.get("cooldown_seconds", 7200),
                "base_success_rate": electric_fish_config.get("base_success_rate", 0.6),
                "failure_penalty_max_rate": electric_fish_config.get(
                    "failure_penalty_max_rate", 0.5
                ),
            },
            "wipe_bomb": {
                "max_attempts_per_day": game_global_config.get("wipe_bomb_attempts", 3)
            },
            "wheel_of_fate_daily_limit": game_global_config.get(
                "wheel_of_fate_daily_limit", 3
            ),
            "daily_reset_hour": game_global_config.get("daily_reset_hour", 0),
            "signin": signin_config,
            "user": {"initial_coins": user_config.get("initial_coins", 200)},
            "market": {"listing_tax_rate": market_config.get("listing_tax_rate", 0.05)},
            "tax": {
                "is_tax": self.is_tax,
                "threshold": self.threshold,
                "step_coins": self.step_coins,
                "step_rate": self.step_rate,
                "min_rate": self.min_rate,
                "max_rate": self.max_rate,
                "transfer_tax_rate": tax_config.get("transfer_tax_rate", 0.05),
            },
            "pond_upgrades": [
                {"from": 480, "to": 999, "cost": 50000},
                {"from": 999, "to": 9999, "cost": 500000},
                {"from": 9999, "to": 99999, "cost": 50000000},
                {"from": 99999, "to": 999999, "cost": 5000000000},
            ],
            "sell_prices": {
                "rod": {
                    "1": sell_prices_config.get("by_rarity_1", 100),
                    "2": sell_prices_config.get("by_rarity_2", 500),
                    "3": sell_prices_config.get("by_rarity_3", 2000),
                    "4": sell_prices_config.get("by_rarity_4", 5000),
                    "5": sell_prices_config.get("by_rarity_5", 10000),
                },
                "accessory": {
                    "1": sell_prices_config.get("by_rarity_1", 100),
                    "2": sell_prices_config.get("by_rarity_2", 500),
                    "3": sell_prices_config.get("by_rarity_3", 2000),
                    "4": sell_prices_config.get("by_rarity_4", 5000),
                    "5": sell_prices_config.get("by_rarity_5", 10000),
                },
                "refine_multiplier": {
                    "1": 1.0,
                    "2": 1.6,
                    "3": 3.0,
                    "4": 6.0,
                    "5": 12.0,
                    "6": 25.0,
                    "7": 55.0,
                    "8": 125.0,
                    "9": 280.0,
                    "10": 660.0,
                },
            },
            "exchange": exchange_config,
            "tips": {
                "enabled": tips_config.get("enabled", True),
                "tip_probability": tips_config.get("tip_probability", 0.35),
            },
            "show_suggestions": tips_config.get(
                "show_suggestions", True
            ),  # 是否显示建议操作/下一步提示
        }

        self.storage_backend = self._get_storage_backend(config)
        if self.storage_backend != "mysql":
            raise RuntimeError(
                "MySQL only mode is enabled. Set external_sql.enabled=true and backend=mysql."
            )
        logger.info("[storage] backend=mysql (sqlite disabled)")

        # 数据库初始化：仅使用 MySQL
        self.external_sql_sync_manager = None
        self._ensure_mysql_runtime_schema(config)

        self.user_repo = self._build_user_repo(config)
        self.item_template_repo = self._build_item_template_repo(config)
        self.inventory_repo = self._build_inventory_repo(config)
        self.gacha_repo = self._build_gacha_repo(config)
        self.market_repo = self._build_market_repo(config)
        self.shop_repo = self._build_shop_repo(config)
        self.log_repo = self._build_log_repo(config)
        self.achievement_repo = self._build_achievement_repo(config)
        self.buff_repo = self._build_buff_repo(config)
        self.exchange_repo = self._build_exchange_repo(config)

        self.fishing_zone_service = FishingZoneService(
            self.item_template_repo, self.inventory_repo, self.game_config
        )
        self.game_mechanics_service = GameMechanicsService(
            self.user_repo,
            self.log_repo,
            self.inventory_repo,
            self.item_template_repo,
            self.buff_repo,
            self.game_config,
        )
        self.gacha_service = GachaService(
            self.gacha_repo,
            self.user_repo,
            self.inventory_repo,
            self.item_template_repo,
            self.log_repo,
            self.achievement_repo,
        )
        self.user_service = UserService(
            self.user_repo,
            self.log_repo,
            self.inventory_repo,
            self.item_template_repo,
            self.gacha_service,
            self.game_config,
            self.achievement_repo,
        )
        self.inventory_service = InventoryService(
            self.inventory_repo,
            self.user_repo,
            self.item_template_repo,
            None,
            self.game_mechanics_service,
            self.game_config,
            self.log_repo,
        )
        self.shop_service = ShopService(
            self.item_template_repo,
            self.inventory_repo,
            self.user_repo,
            self.shop_repo,
            self.game_config,
        )
        self.market_service = MarketService(
            self.market_repo,
            self.inventory_repo,
            self.user_repo,
            self.log_repo,
            self.item_template_repo,
            self.exchange_repo,
            self.game_config,
        )
        self.achievement_service = AchievementService(
            self.achievement_repo,
            self.user_repo,
            self.inventory_repo,
            self.item_template_repo,
            self.log_repo,
        )
        self.fishing_service = FishingService(
            self.user_repo,
            self.inventory_repo,
            self.item_template_repo,
            self.log_repo,
            self.buff_repo,
            self.fishing_zone_service,
            self.game_config,
        )

        from .core.services.aquarium_service import AquariumService

        self.aquarium_service = AquariumService(
            self.inventory_repo, self.user_repo, self.item_template_repo
        )
        self.exchange_service = ExchangeService(
            self.user_repo,
            self.exchange_repo,
            self.game_config,
            self.log_repo,
            self.market_service,
        )
        self.sicbo_service = SicboService(
            self.user_repo, self.log_repo, self.game_config
        )
        self.sicbo_service.set_message_callback(self._send_sicbo_announcement)

        self.red_packet_repo = self._build_red_packet_repo(config)
        self.red_packet_service = RedPacketService(self.red_packet_repo, self.user_repo)

        self.exchange_handlers = ExchangeHandlers(self)
        self.fishing_handlers = FishingHandlers(self)

        self.effect_manager = EffectManager()
        self.effect_manager.discover_and_register(
            "data.plugins.astrbot_plugin_fishing.core.services.item_effects",
            {
                "user_repo": self.user_repo,
                "buff_repo": self.buff_repo,
                "game_mechanics_service": self.game_mechanics_service,
                "fishing_service": self.fishing_service,
                "log_repo": self.log_repo,
                "game_config": self.game_config,
            },
        )
        self.inventory_service.effect_manager = self.effect_manager
        self.item_template_service = ItemTemplateService(
            self.item_template_repo, self.gacha_repo
        )

        self.fishing_service.start_auto_fishing_task()
        if self.is_tax:
            self.fishing_service.start_daily_tax_task()

        self.achievement_service.start_achievement_check_task()
        self.exchange_service.start_daily_price_update_task()
        self._red_packet_cleanup_task = asyncio.create_task(
            self._red_packet_cleanup_scheduler()
        )
        if self.external_sql_sync_manager:
            self.external_sql_sync_manager.start_periodic_sync()

        data_setup_service = DataSetupService(
            self.item_template_repo, self.gacha_repo, self.shop_repo
        )
        data_setup_service.setup_initial_data()
        try:
            data_setup_service.create_initial_items()
        except:
            pass
        self.data_setup_service = data_setup_service
        self.web_admin_task = None
        self.secret_key = config.get("webui", {}).get("secret_key", "fishing-admin")
        self.port = config.get("webui", {}).get("port", 7777)
        self.impersonation_map = {}

    def _load_config_fallback(self) -> dict:
        config_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "config",
                "astrbot_plugin_fishing_config.json",
            )
        )
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return {}

    def _get_storage_backend(self, config: AstrBotConfig) -> str:
        external_sql = config.get("external_sql", {}) or {}
        backend = str(external_sql.get("backend", "sqlite")).strip().lower()
        if backend in {"sqlite", "mysql"}:
            return backend

        # 未显式配置 backend 时，自动推断：配置了 MySQL 连接信息则走 MySQL
        mysql_url = str(external_sql.get("mysql_url", "")).strip()
        host = str(external_sql.get("host", "")).strip()
        user = str(external_sql.get("user", "")).strip()
        database = str(external_sql.get("database", "")).strip()
        if mysql_url or (host and user and database):
            return "mysql"

        backend = "sqlite"
        return backend

    def _ensure_mysql_runtime_schema(self, config: AstrBotConfig):
        """MySQL 模式下的轻量运行时自修复，避免 SQLite 迁移链影响。"""
        manager = MysqlConnectionManager(config.get("external_sql", {}))
        with manager.get_connection() as conn:
            with conn.cursor() as cursor:

                def _repair_user_items_table() -> None:
                    cursor.execute("SHOW TABLES LIKE 'user_items'")
                    if not cursor.fetchone():
                        cursor.execute(
                            """
                            CREATE TABLE IF NOT EXISTS user_items (
                                user_id VARCHAR(255) NOT NULL,
                                item_id BIGINT NOT NULL,
                                quantity BIGINT NOT NULL DEFAULT 0,
                                PRIMARY KEY (user_id, item_id),
                                KEY idx_user_items_item_id (item_id)
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                            """
                        )
                        return

                    cursor.execute("SHOW COLUMNS FROM user_items")
                    columns = {row["Field"]: row for row in cursor.fetchall()}
                    cursor.execute("SHOW INDEX FROM user_items")
                    indexes = cursor.fetchall()

                    has_composite_primary_key = False
                    primary_key_columns = [
                        row["Column_name"]
                        for row in indexes
                        if row.get("Key_name") == "PRIMARY"
                    ]
                    if primary_key_columns == ["user_id", "item_id"]:
                        has_composite_primary_key = True

                    has_unique_user_item = any(
                        row.get("Key_name") != "PRIMARY"
                        and row.get("Non_unique") == 0
                        and row.get("Column_name") == "user_id"
                        for row in indexes
                    ) and any(
                        row.get("Key_name") != "PRIMARY"
                        and row.get("Non_unique") == 0
                        and row.get("Column_name") == "item_id"
                        for row in indexes
                    )

                    needs_rebuild = (
                        "id" in columns
                        or "user_id" not in columns
                        or "item_id" not in columns
                        or "quantity" not in columns
                        or not (has_composite_primary_key or has_unique_user_item)
                    )

                    if not needs_rebuild:
                        return

                    logger.warning(
                        "检测到 MySQL 表 user_items 结构异常，正在自动修复为复合主键结构。"
                    )
                    cursor.execute("DROP TABLE IF EXISTS user_items_repaired")
                    cursor.execute(
                        """
                        CREATE TABLE user_items_repaired (
                            user_id VARCHAR(255) NOT NULL,
                            item_id BIGINT NOT NULL,
                            quantity BIGINT NOT NULL DEFAULT 0,
                            PRIMARY KEY (user_id, item_id),
                            KEY idx_user_items_item_id (item_id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        """
                    )
                    cursor.execute(
                        """
                        INSERT INTO user_items_repaired (user_id, item_id, quantity)
                        SELECT user_id, item_id, GREATEST(0, COALESCE(SUM(quantity), 0))
                        FROM user_items
                        GROUP BY user_id, item_id
                        ON DUPLICATE KEY UPDATE quantity = VALUES(quantity)
                        """
                    )
                    cursor.execute("DROP TABLE user_items")
                    cursor.execute("RENAME TABLE user_items_repaired TO user_items")

                def _repair_user_buffs_table() -> None:
                    cursor.execute("SHOW TABLES LIKE 'user_buffs'")
                    if not cursor.fetchone():
                        cursor.execute(
                            """
                            CREATE TABLE IF NOT EXISTS user_buffs (
                                id BIGINT NOT NULL AUTO_INCREMENT,
                                user_id VARCHAR(255) NOT NULL,
                                buff_type VARCHAR(255) NOT NULL,
                                payload LONGTEXT,
                                started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                expires_at DATETIME NULL,
                                PRIMARY KEY (id),
                                KEY idx_user_buffs_user_id (user_id),
                                KEY idx_user_buffs_expires_at (expires_at)
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                            """
                        )
                        return

                    cursor.execute("SHOW COLUMNS FROM user_buffs")
                    columns = {row["Field"]: row for row in cursor.fetchall()}
                    id_column = columns.get("id")
                    extra = str((id_column or {}).get("Extra", "")).lower()

                    if id_column and "auto_increment" in extra:
                        return

                    logger.warning(
                        "检测到 MySQL 表 user_buffs 的 id 不是 AUTO_INCREMENT，正在尝试轻量修复。"
                    )

                    if id_column:
                        cursor.execute(
                            """
                            ALTER TABLE user_buffs
                            MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT
                            """
                        )
                        return

                    cursor.execute(
                        """
                        ALTER TABLE user_buffs
                        ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST
                        """
                    )

                # 1) 交易所核心表兜底
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS commodities (
                        commodity_id VARCHAR(255) PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS exchange_prices (
                        price_id BIGINT NOT NULL AUTO_INCREMENT,
                        date VARCHAR(255) NOT NULL,
                        time LONGTEXT NOT NULL,
                        commodity_id VARCHAR(255) NOT NULL,
                        price BIGINT NOT NULL,
                        update_type LONGTEXT,
                        created_at VARCHAR(255) NOT NULL,
                        PRIMARY KEY (price_id),
                        KEY idx_exchange_prices_created_at (created_at),
                        KEY idx_exchange_prices_date_commodity (date(100), commodity_id(100)),
                        CONSTRAINT fk_exchange_prices_0 FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS check_ins (
                        user_id VARCHAR(255) NOT NULL,
                        check_in_date DATE NOT NULL,
                        PRIMARY KEY (user_id, check_in_date)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )

                # 2) 合并遗留临时表（若存在）
                cursor.execute("SHOW TABLES LIKE 'exchange_prices_new'")
                if cursor.fetchone():
                    cursor.execute(
                        """
                        INSERT INTO exchange_prices (date, time, commodity_id, price, update_type, created_at)
                        SELECT n.date, n.time, n.commodity_id, n.price, n.update_type, n.created_at
                        FROM exchange_prices_new n
                        LEFT JOIN exchange_prices e
                          ON e.date = n.date
                         AND e.time = n.time
                         AND e.commodity_id = n.commodity_id
                        WHERE e.price_id IS NULL
                        """
                    )
                    cursor.execute("DROP TABLE exchange_prices_new")

                # 3) 交易所默认商品兜底（补齐缺失项）
                cursor.execute(
                    """
                    INSERT INTO commodities (commodity_id, name, description) VALUES
                    ('dried_fish', '鱼干', '稳健型标的，价格波动低'),
                    ('fish_roe', '鱼卵', '高风险标的，价格波动极大'),
                    ('fish_oil', '鱼油', '投机品，有概率触发事件导致价格大幅涨跌'),
                    ('fish_bone', '鱼骨', '坚硬的鱼骨，保质期长，价格最稳定，适合长期持有'),
                    ('fish_scale', '鱼鳞', '闪亮的鱼鳞，中等保质期，价格波动适中，平衡之选'),
                    ('fish_sauce', '鱼露', '发酵的鱼露，极短保质期，价格剧烈波动，仅供高手')
                    ON DUPLICATE KEY UPDATE
                      name = VALUES(name),
                      description = VALUES(description)
                    """
                )

                # 4) 背包道具表兜底（修复旧版错误的自增 id 结构）
                _repair_user_items_table()

                # 5) Buff 表兜底（修复旧版缺失 AUTO_INCREMENT 的 id）
                _repair_user_buffs_table()
            conn.commit()

    def _build_user_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlUserRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_buff_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlUserBuffRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_item_template_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlItemTemplateRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_inventory_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlInventoryRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_exchange_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlExchangeRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_market_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlMarketRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_achievement_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlAchievementRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_red_packet_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlRedPacketRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_gacha_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlGachaRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_shop_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlShopRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _build_log_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlLogRepository(config.get("external_sql", {}))
        raise RuntimeError("MySQL only mode: sqlite backend is disabled")

    def _normalize_subcommand(self, sub: str) -> str:
        if not sub:
            return ""
        normalized = str(sub).strip().lower()
        alias_map = {
            "註冊": "register",
            "注册": "register",
            "簽到": "signin",
            "签到": "signin",
            "背包": "bag",
            "狀態": "status",
            "状态": "status",
            "魚塘": "pond",
            "鱼塘": "pond",
            "商店": "shop",
            "市場": "market",
            "市场": "market",
            "幫助": "help",
            "帮助": "help",
            "骰寶": "sicbo",
            "骰宝": "sicbo",
            "押點": "bet_pt",
            "押点": "bet_pt",
            "購買": "buy",
            "购买": "buy",
            "上架": "list",
            "我的": "my",
            "下架": "del",
            "同步": "sync",
            "補充": "replenish",
            "补充": "replenish",
            "金幣": "coins",
            "金币": "coins",
            "高級": "premium",
            "高级": "premium",
        }
        return alias_map.get(normalized, normalized)

    def _cleanup_old_temp_files(self, max_age_hours: int = 1):
        """清理舊的臨時圖片文件

        Args:
            max_age_hours: 保留文件的最大小時數，默認1小時
        """
        try:
            import time

            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            if not os.path.exists(self.tmp_dir):
                return

            cleaned_count = 0
            for filename in os.listdir(self.tmp_dir):
                file_path = os.path.join(self.tmp_dir, filename)

                # 只處理圖片文件
                if not filename.endswith((".png", ".jpg", ".jpeg", ".gif")):
                    continue

                try:
                    # 檢查文件年齡
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        cleaned_count += 1
                except Exception as e:
                    logger.warning(f"清理臨時文件失敗 {filename}: {e}")

            if cleaned_count > 0:
                logger.info(f"已清理 {cleaned_count} 個舊的臨時圖片文件")
        except Exception as e:
            logger.error(f"臨時文件清理過程出錯: {e}")

    def _get_effective_user_id(self, event: AstrMessageEvent) -> str:
        user_id = str(event.get_sender_id())
        admin_target = self.impersonation_map.get(user_id)
        if admin_target:
            return str(admin_target)
        return user_id

    def _extract_message_tokens(self, message_str: str) -> list[str]:
        if not message_str:
            return []
        text = message_str.replace("\u3000", " ").strip()
        if not text:
            return []
        text = re.sub(r"^<@!?\d+>\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text.split(" ") if text else []

    async def _check_port_active(self) -> bool:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", int(self.port)), timeout=1.5
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True
        except Exception:
            return False

    async def _send_sicbo_announcement(self, session_info: dict, result_data: dict):
        try:
            if session_info and result_data.get("success"):
                if self.sicbo_service.is_image_mode():
                    from .draw.sicbo import draw_sicbo_result, save_image_to_temp

                    dice = result_data.get("dice", [1, 1, 1])
                    settlement = result_data.get("settlement", {})
                    user_profits = {}
                    for info in settlement:
                        uid = info["user_id"]
                        user_profits[uid] = user_profits.get(uid, 0) + info["profit"]
                    player_results = []
                    for uid, profit in user_profits.items():
                        user = self.user_repo.get_by_id(uid)
                        player_results.append(
                            {
                                "username": user.nickname
                                if user and user.nickname
                                else "未知玩家",
                                "profit": profit,
                            }
                        )
                    image = draw_sicbo_result(
                        dice[0], dice[1], dice[2], [], player_results
                    )
                    image_path = save_image_to_temp(
                        image, "sicbo_result", self.data_dir
                    )
                    await self._send_initiative_image(session_info, image_path)
                else:
                    await self._send_initiative_message(
                        session_info, result_data.get("message", "开奖失败")
                    )
        except Exception as e:
            logger.error(f"发送骰宝公告失败: {e}")

    async def _send_initiative_image(self, session_info: dict, image_path: str) -> bool:
        try:
            umo = session_info.get("unified_msg_origin")
            if not umo:
                return False
            await self.context.send_message(umo, MessageChain().file_image(image_path))
            return True
        except:
            return False

    async def _send_initiative_message(self, session_info: dict, message: str) -> bool:
        try:
            umo = session_info.get("unified_msg_origin")
            if not umo:
                return False
            await self.context.send_message(umo, MessageChain().message(message))
            return True
        except:
            return False

    async def _red_packet_cleanup_scheduler(self):
        while True:
            try:
                await asyncio.sleep(3600)
                self.red_packet_service.cleanup_expired_packets()
            except asyncio.CancelledError:
                break
            except:
                pass

    async def initialize(self):
        logger.info(
            "\n    _____ _     _     _\n    |  ___(_)___| |__ (_)_ __   __ _\n    | |_  | / __| '_ \\| | '_ \\ / _` |\n    |  _| | \\__ \\ | | | | | | | (_| |\n    |_|   |_|___/_| |_|_|_| |_|\\__, |\n                               |___/\n                               "
        )

    @filter.command_group("fish_admin")
    @filter.permission_type(PermissionType.ADMIN)
    def fish_admin_group(self):
        pass

    @filter.permission_type(PermissionType.ADMIN)
    @fish_admin_group.command("coins")  # type: ignore[attr-defined]
    async def fish_admin_coins_subcmd(
        self,
        event: AstrMessageEvent,
        user_id: str = "",
        amount: str = "",
    ):
        """修改用户金币（管理员）"""
        async for r in self.fish_admin_cmd(event, "coins", user_id, amount):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @fish_admin_group.command("premium")  # type: ignore[attr-defined]
    async def fish_admin_premium_subcmd(
        self,
        event: AstrMessageEvent,
        user_id: str = "",
        amount: str = "",
    ):
        """修改用户高级货币（管理员）"""
        async for r in self.fish_admin_cmd(event, "premium", user_id, amount):
            yield r

    async def fish_cmd(
        self,
        event: AstrMessageEvent,
        sub: str = "",
        arg1: str = "",
        arg2: str = "",
        arg3: str = "",
    ):
        """钓鱼主命令（支持繁简别名和标准子命令）"""
        actual_args = [a for a in [sub, arg1, arg2, arg3] if a]
        if not actual_args and event.message_str:
            parts = self._extract_message_tokens(event.message_str)
            if parts:
                first = self._normalize_subcommand(parts[0].lstrip("/"))
                if first in ["fish", "釣魚", "钓鱼"]:
                    actual_args = parts[1:]
                elif parts[0].startswith("/") and first in [
                    "register",
                    "signin",
                    "bag",
                    "status",
                    "pond",
                    "shop",
                    "market",
                    "help",
                    "sicbo",
                    "bet_pt",
                ]:
                    actual_args = [first] + parts[1:]
                else:
                    actual_args = parts[1:] if len(parts) > 1 else []

        if not actual_args:
            async for r in self.fishing_handlers.fish(event):
                yield r
            return

        sub = self._normalize_subcommand(actual_args[0])
        if sub == "register":
            async for r in common_handlers.register_user(self, event):
                yield r
        elif sub == "signin":
            async for r in common_handlers.sign_in(self, event):
                yield r
        elif sub == "bag":
            async for r in inventory_handlers.user_backpack(self, event):
                yield r
        elif sub == "status":
            async for r in common_handlers.state(self, event):
                yield r
        elif sub == "pond":
            async for r in inventory_handlers.pond(self, event):
                yield r
        elif sub == "shop":
            sub2 = (
                self._normalize_subcommand(actual_args[1])
                if len(actual_args) > 1
                else ""
            )
            if sub2 == "buy":
                async for r in market_handlers.buy_in_shop(self, event):
                    yield r
            else:
                async for r in market_handlers.shop(self, event):
                    yield r
        elif sub == "market":
            if len(actual_args) > 1:
                sub2 = self._normalize_subcommand(actual_args[1])
                if sub2 == "list":
                    async for r in market_handlers.list_any(self, event):
                        yield r
                elif sub2 == "buy":
                    async for r in market_handlers.buy_item(self, event):
                        yield r
                elif sub2 == "my":
                    async for r in market_handlers.my_listings(self, event):
                        yield r
                elif sub2 == "del":
                    async for r in market_handlers.delist_item(self, event):
                        yield r
            else:
                async for r in market_handlers.market(self, event):
                    yield r
        elif sub == "help":
            async for r in common_handlers.fishing_help(self, event):
                yield r
        elif sub == "sicbo":
            async for r in sicbo_handlers.start_sicbo_game(self, event):
                yield r
        elif sub == "bet_pt":
            if len(actual_args) > 1:
                try:
                    point = int(actual_args[1])
                    handler = getattr(sicbo_handlers, f"bet_{point}_points", None)
                    if handler:
                        async for r in handler(self, event):
                            yield r
                    else:
                        yield event.plain_result(f"❌ 無效點數 {point}")
                except:
                    yield event.plain_result("❌ 點數必須是數字。")
            else:
                yield event.plain_result(
                    "❌ 請指定點數。用法：/fish 押點 <點數> [金額]"
                )
        else:
            yield event.plain_result(f"❓ 未知子命令 {sub}。")

    async def fish_admin_cmd(
        self,
        event: AstrMessageEvent,
        sub: str = "",
        arg1: str = "",
        arg2: str = "",
    ):
        """钓鱼管理主命令（管理员）"""
        if not sub and event.message_str:
            parts = self._extract_message_tokens(event.message_str)
            if len(parts) > 1:
                sub = parts[1]
        sub = self._normalize_subcommand(sub)
        if sub == "sync":
            async for r in admin_handlers.sync_initial_data(self, event):
                yield r
        elif sub == "replenish":
            async for r in admin_handlers.replenish_fish_pools(self, event):
                yield r
        elif sub == "coins":
            async for r in admin_handlers.modify_coins(self, event):
                yield r
        elif sub == "premium":
            async for r in admin_handlers.modify_premium(self, event):
                yield r

    @filter.command("注册", alias=["註冊"])
    async def cmd_register_cn(self, event: AstrMessageEvent):
        """注册新用户"""
        async for r in common_handlers.register_user(self, event):
            yield r

    @filter.command("钓鱼", alias=["釣魚", "釣鱼"])
    async def cmd_fish_cn(self, event: AstrMessageEvent):
        """进行一次钓鱼"""
        async for r in self.fishing_handlers.fish(event):
            yield r

    @filter.command("签到", alias=["簽到", "簽到"])
    async def cmd_signin_cn(self, event: AstrMessageEvent):
        """每日签到"""
        async for r in common_handlers.sign_in(self, event):
            yield r

    @filter.command("自动钓鱼", alias=["自動釣魚", "自動钓鱼"])
    async def cmd_auto_fish_cn(self, event: AstrMessageEvent):
        """开启或关闭自动钓鱼"""
        async for r in self.fishing_handlers.auto_fish(event):
            yield r

    @filter.command("钓鱼区域", alias=["釣魚區域", "釣魚区域", "区域", "區域"])
    async def cmd_fishing_area_cn(self, event: AstrMessageEvent):
        """查看或切换钓鱼区域"""
        async for r in self.fishing_handlers.fishing_area(event):
            yield r

    @filter.command(
        "钓鱼记录",
        alias=[
            "釣魚記錄",
            "釣魚记录",
            "钓鱼日志",
            "釣魚日誌",
            "钓鱼历史",
            "釣魚歷史",
        ],
    )
    async def cmd_fishing_log_cn(self, event: AstrMessageEvent):
        """查看最近钓鱼记录"""
        async for r in common_handlers.fishing_log(self, event):
            yield r

    @filter.command("钓鱼纪录", alias=["釣魚紀錄"])
    async def cmd_fishing_log_cn_alt(self, event: AstrMessageEvent):
        """查看最近钓鱼记录（纪录同义）"""
        async for r in common_handlers.fishing_log(self, event):
            yield r

    @filter.command(
        "钓鱼帮助",
        alias=["釣魚幫助", "钓鱼菜单", "釣魚菜單", "菜单", "菜單", "帮助", "幫助"],
    )
    async def cmd_fishing_help_cn(self, event: AstrMessageEvent):
        """查看钓鱼帮助菜单"""
        async for r in common_handlers.fishing_help(self, event):
            yield r

    @filter.command(
        "钓鱼帮助文字版",
        alias=["釣魚幫助文字版", "钓鱼帮助 文字版", "釣魚幫助 文字版"],
    )
    async def cmd_fishing_help_text_cn(self, event: AstrMessageEvent):
        """查看钓鱼帮助文字版"""
        async for r in common_handlers.fishing_help(self, event):
            yield r

    @filter.command("状态", alias=["狀態", "我的状态", "我的狀態"])
    async def cmd_status_cn(self, event: AstrMessageEvent):
        """查看个人详细状态"""
        async for r in common_handlers.state(self, event):
            yield r

    @filter.command("背包", alias=["查看背包", "我的背包"])
    async def cmd_bag_cn(self, event: AstrMessageEvent):
        """查看我的所有物品"""
        async for r in inventory_handlers.user_backpack(self, event):
            yield r

    @filter.command("鱼塘", alias=["魚塘"])
    async def cmd_pond_cn(self, event: AstrMessageEvent):
        """查看鱼塘中的所有鱼"""
        async for r in inventory_handlers.pond(self, event):
            yield r

    @filter.command("偷看鱼塘", alias=["偷看魚塘", "查看鱼塘", "查看魚塘", "偷看"])
    async def cmd_peek_pond_cn(self, event: AstrMessageEvent):
        """查看其他用户鱼塘"""
        async for r in inventory_handlers.peek_pond(self, event):
            yield r

    @filter.command("鱼塘容量", alias=["魚塘容量"])
    async def cmd_pond_capacity_cn(self, event: AstrMessageEvent):
        """查看鱼塘容量"""
        async for r in inventory_handlers.pond_capacity(self, event):
            yield r

    @filter.command("升级鱼塘", alias=["升級魚塘", "鱼塘升级", "魚塘升級"])
    async def cmd_upgrade_pond_cn(self, event: AstrMessageEvent):
        """升级鱼塘容量"""
        async for r in inventory_handlers.upgrade_pond(self, event):
            yield r

    @filter.command("水族箱", alias=["水族館", "水族馆"])
    async def cmd_aquarium_cn(self, event: AstrMessageEvent):
        """查看水族箱或子命令"""
        async for r in aquarium_handlers.aquarium(self, event):
            yield r

    @filter.command("水族箱帮助", alias=["水族箱幫助", "水族館幫助", "水族馆帮助"])
    async def cmd_aquarium_help_cn(self, event: AstrMessageEvent):
        """水族箱帮助"""
        async for r in aquarium_handlers.aquarium_help(self, event):
            yield r

    @filter.command("放入水族箱", alias=["移入水族箱"])
    async def cmd_add_to_aquarium_cn(self, event: AstrMessageEvent):
        """将鱼放入水族箱"""
        async for r in aquarium_handlers.add_to_aquarium(self, event):
            yield r

    @filter.command("移出水族箱", alias=["移回鱼塘", "移回魚塘", "取出水族箱"])
    async def cmd_remove_from_aquarium_cn(self, event: AstrMessageEvent):
        """将鱼移出水族箱"""
        async for r in aquarium_handlers.remove_from_aquarium(self, event):
            yield r

    @filter.command("升级水族箱", alias=["升級水族箱", "水族箱升级", "水族箱升級"])
    async def cmd_upgrade_aquarium_cn(self, event: AstrMessageEvent):
        """升级水族箱容量"""
        async for r in aquarium_handlers.upgrade_aquarium(self, event):
            yield r

    @filter.command("鱼竿", alias=["魚竿", "魚杆"])
    async def cmd_rod_cn(self, event: AstrMessageEvent):
        """查看鱼竿"""
        async for r in inventory_handlers.rod(self, event):
            yield r

    @filter.command("鱼饵", alias=["魚餌", "魚饵"])
    async def cmd_bait_cn(self, event: AstrMessageEvent):
        """查看鱼饵"""
        async for r in inventory_handlers.bait(self, event):
            yield r

    @filter.command("饰品", alias=["飾品", "饰品列表", "飾品列表"])
    async def cmd_accessories_cn(self, event: AstrMessageEvent):
        """查看饰品"""
        async for r in inventory_handlers.accessories(self, event):
            yield r

    @filter.command("道具", alias=["我的道具", "查看道具", "道具列表"])
    async def cmd_items_cn(self, event: AstrMessageEvent):
        """查看道具"""
        async for r in inventory_handlers.items(self, event):
            yield r

    @filter.command("使用", alias=["装备", "裝備"])
    async def cmd_use_item_cn(self, event: AstrMessageEvent):
        """使用或装备物品"""
        async for r in inventory_handlers.use_equipment(self, event):
            yield r

    @filter.command(
        "开启全部钱袋",
        alias=[
            "開啟全部錢袋",
            "开啓全部钱袋",
            "開啓全部錢袋",
            "打开全部钱袋",
            "打開全部錢袋",
            "打开所有钱袋",
            "打開所有錢袋",
            "开啓所有钱袋",
            "開啓所有錢袋",
        ],
    )
    async def cmd_open_all_money_bags_cn(self, event: AstrMessageEvent):
        """一次性开启所有钱袋"""
        async for r in inventory_handlers.open_all_money_bags(self, event):
            yield r

    @filter.command(
        "精炼",
        alias=[
            "精煉",
            "强化",
            "強化",
            "精炼装备",
            "精煉裝備",
            "精炼裝备",
            "精煉装备",
            "强化装备",
            "強化裝備",
        ],
    )
    async def cmd_refine_cn(self, event: AstrMessageEvent):
        """精炼鱼竿或饰品"""
        async for r in inventory_handlers.refine_equipment(self, event):
            yield r

    @filter.command("出售", alias=["卖出", "賣出"])
    async def cmd_sell_cn(self, event: AstrMessageEvent):
        """出售指定短码物品"""
        async for r in inventory_handlers.sell_equipment(self, event):
            yield r

    @filter.command("锁定", alias=["鎖定", "上锁", "上鎖"])
    async def cmd_lock_cn(self, event: AstrMessageEvent):
        """锁定鱼竿或饰品"""
        async for r in inventory_handlers.lock_equipment(self, event):
            yield r

    @filter.command("解锁", alias=["解鎖", "开锁", "開鎖"])
    async def cmd_unlock_cn(self, event: AstrMessageEvent):
        """解锁鱼竿或饰品"""
        async for r in inventory_handlers.unlock_equipment(self, event):
            yield r

    @filter.command("金币", alias=["金幣"])
    async def cmd_coins_cn(self, event: AstrMessageEvent):
        """查看金币余额"""
        async for r in inventory_handlers.coins(self, event):
            yield r

    @filter.command("转账", alias=["轉賬", "轉帳", "轉账", "转帐"])
    async def cmd_transfer_cn(self, event: AstrMessageEvent):
        """向指定用户转账金币"""
        async for r in common_handlers.transfer_coins(self, event):
            yield r

    @filter.command(
        "更新昵称",
        alias=["更新暱稱", "修改昵称", "修改暱稱", "改昵称", "改暱稱", "昵称", "暱稱"],
    )
    async def cmd_update_nickname_cn(self, event: AstrMessageEvent):
        """更新游戏昵称"""
        async for r in common_handlers.update_nickname(self, event):
            yield r

    @filter.command(
        "我的建议",
        alias=["我的建議", "个人建议", "個人建議", "切换我的建议", "切換我的建議"],
    )
    async def cmd_toggle_my_suggestions_cn(self, event: AstrMessageEvent):
        """玩家自主开关建议消息"""
        async for r in common_handlers.toggle_my_suggestions(self, event):
            yield r

    @filter.command("高级货币", alias=["高級貨幣", "钻石", "鑽石", "星石"])
    async def cmd_premium_cn(self, event: AstrMessageEvent):
        """查看高级货币余额"""
        async for r in inventory_handlers.premium(self, event):
            yield r

    @filter.command(
        "全部卖出",
        alias=["全部賣出", "全部出售", "賣出全部", "出售全部", "清空鱼", "清空魚"],
    )
    async def cmd_sell_all_cn(self, event: AstrMessageEvent):
        """一键卖出鱼塘所有鱼"""
        async for r in market_handlers.sell_all(self, event):
            yield r

    @filter.command(
        "保留卖出", alias=["保留賣出", "保留出售", "卖出保留", "賣出保留", "出售保留"]
    )
    async def cmd_sell_keep_cn(self, event: AstrMessageEvent):
        """卖出所有鱼并每种保留一条"""
        async for r in market_handlers.sell_keep(self, event):
            yield r

    @filter.command(
        "砸锅卖铁", alias=["砸鍋賣鐵", "破产", "破產", "清空", "砸锅买铁", "砸鍋買鐵"]
    )
    async def cmd_sell_everything_cn(self, event: AstrMessageEvent):
        """出售所有未锁定未装备鱼竿饰品和全部鱼类"""
        async for r in market_handlers.sell_everything(self, event):
            yield r

    @filter.command("出售稀有度", alias=["稀有度出售", "出售星级", "出售星級"])
    async def cmd_sell_by_rarity_cn(self, event: AstrMessageEvent):
        """按稀有度出售鱼"""
        async for r in market_handlers.sell_by_rarity(self, event):
            yield r

    @filter.command(
        "出售所有鱼竿",
        alias=[
            "出售所有魚竿",
            "出售全部鱼竿",
            "出售全部魚竿",
            "卖出所有鱼竿",
            "賣出所有魚竿",
            "卖出全部鱼竿",
            "賣出全部魚竿",
            "清空鱼竿",
            "清空魚竿",
        ],
    )
    async def cmd_sell_all_rods_cn(self, event: AstrMessageEvent):
        """一键出售所有鱼竿"""
        async for r in market_handlers.sell_all_rods(self, event):
            yield r

    @filter.command(
        "出售所有饰品",
        alias=[
            "出售所有飾品",
            "出售全部饰品",
            "出售全部飾品",
            "卖出所有饰品",
            "賣出所有飾品",
            "卖出全部饰品",
            "賣出全部飾品",
            "清空饰品",
            "清空飾品",
        ],
    )
    async def cmd_sell_all_accessories_cn(self, event: AstrMessageEvent):
        """一键出售所有饰品"""
        async for r in market_handlers.sell_all_accessories(self, event):
            yield r

    @filter.command(
        "商店",
        alias=[
            "商店列表",
            "店鋪",
            "店铺",
            "商店购买",
            "商店購買",
            "购买商店商品",
            "購買商店商品",
            "购买商店",
            "購買商店",
            "商店买",
            "商店買",
        ],
    )
    async def cmd_shop_dispatch_cn(self, event: AstrMessageEvent):
        """商店命令入口"""
        parts = self._extract_message_tokens(event.message_str or "")
        cmd = parts[0].lstrip("/").strip() if parts else ""
        if cmd == "商店":
            if len(parts) > 1 and parts[1] in ["购买", "購買", "买", "買"]:
                tail = " ".join(parts[2:]).strip()
                event.message_str = f"/商店购买{(' ' + tail) if tail else ''}"
                async for r in market_handlers.buy_in_shop(self, event):
                    yield r
                return
            async for r in market_handlers.shop(self, event):
                yield r
            return
        if cmd in [
            "商店购买",
            "商店購買",
            "购买商店商品",
            "購買商店商品",
            "购买商店",
            "購買商店",
            "商店买",
            "商店買",
        ]:
            async for r in market_handlers.buy_in_shop(self, event):
                yield r
            return
        async for r in market_handlers.shop(self, event):
            yield r

    @filter.command(
        "市场",
        alias=[
            "市場",
            "市场列表",
            "市場列表",
            "上架",
            "购买",
            "購買",
            "我的上架",
            "上架列表",
            "我的商品",
            "我的挂单",
            "我的掛單",
            "下架",
        ],
    )
    async def cmd_market_dispatch_cn(self, event: AstrMessageEvent):
        """市场命令入口"""
        parts = self._extract_message_tokens(event.message_str or "")
        cmd = parts[0].lstrip("/").strip() if parts else ""
        dispatch = {
            "上架": market_handlers.list_any,
            "购买": market_handlers.buy_item,
            "購買": market_handlers.buy_item,
            "我的上架": market_handlers.my_listings,
            "上架列表": market_handlers.my_listings,
            "我的商品": market_handlers.my_listings,
            "我的挂单": market_handlers.my_listings,
            "我的掛單": market_handlers.my_listings,
            "下架": market_handlers.delist_item,
        }
        if cmd in ["市场", "市場"]:
            if len(parts) > 1:
                sub = parts[1].strip()
                handler = dispatch.get(sub)
                if handler:
                    tail = " ".join(parts[2:]).strip()
                    event.message_str = f"/{sub}{(' ' + tail) if tail else ''}"
                    async for r in handler(self, event):
                        yield r
                    return
            async for r in market_handlers.market(self, event):
                yield r
            return
        handler = dispatch.get(cmd)
        if handler:
            async for r in handler(self, event):
                yield r
            return
        async for r in market_handlers.market(self, event):
            yield r

    @filter.command(
        "交易所",
        alias=[
            "交易市場",
            "交易市场",
            "exchange",
            "持仓",
            "持倉",
            "库存",
            "庫存",
            "开户",
            "開戶",
            "开戶",
            "开通",
            "開通",
            "买入",
            "買入",
            "購入",
            "卖出",
            "賣出",
            "交易所帮助",
            "交易所幫助",
            "交易所说明",
            "交易所說明",
            "交易所历史",
            "交易所歷史",
            "交易所分析",
            "交易所統計",
            "交易所统计",
            "清仓",
            "清倉",
            "清倉庫存",
            "清仓库存",
            "clear",
        ],
    )
    async def cmd_exchange_dispatch_cn(self, event: AstrMessageEvent):
        """交易所命令入口"""
        parts = self._extract_message_tokens(event.message_str or "")
        cmd = parts[0].lstrip("/").strip() if parts else ""
        dispatch = {
            "持仓": self.exchange_handlers.view_inventory,
            "持倉": self.exchange_handlers.view_inventory,
            "库存": self.exchange_handlers.view_inventory,
            "庫存": self.exchange_handlers.view_inventory,
            "买入": self.exchange_handlers.buy_commodity,
            "買入": self.exchange_handlers.buy_commodity,
            "購入": self.exchange_handlers.buy_commodity,
            "卖出": self.exchange_handlers.sell_commodity,
            "賣出": self.exchange_handlers.sell_commodity,
            "清仓": self.exchange_handlers.clear_inventory,
            "清倉": self.exchange_handlers.clear_inventory,
            "清倉庫存": self.exchange_handlers.clear_inventory,
            "清仓库存": self.exchange_handlers.clear_inventory,
            "clear": self.exchange_handlers.clear_inventory,
        }
        if cmd in ["交易所", "交易市場", "交易市场", "exchange"]:
            if len(parts) > 1:
                sub = parts[1].strip()
                handler = dispatch.get(sub)
                if handler:
                    tail = " ".join(parts[2:]).strip()
                    event.message_str = f"/{sub}{(' ' + tail) if tail else ''}"
                    async for r in handler(event):
                        yield r
                    return
            async for r in self.exchange_handlers.exchange_main(event):
                yield r
            return
        handler = dispatch.get(cmd)
        if handler:
            async for r in handler(event):
                yield r
            return
        async for r in self.exchange_handlers.exchange_main(event):
            yield r

    @filter.command("抽卡", alias=["抽奖", "抽獎", "抽卡池", "抽獎池", "抽奖池"])
    async def cmd_gacha_cn(self, event: AstrMessageEvent):
        """进行单次抽卡"""
        async for r in gacha_handlers.gacha(self, event):
            yield r

    @filter.command("十连", alias=["十連"])
    async def cmd_ten_gacha_cn(self, event: AstrMessageEvent):
        """进行十连抽卡"""
        async for r in gacha_handlers.ten_gacha(self, event):
            yield r

    @filter.command(
        "查看卡池",
        alias=["卡池", "卡池詳情", "卡池详情", "查看卡池詳情", "查看卡池详情"],
    )
    async def cmd_view_pool_cn(self, event: AstrMessageEvent):
        """查看卡池详情"""
        async for r in gacha_handlers.view_gacha_pool(self, event):
            yield r

    @filter.command("抽卡记录", alias=["抽卡記錄", "抽卡历史", "抽卡歷史"])
    async def cmd_gacha_history_cn(self, event: AstrMessageEvent):
        """查看抽卡记录"""
        async for r in gacha_handlers.gacha_history(self, event):
            yield r

    @filter.command("擦弹", alias=["擦彈", "擦弹玩法", "擦彈玩法"])
    async def cmd_wipe_bomb_cn(self, event: AstrMessageEvent):
        """进行擦弹玩法"""
        async for r in gacha_handlers.wipe_bomb(self, event):
            yield r

    @filter.command("擦弹记录", alias=["擦彈記錄", "擦弹历史", "擦彈歷史"])
    async def cmd_wipe_bomb_history_cn(self, event: AstrMessageEvent):
        """查看擦弹记录"""
        async for r in gacha_handlers.wipe_bomb_history(self, event):
            yield r

    @filter.command("命运之轮", alias=["命運之輪"])
    async def cmd_wof_start_cn(self, event: AstrMessageEvent):
        """开始命运之轮"""
        async for r in gacha_handlers.start_wheel_of_fate(self, event):
            yield r

    @filter.command("继续", alias=["繼續"])
    async def cmd_wof_continue_cn(self, event: AstrMessageEvent):
        """继续命运之轮"""
        async for r in gacha_handlers.continue_wheel_of_fate(self, event):
            yield r

    @filter.command("放弃", alias=["放棄"])
    async def cmd_wof_stop_cn(self, event: AstrMessageEvent):
        """放弃命运之轮"""
        async for r in gacha_handlers.stop_wheel_of_fate(self, event):
            yield r

    @filter.command(
        "骰宝",
        alias=[
            "骰寶",
            "开庄",
            "開莊",
            "骰宝状态",
            "骰寶狀態",
            "游戏状态",
            "遊戲狀態",
            "我的下注",
            "下注情况",
            "下注情況",
            "骰宝帮助",
            "骰寶幫助",
            "骰宝说明",
            "骰寶說明",
            "骰宝赔率",
            "骰寶賠率",
            "骰宝赔率表",
            "骰寶賠率表",
            "赔率",
            "賠率",
        ],
    )
    async def cmd_sicbo_dispatch_cn(self, event: AstrMessageEvent):
        """骰宝入口"""
        parts = self._extract_message_tokens(event.message_str or "")
        cmd = parts[0].lstrip("/").strip() if parts else ""
        dispatch = {
            "开庄": sicbo_handlers.start_sicbo_game,
            "開莊": sicbo_handlers.start_sicbo_game,
            "骰宝状态": sicbo_handlers.sicbo_status,
            "骰寶狀態": sicbo_handlers.sicbo_status,
            "游戏状态": sicbo_handlers.sicbo_status,
            "遊戲狀態": sicbo_handlers.sicbo_status,
            "我的下注": sicbo_handlers.my_bets,
            "下注情况": sicbo_handlers.my_bets,
            "下注情況": sicbo_handlers.my_bets,
            "骰宝帮助": sicbo_handlers.sicbo_help,
            "骰寶幫助": sicbo_handlers.sicbo_help,
            "骰宝说明": sicbo_handlers.sicbo_help,
            "骰寶說明": sicbo_handlers.sicbo_help,
            "骰宝赔率": sicbo_handlers.sicbo_odds,
            "骰寶賠率": sicbo_handlers.sicbo_odds,
            "骰宝赔率表": sicbo_handlers.sicbo_odds,
            "骰寶賠率表": sicbo_handlers.sicbo_odds,
            "赔率": sicbo_handlers.sicbo_odds,
            "賠率": sicbo_handlers.sicbo_odds,
        }
        if cmd in ["骰宝", "骰寶"]:
            if len(parts) < 2:
                async for r in sicbo_handlers.sicbo_help(self, event):
                    yield r
                return
            sub = parts[1].strip()
            tail = " ".join(parts[2:]).strip()
            event.message_str = f"/{sub}{(' ' + tail) if tail else ''}"
            cmd = sub
        handler = dispatch.get(cmd)
        if not handler:
            yield event.plain_result(
                "❌ 未知骰宝子命令。可用：开庄/状态/帮助/赔率/我的下注/骰宝下注"
            )
            return
        async for r in handler(self, event):
            yield r

    @filter.command(
        "骰宝下注",
        alias=[
            "骰寶下注",
            "大",
            "小",
            "单",
            "單",
            "双",
            "雙",
            "豹子",
            "一点",
            "二点",
            "三点",
            "四点",
            "五点",
            "六点",
            "4点",
            "5点",
            "6点",
            "7点",
            "8点",
            "9点",
            "10点",
            "11点",
            "12点",
            "13点",
            "14点",
            "15点",
            "16点",
            "17点",
        ],
    )
    async def cmd_sicbo_bet_cn(self, event: AstrMessageEvent):
        """骰宝下注入口（兼容旧指令）"""
        cmd = ""
        parts = []
        if event.message_str:
            parts = self._extract_message_tokens(event.message_str)
            if parts:
                cmd = parts[0].lstrip("/").strip()

        dispatch = {
            "大": sicbo_handlers.bet_big,
            "小": sicbo_handlers.bet_small,
            "单": sicbo_handlers.bet_odd,
            "單": sicbo_handlers.bet_odd,
            "双": sicbo_handlers.bet_even,
            "雙": sicbo_handlers.bet_even,
            "豹子": sicbo_handlers.bet_triple,
            "一点": sicbo_handlers.bet_one_point,
            "二点": sicbo_handlers.bet_two_point,
            "三点": sicbo_handlers.bet_three_point,
            "四点": sicbo_handlers.bet_four_point,
            "五点": sicbo_handlers.bet_five_point,
            "六点": sicbo_handlers.bet_six_point,
            "4点": sicbo_handlers.bet_4_points,
            "5点": sicbo_handlers.bet_5_points,
            "6点": sicbo_handlers.bet_6_points,
            "7点": sicbo_handlers.bet_7_points,
            "8点": sicbo_handlers.bet_8_points,
            "9点": sicbo_handlers.bet_9_points,
            "10点": sicbo_handlers.bet_10_points,
            "11点": sicbo_handlers.bet_11_points,
            "12点": sicbo_handlers.bet_12_points,
            "13点": sicbo_handlers.bet_13_points,
            "14点": sicbo_handlers.bet_14_points,
            "15点": sicbo_handlers.bet_15_points,
            "16点": sicbo_handlers.bet_16_points,
            "17点": sicbo_handlers.bet_17_points,
        }

        if cmd == "骰宝下注" or cmd == "骰寶下注":
            if len(parts) < 2:
                yield event.plain_result(
                    "❌ 用法：/骰宝下注 玩法 金额，例如 /骰宝下注 大 100"
                )
                return
            cmd = parts[1].strip()

        handler = dispatch.get(cmd)
        if not handler:
            yield event.plain_result(
                "❌ 無效下注玩法。可用：大/小/单/双/豹子/一点..六点/4点..17点"
            )
            return

        async for r in handler(self, event):
            yield r

    @filter.command("排行榜", alias=["phb"])
    async def cmd_ranking_cn(self, event: AstrMessageEvent):
        """查看排行榜"""
        async for r in social_handlers.ranking(self, event):
            yield r

    @filter.command("偷鱼", alias=["偷魚", "偷魚", "偷鱼"])
    async def cmd_steal_fish_cn(self, event: AstrMessageEvent):
        """偷取指定用户的一条鱼"""
        async for r in social_handlers.steal_fish(self, event):
            yield r

    @filter.command("电鱼", alias=["電魚", "電鱼", "电魚"])
    async def cmd_electric_fish_cn(self, event: AstrMessageEvent):
        """电击指定用户鱼塘"""
        async for r in social_handlers.electric_fish(self, event):
            yield r

    @filter.command("驱灵", alias=["驅靈", "驅灵", "驱靈"])
    async def cmd_dispel_cn(self, event: AstrMessageEvent):
        """驱散目标海灵守护"""
        async for r in social_handlers.dispel_protection(self, event):
            yield r

    @filter.command("查看称号", alias=["查看稱號", "称号", "稱號"])
    async def cmd_view_titles_cn(self, event: AstrMessageEvent):
        """查看拥有称号"""
        async for r in social_handlers.view_titles(self, event):
            yield r

    @filter.command("使用称号", alias=["使用稱號"])
    async def cmd_use_title_cn(self, event: AstrMessageEvent):
        """装备指定称号"""
        async for r in social_handlers.use_title(self, event):
            yield r

    @filter.command("查看成就", alias=["成就"])
    async def cmd_view_achievements_cn(self, event: AstrMessageEvent):
        """查看成就进度"""
        async for r in social_handlers.view_achievements(self, event):
            yield r

    @filter.command("税收记录", alias=["稅收記錄"])
    async def cmd_tax_record_cn(self, event: AstrMessageEvent):
        """查看税收记录"""
        async for r in social_handlers.tax_record(self, event):
            yield r

    @filter.command(
        "鱼类图鉴",
        alias=["魚類圖鑑", "魚類圖鉴", "魚類圖鑒", "鱼类图鑑", "图鉴", "圖鑑", "图鑑"],
    )
    async def cmd_fish_pokedex_cn(self, event: AstrMessageEvent):
        """查看鱼类图鉴"""
        async for r in self.fishing_handlers.fish_pokedex(event):
            yield r

    @filter.command(
        "红包",
        alias=[
            "紅包",
            "发红包",
            "發紅包",
            "发放红包",
            "發放紅包",
            "领红包",
            "領紅包",
            "抢红包",
            "搶紅包",
            "拿红包",
            "拿紅包",
            "取红包",
            "取紅包",
            "领取红包",
            "領取紅包",
            "红包列表",
            "紅包列表",
            "查看红包列表",
            "查看紅包列表",
            "红包详情",
            "紅包詳情",
            "查看红包",
            "查看紅包",
            "撤回红包",
            "撤回紅包",
            "撤销红包",
            "撤銷紅包",
            "取消红包",
            "取消紅包",
        ],
    )
    async def cmd_red_packet_dispatch_cn(self, event: AstrMessageEvent):
        """红包命令入口"""
        parts = self._extract_message_tokens(event.message_str or "")
        cmd = parts[0].lstrip("/").strip() if parts else ""
        dispatch = {
            "发红包": red_packet_handlers.send_red_packet,
            "發紅包": red_packet_handlers.send_red_packet,
            "发放红包": red_packet_handlers.send_red_packet,
            "發放紅包": red_packet_handlers.send_red_packet,
            "领红包": red_packet_handlers.claim_red_packet,
            "領紅包": red_packet_handlers.claim_red_packet,
            "抢红包": red_packet_handlers.claim_red_packet,
            "搶紅包": red_packet_handlers.claim_red_packet,
            "拿红包": red_packet_handlers.claim_red_packet,
            "拿紅包": red_packet_handlers.claim_red_packet,
            "取红包": red_packet_handlers.claim_red_packet,
            "取紅包": red_packet_handlers.claim_red_packet,
            "领取红包": red_packet_handlers.claim_red_packet,
            "領取紅包": red_packet_handlers.claim_red_packet,
            "红包列表": red_packet_handlers.list_red_packets,
            "紅包列表": red_packet_handlers.list_red_packets,
            "查看红包列表": red_packet_handlers.list_red_packets,
            "查看紅包列表": red_packet_handlers.list_red_packets,
            "红包详情": red_packet_handlers.red_packet_details,
            "紅包詳情": red_packet_handlers.red_packet_details,
            "查看红包": red_packet_handlers.red_packet_details,
            "查看紅包": red_packet_handlers.red_packet_details,
            "撤回红包": red_packet_handlers.revoke_red_packet,
            "撤回紅包": red_packet_handlers.revoke_red_packet,
            "撤销红包": red_packet_handlers.revoke_red_packet,
            "撤銷紅包": red_packet_handlers.revoke_red_packet,
            "取消红包": red_packet_handlers.revoke_red_packet,
            "取消紅包": red_packet_handlers.revoke_red_packet,
        }
        if cmd in ["红包", "紅包"]:
            if len(parts) < 2:
                async for r in red_packet_handlers.list_red_packets(self, event):
                    yield r
                return
            sub = parts[1].strip()
            tail = " ".join(parts[2:]).strip()
            event.message_str = f"/{sub}{(' ' + tail) if tail else ''}"
            cmd = sub
        handler = dispatch.get(cmd)
        if not handler:
            yield event.plain_result(
                "❌ 未知红包子命令。可用：发红包/领红包/红包列表/红包详情/撤回红包"
            )
            return
        async for r in handler(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command(
        "钓鱼管理",
        alias=[
            "釣魚管理",
            "修改金币",
            "修改金幣",
            "奖励金币",
            "獎勵金幣",
            "扣除金币",
            "扣除金幣",
            "修改高级货币",
            "修改高級貨幣",
            "奖励高级货币",
            "獎勵高級貨幣",
            "扣除高级货币",
            "扣除高級貨幣",
            "全体奖励金币",
            "全體獎勵金幣",
            "全体奖励高级货币",
            "全體獎勵高級貨幣",
            "全体扣除金币",
            "全體扣除金幣",
            "全体扣除高级货币",
            "全體扣除高級貨幣",
            "全体发放道具",
            "全體發放道具",
            "开启钓鱼后台管理",
            "開啟釣魚後台管理",
            "开啓钓鱼后台管理",
            "开启钓鱼管理后台",
            "開啟釣魚管理後台",
            "開啟釣魚管理後臺",
            "開啓釣魚管理後臺",
            "開啟釣魚後臺管理",
            "開啓釣魚後臺管理",
            "关闭钓鱼后台管理",
            "關閉釣魚後台管理",
            "关閉钓鱼后台管理",
            "关闭钓鱼管理后台",
            "關閉釣魚管理後台",
            "關閉釣魚管理後臺",
            "關閉釣魚後臺管理",
            "代理上线",
            "代理上線",
            "login",
            "代理下线",
            "代理下線",
            "logout",
            "同步初始设定",
            "同步初始設定",
            "同步设定",
            "同步設定",
            "同步数据",
            "同步數據",
            "同步",
            "授予称号",
            "授予稱號",
            "移除称号",
            "移除稱號",
            "创建称号",
            "創建稱號",
            "补充鱼池",
            "補充魚池",
            "骰宝结算",
            "骰寶結算",
            "骰宝倒计时",
            "骰寶倒計時",
            "骰宝模式",
            "骰寶模式",
            "清理红包",
            "清理紅包",
            "切换建议",
            "切換建議",
            "建议开关",
            "建議開關",
            "切换提示",
            "切換提示",
        ],
    )
    async def cmd_admin_dispatch_cn(self, event: AstrMessageEvent):
        """钓鱼管理命令入口（管理员）"""
        parts = self._extract_message_tokens(event.message_str or "")
        cmd = parts[0].lstrip("/").strip() if parts else ""

        if cmd in ["钓鱼管理", "釣魚管理"]:
            if len(parts) < 2:
                yield event.plain_result(
                    "❌ 用法：/钓鱼管理 子命令 參數，例如 /钓鱼管理 修改金币 用户ID 数量"
                )
                return
            sub_cmd = parts[1].strip()
            tail = " ".join(parts[2:]).strip()
            event.message_str = f"/{sub_cmd}{(' ' + tail) if tail else ''}"
            cmd = sub_cmd

        dispatch = {
            "修改金币": admin_handlers.modify_coins,
            "修改金幣": admin_handlers.modify_coins,
            "奖励金币": admin_handlers.reward_coins,
            "獎勵金幣": admin_handlers.reward_coins,
            "扣除金币": admin_handlers.deduct_coins,
            "扣除金幣": admin_handlers.deduct_coins,
            "修改高级货币": admin_handlers.modify_premium,
            "修改高級貨幣": admin_handlers.modify_premium,
            "奖励高级货币": admin_handlers.reward_premium,
            "獎勵高級貨幣": admin_handlers.reward_premium,
            "扣除高级货币": admin_handlers.deduct_premium,
            "扣除高級貨幣": admin_handlers.deduct_premium,
            "全体奖励金币": admin_handlers.reward_all_coins,
            "全體獎勵金幣": admin_handlers.reward_all_coins,
            "全体奖励高级货币": admin_handlers.reward_all_premium,
            "全體獎勵高級貨幣": admin_handlers.reward_all_premium,
            "全体扣除金币": admin_handlers.deduct_all_coins,
            "全體扣除金幣": admin_handlers.deduct_all_coins,
            "全体扣除高级货币": admin_handlers.deduct_all_premium,
            "全體扣除高級貨幣": admin_handlers.deduct_all_premium,
            "全体发放道具": admin_handlers.reward_all_items,
            "全體發放道具": admin_handlers.reward_all_items,
            "开启钓鱼后台管理": admin_handlers.start_admin,
            "開啟釣魚後台管理": admin_handlers.start_admin,
            "开啓钓鱼后台管理": admin_handlers.start_admin,
            "开启钓鱼管理后台": admin_handlers.start_admin,
            "開啟釣魚管理後台": admin_handlers.start_admin,
            "開啟釣魚管理後臺": admin_handlers.start_admin,
            "開啓釣魚管理後臺": admin_handlers.start_admin,
            "開啟釣魚後臺管理": admin_handlers.start_admin,
            "開啓釣魚後臺管理": admin_handlers.start_admin,
            "关闭钓鱼后台管理": admin_handlers.stop_admin,
            "關閉釣魚後台管理": admin_handlers.stop_admin,
            "关閉钓鱼后台管理": admin_handlers.stop_admin,
            "关闭钓鱼管理后台": admin_handlers.stop_admin,
            "關閉釣魚管理後台": admin_handlers.stop_admin,
            "關閉釣魚管理後臺": admin_handlers.stop_admin,
            "關閉釣魚後臺管理": admin_handlers.stop_admin,
            "代理上线": admin_handlers.impersonate_start,
            "代理上線": admin_handlers.impersonate_start,
            "login": admin_handlers.impersonate_start,
            "代理下线": admin_handlers.impersonate_stop,
            "代理下線": admin_handlers.impersonate_stop,
            "logout": admin_handlers.impersonate_stop,
            "同步初始设定": admin_handlers.sync_initial_data,
            "同步初始設定": admin_handlers.sync_initial_data,
            "同步设定": admin_handlers.sync_initial_data,
            "同步設定": admin_handlers.sync_initial_data,
            "同步数据": admin_handlers.sync_initial_data,
            "同步數據": admin_handlers.sync_initial_data,
            "同步": admin_handlers.sync_initial_data,
            "授予称号": admin_handlers.grant_title,
            "授予稱號": admin_handlers.grant_title,
            "移除称号": admin_handlers.revoke_title,
            "移除稱號": admin_handlers.revoke_title,
            "创建称号": admin_handlers.create_title,
            "創建稱號": admin_handlers.create_title,
            "补充鱼池": admin_handlers.replenish_fish_pools,
            "補充魚池": admin_handlers.replenish_fish_pools,
            "骰宝结算": sicbo_handlers.force_settle_sicbo,
            "骰寶結算": sicbo_handlers.force_settle_sicbo,
            "骰宝倒计时": sicbo_handlers.set_sicbo_countdown,
            "骰寶倒計時": sicbo_handlers.set_sicbo_countdown,
            "骰宝模式": sicbo_handlers.set_sicbo_mode,
            "骰寶模式": sicbo_handlers.set_sicbo_mode,
            "清理红包": red_packet_handlers.cleanup_red_packets,
            "清理紅包": red_packet_handlers.cleanup_red_packets,
            "切换建议": admin_handlers.toggle_suggestions,
            "切換建議": admin_handlers.toggle_suggestions,
            "建议开关": admin_handlers.toggle_suggestions,
            "建議開關": admin_handlers.toggle_suggestions,
            "切换提示": admin_handlers.toggle_suggestions,
            "切換提示": admin_handlers.toggle_suggestions,
        }

        handler = dispatch.get(cmd)
        if not handler:
            yield event.plain_result("❌ 未知管理子命令。可用：/钓鱼管理 同步")
            return

        async for r in handler(self, event):
            yield r

    async def terminate(self):
        logger.info("釣魚插件正在終止...")
        self.fishing_service.stop_auto_fishing_task()
        self.fishing_service.stop_daily_tax_task()
        self.achievement_service.stop_achievement_check_task()
        self.exchange_service.stop_daily_price_update_task()
        if hasattr(self, "_red_packet_cleanup_task"):
            self._red_packet_cleanup_task.cancel()
        if self.web_admin_task:
            self.web_admin_task.cancel()
        if getattr(self, "external_sql_sync_manager", None):
            await self.external_sql_sync_manager.stop()
        logger.info("釣魚插件已終止。")
