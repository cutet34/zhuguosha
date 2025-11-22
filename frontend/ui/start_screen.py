import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))
import pygame
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
from typing import Optional, Tuple, Dict, Any

from frontend.util.size import DEFAULT_WINDOW_SIZE
from frontend.util.color import default_colors
from frontend.util.fonts import Fonts

from config.simple_detailed_config import create_simple_default_game_config
BUTTON_RECT = pygame.Rect(300, 260, 300, 80)

class StartScreen:
    """
    在 pygame 窗口内显示开始界面（一个按钮）。
    点击按钮后弹出系统文件选择对话（tkinter），
    读取并简单验证 JSON 配置，返回 (config_dict, screen, clock)
    如果用户取消或配置无效，允许重试或退出。
    """

    def __init__(self, window_size=DEFAULT_WINDOW_SIZE, title="猪国杀 - 启动"):
        self.window_size = window_size
        self.title = title
        self._msg = ""  # 显示错误/提示信息
        self._msg_timer = 0.0

        btn_width, btn_height = 300, 80
        win_w, win_h = self.window_size
        btn_x = (win_w - btn_width) // 2
        btn_y = int(win_h * 2 / 3)
        self.button_rect = pygame.Rect(btn_x, btn_y, btn_width, btn_height)

        gap = 30
        rand_btn_y = btn_y + btn_height + gap
        self.rand_button_rect = pygame.Rect(btn_x, rand_btn_y, btn_width, btn_height)


    def _ask_open_file(self, filetypes=(("JSON files", "*.json"), ("All files","*.*")))-> Optional[str]:
        """
        使用 tkinter 弹出文件选择，返回路径或 None（取消）。
        注意：必须在主线程调用。
        """
        root = tk.Tk()
        root.withdraw()
        # 属性确保对话框置顶（尽可能）
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        path = filedialog.askopenfilename(title="选择初始配置文件", filetypes=filetypes)
        try:
            root.update()
        except Exception:
            pass
        root.destroy()
        if not path:
            return None
        return path

    def _load_and_validate(self, path: str) -> Tuple[Optional[Dict[str,Any]], Optional[str]]:
        """
        读取 JSON 配置并做最基础的校验（你可以根据和后端约定扩展）。
        返回 (config_dict, error_message)
        """
        if not os.path.exists(path):
            return None, f"文件不存在: {path}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            return None, f"解析 JSON 失败: {e}"

        # 最小校验(TODO)

        return cfg, None

    def run(self) -> Tuple[Optional[Dict[str,Any]], Optional[pygame.Surface], Optional[pygame.time.Clock]]:
        pygame.init()
        screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        pygame.display.set_caption(self.title)
        clock = pygame.time.Clock()

        font_big = Fonts.big()
        font_small = Fonts.small()

        running = True
        while running:
            dt = clock.tick(60) / 1000.0

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                elif ev.type == pygame.VIDEORESIZE:
                    # 更新窗口大小
                    self.window_size = (ev.w, ev.h)
                    screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
                    # 重新计算按钮位置
                    win_w, win_h = self.window_size
                    btn_width, btn_height = 300, 80
                    btn_x = (win_w - btn_width) // 2
                    btn_y = int(win_h * 2 / 3)
                    self.button_rect = pygame.Rect(btn_x, btn_y, btn_width, btn_height)
                    gap = 30
                    rand_btn_y = btn_y + btn_height + gap
                    self.rand_button_rect = pygame.Rect(btn_x, rand_btn_y, btn_width, btn_height)
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self.button_rect.collidepoint(ev.pos):
                        # 弹窗选择文件（阻塞）——在主线程执行，这是预期行为
                        path = self._ask_open_file()
                        if path is None:
                            # 用户取消，回到 start screen
                            self._msg = "已取消选择，点击按钮重试或关闭窗口退出。"
                            self._msg_timer = 300
                        else:
                            cfg, err = self._load_and_validate(path)
                            if err:
                                # 显示错误并允许重试
                                self._msg = f"配置无效: {err}"
                                self._msg_timer = 4.0
                            else:
                                # 成功：返回配置和当前 screen/clock 以供复用
                                pygame.display.quit()
                                return cfg
                    elif self.rand_button_rect.collidepoint(ev.pos):
                        # 随机开始
                        cfg = create_simple_default_game_config()
                        pygame.display.quit()
                        return cfg

            # 更新提示计时器
            if self._msg_timer > 0:
                self._msg_timer -= dt
                if self._msg_timer <= 0:
                    self._msg = ""

            # 渲染
            screen.fill(default_colors["greybrown"])
            title_surf = font_big.render("猪国杀", True, default_colors["darkbrown"])
            # 横向居中
            w, h = self.window_size
            title_x = (w - title_surf.get_width()) // 2
            title_pos = (title_x, 80)
            screen.blit(title_surf, title_pos)

            # 绘制“选择配置并开始”按钮
            pygame.draw.rect(screen, default_colors["midgrey"], self.button_rect, border_radius=8)
            btn_text = font_big.render("选择配置并开始", True, default_colors["white"])
            bx = self.button_rect.x + (self.button_rect.width - btn_text.get_width())/2
            by = self.button_rect.y + (self.button_rect.height - btn_text.get_height())/2
            screen.blit(btn_text, (bx, by))

            # 绘制“随机开始”按钮
            pygame.draw.rect(screen, default_colors["midgrey"], self.rand_button_rect, border_radius=8)
            rand_btn_text = font_big.render("随机开始", True, default_colors["white"])
            rbx = self.rand_button_rect.x + (self.rand_button_rect.width - rand_btn_text.get_width())/2
            rby = self.rand_button_rect.y + (self.rand_button_rect.height - rand_btn_text.get_height())/2
            screen.blit(rand_btn_text, (rbx, rby))

            # 显示提示/错误信息
            if self._msg:
                err_surf = font_small.render(self._msg, True, (255,180,180))
                screen.blit(err_surf, (50, 360))

            pygame.display.flip()

        return None