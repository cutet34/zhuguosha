"""
困难难度策略 AI 控制器（HardAIControl）。

你可以把它理解成两层：
- 第一层：继承 BasicAIControl 的“底线规则”（濒死吃桃/能响应就响应/主公公开、打主公者更可疑等）
- 第二层：HardAI 自己做“打分选择”：
    1) 先给每张可出的牌打分（牌价值）
    2) 对需要指定目标的牌，再给每个目标打分（目标价值：threat/opportunity/strategic/risk）
    3) 选择综合分最高的牌 + 目标

设计目标：
- 可解释：打开 debug 能看到 top5 牌分、每个目标的四项分解
- 可调参：通过常量 / 环境变量 / set_hard_params 修改权重与基础分

注意（重要）：
- 本文件大量读取 game_state 的字段：hp/current_hp、hand_count/hand_cards 等可能存在两套命名。
  所以实现了统一读取函数 _get_hp/_get_hand_count 等，避免你修改策略时踩字段坑。
"""

from __future__ import annotations

from collections import OrderedDict
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from backend.card.card import Card
from backend.control.basic_ai_control import BasicAIControl
from backend.control.ai_debug import ai_debug
from config.enums import CardName, TargetType


class HardAIControl(BasicAIControl):
    """困难难度策略AI（Hard）。

    使用方式：
    - 引擎会周期性 sync_state 把可见信息塞进 self.game_state
    - 出牌阶段：select_card(...) 选一张牌
    - 需要目标：select_targets(...) 选目标

    你主要会改的地方：
    1) 目标四项权重：TARGET_WEIGHT_*
    2) 牌基础分：_card_base_value 里的 base_map
    3) AOE 策略阈值/倍率：AOE_ENEMY_COUNT_THRESHOLD / AOE_ENEMY_MODIFIER
    4) 目标四项的具体计算：OptimizedTargetSelector._calculate_*
    """

    # =====================================================================
    # ① 目标价值四项权重（越大越看重该项）
    #    threat      : “这个人威胁大不大”（偏防守/控场）
    #    opportunity : “这个人现在好杀不杀得掉”（偏收割）
    #    strategic   : “打他符合不符合战略目标”（阵营目标）
    #    risk        : “打错人/打这个人是否风险高”（误伤/副作用，通常是负数扣分）
    #

    # =====================================================================
    TARGET_WEIGHT_THREAT: float = 0.25
    TARGET_WEIGHT_OPPORTUNITY: float = 0.20
    TARGET_WEIGHT_STRATEGIC: float = 0.40
    TARGET_WEIGHT_RISK: float = 0.15

    # 目标打分的 LRU 缓存大小（避免同一轮对同一目标重复算太多次）
    TARGET_EVAL_CACHE_SIZE: int = 256

    # =====================================================================
    # ② AOE 情境修正
    # - 敌人多时，提高 AOE 综合价值
    # - AOE_ENEMY_COUNT_THRESHOLD：敌人数超过该值才加成
    # - AOE_ENEMY_MODIFIER：加成倍率
    # 你要让 Hard 更爱放南蛮/万箭，就调高倍率或降低阈值
    # =====================================================================
    AOE_ENEMY_COUNT_THRESHOLD: int = 2
    AOE_ENEMY_MODIFIER: float = 2.0

    def __init__(self, player_id: int):
        """初始化 HardAI。

        Args:
            player_id: 玩家ID。

        Returns:
            None
        """
        # HardAI 以 BasicAIControl 为基类：
        # - 保留 Basic 的底线规则（濒死吃桃/有牌就响应/基础推断等）
        super().__init__(player_id)

        # 目标四项权重（运行时可改）
        self._target_weights = {
            "threat": float(self.TARGET_WEIGHT_THREAT),
            "opportunity": float(self.TARGET_WEIGHT_OPPORTUNITY),
            "strategic": float(self.TARGET_WEIGHT_STRATEGIC),
            "risk": float(self.TARGET_WEIGHT_RISK),
        }

        # 牌基础分覆盖表（运行时可改）：CardName -> score
        self._card_base_override: Dict[CardName, float] = {}

        # 从环境变量读取可调参数（方便不改代码调参）
        self._load_params_from_env()

        # 目标选择器：负责“对每个目标算 threat/opp/strat/risk 再合成总分”
        self._target_selector = self.OptimizedTargetSelector(self)

    # =====================================================================
    # ③ 参数加载：你不想改代码时，可用环境变量调参
    #
    # - ZHUGUOSHA_HARD_TARGET_WEIGHTS="threat=0.4,opportunity=0.25,strategic=0.2,risk=0.15"
    # - ZHUGUOSHA_HARD_CARD_BASE_JSON='{"TAO":120,"SHA":50,"JUE_DOU":40,"万箭齐发":60}'
    #
    # 注意：基础分 key 支持枚举名/中文（会尝试匹配 CardName）
    # =====================================================================
    def _load_params_from_env(self) -> None:
        """从环境变量加载 hard AI 的可调参数。

        Returns:
            None
        """
        # 1) 目标四项权重
        w_raw = os.getenv("ZHUGUOSHA_HARD_TARGET_WEIGHTS", "").strip()
        if w_raw:
            for part in w_raw.split(","):
                if "=" not in part:
                    continue
                k, v = part.split("=", 1)
                k = k.strip().lower()
                if k not in self._target_weights:
                    continue
                try:
                    self._target_weights[k] = float(v.strip())
                except Exception:
                    continue

        # 2) 牌基础分覆盖（JSON）
        base_raw = os.getenv("ZHUGUOSHA_HARD_CARD_BASE_JSON", "").strip()
        if base_raw:
            try:
                obj = json.loads(base_raw)
            except Exception:
                obj = None
            if isinstance(obj, dict):
                for k, v in obj.items():
                    try:
                        score = float(v)
                    except Exception:
                        continue
                    name_enum = self._coerce_card_name(k)
                    if name_enum is not None:
                        self._card_base_override[name_enum] = score

    def _coerce_card_name(self, key: Any) -> Optional[CardName]:
        """将用户输入 key 转为 CardName。

        Args:
            key: 枚举名字符串、中文字符串、或 CardName。

        Returns:
            CardName 或 None。
        """
        if isinstance(key, CardName):
            return key
        if not isinstance(key, str):
            return None
        s = key.strip()
        if not s:
            return None

        # 优先按枚举名：如 "TAO"、"SHA"
        try:
            return CardName[s]
        except Exception:
            pass

        # 再按中文 value：如 "桃"、"杀"（cn.value）
        for cn in CardName:
            if cn.value == s or cn.name == s:
                return cn
        return None

    def set_hard_params(
        self,
        target_weights: Optional[Dict[str, float]] = None,
        card_base: Optional[Dict[CardName, float]] = None,
    ) -> None:
        """运行时设置 hard AI 参数（便于测试与调参）。

        Args:
            target_weights: 目标四项权重（threat/opportunity/strategic/risk）。
            card_base: 牌基础分覆盖（CardName -> score）。

        Returns:
            None
        """
        if isinstance(target_weights, dict):
            for k, v in target_weights.items():
                kk = str(k).strip().lower()
                if kk not in self._target_weights:
                    continue
                try:
                    self._target_weights[kk] = float(v)
                except Exception:
                    continue

        if isinstance(card_base, dict):
            for k, v in card_base.items():
                if isinstance(k, CardName):
                    try:
                        self._card_base_override[k] = float(v)
                    except Exception:
                        continue

    # =====================================================================
    # ④ 状态读取兼容层：统一读 hp/max_hp/hand_count/alive
    #
    # 你改策略时，尽量都走这些函数，不要直接 p["hp"] / p["current_hp"]。
    # =====================================================================
    def _get_hp(self, p: Dict[str, Any]) -> Optional[int]:
        """读取体力（兼容 current_hp / hp）。"""
        v = p.get("current_hp", None)
        if v is None:
            v = p.get("hp", None)
        try:
            return int(v) if v is not None else None
        except Exception:
            return None

    def _get_max_hp(self, p: Dict[str, Any]) -> Optional[int]:
        """读取体力上限（max_hp）。"""
        v = p.get("max_hp", None)
        try:
            return int(v) if v is not None else None
        except Exception:
            return None

    def _get_hand_count(self, p: Dict[str, Any]) -> int:
        """读取手牌数（兼容 hand_count / hand_cards）。"""
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
        """判断存活（status != '死亡'）。"""
        return p.get("status") != "死亡"

    def _my_info(self) -> Dict[str, Any]:
        """返回自己的可见信息（game_state['self']）。"""
        return (self.game_state or {}).get("self", {}) or {}

    def _get_my_identity(self) -> Optional[str]:
        """返回自己的身份字符串（主公/忠臣/反贼/内奸）。"""
        return self._my_info().get("identity")

    def _iter_other_players(self) -> List[Dict[str, Any]]:
        """遍历其他玩家信息列表（game_state['players']，不含自己）。"""
        players = (self.game_state or {}).get("players", []) or []
        out: List[Dict[str, Any]] = []
        for p in players:
            if not isinstance(p, dict):
                continue
            if p.get("player_id") == self.player_id:
                continue
            out.append(p)
        return out

    # =====================================================================
    # ⑤ “主公定位”与“按身份过滤”（用于 AOE / 战略打分）
    # =====================================================================
    def _find_lord(self) -> Optional[Dict[str, Any]]:
        """找到主公（identity == '主公'）。"""
        for p in self._iter_other_players():
            if p.get("identity") == "主公" and self._is_alive(p):
                return p
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

    # =====================================================================
    # ⑥ AOE 估算层：估计“盟友会被打到几个人”“敌人会被打到几个人”
    #
    # 这里为了可测试性做了简化近似：
    # - 手牌数为 0 => 认为大概率无法响应 => 记为会被 AOE 伤到（1）
    # - 手牌数 > 0 => 认为能响应 => 记为不会被伤到（0）
    # =====================================================================
    def _estimate_aoe_hurt_one(self, p: Dict[str, Any]) -> int:
        """估计 AOE 是否会伤到该玩家（0/1）。"""
        if not self._is_alive(p):
            return 0
        return 1 if self._get_hand_count(p) <= 0 else 0

    def _split_allies_enemies(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """按身份划分盟友/敌人（用于 AOE 策略）。

        Returns:
            (allies, enemies)
        """
        my_id = self._get_my_identity()
        others = [p for p in self._iter_other_players() if self._is_alive(p)]

        # 主公/忠臣：同阵营为盟友，反贼/内奸为敌人
        if my_id in ("主公", "忠臣"):
            allies = [p for p in others if p.get("identity") in ("主公", "忠臣")]
            enemies = [p for p in others if p.get("identity") in ("反贼", "内奸")]
            return allies, enemies

        # 反贼：反贼互为盟友，其他都是敌人
        if my_id == "反贼":
            allies = [p for p in others if p.get("identity") == "反贼"]
            enemies = [p for p in others if p.get("identity") != "反贼"]
            return allies, enemies

        # 内奸：把主公当“需要保护的关键目标”，其余当敌人（这里是猪国杀常见内奸逻辑）
        allies = [p for p in others if p.get("identity") == "主公"]
        enemies = [p for p in others if p.get("identity") != "主公"]
        return allies, enemies

    def _estimate_allies_enemies_hurt(self) -> Tuple[int, int]:
        """估计 AOE 会伤到的盟友人数/敌人人数。"""
        allies, enemies = self._split_allies_enemies()
        allies_hurt = sum(self._estimate_aoe_hurt_one(p) for p in allies)
        enemies_hurt = sum(self._estimate_aoe_hurt_one(p) for p in enemies)
        return int(allies_hurt), int(enemies_hurt)

    def _will_aoe_hurt_lord(self) -> bool:
        """估计 AOE 是否会伤到主公（主公残血时需要更谨慎）。"""
        lord = self._find_lord()
        if not lord:
            return False
        return self._estimate_aoe_hurt_one(lord) >= 1

    # =====================================================================
    # ⑦ 四套 AOE 策略：不同身份对“是否放 AOE”的判断不一样
    #
    # 你想调 AOE 性格：
    # - 更爱放：放宽条件（例如 enemies_hurt >= allies_hurt）
    # - 更保守：更严格（例如 enemies_hurt > allies_hurt * 2）
    # =====================================================================
    def rebel_aoe_strategy(self, allies_hurt: int, enemies_hurt: int) -> bool:
        """反贼 AOE 策略：避免误伤过多反贼，且净收益为正。"""
        total_rebels = len(self._alive_by_identity("反贼"))
        if allies_hurt > 0 and total_rebels > 1:
            allies_ratio = allies_hurt / total_rebels
            if allies_ratio > 0.5:
                return False
        return enemies_hurt > allies_hurt

    def traitor_aoe_strategy(self, allies_hurt: int, enemies_hurt: int) -> bool:
        """内奸 AOE 策略：主公残血时避免误伤主公，其余看净收益。"""
        lord_hp = self._get_lord_hp()
        if lord_hp is not None and lord_hp <= 1:
            if self._will_aoe_hurt_lord():
                return False
        return enemies_hurt >= allies_hurt

    def lord_aoe_strategy(self, allies_hurt: int, enemies_hurt: int) -> bool:
        """主公 AOE 策略：只要不亏就放（等于 enemies_hurt >= allies_hurt）。"""
        _ = len(self._alive_by_identity("忠臣"))
        return enemies_hurt >= allies_hurt

    def loyalist_aoe_strategy(self, allies_hurt: int, enemies_hurt: int) -> bool:
        """忠臣 AOE 策略：主公血低时更保守，否则需要明显净收益。"""
        lord_hp = self._get_lord_hp()
        if lord_hp is not None and lord_hp < 2:
            if self._will_aoe_hurt_lord():
                return False
        return enemies_hurt > allies_hurt * 1.5

    def _aoe_allowed(self) -> bool:
        """统一入口：根据自身身份调用对应 AOE 策略。"""
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

        # 未知身份：保守处理
        return enemies_hurt > allies_hurt

    def calculate_situation_modifier(self, card: Card) -> float:
        """情境修正：敌人多时提高 AOE 价值。

        只对南蛮/万箭生效。

        Args:
            card: 牌对象。

        Returns:
            修正系数（>=1）。
        """
        modifier = 1.0
        if getattr(card, "name_enum", None) in (CardName.NAN_MAN_RU_QIN, CardName.WAN_JIAN_QI_FA):
            _, enemies = self._split_allies_enemies()
            if len(enemies) > self.AOE_ENEMY_COUNT_THRESHOLD:
                modifier *= self.AOE_ENEMY_MODIFIER
        return modifier

    def _get_equipment_slot(self, card: Card) -> str:
        """识别装备槽位：weapon/armor/horse_plus/horse_minus/unknown

        Args:
            card: 牌对象。

        Returns:
            槽位字符串。
        """
        # 兼容不同字段命名
        et = getattr(card, "equipment_type", None)
        if et is None and hasattr(card, "get_equipment_type"):
            try:
                et = card.get_equipment_type()
            except Exception:
                et = None
        s = str(et) if et is not None else ""

        s_low = s.lower()
        if "weapon" in s_low or "武器" in s:
            return "weapon"
        if "armor" in s_low or "防具" in s:
            return "armor"
        if "plus" in s_low or "加" in s:
            return "horse_plus"
        if "minus" in s_low or "减" in s:
            return "horse_minus"
        return "unknown"

    def _my_equipment_occupied(self, slot: str) -> bool:
        """判断自己该槽位是否已有装备。"""
        me = self._my_info()
        if slot == "weapon":
            return bool(me.get("weapon"))
        if slot == "armor":
            return bool(me.get("armor"))
        if slot == "horse_plus":
            return bool(me.get("horse_plus"))
        if slot == "horse_minus":
            return bool(me.get("horse_minus"))
        return False

    def _equipment_base_value(self, card: Card) -> float:
        """不同装备的基础分（不含局势修正）。"""
        slot = self._get_equipment_slot(card)
        base_by_slot = {
            "weapon": 45.0,
            "armor": 55.0,
            "horse_plus": 38.0,
            "horse_minus": 42.0,
            "unknown": 40.0,
        }
        return float(base_by_slot.get(slot, 40.0))

    def _equipment_situation_modifier(self, card: Card, available_targets: Optional[Dict[str, List[int]]]) -> float:
        """装备的局势修正：血量/威胁/是否有进攻机会等。

        Returns:
            乘法修正系数。
        """
        slot = self._get_equipment_slot(card)
        me = self._my_info()
        hp = self._get_hp(me) or 0
        max_hp = self._get_max_hp(me) or 4

        # 敌人粗略数量（身份未知时当敌人，偏保守）
        enemies = []
        my_id = self._get_my_identity()
        for p in self._iter_other_players():
            if not self._is_alive(p):
                continue
            tid = p.get("identity")
            # 身份未知时按敌人算（更愿意防御/控场）
            is_enemy = True if tid is None else (
                    (my_id in ("主公", "忠臣") and tid in ("反贼", "内奸")) or
                    (my_id == "反贼" and tid in ("主公", "忠臣")) or
                    (my_id == "内奸")
            )
            if is_enemy:
                enemies.append(p)

        enemy_cnt = len(enemies)
        targets_attackable = (available_targets or {}).get("attackable", [])

        mod = 1.0

        # 低血量：防具与+马更值钱
        if max_hp > 0 and hp / max_hp <= 0.5:
            if slot in ("armor", "horse_plus"):
                mod *= 1.25

        # 敌人多：防具与+马更值钱
        if enemy_cnt >= 2:
            if slot in ("armor", "horse_plus"):
                mod *= 1.15

        # 当前没有合适进攻目标：武器/-马略降（避免乱装进攻装）
        if slot in ("weapon", "horse_minus") and len(targets_attackable) == 0:
            mod *= 0.90

        return float(mod)

    # =====================================================================
    # ⑧ 牌价值层：给“每张可出的牌”一个分数，Hard 会选分最高的那张
    #
    # 分数来源：
    # - 基础分：_card_base_value（你最常改的地方）
    # - AOE：身份策略 + 情境修正
    # - 杀/决斗：叠加“最佳目标价值”（best_target_score * 10）
    # =====================================================================
    def _card_base_value(self, card: Card) -> float:
        """基础牌价值（不考虑目标/局势）。"""
        if card is None or not hasattr(card, "name_enum"):
            return 0.0

        # 允许外部覆盖基础分（环境变量或 set_hard_params）
        if getattr(card, "name_enum", None) in self._card_base_override:
            return float(self._card_base_override[card.name_enum])

        # ===== 你要调“牌价值排序”，主要改这里 =====
        base_map = {
            CardName.TAO: 100.0,            # 桃：最高
            CardName.WU_XIE_KE_JI: 80.0,    # 无懈
            CardName.SHAN: 55.0,            # 闪
            CardName.SHA: 52.0,             # 杀
            CardName.JUE_DOU: 48.0,         # 决斗
            CardName.NAN_MAN_RU_QIN: 45.0,  # 南蛮
            CardName.WAN_JIAN_QI_FA: 45.0,  # 万箭
        }
        if card.name_enum in base_map:
            return float(base_map[card.name_enum])

        # 装备牌：一个中等基础分
        if card.is_equipment():
            return self._equipment_base_value(card)

        # 其他牌：默认较低
        return 20.0

    def _card_value(self, card: Card, available_targets: Optional[Dict[str, List[int]]]) -> float:
        """综合牌价值：基础分 + 局势修正 + 目标价值。

        Args:
            card: 候选牌。
            available_targets: 可用目标字典（attackable / all）。

        Returns:
            综合价值（越大越优先）。
        """
        if card is None:
            return float("-inf")

        v = self._card_base_value(card)
        name = getattr(card, "name_enum", None)

        targets_all = (available_targets or {}).get("all", [])
        targets_attackable = (available_targets or {}).get("attackable", [])

        # 【桃】满血降权：避免满血浪费桃（但仍保留一定价值，不至于弃掉）
        if name == CardName.TAO:
            me = self._my_info()
            hp = self._get_hp(me)
            max_hp = self._get_max_hp(me)
            if hp is not None and max_hp is not None and hp >= max_hp:
                v -= 50.0
            return v

        # 【AOE】先走身份策略，不允许就直接给极低分（等于不会选）
        if name in (CardName.NAN_MAN_RU_QIN, CardName.WAN_JIAN_QI_FA):
            if not self._aoe_allowed():
                return -1e9
            v *= self.calculate_situation_modifier(card)
            return v

        # 【杀/决斗】无合法目标直接判死刑（不会选）
        if name == CardName.SHA and len(targets_attackable) <= 0:
            return -1e9
        if name == CardName.JUE_DOU and len(targets_all) <= 0:
            return -1e9

        # 【进攻牌】叠加“最佳目标价值”：目标越好，这张牌越值钱
        if name in (CardName.SHA, CardName.JUE_DOU):
            cand = targets_attackable if name == CardName.SHA else targets_all
            best_score = self._target_selector.best_target_score(cand, card)
            v += best_score * 10.0  # 乘子：调大则更“以打人为中心”，调小则更“看牌本身”
        # 装备稍微加一点，避免被基础分压太低
        if card.is_equipment():
            slot = self._get_equipment_slot(card)

            # 槽位已占用：强惩罚，避免无脑重复装（除非你后面实现“更强则替换”）
            if self._my_equipment_occupied(slot):
                v -= 18.0  # 你要更保守就再扣大点
            else:
                v += 10.0  # 空槽奖励：让 AI 更愿意把关键装备装上

            # 局势修正：低血/敌多更偏好防具/+马
            v *= self._equipment_situation_modifier(card, available_targets)

        return float(v)

    def select_card(
        self,
        available_cards: List[Card],
        context: str = "",
        available_targets: Dict[str, List[int]] = None,
    ) -> Optional[Card]:
        """Hard 的出牌选择：对每张牌算综合分，选最高者。

        debug（如果开启）会输出 top5，方便你看“为什么选这张”。

        Args:
            available_cards: 可选牌列表。
            context: 上下文（当前实现里几乎不用，保留兼容）。
            available_targets: 可用目标字典。

        Returns:
            选中的牌或 None。
        """
        if not available_cards:
            return None

        scored: List[Tuple[float, Card]] = []
        best: Optional[Card] = None
        best_v = float("-inf")

        for c in available_cards:
            s = self._card_value(c, available_targets)
            scored.append((float(s), c))
            if s > best_v:
                best_v = float(s)
                best = c

        # 输出 top5 牌分，帮助你调 base_map/权重/乘子
        try:
            scored_sorted = sorted(scored, key=lambda x: x[0], reverse=True)
            top = scored_sorted[:5]
            top_repr = ", ".join([f"{getattr(c,'name_enum',None)}:{v:.2f}" for v, c in top])
            ai_debug(
                f"[AI][hard][p{self.player_id}] choose_card top5=[{top_repr}] "
                f"chosen={getattr(best,'name_enum',None)} score={best_v:.2f}"
            )
        except Exception:
            pass

        # best_v 极低意味着“都不可出”（例如只有无目标的杀/决斗）
        if best is None or best_v <= -1e8:
            return None
        return best

    def select_targets(self, available_targets: List[int], card: Optional[Card] = None) -> List[int]:
        """Hard 的选目标：
        - AOE（TargetType.ALL）：直接全选
        - 单体：用目标选择器挑最佳

        Args:
            available_targets: 候选目标ID列表。
            card: 当前牌。

        Returns:
            目标列表。
        """
        if not available_targets:
            return []

        # AOE：目标是全体，直接返回全部
        if card is not None and getattr(card, "target_type", None) == TargetType.ALL:
            return list(available_targets)

        # 没给 card：保底选第一个（不推荐走到这里）
        if card is None:
            return [available_targets[0]]

        # 单体：选分最高的目标
        best = self._target_selector.best_target_id(available_targets, card)
        if best is None:
            best = available_targets[0]

        ai_debug(f"[AI][hard][p{self.player_id}] choose_target card={getattr(card,'name_enum',None)} target={best}")
        return [best]

    # =====================================================================
    # ⑨ 目标选择器：对每个目标算分（四项分解）并缓存
    #
    # 你想让 Hard “更像人”，基本都在这里改：
    # - threat：谁威胁更大（例如装备/手牌/血量/已跳身份/行为记录）
    # - opportunity：谁更容易被打死（残血/手少/缺响应）
    # - strategic：战略目标（反贼打主公、主忠打疑似反）
    # - risk：误伤风险（打队友扣分、内奸打主公扣分等）
    # =====================================================================
    class OptimizedTargetSelector:
        """优化的目标选择器（四项评分 + LRU 缓存）。"""

        def __init__(self, hard_ai: "HardAIControl"):
            self.hard_ai = hard_ai
            self._evaluation_cache: "OrderedDict[Tuple, float]" = OrderedDict()

        # --- LRU 缓存：避免重复算同一目标 ---
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

        # --- 从 game_state 找目标玩家信息 ---
        def _get_player_by_id(self, pid: int) -> Optional[Dict[str, Any]]:
            me = self.hard_ai._my_info()
            if me.get("player_id") == pid:
                return me
            for p in self.hard_ai._iter_other_players():
                if p.get("player_id") == pid:
                    return p
            return None

        # --- 敌我判断：
        def _is_enemy(self, my_id: Optional[str], target_id: Optional[str]) -> bool:
            if not my_id or not target_id:
                # 身份未知时：先当敌人处理（偏保守）
                return True
            if my_id in ("主公", "忠臣"):
                return target_id in ("反贼", "内奸")
            if my_id == "反贼":
                return target_id in ("主公", "忠臣")
            if my_id == "内奸":
                return True
            return True

        # =============================
        # threat：威胁（越高越想先处理）
        # - 敌人身份加成
        # - 血量高/手牌多也更威胁（更难杀、反击能力更强）
        # =============================
        def _calculate_threat_score(self, target: Dict[str, Any], my_identity: Optional[str]) -> float:
            tid = target.get("identity")
            enemy = 1.0 if self._is_enemy(my_identity, tid) else 0.0
            hp = self.hard_ai._get_hp(target) or 0
            hand = self.hard_ai._get_hand_count(target)
            # 你想更怕“手牌多的人”，就把 0.20 调大
            return enemy * (0.6 + 0.20 * hp + 0.20 * hand)

        # =============================
        # opportunity：机会（越高越容易打出收益）
        # - 杀：偏好残血（hp 越低越高）
        # - 决斗：偏好对方手少（hand 越少越高）
        # =============================
        def _calculate_opportunity_score(self, target: Dict[str, Any], card: Card) -> float:
            hp = self.hard_ai._get_hp(target)
            if hp is None:
                hp = 3
            hand = self.hard_ai._get_hand_count(target)
            if getattr(card, "name_enum", None) == CardName.JUE_DOU:
                # 你想更看重“手少就决斗”，把 0.2 调大
                return max(0.0, 1.5 - 0.2 * hand)
            # 你想更看重“残血先杀”，把 0.6 调大
            return max(0.0, 2.0 - 0.6 * hp)

        # =============================
        # strategic：战略（阵营目标）
        # - 反贼：主公最高优先
        # - 主公/忠臣：反贼最高，其次内奸
        # - 内奸：通常先清场（反/忠），避免过早打死主公
        # =============================
        def _calculate_strategic_score(self, target: Dict[str, Any], my_identity: Optional[str]) -> float:
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

        # =============================
        # risk：风险（通常是负值扣分）
        # - 主公/忠臣误伤队友：强扣分
        # - 内奸打主公：扣分（尤其主公残血，避免“帮反贼”）
        #
        # 你想让 AI 更怕误伤/更保守，就让这里更负一些。
        # =============================
        def _calculate_risk_score(self, target: Dict[str, Any], my_identity: Optional[str]) -> float:
            tid = target.get("identity")
            if not my_identity or not tid:
                return 0.0

            if my_identity in ("主公", "忠臣") and tid in ("主公", "忠臣"):
                return -3.0

            if my_identity == "内奸" and tid == "主公":
                lord_hp = self.hard_ai._get_hp(target) or 3
                return -2.0 if lord_hp <= 2 else -1.0

            return -0.2

        # =================================================================
        # evaluate_target：四项合成总分（带缓存 + debug）
        #
        # key 里包含：目标id、牌名、我方身份、目标身份、目标hp、目标手牌数
        # 这些变量不变时，分数就复用缓存，减少重复计算。
        # =================================================================
        def evaluate_target(self, target_id: int, card: Card) -> float:
            """计算目标综合分（带缓存）。"""
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

            w = self.hard_ai._target_weights
            score = 0.0
            score += threat * float(w.get("threat", 0.40))
            score += opportunity * float(w.get("opportunity", 0.25))
            score += strategic * float(w.get("strategic", 0.20))
            score += risk * float(w.get("risk", 0.15))

            # debug：输出四项分解，方便你调公式与权重
            ai_debug(
                f"[AI][hard][p{self.hard_ai.player_id}] target_score card={getattr(card,'name_enum',None)} tid={target_id} "
                f"threat={threat:.2f} opp={opportunity:.2f} strat={strategic:.2f} risk={risk:.2f} => {score:.2f}"
            )

            self._lru_set(key, score)
            return float(score)

        def best_target_id(self, candidates: List[int], card: Card) -> Optional[int]:
            """返回最佳目标ID（分数最高）。"""
            best_id: Optional[int] = None
            best_score = float("-inf")
            for tid in candidates:
                s = self.evaluate_target(int(tid), card)
                if s > best_score:
                    best_score = s
                    best_id = int(tid)
            return best_id

        def best_target_score(self, candidates: List[int], card: Card) -> float:
            """返回候选目标的最高分（用于叠加到牌价值上）。"""
            best = float("-inf")
            for tid in candidates:
                best = max(best, self.evaluate_target(int(tid), card))
            return 0.0 if best == float("-inf") else float(best)
