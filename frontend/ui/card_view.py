import pygame
from typing import List
from frontend.core.asset_manager import AssetManager
from frontend.config.card_config import CardConfig
from config.card_properties import get_card_properties
from frontend.util.color import default_colors

from frontend.util.size import CARD_SIZE, HP_BAR_SIZE

class CardView:
    def __init__(self, config: CardConfig, asset_mgr: AssetManager):
        self.config = config
        self.asset_mgr = asset_mgr
        properties = get_card_properties(config.name)
        self.name = properties["display_name"]  # 中文显示名称
        self.card_type = properties["card_type"]  # 牌类型（基本/锦囊/装备）
        self.surface = asset_mgr.get_card_surface(config.name)
        self.position = (0, 0)  # 存储当前位置
        self.rect = self.surface.get_rect()


    def draw(self, screen: pygame.Surface, pos):
        self.position = pos
        self.rect.center = pos
        screen.blit(self.surface, self.rect)

    def set_position(self, pos):
        """设置卡牌位置"""
        self.position = pos
        self.rect.center = pos

    def get_rect(self):
        """获取卡牌的矩形区域"""
        return self.rect