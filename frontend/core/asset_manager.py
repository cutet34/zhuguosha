import os
import pygame
from config.enums import CardName, CharacterName, EffectName, PlayerIdentity
from frontend.util.size import CARD_SIZE


def _fit_to_box(src: pygame.Surface, box_size: tuple[int, int]) -> pygame.Surface:
    """等比缩放并居中裁剪到固定框（cover）。

    Args:
        src: 原始图像 Surface。
        box_size: 目标尺寸 (w, h)。

    Returns:
        适配后的 Surface（严格为 box_size）。
    """
    bw, bh = box_size
    sw, sh = src.get_size()

    if sw <= 0 or sh <= 0:
        return pygame.Surface((bw, bh), pygame.SRCALPHA)

    # cover：保证至少铺满框，超出部分裁掉
    scale = max(bw / sw, bh / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    scaled = pygame.transform.smoothscale(src, (nw, nh))

    out = pygame.Surface((bw, bh), pygame.SRCALPHA)
    x = (bw - nw) // 2
    y = (bh - nh) // 2
    out.blit(scaled, (x, y))
    return out

class AssetManager:
    def __init__(self, asset_root=None):
        self._cache = {}

        if asset_root is None:
            asset_root = os.path.join("frontend", "assets")
        asset_root = os.path.normpath(asset_root)

        self.card_base_path = os.path.join(asset_root, "cards")
        self.character_base_path = os.path.join(asset_root, "characters")
        self.effect_base_path = os.path.join(asset_root, "effects")

    def get_card_surface(self, code: CardName) -> pygame.Surface:
        key = ("card", code.value)
        if key in self._cache:
            return self._cache[key]

        filename = f"{code.value}.jpg"
        path = os.path.join(self.card_base_path, filename)

        surf = pygame.image.load(path).convert_alpha()
        surf = _fit_to_box(surf, CARD_SIZE)

        self._cache[key] = surf
        return surf

    def get_card_back(self) -> pygame.Surface:
        key = ("card", "back")
        if key in self._cache:
            return self._cache[key]

        path = os.path.join(self.card_base_path, "back.jpg")
        if os.path.exists(path):
            surf = pygame.image.load(path).convert_alpha()
        else:
            # 占位图
            surf = pygame.Surface((100, 150))
            surf.fill((180, 180, 180))
        self._cache[key] = surf
        return surf

    def get_deck_surface(self) -> pygame.Surface:
        """
        返回牌堆图像的 Surface 对象
        """
        key = ("card", "deck")
        if key in self._cache:
            return self._cache[key]

        path = os.path.join(self.card_base_path, "deck.jpg")
        surf = pygame.image.load(path).convert_alpha()
        self._cache[key] = surf
        return surf

    def get_character_surface(self, code: CharacterName) -> pygame.Surface:
        key = ("character", code.value)
        if key in self._cache:
            return self._cache[key]

        filename = f"{code.value}.jpg"
        path = os.path.join(self.character_base_path, filename)

        if os.path.exists(path):
            surf = pygame.image.load(path).convert_alpha()
            surf = _fit_to_box(surf, CARD_SIZE)  # 关键：统一尺寸
        else:
            # 占位图也做成统一尺寸
            surf = pygame.Surface(CARD_SIZE, pygame.SRCALPHA)
            surf.fill((180, 180, 180))

        self._cache[key] = surf
        return surf

    def get_effect_surface(self, code: EffectName) -> pygame.Surface:
        key = ("effect", code.value)
        if key in self._cache:
            return self._cache[key]

        filename = f"{code.value}.png"
        path = os.path.join(self.effect_base_path, filename)

        if os.path.exists(path):
            surf = pygame.image.load(path).convert_alpha()
        else:
            # 占位图
            surf = pygame.Surface((100, 100))
            surf.fill((255, 0, 0))

        self._cache[key] = surf
        return surf
    
    def get_death_effect_surface(self, identity: PlayerIdentity) -> pygame.Surface:
        """
        根据玩家身份获取死亡特效图像
        """
        if identity == PlayerIdentity.LORD:
            id_str = "zhugong"
        elif identity == PlayerIdentity.LOYALIST:
            id_str = "zhongchen"
        elif identity == PlayerIdentity.REBEL:
            id_str = "fanzei"
        elif identity == PlayerIdentity.TRAITOR:
            id_str = "neijian"
        key = ("effect", f"death_{id_str}")
        if key in self._cache:
            return self._cache[key]

        filename = f"dead_{id_str}.png"
        path = os.path.join(self.effect_base_path, filename)

        if os.path.exists(path):
            surf = pygame.image.load(path).convert_alpha()
        else:
            # 占位图
            surf = pygame.Surface((100, 100))
            surf.fill((0, 0, 0))

        self._cache[key] = surf
        return surf
