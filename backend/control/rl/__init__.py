"""Reinforcement Learning controls (pure Python).

This package is intentionally self-contained:
- no numpy / torch dependency
- training scripts are isolated (no side effects on import)
"""

from .rl_control import RLControl

__all__ = ["RLControl"]
