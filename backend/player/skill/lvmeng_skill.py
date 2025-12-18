from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from config.enums import GameEvent

if TYPE_CHECKING:
    from backend.player.player import Player


class KeJiSkill:
    """吕蒙：克己

    弃牌阶段开始前，若你本回合未使用或打出过【杀】，你可跳过此阶段。
    （在当前引擎里，我们用 sha_used_this_turn 近似“本回合用/打出过杀”。）
    """

    name: str = "克己"
    is_locked: bool = False
    need_ask: bool = True

    def should_skip_phase(self, player: "Player", event_type: GameEvent, context: Dict[str, Any]) -> bool:
        """判断是否因【克己】跳过某阶段。

        Args:
            player: 玩家对象。
            event_type: 当前阶段事件类型。
            context: 阶段上下文。

        Returns:
            bool: 是否跳过该阶段。
        """
        # 只管弃牌阶段
        if event_type != GameEvent.DISCARD_CARD:
            return False

        # 本回合用过杀 → 克己失效
        if getattr(player, "sha_used_this_turn", False):
            return False

        # 本回合没用过杀 → 问是否发动克己
        return player.ask_activate_skill(self.name, context)

    def can_activate(self, player: "Player", context: Dict[str, Any]) -> bool:
        """克己走阶段跳过钩子，不通过 trigger_skills 显式触发。

        Args:
            player: 玩家对象。
            context: 上下文。

        Returns:
            bool: False
        """
        return False

    def activate(self, player: "Player", context: Dict[str, Any]) -> None:
        """兼容接口：不做任何事。

        Args:
            player: 玩家对象。
            context: 上下文。

        Returns:
            None
        """
        return None


