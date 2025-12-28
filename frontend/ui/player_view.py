import pygame
from typing import Dict, List, Union,Optional
from frontend.core.asset_manager import AssetManager
from frontend.ui.card_sprite import CardSprite
from frontend.config.player_config import PlayerConfig
from frontend.config.card_config import CardConfig
from config.simple_card_config import SimpleGameConfig, SimpleCardConfig, SimplePlayerConfig
from config.enums import EquipmentType, CardName, PlayerIdentity, CharacterName

from frontend.util.fonts import Fonts
from frontend.util.size import CARD_SIZE, HP_BAR_SIZE
from frontend.util.color import default_colors
from frontend.ui.card_view import CardView

class PlayerView:
    def __init__(self, game_config: SimpleGameConfig, config: Union[PlayerConfig, SimplePlayerConfig], player_id: int, is_self: bool, asset_mgr: AssetManager):
        self.game_config = game_config
        self.config = config
        self.id = player_id
        self.is_self = is_self
        self.hand_click_rects: list[pygame.Rect] = []

        # 计算 max_hp：根据武将和身份动态计算（与后端逻辑一致）
        self.max_hp = self._calculate_max_hp()
        self.hp = self.max_hp
        self.cards: List[CardView] = []
        self.card_cnt = 0
        self.asset_mgr = asset_mgr
        self.character_pos = self._get_character_pos()  # 玩家中心点坐标（非手牌坐标）
        self.card_center_pos = self._get_card_center_pos()  # 手牌中心点坐标
        self.selected_card = None

        self.equipment: Dict[EquipmentType, CardName] = {}  # 装备栏
        self.equip_types = [EquipmentType.WEAPON, EquipmentType.ARMOR, EquipmentType.HORSE_PLUS, EquipmentType.HORSE_MINUS]
        for et in self.equip_types:
            self.equipment[et] = None
        
        self.dead = False

    def pick_hand_card_index_at(self, pos: tuple[int, int]) -> Optional[int]:
        if not self.is_self or not self.cards:
            return None

        # 有 click_rects 就用它（解决重叠遮挡）
        if getattr(self, "hand_click_rects", None) and len(self.hand_click_rects) == len(self.cards):
            for i in range(len(self.cards) - 1, -1, -1):
                if self.hand_click_rects[i].collidepoint(pos):
                    return i
            return None

        # 兜底：没有 click_rects 就用整张 rect
        for i in range(len(self.cards) - 1, -1, -1):
            if self.cards[i].rect.collidepoint(pos):
                return i
        return None

    def _get_character_pos(self):
        # 根据 player_id 和 is_self 计算位置
        screen_width, screen_height = pygame.display.get_surface().get_size()
        # 默认配置：5人局，900*640窗口，player 0占据最下900*200，player1-4均匀分布在最上方900*200
        if self.is_self:
            return (screen_width - 140, screen_height - 100)
        else:
            return ((self.id - 0.5) * (screen_width // (len(self.game_config.players_config) - 1)), 100)

    def _get_card_center_pos(self):
        if self.is_self:
            screen_width, screen_height = pygame.display.get_surface().get_size()
            return ((self.character_pos[0] - CARD_SIZE[0] // 2) // 2, self.character_pos[1]+50)
        else:
            return (None, None)  # 非self不显示手牌
    
    def draw(self, screen: pygame.Surface):
        # 绘制角色(血条等)
        self._draw_character(screen)
        self._draw_card_cnt(screen)
        self._draw_equipment(screen)
        # 绘制手牌
        if self.is_self:
            self._draw_hand(screen)
        # 绘制死亡效果（如果已死亡）
        self._draw_dead_overlay(screen)
        self.draw_lord(screen)

    def _draw_character(self, screen):
        # 绘制武将牌
        char_surf = self.asset_mgr.get_character_surface(self.config.character_name)
        # 若非self，在玩家位置绘制武将牌
        if not self.is_self:
            rect = char_surf.get_rect(center=self.character_pos)
            screen.blit(char_surf, rect.topleft)
        else:
            rect = char_surf.get_rect(center=(self.character_pos))
            screen.blit(char_surf, rect.topleft)
        # 红条：武将牌正下方，100像素宽，10像素高，以position为左上角绘制
        pos = (self.character_pos[0] - CARD_SIZE[0] // 2 + 1, self.character_pos[1] + CARD_SIZE[1] // 2 + 1)
        # 绘制血条背景和前景，以pos为左上角
        pygame.draw.rect(screen, (100, 0, 0), (*pos, HP_BAR_SIZE[0], HP_BAR_SIZE[1]))  # 血条背景
        hp_width = int(HP_BAR_SIZE[0] * self.hp / self.max_hp)
        pygame.draw.rect(screen, (0, 255, 0), (*pos, hp_width, HP_BAR_SIZE[1]))  # 血条前景

    def _draw_hand(self, screen):
        if not self.is_self:
            return
        if not self.cards or len(self.cards) == 0:
            return

        # 重新计算卡牌位置
        self._recalculate_card_positions(screen)
        # 绘制卡牌
        for card in self.cards:
            card.draw(screen, card.position)
    
    def _draw_card_cnt(self, screen):
        # character_pos右下角，灰色背景黑字小方块显示手牌数目，字在方块中央
        font = Fonts.small()
        cnt_surf = font.render(str(self.card_cnt), True, default_colors['white'])
        box_size = 20
        box_surf = pygame.Surface((box_size, box_size))
        box_surf.fill(default_colors['darkbrown'])
        box_rect = box_surf.get_rect(bottomright=(self.character_pos[0] + CARD_SIZE[0] // 2, self.character_pos[1] + CARD_SIZE[1] // 2))
        screen.blit(box_surf, box_rect)
        cnt_rect = cnt_surf.get_rect(center=box_rect.center)
        screen.blit(cnt_surf, cnt_rect)
    
    def _draw_equipment(self, screen):
        # character_pos右侧自上至下，依次绘制四个装备槽
        for i, equip_type in enumerate(self.equip_types):
            pos = (self.character_pos[0] + CARD_SIZE[0] // 2, self.character_pos[1] - CARD_SIZE[1] // 2 + i * 25)
            box_surf = pygame.Surface((80, 22))
            box_surf.fill(default_colors['darkbrown'])
            font = Fonts.small()
            equip_name = self.equipment.get(equip_type, None)
            if equip_name:
                equip_surf = font.render(equip_name.value, True, default_colors['white'])
            else:
                equip_surf = font.render("（空）", True, default_colors['white'])
            box_rect = box_surf.get_rect(topleft=pos)
            screen.blit(box_surf, box_rect)
            equip_rect = equip_surf.get_rect(center=box_rect.center)
            screen.blit(equip_surf, equip_rect)
    
    def _draw_dead_overlay(self, screen):
        if not self.dead:
            return
        dead_surf = self.asset_mgr.get_death_effect_surface(self.config.identity)
        rect = dead_surf.get_rect(center=self.character_pos)
        screen.blit(dead_surf, rect)

    def draw_lord(self, screen):
        if self.config.identity != PlayerIdentity.LORD:
            return
        if self.dead:
            return
        font = Fonts.medium()
        lord_surf = font.render("主公", True, default_colors['greybrown'])
        rect = lord_surf.get_rect(center=(self.character_pos[0], self.character_pos[1] - CARD_SIZE[1] // 2))
        lord_background = pygame.Surface((rect.width + 10, rect.height + 4))
        lord_background.fill(default_colors['darkbrown'])
        lord_background_rect = lord_background.get_rect(center=rect.center)
        screen.blit(lord_background, lord_background_rect)
        screen.blit(lord_surf, rect)

    def add_card(self, config: CardConfig):
        if not self.is_self:
            return
        card = CardView(config, self.asset_mgr)
        self.cards.append(card)

    def remove_card(self, cfg: CardConfig):
        for card in self.cards:
            if card.config.__eq__(cfg):
                self.cards.remove(card)
                return

    def select_card(self, mouse_pos):
        for card in reversed(self.cards):
            if card.rect.collidepoint(mouse_pos):
                self.selected_card = card
                return card
        return None

    def get_hp(self):
        return self.hp
    
    def update_hp(self, new_hp: int):
        self.hp = new_hp

    def handle_resize(self, screen: pygame.Surface):
        """处理窗口大小改变事件，重新计算位置"""
        # 更新位置
        self.character_pos = self._get_character_pos()
        self.card_center_pos = self._get_card_center_pos()
        # 重新计算卡牌位置
        if self.is_self and self.cards:
            self._recalculate_card_positions(screen)

    def _calculate_max_hp(self) -> int:
        """计算玩家的最大血量上限（与后端逻辑一致）
        
        规则：
        1. 每个武将都有基础血量上限（默认4）
        2. 如果身份是主公，血量上限+1
        
        Returns:
            最大血量上限
        """
        # 获取武将和身份
        if isinstance(self.config, SimplePlayerConfig):
            character_name = self.config.character_name
            identity = self.config.identity
        else:
            # 兼容旧的 PlayerConfig
            character_name = self.config.character_name
            identity = self.config.identity
        
        # 获取基础血量上限（与后端 Player.get_base_max_hp() 逻辑一致）
        # 默认所有武将基础血量上限为4
        base_max_hp = 4
        
        # 如果身份是主公，血量上限+1
        if identity == PlayerIdentity.LORD:
            return base_max_hp + 1
        else:
            return base_max_hp

    def _recalculate_card_positions(self, screen: pygame.Surface) -> None:
        """重新计算手牌位置，并生成可点击的可见区域（解决重叠导致点不到的问题）。"""
        if not self.cards:
            return

        n = len(self.cards)
        center_x = self.card_center_pos[0]
        y = self.card_center_pos[1]

        # 用真实卡面宽高，不要用 CARD_SIZE（否则图片尺寸不一致会错）
        w = self.cards[0].rect.width
        h = self.cards[0].rect.height

        left_bound = w // 2 + 10
        right_bound = self.character_pos[0] - w // 2 - 10
        if right_bound <= left_bound:
            right_bound = left_bound + 1

        max_span = right_bound - left_bound
        if n == 1:
            x0 = max(min(center_x, right_bound), left_bound)
            self.cards[0].set_position((x0, y))
        else:
            # step = 相邻中心点距离；牌多时允许重叠
            step_max = w + 10
            step_min = max(22, int(w * 0.30))  # 至少露出 30% 宽度（否则左牌会被完全盖住）
            step = max_span / (n - 1)
            step = max(step_min, min(step, step_max))

            span = step * (n - 1)
            start_x = center_x - span / 2
            if start_x < left_bound:
                start_x = left_bound
            if start_x + span > right_bound:
                start_x = right_bound - span

            for i, card in enumerate(self.cards):
                x = start_x + i * step
                card.set_position((x, y))

        # ---------- 关键：生成“可点击的可见区域” ----------
        self.hand_click_rects = []
        for i, card in enumerate(self.cards):
            r = card.rect.copy()

            # 如果有下一张牌覆盖，裁掉被覆盖的右侧区域
            if i < n - 1:
                next_left = self.cards[i + 1].rect.left
                # 让当前牌可点区域的 right 不超过 next_left-1
                r.right = min(r.right, next_left - 1)

            # 保底：如果被裁到没有宽度，给它留一条可点的细条
            if r.width < 6:
                r.right = card.rect.left + 6

            self.hand_click_rects.append(r)


