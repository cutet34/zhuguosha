from typing import Optional,List,Tuple
from typing import Dict
import pygame
from config.simple_card_config import SimpleGameConfig, SimpleCardConfig
from config.enums import CardName
from frontend.util.color import default_colors
from frontend.ui.player_view import PlayerView
from frontend.core.asset_manager import AssetManager
from frontend.ui.card_sprite import CardSprite
from frontend.config.card_config import CardConfig
from frontend.util.size import CARD_SIZE


class Renderer:
    def __init__(self, config: SimpleGameConfig, screen: pygame.Surface):
        self.config = config
        self.screen = screen
        self.bg = pygame.Surface(self.screen.get_size())
        self.bg.fill(default_colors["greybrown"])
        self.asset_mgr = AssetManager()
        self.all_sprites = pygame.sprite.LayeredDirty()
        # Initialize card sprites in deck:
        self.deck_center_pos = self._get_deck_center_pos()
        self.screen_center = (self.screen.get_width() // 2, self.deck_center_pos[1])
        # UI 字体（用于提示/按钮）
        pygame.font.init()
        self.ui_font = pygame.font.SysFont("Microsoft YaHei", 20)
        self.ui_font_small = pygame.font.SysFont("Microsoft YaHei", 16)


        # Initialize player view:
        self.player_views = []
        for i, p_cfg in enumerate(config.players_config):
            is_self = (i == 0)  # 假设第一个玩家是自己
            pv = PlayerView(config, p_cfg, i, is_self, asset_mgr=self.asset_mgr)  # asset_mgr 可选
            self.player_views.append(pv)
    
    def add_sprite(self, sprite: CardSprite):
        self.all_sprites.add(sprite)
    def remove_sprite(self, sprite: CardSprite):
        self.all_sprites.remove(sprite)

    def handle_resize(self, new_screen: pygame.Surface):
        """处理窗口大小改变事件"""
        self.screen = new_screen
        # 重新创建背景
        self.bg = pygame.Surface(self.screen.get_size())
        self.bg.fill(default_colors["greybrown"])
        # 重新计算位置
        self.deck_center_pos = self._get_deck_center_pos()
        self.screen_center = (self.screen.get_width() // 2, self.deck_center_pos[1])
        # 通知所有玩家视图更新位置
        for player_view in self.player_views:
            player_view.handle_resize(self.screen)

    def _get_deck_center_pos(self):
        screen_width, screen_height = pygame.display.get_surface().get_size()
        return (screen_width - 100, screen_height // 2)
    def draw_deck(self, screen: pygame.Surface):
        deck_surf = self.asset_mgr.get_deck_surface()
        rect = deck_surf.get_rect(center=self.deck_center_pos)
        screen.blit(deck_surf, rect.topleft)

    def draw(self, do_flip: bool = True):
        self.screen.blit(self.bg, (0, 0))
        for pv in self.player_views:
            pv.draw(self.screen)
        self.draw_deck(self.screen)
        self.all_sprites.draw(self.screen)
        if do_flip:
            pygame.display.flip()

    def draw_text(
        self,
        text: str,
        pos: tuple[int, int],
        font: Optional[pygame.font.Font] = None,
        color: tuple[int, int, int] = (255, 255, 255),
    ) -> pygame.Rect:
        """绘制文本并返回其矩形区域。

        Args:
            text: 文本内容。
            pos: 左上角坐标 (x, y)。
            font: 字体对象。
            color: 文本颜色。

        Returns:
            文本 Rect。
        """
        if font is None:
            font = self.ui_font
        surf = font.render(text, True, color)
        rect = surf.get_rect(topleft=pos)
        self.screen.blit(surf, rect)
        return rect

    def draw_button(self, rect: pygame.Rect, label: str, enabled: bool = True) -> None:
        """绘制按钮（最小实现：矩形+边框+文字）。

        Args:
            rect: 按钮区域。
            label: 按钮文本。
            enabled: 是否可用。

        Returns:
            None
        """
        bg = (60, 60, 60) if enabled else (35, 35, 35)
        border = (200, 200, 200) if enabled else (120, 120, 120)

        pygame.draw.rect(self.screen, bg, rect, border_radius=10)
        pygame.draw.rect(self.screen, border, rect, width=2, border_radius=10)

        font = self.ui_font
        text_surf = font.render(label, True, (255, 255, 255) if enabled else (180, 180, 180))
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)

    def draw_input_panel(
        self,
        title: str,
        prompt: str,
        selected_lines: List[str],
        confirm_enabled: bool,
        cancel_enabled: bool = True,
    ) -> Dict[str, pygame.Rect]:
        """绘制底部输入面板，并返回按钮 Rect 供命中测试。

        Args:
            title: 面板标题（例如：出牌阶段/弃牌阶段/响应）。
            prompt: 提示文本。
            selected_lines: 当前选择摘要（多行）。
            confirm_enabled: 确认按钮是否可用。
            cancel_enabled: 取消按钮是否可用。

        Returns:
            {"confirm": confirm_rect, "cancel": cancel_rect, "panel": panel_rect}
        """
        w, h = self.screen.get_size()
        panel_w = int(w * 0.46)
        panel_h = int(h * 0.23)
        panel_x = (w - panel_w) // 2
        panel_y = (h - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        # 背景与边框
        pygame.draw.rect(self.screen, (18, 18, 18), panel_rect, border_radius=14)
        pygame.draw.rect(self.screen, (120, 120, 120), panel_rect, width=2, border_radius=14)

        # 标题
        self.draw_text(f"[{title}]", (panel_x + 14, panel_y + 10), font=self.ui_font, color=(255, 220, 140))

        # prompt（太长就截断到两行的感觉）
        p = (prompt or "").replace("\n", " ")
        if len(p) > 90:
            p = p[:90] + "..."
        self.draw_text(p, (panel_x + 14, panel_y + 44), font=self.ui_font_small, color=(230, 230, 230))

        # 已选信息（最多显示 4 行）
        y0 = panel_y + 72
        for i, line in enumerate(selected_lines[:4]):
            self.draw_text(f"- {line}", (panel_x + 14, y0 + i * 18), font=self.ui_font_small, color=(200, 200, 200))

        # 按钮区域
        btn_w, btn_h = 120, 38
        gap = 12
        cancel_rect = pygame.Rect(panel_x + panel_w - btn_w * 2 - gap - 14, panel_y + panel_h - btn_h - 12, btn_w, btn_h)
        confirm_rect = pygame.Rect(panel_x + panel_w - btn_w - 14, panel_y + panel_h - btn_h - 12, btn_w, btn_h)

        self.draw_button(cancel_rect, "取消", enabled=cancel_enabled)
        self.draw_button(confirm_rect, "确认", enabled=confirm_enabled)

        return {"confirm": confirm_rect, "cancel": cancel_rect, "panel": panel_rect}


    def get_player_at_position(self, pos: tuple[int, int]) -> Optional[int]:
        """根据鼠标坐标获取对应玩家ID（命中角色牌区域）。

        Args:
            pos: 鼠标坐标。

        Returns:
            命中的玩家ID，未命中返回 None。
        """
        x, y = pos
        for pv in self.player_views:
            cx, cy = pv.character_pos
            # 角色牌区域按 CARD_SIZE 近似（你绘制武将牌就是这个尺寸）
            rect = pygame.Rect(0, 0, CARD_SIZE[0], CARD_SIZE[1])
            rect.center = (cx, cy)
            if rect.collidepoint(x, y) and not pv.dead:
                return pv.id
        return None