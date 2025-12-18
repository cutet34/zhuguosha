# 玩家模块
from typing import List, Optional, Tuple, Dict, Any
import sys
import os


sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.card.card import Card
from backend.deck.deck import Deck
from backend.control.control import Control
from backend.control.control_factory import ControlFactory
from backend.player.equipment_manager import EquipmentManager
from backend.player.phase_skill_handler import PhaseSkillManager
from backend.utils.logger import game_logger
from backend.utils.event_sender import send_draw_card_event, send_play_card_event, send_hp_change_event, send_discard_card_event, send_equip_change_event, send_death_event
from config.enums import CardName, CardType, ControlType, PlayerStatus, PlayerIdentity, CharacterName, TargetType, \
    GameEvent, EquipmentType, Faction, Gender


class Player:
    """玩家基类
    
    这个模块要继承，其中每一个函数都包含一个默认函数。
    所有都为子类的为白板武将，在实现其他武将时，应继承默认函数，并修改外接口。
    """
    
    # 武将基础血量上限映射（子类可以覆盖 get_base_max_hp 方法来自定义）
    
    def get_base_max_hp(self) -> int:
        """获取武将的基础血量上限（子类可以覆盖此方法来自定义）
        
        Returns:
            基础血量上限
        """
        return 4
    
    def __init__(self, player_id: int, name: str, control_type: ControlType, deck: Deck, identity: PlayerIdentity = None, character_name: CharacterName = None, player_controller = None,faction: Faction = None,gender:Gender = None) :
        """初始化函数
        
        Args:
            player_id: 玩家ID
            name: 玩家名称
            control_type: 操控类型
            deck: 牌堆
            identity: 玩家身份
            character_name: 武将名
            player_controller: 玩家控制器引用
            faction:武将阵营
        """
        self.player_id = player_id
        self.name = name
        self.character_name = character_name or CharacterName.BAI_BAN_WU_JIANG  # 武将名，默认为白板武将
        self.identity = identity or PlayerIdentity.REBEL  # 玩家身份，默认为反贼
        self.status = PlayerStatus.ALIVE  # 存活状态
        self.faction=faction or Faction.WEI   #阵营,默认为魏
        self.gender=gender or Gender.MALE #性别，默认为男
        self.skills = []  # 玩家技能列表（Skill 实例）
        self.runtime_state = {}  # 通用状态标记，技能可写入，规则点读取，记录技能产生的临时状态/次数/开关

        # 计算血量上限：基础血量上限 + 主公加成（+1）
        base_max_hp = self.get_base_max_hp()
        if self.identity == PlayerIdentity.LORD:
            self.max_hp = base_max_hp + 1  # 主公血量上限+1
        else:
            self.max_hp = base_max_hp
        
        self.current_hp = self.max_hp  # 当前血量等于血量上限
        self.initial_hand_size = 4  # 初始手牌数量
        
        self.deck = deck
        
        # 手牌
        self.hand_cards: List[Card] = []
        
        # 装备管理器
        self.equipment_manager = EquipmentManager(player_id, name, deck)
        
        # 阶段技能管理器
        self.phase_skill_manager = PhaseSkillManager()
        
        # 操控模块（使用工厂模式创建）
        self.control = ControlFactory.create_control(control_type, player_id)
        
        # 回合状态跟踪
        self.sha_used_this_turn = False  # 当前回合是否已使用杀
        self.player_controller = player_controller  # 玩家控制器引用
        
        # 伤害来源追踪
        self.last_damage_source: Optional[int] = None  # 最后一次伤害的来源玩家ID
        
        self.skill_activate_time_with_skill:Dict[GameEvent, Optional[str]] = { # 技能发动时间
            GameEvent.DRAW_CARD: None,
            GameEvent.PLAY_CARD: None,
            GameEvent.DISCARD_CARD: None,
            GameEvent.DAMAGE: None,
            GameEvent.HEAL: None,
            GameEvent.DEATH: None,
            GameEvent.EQUIP: None,
        }
        # 初始化手牌
        if self.deck is not None:
            self._draw_initial_cards()
    
    # 装备属性（只读，向后兼容，从 EquipmentManager 获取）
    # 注意：只能通过 equipment_manager.equip() 来装备，不能直接修改这些属性
    @property
    def weapon(self) -> Optional[Card]:
        """武器牌"""
        return self.equipment_manager.weapon
    
    @property
    def armor(self) -> Optional[Card]:
        """防具牌"""
        return self.equipment_manager.armor
    
    @property
    def horse_plus(self) -> Optional[Card]:
        """+1马"""
        return self.equipment_manager.horse_plus
    
    @property
    def horse_minus(self) -> Optional[Card]:
        """-1马"""
        return self.equipment_manager.horse_minus
    
    def _draw_initial_cards(self) -> None:
        """抽取初始手牌"""
        for _ in range(self.initial_hand_size):
            card = self.deck.draw_card()
            if card:
                self.hand_cards.append(card)
                
                # 发送摸牌事件到前端
                send_draw_card_event(card, self.player_id)
        
        # 记录初始手牌
        if self.hand_cards:
            card_names = [card.name for card in self.hand_cards]
            game_logger.log_info(f"{self.name} 初始手牌: {', '.join(card_names)}")
    
    def is_alive(self) -> bool:
        """检查是否存活"""
        return self.status == PlayerStatus.ALIVE
    
    def draw_card(self, count: int = 2) -> List[Card]:
        """一般摸牌（直接摸牌，不触发技能询问）
        
        Args:
            count: 摸牌数量
            
        Returns:
            摸到的牌列表
        """
        drawn_cards = []
        for _ in range(count):
            card = self.deck.draw_card()
            if card:
                self.hand_cards.append(card)
                drawn_cards.append(card)
                
                # 发送摸牌事件到前端
                send_draw_card_event(card, self.player_id)
        
        # 记录摸牌日志
        if drawn_cards:
            game_logger.log_player_draw_cards(self.name, drawn_cards)
        
        return drawn_cards
    
    def draw_card_phase(self) -> List[Card]:
        """摸牌阶段（使用阶段技能管理器）
        
        用于回合中的摸牌阶段，会触发技能询问
            
        Returns:
            摸到的牌列表
        """
        return self.phase_skill_manager.execute_phase(self, GameEvent.DRAW_CARD)

    def draw_card_phase_default(self) -> List[Card]:
        """默认摸牌流程（原有实现）"""
        return self.draw_card(2)

    def draw_card_phase_with_skill(self) -> List[Card]:
        """发动技能后的摸牌阶段（子类可覆盖），默认等同于默认摸牌流程"""
        return self.draw_card_phase_default()
    
    def play_card(self, available_targets: Dict[str, List[int]] = None) -> Tuple[Optional[Card], List[int]]:
        """出牌（使用阶段技能管理器）
        
        Args:
            available_targets: 可用目标字典，包含attackable、all、dis1等键
            
        Returns:
            (选择的牌, 目标列表)
        """
        return self.phase_skill_manager.execute_phase(self, GameEvent.PLAY_CARD, available_targets=available_targets)

    def play_card_with_skill(self, available_targets: Dict[str, List[int]] = None) -> Tuple[Optional[Card], List[int]]:
        """发动技能后的出牌阶段（子类可覆盖），默认等同于默认出牌流程"""
        return self.play_card_default(available_targets)

    def play_card_default(self, available_targets: Dict[str, List[int]] = None) -> Tuple[Optional[Card], List[int]]:
        """未发动技能时的默认出牌流程（原有实现）"""
        # 获取可选牌（传入available_targets以检查是否有合法目标）
        playable_cards = self._get_playable_cards(available_targets)
        if not playable_cards:
            return None, []
        
        # 让操控模块选择牌（传入available_targets以便检查是否有合法目标）
        selected_card = self.control.select_card(playable_cards, "", available_targets)
        if selected_card is None:
            return None, []
        
        # 根据牌的类型和可用目标确定可选目标
        targets = self._get_targets_for_card(selected_card, available_targets)
        
        # 确保目标列表中不包含自己（除了SELF类型的牌）
        if selected_card.target_type != TargetType.SELF:
            targets = [t for t in targets if t != self.player_id]
        
        # 如果是杀，需要在Control中重新过滤攻击范围内的目标（使用逆时针距离）
        # 因为player_controller的get_targets使用的是最小距离，而猪国杀应该只使用逆时针距离
        if selected_card.name_enum == CardName.SHA and selected_card.target_type == TargetType.ATTACKABLE:
            # 对于杀，让Control重新过滤攻击范围内的目标
            if hasattr(self.control, 'filter_attackable_targets'):
                targets = self.control.filter_attackable_targets(targets, available_targets)
        if selected_card is not None and selected_card.name_enum == CardName.SHA:
            self.runtime_state["sha_used_or_played_in_play_phase"] = True

        # 如果是自己类型的牌，直接使用自己
        if selected_card.target_type == TargetType.SELF:
            selected_targets = [self.player_id]
        elif selected_card.target_type == TargetType.ALL:
            # 对于ALL类型的牌，需要区分：
            # - 南蛮入侵、万箭齐发：使用所有目标
            # - 决斗：只选择一个目标
            if selected_card.name_enum == CardName.JUE_DOU:
                # 决斗只选择一个目标
                selected_targets = self.control.select_targets(targets, selected_card)
                # 确保只选择一个目标
                if selected_targets:
                    selected_targets = [selected_targets[0]]
                else:
                    selected_targets = []
            else:
                # 其他ALL类型牌（南蛮入侵、万箭齐发）使用所有目标
                selected_targets = targets
        else:
            # 让操控模块选择目标
            selected_targets = self.control.select_targets(targets, selected_card)
        
        # 从手牌中移除已出的牌
        if selected_card in self.hand_cards:
            self.hand_cards.remove(selected_card)
        
        # 记录出牌日志
        # 获取目标玩家名称
        target_names = []
        if hasattr(self, 'player_controller') and self.player_controller:
            for target_id in selected_targets:
                target_player = self.player_controller.get_player(target_id)
                if target_player:
                    target_names.append(target_player.name)
        else:
            # 如果没有player_controller引用，使用ID
            target_names = [f"玩家{target_id}" for target_id in selected_targets]
        
        game_logger.log_player_play_card(self.name, selected_card.name, selected_targets, target_names)
        
        # 发送出牌事件到前端
        # 对于多目标牌（TargetType.ALL），需要区分：
        # - 决斗：虽然目标类型是ALL，但实际只选择一个目标，应该发送给实际目标
        # - 南蛮入侵、万箭齐发：真正的多目标牌，发送给[-1]表示对所有目标生效
        if selected_card.target_type == TargetType.ALL:
            if selected_card.name_enum == CardName.JUE_DOU:
                # 决斗只选择一个目标，发送给实际目标
                send_play_card_event(selected_card, self.player_id, selected_targets)
            else:
                # 真正的多目标牌（南蛮入侵、万箭齐发）只发送一个事件给[-1]
                # 避免发送多个重复的事件
                if selected_targets:
                    send_play_card_event(selected_card, self.player_id, [-1])
                else:
                    send_play_card_event(selected_card, self.player_id, [self.player_id])
        else:
            # 单目标牌正常发送
            send_play_card_event(selected_card, self.player_id, selected_targets)

        
        return selected_card, selected_targets
    
    def discard_card(self) -> List[Card]:
        """弃牌（使用阶段技能管理器）"""
        return self.phase_skill_manager.execute_phase(self, GameEvent.DISCARD_CARD)

    def discard_card_with_skill(self) -> List[Card]:
        """发动技能后的弃牌阶段（子类可覆盖），默认等同于默认弃牌流程"""
        return self.discard_card_default()
    
    def discard_card_default(self) -> List[Card]:
        """默认弃牌流程（原有实现）"""
        # 检查手牌数量是否超过上限
        if len(self.hand_cards) <= self.current_hp:
            return []
        
        # 让操控模块选择要弃的牌
        discard_count = len(self.hand_cards) - self.current_hp
        selected_cards = self.control.select_cards_to_discard(self.hand_cards, discard_count)
        
        # 确保selected_cards不为None
        if selected_cards is None:
            selected_cards = []
        
        # 从手牌中移除并放入弃牌堆
        discarded_cards = []
        for card in selected_cards:
            if card in self.hand_cards:
                self.hand_cards.remove(card)
                # 将牌放入弃牌堆
                self.deck.discard_card(card)
                # 发送弃牌事件
                send_discard_card_event(card, self.player_id)
                discarded_cards.append(card)
        
        # 记录弃牌日志
        if discarded_cards:
            card_names = [card.name for card in discarded_cards]
            game_logger.log_info(f"{self.name} 弃牌: {', '.join(card_names)}")
        
        return discarded_cards

    def should_skip_phase(self, event_type: "GameEvent", context: Dict[str, Any]) -> bool:
        """判断是否跳过某个阶段（通用钩子）。"""
        for skill in getattr(self, "skills", []):
            fn = getattr(skill, "should_skip_phase", None)
            if callable(fn) and fn(self, event_type, context):
                return True
        return False

    def take_damage(self, damage: int, source_player_id: Optional[int] = None,
                    damage_type: str = None, original_card_name: str = None) -> None:
        """受伤（使用阶段技能管理器）"""
        self.phase_skill_manager.execute_phase(
            self, GameEvent.DAMAGE, 
            damage=damage, 
            source_player_id=source_player_id,
            damage_type=damage_type,
            original_card_name=original_card_name
        )

    def take_damage_default(self, damage: int, source_player_id: Optional[int] = None,
                           damage_type: str = None, original_card_name: str = None) -> None:
        """默认受伤流程（原有实现）"""
        old_hp = self.current_hp
        self.current_hp = max(0, self.current_hp - damage)
        
        # 记录伤害来源
        if source_player_id is not None:
            self.last_damage_source = source_player_id
        
        # 记录受伤日志
        game_logger.log_player_damage(self.name, damage, self.current_hp, self.max_hp)
        
        # 发送血量变化事件到前端（传递伤害来源和伤害类型信息）
        if self.current_hp != old_hp:
            send_hp_change_event(
                self.player_id, self.current_hp,
                source_player_id=source_player_id,
                damage_type=damage_type,
                original_card_name=original_card_name
            )
        
        if self.current_hp == 0 and old_hp > 0:
            # 血量降到0时进入濒死状态，不直接死亡
            game_logger.log_player_dying(self.name)
            # 濒死处理由GameController负责

    def take_damage_with_skill(self, damage: int, source_player_id: Optional[int] = None,
                               damage_type: str = None, original_card_name: str = None) -> None:
        """发动技能后的受伤流程（子类可覆盖），默认等同于默认受伤流程"""
        self.take_damage_default(damage, source_player_id, damage_type, original_card_name)
    
    def die(self) -> None:
        """死亡（默认实现）"""
        self.status = PlayerStatus.DEAD
        self.current_hp = 0
        
        # 记录死亡日志
        identity_name = self.identity.value if self.identity else None
        game_logger.log_player_death(self.name, identity_name)
        
        # 发送死亡事件到前端
        send_death_event(self.player_id)
        
        # 处理死亡时的特殊逻辑
        self._handle_death_consequences()
        
        # 死亡时将所有手牌和装备牌进入弃牌堆
        if hasattr(self, 'deck') and self.deck:
            # 将所有手牌进入弃牌堆
            for card in self.hand_cards:
                self.deck.discard_card(card)
                # 发送弃牌事件
                send_discard_card_event(card, self.player_id)
            self.hand_cards.clear()
            
            # 将装备牌进入弃牌堆（使用装备管理器）
            self.equipment_manager.discard_all()
        else:
            # 如果没有牌堆引用，直接清空
            self.hand_cards.clear()
            self.equipment_manager.unequip_all()
    
    def _handle_death_consequences(self) -> None:
        """处理死亡时的特殊逻辑"""
        if not hasattr(self, 'player_controller') or not self.player_controller:
            return
        
        # 获取伤害来源
        killer_id = self.last_damage_source
        if killer_id is None:
            return
        
        killer = self.player_controller.get_player(killer_id)
        if killer is None or not killer.is_alive():
            return
        
        # 主公杀死忠臣的惩罚
        if (self.identity == PlayerIdentity.LOYALIST and 
            killer.identity == PlayerIdentity.LORD):
            self._handle_lord_kill_loyalist(killer)
        
        # 杀死反贼的奖励
        elif self.identity == PlayerIdentity.REBEL:
            self._handle_kill_rebel_reward(killer)
    
    def _handle_lord_kill_loyalist(self, killer) -> None:
        """处理主公杀死忠臣的惩罚"""
        game_logger.log_info(f"{killer.name} 杀死了忠臣 {self.name}，需要弃掉所有牌！")
        
        # 弃掉所有手牌
        if killer.hand_cards:
            for card in killer.hand_cards.copy():
                killer.hand_cards.remove(card)
                killer.deck.discard_card(card)
                # 发送弃牌事件
                send_discard_card_event(card, killer.player_id)
            game_logger.log_info(f"{killer.name} 弃掉了所有手牌")
        
        # 弃掉所有装备牌（使用装备管理器）
        unequipped = killer.equipment_manager.unequip_all()
        if unequipped:
            slot_names = {
                "weapon": "武器",
                "armor": "防具",
                "horse_plus": "防御马",
                "horse_minus": "进攻马",
            }
            for slot_name, card in unequipped:
                game_logger.log_info(f"{killer.name} 弃掉了{slot_names.get(slot_name, '装备')}")
    
    def _handle_kill_rebel_reward(self, killer) -> None:
        """处理杀死反贼的奖励"""
        # 先检查游戏是否结束，如果结束则不执行奖励
        if hasattr(self, 'player_controller') and self.player_controller:
            if self.player_controller.game_over():
                return
        
        game_logger.log_info(f"{killer.name} 杀死了反贼 {self.name}，摸三张牌！")
        
        # 摸三张牌
        drawn_cards = killer.draw_card(3)
        if drawn_cards:
            card_names = [card.name for card in drawn_cards]
            game_logger.log_info(f"{killer.name} 摸到了: {', '.join(card_names)}")
    
    def heal(self, heal_amount: int) -> None:
        """回复（默认实现）
        
        Args:
            heal_amount: 回复量
        """
        old_hp = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + heal_amount)
        actual_heal = self.current_hp - old_hp
        
        # 记录治疗日志
        if actual_heal > 0:
            game_logger.log_player_heal(self.name, actual_heal, self.current_hp, self.max_hp)
            
            # 发送血量变化事件到前端
            send_hp_change_event(self.player_id, self.current_hp)
    
    def equip(self, card: Card) -> bool:
        """装备（使用装备管理器）
        
        Args:
            card: 要装备的牌
            
        Returns:
            是否装备成功
        """
        return self.equipment_manager.equip(card)
    
    def _get_playable_cards(self, available_targets: Dict[str, List[int]] = None) -> List[Card]:
        """获取可出的牌
        
        Args:
            available_targets: 可用目标字典，用于检查是否有合法目标
        """
        playable_cards = []
        
        for card in self.hand_cards:
            if self._can_play_card(card, available_targets):
                playable_cards.append(card)
        
        return playable_cards
    
    def _can_play_card(self, card: Card, available_targets: Dict[str, List[int]] = None) -> bool:
        """判断是否可以出指定牌
        
        Args:
            card: 要判断的牌
            available_targets: 可用目标字典，用于检查是否有合法目标
            
        Returns:
            是否可以出牌
        """
        # 杀牌判断
        # 中文注释：若已使用过杀，则只有在上限 > 1（或无限）时仍允许继续出杀
        limit = self.get_sha_limit({"available_targets": available_targets})
        if self.sha_used_this_turn and limit <= 1:
            return False


        # 闪牌判断
        elif card.name_enum == CardName.SHAN:
            # 闪无论如何不能使用
            return False
        
        # 桃牌判断
        elif card.name_enum == CardName.TAO:
            # 桃只有在不是满血时可以使用
            return self.current_hp < self.max_hp
        
        # 装备牌判断
        elif card.card_type == CardType.EQUIPMENT:
            # 装备一定可以使用
            return True
        
        # 锦囊牌判断
        elif card.card_type == CardType.TRICK:
            # 无懈可击不能使用
            if card.name_enum == CardName.WU_XIE_KE_JI:
                return False
            # 其他锦囊牌需要检查是否有合法目标
            # 对于TargetType.SELF类型的锦囊牌，目标总是自己，不需要检查
            if card.target_type == TargetType.SELF:
                return True
            # 其他类型的锦囊牌需要检查目标
            targets = self._get_targets_for_card(card, available_targets)
            return len(targets) > 0
        
        # 其他牌默认可以使用（如果没有目标类型要求）
        # 但为了安全起见，如果available_targets不为None，也检查一下目标
        if available_targets is not None:
            # 对于TargetType.SELF类型的牌，目标总是自己，不需要检查
            if card.target_type == TargetType.SELF:
                return True
            # 对于需要目标的牌，检查是否有合法目标
            targets = self._get_targets_for_card(card, available_targets)
            # 如果牌的目标类型不是SELF，则需要有合法目标
            if card.target_type != TargetType.SELF:
                return len(targets) > 0
        
        return True
    def _get_targets_for_card(self, card: Card, available_targets: Dict[str, List[int]] = None) -> List[int]:
        """获取牌的目标列表
        
        Args:
            card: 要出的牌
            available_targets: 可用目标字典
            
        Returns:
            该牌可选的目标列表
        """
        if available_targets is None:
            return []
        
        # 根据牌的目标类型选择合适的目标列表
        if card.target_type == TargetType.ATTACKABLE:
            targets = available_targets.get("attackable", [])
        elif card.target_type == TargetType.ALL:
            targets = available_targets.get("all", [])
        elif card.target_type == TargetType.DIS1:
            targets = available_targets.get("dis1", [])
        elif card.target_type == TargetType.SELF:
            return [self.player_id]
        else:
            # 默认返回攻击距离内的目标
            targets = available_targets.get("attackable", [])
        
        # 确保目标列表中不包含自己（除了SELF类型的牌）
        if card.target_type != TargetType.ALL:
            targets = [t for t in targets if t != self.player_id]
        return targets

    def get_sha_limit(self, context: Dict[str, Any]) -> int:
        """计算本回合【杀】的使用次数上限（通用钩子）。

        约定：
        - 默认上限为 1。
        - 诸葛连弩：视为无限（用一个极大值表示）。
        - 技能可通过实现 skill.modify_sha_limit(...) 修改上限。

        Args:
            context: 上下文字典，可包含 available_targets、event_type 等信息。

        Returns:
            int: 本回合【杀】次数上限。
        """
        # 中文注释：基础上限
        base_limit = 1

        # 中文注释：诸葛连弩 => 无限
        if self.weapon is not None and self.weapon.name_enum == CardName.ZHU_GE_LIAN_NU:
            base_limit = 10 ** 9

        # 中文注释：技能可修改上限（不依赖任何 runtime_state 的特定 key）
        for skill in getattr(self, "skills", []):
            fn = getattr(skill, "modify_sha_limit", None)
            if callable(fn):
                base_limit = fn(self, base_limit, context)

        return base_limit

    def ask_use_card(self, card_name: CardName, context: str = "") -> Optional[Card]:
        """询问玩家是否使用指定牌（响应类查询，与正常出牌分开）
        
        Args:
            card_name: 牌名枚举
            context: 使用上下文描述（如"响应决斗"、"响应南蛮入侵"、"受到杀的攻击"等）
            
        Returns:
            选择的牌或None（不使用）
        """
        # 查找手牌中是否有指定牌名的牌（使用枚举匹配，保持从左往右的顺序）
        available_cards = [card for card in self.hand_cards if card.name_enum == card_name]
        
        if not available_cards:
            return None
        
        # 使用专门的响应类查询方法（与正常出牌分开）
        selected_card = self.control.ask_use_card_response(card_name, available_cards, context)
        
        if selected_card is not None:
            # 如果选择了使用牌，从手牌中移除
            if selected_card in self.hand_cards:
                self.hand_cards.remove(selected_card)
        
        return selected_card
    
    def ask_use_tao(self, context: str = "") -> Optional[Card]:
        """询问玩家是否使用桃
        
        Args:
            context: 使用上下文描述
            
        Returns:
            选择的桃或None（不使用）
        """
        return self.ask_use_card(CardName.TAO, context)
    
    def ask_use_shan(self, context: str = "") -> Optional[Card]:
        """询问玩家是否使用闪
        
        Args:
            context: 使用上下文描述
            
        Returns:
            选择的闪或None（不使用）
        """
        return self.ask_use_card(CardName.SHAN, context)
    
    def ask_use_sha(self, context: str = "") -> Optional[Card]:
        """询问玩家是否使用杀
        
        Args:
            context: 使用上下文描述
            
        Returns:
            选择的杀或None（不使用）
        """
        return self.ask_use_card(CardName.SHA, context)
    
    def ask_use_wu_xie_ke_ji(self, context: str = "") -> Optional[Card]:
        """询问玩家是否使用无懈可击
        
        Args:
            context: 使用上下文描述
            
        Returns:
            选择的无懈可击或None（不使用）
        """
        return self.ask_use_card(CardName.WU_XIE_KE_JI, context)
    
    def reset_turn_state(self) -> None:
        """重置回合状态"""
        self.runtime_state["play_phase_executed"] = False
        self.runtime_state["sha_used_or_played_in_play_phase"] = False

    def get_draw_num(self, base_num: int, context: Dict[str, Any]) -> int:
        """计算摸牌阶段应摸的牌数（通用钩子）。

        说明：
        - 默认摸牌数为 base_num（通常是 2）。
        - 装备、技能等可以通过实现 modify_draw_num(player, current_num, context)
          来修改最终的摸牌数量。
        - 本方法只负责组合这些修改，不关心具体武将或技能名。

        Args:
            base_num: 基础摸牌数（如 2）。
            context: 摸牌阶段上下文信息。

        Returns:
            int: 最终应摸的牌数。
        """
        draw_num = base_num

        for sk in getattr(self, "skills", []):
            modify_fn = getattr(sk, "modify_draw_num", None)
            if callable(modify_fn):
                draw_num = modify_fn(self, draw_num, context)

        return draw_num

    def ask_activate_skill(self, skill_name: str, context: dict) -> bool:
        """统一武将技能发动询问，直接委托Control，true为发动。"""
        if hasattr(self.control, 'ask_activate_skill') and callable(self.control.ask_activate_skill):
            try:
                return bool(self.control.ask_activate_skill(skill_name, context))
            except Exception:
                return False
        return False

    def trigger_skills(self, context: Dict[str, Any]) -> None:
        """触发玩家身上的技能（广播式触发：同一阶段/事件可触发多个技能）。

        规则：
        - 先调用 skill.can_activate(self, context) 判断是否满足触发条件。
        - 锁定技（skill.is_locked == True）直接生效，不询问。
        - 非锁定技默认会询问 control：player.ask_activate_skill(skill_name, context)。
        - 技能可以自定义：
          - skill.name：技能名（用于询问与日志）
          - skill.need_ask：是否需要询问（默认 True；锁定技一般不需要）

        Args:
            context: 技能触发上下文，建议至少包含 phase/event_type 等信息。
                     例如：{"phase": GamePhase.PLAY_CARD, "event_type": GameEvent.PLAY_CARD, ...}

        Returns:
            None
        """
        # 没有技能列表则直接返回（兼容旧实现）
        skills = getattr(self, "skills", None)
        if not skills:
            return

        # 遍历副本，避免技能在触发中增删列表导致迭代异常
        for skill in list(skills):
            try:
                # 先判断是否满足触发条件
                if not skill.can_activate(self, context):
                    continue

                # 锁定技不询问，直接生效
                is_locked = bool(getattr(skill, "is_locked", False))
                if is_locked:
                    skill.activate(self, context)
                    continue

                # 非锁定技默认需要询问是否发动
                skill_name = getattr(skill, "name", skill.__class__.__name__)
                need_ask = bool(getattr(skill, "need_ask", True))
                if need_ask:
                    if not self.ask_activate_skill(skill_name, context):
                        continue

                # 执行技能效果
                skill.activate(self, context)

            except Exception as e:
                #技能异常不应打崩主流程，记录日志后跳过
                try:
                    game_logger.log_error(f"技能触发异常：{getattr(skill, 'name', skill.__class__.__name__)}，错误：{e}")
                except Exception:
                    pass
                continue



