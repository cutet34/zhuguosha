# 操控模块（预留接口）
from typing import List, Optional, Dict, Any
import sys
import os
import random
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.utils.logger import game_logger
from config.enums import ControlType, CardName
from backend.card.card import Card
from communicator.comm_event import CommEvent, DrawCardEvent, PlayCardEvent, HPChangeEvent, DiscardCardEvent, EquipChangeEvent, DeathEvent
from backend.control.event_handler import (
    EventHandler, DrawCardEventHandler, PlayCardEventHandler, HPChangeEventHandler,
    DiscardCardEventHandler, EquipChangeEventHandler, DeathEventHandler, DefaultEventHandler
)


class Control:
    """操控模块基类
    
    预留接口，具体实现待补充
    使用策略模式处理各种事件
    """
    
    def __init__(self, control_type: ControlType, player_id: Optional[int] = None):
        """初始化操控模块
        
        Args:
            control_type: 操控类型（玩家操控/AI操控/规则操控）
            player_id: 关联的玩家ID（可选）
        """
        self.control_type = control_type
        self.player_id = player_id
        self.game_state: Dict[str, Any] = {}  # 存储当前游戏状态
        self.use_skill = True
        
        # 注册事件处理器（策略模式）
        self.event_handlers: Dict[type, EventHandler] = {
            DrawCardEvent: DrawCardEventHandler(),
            PlayCardEvent: PlayCardEventHandler(),
            HPChangeEvent: HPChangeEventHandler(),
            DiscardCardEvent: DiscardCardEventHandler(),
            EquipChangeEvent: EquipChangeEventHandler(),
            DeathEvent: DeathEventHandler(),
        }
        self.default_handler = DefaultEventHandler()
        
    def set_use_skill(self, use_skill: bool) -> None:
        """设置是否使用技能
        
        Args:
            use_skill: 是否使用技能
        """
        self.use_skill = use_skill
    
    def select_card(self, available_cards: List[Card], context: str = "", available_targets: Dict[str, List[int]] = None) -> Optional[Card]:
        """选择要出的牌（正常出牌阶段）
        
        Args:
            available_cards: 可选的牌列表（从左往右的顺序）
            context: 使用上下文（正常出牌时通常为空）
            available_targets: 可用目标字典（可选，用于检查是否有合法目标）
            
        Returns:
            选择的牌或None
        """
        # 从可选牌中随机选择一张（默认实现）
        if available_cards:
            return random.choice(available_cards)
        return None
    
    def ask_use_card_response(self, card_name: CardName, available_cards: List[Card], context: str = "") -> Optional[Card]:
        """询问是否使用指定牌（响应类查询，与正常出牌分开）
        
        Args:
            card_name: 要查询的牌名枚举
            available_cards: 可选的牌列表（从左往右的顺序，只包含指定牌名的牌）
            context: 使用上下文（如"响应决斗"、"响应南蛮入侵"、"受到杀的攻击"等）
            
        Returns:
            选择的牌或None（不使用）
        """
        # 默认实现：随机选择一张（子类可以覆盖）
        if available_cards:
            return random.choice(available_cards)
        return None
    
    def select_targets(self, available_targets: List[int], card: Optional[Card] = None) -> List[int]:
        """选择目标
        
        Args:
            available_targets: 可选目标列表
            card: 要为哪张牌选择目标（可选）
            
        Returns:
            选择的目标列表
        """
        # 从可选目标中随机选择一个
        if available_targets:
            return [random.choice(available_targets)]
        return []
    
    def filter_attackable_targets(self, targets: List[int], available_targets_dict: Dict[str, List[int]] = None) -> List[int]:
        """过滤攻击范围内的目标（默认实现，子类可以覆盖）
        
        Args:
            targets: 目标列表
            available_targets_dict: 可用目标字典（可选）
            
        Returns:
            过滤后的目标列表
        """
        # 默认实现：直接返回原列表
        return targets
    
    def select_cards_to_discard(self, hand_cards: List[Card], count: int) -> List[Card]:
        """选择要弃的牌
        
        Args:
            hand_cards: 手牌列表
            count: 要弃的牌数量
            
        Returns:
            选择要弃的牌列表
        """
        # 从手牌中随机选择对应数量的牌
        if count <= 0:
            return []
        if count >= len(hand_cards):
            return hand_cards.copy()
        # 随机选择count张牌
        return random.sample(hand_cards, count)

    def select_cards_to_discard_any(
        self,
        hand_cards: List[Card],
        max_count: int,
        min_count: int = 0,
        context: str = "",
    ) -> List[Card]:
        """选择要弃置的若干张牌（数量可变）。

        设计动机：
        - 弃牌阶段通常是“必须弃 count 张”（固定数量）。
        - 某些技能（如孙权【制衡】）需要“弃置任意张（0..上限）”。
        - 为了不破坏已有接口，新增此方法。

        Args:
            hand_cards: 手牌列表。
            max_count: 最多可弃置数量。
            min_count: 最少必须弃置数量。
            context: 上下文提示信息。

        Returns:
            选择的弃置牌列表（数量在 [min_count, max_count] 范围内）。
        """
        if not hand_cards:
            return []
        max_n = max(0, min(int(max_count), len(hand_cards)))
        min_n = max(0, min(int(min_count), max_n))

        # 默认策略：
        # - 如果允许 0 张，则随机决定弃几张（更贴近“可选”语义）。
        # - 如果必须弃至少 1 张，则弃 min_n 张。
        if min_n == 0:
            k = random.randint(0, max_n)
        else:
            k = min_n
        if k <= 0:
            return []
        if k >= len(hand_cards):
            return hand_cards.copy()
        return random.sample(hand_cards, k)

    def ask_activate_skill(self, skill_name: str, context: dict) -> bool:
        """询问是否发动某个技能。skill_name如"Lvmeng_Discard_NoDrop"，context可包含player_id、hand_cards等信息。
        默认实现：始终不发动（子类/策略可重载）"""
        return self.use_skill
    
    def on_event(self, event: CommEvent) -> None:
        """接收游戏事件通知
        
        当游戏中有事件发生时，ControlManager会调用此方法通知Control
        使用策略模式分发到对应的事件处理器
        
        Args:
            event: 游戏事件（DrawCardEvent, PlayCardEvent等）
        """
        # 根据事件类型获取对应的处理器
        event_type = type(event)
        handler = self.event_handlers.get(event_type, self.default_handler)
        handler.handle(event, self.player_id)
    
    def register_handler(self, event_type: type, handler: EventHandler) -> None:
        """注册自定义事件处理器
        
        Args:
            event_type: 事件类型（如 DrawCardEvent）
            handler: 事件处理器实例
        """
        self.event_handlers[event_type] = handler
    
    def sync_state(self, state: Dict[str, Any]) -> None:
        """同步游戏状态
        
        定期调用此方法，将当前游戏状态同步给Control
        
        Args:
            state: 游戏状态字典，包含：
                - self: 自己的完整信息
                - players: 其他玩家的公开信息
                - deck: 牌堆信息
        """
        self.game_state = state
        game_logger.log_debug(f"Control状态已同步: {len(state.get('players', []))} 个其他玩家")
