"""AI 调试输出工具。

原则：
- 默认不输出，避免污染对拍 stdout。
- 开关由环境变量控制，输出写到 stderr。

环境变量：
- ZHUGUOSHA_AI_DEBUG=1     开启 AI debug。

"""

from __future__ import annotations

import os
import sys
from typing import Any


def ai_debug_enabled() -> bool:
    """是否开启 AI 调试输出。

    Returns:
        是否开启。
    """
    raw = os.getenv("ZHUGUOSHA_AI_DEBUG", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def ai_debug(*parts: Any) -> None:
    """输出 AI 调试信息到 stderr。

    Args:
        *parts: 任意可打印对象。

    Returns:
        None
    """
    if not ai_debug_enabled():
        return
    msg = " ".join(str(p) for p in parts)
    sys.stderr.write(msg + "\n")
