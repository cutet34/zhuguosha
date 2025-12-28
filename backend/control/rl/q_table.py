from __future__ import annotations

import json
import os
from dataclasses import dataclass
import random
from typing import Dict, Iterable, List, Optional, Tuple


State = Tuple[int, ...]
Action = str


def _state_to_key(state: State) -> str:
    return ",".join(str(x) for x in state)


def _key_to_state(key: str) -> State:
    if key == "":
        return tuple()
    return tuple(int(x) for x in key.split(","))


@dataclass
class QTable:
    """A sparse tabular Q-function: Q[state][action] -> value.

    Stored as a nested dict for simplicity and JSON persistence.
    """

    table: Dict[str, Dict[Action, float]]

    @classmethod
    def empty(cls) -> "QTable":
        return cls(table={})

    @classmethod
    def load(cls, path: str) -> "QTable":
        if not path:
            return cls.empty()
        if not os.path.exists(path):
            return cls.empty()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return cls.empty()
        # Ensure nested dict types
        cleaned: Dict[str, Dict[Action, float]] = {}
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, dict):
                cleaned[k] = {str(a): float(val) for a, val in v.items()}
        return cls(table=cleaned)

    def save(self, path: str) -> None:
        if not path:
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.table, f, ensure_ascii=False, indent=2, sort_keys=True)

    def get(self, state: State, action: Action, default: float = 0.0) -> float:
        sk = _state_to_key(state)
        return float(self.table.get(sk, {}).get(action, default))

    def set(self, state: State, action: Action, value: float) -> None:
        sk = _state_to_key(state)
        if sk not in self.table:
            self.table[sk] = {}
        self.table[sk][action] = float(value)

    def best_action(self, state: State, legal_actions: Iterable[Action]) -> Optional[Action]:
        best_actions: List[Action] = []
        best_v = float("-inf")
        for a in legal_actions:
            v = self.get(state, a)
            if v > best_v:
                best_v = v
                best_actions = [a]
            elif v == best_v:
                best_actions.append(a)
        if not best_actions:
            return None
        # 同分动作随机打破平局，避免长期固定选择 PASS
        return random.choice(best_actions)

    def update_episode_monte_carlo(
        self,
        trajectory: List[Tuple[State, Action]],
        final_reward: float,
        gamma: float,
        alpha: float,
    ) -> None:
        """Monte-Carlo style update: same terminal reward propagated backward with discount."""
        g = float(final_reward)
        for t, (s, a) in enumerate(reversed(trajectory)):
            target = g * (gamma ** t)
            old = self.get(s, a)
            new = old + alpha * (target - old)
            self.set(s, a, new)
