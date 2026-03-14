import functools
import os
import traceback
import json
import re
import random
from typing import Dict, Any
from datetime import datetime, timedelta
import csv
import io
from pathlib import Path

from quart import (
    Quart,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Blueprint,
    current_app,
    jsonify,
)
from astrbot.api import logger


admin_bp = Blueprint(
    "admin_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
)


def _plugin_config_path() -> Path:
    # .../data/plugins/astrbot_plugin_fishing/manager/server.py -> .../data/config/...
    return (
        Path(__file__).resolve().parents[3]
        / "config"
        / "astrbot_plugin_fishing_config.json"
    )


def _load_plugin_config() -> Dict[str, Any]:
    cfg_path = _plugin_config_path()
    if not cfg_path.exists():
        return {}
    with cfg_path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _save_plugin_config(cfg: Dict[str, Any]) -> None:
    cfg_path = _plugin_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _normalize_exchange_config(exchange_cfg: Dict[str, Any]) -> Dict[str, Any]:
    exchange_cfg.setdefault("initial_prices", {})
    exchange_cfg.setdefault("volatility", {})
    exchange_cfg.setdefault("commodity_descriptions", {})
    exchange_cfg.setdefault("commodity_effects", {})
    exchange_cfg.setdefault("shelf_life_days", {})

    # 兼容旧字段 shelf_life -> shelf_life_days
    shelf_life = exchange_cfg.get("shelf_life", {}) or {}
    shelf_life_days = exchange_cfg.get("shelf_life_days", {}) or {}
    for key, value in shelf_life.items():
        if key.endswith("_min") or key.endswith("_max"):
            continue
        if key not in shelf_life_days:
            try:
                shelf_life_days[key] = int(value)
            except Exception:
                pass
    exchange_cfg["shelf_life_days"] = shelf_life_days
    return exchange_cfg


def _apply_exchange_runtime_config(exchange_service, exchange_cfg: Dict[str, Any]):
    # 同步到运行中服务，避免必须重启
    exchange_cfg = _normalize_exchange_config(exchange_cfg)

    if isinstance(exchange_service.config, dict):
        exchange_service.config["exchange"] = exchange_cfg

    exchange_service.price_service.config = exchange_cfg
    exchange_service.inventory_service.config = exchange_cfg
    exchange_service.price_service.commodities = (
        exchange_service.price_service._load_commodities()
    )
    exchange_service.inventory_service.commodities = (
        exchange_service.inventory_service._load_commodities()
    )
    exchange_service.commodities = exchange_service.price_service.commodities


def _get_item_effect_notes(cfg: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    notes = cfg.setdefault("item_effect_notes", {})
    notes.setdefault("rods", {})
    notes.setdefault("baits", {})
    notes.setdefault("accessories", {})
    return notes


def _set_item_effect_note(category: str, item_id: int, note: str) -> None:
    cfg = _load_plugin_config()
    notes = _get_item_effect_notes(cfg)
    notes.setdefault(category, {})[str(item_id)] = (note or "").strip()
    _save_plugin_config(cfg)


# 工厂函数现在接收服务实例
def create_app(secret_key: str, services: Dict[str, Any]):
    """
    创建并配置Quart应用实例。

    Args:
        secret_key: 用于session加密的密钥。
        services: 关键字参数，包含所有需要注入的服务实例。
    """
    app = Quart(__name__)
    app.secret_key = os.urandom(24)
    app.config["SECRET_LOGIN_KEY"] = secret_key

    # 将所有注入的服务实例存入app的配置中，供路由函数使用
    # 键名将转换为大写，例如 'user_service' -> 'USER_SERVICE'
    for service_name, service_instance in services.items():
        app.config[service_name.upper()] = service_instance

    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.route("/")
    def root():
        return redirect(url_for("admin_bp.index"))

    @app.route("/favicon.ico")
    def favicon():
        # 返回404而不是500错误
        from quart import abort

        abort(404)

    # 添加全局错误处理器
    @app.errorhandler(404)
    async def handle_404_error(error):
        # 只对非静态资源记录404错误
        if (
            not request.path.startswith("/admin/static/")
            and request.path != "/favicon.ico"
        ):
            logger.error(f"404 Not Found: {request.url} - {request.method}")

        # 为API路径返回JSON，为页面返回HTML
        if request.path.startswith("/admin/market/") and request.method in [
            "POST",
            "PUT",
            "DELETE",
        ]:
            return {"success": False, "message": "API端点不存在"}, 404
        return "Not Found", 404

    @app.errorhandler(500)
    async def handle_500_error(error):
        logger.error(f"Internal Server Error: {error}")
        logger.error(traceback.format_exc())

        # 为API路径返回JSON，为页面返回HTML
        if request.path.startswith("/admin/market/") and request.method in [
            "POST",
            "PUT",
            "DELETE",
        ]:
            return {"success": False, "message": "服务器内部错误"}, 500
        return "Internal Server Error", 500

    return app


def login_required(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("admin_bp.login"))
        return await f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            await flash("无权限访问该页面", "danger")
            return redirect(url_for("admin_bp.login"))
        return await f(*args, **kwargs)

    return decorated_function


@admin_bp.route("/login", methods=["GET", "POST"])
async def login():
    if request.method == "POST":
        form = await request.form
        # 从应用配置中获取密钥
        secret_key = current_app.config["SECRET_LOGIN_KEY"]
        if form.get("secret_key") == secret_key:
            session["logged_in"] = True
            # 简单角色标记：现阶段使用同一密钥视为管理员
            session["is_admin"] = True
            await flash("登录成功！", "success")
            return redirect(url_for("admin_bp.index"))
        else:
            await flash("登录失败，请检查密钥！", "danger")
    return await render_template("login.html")


@admin_bp.route("/logout")
async def logout():
    session.pop("logged_in", None)
    await flash("你已成功登出。", "info")
    return redirect(url_for("admin_bp.login"))


@admin_bp.route("/")
@login_required
async def index():
    return await render_template("index.html")


# --- 物品模板管理 (鱼、鱼竿、鱼饵、饰品) ---
# 使用 item_template_service 来处理所有模板相关的CRUD操作


@admin_bp.route("/fish")
@login_required
async def manage_fish():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    fishes = item_template_service.get_all_fish()
    return await render_template("fish.html", fishes=fishes)


@admin_bp.route("/fish/add", methods=["POST"])
@login_required
async def add_fish():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 注意：服务层应处理来自表单的数据转换和验证
    item_template_service.add_fish_template(form.to_dict())
    await flash("鱼类添加成功！", "success")
    return redirect(url_for("admin_bp.manage_fish"))


@admin_bp.route("/fish/edit/<int:fish_id>", methods=["POST"])
@login_required
async def edit_fish(fish_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.update_fish_template(fish_id, form.to_dict())
    await flash(f"鱼类ID {fish_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_fish"))


@admin_bp.route("/fish/delete/<int:fish_id>", methods=["POST"])
@login_required
async def delete_fish(fish_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.delete_fish_template(fish_id)
    await flash(f"鱼类ID {fish_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_fish"))


@admin_bp.route("/fish/csv/template")
@login_required
async def fish_csv_template():
    header = [
        "name",
        "description",
        "rarity",
        "base_value",
        "min_weight",
        "max_weight",
        "icon_url",
    ]
    sample = ["示例鱼", "一条很普通的示例鱼", "1", "10", "100", "500", ""]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerow(sample)
    csv_data = output.getvalue()

    from quart import Response

    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=fish_template.csv",
        },
    )


@admin_bp.route("/fish/csv/import", methods=["POST"])
@login_required
async def import_fish_csv():
    try:
        files = await request.files
        file = files.get("file")
        if not file:
            await flash("未选择文件", "danger")
            return redirect(url_for("admin_bp.manage_fish"))

        content = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))

        required_cols = {"name", "rarity", "base_value", "min_weight", "max_weight"}
        if not required_cols.issubset(
            set([c.strip() for c in reader.fieldnames or []])
        ):
            await flash(
                "CSV列缺失，至少需要: name, rarity, base_value, min_weight, max_weight",
                "danger",
            )
            return redirect(url_for("admin_bp.manage_fish"))

        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
        success_count = 0
        fail_count = 0
        for idx, row in enumerate(reader, start=2):
            try:
                data = {
                    "name": (row.get("name") or "").strip(),
                    "description": (row.get("description") or "").strip() or None,
                    "rarity": int(row.get("rarity") or 1),
                    "base_value": int(row.get("base_value") or 0),
                    "min_weight": int(row.get("min_weight") or 1),
                    "max_weight": int(row.get("max_weight") or 100),
                    "icon_url": (row.get("icon_url") or "").strip() or None,
                }
                if not data["name"]:
                    raise ValueError("缺少名称")
                item_template_service.add_fish_template(data)
                success_count += 1
            except Exception as e:
                logger.error(f"导入鱼类第{idx}行失败: {e}")
                fail_count += 1

        if success_count:
            await flash(
                f"成功导入 {success_count} 条鱼类记录"
                + (f"，失败 {fail_count} 条" if fail_count else ""),
                "success",
            )
        else:
            await flash("未成功导入任何鱼类记录", "warning")
    except Exception as e:
        logger.error(f"导入鱼类CSV出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"导入失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_fish"))


# --- 鱼竿管理 (Rods) ---
@admin_bp.route("/rods")
@login_required
async def manage_rods():
    # 从app配置中获取服务实例
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 调用服务层方法获取所有鱼竿模板
    items = item_template_service.get_all_rods()
    cfg = _load_plugin_config()
    notes = _get_item_effect_notes(cfg).get("rods", {})
    for item in items:
        setattr(item, "effect_note", notes.get(str(item.rod_id), ""))
    return await render_template("rods.html", items=items)


@admin_bp.route("/rods/add", methods=["POST"])
@login_required
async def add_rod():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 调用服务层方法添加新的鱼竿模板
    created = item_template_service.add_rod_template(form.to_dict())
    _set_item_effect_note("rods", created.rod_id, form.get("effect_note", ""))
    await flash("鱼竿添加成功！", "success")
    return redirect(url_for("admin_bp.manage_rods"))


@admin_bp.route("/rods/edit/<int:rod_id>", methods=["POST"])
@login_required
async def edit_rod(rod_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 调用服务层方法更新指定的鱼竿模板
    item_template_service.update_rod_template(rod_id, form.to_dict())
    _set_item_effect_note("rods", rod_id, form.get("effect_note", ""))
    await flash(f"鱼竿ID {rod_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_rods"))


@admin_bp.route("/rods/delete/<int:rod_id>", methods=["POST"])
@login_required
async def delete_rod(rod_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    # 调用服务层方法删除指定的鱼竿模板
    item_template_service.delete_rod_template(rod_id)
    await flash(f"鱼竿ID {rod_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_rods"))


# --- Rods CSV 模板下载与导入 ---
@admin_bp.route("/rods/csv/template")
@login_required
async def rods_csv_template():
    header = [
        "name",
        "description",
        "rarity",
        "source",
        "purchase_cost",
        "bonus_fish_quality_modifier",
        "bonus_fish_quantity_modifier",
        "bonus_rare_fish_chance",
        "durability",
        "icon_url",
    ]
    sample = [
        "示例鱼竿",
        "这是一个示例描述",
        "3",
        "shop",
        "1000",
        "1.1",
        "1.0",
        "0.05",
        "",
        "",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerow(sample)
    csv_data = output.getvalue()

    from quart import Response

    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=rods_template.csv",
        },
    )


