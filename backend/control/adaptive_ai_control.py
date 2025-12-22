from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
import os
import random

from backend.control.control import Control
from backend.control.simple_control import SimpleControl
from backend.card.card import Card
from config.enums import ControlType, CardName, TargetType


class AIDifficulty(Enum):
    """AI 难度枚举。"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class BasicAIControl(Control):
    """中等难度基础策略AI。

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
        available_targets: Dict[str, List[int]] = None
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


class AdaptiveAIControl(Control):
    """多难度AI控制器。

    Args:
        player_id: 玩家ID。
        difficulty: 难度（可选）。

    Returns:
        None
    """

    def __init__(self, player_id: int, difficulty: Optional[AIDifficulty] = None):
        super().__init__(ControlType.AI, player_id)
        self.difficulty: AIDifficulty = difficulty or self._difficulty_from_env() or AIDifficulty.HARD
        self._delegate: Control = self._build_delegate()

    def _difficulty_from_env(self) -> Optional[AIDifficulty]:
        """从环境变量读取难度。

        Returns:
            AIDifficulty 或 None。
        """
        raw = os.getenv("ZHUGUOSHA_AI_DIFFICULTY", "").strip().lower()
        if not raw:
            return None
        for d in AIDifficulty:
            if d.value == raw:
                return d
        return None

    def _build_delegate(self) -> Control:
        """根据难度创建策略控制器。

        Returns:
            Control 实例。
        """
        if self.difficulty == AIDifficulty.EASY:
            return Control(ControlType.AI, self.player_id)  # 基类随机
        if self.difficulty == AIDifficulty.MEDIUM:
            return BasicAIControl(self.player_id)
        if self.difficulty == AIDifficulty.HARD:
            return SimpleControl(self.player_id)
        if self.difficulty == AIDifficulty.EXPERT:
            # 原 RI/RL 逻辑并入 EXPERT
            from backend.control.rl.rl_control import ExpertAIControl
            return ExpertAIControl(self.player_id)

        return SimpleControl(self.player_id)

    def _sync_delegate_state(self) -> None:
        """同步关键状态到 delegate。

        Returns:
            None
        """
        self._delegate.set_use_skill(self.use_skill)

    def select_card(
        self,
        available_cards: List[Card],
        context: str = "",
        available_targets: Dict[str, List[int]] = None
    ) -> Optional[Card]:
        """转发出牌选择。"""
        self._sync_delegate_state()
        return self._delegate.select_card(available_cards, context, available_targets)

    def select_targets(self, available_targets: List[int], card: Optional[Card] = None) -> List[int]:
        """转发目标选择。"""
        self._sync_delegate_state()
        return self._delegate.select_targets(available_targets, card)

    def select_cards_to_discard(self, hand_cards: List[Card], count: int) -> List[Card]:
        """转发弃牌选择。"""
        self._sync_delegate_state()
        return self._delegate.select_cards_to_discard(hand_cards, count)

    def ask_use_card_response(self, card_name: CardName, available_cards: List[Card], context: str = "") -> Optional[Card]:
        """转发响应牌选择。"""
        self._sync_delegate_state()
        return self._delegate.ask_use_card_response(card_name, available_cards, context)

    def ask_activate_skill(self, skill_name: str, context: dict) -> bool:
        """转发技能发动询问。"""
        self._sync_delegate_state()
        return self._delegate.ask_activate_skill(skill_name, context)

    def on_event(self, event: Any) -> None:
        """事件转发。"""
        super().on_event(event)
        try:
            self._delegate.on_event(event)
        except Exception:
            pass

    def sync_state(self, state: Dict[str, Any]) -> None:
        """状态同步转发。"""
        super().sync_state(state)
        try:
            self._delegate.sync_state(state)
        except Exception:
            pass
