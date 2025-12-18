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
    ZHU_GE_LIAN_NU = "诸葛连弩"
    CI_XIONG_SHUANG_GU_JIAN = "雌雄双股剑"
    HAN_BING_JIAN = "寒冰剑"
    QING_GANG_JIAN = "青釭剑"
    ZHANG_BA_SHE_MAO = "丈八蛇矛"
    GUAN_SHI_FU = "贯石斧"
    QING_LONG_YAN_YUE_DAO = "青龙偃月刀"
    FANG_TIAN_HUA_JI = "方天画戟"
    QI_LIN_GONG = "麒麟弓"
    GU_DING_DAO = "古锭刀"
    ZHU_QUE_YU_SHAN = "朱雀羽扇"
    
    # 装备牌 - 防具
    BA_GUA_ZHEN = "八卦阵"
    REN_WANG_DUN = "仁王盾"
    TENG_JIA = "藤甲"
    BAI_YIN_SHI_ZI = "白银狮子"
    
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
    RL = "强化学习操控"

class PlayerIdentity(Enum):
    """玩家身份枚举"""
    LORD = "主公"      # 主公
    LOYALIST = "忠臣"  # 忠臣
    REBEL = "反贼"     # 反贼
    TRAITOR = "内奸"   # 内奸

class CharacterName(Enum):
    """武将名枚举"""
    BAI_BAN_WU_JIANG = "白板武将"  # 白板武将

#魏
    CAO_CAO = "曹操"
    SI_MA_YI = "司马懿"
    XIA_HOU_DUN = "夏侯惇"
    ZHANG_LIAO = "张辽"
    XU_CHU = "许褚"
    GUO_JIA = "郭嘉"
    ZHEN_JI = "甄姬"
    LI_DIAN = "李典"
    CAO_ZHANG = "曹彰"
    LE_JIN = "乐进"
#蜀
    LIU_BEI = "刘备"
    GUAN_YU = "关羽"
    ZHANG_FEI = "张飞"
    ZHU_GE_LIANG = "诸葛亮"
    ZHAO_YUN = "赵云"
    MA_CHAO = "马超"
    HUANG_YUE_YING = "黄月英"
    XU_SHU = "徐庶"
    YI_JI = "伊籍"
    GAN_FU_REN = "甘夫人"
#吴
    SUN_QUAN = "孙权"
    GAN_NING = "甘宁"
    LV_MENG = "吕蒙"
    HUANG_GAI = "黄盖"
    ZHOU_YU = "周瑜"
    DA_QIAO = "大乔"
    LU_XUN = "陆逊"
    SUN_SHANG_XIANG = "孙尚香"
    LING_CAO = "凌操"
#群
    HUA_TUO = "华佗"
    LV_BU = "吕布"
    DIAO_CHAN = "貂蝉"
    HUA_XIONG = "华雄"
    YUAN_SHU = "袁术"
    GONG_SUN_ZAN = "公孙瓒"
    PAN_FENG = "潘凤"

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
    JIU = "酒"
    LEI_SHA = "雷杀"
    HUO_SHA = "火杀"
    # 锦囊牌
    JUE_DOU = "决斗"
    JIE_DAO_SHA_REN = "借刀杀人"
    WAN_JIAN_QI_FA = "万箭齐发"
    NAN_MAN_RU_QIN = "南蛮入侵"
    GUO_HE_CHAI_QIAO = "过河拆桥"
    SHUN_SHOU_QIAN_YANG = "顺手牵羊"
    WU_ZHONG_SHENG_YOU = "无中生有"
    WU_GU_FENG_DENG = "五谷丰登"
    TAO_YUAN_JIE_YI = "桃园结义"
    WU_XIE_KE_JI = "无懈可击"
    HUO_GONG = "火攻"
    TIE_SUO_LIAN_HUAN = "铁索连环"
    LE_BU_SI_SHU = "乐不思蜀"
    SHAN_DIAN = "闪电"
    BING_LIANG_CUN_DUAN = "兵粮寸断"
    # 装备牌 - 武器
    ZHU_GE_LIAN_NU = "诸葛连弩"
    CI_XIONG_SHUANG_GU_JIAN = "雌雄双股剑"
    HAN_BING_JIAN = "寒冰剑"
    QING_GANG_JIAN = "青釭剑"
    ZHANG_BA_SHE_MAO = "丈八蛇矛"
    GUAN_SHI_FU = "贯石斧"
    QING_LONG_YAN_YUE_DAO = "青龙偃月刀"
    FANG_TIAN_HUA_JI = "方天画戟"
    QI_LIN_GONG = "麒麟弓"
    GU_DING_DAO = "古锭刀"
    ZHU_QUE_YU_SHAN = "朱雀羽扇"
    # 装备牌 - 防具
    BA_GUA_ZHEN = "八卦阵"
    REN_WANG_DUN = "仁王盾"
    TENG_JIA = "藤甲"
    BAI_YIN_SHI_ZI = "白银狮子"
    # 装备牌 - 坐骑
    JIN_GONG_MA = "进攻马"  # +1马
    FANG_YU_MA = "防御马"   # -1马

class EffectName(Enum):
    """特效名称枚举"""
    HURT = "hurt"
    HEAL = "heal"
    DAMAGE = "damage"
    BOOM = "boom"

class Faction(Enum):
    """阵营名称枚举"""
    WEI = "魏"
    SHU = "蜀"
    WU = "吴"
    QUN = "群"

class Gender(Enum):
    MALE="男"
    FEMALE="女"