@admin_bp.route("/rods/csv/import", methods=["POST"])
@login_required
async def import_rods_csv():
    try:
        files = await request.files
        file = files.get("file")
        if not file:
            await flash("未选择文件", "danger")
            return redirect(url_for("admin_bp.manage_rods"))

        content = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        required_cols = {
            "name",
            "rarity",
            "source",
            "bonus_fish_quality_modifier",
            "bonus_fish_quantity_modifier",
            "bonus_rare_fish_chance",
        }
        if not required_cols.issubset(
            set([c.strip() for c in reader.fieldnames or []])
        ):
            await flash(
                "CSV列缺失，至少需要: name, rarity, source, 三个加成字段", "danger"
            )
            return redirect(url_for("admin_bp.manage_rods"))

        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
        success_count = 0
        fail_count = 0
        for idx, row in enumerate(reader, start=2):  # 从第2行开始（跳过表头）
            try:
                data = {
                    "name": (row.get("name") or "").strip(),
                    "description": (row.get("description") or "").strip() or None,
                    "rarity": int(row.get("rarity") or 1),
                    "source": (row.get("source") or "shop").strip(),
                    "purchase_cost": int(row["purchase_cost"])
                    if (row.get("purchase_cost") or "").strip() != ""
                    else None,
                    "bonus_fish_quality_modifier": float(
                        row.get("bonus_fish_quality_modifier") or 1.0
                    ),
                    "bonus_fish_quantity_modifier": float(
                        row.get("bonus_fish_quantity_modifier") or 1.0
                    ),
                    "bonus_rare_fish_chance": float(
                        row.get("bonus_rare_fish_chance") or 0.0
                    ),
                    "durability": int(row["durability"])
                    if (row.get("durability") or "").strip() != ""
                    else None,
                    "icon_url": (row.get("icon_url") or "").strip() or None,
                }
                if not data["name"]:
                    raise ValueError("缺少名称")
                item_template_service.add_rod_template(data)
                success_count += 1
            except Exception as e:
                logger.error(f"导入鱼竿第{idx}行失败: {e}")
                fail_count += 1

        if success_count:
            await flash(
                f"成功导入 {success_count} 条鱼竿记录"
                + (f"，失败 {fail_count} 条" if fail_count else ""),
                "success",
            )
        else:
            await flash("未成功导入任何鱼竿记录", "warning")
    except Exception as e:
        logger.error(f"导入鱼竿CSV出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"导入失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_rods"))


# --- 鱼饵管理 (Baits) ---
@admin_bp.route("/baits")
@login_required
async def manage_baits():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    items = item_template_service.get_all_baits()
    cfg = _load_plugin_config()
    notes = _get_item_effect_notes(cfg).get("baits", {})
    for item in items:
        setattr(item, "effect_note", notes.get(str(item.bait_id), ""))
    return await render_template("baits.html", items=items)


@admin_bp.route("/baits/add", methods=["POST"])
@login_required
async def add_bait():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    created = item_template_service.add_bait_template(form.to_dict())
    _set_item_effect_note("baits", created.bait_id, form.get("effect_note", ""))
    await flash("鱼饵添加成功！", "success")
    return redirect(url_for("admin_bp.manage_baits"))


@admin_bp.route("/baits/edit/<int:bait_id>", methods=["POST"])
@login_required
async def edit_bait(bait_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.update_bait_template(bait_id, form.to_dict())
    _set_item_effect_note("baits", bait_id, form.get("effect_note", ""))
    await flash(f"鱼饵ID {bait_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_baits"))


@admin_bp.route("/baits/delete/<int:bait_id>", methods=["POST"])
@login_required
async def delete_bait(bait_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.delete_bait_template(bait_id)
    await flash(f"鱼饵ID {bait_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_baits"))


# --- 饰品管理 (Accessories) ---
@admin_bp.route("/accessories")
@login_required
async def manage_accessories():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    items = item_template_service.get_all_accessories()
    cfg = _load_plugin_config()
    notes = _get_item_effect_notes(cfg).get("accessories", {})
    for item in items:
        setattr(item, "effect_note", notes.get(str(item.accessory_id), ""))
    return await render_template("accessories.html", items=items)


@admin_bp.route("/accessories/add", methods=["POST"])
@login_required
async def add_accessory():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    created = item_template_service.add_accessory_template(form.to_dict())
    _set_item_effect_note(
        "accessories", created.accessory_id, form.get("effect_note", "")
    )
    await flash("饰品添加成功！", "success")
    return redirect(url_for("admin_bp.manage_accessories"))


@admin_bp.route("/accessories/edit/<int:accessory_id>", methods=["POST"])
@login_required
async def edit_accessory(accessory_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.update_accessory_template(accessory_id, form.to_dict())
    _set_item_effect_note("accessories", accessory_id, form.get("effect_note", ""))
    await flash(f"饰品ID {accessory_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_accessories"))


@admin_bp.route("/accessories/delete/<int:accessory_id>", methods=["POST"])
@login_required
async def delete_accessory(accessory_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.delete_accessory_template(accessory_id)
    await flash(f"饰品ID {accessory_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_accessories"))


# --- Accessories CSV 模板下载与导入 ---
@admin_bp.route("/accessories/csv/template")
@login_required
async def accessories_csv_template():
    header = [
        "name",
        "description",
        "rarity",
        "slot_type",
        "bonus_fish_quality_modifier",
        "bonus_fish_quantity_modifier",
        "bonus_rare_fish_chance",
        "bonus_coin_modifier",
        "other_bonus_description",
        "icon_url",
    ]
    sample = [
        "示例饰品",
        "这是一个示例描述",
        "2",
        "general",
        "1.05",
        "1.0",
        "0.02",
        "1.10",
        "额外描述",
        "",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerow(sample)
    csv_data = output.getvalue()

    from quart import Response

    return Response(
        csv_data,
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=accessories_template.csv",
        },
    )


@admin_bp.route("/accessories/csv/import", methods=["POST"])
@login_required
async def import_accessories_csv():
    try:
        files = await request.files
        file = files.get("file")
        if not file:
            await flash("未选择文件", "danger")
            return redirect(url_for("admin_bp.manage_accessories"))

        content = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        required_cols = {
            "name",
            "rarity",
            "slot_type",
            "bonus_fish_quality_modifier",
            "bonus_fish_quantity_modifier",
            "bonus_rare_fish_chance",
            "bonus_coin_modifier",
        }
        if not required_cols.issubset(
            set([c.strip() for c in reader.fieldnames or []])
        ):
            await flash(
                "CSV列缺失，至少需要: name, rarity, slot_type, 四个加成字段", "danger"
            )
            return redirect(url_for("admin_bp.manage_accessories"))

        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
        success_count = 0
        fail_count = 0
        for idx, row in enumerate(reader, start=2):
            try:
                data = {
                    "name": (row.get("name") or "").strip(),
                    "description": (row.get("description") or "").strip() or None,
                    "rarity": int(row.get("rarity") or 1),
                    "slot_type": (row.get("slot_type") or "general").strip(),
                    "bonus_fish_quality_modifier": float(
                        row.get("bonus_fish_quality_modifier") or 1.0
                    ),
                    "bonus_fish_quantity_modifier": float(
                        row.get("bonus_fish_quantity_modifier") or 1.0
                    ),
                    "bonus_rare_fish_chance": float(
                        row.get("bonus_rare_fish_chance") or 0.0
                    ),
                    "bonus_coin_modifier": float(row.get("bonus_coin_modifier") or 1.0),
                    "other_bonus_description": (
                        row.get("other_bonus_description") or ""
                    ).strip()
                    or None,
                    "icon_url": (row.get("icon_url") or "").strip() or None,
                }
                if not data["name"]:
                    raise ValueError("缺少名称")
                item_template_service.add_accessory_template(data)
                success_count += 1
            except Exception as e:
                logger.error(f"导入饰品第{idx}行失败: {e}")
                fail_count += 1

        if success_count:
            await flash(
                f"成功导入 {success_count} 条饰品记录"
                + (f"，失败 {fail_count} 条" if fail_count else ""),
                "success",
            )
        else:
            await flash("未成功导入任何饰品记录", "warning")
    except Exception as e:
        logger.error(f"导入饰品CSV出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"导入失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_accessories"))


# --- 抽卡池管理 ---
@admin_bp.route("/gacha")
@login_required
async def manage_gacha():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    pools = item_template_service.get_all_gacha_pools()
    # 直接渲染，不再拼装包含物品的展示数据
    return await render_template("gacha.html", pools=pools)


@admin_bp.route("/gacha/add", methods=["POST"])
@login_required
async def add_gacha_pool():
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    data = form.to_dict()
    # 将 currency_type/cost_amount 映射到 cost_coins 或 cost_premium_currency
    currency_type = data.get("currency_type", "coins")
    amount = int(data.get("cost_amount", 0) or 0)
    # 限时逻辑：仅当开关为 ON 时保留截止时间
    is_limited_flag = data.get("is_limited_time") in (True, "1", 1, "on")
    open_until_value = (
        data.get("open_until") if is_limited_flag and data.get("open_until") else None
    )
    payload = {
        "name": data.get("name"),
        "description": data.get("description"),
        "cost_coins": amount if currency_type == "coins" else 0,
        "cost_premium_currency": amount if currency_type == "premium" else 0,
        "is_limited_time": is_limited_flag,
        "open_until": open_until_value,
    }
    item_template_service.add_pool_template(payload)
    await flash("奖池添加成功！", "success")
    return redirect(url_for("admin_bp.manage_gacha"))


@admin_bp.route("/gacha/edit/<int:pool_id>", methods=["POST"])
@login_required
async def edit_gacha_pool(pool_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    data = form.to_dict()
    currency_type = data.get("currency_type", "coins")
    amount = int(data.get("cost_amount", 0) or 0)
    # 限时逻辑：仅当开关为 ON 时保留截止时间
    is_limited_flag = data.get("is_limited_time") in (True, "1", 1, "on")
    open_until_value = (
        data.get("open_until") if is_limited_flag and data.get("open_until") else None
    )
    payload = {
        "name": data.get("name"),
        "description": data.get("description"),
        "cost_coins": amount if currency_type == "coins" else 0,
        "cost_premium_currency": amount if currency_type == "premium" else 0,
        "is_limited_time": is_limited_flag,
        "open_until": open_until_value,
    }
    item_template_service.update_pool_template(pool_id, payload)
    await flash(f"奖池ID {pool_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_gacha"))


@admin_bp.route("/gacha/copy/<int:pool_id>", methods=["POST"])
@login_required
async def copy_gacha_pool(pool_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        new_pool_id = item_template_service.copy_pool_template(pool_id)
        await flash(
            f"奖池ID {pool_id} 已成功复制，新奖池ID为 {new_pool_id}！", "success"
        )
    except Exception as e:
        await flash(f"复制奖池失败：{str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_gacha"))


@admin_bp.route("/gacha/delete/<int:pool_id>", methods=["POST"])
@login_required
async def delete_gacha_pool(pool_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.delete_pool_template(pool_id)
    await flash(f"奖池ID {pool_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_gacha"))


# --- 奖池物品详情管理 ---
@admin_bp.route("/gacha/pool/<int:pool_id>")
@login_required
async def manage_gacha_pool_details(pool_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    details = item_template_service.get_pool_details_for_admin(pool_id)

    if not details.get("pool"):
        await flash("找不到指定的奖池！", "danger")
        return redirect(url_for("admin_bp.manage_gacha"))

    enriched_items = []
    for item in details.get("pool").items:
        # 将 dataclass 转换为字典以便修改
        item_dict = item.__dict__
        item_name = "未知物品"
        item_rarity = None  # 添加星级属性
        item_type = item.item_type
        item_id = item.item_id

        # 根据类型从 item_template_service 获取名称和星级
        if item_type == "rod":
            template = item_template_service.item_template_repo.get_rod_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "accessory":
            template = item_template_service.item_template_repo.get_accessory_by_id(
                item_id
            )
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "bait":
            template = item_template_service.item_template_repo.get_bait_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "item":
            template = item_template_service.item_template_repo.get_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "fish":
            template = item_template_service.item_template_repo.get_fish_by_id(item_id)
            if template:
                item_name = template.name
                item_rarity = template.rarity
        elif item_type == "titles":
            template = item_template_service.item_template_repo.get_title_by_id(item_id)
            if template:
                item_name = template.name
        elif item_type == "coins":
            item_name = f"{item.quantity} 金币"

        item_dict["item_name"] = item_name  # 添加名称属性
        item_dict["rarity"] = item_rarity  # 添加星级属性
        enriched_items.append(item_dict)

    return await render_template(
        "gacha_pool_details.html",
        pool=details["pool"],
        items=enriched_items,  # 传递丰富化后的物品列表
        all_rods=details["all_rods"],
        all_baits=details["all_baits"],
        all_accessories=details["all_accessories"],
        all_items=item_template_service.get_all_items(),  # 新增
    )


@admin_bp.route("/gacha/pool/<int:pool_id>/add_item", methods=["POST"])
@login_required
async def add_item_to_pool(pool_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    item_template_service.add_item_to_pool(pool_id, form.to_dict())
    await flash("成功向奖池中添加物品！", "success")
    return redirect(url_for("admin_bp.manage_gacha_pool_details", pool_id=pool_id))


@admin_bp.route("/gacha/pool/edit_item/<int:item_id>", methods=["POST"])
@login_required
async def edit_pool_item(item_id):
    form = await request.form
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    pool_id = request.args.get("pool_id")
    if not pool_id:
        await flash("编辑失败：缺少奖池ID信息。", "danger")
        return redirect(url_for("admin_bp.manage_gacha"))
    item_template_service.update_pool_item(item_id, form.to_dict())
    await flash(f"奖池物品ID {item_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_gacha_pool_details", pool_id=pool_id))


@admin_bp.route("/gacha/pool/delete_item/<int:item_id>", methods=["POST"])
@login_required
async def delete_pool_item(item_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    pool_id = request.args.get("pool_id")
    if not pool_id:
        await flash("删除失败：缺少奖池ID信息。", "danger")
        return redirect(url_for("admin_bp.manage_gacha"))
    item_template_service.delete_pool_item(item_id)
    await flash(f"奖池物品ID {item_id} 已删除！", "warning")
    return redirect(url_for("admin_bp.manage_gacha_pool_details", pool_id=pool_id))


@admin_bp.route("/gacha/pool/update_weight/<int:item_id>", methods=["POST"])
@login_required
async def update_pool_item_weight(item_id):
    """快速更新奖池物品权重"""
    try:
        data = await request.get_json()
        weight = data.get("weight")

        if not weight or not isinstance(weight, (int, float)) or weight < 1:
            return jsonify({"success": False, "message": "权重必须是大于0的数字"}), 400

        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]

        # 直接更新权重，update_pool_item方法会处理验证
        item_template_service.update_pool_item(item_id, {"weight": int(weight)})

        return jsonify({"success": True, "message": "权重更新成功"})

    except Exception as e:
        logger.error(f"权重更新失败 - item_id: {item_id}, error: {str(e)}")
        return jsonify({"success": False, "message": f"更新失败: {str(e)}"}), 500


# --- 用户管理 ---
@admin_bp.route("/users")
@login_required
@admin_required
async def manage_users():
    user_service = current_app.config["USER_SERVICE"]
    page = int(request.args.get("page", 1))
    search = request.args.get("search", "")

    result = user_service.get_users_for_admin(
        page=page, per_page=20, search=search or None
    )

    if not result["success"]:
        await flash("获取用户列表失败：" + result.get("message", "未知错误"), "danger")
        return redirect(url_for("admin_bp.index"))

    return await render_template(
        "users.html",
        users=result["users"],
        pagination=result["pagination"],
        search=search,
    )


@admin_bp.route("/users/<user_id>")
@login_required
@admin_required
async def get_user_detail(user_id):
    user_service = current_app.config["USER_SERVICE"]
    result = user_service.get_user_details_for_admin(user_id)

    if not result["success"]:
        return {"success": False, "message": result["message"]}, 404

    # 将User对象转换为字典以便JSON序列化
    user_dict = {
        "user_id": result["user"].user_id,
        "nickname": result["user"].nickname,
        "coins": result["user"].coins,
        "premium_currency": result["user"].premium_currency,
        "total_fishing_count": result["user"].total_fishing_count,
        "total_weight_caught": result["user"].total_weight_caught,
        "total_coins_earned": result["user"].total_coins_earned,
        "consecutive_login_days": result["user"].consecutive_login_days,
        "fish_pond_capacity": result["user"].fish_pond_capacity,
        "fishing_zone_id": result["user"].fishing_zone_id,
        "auto_fishing_enabled": result["user"].auto_fishing_enabled,
        "created_at": result["user"].created_at.isoformat()
        if result["user"].created_at
        else None,
        "last_login_time": result["user"].last_login_time.isoformat()
        if result["user"].last_login_time
        else None,
    }

    return {
        "success": True,
        "user": user_dict,
        "equipped_rod": result["equipped_rod"],
        "equipped_accessory": result["equipped_accessory"],
        "current_title": result["current_title"],
        "titles": result.get("titles", []),
    }


@admin_bp.route("/users/<user_id>/update", methods=["POST"])
@login_required
@admin_required
async def update_user(user_id):
    user_service = current_app.config["USER_SERVICE"]

    try:
        # 获取JSON数据
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400

        return user_service.update_user_for_admin(user_id, data)
    except Exception as e:
        return {"success": False, "message": f"更新用户时发生错误: {str(e)}"}, 500


@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
async def delete_user(user_id):
    user_service = current_app.config["USER_SERVICE"]

    try:
        return user_service.delete_user_for_admin(user_id)
    except Exception as e:
        return {"success": False, "message": f"删除用户时发生错误: {str(e)}"}, 500


# --- 交易所管理 ---
@admin_bp.route("/exchange")
@login_required
async def manage_exchange():
    try:
        exchange_service = current_app.config["EXCHANGE_SERVICE"]

        # 获取当前价格
        market_status = exchange_service.get_market_status()

        # 获取价格历史（最近7天）
        price_history = exchange_service.get_price_history(days=7)

        # 获取用户持仓统计
        user_stats = exchange_service.get_user_commodity_stats()

        plugin_cfg = _load_plugin_config()
        exchange_cfg = _normalize_exchange_config(plugin_cfg.get("exchange", {}) or {})

        commodity_rows = []
        commodities = market_status.get("commodities", {}) if market_status else {}
        for commodity_id, info in commodities.items():
            commodity_rows.append(
                {
                    "commodity_id": commodity_id,
                    "name": info.get("name", commodity_id),
                    "description": info.get("description", ""),
                    "initial_price": (exchange_cfg.get("initial_prices", {}) or {}).get(
                        commodity_id, 1000
                    ),
                    "volatility": (exchange_cfg.get("volatility", {}) or {}).get(
                        commodity_id, 0.1
                    ),
                    "shelf_life_days": (
                        exchange_cfg.get("shelf_life_days", {}) or {}
                    ).get(commodity_id, 3),
                    "effect": (exchange_cfg.get("commodity_effects", {}) or {}).get(
                        commodity_id, ""
                    ),
                }
            )

        commodity_rows.sort(key=lambda x: x["commodity_id"])

        return await render_template(
            "exchange.html",
            market_status=market_status,
            price_history=price_history,
            user_stats=user_stats,
            commodity_rows=commodity_rows,
            now=datetime.now(),
        )
    except Exception as e:
        logger.error(f"交易所管理页面出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"页面加载失败: {str(e)}", "danger")
        return redirect(url_for("admin_bp.index"))


@admin_bp.route("/config/help")
@login_required
async def config_help():
    return await render_template("config_help.html")


@admin_bp.route("/exchange/update_prices", methods=["POST"])
@login_required
async def update_exchange_prices():
    try:
        exchange_service = current_app.config["EXCHANGE_SERVICE"]
        result = exchange_service.manual_update_prices()

        if result["success"]:
            await flash("交易所价格更新成功！", "success")
        else:
            await flash(f"价格更新失败：{result['message']}", "danger")
    except Exception as e:
        logger.error(f"更新交易所价格失败: {e}")
        await flash(f"价格更新失败: {str(e)}", "danger")

    return redirect(url_for("admin_bp.manage_exchange"))


@admin_bp.route("/exchange/reset_prices", methods=["POST"])
@login_required
async def reset_exchange_prices():
    try:
        exchange_service = current_app.config["EXCHANGE_SERVICE"]
        result = exchange_service.reset_prices_to_initial()

        if result["success"]:
            await flash("交易所价格已重置到初始值！", "success")
        else:
            await flash(f"价格重置失败：{result['message']}", "danger")
    except Exception as e:
        logger.error(f"重置交易所价格失败: {e}")
        await flash(f"价格重置失败: {str(e)}", "danger")

    return redirect(url_for("admin_bp.manage_exchange"))


@admin_bp.route("/exchange/market_status", methods=["POST"])
@login_required
@admin_required
async def update_exchange_market_status():
    try:
        form = await request.form
        market_sentiment = form.get("market_sentiment", "neutral")
        price_trend = form.get("price_trend", "stable")
        supply_demand = form.get("supply_demand", "平衡")

        cfg = _load_plugin_config()
        exchange_cfg = cfg.get("exchange", {}) or {}
        exchange_cfg["manual_market_sentiment"] = market_sentiment
        exchange_cfg["manual_price_trend"] = price_trend
        exchange_cfg["manual_supply_demand"] = supply_demand
        cfg["exchange"] = exchange_cfg
        _save_plugin_config(cfg)

        exchange_service = current_app.config.get("EXCHANGE_SERVICE")
        if exchange_service and hasattr(exchange_service, "price_service"):
            price_service = exchange_service.price_service
            price_service.config["manual_market_sentiment"] = market_sentiment
            price_service.config["manual_price_trend"] = price_trend
            price_service.config["manual_supply_demand"] = supply_demand

        sentiment_labels = {
            "panic": "恐慌",
            "pessimistic": "悲观",
            "neutral": "中性",
            "optimistic": "乐观",
            "euphoric": "狂热",
        }
        trend_labels = {
            "crashing": "暴跌",
            "declining": "下跌",
            "stable": "稳定",
            "rising": "上涨",
            "surging": "暴涨",
        }
        await flash(
            f"市场状态已更新：情绪={sentiment_labels.get(market_sentiment, market_sentiment)}，趋势={trend_labels.get(price_trend, price_trend)}，供需={supply_demand}",
            "success",
        )
    except Exception as e:
        logger.error(f"更新市场状态失败: {e}")
        await flash(f"更新失败: {str(e)}", "danger")

    return redirect(url_for("admin_bp.manage_exchange"))


@admin_bp.route("/exchange/commodity/upsert", methods=["POST"])
@login_required
@admin_required
async def upsert_exchange_commodity():
    try:
        form = await request.form
        commodity_id = (form.get("commodity_id") or "").strip().lower()
        name = (form.get("name") or "").strip()
        description = (form.get("description") or "").strip()
        effect = (form.get("effect") or "").strip()

        if not commodity_id or not re.fullmatch(r"[a-z0-9_]{2,64}", commodity_id):
            await flash(
                "商品ID格式无效（仅支持小写字母/数字/下划线，2-64位）", "danger"
            )
            return redirect(url_for("admin_bp.manage_exchange"))
        if not name:
            await flash("商品名称不能为空", "danger")
            return redirect(url_for("admin_bp.manage_exchange"))

        try:
            initial_price = int(form.get("initial_price") or 1000)
            volatility = float(form.get("volatility") or 0.1)
            shelf_life_days = int(form.get("shelf_life_days") or 3)
        except Exception:
            await flash("价格/波动率/保质期参数格式错误", "danger")
            return redirect(url_for("admin_bp.manage_exchange"))

        if initial_price < 1:
            initial_price = 1
        volatility = max(0.001, min(volatility, 1.0))
        shelf_life_days = max(1, shelf_life_days)

        exchange_service = current_app.config["EXCHANGE_SERVICE"]
        exchange_repo = exchange_service.exchange_repo

        with exchange_repo._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO commodities (commodity_id, name, description)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    description = VALUES(description)
                    """,
                    (commodity_id, name, description),
                )
                conn.commit()

        # 写入配置：初始价/波动率/保质期/描述/效果
        cfg = _load_plugin_config()
        exchange_cfg = _normalize_exchange_config(cfg.get("exchange", {}) or {})
        exchange_cfg["initial_prices"][commodity_id] = initial_price
        exchange_cfg["volatility"][commodity_id] = volatility
        exchange_cfg["shelf_life_days"][commodity_id] = shelf_life_days
        exchange_cfg.setdefault("shelf_life", {})[commodity_id] = shelf_life_days
        exchange_cfg["commodity_descriptions"][commodity_id] = description
        exchange_cfg["commodity_effects"][commodity_id] = effect
        cfg["exchange"] = exchange_cfg
        _save_plugin_config(cfg)

        _apply_exchange_runtime_config(exchange_service, exchange_cfg)

        await flash(f"商品 {commodity_id} 已保存，并同步作用效果与交易参数", "success")
    except Exception as e:
        logger.error(f"保存交易商品失败: {e}")
        logger.error(traceback.format_exc())
        await flash(f"保存失败: {str(e)}", "danger")

    return redirect(url_for("admin_bp.manage_exchange"))


# --- 市场管理 ---
@admin_bp.route("/market")
@login_required
async def manage_market():
    try:
        market_service = current_app.config["MARKET_SERVICE"]

        # 获取查询参数
        page = int(request.args.get("page", 1))
        item_type = request.args.get("item_type", "")
        min_price = request.args.get("min_price", "")
        max_price = request.args.get("max_price", "")
        search = request.args.get("search", "")

        # 转换参数
        min_price = int(min_price) if min_price else None
        max_price = int(max_price) if max_price else None
        item_type = item_type or None
        search = search or None

        result = market_service.get_all_market_listings_for_admin(
            page=page,
            per_page=20,
            item_type=item_type,
            min_price=min_price,
            max_price=max_price,
            search=search,
        )

        if not result["success"]:
            await flash(
                "获取市场列表失败：" + result.get("message", "未知错误"), "danger"
            )
            return redirect(url_for("admin_bp.index"))

        return await render_template(
            "market.html",
            listings=result["listings"],
            pagination=result["pagination"],
            stats=result["stats"],
            filters={
                "item_type": request.args.get("item_type", ""),
                "min_price": request.args.get("min_price", ""),
                "max_price": request.args.get("max_price", ""),
                "search": request.args.get("search", ""),
            },
        )
    except Exception as e:
        logger.error(f"市场管理页面出错: {e}")
        logger.error(traceback.format_exc())
        await flash(f"页面加载失败: {str(e)}", "danger")
        return redirect(url_for("admin_bp.index"))


@admin_bp.route("/market/<int:market_id>/price", methods=["POST"])
@login_required
async def update_market_price(market_id):
    market_service = current_app.config["MARKET_SERVICE"]

    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400

        new_price = data.get("price")
        if new_price is None:
            return {"success": False, "message": "缺少价格参数"}, 400

        # 类型校验: 检查 new_price 是否为数字
        try:
            new_price_numeric = float(new_price)
        except (TypeError, ValueError):
            return {"success": False, "message": "价格参数必须为数字"}, 400

        return market_service.update_market_item_price(
            market_id, int(new_price_numeric)
        )
    except Exception as e:
        logger.error(f"更新价格错误: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"更新价格时发生错误: {str(e)}"}, 500


@admin_bp.route("/market/<int:market_id>/remove", methods=["POST"])
@login_required
async def remove_market_item(market_id):
    market_service = current_app.config["MARKET_SERVICE"]

    try:
        return market_service.remove_market_item_by_admin(market_id)
    except Exception as e:
        logger.error(f"下架商品错误: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"下架商品时发生错误: {str(e)}"}, 500


@admin_bp.route("/market/cleanup", methods=["POST"])
@login_required
async def cleanup_market_listings():
    market_service = current_app.config["MARKET_SERVICE"]
    try:
        market_service.cleanup_expired_listings()
        return {"success": True, "message": "已清理过期/腐败挂单"}
    except Exception as e:
        logger.error(f"清理市场挂单错误: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"清理失败: {str(e)}"}, 500


@admin_bp.route("/users/create", methods=["POST"])
@login_required
@admin_required
async def create_user():
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        return user_service.create_user_for_admin(data)
    except Exception as e:
        return {"success": False, "message": f"创建用户时发生错误: {str(e)}"}, 500


# --- 用户物品管理 ---
@admin_bp.route("/users/<user_id>/inventory")
@login_required
@admin_required
async def manage_user_inventory(user_id):
    try:
        user_service = current_app.config["USER_SERVICE"]
        item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]

        # 获取用户库存信息
        inventory_result = user_service.get_user_inventory_for_admin(user_id)

        if not inventory_result["success"]:
            await flash(
                "获取用户库存失败：" + inventory_result.get("message", "未知错误"),
                "danger",
            )
            return redirect(url_for("admin_bp.manage_users"))

        # 获取所有物品模板用于添加物品
        all_fish = item_template_service.get_all_fish()
        all_rods = item_template_service.get_all_rods()
        all_accessories = item_template_service.get_all_accessories()
        all_baits = item_template_service.get_all_baits()
        all_items = item_template_service.get_all_items()

        return await render_template(
            "users_inventory.html",
            user_id=user_id,
            user_nickname=inventory_result["nickname"],
            inventory=inventory_result,
            all_fish=all_fish,
            all_rods=all_rods,
            all_accessories=all_accessories,
            all_baits=all_baits,
            all_items=all_items,
        )
    except Exception as e:
        await flash(f"页面加载失败: {str(e)}", "danger")
        return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/<user_id>/inventory/add", methods=["POST"])
@login_required
async def add_item_to_user_inventory(user_id):
    user_service = current_app.config["USER_SERVICE"]

    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400

        item_type = data.get("item_type")
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)
        quality_level = data.get("quality_level", 0)  # 添加品质等级参数

        if not item_type or not item_id:
            return {"success": False, "message": "缺少必要参数"}, 400

        result = user_service.add_item_to_user_inventory(
            user_id, item_type, item_id, quantity, quality_level
        )
        return result
    except Exception as e:
        return {"success": False, "message": f"添加物品时发生错误: {str(e)}"}, 500


@admin_bp.route("/users/<user_id>/inventory/remove", methods=["POST"])
@login_required
async def remove_item_from_user_inventory(user_id):
    user_service = current_app.config["USER_SERVICE"]

    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400

        item_type = data.get("item_type")
        item_id = data.get("item_id")
        quantity = data.get("quantity", 1)

        if not item_type or not item_id:
            return {"success": False, "message": "缺少必要参数"}, 400

        result = user_service.remove_item_from_user_inventory(
            user_id, item_type, item_id, quantity
        )
        return result
    except Exception as e:
        return {"success": False, "message": f"移除物品时发生错误: {str(e)}"}, 500


# --- 用户物品实例属性编辑（精炼等级/耐久度） ---
@admin_bp.route(
    "/users/<user_id>/inventory/rod/<int:instance_id>/update", methods=["POST"]
)
@login_required
@admin_required
async def update_rod_instance(user_id, instance_id):
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        return user_service.update_user_rod_instance_for_admin(
            user_id, instance_id, data
        )
    except Exception as e:
        return {"success": False, "message": f"更新鱼竿实例时发生错误: {str(e)}"}, 500


@admin_bp.route(
    "/users/<user_id>/inventory/accessory/<int:instance_id>/update", methods=["POST"]
)
@login_required
@admin_required
async def update_accessory_instance(user_id, instance_id):
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400
        return user_service.update_user_accessory_instance_for_admin(
            user_id, instance_id, data
        )
    except Exception as e:
        return {"success": False, "message": f"更新饰品实例时发生错误: {str(e)}"}, 500


# --- 称号管理 ---
@admin_bp.route("/titles")
@login_required
@admin_required
async def manage_titles():
    user_service = current_app.config["USER_SERVICE"]
    result = user_service.get_all_titles_for_admin()
    if not result["success"]:
        await flash("获取称号列表失败：" + result.get("message", "未知错误"), "danger")
        return redirect(url_for("admin_bp.index"))
    return await render_template("titles.html", titles=result["titles"])


@admin_bp.route("/titles/add", methods=["POST"])
@login_required
@admin_required
async def add_title():
    user_service = current_app.config["USER_SERVICE"]
    form = await request.form
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    display_format = form.get("display_format", "{name}").strip()
    trigger_type = form.get("trigger_type", "").strip() or None
    trigger_value = form.get("trigger_value", "").strip()

    if not name:
        await flash("称号名称不能为空", "danger")
        return redirect(url_for("admin_bp.manage_titles"))

    if not description:
        description = f"自定义称号：{name}"

    trigger_value_int = int(trigger_value) if trigger_value else None

    result = user_service.create_custom_title(
        name, description, display_format, trigger_type, trigger_value_int
    )
    if result["success"]:
        await flash(result["message"], "success")
    else:
        await flash(result["message"], "danger")
    return redirect(url_for("admin_bp.manage_titles"))


@admin_bp.route("/titles/edit/<int:title_id>", methods=["POST"])
@login_required
@admin_required
async def edit_title(title_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    form = await request.form
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    display_format = form.get("display_format", "{name}").strip()
    trigger_type = form.get("trigger_type", "").strip() or None
    trigger_value = form.get("trigger_value", "").strip()

    if not name:
        await flash("称号名称不能为空", "danger")
        return redirect(url_for("admin_bp.manage_titles"))

    # 检查称号是否存在
    existing_title = item_template_service.get_title_by_id(title_id)
    if not existing_title:
        await flash(f"称号ID {title_id} 不存在", "danger")
        return redirect(url_for("admin_bp.manage_titles"))

    # 检查名称是否与其他称号冲突
    title_by_name = item_template_service.get_title_by_name(name)
    if title_by_name and title_by_name.title_id != title_id:
        await flash(f"称号名称 '{name}' 已被其他称号使用", "danger")
        return redirect(url_for("admin_bp.manage_titles"))

    # 更新称号
    trigger_value_int = int(trigger_value) if trigger_value else None
    title_data = {
        "name": name,
        "description": description,
        "display_format": display_format,
        "trigger_type": trigger_type,
        "trigger_value": trigger_value_int,
    }
    item_template_service.update_title_template(title_id, title_data)
    await flash(f"称号ID {title_id} 更新成功！", "success")
    return redirect(url_for("admin_bp.manage_titles"))


@admin_bp.route("/titles/delete/<int:title_id>", methods=["POST"])
@login_required
@admin_required
async def delete_title(title_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        item_template_service.delete_title_template(title_id)
        await flash(f"称号ID {title_id} 已删除！", "warning")
    except Exception as e:
        await flash(f"删除失败：{str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_titles"))


@admin_bp.route("/users/<user_id>/grant_title", methods=["POST"])
@login_required
@admin_required
async def grant_title_to_user(user_id):
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400

        title_name = data.get("title_name")
        if not title_name:
            return {"success": False, "message": "缺少称号名称"}, 400

        result = user_service.grant_title_to_user_by_name(user_id, title_name)
        return result
    except Exception as e:
        return {"success": False, "message": f"授予称号时发生错误: {str(e)}"}, 500


@admin_bp.route("/users/<user_id>/revoke_title", methods=["POST"])
@login_required
@admin_required
async def revoke_title_from_user(user_id):
    user_service = current_app.config["USER_SERVICE"]
    try:
        data = await request.get_json()
        if not data:
            return {"success": False, "message": "无效的请求数据"}, 400

        title_name = data.get("title_name")
        if not title_name:
            return {"success": False, "message": "缺少称号名称"}, 400

        result = user_service.revoke_title_from_user_by_name(user_id, title_name)
        return result
    except Exception as e:
        return {"success": False, "message": f"移除称号时发生错误: {str(e)}"}, 500


@admin_bp.route("/api/titles", methods=["GET"])
@login_required
@admin_required
async def api_get_all_titles():
    """获取所有称号列表的API"""
    user_service = current_app.config["USER_SERVICE"]
    result = user_service.get_all_titles_for_admin()
    return jsonify(result)


# --- 道具管理 ---
@admin_bp.route("/items")
@login_required
@admin_required
async def manage_items():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    items = item_template_service.get_all_items()
    return await render_template("items.html", items=items)


@admin_bp.route("/items/add", methods=["POST"])
@login_required
@admin_required
async def add_item():
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        form_data = await request.form
        data = {k: v for k, v in form_data.items() if v}
        data["rarity"] = int(data.get("rarity", 1))
        data["cost"] = int(data.get("cost", 0))
        is_flag = "is_consumable" in form_data
        data["is_consumable"] = is_flag
        if "effect_type" not in data:
            data["effect_type"] = None
        if "effect_payload" not in data:
            data["effect_payload"] = None
        item_template_service.add_item_template(data)
        await flash("道具模板已添加", "success")
    except Exception as e:
        await flash(f"添加道具模板失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_items"))


@admin_bp.route("/items/edit/<int:item_id>", methods=["POST"])
@login_required
@admin_required
async def edit_item(item_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        form_data = await request.form
        data = {k: v for k, v in form_data.items() if v}
        data["rarity"] = int(data.get("rarity", 1))
        data["cost"] = int(data.get("cost", 0))
        is_flag = "is_consumable" in form_data
        data["is_consumable"] = is_flag
        if "effect_type" not in data:
            data["effect_type"] = None
        if "effect_payload" not in data:
            data["effect_payload"] = None
        item_template_service.update_item_template(item_id, data)
        await flash("道具模板已更新", "success")
    except Exception as e:
        await flash(f"更新道具模板失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_items"))


@admin_bp.route("/items/delete/<int:item_id>", methods=["POST"])
@login_required
@admin_required
async def delete_item(item_id):
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    try:
        item_template_service.delete_item_template(item_id)
        await flash("道具模板已删除", "success")
    except Exception as e:
        await flash(f"删除道具模板失败: {str(e)}", "danger")
    return redirect(url_for("admin_bp.manage_items"))


@admin_bp.route("/zones", methods=["GET"])
@login_required
async def manage_zones():
    fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]
    zones = fishing_zone_service.get_all_zones()
    all_fish = item_template_service.get_all_fish()
    all_items = item_template_service.get_all_items()
    return await render_template(
        "zones.html", zones=zones, all_fish=all_fish, all_items=all_items
    )


@admin_bp.route("/api/zones", methods=["POST"])
@login_required
async def create_zone_api():
    try:
        data = await request.get_json()
        fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]

        # --- Enhanced Validation ---
        errors = {}
        zone_id = data.get("id")
        if not zone_id or not str(zone_id).isdigit() or int(zone_id) <= 0:
            errors["id"] = "区域 ID 必须是一个正整数"

        if not data.get("name"):
            errors["name"] = "区域名称不能为空"

        quota = data.get("daily_rare_fish_quota")
        if quota is None or not str(quota).isdigit() or int(quota) < 0:
            errors["daily_rare_fish_quota"] = "稀有鱼每日配额必须是一个非负整数"

        fishing_cost = data.get("fishing_cost")
        if (
            fishing_cost is None
            or not str(fishing_cost).isdigit()
            or int(fishing_cost) < 1
        ):
            errors["fishing_cost"] = "钓鱼消耗必须是一个正整数"

        if errors:
            return jsonify(
                {"success": False, "message": "数据校验失败", "errors": errors}
            ), 400
        # --- End of Validation ---

        new_zone = fishing_zone_service.create_zone(data)
        # create_zone 已返回字典，直接返回
        return jsonify(
            {"success": True, "message": "钓鱼区域创建成功", "zone": new_zone}
        )
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 409  # 409 Conflict
    except Exception as e:
        logger.error(f"创建钓鱼区域失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/api/zones/<int:zone_id>", methods=["PUT"])
@login_required
async def update_zone_api(zone_id):
    try:
        data = await request.get_json()
        fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]

        # --- Enhanced Validation ---
        errors = {}
        if not data.get("name"):
            errors["name"] = "区域名称不能为空"

        quota = data.get("daily_rare_fish_quota")
        if quota is None or not str(quota).isdigit() or int(quota) < 0:
            errors["daily_rare_fish_quota"] = "稀有鱼每日配额必须是一个非负整数"

        fishing_cost = data.get("fishing_cost")
        if (
            fishing_cost is None
            or not str(fishing_cost).isdigit()
            or int(fishing_cost) < 1
        ):
            errors["fishing_cost"] = "钓鱼消耗必须是一个正整数"

        if errors:
            return jsonify(
                {"success": False, "message": "数据校验失败", "errors": errors}
            ), 400
        # --- End of Validation ---

        fishing_zone_service.update_zone(zone_id, data)
        # 前端会刷新页面，这里不必返回完整对象
        return jsonify({"success": True, "message": "钓鱼区域更新成功"})
    except Exception as e:
        logger.error(f"更新钓鱼区域失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/api/zones/assign-fish", methods=["POST"])
@login_required
async def assign_fish_to_zones_api():
    try:
        data = await request.get_json()
        fish_id = data.get("fish_id")
        zone_ids = data.get("zone_ids") or []
        if not fish_id or not isinstance(zone_ids, list):
            return jsonify({"success": False, "message": "参数错误"}), 400

        fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]
        for zone_id in zone_ids:
            zone = fishing_zone_service.inventory_repo.get_zone_by_id(int(zone_id))
            existing = (
                fishing_zone_service.inventory_repo.get_specific_fish_ids_for_zone(
                    zone.id
                )
            )
            if fish_id not in existing:
                existing.append(int(fish_id))
                fishing_zone_service.inventory_repo.update_specific_fish_for_zone(
                    zone.id, existing
                )

        fishing_zone_service.strategies = fishing_zone_service._load_strategies()
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"自动分配限定鱼失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/api/zones/<int:zone_id>", methods=["DELETE"])
@login_required
async def delete_zone_api(zone_id):
    try:
        fishing_zone_service = current_app.config["FISHING_ZONE_SERVICE"]
        fishing_zone_service.delete_zone(zone_id)
        return jsonify({"success": True, "message": "钓鱼区域删除成功"})
    except Exception as e:
        logger.error(f"删除钓鱼区域失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500


# --- 商店管理 (Shop Offers) - 已集成到商店详情页面 ---


# ===== 商店管理（新设计：shops + shop_items） =====
@admin_bp.route("/shops")
@login_required
async def manage_shops():
    shop_service = current_app.config["SHOP_SERVICE"]
    shops = shop_service.shop_repo.get_all_shops()
    # 对商店列表进行排序：按 sort_order 升序，然后按 shop_id 升序
    shops.sort(key=lambda x: (x.get("sort_order", 999), x.get("shop_id", 999)))

    # 确保所有值都是 JSON 可序列化的
    def sanitize(obj):
        from datetime import timedelta, datetime

        if isinstance(obj, timedelta):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        return obj

    shops = sanitize(shops)
    return await render_template("shops.html", shops=shops)


@admin_bp.route("/shops/<int:shop_id>")
@login_required
async def manage_shop_details(shop_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    item_template_service = current_app.config["ITEM_TEMPLATE_SERVICE"]

    # 获取商店信息
    shop = shop_service.shop_repo.get_shop_by_id(shop_id)
    if not shop:
        return "商店不存在", 404

    # 获取商店内的商品
    items = shop_service.shop_repo.get_shop_items(shop_id)
    items_with_details = []

    for item in items:
        # 获取成本和奖励
        costs = shop_service.shop_repo.get_item_costs(item["item_id"])
        rewards = shop_service.shop_repo.get_item_rewards(item["item_id"])

        # 为成本添加物品名称
        for cost in costs:
            if cost["cost_type"] == "fish":
                fish_template = item_template_service.get_fish_by_id(
                    cost.get("cost_item_id")
                )
                cost["fish_name"] = fish_template.name if fish_template else None
            elif cost["cost_type"] == "item":
                item_template = item_template_service.get_item_by_id(
                    cost.get("cost_item_id")
                )
                cost["item_name"] = item_template.name if item_template else None
            elif cost["cost_type"] == "rod":
                rod_template = item_template_service.get_rod_by_id(
                    cost.get("cost_item_id")
                )
                cost["rod_name"] = rod_template.name if rod_template else None
            elif cost["cost_type"] == "accessory":
                accessory_template = item_template_service.get_accessory_by_id(
                    cost.get("cost_item_id")
                )
                cost["accessory_name"] = (
                    accessory_template.name if accessory_template else None
                )

        # 为奖励添加物品名称
        for reward in rewards:
            if reward["reward_type"] == "fish":
                fish_template = item_template_service.get_fish_by_id(
                    reward.get("reward_item_id")
                )
                reward["fish_name"] = fish_template.name if fish_template else None
            elif reward["reward_type"] == "item":
                item_template = item_template_service.get_item_by_id(
                    reward.get("reward_item_id")
                )
                reward["item_name"] = item_template.name if item_template else None
            elif reward["reward_type"] == "rod":
                rod_template = item_template_service.get_rod_by_id(
                    reward.get("reward_item_id")
                )
                reward["rod_name"] = rod_template.name if rod_template else None
            elif reward["reward_type"] == "accessory":
                accessory_template = item_template_service.get_accessory_by_id(
                    reward.get("reward_item_id")
                )
                reward["accessory_name"] = (
                    accessory_template.name if accessory_template else None
                )
            elif reward["reward_type"] == "bait":
                bait_template = item_template_service.get_bait_by_id(
                    reward.get("reward_item_id")
                )
                reward["bait_name"] = bait_template.name if bait_template else None

        items_with_details.append(
            {
                "item": item,
                "costs": costs,
                "rewards": rewards,
            }
        )

    # 获取所有可用的商品（兼容旧接口）
    available_offers = shop_service.shop_repo.get_active_offers()

    # 可选物品下拉所需的全量模板数据
    all_rods = item_template_service.get_all_rods()
    all_baits = item_template_service.get_all_baits()
    all_accessories = item_template_service.get_all_accessories()
    all_items = item_template_service.get_all_items()
    all_fish = item_template_service.get_all_fish()

    return await render_template(
        "shop_details.html",
        shop=shop,
        items=items_with_details,
        available_offers=available_offers,
        all_rods=all_rods,
        all_baits=all_baits,
        all_accessories=all_accessories,
        all_items=all_items,
        all_fish=all_fish,
    )


@admin_bp.route("/api/shops", methods=["GET"])
@login_required
async def api_list_shops():
    shop_service = current_app.config["SHOP_SERVICE"]
    shops = shop_service.shop_repo.get_all_shops()
    # 对商店列表进行排序：按 sort_order 升序，然后按 shop_id 升序
    shops.sort(key=lambda x: (x.get("sort_order", 999), x.get("shop_id", 999)))
    return jsonify({"success": True, "shops": shops})


@admin_bp.route("/shops/add", methods=["POST"])
@login_required
async def add_shop():
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]

    shop_data = {
        "name": data.get("name"),
        "description": data.get("description"),
        "shop_type": data.get("shop_type", "normal"),
        "is_active": data.get("is_active") == "on",
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "daily_start_time": data.get("daily_start_time") or None,
        "daily_end_time": data.get("daily_end_time") or None,
        "sort_order": int(data.get("sort_order", 100)),
    }

    created = shop_service.shop_repo.create_shop(shop_data)
    return redirect(url_for("admin_bp.manage_shops"))


@admin_bp.route("/shops/edit/<int:shop_id>", methods=["POST"])
@login_required
async def edit_shop(shop_id):
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]

    shop_data = {
        "name": data.get("name"),
        "description": data.get("description"),
        "shop_type": data.get("shop_type", "normal"),
        "is_active": data.get("is_active") == "on",
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "daily_start_time": data.get("daily_start_time") or None,
        "daily_end_time": data.get("daily_end_time") or None,
        "sort_order": int(data.get("sort_order", 100)),
    }

    shop_service.shop_repo.update_shop(shop_id, shop_data)
    return redirect(url_for("admin_bp.manage_shops"))


@admin_bp.route("/shops/delete/<int:shop_id>", methods=["POST"])
@login_required
async def delete_shop(shop_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.delete_shop(shop_id)
    return redirect(url_for("admin_bp.manage_shops"))


@admin_bp.route("/api/shops", methods=["POST"])
@login_required
async def api_create_shop():
    payload = await request.get_json()
    shop_service = current_app.config["SHOP_SERVICE"]
    created = shop_service.shop_repo.create_shop(payload or {})
    return jsonify({"success": True, "shop": created})


@admin_bp.route("/api/shops/<int:shop_id>", methods=["PUT"])
@login_required
async def api_update_shop(shop_id):
    payload = await request.get_json()
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.update_shop(shop_id, payload or {})
    return jsonify({"success": True})


@admin_bp.route("/api/shops/<int:shop_id>", methods=["DELETE"])
@login_required
async def api_delete_shop(shop_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.delete_shop(shop_id)
    return jsonify({"success": True})


@admin_bp.route("/api/shops/<int:shop_id>/items", methods=["GET"])
@login_required
async def api_get_shop_items(shop_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    items = shop_service.shop_repo.get_shop_items(shop_id)
    return jsonify({"success": True, "items": items})


@admin_bp.route("/shops/<int:shop_id>/items/add", methods=["POST"])
@login_required
async def add_shop_item(shop_id):
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]

    # 创建商品
    item_data = {
        "name": data.get("name") or "未命名商品",
        "description": data.get("description") or "",
        "category": data.get("category", "general"),
        "stock_total": int(data.get("stock_total"))
        if data.get("stock_total")
        else None,
        "stock_sold": int(data.get("stock_sold", 0)),
        "per_user_limit": int(data.get("per_user_limit"))
        if data.get("per_user_limit")
        else None,
        "per_user_daily_limit": int(data.get("per_user_daily_limit"))
        if data.get("per_user_daily_limit")
        else None,
        "is_active": data.get("is_active") == "on",
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "sort_order": int(data.get("sort_order", 100)),
    }

    created_item = shop_service.shop_repo.create_shop_item(shop_id, item_data)
    item_id = created_item["item_id"]

    # 解析并添加成本
    cost_full_ids = (
        data.getlist("cost_item_full_id") if hasattr(data, "getlist") else []
    )
    cost_amounts = data.getlist("cost_amount") if hasattr(data, "getlist") else []
    cost_relations = data.getlist("cost_relation") if hasattr(data, "getlist") else []
    cost_groups = data.getlist("cost_group") if hasattr(data, "getlist") else []
    cost_quality_levels = (
        data.getlist("cost_quality_level") if hasattr(data, "getlist") else []
    )

    for idx, full_id in enumerate(cost_full_ids):
        if not full_id:
            continue
        amount_text = cost_amounts[idx] if idx < len(cost_amounts) else ""
        if not amount_text:
            continue
        try:
            amount_val = int(amount_text)
        except Exception:
            continue

        t, _, id_text = full_id.partition("-")
        cost_data = {
            "cost_type": t,
            "cost_amount": amount_val,
            "cost_relation": cost_relations[idx]
            if idx < len(cost_relations)
            else "and",
            "group_id": int(cost_groups[idx])
            if idx < len(cost_groups) and cost_groups[idx]
            else None,
            "quality_level": int(cost_quality_levels[idx])
            if idx < len(cost_quality_levels) and cost_quality_levels[idx]
            else 0,
        }

        if t in ("fish", "item", "rod", "accessory"):
            try:
                cost_data["cost_item_id"] = int(id_text)
            except Exception:
                continue

        shop_service.shop_repo.add_item_cost(item_id, cost_data)

    # 解析并添加奖励
    reward_full_ids = (
        data.getlist("reward_item_full_id") if hasattr(data, "getlist") else []
    )
    reward_quantities = (
        data.getlist("reward_quantity") if hasattr(data, "getlist") else []
    )
    reward_refine_levels = (
        data.getlist("reward_refine_level") if hasattr(data, "getlist") else []
    )
    reward_quality_levels = (
        data.getlist("reward_quality_level") if hasattr(data, "getlist") else []
    )

    for idx, full_id in enumerate(reward_full_ids):
        if not full_id:
            continue
        qty_text = reward_quantities[idx] if idx < len(reward_quantities) else "1"
        try:
            qty_val = int(qty_text or "1")
        except Exception:
            qty_val = 1

        t, _, id_text = full_id.partition("-")
        reward_data = {
            "reward_type": t,
            "reward_quantity": qty_val,
            "reward_refine_level": int(reward_refine_levels[idx])
            if idx < len(reward_refine_levels) and reward_refine_levels[idx]
            else None,
            "quality_level": int(reward_quality_levels[idx])
            if idx < len(reward_quality_levels) and reward_quality_levels[idx]
            else 0,
        }

        try:
            reward_data["reward_item_id"] = int(id_text)
        except Exception:
            continue

        shop_service.shop_repo.add_item_reward(item_id, reward_data)

    return redirect(url_for("admin_bp.manage_shop_details", shop_id=shop_id))


@admin_bp.route("/shops/<int:shop_id>/items/edit/<int:item_id>", methods=["POST"])
@login_required
async def edit_shop_item(shop_id, item_id):
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]

    # 更新商品信息
    item_data = {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "category": data.get("category", "general"),
        "stock_total": int(data.get("stock_total"))
        if data.get("stock_total")
        else None,
        "stock_sold": int(data.get("stock_sold", 0)),
        "per_user_limit": int(data.get("per_user_limit"))
        if data.get("per_user_limit")
        else None,
        "per_user_daily_limit": int(data.get("per_user_daily_limit"))
        if data.get("per_user_daily_limit")
        else None,
        "is_active": data.get("is_active") == "on",
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "sort_order": int(data.get("sort_order", 100)),
    }

    shop_service.shop_repo.update_shop_item(item_id, item_data)

    # 更新成本（先删除旧的，再添加新的）
    # 这里简化处理，实际项目中可能需要更精细的更新逻辑
    costs = shop_service.shop_repo.get_item_costs(item_id)
    for cost in costs:
        shop_service.shop_repo.delete_item_cost(cost["cost_id"])

    # 添加新成本
    cost_full_ids = (
        data.getlist("cost_item_full_id") if hasattr(data, "getlist") else []
    )
    cost_amounts = data.getlist("cost_amount") if hasattr(data, "getlist") else []
    cost_relations = data.getlist("cost_relation") if hasattr(data, "getlist") else []
    cost_groups = data.getlist("cost_group") if hasattr(data, "getlist") else []
    cost_quality_levels = (
        data.getlist("cost_quality_level") if hasattr(data, "getlist") else []
    )

    for idx, full_id in enumerate(cost_full_ids):
        if not full_id:
            continue
        amount_text = cost_amounts[idx] if idx < len(cost_amounts) else ""
        if not amount_text:
            continue
        try:
            amount_val = int(amount_text)
        except Exception:
            continue

        t, _, id_text = full_id.partition("-")
        cost_data = {
            "cost_type": t,
            "cost_amount": amount_val,
            "cost_relation": cost_relations[idx]
            if idx < len(cost_relations)
            else "and",
            "group_id": int(cost_groups[idx])
            if idx < len(cost_groups) and cost_groups[idx]
            else None,
            "quality_level": int(cost_quality_levels[idx])
            if idx < len(cost_quality_levels) and cost_quality_levels[idx]
            else 0,
        }

        if t in ("fish", "item", "rod", "accessory"):
            try:
                cost_data["cost_item_id"] = int(id_text)
            except Exception:
                continue

        shop_service.shop_repo.add_item_cost(item_id, cost_data)

    # 更新奖励（先删除旧的，再添加新的）
    rewards = shop_service.shop_repo.get_item_rewards(item_id)
    for reward in rewards:
        shop_service.shop_repo.delete_item_reward(reward["reward_id"])

    # 添加新奖励
    reward_full_ids = (
        data.getlist("reward_item_full_id") if hasattr(data, "getlist") else []
    )
    reward_quantities = (
        data.getlist("reward_quantity") if hasattr(data, "getlist") else []
    )
    reward_refine_levels = (
        data.getlist("reward_refine_level") if hasattr(data, "getlist") else []
    )
    reward_quality_levels = (
        data.getlist("reward_quality_level") if hasattr(data, "getlist") else []
    )

    for idx, full_id in enumerate(reward_full_ids):
        if not full_id:
            continue
        qty_text = reward_quantities[idx] if idx < len(reward_quantities) else "1"
        try:
            qty_val = int(qty_text or "1")
        except Exception:
            qty_val = 1

        t, _, id_text = full_id.partition("-")
        reward_data = {
            "reward_type": t,
            "reward_quantity": qty_val,
            "reward_refine_level": int(reward_refine_levels[idx])
            if idx < len(reward_refine_levels) and reward_refine_levels[idx]
            else None,
            "quality_level": int(reward_quality_levels[idx])
            if idx < len(reward_quality_levels) and reward_quality_levels[idx]
            else 0,
        }

        try:
            reward_data["reward_item_id"] = int(id_text)
        except Exception:
            continue

        shop_service.shop_repo.add_item_reward(item_id, reward_data)

    return redirect(url_for("admin_bp.manage_shop_details", shop_id=shop_id))


@admin_bp.route("/shops/<int:shop_id>/items/remove/<int:item_id>", methods=["POST"])
@login_required
async def remove_shop_item(shop_id, item_id):
    shop_service = current_app.config["SHOP_SERVICE"]

    # 删除商品（会自动删除相关的成本和奖励）
    shop_service.shop_repo.delete_shop_item(item_id)
    await flash("商品已删除", "success")

    return redirect(url_for("admin_bp.manage_shop_details", shop_id=shop_id))


@admin_bp.route("/api/shops/<int:shop_id>/items", methods=["POST"])
@login_required
async def api_add_shop_item(shop_id):
    payload = await request.get_json()
    shop_service = current_app.config["SHOP_SERVICE"]
    created = shop_service.shop_repo.create_shop_item(shop_id, payload or {})
    return jsonify({"success": True, "item": created})


@admin_bp.route("/api/shop/items/<int:item_id>", methods=["PUT"])
@login_required
async def api_update_shop_item(item_id):
    payload = await request.get_json()
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.update_shop_item(item_id, payload or {})
    return jsonify({"success": True})


@admin_bp.route("/api/shop/items/<int:item_id>", methods=["DELETE"])
@login_required
async def api_delete_shop_item(item_id):
    shop_service = current_app.config["SHOP_SERVICE"]
    shop_service.shop_repo.delete_shop_item(item_id)
    return jsonify({"success": True})


# 创建商品模板路由
@admin_bp.route("/offers/create", methods=["POST"])
@login_required
async def create_offer():
    """创建新的商品模板"""
    data = await request.form
    shop_service = current_app.config["SHOP_SERVICE"]

    try:
        # 解析表单数据
        offer_data = {
            "name": data.get("name"),
            "description": data.get("description"),
            "category": "general",  # 添加默认分类
            "is_active": data.get("is_active") == "on",
            "start_time": data.get("start_time") or None,
            "end_time": data.get("end_time") or None,
            "per_user_limit": int(data.get("per_user_limit"))
            if data.get("per_user_limit")
            else None,
            "per_user_daily_limit": int(data.get("per_user_daily_limit"))
            if data.get("per_user_daily_limit")
            else None,
            "stock_total": int(data.get("stock_total"))
            if data.get("stock_total")
            else None,
            "sort_order": int(data.get("sort_order", 100)),
        }

        # 解析成本
        costs = []
        cost_full_ids = (
            data.getlist("cost_item_full_id") if hasattr(data, "getlist") else []
        )
        cost_amounts = data.getlist("cost_amount") if hasattr(data, "getlist") else []
        for idx, full_id in enumerate(cost_full_ids):
            if not full_id:
                continue
            amount_text = cost_amounts[idx] if idx < len(cost_amounts) else ""
            if not amount_text:
                continue
            try:
                amount_val = int(amount_text)
            except Exception:
                continue
            t, _, id_text = full_id.partition("-")
            if t in ("coins", "premium"):
                costs.append({"cost_type": t, "item_id": None, "amount": amount_val})
            elif t in ("fish", "item"):
                try:
                    item_id_val = int(id_text)
                except Exception:
                    continue
                costs.append(
                    {"cost_type": t, "item_id": item_id_val, "amount": amount_val}
                )

        # 解析奖励
        rewards = []
        reward_item_types = data.getlist("reward_item_type")
        reward_item_ids = data.getlist("reward_item_id")
        reward_quantities = data.getlist("reward_quantity")
        reward_refine_levels = data.getlist("reward_refine_level")

        for i, item_type in enumerate(reward_item_types):
            if item_type and reward_item_ids[i] and reward_quantities[i]:
                reward_data = {
                    "item_type": item_type,
                    "item_id": int(reward_item_ids[i]),
                    "quantity": int(reward_quantities[i]),
                }
                if reward_refine_levels[i]:
                    reward_data["refine_level"] = int(reward_refine_levels[i])
                rewards.append(reward_data)

        # 创建商品
        offer = shop_service.shop_repo.create_offer(offer_data, costs)

        # 添加奖励
        for reward_data in rewards:
            shop_service.shop_repo.add_reward(offer.offer_id, reward_data)

        return redirect(url_for("admin_bp.manage_shops"))

    except Exception as e:
        logger.error(f"创建商品失败: {e}")
        return redirect(url_for("admin_bp.manage_shops"))


# --- 教程任務管理 ---
@admin_bp.route("/tutorial")
@login_required
@admin_required
async def manage_tutorial():
    tutorial_repo = current_app.config.get("TUTORIAL_REPO")
    if not tutorial_repo:
        await flash("教程服務未初始化", "danger")
        return redirect(url_for("admin_bp.index"))

    tasks = tutorial_repo.get_all_active_tasks()
    return await render_template("tutorial.html", tasks=tasks)


@admin_bp.route("/tutorial/add", methods=["POST"])
@login_required
@admin_required
async def add_tutorial_task():
    tutorial_repo = current_app.config.get("TUTORIAL_REPO")
    if not tutorial_repo:
        return jsonify({"success": False, "message": "教程服務未初始化"}), 500

    try:
        form = await request.form
        task_data = {
            "sequence": int(form.get("sequence", 0)),
            "category": form.get("category", "core"),
            "title": form.get("title", ""),
            "description": form.get("description", ""),
            "target_type": form.get("target_type", "command"),
            "target_value": int(form.get("target_value", 1)),
            "target_command": form.get("target_command") or None,
            "reward_coins": int(form.get("reward_coins", 0)),
            "reward_premium": int(form.get("reward_premium", 0)),
            "hint": form.get("hint") or None,
            "is_active": form.get("is_active") == "on",
        }

        with tutorial_repo._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tutorial_tasks
                    (sequence, category, title, description, target_type, target_value,
                     target_command, reward_coins, reward_premium, hint, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        task_data["sequence"],
                        task_data["category"],
                        task_data["title"],
                        task_data["description"],
                        task_data["target_type"],
                        task_data["target_value"],
                        task_data["target_command"],
                        task_data["reward_coins"],
                        task_data["reward_premium"],
                        task_data["hint"],
                        1 if task_data["is_active"] else 0,
                    ),
                )
                conn.commit()

        await flash("教程任務添加成功！", "success")
        return redirect(url_for("admin_bp.manage_tutorial"))

    except Exception as e:
        logger.error(f"添加教程任務失敗: {e}")
        await flash(f"添加失敗: {str(e)}", "danger")
        return redirect(url_for("admin_bp.manage_tutorial"))


@admin_bp.route("/tutorial/edit/<int:task_id>", methods=["POST"])
@login_required
@admin_required
async def edit_tutorial_task(task_id):
    tutorial_repo = current_app.config.get("TUTORIAL_REPO")
    if not tutorial_repo:
        return jsonify({"success": False, "message": "教程服務未初始化"}), 500

    try:
        form = await request.form
        task_data = {
            "sequence": int(form.get("sequence", 0)),
            "category": form.get("category", "core"),
            "title": form.get("title", ""),
            "description": form.get("description", ""),
            "target_type": form.get("target_type", "command"),
            "target_value": int(form.get("target_value", 1)),
            "target_command": form.get("target_command") or None,
            "reward_coins": int(form.get("reward_coins", 0)),
            "reward_premium": int(form.get("reward_premium", 0)),
            "hint": form.get("hint") or None,
            "is_active": form.get("is_active") == "on",
        }

        with tutorial_repo._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE tutorial_tasks SET
                    sequence = %s, category = %s, title = %s, description = %s,
                    target_type = %s, target_value = %s, target_command = %s,
                    reward_coins = %s, reward_premium = %s, hint = %s, is_active = %s
                    WHERE task_id = %s
                    """,
                    (
                        task_data["sequence"],
                        task_data["category"],
                        task_data["title"],
                        task_data["description"],
                        task_data["target_type"],
                        task_data["target_value"],
                        task_data["target_command"],
                        task_data["reward_coins"],
                        task_data["reward_premium"],
                        task_data["hint"],
                        1 if task_data["is_active"] else 0,
                        task_id,
                    ),
                )
                conn.commit()

        await flash(f"教程任務 ID {task_id} 更新成功！", "success")
        return redirect(url_for("admin_bp.manage_tutorial"))

    except Exception as e:
        logger.error(f"更新教程任務失敗: {e}")
        await flash(f"更新失敗: {str(e)}", "danger")
        return redirect(url_for("admin_bp.manage_tutorial"))


@admin_bp.route("/tutorial/delete/<int:task_id>", methods=["POST"])
@login_required
@admin_required
async def delete_tutorial_task(task_id):
    tutorial_repo = current_app.config.get("TUTORIAL_REPO")
    if not tutorial_repo:
        return jsonify({"success": False, "message": "教程服務未初始化"}), 500

    try:
        with tutorial_repo._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM tutorial_tasks WHERE task_id = %s", (task_id,)
                )
                conn.commit()

        await flash(f"教程任務 ID {task_id} 已刪除！", "success")
        return redirect(url_for("admin_bp.manage_tutorial"))

    except Exception as e:
        logger.error(f"刪除教程任務失敗: {e}")
        await flash(f"刪除失敗: {str(e)}", "danger")
        return redirect(url_for("admin_bp.manage_tutorial"))


@admin_bp.route("/tutorial/user/<user_id>")
@login_required
@admin_required
async def get_user_tutorial_progress(user_id):
    tutorial_repo = current_app.config.get("TUTORIAL_REPO")
    if not tutorial_repo:
        return jsonify({"success": False, "message": "教程服務未初始化"}), 500

    try:
        tasks = tutorial_repo.get_all_active_tasks()
        progress_list = tutorial_repo.get_user_progress(user_id)
        progress_map = {p.task_id: p for p in progress_list}

        task_status = []
        for task in tasks:
            progress = progress_map.get(task.task_id)
            task_status.append(
                {
                    "task_id": task.task_id,
                    "sequence": task.sequence,
                    "category": task.category,
                    "title": task.title,
                    "target_type": task.target_type,
                    "target_value": task.target_value,
                    "current_progress": progress.current_progress if progress else 0,
                    "is_completed": progress.is_completed if progress else False,
                    "reward_claimed": progress.reward_claimed if progress else False,
                }
            )

        completion = tutorial_repo.get_completion_rate(user_id)

        return jsonify(
            {
                "success": True,
                "tasks": task_status,
                "completion_rate": completion["rate"],
                "total_tasks": completion["total"],
                "completed_tasks": completion["completed"],
            }
        )

    except Exception as e:
        logger.error(f"獲取用戶教程進度失敗: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/tutorial/user/<user_id>/reset", methods=["POST"])
@login_required
@admin_required
async def reset_user_tutorial_progress(user_id):
    tutorial_repo = current_repo = current_app.config.get("TUTORIAL_REPO")
    if not tutorial_repo:
        return jsonify({"success": False, "message": "教程服務未初始化"}), 500

    try:
        with tutorial_repo._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_tutorial_progress WHERE user_id = %s", (user_id,)
                )
                conn.commit()

        return jsonify({"success": True, "message": f"用戶 {user_id} 的教程進度已重置"})

    except Exception as e:
        logger.error(f"重置用戶教程進度失敗: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/tutorial/user/<user_id>/complete/<int:task_id>", methods=["POST"])
@login_required
@admin_required
async def admin_complete_tutorial_task(user_id, task_id):
    tutorial_repo = current_app.config.get("TUTORIAL_REPO")
    if not tutorial_repo:
        return jsonify({"success": False, "message": "教程服務未初始化"}), 500

    try:
        tutorial_repo.complete_task(user_id, task_id)
        return jsonify({"success": True, "message": f"任務 {task_id} 已標記為完成"})

    except Exception as e:
        logger.error(f"標記任務完成失敗: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/tutorial/stats")
@login_required
@admin_required
async def get_tutorial_stats():
    tutorial_repo = current_app.config.get("TUTORIAL_REPO")
    if not tutorial_repo:
        return jsonify({"success": False, "message": "教程服務未初始化"}), 500

    try:
        tasks = tutorial_repo.get_all_active_tasks()
        total_tasks = len(tasks)

        with tutorial_repo._connection_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id, COUNT(*) as completed_count
                    FROM user_tutorial_progress
                    WHERE is_completed = 1
                    GROUP BY task_id
                    """
                )
                completion_stats = {
                    row["task_id"]: row["completed_count"] for row in cursor.fetchall()
                }

                cursor.execute(
                    "SELECT COUNT(DISTINCT user_id) as total_users FROM user_tutorial_progress"
                )
                total_users = cursor.fetchone()["total_users"]

        task_stats = []
        for task in tasks:
            task_stats.append(
                {
                    "task_id": task.task_id,
                    "sequence": task.sequence,
                    "title": task.title,
                    "category": task.category,
                    "completed_count": completion_stats.get(task.task_id, 0),
                }
            )

        return jsonify(
            {
                "success": True,
                "total_tasks": total_tasks,
                "total_users": total_users,
                "task_stats": task_stats,
            }
        )

    except Exception as e:
        logger.error(f"獲取教程統計失敗: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# 旧の商品管理API路由已移除，功能已集成到商店详情页面


# ===== 成就系統管理 =====
@admin_bp.route("/achievements")
@login_required
@admin_required
async def manage_achievements():
    achievement_service = current_app.config.get("ACHIEVEMENT_SERVICE")
    user_service = current_app.config["USER_SERVICE"]

    if not achievement_service:
        await flash("成就服務未初始化", "danger")
        return redirect(url_for("admin_bp.index"))

    achievements = achievement_service.achievements
    achievements_data = []
    for ach in achievements:
        achievements_data.append(
            {
                "id": ach.id,
                "name": ach.name,
                "description": ach.description,
                "target_type": getattr(ach, "target_type", "custom"),
                "target_value": getattr(ach, "target_value", 0),
                "reward": getattr(ach, "reward", None),
            }
        )

    with (
        achievement_service.achievement_repo._connection_manager.get_connection() as conn
    ):
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.achievement_id, a.name, 
                       COUNT(uap.user_id) as completed_count
                FROM achievements a
                LEFT JOIN user_achievement_progress uap 
                    ON a.achievement_id = uap.achievement_id 
                    AND uap.completed_at IS NOT NULL
                GROUP BY a.achievement_id, a.name
                """
            )
            completion_stats = {
                row["achievement_id"]: row["completed_count"]
                for row in cursor.fetchall()
            }

    for ach in achievements_data:
        ach["completed_count"] = completion_stats.get(ach["id"], 0)

    return await render_template("achievements.html", achievements=achievements_data)


