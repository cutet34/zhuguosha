import pygame
import platform
import os

class Fonts:
    # 定义不同平台下的中文字体优先级列表
    CHINESE_FONTS = {
        'windows': ['SimHei', 'Microsoft YaHei', 'SimHei', 'FangSong', 'KaiTi'],
        'darwin': ['PingFang SC', 'Hiragino Sans GB', 'STHeiti', 'Heiti SC', 'Arial Unicode MS'],
        'linux': ['Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'DejaVu Sans', 'Liberation Sans']
    }

    @staticmethod
    def get_system_type():
        """获取系统类型"""
        system = platform.system().lower()
        if system == 'windows':
            return 'windows'
        elif system == 'darwin':
            return 'darwin'  # macOS
        elif system == 'linux':
            return 'linux'
        else:
            return 'linux'  # 默认使用linux字体列表

    @staticmethod
    def get_available_chinese_font():
        """获取可用的中文字体"""
        system_type = Fonts.get_system_type()
        font_list = Fonts.CHINESE_FONTS.get(system_type, Fonts.CHINESE_FONTS['linux'])

        # 获取系统所有可用字体
        available_fonts = pygame.font.get_fonts()

        # 按优先级查找可用的中文字体
        for font_name in font_list:
            # 将字体名转换为pygame使用的格式（小写，空格替换）
            font_variants = [
                font_name.lower(),
                font_name.lower().replace(' ', ''),
                font_name.lower().replace(' ', '-'),
            ]

            for variant in font_variants:
                if variant in available_fonts:
                    return font_name

        # 如果没有找到中文字体，返回默认字体
        return None  # pygame会使用默认字体

    @staticmethod
    def get_font(size, font_name=None):
        """获取字体对象，支持回退机制"""
        if font_name:
            try:
                return pygame.font.SysFont(font_name, size)
            except:
                pass

        # 尝试使用中文字体
        chinese_font = Fonts.get_available_chinese_font()
        if chinese_font:
            try:
                return pygame.font.SysFont(chinese_font, size)
            except:
                pass

        # 最后回退到默认字体
        try:
            return pygame.font.SysFont(None, size)  # None表示使用系统默认字体
        except:
            return pygame.font.Font(None, size)  # 使用pygame默认字体

    @staticmethod
    def big():
        return Fonts.get_font(36)

    @staticmethod
    def medium():
        return Fonts.get_font(28)

    @staticmethod
    def small():
        return Fonts.get_font(20)

    @staticmethod
    def li_shu_48():
        """尝试获取隶书字体，如果没有则使用普通中文字体"""
        system_type = Fonts.get_system_type()

        # 特殊字体列表（隶书等）
        special_fonts = {
            'windows': ['LiSu', 'FangSong', 'KaiTi'],
            'darwin': ['STFangsong', 'STKaiti', 'PingFang SC'],
            'linux': ['AR PL UKai CN', 'AR PL UMing CN', 'Noto Sans CJK SC']
        }

        font_list = special_fonts.get(system_type, special_fonts['linux'])
        available_fonts = pygame.font.get_fonts()

        for font_name in font_list:
            font_variants = [
                font_name.lower(),
                font_name.lower().replace(' ', ''),
                font_name.lower().replace(' ', '-'),
            ]

            for variant in font_variants:
                if variant in available_fonts:
                    return pygame.font.SysFont(font_name, 48)

        # 回退到普通中文字体
        return Fonts.get_font(48)
