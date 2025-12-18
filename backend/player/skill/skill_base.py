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