@admin_bp.route("/achievements/<int:achievement_id>/users")
@login_required
@admin_required
async def get_achievement_users(achievement_id):
    achievement_service = current_app.config.get("ACHIEVEMENT_SERVICE")
    if not achievement_service:
        return jsonify({"success": False, "message": "成就服務未初始化"}), 500

    page = int(request.args.get("page", 1))
    per_page = 20

    with (
        achievement_service.achievement_repo._connection_manager.get_connection() as conn
    ):
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.user_id, u.nickname, uap.completed_at, uap.current_progress
                FROM user_achievement_progress uap
                JOIN users u ON uap.user_id = u.user_id
                WHERE uap.achievement_id = %s
                ORDER BY uap.completed_at DESC
                LIMIT %s OFFSET %s
                """,
                (achievement_id, per_page, (page - 1) * per_page),
            )
            users = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(*) as total FROM user_achievement_progress WHERE achievement_id = %s",
                (achievement_id,),
            )
            total = cursor.fetchone()["total"]

    return jsonify(
        {
            "success": True,
            "users": users,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
        }
    )


@admin_bp.route("/achievements/grant", methods=["POST"])
@login_required
@admin_required
async def grant_achievement_to_user():
    achievement_service = current_app.config.get("ACHIEVEMENT_SERVICE")
    if not achievement_service:
        return jsonify({"success": False, "message": "成就服務未初始化"}), 500

    data = await request.get_json()
    user_id = data.get("user_id")
    achievement_id = data.get("achievement_id")

    if not user_id or not achievement_id:
        return jsonify({"success": False, "message": "缺少參數"}), 400

    user = achievement_service.user_repo.get_by_id(user_id)
    if not user:
        return jsonify({"success": False, "message": "用戶不存在"}), 404

    ach = None
    for a in achievement_service.achievements:
        if a.id == achievement_id:
            ach = a
            break

    if not ach:
        return jsonify({"success": False, "message": "成就不存在"}), 404

    achievement_service.achievement_repo.update_user_progress(
        user_id, achievement_id, ach.target_value, datetime.now()
    )

    if ach.reward:
        achievement_service._grant_reward(user, ach)

    return jsonify(
        {"success": True, "message": f"已為用戶 {user_id} 授予成就 {ach.name}"}
    )


@admin_bp.route("/achievements/revoke", methods=["POST"])
@login_required
@admin_required
async def revoke_achievement_from_user():
    achievement_service = current_app.config.get("ACHIEVEMENT_SERVICE")
    if not achievement_service:
        return jsonify({"success": False, "message": "成就服務未初始化"}), 500

    data = await request.get_json()
    user_id = data.get("user_id")
    achievement_id = data.get("achievement_id")

    if not user_id or not achievement_id:
        return jsonify({"success": False, "message": "缺少參數"}), 400

    with (
        achievement_service.achievement_repo._connection_manager.get_connection() as conn
    ):
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM user_achievement_progress WHERE user_id = %s AND achievement_id = %s",
                (user_id, achievement_id),
            )
            conn.commit()

    return jsonify({"success": True, "message": "已撤銷成就"})


@admin_bp.route("/achievements/user/<user_id>")
@login_required
@admin_required
async def get_user_achievements_api(user_id):
    achievement_service = current_app.config.get("ACHIEVEMENT_SERVICE")
    if not achievement_service:
        return jsonify({"success": False, "message": "成就服務未初始化"}), 500

    result = achievement_service.get_user_achievements(user_id)
    return jsonify(result)


# ===== 公會系統管理 =====
@admin_bp.route("/guilds")
@login_required
@admin_required
async def manage_guilds():
    guild_service = current_app.config.get("GUILD_SERVICE")
    if not guild_service:
        await flash("公會服務未初始化", "danger")
        return redirect(url_for("admin_bp.index"))

    page = int(request.args.get("page", 1))
    per_page = 20
    search = request.args.get("search", "")

    with guild_service.guild_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            if search:
                cursor.execute(
                    """
                    SELECT SQL_CALC_FOUND_ROWS g.*, 
                           (SELECT COUNT(*) FROM guild_members gm WHERE gm.guild_id = g.guild_id) as member_count
                    FROM guilds g
                    WHERE g.name LIKE %s OR g.description LIKE %s
                    ORDER BY g.level DESC, g.exp DESC
                    LIMIT %s OFFSET %s
                    """,
                    (f"%{search}%", f"%{search}%", per_page, (page - 1) * per_page),
                )
            else:
                cursor.execute(
                    """
                    SELECT SQL_CALC_FOUND_ROWS g.*,
                           (SELECT COUNT(*) FROM guild_members gm WHERE gm.guild_id = g.guild_id) as member_count
                    FROM guilds g
                    ORDER BY g.level DESC, g.exp DESC
                    LIMIT %s OFFSET %s
                    """,
                    (per_page, (page - 1) * per_page),
                )
            guilds = cursor.fetchall()

            cursor.execute("SELECT FOUND_ROWS() as total")
            total = cursor.fetchone()["total"]

    return await render_template(
        "guilds.html",
        guilds=guilds,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
        search=search,
    )


@admin_bp.route("/guilds/<int:guild_id>")
@login_required
@admin_required
async def get_guild_details(guild_id):
    guild_service = current_app.config.get("GUILD_SERVICE")
    if not guild_service:
        return jsonify({"success": False, "message": "公會服務未初始化"}), 500

    with guild_service.guild_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM guilds WHERE guild_id = %s", (guild_id,))
            guild = cursor.fetchone()

            if not guild:
                return jsonify({"success": False, "message": "公會不存在"}), 404

            cursor.execute(
                """
                SELECT gm.*, u.nickname
                FROM guild_members gm
                JOIN users u ON gm.user_id = u.user_id
                WHERE gm.guild_id = %s
                ORDER BY gm.is_leader DESC, gm.is_officer DESC, gm.total_contribution DESC
                """,
                (guild_id,),
            )
            members = cursor.fetchall()

            cursor.execute(
                "SELECT * FROM guild_buffs WHERE guild_id = %s AND expires_at > NOW()",
                (guild_id,),
            )
            buffs = cursor.fetchall()

    return jsonify(
        {
            "success": True,
            "guild": guild,
            "members": members,
            "buffs": buffs,
        }
    )


@admin_bp.route("/guilds/<int:guild_id>/kick/<user_id>", methods=["POST"])
@login_required
@admin_required
async def admin_kick_guild_member(guild_id, user_id):
    guild_service = current_app.config.get("GUILD_SERVICE")
    if not guild_service:
        return jsonify({"success": False, "message": "公會服務未初始化"}), 500

    with guild_service.guild_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM guild_members WHERE guild_id = %s AND user_id = %s",
                (guild_id, user_id),
            )
            conn.commit()

    return jsonify({"success": True, "message": "已將成員踢出公會"})


@admin_bp.route("/guilds/<int:guild_id>/transfer/<new_leader_id>", methods=["POST"])
@login_required
@admin_required
async def admin_transfer_guild_leader(guild_id, new_leader_id):
    guild_service = current_app.config.get("GUILD_SERVICE")
    if not guild_service:
        return jsonify({"success": False, "message": "公會服務未初始化"}), 500

    with guild_service.guild_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE guild_members SET is_leader = 0 WHERE guild_id = %s",
                (guild_id,),
            )
            cursor.execute(
                "UPDATE guild_members SET is_leader = 1, is_officer = 1 WHERE guild_id = %s AND user_id = %s",
                (guild_id, new_leader_id),
            )
            cursor.execute(
                "UPDATE guilds SET leader_id = %s WHERE guild_id = %s",
                (new_leader_id, guild_id),
            )
            conn.commit()

    return jsonify({"success": True, "message": "已轉讓會長"})


@admin_bp.route("/guilds/<int:guild_id>/disband", methods=["POST"])
@login_required
@admin_required
async def admin_disband_guild(guild_id):
    guild_service = current_app.config.get("GUILD_SERVICE")
    if not guild_service:
        return jsonify({"success": False, "message": "公會服務未初始化"}), 500

    with guild_service.guild_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM guild_members WHERE guild_id = %s", (guild_id,))
            cursor.execute("DELETE FROM guild_buffs WHERE guild_id = %s", (guild_id,))
            cursor.execute("DELETE FROM guilds WHERE guild_id = %s", (guild_id,))
            conn.commit()

    return jsonify({"success": True, "message": "公會已解散"})


@admin_bp.route("/guilds/<int:guild_id>/buffs/clear", methods=["POST"])
@login_required
@admin_required
async def admin_clear_guild_buffs(guild_id):
    guild_service = current_app.config.get("GUILD_SERVICE")
    if not guild_service:
        return jsonify({"success": False, "message": "公會服務未初始化"}), 500

    with guild_service.guild_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM guild_buffs WHERE guild_id = %s", (guild_id,))
            conn.commit()

    return jsonify({"success": True, "message": "已清除公會 Buff"})


# ===== 用戶 Buff 管理 =====
@admin_bp.route("/users/<user_id>/buffs")
@login_required
@admin_required
async def get_user_buffs(user_id):
    user_service = current_app.config["USER_SERVICE"]
    buff_repo = current_app.config.get("BUFF_REPO")

    if not buff_repo:
        return jsonify({"success": False, "message": "Buff 服務未初始化"}), 500

    buffs = buff_repo.get_all_active_by_user(user_id)
    buffs_data = []
    for buff in buffs:
        buffs_data.append(
            {
                "id": buff.id,
                "user_id": buff.user_id,
                "buff_type": buff.buff_type,
                "payload": buff.payload,
                "started_at": buff.started_at.isoformat() if buff.started_at else None,
                "expires_at": buff.expires_at.isoformat() if buff.expires_at else None,
            }
        )

    return jsonify({"success": True, "buffs": buffs_data})


@admin_bp.route("/users/<user_id>/buffs/add", methods=["POST"])
@login_required
@admin_required
async def add_user_buff(user_id):
    buff_repo = current_app.config.get("BUFF_REPO")
    if not buff_repo:
        return jsonify({"success": False, "message": "Buff 服務未初始化"}), 500

    data = await request.get_json()
    buff_type = data.get("buff_type")
    payload = data.get("payload", "{}")
    duration_hours = data.get("duration_hours", 24)

    if not buff_type:
        return jsonify({"success": False, "message": "缺少 buff_type"}), 400

    from ..core.domain.models import UserBuff

    expires_at = datetime.now() + timedelta(hours=duration_hours)
    buff = UserBuff(
        id=0,
        user_id=user_id,
        buff_type=buff_type,
        payload=payload if isinstance(payload, str) else json.dumps(payload),
        started_at=datetime.now(),
        expires_at=expires_at,
    )

    buff_repo.add(buff)

    return jsonify({"success": True, "message": f"已添加 Buff: {buff_type}"})


@admin_bp.route("/users/<user_id>/buffs/<int:buff_id>/remove", methods=["POST"])
@login_required
@admin_required
async def remove_user_buff(user_id, buff_id):
    buff_repo = current_app.config.get("BUFF_REPO")
    if not buff_repo:
        return jsonify({"success": False, "message": "Buff 服務未初始化"}), 500

    with buff_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM user_buffs WHERE id = %s AND user_id = %s",
                (buff_id, user_id),
            )
            conn.commit()

    return jsonify({"success": True, "message": "已移除 Buff"})


# ===== 紅包系統管理 =====
@admin_bp.route("/redpackets")
@login_required
@admin_required
async def manage_redpackets():
    red_packet_service = current_app.config.get("RED_PACKET_SERVICE")
    if not red_packet_service:
        await flash("紅包服務未初始化", "danger")
        return redirect(url_for("admin_bp.index"))

    page = int(request.args.get("page", 1))
    status = request.args.get("status", "active")
    per_page = 20

    with (
        red_packet_service.red_packet_repo._connection_manager.get_connection() as conn
    ):
        with conn.cursor() as cursor:
            if status == "active":
                cursor.execute(
                    """
                    SELECT SQL_CALC_FOUND_ROWS rp.*, u.nickname as sender_name,
                           (SELECT COUNT(*) FROM red_packet_claims rpc WHERE rpc.packet_id = rp.packet_id) as claimed_count
                    FROM red_packets rp
                    JOIN users u ON rp.sender_id = u.user_id
                    WHERE rp.expires_at > NOW() AND rp.remaining_count > 0
                    ORDER BY rp.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (per_page, (page - 1) * per_page),
                )
            elif status == "expired":
                cursor.execute(
                    """
                    SELECT SQL_CALC_FOUND_ROWS rp.*, u.nickname as sender_name,
                           (SELECT COUNT(*) FROM red_packet_claims rpc WHERE rpc.packet_id = rp.packet_id) as claimed_count
                    FROM red_packets rp
                    JOIN users u ON rp.sender_id = u.user_id
                    WHERE rp.expires_at <= NOW() OR rp.remaining_count <= 0
                    ORDER BY rp.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (per_page, (page - 1) * per_page),
                )
            else:
                cursor.execute(
                    """
                    SELECT SQL_CALC_FOUND_ROWS rp.*, u.nickname as sender_name,
                           (SELECT COUNT(*) FROM red_packet_claims rpc WHERE rpc.packet_id = rp.packet_id) as claimed_count
                    FROM red_packets rp
                    JOIN users u ON rp.sender_id = u.user_id
                    ORDER BY rp.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (per_page, (page - 1) * per_page),
                )

            packets = cursor.fetchall()
            cursor.execute("SELECT FOUND_ROWS() as total")
            total = cursor.fetchone()["total"]

    return await render_template(
        "redpackets.html",
        packets=packets,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
        status=status,
    )


