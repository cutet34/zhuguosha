from __future__ import annotations

from typing import Any, Dict, List, Optional
import os

from backend.card.card import Card
from backend.control.control import Control
from backend.control.simple_control import SimpleControl
from backend.control.ai_difficulty import AIDifficulty
from backend.control.basic_ai_control import BasicAIControl
from backend.control.hard_ai_control import HardAIControl

from config.enums import ControlType, CardName


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
        # 你这次的约定：
        # - EASY  -> SimpleControl（入门级规则/启发式）
        # - MEDIUM-> BasicAIControl（中等：基础策略）
        # - HARD  -> HardAIControl（困难：牌价值判断）
        # - EXPERT-> ExpertAIControl（强化学习/RI）
        if self.difficulty == AIDifficulty.EASY:
            return SimpleControl(self.player_id)
        if self.difficulty == AIDifficulty.MEDIUM:
            return BasicAIControl(self.player_id)
        if self.difficulty == AIDifficulty.HARD:
            return HardAIControl(self.player_id)
        if self.difficulty == AIDifficulty.EXPERT:
            from backend.control.rl.rl_control import ExpertAIControl
            return ExpertAIControl(self.player_id)

        return HardAIControl(self.player_id)

    # -------------------- RL/RI 训练接口转发（EXPERT 难度可用） --------------------
    def set_training_params(self, **kwargs: Any) -> None:
        """向子策略转发训练参数（若支持）。

        Args:
            **kwargs: 训练器传入的参数。

        Returns:
            None
        """
        fn = getattr(self._delegate, "set_training_params", None)
        if callable(fn):
            fn(**kwargs)

    def begin_episode(self) -> None:
        """开始新一局训练（若支持）。"""
        fn = getattr(self._delegate, "begin_episode", None)
        if callable(fn):
            fn()

    def end_episode(self, reward: float) -> None:
        """结束一局训练并回传终局奖励（若支持）。"""
        fn = getattr(self._delegate, "end_episode", None)
        if callable(fn):
            fn(reward)

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

    def select_cards_to_discard_any(
        self,
        hand_cards: List[Card],
        max_count: int,
        min_count: int = 0,
        context: str = "",
    ) -> List[Card]:
        """转发可变数量弃牌选择（用于技能如【制衡】）。"""
        self._sync_delegate_state()
        fn = getattr(self._delegate, "select_cards_to_discard_any", None)
        if callable(fn):
            return fn(hand_cards, max_count, min_count, context)
        return super().select_cards_to_discard_any(hand_cards, max_count, min_count, context)

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
