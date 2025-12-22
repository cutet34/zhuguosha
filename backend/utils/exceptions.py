# 自定义异常定义（用于更清晰的错误信息）
from __future__ import annotations


class GameException(Exception):
    """游戏基础异常。"""


class InvalidInputException(GameException):
    """输入非法异常。"""


class InvalidCardException(GameException):
    """无效的牌异常。"""

    def __init__(self, card: object):
        super().__init__(f"无效的牌: {card}")
        self.card = card


class InvalidTargetException(GameException):
    """无效的目标异常。"""

    def __init__(self, target_id: int):
        super().__init__(f"无效的目标: {target_id}")
        self.target_id = target_id
