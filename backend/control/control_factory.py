# Control工厂模块
"""根据操控类型创建对应的Control实例"""
from typing import Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.control.control import Control
from backend.control.basic_ai_control import BasicAIControl
from config.enums import ControlType


class ControlFactory:
    """Control工厂类
    
    根据操控类型创建对应的Control实例
    """
    
    @staticmethod
    def create_control(
        control_type: ControlType,
        player_id: Optional[int] = None,
        ai_difficulty: Optional[str] = None,
    ) -> Control:
        """创建Control实例
        
        Args:
            control_type: 操控类型
            player_id: 关联的玩家ID
            ai_difficulty: AI 难度（仅当 control_type=AI 时生效，可选：easy/medium/hard/expert）。
            
        Returns:
            Control实例
        """
        if control_type == ControlType.SIMPLE_AI:
            # SIMPLE_AI：历史遗留类型，这里直接等同 EASY（BasicAIControl）。
            return BasicAIControl(player_id)

        elif control_type == ControlType.AI:
            # AI操控：暂时使用基类Control（后续可以实现AIControl）
            from backend.control.adaptive_ai_control import AdaptiveAIControl
            # 允许配置中为同一局不同玩家指定不同难度
            from backend.control.ai_difficulty import AIDifficulty
            diff = None
            if isinstance(ai_difficulty, str) and ai_difficulty.strip():
                raw = ai_difficulty.strip().lower()
                # 兼容旧命名
                alias = {
                    "simple": "easy",
                    "basic": "easy",
                }
                raw = alias.get(raw, raw)

                # 显式给了 ai_difficulty，就必须合法，禁止“默默默认 HARD”
                for d in AIDifficulty:
                    if d.value == raw:
                        diff = d
                        break
                if diff is None:
                    allowed = ", ".join([d.value for d in AIDifficulty])
                    raise ValueError(f"ai_difficulty 无效: {ai_difficulty!r}，允许值: {allowed}")
            return AdaptiveAIControl(player_id, diff)
        elif control_type == ControlType.HUMAN:
            # 玩家操控：使用基类Control（后续可以实现HumanControl）
            from backend.control.human_control import HumanControl
            return HumanControl(player_id)
        else:
            # 默认使用基类Control
            return Control(control_type, player_id)

