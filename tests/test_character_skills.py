# 武将技能测试
import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.player.player import (
    Player,
    ZhangFeiPlayer,
    LvMengPlayer,
    LingCaoPlayer,
    ZhouYuPlayer,
    SunQuanPlayer,
    HuangGaiPlayer,
)
from backend.deck.deck import Deck
from backend.card.card import Card
from config.simple_card_config import SimpleGameConfig, SimpleCardConfig, SimplePlayerConfig
from config.enums import CardSuit, CardName, ControlType, PlayerIdentity, CharacterName, GameEvent


class TestCharacterSkills(unittest.TestCase):
    """武将技能测试"""
    
    def setUp(self):
        """测试前准备"""
        deck_config = [
            SimpleCardConfig(CardName.SHA, CardSuit.HEARTS, 1, count=20),
            SimpleCardConfig(CardName.SHAN, CardSuit.HEARTS, 2, count=10),
            SimpleCardConfig(CardName.TAO, CardSuit.HEARTS, 1, count=5),
            SimpleCardConfig(CardName.QING_GANG_JIAN, CardSuit.SPADES, 6, count=1),
            SimpleCardConfig(CardName.REN_WANG_DUN, CardSuit.SPADES, 2, count=1),
            SimpleCardConfig(CardName.JIN_GONG_MA, CardSuit.HEARTS, 5, count=1),
            SimpleCardConfig(CardName.FANG_YU_MA, CardSuit.SPADES, 5, count=1),
        ]
        players_config = [
            SimplePlayerConfig("玩家1", CharacterName.BAI_BAN_WU_JIANG, PlayerIdentity.REBEL, ControlType.AI),
            SimplePlayerConfig("玩家2", CharacterName.BAI_BAN_WU_JIANG, PlayerIdentity.REBEL, ControlType.AI),
        ]
        self.config = SimpleGameConfig(deck_config=deck_config, players_config=players_config, shuffle_deck=False)
        self.deck = Deck(self.config)
    
    def test_zhangfei_skill_paoxiao(self):
        """测试张飞技能咆哮：出的杀不限次数"""
        zhangfei = ZhangFeiPlayer(1, "张飞", ControlType.SIMPLE_AI, self.deck, PlayerIdentity.REBEL, CharacterName.ZHANG_FEI)
        
        # 给张飞多张杀牌
        sha_cards = [Card(CardSuit.HEARTS, i + 1, CardName.SHA) for i in range(3)]
        zhangfei.hand_cards = sha_cards
        
        # 创建目标玩家
        target_player = Player(2, "目标", ControlType.SIMPLE_AI, self.deck, PlayerIdentity.REBEL, CharacterName.BAI_BAN_WU_JIANG)
        available_targets = {"attackable": [target_player.player_id]}
        
        # 第一次出杀
        card1, targets1 = zhangfei.play_card(available_targets)
        self.assertIsNotNone(card1)
        self.assertEqual(card1.name_enum, CardName.SHA)
        
        # 验证sha_used_this_turn被重置（可以继续出杀）
        # 由于技能发动，sha_used_this_turn应该被重置为False
        self.assertFalse(zhangfei.sha_used_this_turn)
        
        # 第二次出杀（应该可以继续出）
        card2, targets2 = zhangfei.play_card(available_targets)
        self.assertIsNotNone(card2)
        self.assertEqual(card2.name_enum, CardName.SHA)
    
    def test_lvmeng_skill_keji_no_sha(self):
        """测试吕蒙技能克己：本回合未使用杀时不弃牌"""
        lvmeng = LvMengPlayer(1, "吕蒙", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.LV_MENG)
        
        # 清空初始手牌，然后添加6张牌
        lvmeng.hand_cards.clear()
        for i in range(6):
            card = Card(CardSuit.HEARTS, i + 1, CardName.SHA)
            lvmeng.hand_cards.append(card)
        
        # 确保本回合未使用杀
        lvmeng.sha_used_this_turn = False
        
        # 发动技能弃牌（应该不弃牌）
        discarded = lvmeng.discard_card()
        self.assertEqual(len(discarded), 0)
        self.assertEqual(len(lvmeng.hand_cards), 6)  # 手牌未减少
    
    def test_lvmeng_skill_keji_with_sha(self):
        """测试吕蒙技能克己：本回合使用过杀时需要弃牌"""
        lvmeng = LvMengPlayer(1, "吕蒙", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.LV_MENG)
        
        # 清空初始手牌，然后添加6张牌
        lvmeng.hand_cards.clear()
        for i in range(6):
            card = Card(CardSuit.HEARTS, i + 1, CardName.SHA)
            lvmeng.hand_cards.append(card)
        
        # 标记本回合已使用杀
        lvmeng.sha_used_this_turn = True
        
        # 发动技能弃牌（应该执行默认弃牌）
        discarded = lvmeng.discard_card()
        self.assertEqual(len(discarded), 2)  # 应该弃掉2张（6-4=2）
        self.assertEqual(len(lvmeng.hand_cards), 4)  # 手牌应该等于血量上限
    
    def test_lingcao_skill_dujin_no_equipment(self):
        """测试凌操技能独进：无装备时摸3张"""
        lingcao = LingCaoPlayer(1, "凌操", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.LING_CAO)
        
        initial_hand_size = len(lingcao.hand_cards)
        initial_deck_size = len(self.deck.cards)
        
        # 发动技能摸牌
        drawn_cards = lingcao.draw_card_phase()
        
        # 无装备：3 + 0/2 = 3张
        self.assertEqual(len(drawn_cards), 3)
        self.assertEqual(len(lingcao.hand_cards), initial_hand_size + 3)
        self.assertEqual(len(self.deck.cards), initial_deck_size - 3)
    
    def test_lingcao_skill_dujin_with_equipment(self):
        """测试凌操技能独进：有装备时摸牌数量增加"""
        lingcao = LingCaoPlayer(1, "凌操", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.LING_CAO)
        
        # 装备2件装备（使用装备管理器）
        weapon = Card(CardSuit.SPADES, 6, CardName.QING_GANG_JIAN)
        armor = Card(CardSuit.SPADES, 2, CardName.REN_WANG_DUN)
        lingcao.equip(weapon)
        lingcao.equip(armor)
        
        initial_hand_size = len(lingcao.hand_cards)
        initial_deck_size = len(self.deck.cards)
        
        # 发动技能摸牌
        drawn_cards = lingcao.draw_card_phase()
        
        # 2件装备：3 + 2/2 = 4张
        self.assertEqual(len(drawn_cards), 4)
        self.assertEqual(len(lingcao.hand_cards), initial_hand_size + 4)
        self.assertEqual(len(self.deck.cards), initial_deck_size - 4)
    
    def test_lingcao_skill_dujin_four_equipment(self):
        """测试凌操技能独进：4件装备时摸5张"""
        lingcao = LingCaoPlayer(1, "凌操", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.LING_CAO)
        
        # 装备4件装备（使用装备管理器）
        weapon = Card(CardSuit.SPADES, 6, CardName.QING_GANG_JIAN)
        armor = Card(CardSuit.SPADES, 2, CardName.REN_WANG_DUN)
        horse_plus = Card(CardSuit.HEARTS, 5, CardName.FANG_YU_MA)
        horse_minus = Card(CardSuit.SPADES, 5, CardName.JIN_GONG_MA)
        lingcao.equip(weapon)
        lingcao.equip(armor)
        lingcao.equip(horse_plus)
        lingcao.equip(horse_minus)
        
        initial_hand_size = len(lingcao.hand_cards)
        
        # 发动技能摸牌
        drawn_cards = lingcao.draw_card_phase()
        
        # 4件装备：2 + 4/2 = 4张
        self.assertEqual(len(drawn_cards), 5)
        self.assertEqual(len(lingcao.hand_cards), initial_hand_size + 5)
    
    def test_lingcao_skill_dujin_not_activate(self):
        """测试凌操技能独进：可以选择不发动技能，此时摸2张（默认摸牌）"""
        lingcao = LingCaoPlayer(1, "凌操", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.LING_CAO)
        
        initial_hand_size = len(lingcao.hand_cards)
        initial_deck_size = len(self.deck.cards)
        
        # 设置control不使用技能（通过ask_activate_skill返回False）
        lingcao.control.set_use_skill(False)
        
        # 不发动技能摸牌（应该执行默认摸牌流程，摸2张）
        drawn_cards = lingcao.draw_card_phase()
        
        # 不发动技能时，应该摸2张（默认摸牌数量）
        self.assertEqual(len(drawn_cards), 2)
        self.assertEqual(len(lingcao.hand_cards), initial_hand_size + 2)
        self.assertEqual(len(self.deck.cards), initial_deck_size - 2)

    def test_zhouyu_skill_yingzi_draw_plus_one(self):
        """测试周瑜技能英姿：摸牌阶段额定摸牌数 +1（通过 modify_draw_num 钩子）。"""
        zhouyu = ZhouYuPlayer(1, "周瑜", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.ZHOU_YU)

        initial_hand_size = len(zhouyu.hand_cards)
        initial_deck_size = len(self.deck.cards)

        drawn_cards = zhouyu.draw_card_phase()

        # 默认摸牌 2 + 英姿 +1 => 3
        self.assertEqual(len(drawn_cards), 3)
        self.assertEqual(len(zhouyu.hand_cards), initial_hand_size + 3)
        self.assertEqual(len(self.deck.cards), initial_deck_size - 3)

    def test_sunquan_skill_zhiheng_discard_and_draw_same_count(self):
        """测试孙权技能制衡：弃置任意张（此版本无选择接口时退化为弃置全部），摸等量牌。"""
        sunquan = SunQuanPlayer(1, "孙权", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.SUN_QUAN)

        # 固定手牌为 3 张，避免受初始发牌影响
        sunquan.hand_cards.clear()
        for i in range(3):
            sunquan.hand_cards.append(Card(CardSuit.HEARTS, i + 1, CardName.SHA))

        skill = sunquan.skills[0]
        context = {"event_type": GameEvent.PLAY_CARD}
        self.assertTrue(skill.can_activate(sunquan, context))

        discard_before = len(self.deck.discard_pile)
        hand_before = len(sunquan.hand_cards)

        skill.activate(sunquan, context)

        # 退化为“弃置全部手牌”：弃 3 摸 3，最终手牌数量不变
        self.assertEqual(len(sunquan.hand_cards), hand_before)
        self.assertEqual(len(self.deck.discard_pile), discard_before + hand_before)

    def test_huanggai_skill_kurou_hp_minus_one_draw_two(self):
        """测试黄盖技能苦肉：失去 1 点体力，摸 2 张牌。"""
        huanggai = HuangGaiPlayer(1, "黄盖", ControlType.AI, self.deck, PlayerIdentity.REBEL, CharacterName.HUANG_GAI)

        # 为了避免直接进入死亡流程，确保体力至少为 2
        huanggai.current_hp = 2

        skill = huanggai.skills[0]
        context = {"event_type": GameEvent.PLAY_CARD}
        self.assertTrue(skill.can_activate(huanggai, context))

        hp_before = huanggai.current_hp
        hand_before = len(huanggai.hand_cards)

        skill.activate(huanggai, context)

        self.assertEqual(huanggai.current_hp, hp_before - 1)
        self.assertEqual(len(huanggai.hand_cards), hand_before + 2)


if __name__ == '__main__':
    unittest.main()

