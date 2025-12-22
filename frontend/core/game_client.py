import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))
import pygame
import threading
import queue
from typing import Optional, Dict, Any
from frontend.util.size import DEFAULT_WINDOW_SIZE
from frontend.util.color import default_colors
from config.enums import EffectName, CardName, EquipmentType, EquipmentName

from frontend.core.renderer import Renderer
from frontend.core.animation_manager import AnimationManager

from config.simple_card_config import SimpleGameConfig
from frontend.config.card_config import CardConfig

from frontend.core.game_state import game_state, GameStateEnum
from communicator.communicator import communicator, AckEvent
from communicator.comm_event import InputRequestEvent, InputResponseEvent

class GameClient:
    def __init__(self, config: SimpleGameConfig, screen: Optional[pygame.Surface]=None, clock: Optional[pygame.time.Clock]=None):
        self.config = config
        self.screen = screen
        self.clock = clock if clock is not None else pygame.time.Clock()

        self.renderer = Renderer(config, self.screen)
        self.animation_mgr = AnimationManager(self.renderer)
        # 当前等待玩家输入的请求（若为 None 表示不在选择中）
        self.pending_input_request: Optional[InputRequestEvent] = None
        self.selected_target_ids = []  # 选择目标时用
        self.selected_card_index = None  # 选择牌时用

    def _handle_selecting_click(self, pos: tuple[int, int]) -> None:
        """SELECTING 状态：根据 pending_input_request 进行选牌/选目标，并回传后端。"""
        req = self.pending_input_request
        if req is None:
            return

        action = getattr(req, "action", "")
        options = getattr(req, "options", {}) or {}

        # 选目标：点角色牌
        if action == "select_targets":
            targets = set(options.get("targets", []))
            pid = self.renderer.get_player_at_position(pos)
            if pid is None or pid not in targets:
                return
            self._submit_input_response({"target_ids": [pid]})
            return

        # 选牌：点手牌（自己的 PlayerView）
        if action in ("select_card", "ask_use_card_response", "discard"):
            self_pv = None
            for pv in self.renderer.player_views:
                if pv.is_self:
                    self_pv = pv
                    break
            if self_pv is None:
                return

            idx = self_pv.pick_hand_card_index_at(pos)
            if idx is None:
                return

            if action == "discard":
                # 最小实现：先支持单选弃牌；如果后端要求 count>1，再扩展为多选
                self._submit_input_response({"indices": [idx]})
            else:
                self._submit_input_response({"index": idx})
            return

        # 是否发动技能：最小实现，点击任意处=发动；ESC=取消
        if action == "ask_activate_skill":
            self._submit_input_response({"activate": True})
            return

    def _submit_input_response(self, payload: dict) -> None:
        """提交 InputResponseEvent 并回到 WAITING。"""
        req = self.pending_input_request
        if req is None:
            return
        communicator.send_to_backend(
            InputResponseEvent(request_id=req.request_id, player_id=req.player_id, payload=payload)
        )
        self.pending_input_request = None
        game_state.set_state(GameStateEnum.WAITING)

    def _select_target_click(self, pos: tuple[int, int], options: dict) -> None:
        """处理选目标点击。

        Args:
            pos: 鼠标坐标。
            options: request.options。

        Returns:
            None
        """
        targets = set(options.get("targets", []))
        pid = self.renderer.get_player_at_position(pos)
        if pid is None or pid not in targets:
            return

        # 最小实现：点中一个就直接提交（单目标）
        self._submit_input_response({"target_ids": [pid]})

    def _select_card_click(self, pos: tuple[int, int], options: dict) -> None:
        """处理选牌点击（选手牌）。

        Args:
            pos: 鼠标坐标。
            options: request.options。

        Returns:
            None
        """
        # 找到自己的 PlayerView
        self_pv = None
        for _, pv in self.renderer.player_views.items():
            if getattr(pv, "is_self", False):
                self_pv = pv
                break
        if self_pv is None:
            return

        # 需要 PlayerView 提供 pick_hand_card_index_at
        idx = getattr(self_pv, "pick_hand_card_index_at", None)
        if idx is None:
            return

        card_index = self_pv.pick_hand_card_index_at(pos)
        if card_index is None:
            return

        # discard 可能要多选，这里先做最小：单选
        action = getattr(self.pending_input_request, "action", "")
        if action == "discard":
            self._submit_input_response({"indices": [card_index]})
        else:
            self._submit_input_response({"index": card_index})


    def after_draw_card(self, card_config: CardConfig, to_player: int, event_id: int):
        # 返回draw_card_event的on_complete调用，处理牌局状态更新等
        player = self.renderer.player_views[to_player]
        player.add_card(card_config)
        player.card_cnt += 1
        communicator.send_to_backend(AckEvent(original_event_id=event_id, success=True, message="Draw card processed"))
        game_state.set_state(GameStateEnum.WAITING)
    def draw_card_event(self, card_config: CardConfig, to_player: int, event_id: int):
        # 处理摸牌事件，添加动画等
        player = self.renderer.player_views[to_player]
        if player.is_self:
            to_pos = player.card_center_pos
        else:
            to_pos = player.character_pos
        face_up = player.is_self
        if to_pos != (None, None):
            self.animation_mgr.add_draw_card_animation(card_config, to_pos, face_up, on_complete=lambda: self.after_draw_card(card_config, to_player, event_id))

    def set_waiting_and_ack(self, event_id: int):
        communicator.send_to_backend(AckEvent(original_event_id=event_id, success=True, message="Event processed"))
        game_state.set_state(GameStateEnum.WAITING)
    def after_play_card(self, card_config: CardConfig, from_player: int, to_player: int, event_id: int):
        # 返回play_card_event的on_complete调用，处理牌局状态更新等
        from_pv = self.renderer.player_views[from_player]
        center_pos = self.renderer.screen_center
        if to_player == -1:
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
            return

        to_pv = self.renderer.player_views[to_player]
        if card_config.name == CardName.SHA:
            effect_pos = to_pv.character_pos
            self.animation_mgr.add_effect(EffectName.HURT, effect_pos, duration_frames=60, on_complete=lambda: game_state.set_state(GameStateEnum.WAITING))
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
        elif card_config.name == CardName.SHAN:
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
        elif card_config.name == CardName.TAO:
            effect_pos = to_pv.character_pos
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
        elif card_config.name == CardName.JUE_DOU:
            effect_pos = to_pv.character_pos
            self.animation_mgr.add_effect(EffectName.BOOM, effect_pos, duration_frames=60, on_complete=lambda: game_state.set_state(GameStateEnum.WAITING))
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60, on_complete= lambda: self.set_waiting_and_ack(event_id=event_id))
        else:
            self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
    def play_card_event(self, card: CardConfig, from_player: int, to_player: int, event_id: int):
        # 处理出牌事件，添加动画等
        from_pv = self.renderer.player_views[from_player]
        from_pv.card_cnt -= 1
        to_pos = self.renderer.screen_center
        if from_pv.is_self:
            from_pos = from_pv.card_center_pos
            from_pv.remove_card(card)
        else:
            from_pos = from_pv.character_pos
            # remove card from self before animation
        if to_pos != (None, None):
            after_lambda = lambda: self.after_play_card(card, from_player, to_player, event_id=event_id)
            self.animation_mgr.add_play_card_animation(card, from_pos, to_pos, on_complete=after_lambda)
    def change_hp_event(self, player_id: int, new_hp: int, event_id: int):
        # 处理血量变化事件，更新显示等
        player = self.renderer.player_views[player_id]
        old_hp = player.get_hp()
        player.update_hp(new_hp)
        if new_hp < old_hp:
            effect_pos = player.character_pos
            self.animation_mgr.add_effect(EffectName.DAMAGE, effect_pos, duration_frames=60, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))
        elif new_hp > old_hp:
            effect_pos = player.character_pos
            self.animation_mgr.add_effect(EffectName.HEAL, effect_pos, duration_frames=60, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))

    def after_discard_card(self, card_config: CardConfig, event_id: int):
        # 处理弃牌后的逻辑
        center_pos = self.renderer.deck_center_pos
        self.animation_mgr.add_show_card(card_config, center_pos, duration_frames=60, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))

    def discard_card_event(self, card: CardConfig, player_id: int, event_id: int):
        # 处理弃牌事件，添加动画等
        player = self.renderer.player_views[player_id]
        if not (card.name.value in EquipmentName._value2member_map_):
            player.card_cnt -= 1
        if player.is_self:
            player.remove_card(card)
        # 添加弃牌动画
        from_pos = player.character_pos if not player.is_self else player.card_center_pos
        to_pos = self.renderer.deck_center_pos
        if to_pos != (None, None):
            self.animation_mgr.add_discard_card_animation(card, from_pos, to_pos, on_complete=lambda: self.after_discard_card(card, event_id=event_id))

    def equip_change_event(self, player_id: int, equip_name: CardName, equip_type: EquipmentType, event_id: int):
        # 处理装备变化事件，更新装备栏等
        player = self.renderer.player_views[player_id]
        player.equipment[equip_type] = equip_name
        game_state.set_state(GameStateEnum.WAITING)
        communicator.send_to_backend(AckEvent(original_event_id=event_id, success=True, message="Equip change processed"))

    def death_event(self, player_id: int, event_id: int):
        # 处理角色死亡事件，播放动画等
        player = self.renderer.player_views[player_id]
        player.dead = True
        game_state.set_state(GameStateEnum.WAITING)
        communicator.send_to_backend(AckEvent(original_event_id=event_id, success=True, message="Death event processed"))
        # effect_pos = player.character_pos
        # self.animation_mgr.add_effect(EffectName.DEATH, effect_pos, duration_frames=90, on_complete=lambda: self.set_waiting_and_ack(event_id=event_id))

    def run(self):
        running = True
        i=0
        game_state.set_state(GameStateEnum.WAITING)
        while running:
            if game_state.state == GameStateEnum.WAITING:
                event = communicator.receive_from_backend()
                if event is not None:
                    event_id = getattr(event, '_event_id', None)
                    if type(event).__name__ == "DrawCardEvent":
                        simple_card_cfg = event.card_config
                        card_cfg = CardConfig(card_name=simple_card_cfg.name, suit=simple_card_cfg.suit, rank=simple_card_cfg.rank)
                        self.draw_card_event(card_cfg, event.to_player, event_id=event_id)
                    elif type(event).__name__ == "PlayCardEvent":
                        simple_card_cfg = event.card_config
                        card_cfg = CardConfig(card_name=simple_card_cfg.name, suit=simple_card_cfg.suit, rank=simple_card_cfg.rank)
                        self.play_card_event(card_cfg, event.from_player, event.to_player, event_id=event_id)
                    elif type(event).__name__ == "HPChangeEvent":
                        self.change_hp_event(event.player_id, event.new_hp, event_id=event_id)
                    elif type(event).__name__ == "DiscardCardEvent":
                        print("processing discard card event")
                        simple_card_cfg = event.card_config
                        card_cfg = CardConfig(card_name=simple_card_cfg.name, suit=simple_card_cfg.suit, rank=simple_card_cfg.rank)
                        self.discard_card_event(card_cfg, event.player, event_id=event_id)
                    elif type(event).__name__ == "EquipChangeEvent":
                        self.equip_change_event(event.player_id, event.equip_name, event.equip_type, event_id=event_id)
                    elif type(event).__name__ == "DeathEvent":
                        self.death_event(event.player_id, event_id=event_id)
                        print("Processing death event")
                    elif type(event).__name__ == "InputRequestEvent":
                        # 进入选择状态
                        self.pending_input_request = event
                        game_state.set_state(GameStateEnum.SELECTING)
                    else:
                        pass
                else:
                    # print("No event received, continuing...")
                    pass
            elif game_state.state == GameStateEnum.ANIMATING:
                # print("Animating...")
                pass
            elif game_state.state == GameStateEnum.SELECTING:
                pass
            elif game_state.state == GameStateEnum.PAUSED:
                pass
            elif game_state.state == GameStateEnum.ENDED:
                running = False
            else:
                pass
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.VIDEORESIZE:
                    # 更新窗口大小
                    self.screen = pygame.display.set_mode((ev.w, ev.h), pygame.RESIZABLE)
                    # 通知渲染器更新布局
                    self.renderer.handle_resize(self.screen)
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if game_state.state == GameStateEnum.SELECTING:
                        self._handle_selecting_click(ev.pos)
                elif ev.type == pygame.KEYDOWN:
                    if game_state.state == GameStateEnum.SELECTING and ev.key == pygame.K_ESCAPE:
                        self._submit_input_response({"cancel": True})
            self.animation_mgr.update()
            self.renderer.draw()
            self.clock.tick(30)

        # 退出清理
        self._stop_event.set()
        pygame.quit()
