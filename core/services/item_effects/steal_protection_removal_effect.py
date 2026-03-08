from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item


class StealProtectionRemovalEffect(AbstractItemEffect):
    effect_type = "STEAL_PROTECTION_REMOVAL"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1, target_user_id: str = None
    ) -> Dict[str, Any]:
        """
        驅靈香效果：用於驅散目標玩家的海靈守護效果。
        命令使用：/使用 D短碼 @目標用戶 或 /驅靈 @目標用戶
        """
        # 檢查是否提供了目標用戶ID
        if not target_user_id:
            return {
                "success": False, 
                "message": "請指定要驅散守護的目標用戶！\n用法：/使用 D短碼 @目標用戶 或 /驅靈 @目標用戶"
            }
        
        # 檢查是否對自己使用
        if str(target_user_id) == str(user.user_id):
            return {"success": False, "message": "不能對自己使用驅靈香哦！"}
        
        # 檢查目標用戶是否存在
        target_user = self.user_repo.get_by_id(target_user_id)
        if not target_user:
            return {"success": False, "message": f"目標用戶 {target_user_id} 不存在！"}
        
        # 嘗試驅散
        result = self.game_mechanics_service.dispel_steal_protection(target_user_id)
        
        if result.get("success"):
            return {
                "success": True,
                "message": result.get("message", "成功驅散了目標的海靈守護！")
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "驅散失敗！")
            }
