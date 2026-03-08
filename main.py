import os
import asyncio
import re

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter, MessageChain
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.permission import PermissionType

# ==========================================================
# 导入所有仓储层 & 服务层
# ==========================================================
from .core.repositories.sqlite_user_repo import SqliteUserRepository
from .core.repositories.sqlite_item_template_repo import SqliteItemTemplateRepository
from .core.repositories.sqlite_inventory_repo import SqliteInventoryRepository
from .core.repositories.sqlite_gacha_repo import SqliteGachaRepository
from .core.repositories.sqlite_market_repo import SqliteMarketRepository
from .core.repositories.sqlite_shop_repo import SqliteShopRepository
from .core.repositories.sqlite_log_repo import SqliteLogRepository
from .core.repositories.sqlite_achievement_repo import SqliteAchievementRepository
from .core.repositories.sqlite_user_buff_repo import SqliteUserBuffRepository
from .core.repositories.sqlite_exchange_repo import SqliteExchangeRepository
from .core.repositories.sqlite_red_packet_repo import SqliteRedPacketRepository
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

from .core.database.migration import run_migrations
from .core.database.external_sql_sync import ExternalSqlSyncManager

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
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
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

        run_migrations(
            db_path,
            os.path.join(os.path.dirname(__file__), "core", "database", "migrations"),
        )

        self.external_sql_sync_manager = ExternalSqlSyncManager(
            db_path, config.get("external_sql", {})
        )
        self.external_sql_sync_manager.startup_sync()
        self.storage_backend = self._get_storage_backend(config)

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

    def _get_storage_backend(self, config: AstrBotConfig) -> str:
        external_sql = config.get("external_sql", {}) or {}
        backend = str(external_sql.get("backend", "sqlite")).strip().lower()
        if backend not in {"sqlite", "mysql"}:
            backend = "sqlite"
        return backend

    def _build_user_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlUserRepository(config.get("external_sql", {}))
        return SqliteUserRepository(self.db_path)

    def _build_buff_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlUserBuffRepository(config.get("external_sql", {}))
        return SqliteUserBuffRepository(self.db_path)

    def _build_item_template_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlItemTemplateRepository(config.get("external_sql", {}))
        return SqliteItemTemplateRepository(self.db_path)

    def _build_inventory_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlInventoryRepository(config.get("external_sql", {}))
        return SqliteInventoryRepository(self.db_path)

    def _build_exchange_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlExchangeRepository(config.get("external_sql", {}))
        return SqliteExchangeRepository(self.db_path)

    def _build_market_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlMarketRepository(config.get("external_sql", {}))
        return SqliteMarketRepository(self.db_path)

    def _build_achievement_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlAchievementRepository(config.get("external_sql", {}))
        return SqliteAchievementRepository(self.db_path)

    def _build_red_packet_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlRedPacketRepository(config.get("external_sql", {}))
        return SqliteRedPacketRepository(self.db_path)

    def _build_gacha_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlGachaRepository(config.get("external_sql", {}))
        return SqliteGachaRepository(self.db_path)

    def _build_shop_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlShopRepository(config.get("external_sql", {}))
        return SqliteShopRepository(self.db_path)

    def _build_log_repo(self, config: AstrBotConfig):
        if self.storage_backend == "mysql":
            return MysqlLogRepository(config.get("external_sql", {}))
        return SqliteLogRepository(self.db_path)

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
        "钓鱼帮助", alias=["釣魚幫助", "钓鱼菜单", "釣魚菜單", "菜单", "菜單"]
    )
    async def cmd_fishing_help_cn(self, event: AstrMessageEvent):
        """查看钓鱼帮助菜单"""
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
            "打开全部钱袋",
            "打開全部錢袋",
            "打开所有钱袋",
            "打開所有錢袋",
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

    @filter.command("商店", alias=["商店", "商店列表", "店鋪", "店铺"])
    async def cmd_shop_cn(self, event: AstrMessageEvent):
        """查看商店列表或详情"""
        async for r in market_handlers.shop(self, event):
            yield r

    @filter.command(
        "商店购买",
        alias=[
            "商店購買",
            "购买商店商品",
            "購買商店商品",
            "购买商店",
            "購買商店",
            "商店买",
            "商店買",
        ],
    )
    async def cmd_buy_in_shop_cn(self, event: AstrMessageEvent):
        """从商店购买商品"""
        async for r in market_handlers.buy_in_shop(self, event):
            yield r

    @filter.command("市场", alias=["市場", "市场列表", "市場列表"])
    async def cmd_market_cn(self, event: AstrMessageEvent):
        """查看玩家交易市场"""
        async for r in market_handlers.market(self, event):
            yield r

    @filter.command("上架")
    async def cmd_list_any_cn(self, event: AstrMessageEvent):
        """将物品上架到市场"""
        async for r in market_handlers.list_any(self, event):
            yield r

    @filter.command("购买", alias=["購買"])
    async def cmd_buy_item_cn(self, event: AstrMessageEvent):
        """从市场购买商品"""
        async for r in market_handlers.buy_item(self, event):
            yield r

    @filter.command("我的上架", alias=["上架列表", "我的商品", "我的挂单", "我的掛單"])
    async def cmd_my_listings_cn(self, event: AstrMessageEvent):
        """查看我上架的商品"""
        async for r in market_handlers.my_listings(self, event):
            yield r

    @filter.command("下架")
    async def cmd_delist_item_cn(self, event: AstrMessageEvent):
        """下架我的商品"""
        async for r in market_handlers.delist_item(self, event):
            yield r

    @filter.command("交易所", alias=["交易所", "交易市場", "交易市场", "exchange"])
    async def cmd_exchange_cn(self, event: AstrMessageEvent):
        """交易所主命令"""
        async for r in self.exchange_handlers.exchange_main(event):
            yield r

    @filter.command("持仓", alias=["持倉", "库存", "庫存"])
    async def cmd_exchange_inventory_cn(self, event: AstrMessageEvent):
        """查看交易所持仓"""
        async for r in self.exchange_handlers.view_inventory(event):
            yield r

    @filter.command("清仓", alias=["清倉", "清倉庫存", "清仓库存", "clear"])
    async def cmd_exchange_clear_cn(self, event: AstrMessageEvent):
        """清空交易所持仓"""
        async for r in self.exchange_handlers.clear_inventory(event):
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

    @filter.command("开庄", alias=["開莊"])
    async def cmd_sicbo_start_cn(self, event: AstrMessageEvent):
        """开启骰宝游戏"""
        async for r in sicbo_handlers.start_sicbo_game(self, event):
            yield r

    @filter.command("骰宝状态", alias=["骰寶狀態", "游戏状态", "遊戲狀態"])
    async def cmd_sicbo_status_cn(self, event: AstrMessageEvent):
        """查看骰宝游戏状态"""
        async for r in sicbo_handlers.sicbo_status(self, event):
            yield r

    @filter.command("我的下注", alias=["下注情况", "下注情況"])
    async def cmd_sicbo_my_bets_cn(self, event: AstrMessageEvent):
        """查看我的下注"""
        async for r in sicbo_handlers.my_bets(self, event):
            yield r

    @filter.command("骰宝帮助", alias=["骰寶幫助", "骰宝说明", "骰寶說明"])
    async def cmd_sicbo_help_cn(self, event: AstrMessageEvent):
        """查看骰宝帮助"""
        async for r in sicbo_handlers.sicbo_help(self, event):
            yield r

    @filter.command(
        "骰宝赔率", alias=["骰寶賠率", "骰宝赔率表", "骰寶賠率表", "赔率", "賠率"]
    )
    async def cmd_sicbo_odds_cn(self, event: AstrMessageEvent):
        """查看骰宝赔率"""
        async for r in sicbo_handlers.sicbo_odds(self, event):
            yield r

    @filter.command("大")
    async def cmd_sicbo_big_cn(self, event: AstrMessageEvent):
        """骰宝押大"""
        async for r in sicbo_handlers.bet_big(self, event):
            yield r

    @filter.command("小")
    async def cmd_sicbo_small_cn(self, event: AstrMessageEvent):
        """骰宝押小"""
        async for r in sicbo_handlers.bet_small(self, event):
            yield r

    @filter.command("单", alias=["單"])
    async def cmd_sicbo_odd_cn(self, event: AstrMessageEvent):
        """骰宝押单"""
        async for r in sicbo_handlers.bet_odd(self, event):
            yield r

    @filter.command("双", alias=["雙"])
    async def cmd_sicbo_even_cn(self, event: AstrMessageEvent):
        """骰宝押双"""
        async for r in sicbo_handlers.bet_even(self, event):
            yield r

    @filter.command("豹子")
    async def cmd_sicbo_triple_cn(self, event: AstrMessageEvent):
        """骰宝押豹子"""
        async for r in sicbo_handlers.bet_triple(self, event):
            yield r

    @filter.command("一点")
    async def cmd_sicbo_1_cn(self, event: AstrMessageEvent):
        """骰宝押一点"""
        async for r in sicbo_handlers.bet_one_point(self, event):
            yield r

    @filter.command("二点")
    async def cmd_sicbo_2_cn(self, event: AstrMessageEvent):
        """骰宝押二点"""
        async for r in sicbo_handlers.bet_two_point(self, event):
            yield r

    @filter.command("三点")
    async def cmd_sicbo_3_cn(self, event: AstrMessageEvent):
        """骰宝押三点"""
        async for r in sicbo_handlers.bet_three_point(self, event):
            yield r

    @filter.command("四点")
    async def cmd_sicbo_4_cn(self, event: AstrMessageEvent):
        """骰宝押四点"""
        async for r in sicbo_handlers.bet_four_point(self, event):
            yield r

    @filter.command("五点")
    async def cmd_sicbo_5_cn(self, event: AstrMessageEvent):
        """骰宝押五点"""
        async for r in sicbo_handlers.bet_five_point(self, event):
            yield r

    @filter.command("六点")
    async def cmd_sicbo_6_cn(self, event: AstrMessageEvent):
        """骰宝押六点"""
        async for r in sicbo_handlers.bet_six_point(self, event):
            yield r

    @filter.command("4点")
    async def cmd_sicbo_t4_cn(self, event: AstrMessageEvent):
        """骰宝押总点数4"""
        async for r in sicbo_handlers.bet_4_points(self, event):
            yield r

    @filter.command("5点")
    async def cmd_sicbo_t5_cn(self, event: AstrMessageEvent):
        """骰宝押总点数5"""
        async for r in sicbo_handlers.bet_5_points(self, event):
            yield r

    @filter.command("6点")
    async def cmd_sicbo_t6_cn(self, event: AstrMessageEvent):
        """骰宝押总点数6"""
        async for r in sicbo_handlers.bet_6_points(self, event):
            yield r

    @filter.command("7点")
    async def cmd_sicbo_t7_cn(self, event: AstrMessageEvent):
        """骰宝押总点数7"""
        async for r in sicbo_handlers.bet_7_points(self, event):
            yield r

    @filter.command("8点")
    async def cmd_sicbo_t8_cn(self, event: AstrMessageEvent):
        """骰宝押总点数8"""
        async for r in sicbo_handlers.bet_8_points(self, event):
            yield r

    @filter.command("9点")
    async def cmd_sicbo_t9_cn(self, event: AstrMessageEvent):
        """骰宝押总点数9"""
        async for r in sicbo_handlers.bet_9_points(self, event):
            yield r

    @filter.command("10点")
    async def cmd_sicbo_t10_cn(self, event: AstrMessageEvent):
        """骰宝押总点数10"""
        async for r in sicbo_handlers.bet_10_points(self, event):
            yield r

    @filter.command("11点")
    async def cmd_sicbo_t11_cn(self, event: AstrMessageEvent):
        """骰宝押总点数11"""
        async for r in sicbo_handlers.bet_11_points(self, event):
            yield r

    @filter.command("12点")
    async def cmd_sicbo_t12_cn(self, event: AstrMessageEvent):
        """骰宝押总点数12"""
        async for r in sicbo_handlers.bet_12_points(self, event):
            yield r

    @filter.command("13点")
    async def cmd_sicbo_t13_cn(self, event: AstrMessageEvent):
        """骰宝押总点数13"""
        async for r in sicbo_handlers.bet_13_points(self, event):
            yield r

    @filter.command("14点")
    async def cmd_sicbo_t14_cn(self, event: AstrMessageEvent):
        """骰宝押总点数14"""
        async for r in sicbo_handlers.bet_14_points(self, event):
            yield r

    @filter.command("15点")
    async def cmd_sicbo_t15_cn(self, event: AstrMessageEvent):
        """骰宝押总点数15"""
        async for r in sicbo_handlers.bet_15_points(self, event):
            yield r

    @filter.command("16点")
    async def cmd_sicbo_t16_cn(self, event: AstrMessageEvent):
        """骰宝押总点数16"""
        async for r in sicbo_handlers.bet_16_points(self, event):
            yield r

    @filter.command("17点")
    async def cmd_sicbo_t17_cn(self, event: AstrMessageEvent):
        """骰宝押总点数17"""
        async for r in sicbo_handlers.bet_17_points(self, event):
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

    @filter.command("发红包", alias=["發紅包", "发放红包", "發放紅包"])
    async def cmd_send_red_packet_cn(self, event: AstrMessageEvent):
        """发送红包"""
        async for r in red_packet_handlers.send_red_packet(self, event):
            yield r

    @filter.command(
        "领红包",
        alias=[
            "領紅包",
            "抢红包",
            "搶紅包",
            "拿红包",
            "拿紅包",
            "取红包",
            "取紅包",
            "领取红包",
            "領取紅包",
        ],
    )
    async def cmd_claim_red_packet_cn(self, event: AstrMessageEvent):
        """领取红包"""
        async for r in red_packet_handlers.claim_red_packet(self, event):
            yield r

    @filter.command(
        "红包列表", alias=["紅包列表", "红包", "紅包", "查看红包列表", "查看紅包列表"]
    )
    async def cmd_red_packet_list_cn(self, event: AstrMessageEvent):
        """查看活跃红包列表"""
        async for r in red_packet_handlers.list_red_packets(self, event):
            yield r

    @filter.command("红包详情", alias=["紅包詳情", "查看红包", "查看紅包"])
    async def cmd_red_packet_detail_cn(self, event: AstrMessageEvent):
        """查看红包详情"""
        async for r in red_packet_handlers.red_packet_details(self, event):
            yield r

    @filter.command(
        "撤回红包", alias=["撤回紅包", "撤销红包", "撤銷紅包", "取消红包", "取消紅包"]
    )
    async def cmd_revoke_red_packet_cn(self, event: AstrMessageEvent):
        """撤回未领完红包"""
        async for r in red_packet_handlers.revoke_red_packet(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("修改金币", alias=["修改金幣"])
    async def cmd_admin_modify_coins_cn(self, event: AstrMessageEvent):
        """修改用户金币（管理员）"""
        async for r in admin_handlers.modify_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("奖励金币", alias=["獎勵金幣"])
    async def cmd_admin_reward_coins_cn(self, event: AstrMessageEvent):
        """奖励用户金币（管理员）"""
        async for r in admin_handlers.reward_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("扣除金币", alias=["扣除金幣"])
    async def cmd_admin_deduct_coins_cn(self, event: AstrMessageEvent):
        """扣除用户金币（管理员）"""
        async for r in admin_handlers.deduct_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("修改高级货币", alias=["修改高級貨幣"])
    async def cmd_admin_modify_premium_cn(self, event: AstrMessageEvent):
        """修改高级货币（管理员）"""
        async for r in admin_handlers.modify_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("奖励高级货币", alias=["獎勵高級貨幣"])
    async def cmd_admin_reward_premium_cn(self, event: AstrMessageEvent):
        """奖励高级货币（管理员）"""
        async for r in admin_handlers.reward_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("扣除高级货币", alias=["扣除高級貨幣"])
    async def cmd_admin_deduct_premium_cn(self, event: AstrMessageEvent):
        """扣除高级货币（管理员）"""
        async for r in admin_handlers.deduct_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体奖励金币", alias=["全體獎勵金幣"])
    async def cmd_admin_reward_all_coins_cn(self, event: AstrMessageEvent):
        """全体奖励金币（管理员）"""
        async for r in admin_handlers.reward_all_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体奖励高级货币", alias=["全體獎勵高級貨幣"])
    async def cmd_admin_reward_all_premium_cn(self, event: AstrMessageEvent):
        """全体奖励高级货币（管理员）"""
        async for r in admin_handlers.reward_all_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体扣除金币", alias=["全體扣除金幣"])
    async def cmd_admin_deduct_all_coins_cn(self, event: AstrMessageEvent):
        """全体扣除金币（管理员）"""
        async for r in admin_handlers.deduct_all_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体扣除高级货币", alias=["全體扣除高級貨幣"])
    async def cmd_admin_deduct_all_premium_cn(self, event: AstrMessageEvent):
        """全体扣除高级货币（管理员）"""
        async for r in admin_handlers.deduct_all_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体发放道具", alias=["全體發放道具"])
    async def cmd_admin_reward_all_items_cn(self, event: AstrMessageEvent):
        """全体发放道具（管理员）"""
        async for r in admin_handlers.reward_all_items(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command(
        "开启钓鱼后台管理",
        alias=[
            "開啟釣魚後台管理",
            "开啓钓鱼后台管理",
            "开启钓鱼管理后台",
            "開啟釣魚管理後台",
            "開啟釣魚管理後臺",
            "開啓釣魚管理後臺",
            "開啟釣魚後臺管理",
            "開啓釣魚後臺管理",
        ],
    )
    async def cmd_admin_start_web_cn(self, event: AstrMessageEvent):
        """开启钓鱼后台管理（管理员）"""
        async for r in admin_handlers.start_admin(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command(
        "关闭钓鱼后台管理",
        alias=[
            "關閉釣魚後台管理",
            "关閉钓鱼后台管理",
            "关闭钓鱼管理后台",
            "關閉釣魚管理後台",
            "關閉釣魚管理後臺",
            "關閉釣魚後臺管理",
        ],
    )
    async def cmd_admin_stop_web_cn(self, event: AstrMessageEvent):
        """关闭钓鱼后台管理（管理员）"""
        async for r in admin_handlers.stop_admin(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("代理上线", alias=["代理上線", "login"])
    async def cmd_admin_impersonate_start_cn(self, event: AstrMessageEvent):
        """代理上线（管理员）"""
        async for r in admin_handlers.impersonate_start(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("代理下线", alias=["代理下線", "logout"])
    async def cmd_admin_impersonate_stop_cn(self, event: AstrMessageEvent):
        """代理下线（管理员）"""
        async for r in admin_handlers.impersonate_stop(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command(
        "同步初始设定",
        alias=["同步初始設定", "同步设定", "同步設定", "同步数据", "同步數據", "同步"],
    )
    async def cmd_admin_sync_data_cn(self, event: AstrMessageEvent):
        """同步初始数据（管理员）"""
        async for r in admin_handlers.sync_initial_data(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("授予称号", alias=["授予稱號"])
    async def cmd_admin_grant_title_cn(self, event: AstrMessageEvent):
        """授予称号（管理员）"""
        async for r in admin_handlers.grant_title(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("移除称号", alias=["移除稱號"])
    async def cmd_admin_revoke_title_cn(self, event: AstrMessageEvent):
        """移除称号（管理员）"""
        async for r in admin_handlers.revoke_title(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("创建称号", alias=["創建稱號"])
    async def cmd_admin_create_title_cn(self, event: AstrMessageEvent):
        """创建称号（管理员）"""
        async for r in admin_handlers.create_title(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("补充鱼池", alias=["補充魚池"])
    async def cmd_admin_replenish_pool_cn(self, event: AstrMessageEvent):
        """补充鱼池（管理员）"""
        async for r in admin_handlers.replenish_fish_pools(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("骰宝结算", alias=["骰寶結算"])
    async def cmd_admin_sicbo_settle_cn(self, event: AstrMessageEvent):
        """强制结算骰宝（管理员）"""
        async for r in sicbo_handlers.force_settle_sicbo(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("骰宝倒计时", alias=["骰寶倒計時"])
    async def cmd_admin_sicbo_countdown_cn(self, event: AstrMessageEvent):
        """设置骰宝倒计时（管理员）"""
        async for r in sicbo_handlers.set_sicbo_countdown(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("骰宝模式", alias=["骰寶模式"])
    async def cmd_admin_sicbo_mode_cn(self, event: AstrMessageEvent):
        """设置骰宝消息模式（管理员）"""
        async for r in sicbo_handlers.set_sicbo_mode(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("清理红包", alias=["清理紅包"])
    async def cmd_admin_cleanup_red_packet_cn(self, event: AstrMessageEvent):
        """清理红包（管理员）"""
        async for r in red_packet_handlers.cleanup_red_packets(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command(
        "切换建议", alias=["切換建議", "建议开关", "建議開關", "切换提示", "切換提示"]
    )
    async def cmd_admin_toggle_suggestions_cn(self, event: AstrMessageEvent):
        """切换建议操作显示（管理员）"""
        async for r in admin_handlers.toggle_suggestions(self, event):
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
        if hasattr(self, "external_sql_sync_manager"):
            await self.external_sql_sync_manager.stop()
        logger.info("釣魚插件已終止。")
