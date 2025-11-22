import pygame
from config.simple_card_config import SimpleGameConfig, SimpleCardConfig
from config.enums import CardName
from frontend.util.color import default_colors
from frontend.ui.player_view import PlayerView
from frontend.core.asset_manager import AssetManager
from frontend.ui.card_sprite import CardSprite
from frontend.config.card_config import CardConfig
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

    def draw(self):
        self.screen.blit(self.bg, (0, 0))
        for pv in self.player_views:
            pv.draw(self.screen)
        self.draw_deck(self.screen)
        # Update dirty sprites
        self.all_sprites.draw(self.screen)
        pygame.display.flip()