@admin_bp.route("/redpackets/<int:packet_id>/claims")
@login_required
@admin_required
async def get_redpacket_claims(packet_id):
    red_packet_service = current_app.config.get("RED_PACKET_SERVICE")
    if not red_packet_service:
        return jsonify({"success": False, "message": "紅包服務未初始化"}), 500

    with (
        red_packet_service.red_packet_repo._connection_manager.get_connection() as conn
    ):
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT rpc.*, u.nickname
                FROM red_packet_claims rpc
                JOIN users u ON rpc.user_id = u.user_id
                WHERE rpc.packet_id = %s
                ORDER BY rpc.claimed_at DESC
                """,
                (packet_id,),
            )
            claims = cursor.fetchall()

    return jsonify({"success": True, "claims": claims})


@admin_bp.route("/redpackets/<int:packet_id>/revoke", methods=["POST"])
@login_required
@admin_required
async def admin_revoke_redpacket(packet_id):
    red_packet_service = current_app.config.get("RED_PACKET_SERVICE")
    if not red_packet_service:
        return jsonify({"success": False, "message": "紅包服務未初始化"}), 500

    with (
        red_packet_service.red_packet_repo._connection_manager.get_connection() as conn
    ):
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM red_packets WHERE packet_id = %s",
                (packet_id,),
            )
            packet = cursor.fetchone()

            if not packet:
                return jsonify({"success": False, "message": "紅包不存在"}), 404

            remaining_amount = packet["remaining_count"] * packet["amount_per_packet"]

            cursor.execute(
                "UPDATE users SET coins = coins + %s WHERE user_id = %s",
                (remaining_amount, packet["sender_id"]),
            )

            cursor.execute(
                "UPDATE red_packets SET remaining_count = 0 WHERE packet_id = %s",
                (packet_id,),
            )
            conn.commit()

    return jsonify(
        {"success": True, "message": f"紅包已撤銷，已返還 {remaining_amount} 金幣"}
    )


@admin_bp.route("/redpackets/cleanup", methods=["POST"])
@login_required
@admin_required
async def admin_cleanup_redpackets():
    red_packet_service = current_app.config.get("RED_PACKET_SERVICE")
    if not red_packet_service:
        return jsonify({"success": False, "message": "紅包服務未初始化"}), 500

    deleted = red_packet_service.cleanup_expired_packets()
    return jsonify({"success": True, "message": f"已清理 {deleted} 個過期紅包"})


# ===== 骰寶賭場管理 =====
@admin_bp.route("/sicbo")
@login_required
@admin_required
async def manage_sicbo():
    return await render_template("sicbo.html")


@admin_bp.route("/sicbo/stats")
@login_required
@admin_required
async def get_sicbo_stats():
    sicbo_service = current_app.config.get("SICBO_SERVICE")
    if not sicbo_service:
        return jsonify({"success": False, "message": "骰寶服務未初始化"}), 500

    active_games = []
    for session_id, game in sicbo_service.games.items():
        active_games.append(
            {
                "session_id": session_id,
                "game_id": game.game_id,
                "start_time": game.start_time.isoformat() if game.start_time else None,
                "end_time": game.end_time.isoformat() if game.end_time else None,
                "total_pot": game.total_pot,
                "bet_count": len(game.bets),
                "is_active": game.is_active,
                "is_settled": game.is_settled,
            }
        )

    with sicbo_service.log_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DATE(created_at) as date,
                       COUNT(*) as total_games,
                       SUM(CASE WHEN result > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN result < 0 THEN 1 ELSE 0 END) as losses,
                       SUM(result) as net_result
                FROM fishing_logs
                WHERE action = 'sicbo_bet' AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                """
            )
            daily_stats = cursor.fetchall()

            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id) as total_players,
                       SUM(CASE WHEN result > 0 THEN 1 ELSE 0 END) as total_wins,
                       SUM(CASE WHEN result < 0 THEN 1 ELSE 0 END) as total_losses,
                       SUM(ABS(result)) as total_volume
                FROM fishing_logs
                WHERE action = 'sicbo_bet' AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                """
            )
            monthly_summary = cursor.fetchone()

    return jsonify(
        {
            "success": True,
            "active_games": active_games,
            "daily_stats": daily_stats,
            "monthly_summary": monthly_summary,
            "config": {
                "countdown_seconds": sicbo_service.countdown_seconds,
                "min_bet": sicbo_service.min_bet,
                "max_bet": sicbo_service.max_bet,
                "message_mode": sicbo_service.message_mode,
            },
        }
    )


@admin_bp.route("/sicbo/config", methods=["POST"])
@login_required
@admin_required
async def update_sicbo_config():
    sicbo_service = current_app.config.get("SICBO_SERVICE")
    if not sicbo_service:
        return jsonify({"success": False, "message": "骰寶服務未初始化"}), 500

    data = await request.get_json()

    if "countdown_seconds" in data:
        sicbo_service.countdown_seconds = int(data["countdown_seconds"])
    if "min_bet" in data:
        sicbo_service.min_bet = int(data["min_bet"])
    if "max_bet" in data:
        sicbo_service.max_bet = int(data["max_bet"])
    if "message_mode" in data:
        sicbo_service.message_mode = data["message_mode"]

    return jsonify({"success": True, "message": "配置已更新"})


@admin_bp.route("/sicbo/force-settle/<session_id>", methods=["POST"])
@login_required
@admin_required
async def admin_force_settle_sicbo(session_id):
    sicbo_service = current_app.config.get("SICBO_SERVICE")
    if not sicbo_service:
        return jsonify({"success": False, "message": "骰寶服務未初始化"}), 500

    if session_id not in sicbo_service.games:
        return jsonify({"success": False, "message": "遊戲不存在"}), 404

    game = sicbo_service.games[session_id]
    if game.is_settled:
        return jsonify({"success": False, "message": "遊戲已結算"}), 400

    dice = [random.randint(1, 6) for _ in range(3)]

    result = sicbo_service._settle_game(session_id, dice)

    return jsonify(
        {
            "success": True,
            "message": "強制結算完成",
            "dice": dice,
            "result": result,
        }
    )


# ===== 通行證管理 =====
@admin_bp.route("/passes")
@login_required
@admin_required
async def manage_passes():
    user_service = current_app.config["USER_SERVICE"]

    page = int(request.args.get("page", 1))
    zone_id = request.args.get("zone_id", "")
    per_page = 20

    with user_service.user_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            if zone_id:
                cursor.execute(
                    """
                    SELECT SQL_CALC_FOUND_ROWS u.user_id, u.nickname, u.zone_pass_expires_at, 
                           fz.name as zone_name, fz.id as zone_id
                    FROM users u
                    JOIN fishing_zones fz ON u.fishing_zone_id = fz.id
                    WHERE u.zone_pass_expires_at IS NOT NULL AND u.fishing_zone_id = %s
                    ORDER BY u.zone_pass_expires_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (zone_id, per_page, (page - 1) * per_page),
                )
            else:
                cursor.execute(
                    """
                    SELECT SQL_CALC_FOUND_ROWS u.user_id, u.nickname, u.zone_pass_expires_at,
                           fz.name as zone_name, fz.id as zone_id
                    FROM users u
                    LEFT JOIN fishing_zones fz ON u.fishing_zone_id = fz.id
                    WHERE u.zone_pass_expires_at IS NOT NULL
                    ORDER BY u.zone_pass_expires_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (per_page, (page - 1) * per_page),
                )
            users = cursor.fetchall()
            cursor.execute("SELECT FOUND_ROWS() as total")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT id, name FROM fishing_zones WHERE requires_pass = 1")
            zones = cursor.fetchall()

    return await render_template(
        "passes.html",
        users=users,
        zones=zones,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
        zone_id=zone_id,
    )


@admin_bp.route("/passes/grant", methods=["POST"])
@login_required
@admin_required
async def grant_zone_pass():
    user_service = current_app.config["USER_SERVICE"]

    data = await request.get_json()
    user_id = data.get("user_id")
    duration_hours = data.get("duration_hours", 24)

    if not user_id:
        return jsonify({"success": False, "message": "缺少 user_id"}), 400

    with user_service.user_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
            cursor.execute(
                "UPDATE users SET zone_pass_expires_at = %s WHERE user_id = %s",
                (expires_at, user_id),
            )
            conn.commit()

    return jsonify({"success": True, "message": f"已授予 {duration_hours} 小時通行證"})


@admin_bp.route("/passes/revoke", methods=["POST"])
@login_required
@admin_required
async def revoke_zone_pass():
    user_service = current_app.config["USER_SERVICE"]

    data = await request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"success": False, "message": "缺少 user_id"}), 400

    with user_service.user_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET zone_pass_expires_at = NULL WHERE user_id = %s",
                (user_id,),
            )
            conn.commit()

    return jsonify({"success": True, "message": "已撤銷通行證"})


@admin_bp.route("/passes/batch-grant", methods=["POST"])
@login_required
@admin_required
async def batch_grant_zone_pass():
    user_service = current_app.config["USER_SERVICE"]

    data = await request.get_json()
    user_ids = data.get("user_ids", [])
    duration_hours = data.get("duration_hours", 24)

    if not user_ids:
        return jsonify({"success": False, "message": "缺少 user_ids"}), 400

    expires_at = datetime.now() + timedelta(hours=duration_hours)
    updated = 0

    with user_service.user_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            for user_id in user_ids:
                cursor.execute(
                    "UPDATE users SET zone_pass_expires_at = %s WHERE user_id = %s",
                    (expires_at, user_id),
                )
                updated += 1
            conn.commit()

    return jsonify({"success": True, "message": f"已為 {updated} 位用戶授予通行證"})


# ===== 數據統計儀表板 =====
@admin_bp.route("/dashboard/stats")
@login_required
@admin_required
async def get_dashboard_stats():
    user_service = current_app.config["USER_SERVICE"]
    market_service = current_app.config["MARKET_SERVICE"]

    with user_service.user_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DATE(created_at) as date, COUNT(*) as new_users
                FROM users
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY DATE(created_at)
                ORDER BY date
                """
            )
            user_growth = cursor.fetchall()

            cursor.execute("SELECT SUM(coins) as total_coins FROM users")
            total_coins = cursor.fetchone()["total_coins"] or 0

            cursor.execute(
                """
                SELECT DATE(created_at) as date, SUM(amount) as total_volume
                FROM fishing_logs
                WHERE action IN ('sell_fish', 'buy_item', 'market_buy') 
                  AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at)
                ORDER BY date
                """
            )
            economy_volume = cursor.fetchall()

            cursor.execute(
                """
                SELECT f.name, COUNT(*) as catch_count
                FROM fishing_records fr
                JOIN fish f ON fr.fish_id = f.fish_id
                WHERE fr.caught_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY f.name
                ORDER BY catch_count DESC
                LIMIT 10
                """
            )
            top_fish = cursor.fetchall()

            cursor.execute(
                """
                SELECT u.nickname, u.coins, u.premium_currency, u.total_fishing_count
                FROM users u
                ORDER BY u.coins DESC
                LIMIT 10
                """
            )
            top_players = cursor.fetchall()

    return jsonify(
        {
            "success": True,
            "user_growth": user_growth,
            "total_coins": total_coins,
            "economy_volume": economy_volume,
            "top_fish": top_fish,
            "top_players": top_players,
        }
    )