class ZhangFeiPlayer(Player):
    """张飞武将：咆哮（锁定技，被动：杀次数不受限制）"""

    def __init__(self, *args, **kwargs):
        """初始化张飞玩家（仅装配元数据与技能，不改规则流程）。

        Args:
            *args: 透传给 Player 基类的参数。
            **kwargs: 透传给 Player 基类的参数。

        Returns:
            None
        """
        super().__init__(*args, **kwargs)

        # 设置阵营势力（元数据）
        self.faction = Faction.SHU

        # 装配技能对象（局部导入避免循环引用）
        from backend.player.skill.zhangfei_skill import ZhangFeiSkill
        self.skills.append(ZhangFeiSkill())



class LvmengPlayer(Player):
    """吕蒙武将：克己"""

    def __init__(self, *args, **kwargs):
        """初始化吕蒙玩家。

        Args:
            *args: 透传参数。
            **kwargs: 透传参数。

        Returns:
            None
        """
        super().__init__(*args, **kwargs)
        self.faction = Faction.WU

        from backend.player.skill.lvmeng_skill import KeJiSkill
        self.skills.append(KeJiSkill())



class ZhuguoShaPlayer(Player):
    """猪国杀武将：专供猪国杀规则使用，没有弃牌阶段"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 设置阵营势力
        self.faction=None
        # 设置弃牌阶段技能名（虽然不会执行弃牌，但设置技能名以便识别）
        self.skill_activate_time_with_skill[GameEvent.DISCARD_CARD] = "无弃牌阶段"
    
    def discard_card_with_skill(self) -> List[Card]:
        """猪国杀规则：没有弃牌阶段，直接返回空列表"""
        game_logger.log_info(f"{self.name} 猪国杀规则：跳过弃牌阶段")
        return []

class LingcaoPlayer(Player):
    """凌操武将：独进"""

    def __init__(self, *args, **kwargs):
        """初始化凌操玩家（装配元数据与技能）。

        Args:
            *args: 透传给 Player 基类的参数。
            **kwargs: 透传给 Player 基类的参数。

        Returns:
            None
        """
        super().__init__(*args, **kwargs)

        # 中文注释：设置阵营势力
        self.faction = Faction.WU

        # 中文注释：装配技能对象（不再使用 skill_activate_time_with_skill）
        from backend.player.skill.lingcao_skill import DuJinSkill
        self.skills.append(DuJinSkill())


class CaoCaoPlayer(Player):
    """曹操 —— 技能：奸雄、护驾（主公技）"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 设置阵营势力
        self.faction=Faction.WEI

        # 注册阶段技能：受到伤害时触发“奸雄”
        self.skill_activate_time_with_skill[GameEvent.DAMAGE] = "奸雄"

    # ======================【奸雄】=======================
    def take_damage_with_skill(self, damage, source_player_id=None,
                               damage_type=None, original_card_name=None):
        """
        曹操【奸雄】：
        当你受到伤害后，你可以获得对你造成伤害的牌。
        """

        # 先执行默认掉血
        self.take_damage_default(damage, source_player_id,
                                 damage_type, original_card_name)

        # original_card_name 代表造成伤害的牌名
        if original_card_name is None:
            return

        # 询问曹操要不要发动奸雄
        context = {
            "damage": damage,
            "source_player": source_player_id,
            "card_name": original_card_name
        }
        activate = self.ask_activate_skill("奸雄", context)

        if activate:
            # 让造成伤害的那张卡进入曹操手牌
            game_logger.log_info(f"{self.name} 发动【奸雄】，获得造成伤害的牌：{original_card_name}")
            # 给曹操添加一张该牌名的手牌（模拟进入手牌）
            self.hand_cards.append(Card(original_card_name))

    # ======================【护驾】（响应技能）=======================

    def ask_use_shan(self, context: str = "") -> Optional[Card]:
        """
        曹操【护驾】完整逻辑：
            1. 曹操需要闪时，先询问是否发动护驾
            2. 曹操选择发动后：
                - 按顺序询问每个魏势力友方是否愿意提供闪
                - 若有队友提供闪 → 曹操视为使用闪（队友失去闪）
            3. 若没人帮忙 → 曹操自己问自己有没有闪（父类 ask_use_shan）

        Args:
            context: 使用闪的场景，如"受到杀的攻击"

        Returns:
            Optional[Card]: 曹操最终打出的闪（含队友代打），或 None（没有闪）
        """

        # ---------- 1. 曹操决定是否发动护驾 ----------
        activate = self.ask_activate_skill("护驾", {"context": context})

        if not activate:
            # 不发动技能 → 走父类正常 ask_use_shan()
            return super().ask_use_shan(context)

        game_logger.log_info(f"{self.name} 发动【护驾】！")

        # ---------- 2. 曹操发动护驾 → 寻找魏势力队友 ----------
        if self.player_controller:
            for p in self.player_controller.players:

                # 跳过自己
                if p.player_id == self.player_id:
                    continue

                # 只询问魏势力
                if p.identity != Faction.WEI:
                    continue

                # 找出该玩家所有闪
                shan_cards = [c for c in p.hand_cards if c.name_enum == CardName.SHAN]

                if not shan_cards:
                    continue

                # 询问队友是否愿意替曹操打闪
                provided = p.ask_use_card_response(
                    CardName.SHAN,
                    shan_cards,
                    f"替 {self.name} 发动【护驾】（{context}）"
                )

                if provided:
                    # 队友提供闪
                    p.hand_cards.remove(provided)
                    game_logger.log_info(
                        f"【护驾】成功：{p.name} 替 {self.name} 打出了【闪】"
                    )
                    return provided

        # ---------- 3. 魏势力无人帮忙 → 曹操自己打闪 ----------
        return super().ask_use_shan(context)
