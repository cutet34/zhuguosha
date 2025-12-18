from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.player.player import Player


class DuJinSkill:
    """凌操：独进

    摸牌阶段，你可以多摸 X+1 张牌（X 为你装备区里牌数的一半且向下取整）。
    """

    name: str = "独进"
    is_locked: bool = False
    need_ask: bool = True

    def can_activate(self, player: "Player", context: Dict[str, Any]) -> bool:
        """独进通过修改摸牌数生效，不依赖显式触发。

        Args:
            player: 玩家对象。
            context: 上下文。

        Returns:
            bool: 始终为 False（不走 trigger_skills 的 activate 流程）。
        """
        return False

    def activate(self, player: "Player", context: Dict[str, Any]) -> None:
        """兼容接口：独进不通过 activate 产生效果。

        Args:
            player: 玩家对象。
            context: 上下文。

        Returns:
            None
        """
        return None

    def modify_draw_num(self, player: "Player", current_num: int, context: Dict[str, Any]) -> int:
        """修改摸牌数（被动规则修正）。

        Args:
            player: 玩家对象。
            current_num: 当前计算出的摸牌数（通常为 2）。
            context: 摸牌阶段上下文。

        Returns:
            int: 修改后的摸牌数。
        """
        # 统计装备区数量
        equip_cnt = 0
        if getattr(player, "weapon", None):
            equip_cnt += 1
        if getattr(player, "armor", None):
            equip_cnt += 1
        if getattr(player, "horse_plus", None):
            equip_cnt += 1
        if getattr(player, "horse_minus", None):
            equip_cnt += 1

        extra = (equip_cnt // 2) + 1

        # 可选技：询问是否发动独进
        if player.ask_activate_skill(self.name, context):
            return current_num + extra
        return current_num

