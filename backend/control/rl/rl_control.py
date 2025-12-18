from __future__ import annotations

import os
import random
from typing import Any, Dict, List, Optional, Tuple

from config.enums import CardName, ControlType
from backend.card.card import Card
from backend.control.control import Control

from .action_space import PASS_ACTION, legal_actions_from_playable_cards
from .q_table import QTable, State, Action
from .state_encoder import StateEncoder


class RLControl(Control):
    """A minimal tabular Q-learning control.

    Design goals:
    - No third-party dependencies
    - No training side effects on import
    - Works as a drop-in Control implementation
    """

    def __init__(self, player_id: Optional[int] = None):
        super().__init__(ControlType.RL, player_id)

        # Learning components
        self.encoder = StateEncoder()
        self.q_table: QTable = QTable.empty()

        # Training params (can be overridden by trainer)
        self.epsilon: float = 0.2
        self.alpha: float = 0.1
        self.gamma: float = 0.95
        self.q_table_path: str = ""

        # Episode trajectory: list of (state, action)
        self._trajectory: List[Tuple[State, Action]] = []

    # -------------------- training control --------------------
    def set_training_params(
        self,
        *,
        q_table_path: Optional[str] = None,
        epsilon: Optional[float] = None,
        alpha: Optional[float] = None,
        gamma: Optional[float] = None,
    ) -> None:
        if q_table_path is not None:
            self.q_table_path = q_table_path
            self.q_table = QTable.load(q_table_path)
        if epsilon is not None:
            self.epsilon = float(epsilon)
        if alpha is not None:
            self.alpha = float(alpha)
        if gamma is not None:
            self.gamma = float(gamma)

    def begin_episode(self) -> None:
        self._trajectory = []

    def end_episode(self, reward: float) -> None:
        # Update Q with terminal reward, then persist
        if self._trajectory:
            self.q_table.update_episode_monte_carlo(
                self._trajectory,
                final_reward=float(reward),
                gamma=float(self.gamma),
                alpha=float(self.alpha),
            )
        if self.q_table_path:
            self.q_table.save(self.q_table_path)

    # -------------------- Control overrides --------------------
    def sync_state(self, state: Dict[str, Any]) -> None:
        # Keep base behavior (stores state)
        super().sync_state(state)

    def select_card(
        self,
        available_cards: List[Card],
        context: str = "",
        available_targets: Dict[str, List[int]] = None,
    ) -> Optional[Card]:
        if not available_cards:
            return None

        # Encode state from last synced visible state
        state = self.encoder.encode(self.game_state)
        legal_actions = legal_actions_from_playable_cards(available_cards)

        # Epsilon-greedy selection
        if random.random() < self.epsilon:
            action = random.choice(legal_actions)
        else:
            best = self.q_table.best_action(state, legal_actions)
            action = best if best is not None else random.choice(legal_actions)

        # Record decision for learning
        self._trajectory.append((state, action))

        if action == PASS_ACTION:
            return None

        # Map action back to an actual card instance (deterministic: choose first)
        for c in available_cards:
            if hasattr(c, "name_enum") and isinstance(c.name_enum, CardName):
                if c.name_enum.name == action:
                    return c
        # Fallback
        return random.choice(available_cards)

    def select_targets(self, available_targets: List[int], card: Optional[Card] = None) -> List[int]:
        if not available_targets:
            return []
        return [random.choice(available_targets)]

    def select_cards_to_discard(self, hand_cards: List[Card], count: int) -> List[Card]:
        # Keep default random discard behavior
        return super().select_cards_to_discard(hand_cards, count)

    def ask_use_card_response(
        self,
        card_name: CardName,
        available_cards: List[Card],
        context: str = "",
    ) -> Optional[Card]:
        # Minimal: respond probabilistically (can be learned later)
        if not available_cards:
            return None
        # Prefer saving responses for TAO/SHAN/WU_XIE, but keep simple.
        if card_name in (CardName.TAO, CardName.SHAN, CardName.WU_XIE_KE_JI):
            return available_cards[0]
        return available_cards[0] if random.random() < 0.5 else None

    def ask_activate_skill(self, skill_name: str, context: dict) -> bool:
        return super().ask_activate_skill(skill_name, context)
