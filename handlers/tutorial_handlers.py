from astrbot.api.event import AstrMessageEvent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def view_tutorial(self: "FishingPlugin", event: AstrMessageEvent):
    """查看教程任務"""
    user_id = self._get_effective_user_id(event)

    if not self.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    display = self.tutorial_service.format_tutorial_display(user_id)
    yield event.plain_result(display)


async def claim_tutorial_reward(self: "FishingPlugin", event: AstrMessageEvent):
    """領取教程獎勵"""
    user_id = self._get_effective_user_id(event)

    if not self.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    args = event.message_str.strip().split()
    if len(args) >= 3:
        try:
            task_id = int(args[2])
            result = self.tutorial_service.claim_task_reward(user_id, task_id)
        except ValueError:
            result = self.tutorial_service.claim_all_rewards(user_id)
    else:
        result = self.tutorial_service.claim_all_rewards(user_id)

    yield event.plain_result(result["message"])


async def get_tutorial_hint(self: "FishingPlugin", event: AstrMessageEvent):
    """獲取當前任務提示"""
    user_id = self._get_effective_user_id(event)

    if not self.user_repo.check_exists(user_id):
        yield event.plain_result("❌ 請先使用 /註冊 開始遊戲！")
        return

    hint = self.tutorial_service.get_task_hint(user_id)
    yield event.plain_result(hint)


async def tutorial_dispatch(self: "FishingPlugin", event: AstrMessageEvent):
    """教程指令分發"""
    parts = event.message_str.strip().split()

    if len(parts) == 1:
        async for r in view_tutorial(self, event):
            yield r
        return

    sub_cmd = parts[1].lower() if len(parts) > 1 else ""

    if sub_cmd in ["領取", "領獎", "領取獎勵", "claim"]:
        async for r in claim_tutorial_reward(self, event):
            yield r
    elif sub_cmd in ["提示", "hint", "下一步"]:
        async for r in get_tutorial_hint(self, event):
            yield r
    else:
        async for r in view_tutorial(self, event):
            yield r