# ===== 操作日誌 =====
@admin_bp.route("/logs")
@login_required
@admin_required
async def manage_logs():
    log_repo = current_app.config.get("LOG_REPO")

    if not log_repo:
        await flash("日誌服務未初始化", "danger")
        return redirect(url_for("admin_bp.index"))

    page = int(request.args.get("page", 1))
    action = request.args.get("action", "")
    user_id = request.args.get("user_id", "")
    per_page = 50

    with log_repo._connection_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            conditions = ["1=1"]
            params = []

            if action:
                conditions.append("action = %s")
                params.append(action)
            if user_id:
                conditions.append("user_id = %s")
                params.append(user_id)

            where_clause = " AND ".join(conditions)

            cursor.execute(
                f"""
                SELECT SQL_CALC_FOUND_ROWS fl.*, u.nickname
                FROM fishing_logs fl
                LEFT JOIN users u ON fl.user_id = u.user_id
                WHERE {where_clause}
                ORDER BY fl.created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [per_page, (page - 1) * per_page],
            )
            logs = cursor.fetchall()
            cursor.execute("SELECT FOUND_ROWS() as total")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT DISTINCT action FROM fishing_logs ORDER BY action")
            actions = [row["action"] for row in cursor.fetchall()]

    return await render_template(
        "logs.html",
        logs=logs,
        actions=actions,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
        action=action,
        user_id=user_id,
    )
