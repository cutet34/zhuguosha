from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List, Optional

from backend.control.control import Control
from config.enums import ControlType, CardName
from backend.card.card import Card
from communicator.communicator import communicator
from communicator.comm_event import InputRequestEvent, InputResponseEvent
from backend.utils.event_sender import get_wait_for_ack


class HumanControl(Control):
    """人类玩家控制器：无前端时走控制台，有前端时走事件交互。"""

    def __init__(self, player_id: Optional[int] = None) -> None:
        """初始化玩家控制器。

        Args:
            player_id: 玩家编号。

        Returns:
            None
        """
        super().__init__(ControlType.HUMAN, player_id)
        # 事件模式下使用的锁和条件变量
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._pending_request_id: Optional[str] = None
        self._pending_payload: Optional[Dict[str, Any]] = None

    # ===================== 公共接口：给 PlayerController / GameController 调用 =====================

    def select_card(
        self,
        available_cards: List[Card],
        context: str = "",
        available_targets: Dict[str, List[int]] = None
    ) -> Optional[Card]:
        """选择要出的牌。

        Args:
            available_cards: 可选牌列表。
            context: 上下文提示信息。
            available_targets: 可用目标字典（本函数中可不使用）。

        Returns:
            选中的牌；若不出牌则返回 None。
        """
        if not available_cards:
            return None

        if self._use_console_mode():
            return self._select_card_console(available_cards)

        # 前端事件模式
        request_id = self._start_request()
        options = {
            "cards": [
                {
                    "index": i,
                    "name": str(c.name_enum),
                    "suit": getattr(c, "suit", None).name if getattr(c, "suit", None) else None,
                    "rank": getattr(c, "rank", None),
                }
                for i, c in enumerate(available_cards)
            ]
        }
        req = InputRequestEvent(
            request_id=request_id,
            player_id=self.player_id,
            action="select_card",
            prompt=context or "请选择要出的牌",
            options=options,
        )
        if communicator is not None:
            communicator.send_to_frontend(req, wait_for_ack=False)

        payload = self._wait_result(request_id) or {}
        if payload.get("cancel"):
            return None

        idx = payload.get("index")
        if idx is None:
            return None
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return None
        if 0 <= idx < len(available_cards):
            return available_cards[idx]
        return None

    def select_targets(self, available_targets: List[int], card: Optional[Card] = None) -> List[int]:
        """选择目标玩家。

        Args:
            available_targets: 可选目标玩家 ID 列表。
            card: 当前要使用的牌对象。

        Returns:
            选中的目标玩家 ID 列表。
        """
        if not available_targets:
            return []

        if self._use_console_mode():
            return self._select_targets_console(available_targets)

        request_id = self._start_request()
        options = {
            "targets": available_targets,
            "card_name": str(card.name_enum) if card else None,
        }
        req = InputRequestEvent(
            request_id=request_id,
            player_id=self.player_id,
            action="select_targets",
            prompt="请选择目标",
            options=options,
        )
        if communicator is not None:
            communicator.send_to_frontend(req, wait_for_ack=False)

        payload = self._wait_result(request_id) or {}
        if payload.get("cancel"):
            return []

        target_ids = payload.get("target_ids", [])
        result: List[int] = []
        for t in target_ids:
            try:
                tid = int(t)
            except (TypeError, ValueError):
                continue
            if tid in available_targets and tid not in result:
                result.append(tid)
        return result

    def select_cards_to_discard(self, hand_cards: List[Card], count: int) -> List[Card]:
        """选择要弃置的牌。

        Args:
            hand_cards: 手牌列表。
            count: 需要弃置的数量。

        Returns:
            被弃置的牌列表。
        """
        if count <= 0 or not hand_cards:
            return []

        if self._use_console_mode():
            return self._select_discard_console(hand_cards, count)

        request_id = self._start_request()
        options = {
            "count": count,
            "cards": [
                {
                    "index": i,
                    "name": str(c.name_enum),
                    "suit": getattr(c, "suit", None).name if getattr(c, "suit", None) else None,
                    "rank": getattr(c, "rank", None),
                }
                for i, c in enumerate(hand_cards)
            ],
        }
        req = InputRequestEvent(
            request_id=request_id,
            player_id=self.player_id,
            action="discard",
            prompt=f"请选择要弃置的 {count} 张牌",
            options=options,
        )
        if communicator is not None:
            communicator.send_to_frontend(req, wait_for_ack=False)

        payload = self._wait_result(request_id) or {}
        indices = payload.get("indices", [])
        idxs: List[int] = []
        for x in indices:
            try:
                i = int(x)
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(hand_cards) and i not in idxs:
                idxs.append(i)
        if len(idxs) != count:
            # 不够就尽量少弃；你也可以在这里强制重新请求
            pass
        return [hand_cards[i] for i in idxs]

    def select_cards_to_discard_any(
        self,
        hand_cards: List[Card],
        max_count: int,
        min_count: int = 0,
        context: str = "",
    ) -> List[Card]:
        """选择要弃置的若干张牌（数量可变）。

        Args:
            hand_cards: 手牌列表。
            max_count: 最多可弃置数量。
            min_count: 最少必须弃置数量。
            context: 上下文提示信息。

        Returns:
            被弃置的牌列表。
        """
        if not hand_cards:
            return []
        max_n = max(0, min(int(max_count), len(hand_cards)))
        min_n = max(0, min(int(min_count), max_n))

        if self._use_console_mode():
            return self._select_discard_any_console(hand_cards, min_n, max_n, context)

        request_id = self._start_request()
        options = {
            "min_count": min_n,
            "count": max_n,
            "allow_less": True,
            "cards": [
                {
                    "index": i,
                    "name": str(c.name_enum),
                    "suit": getattr(c, "suit", None).name if getattr(c, "suit", None) else None,
                    "rank": getattr(c, "rank", None),
                }
                for i, c in enumerate(hand_cards)
            ],
        }
        req = InputRequestEvent(
            request_id=request_id,
            player_id=self.player_id,
            action="discard",
            prompt=context or f"请选择要弃置的牌（{min_n}~{max_n} 张，回车确认）",
            options=options,
        )
        if communicator is not None:
            communicator.send_to_frontend(req, wait_for_ack=False)

        payload = self._wait_result(request_id) or {}
        if payload.get("cancel"):
            return []

        indices = payload.get("indices", [])
        idxs: List[int] = []
        for x in indices:
            try:
                i = int(x)
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(hand_cards) and i not in idxs:
                idxs.append(i)

        if len(idxs) < min_n:
            return []
        if len(idxs) > max_n:
            idxs = idxs[:max_n]
        return [hand_cards[i] for i in idxs]

    def ask_use_card_response(
        self,
        card_name: CardName,
        available_cards: List[Card],
        context: str = ""
    ) -> Optional[Card]:
        """询问是否打出响应牌。

        Args:
            card_name: 需要响应的牌名。
            available_cards: 可用于响应的牌列表。
            context: 上下文提示信息。

        Returns:
            打出的牌；若不响应则返回 None。
        """
        if not available_cards:
            return None

        if self._use_console_mode():
            return self._ask_response_console(card_name, available_cards)

        request_id = self._start_request()
        options = {
            "need_card_name": str(card_name),
            "cards": [
                {
                    "index": i,
                    "name": str(c.name_enum),
                    "suit": getattr(c, "suit", None).name if getattr(c, "suit", None) else None,
                    "rank": getattr(c, "rank", None),
                }
                for i, c in enumerate(available_cards)
            ],
        }
        req = InputRequestEvent(
            request_id=request_id,
            player_id=self.player_id,
            action="ask_use_card_response",
            prompt=context or f"是否打出 {card_name}？",
            options=options,
        )
        if communicator is not None:
            communicator.send_to_frontend(req, wait_for_ack=False)

        payload = self._wait_result(request_id) or {}
        if payload.get("cancel"):
            return None

        idx = payload.get("index")
        if idx is None:
            return None
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return None
        if 0 <= idx < len(available_cards):
            return available_cards[idx]
        return None

    def ask_activate_skill(self, skill_name: str, context: dict) -> bool:
        """询问是否发动技能。

        Args:
            skill_name: 技能名称。
            context: 上下文信息字典。

        Returns:
            是否发动该技能。
        """
        if self._use_console_mode():
            raw = input(f"[HUMAN] 发动技能 {skill_name}? (y/n) ").strip().lower()
            return raw in ("y", "yes", "1", "true")

        request_id = self._start_request()
        options = {
            "skill_name": skill_name,
            "context": context,
        }
        req = InputRequestEvent(
            request_id=request_id,
            player_id=self.player_id,
            action="ask_activate_skill",
            prompt=f"是否发动技能 {skill_name}？",
            options=options,
        )
        if communicator is not None:
            communicator.send_to_frontend(req, wait_for_ack=False)

        payload = self._wait_result(request_id) or {}
        # 要么直接传 {"activate": bool}，要么传 {"cancel": True}
        if "activate" in payload:
            return bool(payload["activate"])
        if payload.get("cancel"):
            return False
        return False

    # ===================== 事件入口：由 ControlManager 调用 =====================

    def on_event(self, event) -> None:
        """处理来自前端的输入响应事件。

        Args:
            event: 通信事件对象。

        Returns:
            None
        """
        # 只关心 InputResponseEvent
        if not isinstance(event, InputResponseEvent):
            return
        if event.player_id != self.player_id:
            return

        with self._lock:
            if event.request_id != self._pending_request_id:
                return
            # 把前端 payload 存起来，唤醒等待中的请求
            self._pending_payload = event.payload or {}
            self._pending_request_id = None
            self._cv.notify_all()

    # ===================== 内部工具方法 =====================

    def _use_console_mode(self) -> bool:
        """判断当前是否使用控制台模式。

        Args:
            None

        Returns:
            若处于“纯后端”运行（未启用前后端通信）则返回 True。
        """
        # 说明：
        # - 是否走“控制台模式”的关键不在 ack 配置，而在于有没有前后端通信通道。
        # - 单元测试会注入 communicator 来做事件往返验证；此时必须走事件模式。
        return communicator is None

    def _start_request(self) -> str:
        """开始一次新的前端请求。

        Args:
            None

        Returns:
            生成的请求 ID。
        """
        with self._lock:
            self._pending_payload = None
            self._pending_request_id = uuid.uuid4().hex
            return self._pending_request_id

    def _wait_result(self, request_id: str) -> Optional[Dict[str, Any]]:
        """阻塞等待前端响应。

        Args:
            request_id: 本次请求的唯一 ID。

        Returns:
            前端返回的 payload 字典；若异常则返回 None。
        """
        with self._lock:
            while self._pending_request_id == request_id and self._pending_payload is None:
                self._cv.wait(timeout=0.1)
            return self._pending_payload

    # ===================== 控制台模式下的实现（你原来的代码搬过来即可） =====================

    def _select_card_console(self, available_cards: List[Card]) -> Optional[Card]:
        """控制台模式：选择要出的牌。

        Args:
            available_cards: 可选牌列表。

        Returns:
            选中的牌；若不出牌则返回 None。
        """
        print("\n[HUMAN] 请选择要出的牌：-1 放弃")
        for i, c in enumerate(available_cards):
            print(f"  {i}: {c}")
        while True:
            raw = input("card_index = ").strip()
            try:
                idx = int(raw)
            except ValueError:
                continue
            if idx == -1:
                return None
            if 0 <= idx < len(available_cards):
                return available_cards[idx]

    def _select_targets_console(self, available_targets: List[int]) -> List[int]:
        """控制台模式：选择目标玩家。

        Args:
            available_targets: 可选目标玩家 ID 列表。

        Returns:
            选中的目标玩家 ID 列表。
        """
        print("\n[HUMAN] 请选择目标，逗号分隔；直接回车表示不选")
        print("targets =", available_targets)
        raw = input("target_ids = ").strip()
        if not raw:
            return []
        result: List[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                tid = int(part)
            except ValueError:
                continue
            if tid in available_targets and tid not in result:
                result.append(tid)
        return result

    def _select_discard_console(self, hand_cards: List[Card], count: int) -> List[Card]:
        """控制台模式：选择要弃置的牌。

        Args:
            hand_cards: 手牌列表。
            count: 需要弃置的数量。

        Returns:
            被弃置的牌列表。
        """
        print(f"\n[HUMAN] 请选择要弃置的牌（需要 {count} 张），逗号分隔：")
        for i, c in enumerate(hand_cards):
            print(f"  {i}: {c}")
        while True:
            raw = input("discard_indexes = ").strip()
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            idxs: List[int] = []
            ok = True
            for p in parts:
                try:
                    idx = int(p)
                except ValueError:
                    ok = False
                    break
                if idx < 0 or idx >= len(hand_cards) or idx in idxs:
                    ok = False
                    break
                idxs.append(idx)
            if ok and len(idxs) == count:
                return [hand_cards[i] for i in idxs]

    def _select_discard_any_console(
        self,
        hand_cards: List[Card],
        min_count: int,
        max_count: int,
        context: str = "",
    ) -> List[Card]:
        """控制台模式：选择要弃置的若干张牌（数量可变）。

        Args:
            hand_cards: 手牌列表。
            min_count: 最少必须弃置数量。
            max_count: 最多可弃置数量。
            context: 上下文提示信息。

        Returns:
            被弃置的牌列表。
        """
        print(f"\n[HUMAN] {context or '请选择要弃置的牌'}（{min_count}~{max_count} 张），逗号分隔；直接回车表示不弃")
        for i, c in enumerate(hand_cards):
            print(f"  {i}: {c}")
        while True:
            raw = input("discard_indexes = ").strip()
            if not raw:
                return [] if min_count == 0 else []
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            idxs: List[int] = []
            ok = True
            for p in parts:
                try:
                    idx = int(p)
                except ValueError:
                    ok = False
                    break
                if idx < 0 or idx >= len(hand_cards) or idx in idxs:
                    ok = False
                    break
                idxs.append(idx)
            if not ok:
                continue
            if len(idxs) < min_count or len(idxs) > max_count:
                continue
            return [hand_cards[i] for i in idxs]

    def _ask_response_console(self, card_name: CardName, available_cards: List[Card]) -> Optional[Card]:
        """控制台模式：询问是否打出响应牌。

        Args:
            card_name: 需要响应的牌名。
            available_cards: 可用于响应的牌列表。

        Returns:
            打出的牌；若不响应则返回 None。
        """
        print(f"\n[HUMAN] 是否打出 {card_name}？-1 不打")
        for i, c in enumerate(available_cards):
            print(f"  {i}: {c}")
        while True:
            raw = input("response_index = ").strip()
            try:
                idx = int(raw)
            except ValueError:
                continue
            if idx == -1:
                return None
            if 0 <= idx < len(available_cards):
                return available_cards[idx]
