# 枚举定义文件
from enum import Enum

class CardSuit(Enum):
    """花色枚举"""
    HEARTS = "红桃"
    DIAMONDS = "方块"
    CLUBS = "梅花"
    SPADES = "黑桃"

class CardType(Enum):
    """牌类型枚举"""
    BASIC = "基本牌"
    TRICK = "锦囊牌"
    EQUIPMENT = "装备牌"

class EquipmentType(Enum):
    """装备类型枚举"""
    WEAPON = "武器"
    ARMOR = "防具"
    HORSE_PLUS = "+1马"
    HORSE_MINUS = "-1马"

class EquipmentName(Enum):
    # 装备牌 - 武器
    QING_GANG_JIAN = "青釭剑"
    ZHU_GE_LIAN_NU = "诸葛连弩"
    
    # 装备牌 - 防具
    REN_WANG_DUN = "仁王盾"
    
    # 装备牌 - 坐骑
    JIN_GONG_MA = "进攻马"  # +1马
    FANG_YU_MA = "防御马"   # -1马

class GameEvent(Enum):
    """游戏事件枚举"""
    PREPARE = "准备阶段"
    DRAW_CARD = "摸牌"
    PLAY_CARD = "出牌"
    DISCARD_CARD = "弃牌"
    DAMAGE = "受伤"
    HEAL = "回复"
    DEATH = "死亡"
    EQUIP = "装备"

class PlayerStatus(Enum):
    """玩家状态枚举"""
    ALIVE = "存活"
    DEAD = "死亡"

class ControlType(Enum):
    """操控类型枚举"""
    HUMAN = "玩家操控"
    AI = "AI操控"
    SIMPLE_AI = "规则操控"

class PlayerIdentity(Enum):
    """玩家身份枚举"""
    LORD = "主公"      # 主公
    LOYALIST = "忠臣"  # 忠臣
    REBEL = "反贼"     # 反贼
    TRAITOR = "内奸"   # 内奸

class CharacterName(Enum):
    """武将名枚举"""
    BAI_BAN_WU_JIANG = "白板武将"  # 白板武将
    GUAN_YU = "关羽"              # 关羽
    ZHANG_FEI = "张飞"            # 张飞
    LV_MENG = "吕蒙"              # 吕蒙
    LING_CAO = "凌操"             # 凌操
    ZHU_GUO_SHA = "猪国杀武将"     # 猪国杀武将（无弃牌阶段）


class TargetType(Enum):
    """目标类型枚举"""
    ATTACKABLE = "攻击范围内的目标"  # 攻击范围内的目标
    DIS1 = "距离为1的目标"         # 距离为1的目标
    ALL = "所有目标"              # 所有目标
    SELF = "自己"                # 自己

class CardName(Enum):
    """牌名枚举"""
    # 基本牌
    SHA = "杀"
    SHAN = "闪"
    TAO = "桃"
    
    # 锦囊牌
    WU_XIE_KE_JI = "无懈可击"
    NAN_MAN_RU_QIN = "南蛮入侵"
    WAN_JIAN_QI_FA = "万箭齐发"
    JUE_DOU = "决斗"
    
    # 装备牌 - 武器
    QING_GANG_JIAN = "青釭剑"
    ZHU_GE_LIAN_NU = "诸葛连弩"
    
    # 装备牌 - 防具
    REN_WANG_DUN = "仁王盾"
    
    # 装备牌 - 坐骑
    JIN_GONG_MA = "进攻马"  # +1马
    FANG_YU_MA = "防御马"   # -1马

class EffectName(Enum):
    """特效名称枚举"""
    HURT = "hurt"
    HEAL = "heal"
    DAMAGE = "damage"
    BOOM = "boom"