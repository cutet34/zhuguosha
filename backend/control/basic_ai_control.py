"""中等难度基础策略 AI 控制器。

将 BasicAIControl 从 adaptive_ai_control.py 拆分出来，便于按难度分层维护。
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from backend.card.card import Card
from backend.control.control import Control
from config.enums import CardName, ControlType, TargetType


class BasicAIControl(Control):
    """中等难度基础策略AI。

    策略非常朴素：装备优先、AOE(目标>=2)优先、否则优先出杀/决斗。

    Args:
        player_id: 玩家ID。

    Returns:
        None
    """

    def __init__(self, player_id: int):
        super().__init__(ControlType.AI, player_id)

    def select_card(
        self,
        available_cards: List[Card],
        context: str = "",
        available_targets: Dict[str, List[int]] = None,
    ) -> Optional[Card]:
        """选择要出的牌。

        Args:
            available_cards: 可选牌列表。
            context: 上下文。
            available_targets: 可用目标字典。

        Returns:
            选中的牌或 None。
        """
        if not available_cards:
            return None

        targets_all = (available_targets or {}).get("all", [])
        targets_attackable = (available_targets or {}).get("attackable", [])

        # 1) 优先装备
        for c in available_cards:
            if c.is_equipment():
                return c

        # 2) 群体牌：目标多时优先
        aoe_names = {CardName.NAN_MAN_RU_QIN, CardName.WAN_JIAN_QI_FA}
        for c in available_cards:
            if c.name_enum in aoe_names and len(targets_all) >= 2:
                return c

        # 3) 进攻：杀/决斗
        for c in available_cards:
            if c.name_enum == CardName.SHA and len(targets_attackable) >= 1:
                return c
        for c in available_cards:
            if c.name_enum == CardName.JUE_DOU and len(targets_all) >= 1:
                return c

        return random.choice(available_cards)

    def select_targets(self, available_targets: List[int], card: Optional[Card] = None) -> List[int]:
        """选择目标。

        Args:
            available_targets: 可选目标。
            card: 当前牌。

        Returns:
            目标列表。
        """
        if not available_targets:
            return []
        if card is not None and getattr(card, "target_type", None) == TargetType.ALL:
            return list(available_targets)
        return [random.choice(available_targets)]
