# 游戏控制盘模块
from typing import Dict, Any, Optional, Tuple
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.player_controller.player_controller import PlayerController
from backend.deck.deck import Deck
from backend.card.card import Card
from backend.utils.logger import game_logger
from backend.game_controller.card_effect_handler import CardEffectHandlerFactory
from config.enums import CardName, CardType, GameEvent, CardSuit
from config.simple_card_config import SimpleGameConfig


class GameController:
    """游戏控制盘模块
    
    负责游戏的主循环和牌效果处理
    """
    
    def __init__(self, config: SimpleGameConfig):
        """初始化函数
        
        Args:
            config: GameConfig配置对象
        """
        self.config = config
        self.player_controller = None
        self.deck = None
        self.current_player_id = None
        self.game_ended = False
    
    def initialize(self) -> None:
        """初始化游戏
        
        根据配置文件调用玩家控制模块生成玩家、调用牌堆模块生成牌堆
        """
        game_logger.log_info("开始初始化游戏...")
        
        # 创建牌堆
        self.deck = Deck(self.config)
        game_logger.log_info(f"牌堆创建完成，总牌数: {len(self.deck.cards)}")
        
        # 创建玩家控制器
        self.player_controller = PlayerController(self.config, self.deck)
        game_logger.log_info(f"玩家控制器创建完成，玩家数量: {len(self.player_controller.players)}")
        
        # 获取初始玩家
        self.current_player_id = self.player_controller.get_initial_player()
        game_logger.log_info(f"初始玩家ID: {self.current_player_id}")
        
        game_logger.log_info("游戏初始化完成")
    
    def start_game(self) -> None:
        """开始游戏主循环"""
        # 如果还没有初始化，则初始化
        if self.player_controller is None:
            self.initialize()
        game_logger.log_info("游戏主循环开始")
        
        # 主循环
        turn_number = 1
        max_turns = 1000  # 防止无限循环
        while not self.game_ended and turn_number <= max_turns:
            current_player = self.player_controller.get_player(self.current_player_id)
            
            # 检查当前玩家是否有效
            if current_player is None:
                game_logger.log_error(f"当前玩家ID {self.current_player_id} 无效，强制结束游戏")
                self.game_ended = True
                break
            
            # 检查当前玩家是否存活
            if not current_player.is_alive():
                # 如果当前玩家已死亡，跳到下一个玩家
                self.current_player_id = self.player_controller.next_player(self.current_player_id)
                continue
            
            # 记录回合开始
            game_logger.log_turn_start(current_player.name, turn_number)
            
            # 记录所有玩家状态
            game_logger.log_all_players_status(self.player_controller.players)
            
            # 记录牌堆状态
            game_logger.log_deck_status(self.deck)
            
            # 准备阶段
            game_logger.log_phase_start(current_player.name, "准备")
            self.player_controller.event(self.current_player_id, GameEvent.PREPARE)
            # 同步状态
            self.player_controller.control_manager.sync_game_state()
            
            # 摸牌阶段
            game_logger.log_phase_start(current_player.name, "摸牌")
            self.player_controller.event(self.current_player_id, GameEvent.DRAW_CARD)
            # 同步状态（摸牌后状态变化）
            self.player_controller.control_manager.sync_player_state(self.current_player_id)
            
            # 出牌阶段
            game_logger.log_phase_start(current_player.name, "出牌")
            play_card_count = 0
            max_play_cards = 100  # 防止无限出牌
            while play_card_count < max_play_cards:
                card, targets = self.player_controller.event(
                    self.current_player_id, GameEvent.PLAY_CARD
                )
                if card is None:
                    break
                play_card_count += 1
                game_logger.log_info(f"玩家 {current_player.name} 打出牌: {card.name}")
                # 处理牌效果（预留接口）
                self._handle_card_effect(card, targets)
                # 同步状态（出牌后状态变化）
                self.player_controller.control_manager.sync_game_state()
                
                # 检查游戏是否在出牌过程中结束
                if self.player_controller.game_over():
                    self.game_ended = True
                    break
            
            # 弃牌阶段
            self.player_controller.event(self.current_player_id, GameEvent.DISCARD_CARD)
            # 同步状态（弃牌后状态变化）
            self.player_controller.control_manager.sync_player_state(self.current_player_id)
            
            # 记录回合结束
            game_logger.log_turn_end(current_player.name)
            
            # 检查游戏是否结束
            if self.player_controller.game_over():
                # 输出胜利方
                winner = self.player_controller.get_winner()
                if winner:
                    game_logger.log_info(f" 游戏结束！{winner}")
                    print(f" 游戏结束！{winner}")
                break
            
            # 检查是否还有存活玩家
            alive_players = [p for p in self.player_controller.players if p.is_alive()]
            if not alive_players:
                self.game_ended = True
                break
            
            # 下一个玩家
            next_player_id = self.player_controller.next_player(self.current_player_id)
            if next_player_id == self.current_player_id and len(alive_players) > 1:
                # 如果下一个玩家还是自己，说明有问题，强制结束
                game_logger.log_warning(f"next_player返回了相同的玩家ID: {next_player_id}，强制结束游戏")
                self.game_ended = True
                break
            self.current_player_id = next_player_id
            turn_number += 1
        
        if turn_number > max_turns:
            game_logger.log_error(f"游戏超过最大回合数 {max_turns}，强制结束")
            self.game_ended = True
        
        # 善后工作
        self._cleanup()
    
    def _handle_card_effect(self, card: Card, targets: list) -> None:
        """处理牌效果（使用策略模式）
        
        Args:
            card: 出的牌
            targets: 目标列表
        """
        # 使用工厂模式创建对应的处理器
        handler = CardEffectHandlerFactory.create_handler(card, self)
        if handler:
            handler.handle(card, targets)
        else:
            game_logger.log_warning(f"未知的牌类型或牌名: {card.name}")
    
    def _cleanup(self) -> None:
        """善后工作（回收内存等）"""
        # 目前主要用于关闭 PlayerController 中的后台线程（如前端输入分发器）
        try:
            if self.player_controller is not None:
                stop = getattr(self.player_controller, "stop", None)
                if callable(stop):
                    stop()
        except Exception:
            # 清理不应影响正常结束
            pass
