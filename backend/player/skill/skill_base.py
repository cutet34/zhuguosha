from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.player.player import Player  # 只用于类型检查，避免运行时循环导入

# 1. 定义技能接口
class Skill(ABC):
    @abstractmethod
    def can_activate(self, player: Player, context: Dict) -> bool:
        """检查技能是否可以激活"""
        pass

    @abstractmethod
    def activate(self, player: Player, context: Dict) -> Any:
        """激活技能"""
        pass
    name: str = ""

    def reset_turn_state(self, player: "Player") -> None:
        """重置该技能在本回合内使用的运行时状态。

        Args:
            player: 拥有该技能的玩家对象。

        Returns:
            None: 默认不做任何处理，由需要的子类重写。
        """
        return None