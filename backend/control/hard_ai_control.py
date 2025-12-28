"""困难难度策略 AI 控制器（HardAIControl）。

目标：把 HARD 做成“截图里那种”可解释启发式：
1) 牌价值评估：桃最高，AOE 加入身份策略与情境修正。
2) 目标价值评估：threat/opportunity/strategic/risk 四项加权，并使用 LRU 缓存。

说明：项目的可见状态来自 ControlManager.sync_state，字段可能出现 hp/current_hp、hand_count/hand_cards
两套命名，本文件做了兼容读取。
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from backend.card.card import Card
from backend.control.control import Control
from config.enums import CardName, ControlType, TargetType


class HardAIControl(Control):
    """困难难度策略AI。

    核心接口与 Control 一致：select_card / select_targets。

    Args:
        player_id: 玩家ID。

    Returns:
        None
    """

    # ====== 目标价值四项权重（按你截图默认：0.4/0.25/0.2/0.15） ======
    TARGET_WEIGHT_THREAT: float = 0.40
    TARGET_WEIGHT_OPPORTUNITY: float = 0.25
    TARGET_WEIGHT_STRATEGIC: float = 0.20
    TARGET_WEIGHT_RISK: float = 0.15

    # ====== LRU 缓存大小 ======
    TARGET_EVAL_CACHE_SIZE: int = 256

    # ====== AOE 情境修正（敌人多时 AOE 更值钱） ======
    AOE_ENEMY_COUNT_THRESHOLD: int = 2
    AOE_ENEMY_MODIFIER: float = 2.0

    def __init__(self, player_id: int):
        super().__init__(ControlType.AI, player_id)
        self._target_selector = self.OptimizedTargetSelector(self)

    # ---------------------------------------------------------------------
    # 统一读取：兼容 hp/current_hp、hand_count/hand_cards
    # ---------------------------------------------------------------------
    def _get_hp(self, p: Dict[str, Any]) -> Optional[int]:
        """读取体力。

        Args:
            p: 玩家信息字典。

        Returns:
            体力或 None。
        """
        v = p.get("current_hp", None)
        if v is None:
            v = p.get("hp", None)
        try:
            return int(v) if v is not None else None
        except Exception:
            return None

    def _get_max_hp(self, p: Dict[str, Any]) -> Optional[int]:
        """读取体力上限。

        Args:
            p: 玩家信息字典。

        Returns:
            体力上限或 None。
        """
        v = p.get("max_hp", None)
        try:
            return int(v) if v is not None else None
        except Exception:
            return None

    def _get_hand_count(self, p: Dict[str, Any]) -> int:
        """读取手牌数。

        Args:
            p: 玩家信息字典。

        Returns:
            手牌数（缺省为 0）。
        """
        v = p.get("hand_count", None)
        if v is None:
            cards = p.get("hand_cards", None)
            if isinstance(cards, list):
                return len(cards)
            return 0
        try:
            return int(v)
        except Exception:
            return 0

    def _is_alive(self, p: Dict[str, Any]) -> bool:
        """判断存活。"""
        return p.get("status") != "死亡"

    def _my_info(self) -> Dict[str, Any]:
        """返回 self 字段。"""
        return (self.game_state or {}).get("self", {}) or {}

    def _get_my_identity(self) -> Optional[str]:
        """返回自己的身份字符串（主公/忠臣/反贼/内奸）。"""
        return self._my_info().get("identity")

    def _iter_other_players(self) -> List[Dict[str, Any]]:
        """遍历对手玩家列表（不含自己）。"""
        players = (self.game_state or {}).get("players", []) or []
        out: List[Dict[str, Any]] = []
        for p in players:
            if not isinstance(p, dict):
                continue
            if p.get("player_id") == self.player_id:
                continue
            out.append(p)
        return out

    def _find_lord(self) -> Optional[Dict[str, Any]]:
        """找到主公。"""
        for p in self._iter_other_players():
            if p.get("identity") == "主公" and self._is_alive(p):
                return p
        # 有的状态同步把主公也放在 self 里（自己是主公）
        me = self._my_info()
        if me.get("identity") == "主公" and self._is_alive(me):
            return me
        return None

    def _get_lord_hp(self) -> Optional[int]:
        """读取主公体力。"""
        lord = self._find_lord()
        return self._get_hp(lord) if lord else None

    def _alive_by_identity(self, identity: str) -> List[Dict[str, Any]]:
        """按身份过滤存活玩家（含自己）。"""
        out: List[Dict[str, Any]] = []
        me = self._my_info()
        if me.get("identity") == identity and self._is_alive(me):
            out.append(me)
        for p in self._iter_other_players():
            if p.get("identity") == identity and self._is_alive(p):
                out.append(p)
        return out

    # ---------------------------------------------------------------------
    # AOE：估计 allies_hurt / enemies_hurt（为稳定测试，采用“手牌为0 => 必中”近似）
    # ---------------------------------------------------------------------
    def _estimate_aoe_hurt_one(self, p: Dict[str, Any]) -> int:
        """估计 AOE 是否会“伤到”某人（0/1）。

        Args:
            p: 玩家信息。

        Returns:
            0 或 1。
        """
        if not self._is_alive(p):
            return 0
        # 简化：手牌为 0 大概率没响应牌，记为 1；否则记为 0
        return 1 if self._get_hand_count(p) <= 0 else 0

    def _split_allies_enemies(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """按身份划分盟友/敌人（用于 AOE 策略）。

        Returns:
            (allies, enemies)
        """
        my_id = self._get_my_identity()
        others = [p for p in self._iter_other_players() if self._is_alive(p)]

        if my_id in ("主公", "忠臣"):
            allies = [p for p in others if p.get("identity") in ("主公", "忠臣")]
            enemies = [p for p in others if p.get("identity") in ("反贼", "内奸")]
            return allies, enemies

        if my_id == "反贼":
            allies = [p for p in others if p.get("identity") == "反贼"]
            enemies = [p for p in others if p.get("identity") != "反贼"]
            return allies, enemies

        # 内奸：把主公当作“需要保护的目标”，其余当敌人
        allies = [p for p in others if p.get("identity") == "主公"]
        enemies = [p for p in others if p.get("identity") != "主公"]
        return allies, enemies

    def _estimate_allies_enemies_hurt(self) -> Tuple[int, int]:
        """估计 AOE 对盟友/敌人的伤害人数。

        Returns:
            (allies_hurt, enemies_hurt)
        """
        allies, enemies = self._split_allies_enemies()
        allies_hurt = sum(self._estimate_aoe_hurt_one(p) for p in allies)
        enemies_hurt = sum(self._estimate_aoe_hurt_one(p) for p in enemies)
        return int(allies_hurt), int(enemies_hurt)

    def _will_aoe_hurt_lord(self) -> bool:
        """估计 AOE 是否会伤到主公。"""
        lord = self._find_lord()
        if not lord:
            return False
        return self._estimate_aoe_hurt_one(lord) >= 1

    # ---- 你截图里的四套 AOE 策略（只换了字段读取方式）----
    def rebel_aoe_strategy(self, allies_hurt: int, enemies_hurt: int) -> bool:
        """反贼AOE策略。"""
        total_rebels = len(self._alive_by_identity("反贼"))
        if allies_hurt > 0 and total_rebels > 1:
            allies_ratio = allies_hurt / total_rebels
            if allies_ratio > 0.5:
                return False
        return enemies_hurt > allies_hurt

    def traitor_aoe_strategy(self, allies_hurt: int, enemies_hurt: int) -> bool:
        """内奸AOE策略。"""
        lord_hp = self._get_lord_hp()
        if lord_hp is not None and lord_hp <= 1:
            if self._will_aoe_hurt_lord():
                return False
        return enemies_hurt >= allies_hurt

    def lord_aoe_strategy(self, allies_hurt: int, enemies_hurt: int) -> bool:
        """主公AOE策略。"""
        # 截图里 loyal_count 未参与最终判断，这里保持一致
        _ = len(self._alive_by_identity("忠臣"))
        return enemies_hurt >= allies_hurt

    def loyalist_aoe_strategy(self, allies_hurt: int, enemies_hurt: int) -> bool:
        """忠臣AOE策略。"""
        lord_hp = self._get_lord_hp()
        if lord_hp is not None and lord_hp < 2:
            if self._will_aoe_hurt_lord():
                return False
        return enemies_hurt > allies_hurt * 1.5

    def _aoe_allowed(self) -> bool:
        """根据身份策略判断 AOE 是否可用。"""
        allies_hurt, enemies_hurt = self._estimate_allies_enemies_hurt()
        my_id = self._get_my_identity()

        if my_id == "反贼":
            return self.rebel_aoe_strategy(allies_hurt, enemies_hurt)
        if my_id == "主公":
            return self.lord_aoe_strategy(allies_hurt, enemies_hurt)
        if my_id == "忠臣":
            return self.loyalist_aoe_strategy(allies_hurt, enemies_hurt)
        if my_id == "内奸":
            return self.traitor_aoe_strategy(allies_hurt, enemies_hurt)

        # 未知身份：保守
        return enemies_hurt > allies_hurt

    def calculate_situation_modifier(self, card: Card) -> float:
        """情境修正（截图思路：敌人多时提高 AOE 价值）。

        Args:
            card: 牌对象。

        Returns:
            修正系数。
        """
        modifier = 1.0
        if getattr(card, "name_enum", None) in (CardName.NAN_MAN_RU_QIN, CardName.WAN_JIAN_QI_FA):
            _, enemies = self._split_allies_enemies()
            if len(enemies) > self.AOE_ENEMY_COUNT_THRESHOLD:
                modifier *= self.AOE_ENEMY_MODIFIER
        return modifier

    # ---------------------------------------------------------------------
    # 牌价值：桃最高；AOE 走身份策略 + 情境；杀/决斗叠加“最佳目标价值”。
    # ---------------------------------------------------------------------
    def _card_base_value(self, card: Card) -> float:
        """基础牌价值。

        Args:
            card: 牌对象。

        Returns:
            价值分数。
        """
        if card is None or not hasattr(card, "name_enum"):
            return 0.0

        base_map = {
            CardName.TAO: 100.0,
            CardName.WU_XIE_KE_JI: 80.0,
            CardName.SHAN: 55.0,
            CardName.SHA: 52.0,
            CardName.JUE_DOU: 48.0,
            CardName.NAN_MAN_RU_QIN: 45.0,
            CardName.WAN_JIAN_QI_FA: 45.0,
        }
        if card.name_enum in base_map:
            return float(base_map[card.name_enum])
        if card.is_equipment():
            return 32.0
        return 20.0

    def _card_value(self, card: Card, available_targets: Optional[Dict[str, List[int]]]) -> float:
        """综合牌价值。

        Args:
            card: 候选牌。
            available_targets: 可用目标字典。

        Returns:
            综合价值（越大越优先）。
        """
        if card is None:
            return float("-inf")

        v = self._card_base_value(card)
        name = getattr(card, "name_enum", None)

        targets_all = (available_targets or {}).get("all", [])
        targets_attackable = (available_targets or {}).get("attackable", [])

        # 【桃】满血降权（避免满血“浪费桃”）
        if name == CardName.TAO:
            me = self._my_info()
            hp = self._get_hp(me)
            max_hp = self._get_max_hp(me)
            if hp is not None and max_hp is not None and hp >= max_hp:
                v -= 50.0
            return v

        # AOE：先判身份策略
        if name in (CardName.NAN_MAN_RU_QIN, CardName.WAN_JIAN_QI_FA):
            if not self._aoe_allowed():
                return -1e9
            v *= self.calculate_situation_modifier(card)
            return v

        # 杀/决斗：无合法目标不可选
        if name == CardName.SHA and len(targets_attackable) <= 0:
            return -1e9
        if name == CardName.JUE_DOU and len(targets_all) <= 0:
            return -1e9

        # 对进攻牌叠加“最佳目标价值”
        if name in (CardName.SHA, CardName.JUE_DOU):
            cand = targets_attackable if name == CardName.SHA else targets_all
            best_score = self._target_selector.best_target_score(cand, card)
            v += best_score * 10.0

        # 装备稍微加一点（避免被基础分压太低）
        if card.is_equipment():
            v += 3.0

        return float(v)

    def select_card(
        self,
        available_cards: List[Card],
        context: str = "",
        available_targets: Dict[str, List[int]] = None,
    ) -> Optional[Card]:
        """选择要出的牌：取综合价值最大者。

        Args:
            available_cards: 可选牌列表。
            context: 上下文。
            available_targets: 可用目标字典。

        Returns:
            选中的牌或 None。
        """
        if not available_cards:
            return None

        best: Optional[Card] = None
        best_v = float("-inf")
        for c in available_cards:
            s = self._card_value(c, available_targets)
            if s > best_v:
                best_v = s
                best = c

        if best is None or best_v <= -1e8:
            return None
        return best

    def select_targets(self, available_targets: List[int], card: Optional[Card] = None) -> List[int]:
        """选择目标：AOE 返回全体；单体牌用目标选择器。

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

        if card is None:
            return [available_targets[0]]

        best = self._target_selector.best_target_id(available_targets, card)
        return [best] if best is not None else [available_targets[0]]

    # =====================================================================
    # 目标选择器：四项评分 + LRU 缓存
    # =====================================================================
    class OptimizedTargetSelector:
        """优化的目标选择器（截图里那种）。

        Args:
            hard_ai: HardAIControl 实例。

        Returns:
            None
        """

        def __init__(self, hard_ai: "HardAIControl"):
            self.hard_ai = hard_ai
            self._evaluation_cache: "OrderedDict[Tuple, float]" = OrderedDict()

        def _lru_get(self, key: Tuple) -> Optional[float]:
            if key not in self._evaluation_cache:
                return None
            v = self._evaluation_cache[key]
            self._evaluation_cache.move_to_end(key)
            return float(v)

        def _lru_set(self, key: Tuple, value: float) -> None:
            self._evaluation_cache[key] = float(value)
            self._evaluation_cache.move_to_end(key)
            if len(self._evaluation_cache) > int(self.hard_ai.TARGET_EVAL_CACHE_SIZE):
                self._evaluation_cache.popitem(last=False)

        def _get_player_by_id(self, pid: int) -> Optional[Dict[str, Any]]:
            me = self.hard_ai._my_info()
            if me.get("player_id") == pid:
                return me
            for p in self.hard_ai._iter_other_players():
                if p.get("player_id") == pid:
                    return p
            return None

        def _is_enemy(self, my_id: Optional[str], target_id: Optional[str]) -> bool:
            if not my_id or not target_id:
                return True
            if my_id in ("主公", "忠臣"):
                return target_id in ("反贼", "内奸")
            if my_id == "反贼":
                return target_id in ("主公", "忠臣")
            if my_id == "内奸":
                # 内奸对谁都能打，但主公风险更高
                return True
            return True

        # --- 四项评分（粗粒度，可继续加细节） ---
        def _calculate_threat_score(self, target: Dict[str, Any], my_identity: Optional[str]) -> float:
            """威胁：敌人 + 手牌多 + 血多 => 更威胁。"""
            tid = target.get("identity")
            enemy = 1.0 if self._is_enemy(my_identity, tid) else 0.0
            hp = self.hard_ai._get_hp(target) or 0
            hand = self.hard_ai._get_hand_count(target)
            return enemy * (0.6 + 0.10 * hp + 0.05 * hand)

        def _calculate_opportunity_score(self, target: Dict[str, Any], card: Card) -> float:
            """机会：杀偏好残血；决斗偏好对方手少。"""
            hp = self.hard_ai._get_hp(target)
            if hp is None:
                hp = 3
            hand = self.hard_ai._get_hand_count(target)
            if getattr(card, "name_enum", None) == CardName.JUE_DOU:
                return max(0.0, 1.5 - 0.2 * hand)
            return max(0.0, 2.0 - 0.6 * hp)

        def _calculate_strategic_score(self, target: Dict[str, Any], my_identity: Optional[str]) -> float:
            """战略：按身份给粗优先级。"""
            tid = target.get("identity")
            if not my_identity or not tid:
                return 0.0

            if my_identity == "反贼":
                return 2.0 if tid == "主公" else (1.0 if tid == "忠臣" else 0.8)
            if my_identity in ("主公", "忠臣"):
                return 2.0 if tid == "反贼" else (1.2 if tid == "内奸" else 0.3)
            if my_identity == "内奸":
                return 1.6 if tid in ("反贼", "忠臣") else (0.2 if tid == "主公" else 0.5)
            return 0.0

        def _calculate_risk_score(self, target: Dict[str, Any], my_identity: Optional[str]) -> float:
            """风险：返回负值用于扣分。"""
            tid = target.get("identity")
            if not my_identity or not tid:
                return 0.0

            # 主公/忠臣阵营误伤
            if my_identity in ("主公", "忠臣") and tid in ("主公", "忠臣"):
                return -3.0

            # 内奸打主公风险更大（尤其主公残血）
            if my_identity == "内奸" and tid == "主公":
                lord_hp = self.hard_ai._get_hp(target) or 3
                return -2.0 if lord_hp <= 2 else -1.0

            return -0.2

        def evaluate_target(self, target_id: int, card: Card) -> float:
            """计算目标综合分（带缓存）。

            Args:
                target_id: 目标ID。
                card: 牌。

            Returns:
                得分。
            """
            my_id = self.hard_ai._get_my_identity()
            target = self._get_player_by_id(target_id)
            if not target:
                return 0.0

            key = (
                int(target_id),
                str(getattr(card, "name_enum", "")),
                str(my_id),
                str(target.get("identity")),
                self.hard_ai._get_hp(target),
                self.hard_ai._get_hand_count(target),
            )
            cached = self._lru_get(key)
            if cached is not None:
                return cached

            threat = self._calculate_threat_score(target, my_id)
            opportunity = self._calculate_opportunity_score(target, card)
            strategic = self._calculate_strategic_score(target, my_id)
            risk = self._calculate_risk_score(target, my_id)

            score = 0.0
            score += threat * float(self.hard_ai.TARGET_WEIGHT_THREAT)
            score += opportunity * float(self.hard_ai.TARGET_WEIGHT_OPPORTUNITY)
            score += strategic * float(self.hard_ai.TARGET_WEIGHT_STRATEGIC)
            score += risk * float(self.hard_ai.TARGET_WEIGHT_RISK)

            self._lru_set(key, score)
            return float(score)

        def best_target_id(self, candidates: List[int], card: Card) -> Optional[int]:
            """返回最佳目标ID。"""
            best_id: Optional[int] = None
            best_score = float("-inf")
            for tid in candidates:
                s = self.evaluate_target(int(tid), card)
                if s > best_score:
                    best_score = s
                    best_id = int(tid)
            return best_id

        def best_target_score(self, candidates: List[int], card: Card) -> float:
            """返回候选目标的最高分。"""
            best = float("-inf")
            for tid in candidates:
                best = max(best, self.evaluate_target(int(tid), card))
            return 0.0 if best == float("-inf") else float(best)
