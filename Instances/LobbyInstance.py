import time

import pyautogui
import pyperclip
import win32gui
import win32con
import keyboard

from Helpers.MouseController import MouseHelper


class LobbyInstance:
    def __init__(self, leader, bots):
        self.leader = leader
        self.bots = bots

    @staticmethod
    def _is_cancelled():
        try:
            return keyboard.is_pressed("ctrl+q")
        except Exception:
            return False

    @staticmethod
    def _focus_window(hwnd):
        try:
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            except Exception:
                pass

            if not win32gui.IsWindow(hwnd):
                return False

            try:
                win32gui.BringWindowToTop(hwnd)
            except Exception:
                pass

            if not win32gui.IsWindow(hwnd):
                return False

            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                return False

            return True
        except Exception:
            return False

    def Collect(self):
        leader_hwnd = self.leader.FindCSWindow()

        for bot in self.bots:
            if self._is_cancelled():
                return False

            hwnd = bot.FindCSWindow()
            if not self._focus_window(hwnd):
                continue

            time.sleep(0.1)
            bot.MoveMouse(380, 100)
            time.sleep(0.5)
            bot.ClickMouse(375, 8)
            time.sleep(0.5)
            bot.ClickMouse(375, 8)
            time.sleep(0.5)
            bot.ClickMouse(204, 157)
            time.sleep(0.5)
            bot.ClickMouse(237, 157)

            if self._is_cancelled():
                return False

            if not self._focus_window(leader_hwnd):
                continue

            self.leader.MoveMouse(380, 100)
            time.sleep(0.6)
            self.leader.ClickMouse(375, 8)
            time.sleep(1)
            MouseHelper.PasteText()
            time.sleep(1)
            self.leader.ClickMouse(195, 140)
            time.sleep(1.5)
            for i in range(142, 221, 5):
                self.leader.ClickMouse(235, i)
                time.sleep(0.001)
            self.leader.ClickMouse(235, 165)

        time.sleep(1.5)

        for bot in self.bots:
            if self._is_cancelled():
                return False
            hwnd = bot.FindCSWindow()
            if not self._focus_window(hwnd):
                continue
            bot.MoveMouse(380, 100)
            time.sleep(0.6)
            bot.ClickMouse(306, 37)

        return True

    def Disband(self):
        # По ТЗ disband должен работать строго с bot1/bot2.
        primary_bots = self.bots[:1]

        for bot in primary_bots:
            if self._is_cancelled():
                return False
            hwnd = bot.FindCSWindow()
            if not self._focus_window(hwnd):
                continue
            time.sleep(0.1)
            bot.MoveMouse(380, 100)
            time.sleep(0.5)
            bot.ClickMouse(375, 8)

        return True