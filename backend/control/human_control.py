# 玩家Control实现（命令行版）
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import os
import sys
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.control.control import Control
from backend.card.card import Card
from backend.utils.logger import game_logger
from backend.utils.exceptions import GameException, InvalidInputException
from config.enums import CardName, ControlType, TargetType
from communicator.communicator import communicator
from communicator.comm_event import InputRequestEvent, InputResponseEvent, AckEvent



class HumanControl(Control):
    """玩家操控（HumanControl）。

    当前实现为命令行交互版：用于本地跑通“人类输入”的闭环。
    如果未来 communicator 提供了请求输入的接口，可以在这里优先走 I/O 通道，
    没有则回退到 input()。

    Args:
        player_id: 玩家ID。

    Returns:
        None
    """

    def __init__(self, player_id: int):
        super().__init__(ControlType.HUMAN, player_id)
        self._inbox_buffer: List[Any] = []  # 缓存不属于本次请求的前端消息
    def _prompt(self, text: str) -> str:
        """读取玩家输入。

        Args:
            text: 提示文本。

        Returns:
            玩家输入（去除首尾空白）。
        """
        return input(text).strip()

    def select_card(
        self,
        available_cards: List[Card],
        context: str = "",
        available_targets: Dict[str, List[int]] = None
    ) -> Optional[Card]:
        """选择要出的牌（出牌阶段）。

        约定：
        - 输入空行/0 表示“不出牌（结束出牌阶段）”
        - 其余输入为 1..n 的序号

        Args:
            available_cards: 可选牌列表（从左到右顺序）。
            context: 上下文（一般为空）。
            available_targets: 可用目标（可选）。

        Returns:
            选中的牌，或 None（不出牌）。
        """
        if not available_cards:
            return None
        # 优先走前端
        try:
            payload = self._request_input(
                action="select_card",
                prompt="请选择要出的牌（取消=不出）",
                options={
                    # 前端只需要能显示牌面：用 card.card_config（SimpleCardConfig）
                    "cards": [c.card_config for c in available_cards],
                    "min": 0,
                    "max": 1,
                },
                timeout=60.0,
            )
            if payload.get("cancel"):
                return None
            idx = payload.get("index", None)
            if isinstance(idx, int) and 0 <= idx < len(available_cards):
                return available_cards[idx]
            return None
        except Exception:
            # 前端没接/超时/异常：回退命令行
            pass
        # 命令行回退
        while True:
            try:
                game_logger.log_info(f"[玩家{self.player_id}] 可出牌：")
                for idx, c in enumerate(available_cards, 1):
                    game_logger.log_info(f"  {idx}. {c}")

                s = self._prompt("选择出牌序号（0/空=不出）：")
                if s == "" or s == "0":
                    return None

                if not s.isdigit():
                    raise InvalidInputException(f"不是数字输入：{s}")

                k = int(s)
                if k < 1 or k > len(available_cards):
                    raise InvalidInputException(f"序号超范围：{k}")

                return available_cards[k - 1]
            except GameException as e:
                game_logger.log_warning(f"[玩家{self.player_id}] 输入无效：{e}")

    def select_targets(self, available_targets: List[int], card: Optional[Card] = None) -> List[int]:
        """选择目标。

        说明：
        - 对 TargetType.ALL：不询问，直接返回全部目标
        - 对 TargetType.SELF：不应走到这里（Player 会直接给 self）
        - 其余默认选择 1 个目标；空行/0 表示“取消选择”（返回空列表）

        Args:
            available_targets: 可选目标玩家ID列表。
            card: 当前选择的牌（可选）。

        Returns:
            选择的目标ID列表。
        """
        if not available_targets:
            return []

        # 群体牌不做选择
        if card is not None and getattr(card, "target_type", None) == TargetType.ALL:
            return list(available_targets)
        # 优先走前端
        try:
            payload = self._request_input(
                action="select_targets",
                prompt="请选择目标（取消=不选）",
                options={
                    "targets": list(available_targets),
                    "min": 0,
                    "max": 1,
                    "allow_cancel": True,
                },
                timeout=60.0,
            )
            if payload.get("cancel"):
                return []
            tids = payload.get("target_ids", [])
            if isinstance(tids, list) and all(isinstance(x, int) for x in tids):
                # 限制在可选目标集合内
                s = set(available_targets)
                tids2 = [x for x in tids if x in s]
                return tids2[:1]
            return []
        except Exception:
            pass
        # 命令行回退（你原逻辑）
        while True:
            try:
                game_logger.log_info(f"[玩家{self.player_id}] 可选目标：{available_targets}")
                s = self._prompt("选择目标序号（0/空=取消）：")
                if s == "" or s == "0":
                    return []

                if not s.isdigit():
                    raise InvalidInputException(f"不是数字输入：{s}")

                k = int(s)
                if k < 1 or k > len(available_targets):
                    raise InvalidInputException(f"序号超范围：{k}")

                return [available_targets[k - 1]]
            except GameException as e:
                game_logger.log_warning(f"[玩家{self.player_id}] 输入无效：{e}")

    def select_cards_to_discard(self, hand_cards: List[Card], count: int) -> List[Card]:
        """选择弃牌。

        Args:
            hand_cards: 手牌列表。
            count: 弃牌数量。

        Returns:
            弃掉的牌列表（长度为 count；若输入不足则尽力补齐）。
        """
        if count <= 0 or not hand_cards:
            return []
        # 优先走前端
        try:
            payload = self._request_input(
                action="discard",
                prompt=f"请选择弃牌（需{count}张）",
                options={
                    "cards": [c.card_config for c in hand_cards],
                    "min": count,
                    "max": count,
                },
                timeout=60.0,
            )
            idxs = payload.get("indices", [])
            if isinstance(idxs, list) and len(idxs) == count and all(isinstance(i, int) for i in idxs):
                # 去重 + 合法范围
                if len(set(idxs)) != len(idxs):
                    return []
                if any(i < 0 or i >= len(hand_cards) for i in idxs):
                    return []
                return [hand_cards[i] for i in idxs]
        except Exception:
            pass

        # 命令行回退（你原逻辑）
        while True:
            try:
                game_logger.log_info(f"[玩家{self.player_id}] 手牌：")
                for idx, c in enumerate(hand_cards, 1):
                    game_logger.log_info(f"  {idx}. {c}")

                s = self._prompt(f"选择弃牌序号（用空格分隔，需{count}张）：")
                parts = [p for p in s.split() if p]
                if len(parts) != count:
                    raise InvalidInputException(f"需要{count}个序号，实际给了{len(parts)}个")

                idxs: List[int] = []
                for p in parts:
                    if not p.isdigit():
                        raise InvalidInputException(f"不是数字输入：{p}")
                    k = int(p)
                    if k < 1 or k > len(hand_cards):
                        raise InvalidInputException(f"序号超范围：{k}")
                    idxs.append(k - 1)

                # 去重检查（避免重复弃同一张）
                if len(set(idxs)) != len(idxs):
                    raise InvalidInputException("弃牌序号不能重复")

                return [hand_cards[i] for i in idxs]
            except GameException as e:
                game_logger.log_warning(f"[玩家{self.player_id}] 输入无效：{e}")

    def ask_use_card_response(self, card_name: CardName, available_cards: List[Card], context: str = "") -> Optional[Card]:
        """询问是否使用响应牌。

        Args:
            card_name: 查询的牌名（枚举）。
            available_cards: 可用牌列表（均为 card_name）。
            context: 上下文描述。

        Returns:
            使用的牌或 None（不使用）。
        """
        if not available_cards:
            return None
        try:
            payload = self._request_input(
                action="ask_use_card_response",
                prompt=f"是否打出 {card_name.value}？{f'({context})' if context else ''}（取消=不打）",
                options={
                    "card_name": card_name.value,
                    "context": context,
                    "cards": [c.card_config for c in available_cards],
                    "min": 0,
                    "max": 1,
                    "allow_cancel": True,
                },
                timeout=30.0,  # 响应通常时间更短
            )

            if payload.get("cancel"):
                return None

            idx = payload.get("index", None)
            if isinstance(idx, int) and 0 <= idx < len(available_cards):
                return available_cards[idx]
            return None
        except Exception:
            # 前端没接/超时/异常：回退命令行
            pass
        while True:
            try:
                game_logger.log_info(f"[玩家{self.player_id}] 是否打出 {card_name.value}？({context})")
                for idx, c in enumerate(available_cards, 1):
                    game_logger.log_info(f"  {idx}. {c}")

                s = self._prompt("选择序号（0/空=不打）：")
                if s == "" or s == "0":
                    return None
                if not s.isdigit():
                    raise InvalidInputException(f"不是数字输入：{s}")
                k = int(s)
                if k < 1 or k > len(available_cards):
                    raise InvalidInputException(f"序号超范围：{k}")
                return available_cards[k - 1]
            except GameException as e:
                game_logger.log_warning(f"[玩家{self.player_id}] 输入无效：{e}")

    def ask_activate_skill(self, skill_name: str, context: dict) -> bool:
        """询问是否发动技能。

        Args:
            skill_name: 技能名。
            context: 技能上下文（字典）。

        Returns:
            是否发动。
        """
        try:
            payload = self._request_input(
                action="ask_activate_skill",
                prompt=f"是否发动技能？（取消=不发动）",
                options={
                    "skill_name": skill_name,
                    "context": context,
                    "allow_cancel": True,
                },
                timeout=30.0,
            )

            # 约定：payload {"activate": bool} 或 {"cancel": True}
            if payload.get("cancel"):
                return False
            activate = payload.get("activate", False)
            return bool(activate)
        except Exception:
            pass
        s = self._prompt(f"是否发动技能？(y/N)：")
        return s.lower() in ("y", "yes", "1", "true")

    def _request_input(self, action: str, prompt: str, options: Dict[str, Any], timeout: float = 60.0) -> Dict[
        str, Any]:
        """向前端请求一次输入并等待响应。

        Args:
            action: 输入行为类型。
            prompt: 提示文本。
            options: 可选项数据。
            timeout: 超时秒数。

        Returns:
            前端返回的 payload 字典。

        Raises:
            TimeoutError: 等待前端响应超时。
        """
        request_id = uuid.uuid4().hex
        communicator.send_to_frontend(
            InputRequestEvent(
                request_id=request_id,
                player_id=self.player_id,
                action=action,
                prompt=prompt,
                options=options,
            ),
            wait_for_ack=False,  # 这里不要用 ACK 来代表“选完了”
        )

        # 等待匹配的 InputResponseEvent
        deadline = time.time() + timeout
        # 先处理缓存里是否已经有匹配的 response（理论上少见，但安全）
        i = 0
        while i < len(self._inbox_buffer):
            evt = self._inbox_buffer[i]
            if isinstance(evt, InputResponseEvent) and evt.request_id == request_id and evt.player_id == self.player_id:
                self._inbox_buffer.pop(i)
                return evt.payload or {}
            i += 1
        while time.time() < deadline:
            evt = communicator.receive_from_frontend()
            if evt is None:
                time.sleep(0.01)
                continue

            # 忽略 ACK（ACK 线程会处理）
            if isinstance(evt, AckEvent):
                continue

            if isinstance(evt, InputResponseEvent) and evt.request_id == request_id and evt.player_id == self.player_id:
                return evt.payload or {}
            # 不是本次请求的 response：缓存起来，避免吞掉
            self._inbox_buffer.append(evt)

            # 其他消息：丢弃或缓存均可；最小实现先丢弃
        raise TimeoutError(f"等待前端输入超时：action={action}, player_id={self.player_id}")