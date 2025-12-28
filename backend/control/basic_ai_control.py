"""中等难度基础策略 AI 控制器。

将 BasicAIControl 从 adaptive_ai_control.py 拆分出来，便于按难度分层维护。
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from backend.card.card import Card
from backend.control.control import Control
from backend.control.ai_debug import ai_debug
from config.enums import CardName, ControlType, TargetType


class BasicAIControl(Control):
    """基础策略AI（当前也作为 EASY 难度使用）。

    设计目标（最基础、但必须“像人”）：
    1) 主公身份公开；其他身份默认不可知（不要靠 game_state["players"][*]["identity"] 透视）。
    2) 濒死必自救：被询问使用【桃】且自己处于濒死/体力<=0 时，有桃必用。
    3) 有牌就响应：被询问使用【闪/杀/无懈可击】时，若手里有且规则允许，优先打出第一张。
    4) 最低限度的阵营推断：
       - 任何玩家对主公使用【杀/决斗】→ 标记为“疑似反贼”。

    注意：本类不实现复杂“献殷勤/表敌意”系统；HardAI 会在此基础上增加评分与策略。

    Args:
        player_id: 玩家ID。

    Returns:
        None
    """

    def __init__(self, player_id: int):
        super().__init__(ControlType.AI, player_id)
        # 中文注释：疑似反贼集合（通过公开行为推断），不等同于真实身份。
        self.suspected_rebels: set[int] = set()

    # ------------------------------------------------------------------
    # 基础工具：读取公开状态
    # ------------------------------------------------------------------
    def _my_info(self) -> Dict:
        """获取自己的可见信息。

        Returns:
            自己信息字典。
        """
        return (self.game_state or {}).get("self", {}) or {}

    def _my_hp(self) -> int:
        """读取自己的体力。

        Returns:
            当前体力（缺省为 0）。
        """
        try:
            return int(self._my_info().get("current_hp", 0))
        except Exception:
            return 0

    def _my_max_hp(self) -> int:
        """读取自己的体力上限。

        Returns:
            体力上限（缺省为 4）。
        """
        try:
            return int(self._my_info().get("max_hp", 4))
        except Exception:
            return 4

    def _my_identity(self) -> Optional[str]:
        """读取自己的身份（主公/忠臣/反贼/内奸）。

        Returns:
            身份字符串或 None。
        """
        v = self._my_info().get("identity")
        return v if isinstance(v, str) and v else None

    def _lord_id(self) -> Optional[int]:
        """获取主公玩家ID（主公身份公开）。

        Returns:
            主公玩家ID 或 None。
        """
        # 先看自己
        me = self._my_info()
        if me.get("identity") == "主公":
            return me.get("player_id")
        # 再看其他玩家
        for p in (self.game_state or {}).get("players", []) or []:
            if not isinstance(p, dict):
                continue
            if p.get("identity") == "主公":
                return p.get("player_id")
        return None

    def _pick_lowest_hp(self, candidate_ids: List[int]) -> Optional[int]:
        """在候选目标中选择体力最低者（公开信息）。

        Args:
            candidate_ids: 候选玩家ID列表。

        Returns:
            选中的玩家ID或None。
        """
        if not candidate_ids:
            return None
        hp_map: Dict[int, int] = {}
        for p in (self.game_state or {}).get("players", []) or []:
            if not isinstance(p, dict):
                continue
            pid = p.get("player_id")
            if pid in candidate_ids:
                try:
                    hp_map[pid] = int(p.get("current_hp", 999))
                except Exception:
                    hp_map[pid] = 999
        # 兜底：如果看不到HP，就随机
        if not hp_map:
            return random.choice(candidate_ids)
        min_hp = min(hp_map.values())
        lowest = [pid for pid, hp in hp_map.items() if hp == min_hp]
        return random.choice(lowest) if lowest else random.choice(candidate_ids)

    # ------------------------------------------------------------------
    # 事件：最小推断
    # ------------------------------------------------------------------
    def on_event(self, event) -> None:
        """接收事件并更新基础推断。

        Args:
            event: CommEvent 事件。

        Returns:
            None
        """
        super().on_event(event)

        # 中文注释：主公身份公开，因此可用“攻击主公者=疑似反贼”做最小推断。
        try:
            from communicator.comm_event import PlayCardEvent
        except Exception:
            PlayCardEvent = None

        if PlayCardEvent is not None and isinstance(event, PlayCardEvent):
            lord_id = self._lord_id()
            if lord_id is None:
                return
            if getattr(event, "to_player", None) != lord_id:
                return
            from_pid = getattr(event, "from_player", None)
            if from_pid is None or from_pid == self.player_id:
                return

            # 只对【杀/决斗】做标记
            name = None
            try:
                name = getattr(getattr(event, "card_config", None), "name", None)
            except Exception:
                name = None
            if name in (CardName.SHA.value, CardName.JUE_DOU.value, "杀", "决斗"):
                if from_pid not in self.suspected_rebels:
                    self.suspected_rebels.add(int(from_pid))
                    ai_debug(f"[AI][basic][p{self.player_id}] infer=suspect_rebel attacker={from_pid} reason=attack_lord")

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

        # 0) 缺血优先吃桃（出牌阶段主动回血）
        my_hp = self._my_hp()
        my_max_hp = self._my_max_hp()
        if my_hp < my_max_hp:
            for c in available_cards:
                if c.name_enum == CardName.TAO:
                    ai_debug(f"[AI][basic][p{self.player_id}] rule=heal_with_tao hp={my_hp}/{my_max_hp}")
                    return c

        # 1) 优先装备
        for c in available_cards:
            if c.is_equipment():
                ai_debug(f"[AI][basic][p{self.player_id}] rule=equip_first card={getattr(c,'name_enum',None)}")
                return c

        # 2) 群体牌：目标多时优先
        aoe_names = {CardName.NAN_MAN_RU_QIN, CardName.WAN_JIAN_QI_FA}
        for c in available_cards:
            if c.name_enum in aoe_names and len(targets_all) >= 2:
                ai_debug(f"[AI][basic][p{self.player_id}] rule=aoe_targets>=2 card={c.name_enum} targets_all={len(targets_all)}")
                return c

        # 3) 进攻：杀/决斗
        for c in available_cards:
            if c.name_enum == CardName.SHA and len(targets_attackable) >= 1:
                ai_debug(f"[AI][basic][p{self.player_id}] rule=sha_attack card={c.name_enum} targets_attackable={len(targets_attackable)}")
                return c
        for c in available_cards:
            if c.name_enum == CardName.JUE_DOU and len(targets_all) >= 1:
                ai_debug(f"[AI][basic][p{self.player_id}] rule=duel card={c.name_enum} targets_all={len(targets_all)}")
                return c

        # 4) 兜底：不强行随机出牌，避免“乱出导致逻辑抖动”。
        ai_debug(f"[AI][basic][p{self.player_id}] rule=no_play")
        return None

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

        # 群体牌直接全选
        if card is not None and getattr(card, "target_type", None) == TargetType.ALL:
            return list(available_targets)

        my_identity = self._my_identity()
        lord_id = self._lord_id()

        # 反贼：优先打主公
        if my_identity == "反贼" and lord_id in available_targets:
            ai_debug(f"[AI][basic][p{self.player_id}] pick_target=lord_as_rebel card={getattr(card,'name_enum',None)}")
            return [int(lord_id)]

        # 主公/忠臣：优先打“疑似反贼”
        if my_identity in {"主公", "忠臣"}:
            suspects = [pid for pid in available_targets if pid in self.suspected_rebels]
            if suspects:
                chosen = self._pick_lowest_hp(suspects) or random.choice(suspects)
                ai_debug(f"[AI][basic][p{self.player_id}] pick_target=suspect_rebel card={getattr(card,'name_enum',None)} target={chosen}")
                return [int(chosen)]

        # 兜底：打血最少的
        chosen2 = self._pick_lowest_hp(available_targets) or random.choice(available_targets)
        ai_debug(f"[AI][basic][p{self.player_id}] pick_target=lowest_hp card={getattr(card,'name_enum',None)} target={chosen2}")
        return [int(chosen2)]

    def ask_use_card_response(self, card_name: CardName, available_cards: List[Card], context: str = "") -> Optional[Card]:
        """响应类用牌选择（基础版）。

        规则（最小但实用）：
        - 自己濒死/体力<=0：被问【桃】则必用。
        - 被问【闪/杀/无懈】等响应牌：有就打第一张。

        Args:
            card_name: 询问的牌名。
            available_cards: 可用牌（已过滤同名）。
            context: 上下文。

        Returns:
            选择的牌或 None。
        """
        if not available_cards:
            return None

        # 桃：只做“自救濒死”。
        if card_name == CardName.TAO:
            hp = self._my_hp()
            status = str(self._my_info().get("status", ""))
            if hp <= 0 or ("濒死" in status) or ("濒死" in context) or ("自救" in context) or ("求桃" in context):
                ai_debug(f"[AI][basic][p{self.player_id}] respond=TAO hp={hp} status={status}")
                return available_cards[0]
            return None

        # 其余响应牌：有就出
        ai_debug(f"[AI][basic][p{self.player_id}] respond={card_name} use_first")
        return available_cards[0]
