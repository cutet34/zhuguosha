import pygame
from pygame.sprite import DirtySprite
from frontend.config.card_config import CardConfig
from config.card_properties import get_card_properties
from frontend.util.color import default_colors

class CardSprite(DirtySprite):
    """
    卡牌精灵，继承 DirtySprite。负责图像、rect、基本动画（位置、翻转）、交互。
    属性约定：
      - self.image: 当前 Surface（DirtySprite 需要）
      - self.rect: 当前 rect（DirtySprite 需要）
    """

    def __init__(self, pos, config: CardConfig, face_up: bool, speed: float, asset_mgr=None):
        super().__init__()
        self.config = config  # CardConfig 对象，包含 name, suit, rank
        properties = get_card_properties(config.name)
        self.name = properties["display_name"]
        self.card_type = properties["card_type"]  # 牌类型（基本/锦囊/装备）

        self.asset_mgr = asset_mgr  # 资源管理器（可选）
        if asset_mgr:
            self.back_surface = asset_mgr.get_card_back()
            self.front_surface = asset_mgr.get_card_surface(config.name)

        self.pos = pos
        self.rect = self.back_surface.get_rect(center=pos)
        self.face_up = face_up  # 是否正面朝上
        self.image = self.front_surface if face_up else self.back_surface  # 初始显示
        self.dirty = 1  # 确保初次绘制

        self.is_animating = False
        self.anim_target = None
        self.anim_speed = speed  # 每帧移动像素

    def draw(self, screen: pygame.Surface):
        screen.blit(self.image, self.rect)

    def start_move_to(self, target_pos):
        self.anim_target = target_pos
        self.is_animating = True


    def update(self):
        self.dirty = 1  # 标记为需要重绘
