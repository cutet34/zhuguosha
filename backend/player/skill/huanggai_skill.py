from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from backend.utils.logger import game_logger
from config.enums import GameEvent

if TYPE_CHECKING:
    from backend.player.player import Player


class KuRouSkill:
    """黄盖：苦肉

    技能描述：
        出牌阶段，你可以失去 1 点体力，然后摸两张牌。

    实现要点：
        - 不做“一回合限一次”的限制，只要满足触发条件即可多次发动。
        - 是否发动通过 ask_activate_skill 逐次询问。
        - 体力是否允许降到 0，由 take_damage / game 规则自己处理。
    """

    name: str = "苦肉"
    is_locked: bool = False
    need_ask: bool = True

    def can_activate(self, player: "Player", context: Dict[str, Any]) -> bool:
        """判断当前是否可以发动苦肉。

        触发条件：
            1. 当前事件为出牌阶段（GameEvent.PLAY_CARD）。
            2. 玩家当前仍处于存活状态（体力值大于 0）。

        Args:
            player: 当前玩家对象。
            context: 技能触发时的上下文字典。

        Returns:
            bool: 若满足发动条件则为 True，否则为 False。
        """
        if context.get("event_type") != GameEvent.PLAY_CARD:
            return False

        # 体力值 <= 0 按规则已经进入濒死 / 死亡流程，这里直接返回 False。
        if getattr(player, "current_hp", 0) <= 0:
            return False

        return True

    def activate(self, player: "Player", context: Dict[str, Any]) -> None:
        """执行苦肉效果：失去 1 点体力，然后摸两张牌。

        说明：
            - 是否发动的询问已由 player.trigger_skills 完成。
            - 这里直接调用 take_damage(1, ...) 让游戏机制处理濒死等细节。

        Args:
            player: 当前玩家对象。
            context: 技能触发时的上下文字典。

        Returns:
            None: 无返回值。
        """
        game_logger.log_info(
            f"{player.name} 发动技能【苦肉】，失去 1 点体力并摸两张牌。"
        )

        # 失去 1 点体力（视作自伤）
        player.take_damage(1, source_player_id=player.player_id)

        # 摸两张牌
        player.draw_card(2)
