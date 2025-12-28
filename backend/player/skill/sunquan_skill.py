from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

from backend.utils.logger import game_logger
from backend.utils.event_sender import send_discard_card_event
from config.enums import GameEvent, ControlType

if TYPE_CHECKING:
    from backend.player.player import Player
    from backend.card.card import Card


class ZhiHengSkill:
    """孙权：制衡

    技能描述：
        出牌阶段限一次，
        你可以弃置任意张牌，然后摸等量的牌。

    实现要点：
        - 一回合限一次：用 runtime_state["zhiheng_used_this_turn"] 控制。
        - 弃置任意张牌：通过底层 Control 交互选择需要弃置的牌。
    """

    name: str = "制衡"
    is_locked: bool = False
    need_ask: bool = True

    FLAG_KEY: str = "zhiheng_used_this_turn"

    def can_activate(self, player: "Player", context: Dict[str, Any]) -> bool:
        """判断当前是否可以发动制衡。

        触发条件：
            1. 当前事件为出牌阶段（GameEvent.PLAY_CARD）。
            2. 本回合尚未发动过制衡。

        Args:
            player: 当前玩家对象。
            context: 技能触发时的上下文字典。

        Returns:
            bool: 若满足发动条件则为 True，否则为 False。
        """
        if context.get("event_type") != GameEvent.PLAY_CARD:
            return False

        # 一回合限一次
        if player.runtime_state.get(self.FLAG_KEY, False):
            return False

        # 官方允许没有手牌时发动（弃 0 摸 0），这里不做手牌数量限制
        return True

    def _select_cards_to_discard(self, player: "Player") -> List["Card"]:
        """选择需要因制衡而弃置的手牌。

        说明：
            这里假定 Player 封装了一个与 Control 交互的接口：
                select_cards_to_discard(max_num: int, min_num: int, reason: str) -> List[Card]

            若你当前项目中接口名称不同，可以在此处做一次适配。

        Args:
            player: 当前玩家对象。

        Returns:
            List[Card]: 选择弃置的手牌列表，可以为空列表。
        """
        hand_cards: List["Card"] = list(getattr(player, "hand_cards", []))
        if not hand_cards:
            return []

        # 与单测/历史实现保持兼容：
        # - 人类操控：允许“弃任意张”（前端多选 + Enter/右键确认；控制台逗号输入）。
        # - AI 操控：若没有专门策略，默认退化为“弃置全部手牌”。
        if getattr(player.control, "control_type", None) != ControlType.HUMAN:
            return hand_cards

        try:
            return player.control.select_cards_to_discard_any(
                hand_cards=hand_cards,
                max_count=len(hand_cards),
                min_count=0,
                context=self.name,
            )
        except Exception:
            return []

    def activate(self, player: "Player", context: Dict[str, Any]) -> None:
        """执行制衡效果：弃置任意张牌，然后摸等量的牌。

        说明：
            - 是否发动的询问已由 player.trigger_skills → ask_activate_skill 完成。
            - 这里只做：选牌 → 弃牌 → 摸牌。
            - 弃 0 张牌是允许的，此时摸 0 张，等于白发。

        Args:
            player: 当前玩家对象。
            context: 技能触发时的上下文字典。

        Returns:
            None: 无返回值。
        """
        # 标记“本回合已发动制衡”
        player.runtime_state[self.FLAG_KEY] = True

        selected_cards = self._select_cards_to_discard(player)
        count = len(selected_cards)

        game_logger.log_info(
            f"{player.name} 发动技能【制衡】，弃置 {count} 张牌后摸 {count} 张牌。"
        )

        # 弃置选中的手牌
        for card in selected_cards:
            if card in player.hand_cards:
                player.hand_cards.remove(card)
                player.deck.discard_card(card)
                send_discard_card_event(card, player.player_id)

        # 摸等量牌
        if count > 0:
            player.draw_card(count)

    def reset_turn_state(self, player: "Player") -> None:
        """重置制衡技能的回合内状态。

        Args:
                player: 拥有该技能的玩家对象。

        Returns:
                None: 无返回值。
        """
        # 与 can_activate 中的 runtime_state FLAG_KEY 保持一致
        player.runtime_state[self.FLAG_KEY] = False
