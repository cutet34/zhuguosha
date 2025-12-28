import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

import pygame
import threading
import queue
from typing import Optional, Dict, Any, Iterable, List

from config.enums import EffectName, CardName, EquipmentType, EquipmentName
from frontend.core.renderer import Renderer
from frontend.core.animation_manager import AnimationManager
from config.simple_card_config import SimpleGameConfig
from frontend.config.card_config import CardConfig
from frontend.core.game_state import game_state, GameStateEnum
from communicator.communicator import communicator, AckEvent
from communicator.comm_event import InputRequestEvent, InputResponseEvent


class GameClient:
    """前端客户端：负责接收后端事件、播放动画、并在需要人类输入时显示确认/取消面板。

    重要依赖（你需要先在 Renderer 里实现）：
    1) Renderer.draw(do_flip: bool=True) 允许关闭 flip（SELECTING 时由 GameClient 统一 flip）
    2) Renderer.draw_input_panel(...) -> Dict[str, pygame.Rect] 返回 confirm/cancel 的 rect
    """

    def __init__(
        self,
        config: SimpleGameConfig,
        screen: Optional[pygame.Surface] = None,
        clock: Optional[pygame.time.Clock] = None
    ) -> None:
        """初始化 GameClient。

        Args:
            config: 游戏配置。
            screen: pygame 屏幕对象。
            clock: pygame 时钟对象。

        Returns:
            None
        """
        self.config = config
        self.screen = screen
        self.clock = clock if clock is not None else pygame.time.Clock()

        self.renderer = Renderer(config, self.screen)
        self.animation_mgr = AnimationManager(self.renderer)

        # 当前等待玩家输入的请求（若为 None 表示不在选择中）
        self.pending_input_request: Optional[InputRequestEvent] = None

        # 选择缓存（只选中，不直接提交；提交由“确认”按钮触发）
        self.selected_target_ids: List[int] = []
        self.selected_card_index: Optional[int] = None

        # 弃牌多选
        self.selected_discard_indices: List[int] = []
        self._discard_need_count: int = 0
        self._discard_min_count: int = 0
        self._discard_allow_less: bool = False

        # UI：输入面板按钮区域（由 Renderer.draw_input_panel 返回）
        self._ui_buttons: Dict[str, pygame.Rect] = {}

        # 后端事件接收：线程 + 队列（关键：不管动画/选择都必须收包，否则会漏响应请求）
        self._stop_event = threading.Event()
        self._evt_queue: "queue.Queue[Any]" = queue.Queue()
        self._recv_thread: Optional[threading.Thread] = None

    # -------------------------
    # PlayerView 兼容访问（list / dict）
    # -------------------------

    def _iter_player_views(self) -> Iterable[Any]:
        """统一迭代 Renderer.player_views，兼容 dict / list 两种存储方式。

        Args:
            None

        Returns:
            PlayerView 可迭代对象。
        """
        pvs = getattr(self.renderer, "player_views", None)
        if pvs is None:
            return []
        if isinstance(pvs, dict):
            return pvs.values()
        return pvs

    def _get_player_view(self, player_id: int) -> Optional[Any]:
        """按玩家 ID 获取 PlayerView，兼容 dict / list。

        Args:
            player_id: 玩家 ID。

        Returns:
            对应的 PlayerView；若不存在则返回 None。
        """
        pvs = getattr(self.renderer, "player_views", None)
        if pvs is None:
            return None
        if isinstance(pvs, dict):
            return pvs.get(player_id)
        if isinstance(player_id, int) and 0 <= player_id < len(pvs):
            return pvs[player_id]
        return None

    def _get_self_player_view(self) -> Optional[Any]:
        """获取自己的 PlayerView（is_self=True）。

        Args:
            None

        Returns:
            自己的 PlayerView；若不存在则返回 None。
        """
        for pv in self._iter_player_views():
            if getattr(pv, "is_self", False):
                return pv
        return None

    # -------------------------
    # 后端事件接收：线程/队列
    # -------------------------

    def _recv_loop(self) -> None:
        """后台接收线程：持续从后端收事件并放入队列。

        Args:
            None

        Returns:
            None
        """
        while not self._stop_event.is_set():
            try:
                ev = communicator.receive_from_backend()
            except Exception:
                ev = None
            if ev is not None:
                self._evt_queue.put(ev)
            else:
                pygame.time.wait(5)

    def _drain_backend_events(self) -> None:
        """每帧把队列里的后端事件尽量取空并处理。

        Args:
            None

        Returns:
            None
        """
        while True:
            try:
                ev = self._evt_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_backend_event(ev)

    def _handle_backend_event(self, event: Any) -> None:
        """处理来自后端的事件（动画/状态/输入请求）。

        Args:
            event: 后端事件对象。

        Returns:
            None
        """
        if event is None:
            return

        event_id = getattr(event, "_event_id", None)
        et = type(event).__name__

        if et == "DrawCardEvent":
            simple_card_cfg = event.card_config
            card_cfg = CardConfig(card_name=simple_card_cfg.name, suit=simple_card_cfg.suit, rank=simple_card_cfg.rank)
            self.draw_card_event(card_cfg, event.to_player, event_id=event_id)
            return

        if et == "PlayCardEvent":
            simple_card_cfg = event.card_config
            card_cfg = CardConfig(card_name=simple_card_cfg.name, suit=simple_card_cfg.suit, rank=simple_card_cfg.rank)
            self.play_card_event(card_cfg, event.from_player, event.to_player, event_id=event_id)
            return

        if et == "HPChangeEvent":
            self.change_hp_event(event.player_id, event.new_hp, event_id=event_id)
            return

        if et == "DiscardCardEvent":
            simple_card_cfg = event.card_config
            card_cfg = CardConfig(card_name=simple_card_cfg.name, suit=simple_card_cfg.suit, rank=simple_card_cfg.rank)
            self.discard_card_event(card_cfg, event.player, event_id=event_id)
            return

        if et == "EquipChangeEvent":
            self.equip_change_event(event.player_id, event.equip_name, event.equip_type, event_id=event_id)
            return

        if et == "DeathEvent":
            self.death_event(event.player_id, event_id=event_id)
            return

        if et == "InputRequestEvent":
            # 进入选择状态：清空上一轮选择缓存
            self.pending_input_request = event

            self.selected_target_ids = []
            self.selected_card_index = None
            self.selected_discard_indices = []

            self._discard_need_count = 0
            self._discard_min_count = 0
            self._discard_allow_less = False

            try:
                action = getattr(event, "action", "")
                options = getattr(event, "options", {}) or {}
                if action == "discard":
                    self._discard_need_count = int(options.get("count", 0) or 0)
                    self._discard_min_count = int(options.get("min_count", self._discard_need_count) or 0)
                    self._discard_allow_less = bool(options.get("allow_less", False))
            except Exception:
                pass

            game_state.set_state(GameStateEnum.SELECTING)
            return

    # -------------------------
    # 输入面板：渲染/命中/提交
    # -------------------------

    def _action_title(self, action: str) -> str:
        """将 action 映射为面板标题。

        Args:
            action: 后端请求动作名。

        Returns:
            标题字符串。
        """
        return {
            "select_card": "出牌阶段",
            "select_targets": "选择目标",
            "discard": "弃牌阶段",
            "ask_use_card_response": "回合外响应",
            "ask_activate_skill": "技能询问",
        }.get(action, "选择")

    def _render_input_panel(self) -> None:
        """SELECTING 状态下绘制输入面板，并缓存按钮 rect。

        Args:
            None

        Returns:
            None
        """
        req = self.pending_input_request
        if req is None:
            self._ui_buttons = {}
            return

        action = getattr(req, "action", "")
        prompt = getattr(req, "prompt", "") or ""
        title = self._action_title(action)

        selected_lines: List[str] = []
        confirm_enabled = False

        if action in ("select_card", "ask_use_card_response"):
            if self.selected_card_index is None:
                selected_lines.append("未选择牌")
                # 允许确认：不选牌确认=结束出牌 / 不响应
                confirm_enabled = True
            else:
                selected_lines.append(f"已选牌：index={self.selected_card_index}")
                confirm_enabled = True

        elif action == "select_targets":
            if not self.selected_target_ids:
                selected_lines.append("未选择目标")
                confirm_enabled = False
            else:
                selected_lines.append(f"已选目标：{self.selected_target_ids}")
                confirm_enabled = True

        elif action == "discard":
            selected_lines.append(f"已选弃牌：{len(self.selected_discard_indices)} 张")
            if self._discard_allow_less:
                selected_lines.append(f"至少 {self._discard_min_count} 张（可少弃）")
                confirm_enabled = len(self.selected_discard_indices) >= self._discard_min_count
            else:
                selected_lines.append(f"需要 {self._discard_need_count} 张")
                confirm_enabled = len(self.selected_discard_indices) == self._discard_need_count

        elif action == "ask_activate_skill":
            selected_lines.append("确认=发动；取消=不发动")
            confirm_enabled = True

        # 注意：Renderer.draw_input_panel 必须返回 confirm/cancel rect
        self._ui_buttons = self.renderer.draw_input_panel(
            title=title,
            prompt=prompt,
            selected_lines=selected_lines,
            confirm_enabled=confirm_enabled,
            cancel_enabled=True,
        )

    def _submit_input_response(self, payload: dict) -> None:
        """提交 InputResponseEvent 并退出选择态。

        Args:
            payload: 回传给后端的 payload。

        Returns:
            None
        """
        req = self.pending_input_request
        if req is None:
            return

        communicator.send_to_backend(
            InputResponseEvent(request_id=req.request_id, player_id=req.player_id, payload=payload)
        )

        # 清理选择态
        self.pending_input_request = None
        self._ui_buttons = {}

        self.selected_target_ids = []
        self.selected_card_index = None
        self.selected_discard_indices = []
        self._discard_need_count = 0
        self._discard_min_count = 0
        self._discard_allow_less = False

        game_state.set_state(GameStateEnum.WAITING)

    def _submit_confirm(self) -> None:
        """点击“确认”后的提交逻辑（根据 action 生成 payload）。

        Args:
            None

        Returns:
            None
        """
        req = self.pending_input_request
        if req is None:
            return
        action = getattr(req, "action", "")

        if action in ("select_card", "ask_use_card_response"):
            if self.selected_card_index is None:
                # 不选牌确认：结束出牌 / 不响应
                self._submit_input_response({"cancel": True})
            else:
                self._submit_input_response({"index": int(self.selected_card_index)})
            return

        if action == "select_targets":
            if not self.selected_target_ids:
                return
            self._submit_input_response({"target_ids": list(self.selected_target_ids)})
            return

        if action == "discard":
            self._submit_input_response({"indices": list(self.selected_discard_indices)})
            return

        if action == "ask_activate_skill":
            self._submit_input_response({"activate": True})
            return

    def _handle_cancel(self) -> None:
        """点击“取消”后的语义（按 action 区分）。

        约定：
        - ask_use_card_response：取消=不响应（直接回包）
        - ask_activate_skill：取消=不发动（直接回包）
        - 其它（select_card/select_targets/discard）：取消=清空选择，不立刻回包

        Args:
            None

        Returns:
            None
        """
        req = self.pending_input_request
        if req is None:
            return
        action = getattr(req, "action", "")

        if action == "ask_use_card_response":
            self._submit_input_response({"cancel": True})
            return

        if action == "ask_activate_skill":
            self._submit_input_response({"activate": False})
            return

        # 其它动作：只清空选择（让你继续选，不会误结束阶段）
        self.selected_target_ids = []
        self.selected_card_index = None
        self.selected_discard_indices = []

    def _handle_ui_click(self, pos: tuple[int, int]) -> bool:
        """在 SELECTING 状态下优先处理面板按钮点击。

        Args:
            pos: 鼠标坐标。

        Returns:
            是否已消费本次点击（True 表示点在按钮上）。
        """
        if not self._ui_buttons or self.pending_input_request is None:
            return False

        cancel_rect = self._ui_buttons.get("cancel")
        confirm_rect = self._ui_buttons.get("confirm")

        if cancel_rect is not None and cancel_rect.collidepoint(pos):
            self._handle_cancel()
            return True

        if confirm_rect is not None and confirm_rect.collidepoint(pos):
            self._submit_confirm()
            return True

        return False

    # -------------------------
    # SELECTING：场景点击（只选中，不提交）
    # -------------------------

    def _handle_selecting_click(self, pos: tuple[int, int]) -> None:
        """SELECTING 状态：点牌/点人只更新选择，不直接提交。

        Args:
            pos: 鼠标坐标。

        Returns:
            None
        """
        req = self.pending_input_request
        if req is None:
            return

        action = getattr(req, "action", "")
        options = getattr(req, "options", {}) or {}

        # 选目标：点角色牌 -> 只选中
        if action == "select_targets":
            targets = set(options.get("targets", []))
            pid = self.renderer.get_player_at_position(pos)
            if pid is None or pid not in targets:
                return
            self.selected_target_ids = [pid]
            return

        # 选牌：点手牌 -> 只选中
        if action in ("select_card", "ask_use_card_response", "discard"):
            self_pv = self._get_self_player_view()
            if self_pv is None:
                return

            idx = self_pv.pick_hand_card_index_at(pos)
            if idx is None:
                return

            if action == "discard":
                # 多选弃牌：点击切换选中
                if idx in self.selected_discard_indices:
                    self.selected_discard_indices.remove(idx)
                else:
                    self.selected_discard_indices.append(idx)
                return

            self.selected_card_index = idx
            return

        # 技能询问：不在这里处理（用确认/取消按钮）
        return

    # -------------------------
    # 事件动画处理（你原来的逻辑基本不动，只做 PlayerView 访问兼容）
    # -------------------------

    def after_draw_card(self, card_config: CardConfig, to_player: int, event_id: int) -> None:
        """摸牌动画结束回调：更新状态并 ACK。

        Args:
            card_config: 牌配置。
            to_player: 玩家 ID。
            event_id: 事件 ID。

        Returns:
            None
        """
        player = self._get_player_view(to_player)
        if player is None:
            return
        player.add_card(card_config)
        player.card_cnt += 1
        communicator.send_to_backend(AckEvent(original_event_id=event_id, success=True, message="Draw card processed"))
        game_state.set_state(GameStateEnum.WAITING)

    def draw_card_event(self, card_config: CardConfig, to_player: int, event_id: int) -> None:
        """处理摸牌事件：播放动画。

        Args:
            card_config: 牌配置。
            to_player: 玩家 ID。
            event_id: 事件 ID。

        Returns:
            None
        """
        player = self._get_player_view(to_player)
        if player is None:
            return
        to_pos = player.card_center_pos if player.is_self else player.character_pos
        face_up = player.is_self
        if to_pos != (None, None):
            self.animation_mgr.add_draw_card_animation(
                card_config,
                to_pos,
                face_up,
                on_complete=lambda: self.after_draw_card(card_config, to_player, event_id)
            )

    def set_waiting_and_ack(self, event_id: int) -> None:
        """通用：ACK 并回到 WAITING。

        Args:
            event_id: 事件 ID。

        Returns:
            None
        """
        communicator.send_to_backend(AckEvent(original_event_id=event_id, success=True, message="Event processed"))
        game_state.set_state(GameStateEnum.WAITING)

    def after_play_card(self, card_config: CardConfig, from_player: int, to_player: int, event_id: int) -> None:
        """出牌动画结束后的处理：显示牌/特效并 ACK。

        Args:
            card_config: 牌配置。
            from_player: 出牌者 ID。
            to_player: 目标 ID。
            event_id: 事件 ID。

        Returns:
            None
        """
        from_pv = self._get_player_view(from_player)
        if from_pv is None:
            return
        center_pos = self.renderer.screen_center

        if to_player == -1:
            self.animation_mgr.add_show_card(
                card_config, center_pos, duration_frames=60,
                on_complete=lambda: self.set_waiting_and_ack(event_id=event_id)
            )
            return

        to_pv = self._get_player_view(to_player)
        if to_pv is None:
            return

        if card_config.name == CardName.SHA:
            self.animation_mgr.add_effect(EffectName.HURT, to_pv.character_pos, duration_frames=60,
                                          on_complete=lambda: game_state.set_state(GameStateEnum.WAITING))
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60,
                                             on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
        elif card_config.name == CardName.JUE_DOU:
            self.animation_mgr.add_effect(EffectName.BOOM, to_pv.character_pos, duration_frames=60,
                                          on_complete=lambda: game_state.set_state(GameStateEnum.WAITING))
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60,
                                             on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
        else:
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60,
                                             on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))

    def play_card_event(self, card: CardConfig, from_player: int, to_player: int, event_id: int) -> None:
        """处理出牌事件：播放移动动画。

        Args:
            card: 牌配置。
            from_player: 出牌者 ID。
            to_player: 目标 ID。
            event_id: 事件 ID。

        Returns:
            None
        """
        from_pv = self._get_player_view(from_player)
        if from_pv is None:
            return
        from_pv.card_cnt -= 1

        to_pos = self.renderer.screen_center
        if from_pv.is_self:
            from_pos = from_pv.card_center_pos
            from_pv.remove_card(card)
        else:
            from_pos = from_pv.character_pos

        if to_pos != (None, None):
            self.animation_mgr.add_play_card_animation(
                card, from_pos, to_pos,
                on_complete=lambda: self.after_play_card(card, from_player, to_player, event_id=event_id)
            )

    def change_hp_event(self, player_id: int, new_hp: int, event_id: int) -> None:
        """处理血量变化事件。

        Args:
            player_id: 玩家 ID。
            new_hp: 新血量。
            event_id: 事件 ID。

        Returns:
            None
        """
        player = self._get_player_view(player_id)
        if player is None:
            return
        old_hp = player.get_hp()
        player.update_hp(new_hp)

        if new_hp < old_hp:
            self.animation_mgr.add_effect(EffectName.DAMAGE, player.character_pos, duration_frames=60,
                                          on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
        elif new_hp > old_hp:
            self.animation_mgr.add_effect(EffectName.HEAL, player.character_pos, duration_frames=60,
                                          on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))

    def after_discard_card(self, card_config: CardConfig, event_id: int) -> None:
        """弃牌动画结束回调：show 并 ACK。

        Args:
            card_config: 牌配置。
            event_id: 事件 ID。

        Returns:
            None
        """
        center_pos = self.renderer.deck_center_pos
        self.animation_mgr.add_show_card(
            card_config, center_pos, duration_frames=60,
            on_complete=lambda: self.set_waiting_and_ack(event_id=event_id)
        )

    def discard_card_event(self, card: CardConfig, player_id: int, event_id: int) -> None:
        """处理弃牌事件。

        Args:
            card: 牌配置。
            player_id: 玩家 ID。
            event_id: 事件 ID。

        Returns:
            None
        """
        player = self._get_player_view(player_id)
        if player is None:
            return

        if not (card.name.value in EquipmentName._value2member_map_):
            player.card_cnt -= 1
        if player.is_self:
            player.remove_card(card)

        from_pos = player.character_pos if not player.is_self else player.card_center_pos
        to_pos = self.renderer.deck_center_pos
        if to_pos != (None, None):
            self.animation_mgr.add_discard_card_animation(
                card, from_pos, to_pos,
                on_complete=lambda: self.after_discard_card(card, event_id=event_id)
            )

    def equip_change_event(self, player_id: int, equip_name: CardName, equip_type: EquipmentType, event_id: int) -> None:
        """处理装备变化事件。

        Args:
            player_id: 玩家 ID。
            equip_name: 装备名。
            equip_type: 装备类型。
            event_id: 事件 ID。

        Returns:
            None
        """
        player = self._get_player_view(player_id)
        if player is None:
            return
        player.equipment[equip_type] = equip_name
        game_state.set_state(GameStateEnum.WAITING)
        communicator.send_to_backend(AckEvent(original_event_id=event_id, success=True, message="Equip change processed"))

    def death_event(self, player_id: int, event_id: int) -> None:
        """处理死亡事件。

        Args:
            player_id: 玩家 ID。
            event_id: 事件 ID。

        Returns:
            None
        """
        player = self._get_player_view(player_id)
        if player is None:
            return
        player.dead = True
        game_state.set_state(GameStateEnum.WAITING)
        communicator.send_to_backend(AckEvent(original_event_id=event_id, success=True, message="Death event processed"))

    # -------------------------
    # 主循环
    # -------------------------

    def run(self) -> None:
        """运行主循环。

        Args:
            None

        Returns:
            None
        """
        running = True
        game_state.set_state(GameStateEnum.WAITING)

        # 启动后端事件接收线程
        if self._recv_thread is None:
            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()

        while running:
            # 1) 每帧都处理后端事件（关键：动画/选择阶段也不漏）
            self._drain_backend_events()

            # 2) 处理 pygame 输入
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False

                elif ev.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode((ev.w, ev.h), pygame.RESIZABLE)
                    self.renderer.handle_resize(self.screen)

                elif ev.type == pygame.MOUSEBUTTONDOWN and game_state.state == GameStateEnum.SELECTING:
                    # 先处理 UI 面板按钮命中（确认/取消）
                    if self._handle_ui_click(ev.pos):
                        continue
                    # 再处理场景点击（只更新选择）
                    if ev.button == 1:
                        self._handle_selecting_click(ev.pos)

                elif ev.type == pygame.KEYDOWN and game_state.state == GameStateEnum.SELECTING:
                    req = self.pending_input_request
                    action = getattr(req, "action", "") if req else ""

                    # ESC：按 action 区分语义（响应/技能：直接否决；其它：清空选择）
                    if ev.key == pygame.K_ESCAPE:
                        self._handle_cancel()

                    # 回车：等价于点击“确认”
                    elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._submit_confirm()

                    # Y/N：技能询问快捷键
                    elif action == "ask_activate_skill" and ev.key in (pygame.K_y, pygame.K_n):
                        self._submit_input_response({"activate": ev.key == pygame.K_y})

                    # 退格：清空弃牌选择
                    elif action == "discard" and ev.key == pygame.K_BACKSPACE:
                        self.selected_discard_indices = []

            # 3) 动画更新
            self.animation_mgr.update()

            # 4) 渲染：SELECTING 时额外绘制输入面板（并保证 flip 时机正确）
            if game_state.state == GameStateEnum.SELECTING and self.pending_input_request is not None:
                # Renderer.draw 需要支持 do_flip=False
                self.renderer.draw(do_flip=False)
                self._render_input_panel()
                pygame.display.flip()
            else:
                self.renderer.draw()

            self.clock.tick(30)

        # 退出清理
        self._stop_event.set()
        pygame.quit()
