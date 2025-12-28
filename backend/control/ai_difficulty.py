from __future__ import annotations

from enum import Enum


class AIDifficulty(Enum):
    """AI 难度枚举

    Args:
        Enum: 枚举基类

    Returns:
        AIDifficulty: 对应难度枚举值
    """
    EASY = "easy"        # 简单：基础策略（不透视、会自救、会响应）
    HARD = "hard"        # 困难：高级策略
    EXPERT = "expert"    # 专家：近似最优策略
