from config.simple_card_config import SimpleGameConfig, SimpleCardConfig
from config.enums import EquipmentType, CardName
class CommEvent:
    """Base class for communication events."""
    pass

class DrawCardEvent(CommEvent):
    def __init__(self, card_config: SimpleCardConfig = None, to_player: int = None):
        self.card_config = card_config  # None表示牌面信息不可见
        self.to_player = to_player
class PlayCardEvent(CommEvent):
    def __init__(self, card_config: SimpleCardConfig, from_player: int, to_player: int, 
                 response_type: str = None, response_target: int = None, 
                 original_card_name: str = None, is_effective: bool = None):
        """
        出牌事件
        
        Args:
            card_config: 牌配置
            from_player: 出牌玩家ID
            to_player: 目标玩家ID
            response_type: 响应类型（"响应决斗"、"响应南蛮入侵"、"响应万箭齐发"、"响应杀"等）
            response_target: 响应目标（对于响应类事件，表示响应的目标玩家ID）
            original_card_name: 原始牌名（对于响应类事件，表示响应的原始牌）
            is_effective: 是否生效（对于无懈可击，表示目标是否生效）
        """
        self.card_config = card_config
        self.from_player = from_player
        self.to_player = to_player
        self.response_type = response_type  # 响应类型
        self.response_target = response_target  # 响应目标
        self.original_card_name = original_card_name  # 原始牌名
        self.is_effective = is_effective  # 是否生效（无懈可击用）
class DiscardCardEvent(CommEvent):
    def __init__(self, card_config: SimpleCardConfig, player: int):
        self.card_config = card_config
        self.player = player
class HPChangeEvent(CommEvent):
    def __init__(self, player_id: int, new_hp: int, source_player_id: int = None, 
                 damage_type: str = None, original_card_name: str = None):
        """
        血量变化事件
        
        Args:
            player_id: 玩家ID
            new_hp: 新的血量值
            source_player_id: 伤害来源玩家ID（如果是伤害）
            damage_type: 伤害类型（"杀"、"决斗"、"南蛮入侵"、"万箭齐发"等）
            original_card_name: 原始牌名（造成伤害的牌）
        """
        self.player_id = player_id
        self.new_hp = new_hp
        self.source_player_id = source_player_id  # 伤害来源
        self.damage_type = damage_type  # 伤害类型
        self.original_card_name = original_card_name  # 原始牌名
class EquipChangeEvent(CommEvent):
    def __init__(self, player_id: int, equip_name: CardName, equip_type: EquipmentType):
        self.player_id = player_id
        self.equip_name = equip_name
        self.equip_type = equip_type
class DeathEvent(CommEvent):
    def __init__(self, player_id: int):
        self.player_id = player_id
class GameOverEvent(CommEvent):
    def __init__(self, winner_id: int):
        self.winner_id = winner_id

class AckEvent(CommEvent):
    """ACK确认事件"""
    def __init__(self, original_event_id: int, success: bool = True, message: str = ""):
        self.original_event_id = original_event_id
        self.success = success
        self.message = message
class InputRequestEvent(CommEvent):
    """后端 -> 前端：请求玩家输入（选牌/选目标/弃牌/是否发动技能）。

    Args:
        request_id: 请求唯一ID，用于匹配 InputResponseEvent。
        player_id: 需要输入的玩家ID。
        action: 行为类型，如 "select_card" / "select_targets" / "discard" / "ask_activate_skill"。
        prompt: 前端提示文本。
        options: 结构化选项数据（dict），由 action 约定字段。
    """

    def __init__(self, request_id: str, player_id: int, action: str, prompt: str = "", options: dict = None):
        self.request_id = request_id
        self.player_id = player_id
        self.action = action
        self.prompt = prompt
        self.options = options or {}


class InputResponseEvent(CommEvent):
    """前端 -> 后端：提交玩家输入结果。

    Args:
        request_id: 对应 InputRequestEvent 的 request_id。
        player_id: 玩家ID。
        payload: 返回数据（dict），由 action 约定字段。
            推荐：
            - select_card: {"index": int} 或 {"cancel": True}
            - select_targets: {"target_ids": [int,...]} 或 {"cancel": True}
            - discard: {"indices": [int,...]}
            - ask_activate_skill: {"activate": bool}
    """

    def __init__(self, request_id: str, player_id: int, payload: dict):
        self.request_id = request_id
        self.player_id = player_id
        self.payload = payload or {}
