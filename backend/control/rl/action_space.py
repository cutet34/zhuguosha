from __future__ import annotations

from typing import Iterable, List, Set

from config.enums import CardName
from backend.card.card import Card


PASS_ACTION = "PASS"


def legal_actions_from_playable_cards(playable_cards: List[Card]) -> List[str]:
    """Builds a stable action list from playable cards.

    Actions are represented as CardName.name strings, plus PASS.
    """
    actions: Set[str] = {PASS_ACTION}
    for c in playable_cards or []:
        try:
            if hasattr(c, "name_enum") and isinstance(c.name_enum, CardName):
                actions.add(c.name_enum.name)
        except Exception:
            continue
    # Deterministic ordering for reproducibility
    return sorted(actions)
