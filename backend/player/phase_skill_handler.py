# 阶段技能处理器模块
"""使用策略模式统一处理各阶段的技能激活逻辑"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.card.card import Card
from backend.utils.logger import game_logger
from config.enums import GameEvent


class PhaseSkillHandler(ABC):
    """阶段技能处理器基类（策略模式）"""
    
    @abstractmethod
    def build_context(self, player, **kwargs) -> dict:
        """构建技能询问上下文
        
        Args:
            player: 玩家对象
            **kwargs: 阶段特定的参数
            
        Returns:
            上下文字典
        """
        pass
    
    @abstractmethod
    def execute_with_skill(self, player, **kwargs):
        """执行技能版本的操作
        
        Args:
            player: 玩家对象
            **kwargs: 阶段特定的参数
            
        Returns:
            操作结果
        """
        pass
    
    @abstractmethod
    def execute_default(self, player, **kwargs):
        """执行默认版本的操作
        
        Args:
            player: 玩家对象
            **kwargs: 阶段特定的参数
            
        Returns:
            操作结果
        """
        pass


class DrawCardPhaseSkillHandler(PhaseSkillHandler):
    """摸牌阶段技能处理器"""

    def build_context(self, player, **kwargs) -> Dict[str, Any]:
        """构建摸牌阶段上下文。

        Args:
            player: 玩家对象。
            **kwargs: 额外参数。

        Returns:
            Dict[str, Any]: 上下文字典。
        """
        return {
            "player_id": player.player_id,
            "name": player.name,
            "current_hp": player.current_hp,
            "max_hp": player.max_hp,
        }

    def execute_default(self, player, base_draw: int = 2, **kwargs) -> List["Card"]:
        """执行默认摸牌流程（支持技能修改摸牌数）。

        Args:
            player: 玩家对象。
            base_draw: 基础摸牌数（默认 2）。
            **kwargs: 额外参数。

        Returns:
            List[Card]: 实际摸到的牌列表。
        """
        # 构建上下文并标记事件类型
        context: Dict[str, Any] = self.build_context(player, **kwargs)
        context["event_type"] = GameEvent.DRAW_CARD

        # 通过通用钩子计算最终摸牌数（凌操【独进】等技能可在此修正）
        final_draw = player.get_draw_num(base_draw, context)

        # 统一调用 draw_card 执行摸牌
        return player.draw_card(final_draw)

    def execute_with_skill(self, player, base_draw: int = 2, **kwargs) -> List["Card"]:
        """兼容旧接口：目前不区分技能版/默认版，统一走摸牌数钩子。

        Args:
            player: 玩家对象。
            base_draw: 基础摸牌数（默认 2）。
            **kwargs: 额外参数。

        Returns:
            List[Card]: 实际摸到的牌列表。
        """
        # 现在“是否有技能”已经通过 get_draw_num 里的技能钩子处理，
        # 不再需要单独的 with_skill 分支。
        return self.execute_default(player, base_draw, **kwargs)




class PlayCardPhaseSkillHandler(PhaseSkillHandler):
    """出牌阶段技能处理器"""

    def build_context(self, player, available_targets=None, **kwargs) -> dict:
        """构建出牌阶段的上下文"""
        return {
            "player_id": player.player_id,
            "name": player.name,
            "current_hp": player.current_hp,
            "max_hp": player.max_hp,
            "hand_size": len(player.hand_cards),
            "available_targets": available_targets or {},
        }
    
    def execute_with_skill(self, player, available_targets=None, **kwargs) -> Tuple[Optional[Card], List[int]]:
        """执行技能版本的出牌"""
        return player.play_card_with_skill(available_targets)
    
    def execute_default(self, player, available_targets=None, **kwargs) -> Tuple[Optional[Card], List[int]]:
        """执行默认版本的出牌"""
        player.runtime_state["play_phase_executed"] = True
        return player.play_card_default(available_targets)


class DiscardCardPhaseSkillHandler(PhaseSkillHandler):
    """弃牌阶段技能处理器"""
    
    def build_context(self, player, **kwargs) -> dict:
        """构建弃牌阶段的上下文"""
        return {
            "player_id": player.player_id,
            "name": player.name,
            "current_hp": player.current_hp,
            "max_hp": player.max_hp,
            "hand_size": len(player.hand_cards),
        }
    
    def execute_with_skill(self, player, **kwargs) -> List[Card]:
        """执行技能版本的弃牌"""
        return player.discard_card_with_skill()
    
    def execute_default(self, player, **kwargs) -> List[Card]:
        """执行默认版本的弃牌"""
        return player.discard_card_default()


class DamagePhaseSkillHandler(PhaseSkillHandler):
    """受伤阶段技能处理器"""
    
    def build_context(self, player, damage=1, source_player_id=None, 
                     damage_type=None, original_card_name=None, **kwargs) -> dict:
        """构建受伤阶段的上下文"""
        return {
            "player_id": player.player_id,
            "name": player.name,
            "current_hp": player.current_hp,
            "max_hp": player.max_hp,
            "hand_size": len(player.hand_cards),
            "damage": damage,
            "source_player_id": source_player_id,
            "damage_type": damage_type,
            "original_card_name": original_card_name,
        }
    
    def execute_with_skill(self, player, damage=1, source_player_id=None,
                          damage_type=None, original_card_name=None, **kwargs) -> None:
        """执行技能版本的受伤"""
        player.take_damage_with_skill(damage, source_player_id, damage_type, original_card_name)
    
    def execute_default(self, player, damage=1, source_player_id=None,
                       damage_type=None, original_card_name=None, **kwargs) -> None:
        """执行默认版本的受伤"""
        player.take_damage_default(damage, source_player_id, damage_type, original_card_name)


class PhaseSkillManager:
    """阶段技能管理器（统一管理技能激活流程）"""
    
    def __init__(self):
        """初始化管理器，注册各阶段的处理器"""
        self.handlers = {
            GameEvent.DRAW_CARD: DrawCardPhaseSkillHandler(),
            GameEvent.PLAY_CARD: PlayCardPhaseSkillHandler(),
            GameEvent.DISCARD_CARD: DiscardCardPhaseSkillHandler(),
            GameEvent.DAMAGE: DamagePhaseSkillHandler(),
        }
    
    def execute_phase(self, player, event_type: GameEvent, **kwargs):
        """执行游戏阶段的统一入口（事件驱动版本）
         这是技能系统的核心调度方法。其设计哲学从“模板方法”升级为“事件驱动”：
        1.不再假设一个阶段只对应一个技能，而是向玩家对象广播一个事件。
        2.由玩家对象内部管理所有技能，并根据上下文决定触发哪些技能（主动或被动）。

            这种设计使得系统能够轻松支持：
      - 同一阶段触发多个技能（例如：锁定技【英姿】+ 主动技【观星】）
      - 复杂的技能类型（锁定技、觉醒技、限定技）
        
        Args:
            player: 玩家对象
            event_type: 游戏事件类型
            **kwargs: 阶段特定的参数
            
        Returns:
            阶段执行结果
        """
        
        # 1. 获取该阶段的处理器
        handler = self.handlers.get(event_type)
        if not handler:
            return None


        # 2. 构建技能执行上下文
        #    上下文是一个字典，封装了阶段执行所需的所有信息，供技能判断条件和效果使用。
        #    这是连接阶段流程和技能系统的桥梁。
        context = handler.build_context(player, **kwargs)
        context["event_type"] = event_type  # 确保技能能知道自己是由哪个事件触发的

        # 3. 触发技能系统（中文注释：允许多个技能在同一阶段各自生效）
        #    锁定技：直接生效
        #    非锁定技：内部会调用 player.ask_activate_skill(...)
        if hasattr(player, "trigger_skills"):
            player.trigger_skills(context)

        # 4：统一阶段跳过判定
        skip_fn = getattr(player, "should_skip_phase", None)
        if callable(skip_fn) and skip_fn(event_type, context):
            game_logger.log_info(f"{player.name}跳过阶段[{event_type.name}]")
            if event_type == GameEvent.DISCARD_CARD:
                return []
            return None

        # 5. 执行阶段默认流程（阶段本体仍由 handler 负责）
        return handler.execute_default(player, **kwargs)

