import pygame
from pygame.sprite import DirtySprite
from config.enums import EffectName

class EffectSprite(DirtySprite):
    """
    特效精灵，继承 DirtySprite。负责图像、rect、基本动画（位置、翻转）、交互。
    属性约定：
      - self.image: 当前 Surface（DirtySprite 需要）
      - self.rect: 当前 rect（DirtySprite 需要）
    """

    def __init__(self, pos, code:EffectName, asset_mgr=None):
        super().__init__()
        self.code = code
        self.asset_mgr = asset_mgr  # 资源管理器（可选）
        if asset_mgr:
            self.image = asset_mgr.get_effect_surface(code)

        self.rect = self.image.get_rect(center=pos)
        self.dirty = 1  # 确保初次绘制

        self.is_animating = False

    def draw(self, screen: pygame.Surface):
        screen.blit(self.image, self.rect)

    def update(self):
        self.dirty = 1
