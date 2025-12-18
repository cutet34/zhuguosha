from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from config.enums import CardName, PlayerIdentity


State = Tuple[int, ...]


def _clip(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _identity_to_int(identity_value: Any) -> int:
    """Maps identity string/value to a small int.

    The project currently syncs identity as a Chinese string (value), not Enum.name.
    """
    if identity_value is None:
        return 0
    s = str(identity_value)
    mapping = {
        PlayerIdentity.LORD.value: 1,
        PlayerIdentity.LOYALIST.value: 2,
        PlayerIdentity.REBEL.value: 3,
        PlayerIdentity.TRAITOR.value: 4,
    }
    return mapping.get(s, 0)


def _card_value_to_enum(card_value: Any) -> CardName | None:
    if card_value is None:
        return None
    s = str(card_value)
    for cn in CardName:
        if cn.value == s:
            return cn
    return None


@dataclass
class StateEncoder:
    """Encodes visible_state (from ControlManager.sync_state) into a small discrete state."""

    # Which card names are tracked as counts in state
    tracked_cards: Tuple[CardName, ...] = (
        CardName.SHA,
        CardName.SHAN,
        CardName.TAO,
        CardName.JUE_DOU,
        CardName.WU_XIE_KE_JI,
        CardName.NAN_MAN_RU_QIN,
        CardName.WAN_JIAN_QI_FA,
    )

    def encode(self, visible_state: Dict[str, Any]) -> State:
        self_info = visible_state.get("self", {}) if isinstance(visible_state, dict) else {}
        players_info = visible_state.get("players", []) if isinstance(visible_state, dict) else []

        # Self basic stats
        self_hp = _clip(int(self_info.get("current_hp", 0) or 0), 0, 10)
        self_hand = _clip(int(self_info.get("hand_count", 0) or 0), 0, 20)
        equip_count = 0
        for k in ("weapon", "armor", "horse_plus", "horse_minus"):
            if self_info.get(k) is not None:
                equip_count += 1
        equip_count = _clip(equip_count, 0, 4)
        identity_code = _identity_to_int(self_info.get("identity"))

        # Opponents summary
        alive_players = [p for p in players_info if isinstance(p, dict) and p.get("status") == "存活"]
        opp_alive = _clip(len(alive_players), 0, 8)
        if alive_players:
            opp_hps = [int(p.get("current_hp", 0) or 0) for p in alive_players]
            opp_min_hp = _clip(min(opp_hps), 0, 10)
            opp_max_hp = _clip(max(opp_hps), 0, 10)
            opp_max_hand = _clip(max(int(p.get("hand_count", 0) or 0) for p in alive_players), 0, 20)
        else:
            opp_min_hp = 0
            opp_max_hp = 0
            opp_max_hand = 0

        # Identity counts (the project currently exposes identity to all controls).
        # This helps RL learn different reward structure by role.
        lord_alive = 0
        rebel_alive = 0
        loyal_alive = 0
        traitor_alive = 0
        for p in alive_players:
            pid = _identity_to_int(p.get("identity"))
            if pid == 1:
                lord_alive += 1
            elif pid == 2:
                loyal_alive += 1
            elif pid == 3:
                rebel_alive += 1
            elif pid == 4:
                traitor_alive += 1
        lord_alive = _clip(lord_alive, 0, 1)
        loyal_alive = _clip(loyal_alive, 0, 8)
        rebel_alive = _clip(rebel_alive, 0, 8)
        traitor_alive = _clip(traitor_alive, 0, 1)

        # Hand card counts (tracked subset)
        counts = {cn: 0 for cn in self.tracked_cards}
        for c in self_info.get("hand_cards", []) or []:
            if not isinstance(c, dict):
                continue
            cn = _card_value_to_enum(c.get("name"))
            if cn in counts:
                counts[cn] += 1
        tracked_counts = tuple(_clip(counts[cn], 0, 10) for cn in self.tracked_cards)

        return (
            identity_code,
            self_hp,
            self_hand,
            equip_count,
            opp_alive,
            opp_min_hp,
            opp_max_hp,
            opp_max_hand,
            lord_alive,
            loyal_alive,
            rebel_alive,
            traitor_alive,
            *tracked_counts,
        )
