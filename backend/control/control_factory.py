# Control工厂模块
"""根据操控类型创建对应的Control实例"""
from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.control.control import Control
from backend.control.simple_control import SimpleControl
from config.enums import ControlType


class ControlFactory:
    """Control工厂类
    
    根据操控类型创建对应的Control实例
    """
    
    @staticmethod
    def create_control(control_type: ControlType, player_id: Optional[int] = None) -> Control:
        """创建Control实例
        
        Args:
            control_type: 操控类型
            player_id: 关联的玩家ID
            
        Returns:
            Control实例
        """
        if control_type == ControlType.SIMPLE_AI:
            # 规则操控：使用SimpleControl
            return SimpleControl(player_id)
        elif control_type == ControlType.RL:
            # 强化学习操控：使用RLControl（纯Python实现，不依赖第三方库）
            from backend.control.rl.rl_control import RLControl
            return RLControl(player_id)
        elif control_type == ControlType.AI:
            # AI操控：暂时使用基类Control（后续可以实现AIControl）
            return Control(control_type, player_id)
        elif control_type == ControlType.HUMAN:
            # 玩家操控：使用基类Control（后续可以实现HumanControl）
            return Control(control_type, player_id)
        else:
            # 默认使用基类Control
            return Control(control_type, player_id)

