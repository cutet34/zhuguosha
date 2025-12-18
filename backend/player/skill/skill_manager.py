from typing import Dict, List
from config.enums import CharacterName
from backend.player.skill.skill_base import Skill


class SkillManager:
    """
    技能管理器

    职责：管理三国杀游戏中所有武将的技能配置
    实现：通过字典建立 武将名 -> 技能列表 的映射关系

    设计模式：管理表模式
    用途：集中管理技能配置，方便查询和扩展新武将技能
    """

    def __init__(self):
        """
        初始化技能管理器

        属性：
            skills (Dict[CharacterName, List[Skill]]):
                核心存储结构，键为武将枚举，值为该武将的所有技能对象列表
                示例：{CharacterName.ZHUGELIANG: [观星技能对象, 空城技能对象]}
        """
        # 使用字典存储技能配置，键为CharacterName枚举，值为Skill对象列表
        # 初始化为空字典，通过register_skill方法动态添加技能
        self.skills: Dict[CharacterName, List[Skill]] = {}

    def register_skill(self, character: CharacterName, skill: Skill) -> None:
        """
        注册单个技能到指定武将

        Args:
            character (CharacterName): 武将名称枚举
            skill (Skill): 技能对象，包含技能名称、效果、触发条件等实现

        Returns:
            None: 无返回值，直接修改内部skills字典

        功能：
            1. 如果该武将首次添加技能，创建空列表
            2. 将技能对象添加到该武将的技能列表中

        """
        # 使用setdefault确保武将技能列表存在，然后添加技能
        self.skills.setdefault(character, []).append(skill)

    def get_skills(self, character: CharacterName) -> List[Skill]:
        """
        获取指定武将的所有技能

        Args:
            character (CharacterName): 要查询的武将名称枚举

        Returns:
            List[Skill]: 该武将的技能列表，如果武将未注册则返回空列表


        """
        # 使用get方法安全获取，避免KeyError，未注册的武将返回空列表
        return self.skills.get(character, [])

    def has_skills(self, character: CharacterName) -> bool:
        """
        检查指定武将是否注册了技能

        Args:
            character (CharacterName): 要检查的武将名称枚举

        Returns:
            bool: 如果武将注册了技能（且技能列表非空）返回True，否则返回False
        """
        return character in self.skills and len(self.skills[character]) > 0

    def get_all_characters_with_skills(self) -> List[CharacterName]:
        """
        获取所有已注册技能的武将列表

        Returns:
            List[CharacterName]: 所有已注册技能的武将名称枚举列表
        """
        return list(self.skills.keys())

    def clear_skills(self, character: CharacterName = None) -> None:
        """
        清除技能注册信息

        Args:
            character (CharacterName | None):
                如果指定武将，则清除该武将的技能；
                如果为None，则清除所有武将的技能
        Returns:
            None: 无返回值，直接修改内部skills字典
        """
        if character is None:
            self.skills.clear()
        elif character in self.skills:
            self.skills[character] = []