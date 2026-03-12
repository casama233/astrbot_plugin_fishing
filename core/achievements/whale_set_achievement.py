from .base import BaseAchievement, UserContext


class WhaleSetCollected(BaseAchievement):
    id = 60
    name = "震鯨了！"
    description = "集齊鯨落三件套（魚竿+飾品+魚餌）"
    target_value = 1
    reward = ("title", 34, 1)

    def get_progress(self, context: UserContext) -> int:
        whale_rod = "鯨落·巨脊長竿"
        whale_accessory = "鯨落·深渊祈珂"
        whale_bait = "鯨落·災潮誘餌"
        user = context.user
        if not hasattr(user, "user_id"):
            return 0
        return getattr(context, "whale_set_complete", 0)

    def check(self, context: UserContext) -> bool:
        return self.get_progress(context) >= 1
