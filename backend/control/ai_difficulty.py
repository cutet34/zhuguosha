from __future__ import annotations

from enum import Enum


class AIDifficulty(Enum):
    """AI 难度枚举

    Args:
        Enum: 枚举基类

    Returns:
        AIDifficulty: 对应难度枚举值
    """
    EASY = "easy"        # 简单：随机选择
    MEDIUM = "medium"    # 中等：基础策略
    HARD = "hard"        # 困难：高级策略
    EXPERT = "expert"    # 专家：近似最优策略
