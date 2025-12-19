from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from config.enums import GameEvent

if TYPE_CHECKING:
    from backend.player.player import Player


class YingZiSkill:
    """周瑜：英姿

    技能描述：
        摸牌阶段，你可令额定摸牌数 +1。
    这里按锁定技实现：只要进入摸牌阶段，摸牌数在基础值上 +1。
    """

    name: str = "英姿"
    is_locked: bool = True
    need_ask: bool = False

    def can_activate(self, player: "Player", context: Dict[str, Any]) -> bool:
        """英姿通过 modify_draw_num 生效，不通过显式发动。

        Args:
            player: 当前玩家对象。
            context: 技能触发时的上下文字典。

        Returns:
            bool: 恒为 False，不走显式发动流程。
        """
        return False

    def activate(self, player: "Player", context: Dict[str, Any]) -> None:
        """技能激活逻辑（占位，不做任何额外操作）。

        Args:
            player: 当前玩家对象。
            context: 技能触发时的上下文字典。

        Returns:
            None: 无返回值。
        """
        return None

    def modify_draw_num(self, player: "Player", current_num: int, context: Dict[str, Any]) -> int:
        """修改摸牌阶段的摸牌数量。

        Args:
            player: 当前玩家对象。
            current_num: 当前基础摸牌数。
            context: 技能触发时的上下文字典，包含 event_type 等信息。

        Returns:
            int: 若为摸牌阶段，则在基础摸牌数上 +1。
        """
        event_type = context.get("event_type")
        if event_type == GameEvent.DRAW_CARD:
            return current_num + 1
        return current_num
