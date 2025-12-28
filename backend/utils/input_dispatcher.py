"""前端输入分发器。

集成模式下，前端会通过 communicator.send_to_backend(...) 把 InputResponseEvent
投递到 communicator.ftb_queue。

后端需要有一个消费环节，把这些输入事件分发给对应玩家的 Control.on_event(...)，
否则 HumanControl 会一直等待，导致“人类玩家无法操作”。
"""

from __future__ import annotations

import queue
import threading
from typing import Optional

from communicator.communicator import communicator
from communicator.comm_event import InputResponseEvent, CommEvent


class FrontendInputDispatcher:
    """后台线程：消费前端->后端队列，并把输入事件分发给对应 Control。"""

    def __init__(self, control_manager) -> None:
        """初始化分发器。

        Args:
            control_manager: ControlManager 实例，用于定位玩家 Control。

        Returns:
            None
        """
        self.control_manager = control_manager
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动分发线程。

        Args:
            None

        Returns:
            None
        """
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="frontend-input-dispatcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self, wait: bool = False) -> None:
        """停止分发线程。

        Args:
            wait: 是否等待线程退出。

        Returns:
            None
        """
        self._stop_event.set()
        if wait and self._thread is not None:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        """线程主循环：不断从 ftb_queue 取事件并分发。"""
        while not self._stop_event.is_set():
            try:
                event: CommEvent = communicator.get_from_frontend(timeout=0.1)
            except queue.Empty:
                continue
            except Exception:
                continue

            # 只处理输入响应；AckEvent 等其他事件由 communicator 内部 ACK 线程处理或直接忽略
            if isinstance(event, InputResponseEvent):
                control = self.control_manager.controls.get(event.player_id)
                if control is not None:
                    control.on_event(event)
