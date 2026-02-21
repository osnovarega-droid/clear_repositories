import ctypes
import time
import random
import psutil
import win32gui
import win32api
import win32con
import win32process
import keyboard

from Instances.LobbyInstance import LobbyInstance
from Managers.AccountsManager import AccountManager
from Managers.LogManager import LogManager
from Managers.SettingsManager import SettingsManager


class LobbyManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LobbyManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._accountManager = AccountManager()
        self._logManager = LogManager()
        self._settingManager = SettingsManager()

        self.team1 = None
        self.team2 = None
        self._last_window_order_logins = []

        self._maps_scrolled_once = False
        self._initialized = True

    # -----------------------------
    # Validation / lifecycle
    # -----------------------------
    def isValid(self):
        if self.team1 is None or self.team2 is None:
            return False

        if not self.team1.leader.isCSValid():
            return False
        if any(not bot.isCSValid() for bot in self.team1.bots):
            return False

        if not self.team2.leader.isCSValid():
            return False
        if any(not bot.isCSValid() for bot in self.team2.bots):
            return False

        return True

    def CollectLobby(self):
        if self._is_cancelled():
            return False

        # Жесткий анализ и пересборка лобби по актуальному порядку окон
        if not self._auto_create_lobbies():
            return False

        # Перед действиями всегда выравниваем окна в линию 1-2-3-4
        if not self.MoveWindows():
            return False

        if self._is_cancelled():
            return False

        if self.team1 and self.team1.Collect() is False:
            return False
        if self.team2 and self.team2.Collect() is False:
            return False

        return True

    def DisbandLobbies(self):
        if self._is_cancelled():
            return False

        # Для disband используем именно текущих bot1/bot2 из активных команд.
        # Если команды ещё не собраны — тогда делаем анализ по окнам.
        if not self._ensure_lobbies_for_disband():
            return False

        # ВАЖНО: не переставляем окна перед disband, чтобы кликать по реальным bot1/bot2,
        # а не по "2-му/4-му" окну после принудительного MoveWindows.
        if self.team1 is not None:
            if self.team1.Disband() is False:
                return False
            self.team1 = None
        if self.team2 is not None:
            if self.team2.Disband() is False:
                return False
            self.team2 = None

        return True

    def _ensure_lobbies_for_disband(self):
        if self.team1 and self.team2 and self._has_primary_bots(self.team1, self.team2):
            return True
        return self._auto_create_lobbies()

    @staticmethod
    def _has_primary_bots(team1, team2):
        return bool(getattr(team1, 'bots', None)) and bool(getattr(team2, 'bots', None))

    def MoveWindows(self, ordered_logins=None):
        if not self.team1 or not self.team2:
            return False

        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

        ordered_members = []
        all_members = [self.team1.leader] + self.team1.bots + [self.team2.leader] + self.team2.bots
        member_by_login = {m.login: m for m in all_members if hasattr(m, 'login')}

        # По умолчанию: строго по списку аккаунтов.
        # Для Shuffle можно передать random ordered_logins.
        if ordered_logins:
            order_source = ordered_logins
        elif self._last_window_order_logins:
            order_source = self._last_window_order_logins
        else:
            order_source = [acc.login for acc in self._accountManager.accounts]

        for login in order_source:
            member = member_by_login.get(login)
            if member:
                ordered_members.append(member)

        if not ordered_members:
            ordered_members = all_members

        target_width = 383
        target_height = 280
        y = 0
        placed = 0

        for member in ordered_members:
            if self._is_cancelled():
                return False


            try:
                hwnd = member.FindCSWindow()
                if not hwnd or not win32gui.IsWindow(hwnd):
                    continue

                x = placed * target_width
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.MoveWindow(hwnd, x, y, target_width, target_height, True)
                win32gui.SetWindowText(hwnd, f"[FSN FREE] {member.login}")
                placed += 1
            except Exception:
                continue

        return placed > 0

    def Shuffle(self):
        if self._is_cancelled():
            return False

        valid_accounts = [acc for acc in self._accountManager.accounts if acc.isCSValid()]
        if len(valid_accounts) < 4:
            self._logManager.add_log("❌ Недостаточно активных CS аккаунтов для Shuffle")
            return False

        random.shuffle(valid_accounts)
        random_order_logins = [acc.login for acc in valid_accounts]
        mid = len(valid_accounts) // 2

        self.team1 = LobbyInstance(valid_accounts[0], valid_accounts[1:mid])
        self.team2 = LobbyInstance(valid_accounts[mid], valid_accounts[mid + 1:])
        self._last_window_order_logins = random_order_logins

        moved = self.MoveWindows(ordered_logins=random_order_logins)
        if moved:
            self._logManager.add_log(
                f"🔀 Shuffle выполнен"
            )
        return moved

    def _auto_create_lobbies(self):
        ordered_accounts = self._get_accounts_sorted_by_window_position()
        total = len(ordered_accounts)
        if total < 4:
            self._logManager.add_log("❌ Нужно минимум 4 валидных CS2 окна для сборки лобби")
            return False

        leader1 = ordered_accounts[0]
        bot1 = ordered_accounts[1]
        leader2 = ordered_accounts[2]
        bot2 = ordered_accounts[3]

        bots1 = [bot1]
        bots2 = [bot2]

        # Если аккаунтов больше 4 — дальше строго чередуем ботов между командами
        for index, account in enumerate(ordered_accounts[4:], start=4):
            if index % 2 == 0:
                bots1.append(account)
            else:
                bots2.append(account)

        self.team1 = LobbyInstance(leader1, bots1)
        self.team2 = LobbyInstance(leader2, bots2)
        self._last_window_order_logins = [acc.login for acc in ordered_accounts]

        return True

    def _get_accounts_sorted_by_window_position(self):
        valid_accounts = [acc for acc in self._accountManager.accounts if acc.isCSValid()]
        if not valid_accounts:
            return []

        ordered = []
        for order_index, account in enumerate(valid_accounts):
            rect = self._get_rect_for_account_window(account)
            if not rect:
                continue

            left = rect[0]
            ordered.append((left, order_index, account))

        # Строго: только слева направо. При равном X сохраняем исходный порядок аккаунтов.
        ordered.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in ordered]

    def _get_rect_for_account_window(self, account):
        pid = 0
        try:
            if account.CS2Process:
                pid = account.CS2Process.pid
        except Exception:
            pid = 0

        if not pid:
            return None

        best = None

        def enum_cb(hwnd, _):
            nonlocal best
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if win32gui.GetParent(hwnd) != 0:
                    return True

                _, hwnd_pid = win32process.GetWindowThreadProcessId(hwnd)
                if hwnd_pid != pid:
                    return True

                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return True

                rect = win32gui.GetWindowRect(hwnd)
                if not best:
                    best = rect
                    return True

                # Берем самое левое окно процесса; если X равен — самое верхнее.
                if rect[0] < best[0] or (rect[0] == best[0] and rect[1] < best[1]):
                    best = rect
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            return None

        return best

    # -----------------------------
    # Win32 helpers (shared)
    # -----------------------------
    @staticmethod
    def _is_cancelled():
        try:
            return keyboard.is_pressed("ctrl+q")
        except Exception:
            return False

    @staticmethod
    def _sleep_with_cancel(duration, step=0.05):
        end_time = time.time() + duration
        while time.time() < end_time:
            if LobbyManager._is_cancelled():
                return True
            time.sleep(min(step, end_time - time.time()))
        return False

    @staticmethod
    def _safe_set_foreground(hwnd):
        if not hwnd:
            return False

        attached = False
        fg_tid = 0
        hwnd_tid = 0

        try:
            if not win32gui.IsWindow(hwnd):
                return False

            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            except Exception:
                pass

            fg = 0
            try:
                fg = win32gui.GetForegroundWindow()
            except Exception:
                fg = 0

            try:
                fg_tid, _ = win32process.GetWindowThreadProcessId(fg)
            except Exception:
                fg_tid = 0

            try:
                hwnd_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                hwnd_tid = 0

            if fg_tid and hwnd_tid and fg_tid != hwnd_tid:
                try:
                    win32process.AttachThreadInput(fg_tid, hwnd_tid, True)
                    attached = True
                except Exception:
                    attached = False

            # Окно могло исчезнуть между вызовами — проверяем повторно.
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
        finally:
            if attached and fg_tid and hwnd_tid and fg_tid != hwnd_tid:
                try:
                    win32process.AttachThreadInput(fg_tid, hwnd_tid, False)
                except Exception:
                    pass

    def lift_all_cs2_windows(self):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

        cs2_pids = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = (proc.info.get('name') or "").lower()
                if name == "cs2.exe":
                    cs2_pids.append(proc.info['pid'])
            except Exception:
                continue

        if not cs2_pids:
            return 0

        processed = set()
        lifted = 0

        def enum_cb(hwnd, _):
            nonlocal lifted
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if win32gui.GetParent(hwnd) != 0:
                    return True

                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in cs2_pids or pid in processed:
                    return True

                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return True

                processed.add(pid)
                self._safe_set_foreground(hwnd)
                lifted += 1
                time.sleep(0.05)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum_cb, None)
        return lifted

    def press_esc_all_cs2_windows(self):
        """Нажимает ESC два раза в КАЖДОМ найденном окне cs2.exe перед запуском лобби-потока."""
        cs2_pids = [
            p.info['pid'] for p in psutil.process_iter(['pid', 'name'])
            if (p.info.get('name') or "").lower() == "cs2.exe"
        ]
        if not cs2_pids:
            return 0

        seen = set()
        count = 0

        def enum_cb(hwnd, _):
            nonlocal count
            if self._is_cancelled():
                return False
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in cs2_pids:
                    return True
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if hwnd in seen:
                    return True

                seen.add(hwnd)
                self._safe_set_foreground(hwnd)
                if self._sleep_with_cancel(0.1):
                    return False

                for _ in range(2):
                    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
                    if self._sleep_with_cancel(0.05):
                        return False
                    win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
                    if self._sleep_with_cancel(0.1):
                        return False

                count += 1
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum_cb, None)
        return count

    def _press_red_buttons_everywhere(self, final_click_pos):
        from PIL import ImageGrab

        def get_avg_color_2x2(x, y, rect):
            left = rect[0] + x
            top = rect[1] + y
            right = left + 2
            bottom = top + 2
            img = ImageGrab.grab(bbox=(left, top, right, bottom))
            r_sum = g_sum = b_sum = 0
            count = 0
            for px in range(img.size[0]):
                for py in range(img.size[1]):
                    r, g, b = img.getpixel((px, py))[:3]
                    r_sum += r
                    g_sum += g
                    b_sum += b
                    count += 1
            if count == 0:
                return (0, 0, 0)
            return (r_sum // count, g_sum // count, b_sum // count)

        def button_state(x, y, rect):
            r, g, b = get_avg_color_2x2(x, y, rect)
            if r > g + 20 and r > b + 20:
                return "red"
            if g > r + 20 and g > b + 20:
                return "green"
            return "red"

        def click_rel(x, y, rect, hwnd):
            if self._is_cancelled():
                return False
            self._safe_set_foreground(hwnd)
            abs_x = rect[0] + x
            abs_y = rect[1] + y
            win32api.SetCursorPos((abs_x, abs_y))
            if self._sleep_with_cancel(0.03):
                return False
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            if self._sleep_with_cancel(0.03):
                return False
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True

        members = []
        if self.team1:
            members.extend([self.team1.leader] + self.team1.bots)
        if self.team2:
            members.extend([self.team2.leader] + self.team2.bots)
        if not members:
            members = [acc for acc in self._accountManager.accounts if acc.isCSValid()]

        for acc in members:
            hwnd = acc.FindCSWindow()
            if not hwnd:
                continue
            try:
                rect = win32gui.GetWindowRect(hwnd)
            except Exception:
                continue

            state = button_state(final_click_pos[0], final_click_pos[1], rect)
            if state == "red":
                if not click_rel(final_click_pos[0], final_click_pos[1], rect, hwnd):
                    return False
                if self._sleep_with_cancel(0.1):
                    return False

        return True

    def _recover_after_match_timeout(self, final_click_pos):
        self._logManager.add_log("⏱ 600s timeout without accepted match. Running recovery flow.")

        if not self._press_red_buttons_everywhere(final_click_pos):
            return False

        esc_count = self.press_esc_all_cs2_windows()
        self._logManager.add_log(f"⌨️ Recovery: ESC x2 sent to {esc_count} CS2 windows")
        if self._is_cancelled():
            return False

        if not self.DisbandLobbies():
            self._logManager.add_log("⚠️ DisbandLobbies failed")
        if self._is_cancelled():
            return False

        if not self.Shuffle():
            self._logManager.add_log("⚠️ Shuffle failed")
            return False
        if self._is_cancelled():
            return False

        return True

    # -----------------------------
    # Main flow (по ТЗ)
    # -----------------------------
    def MakeLobbiesAndSearchGame(self):

        from PIL import ImageGrab
        from Modules.AutoAcceptModule import AutoAcceptModule

        AutoAcceptModule.reset_final_clicks_state()
        
        def click_rel(x, y, rect, hwnd):
            if self._is_cancelled():
                return False
            self._safe_set_foreground(hwnd)
            abs_x = rect[0] + x
            abs_y = rect[1] + y
            win32api.SetCursorPos((abs_x, abs_y))
            if self._sleep_with_cancel(0.03):
                return False
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            if self._sleep_with_cancel(0.03):
                return False
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True

        def get_team_info(team):
            if not team or not team.leader:
                return None
            hwnd = team.leader.FindCSWindow()
            if not hwnd:
                return None
            rect = win32gui.GetWindowRect(hwnd)
            return {"hwnd": hwnd, "rect": rect}

        def get_avg_color_2x2(x, y, rect):
            left = rect[0] + x
            top = rect[1] + y
            right = left + 2
            bottom = top + 2
            img = ImageGrab.grab(bbox=(left, top, right, bottom))
            r_sum = g_sum = b_sum = 0
            count = 0
            for px in range(img.size[0]):
                for py in range(img.size[1]):
                    r, g, b = img.getpixel((px, py))[:3]
                    r_sum += r
                    g_sum += g
                    b_sum += b
                    count += 1
            if count == 0:
                return (0, 0, 0)
            return (r_sum // count, g_sum // count, b_sum // count)

        def button_state(x, y, rect):
            r, g, b = get_avg_color_2x2(x, y, rect)
            if r > g + 20 and r > b + 20:
                return "red"
            if g > r + 20 and g > b + 20:
                return "green"
            return "red"

        def click_final(info, final_click):
            return click_rel(final_click[0], final_click[1], info["rect"], info["hwnd"])

        if self._is_cancelled():
            return False

        FINAL_CLICK = (289, 271)
        OPEN_SEQ = [(206, 8), (154, 23), (142, 33)]
        max_cycles = 3

        for cycle in range(1, max_cycles + 1):
            if AutoAcceptModule.final_clicks_disabled():
                self._logManager.add_log("✅ Match already detected. Stopping lobby/search cycle immediately.")
                return True

            self._logManager.add_log(f"🚀 Make lobbies & search cycle {cycle}/{max_cycles}")

            self.press_esc_all_cs2_windows()
            if self._is_cancelled():
                return False

            self._maps_scrolled_once = False

            if self.CollectLobby() is False:
                return False
            if AutoAcceptModule.final_clicks_disabled():
                self._logManager.add_log("✅ Match detected during lobby collect. Stopping search flow.")
                return True

            self.MoveWindows()
            if self._sleep_with_cancel(2):
                return False

            for team in (self.team1, self.team2):
                if self._is_cancelled():
                    return False
                if AutoAcceptModule.final_clicks_disabled():
                    self._logManager.add_log("✅ Match detected. Skipping remaining start-search actions.")
                    return True
                if not team or not team.leader:
                    continue

                hwnd = team.leader.FindCSWindow()
                if not hwnd:
                    continue

                rect = win32gui.GetWindowRect(hwnd)
                self._safe_set_foreground(hwnd)
                if self._sleep_with_cancel(0.3):
                    return False

                for x, y in OPEN_SEQ:
                    if not click_rel(x, y, rect, hwnd):
                        return False
                    if self._sleep_with_cancel(0.25):
                        return False

            if self._sleep_with_cancel(0.6):
                return False

            info1 = get_team_info(self.team1)
            info2 = get_team_info(self.team2)
            s1_start = button_state(FINAL_CLICK[0], FINAL_CLICK[1], info1["rect"]) if info1 else None
            s2_start = button_state(FINAL_CLICK[0], FINAL_CLICK[1], info2["rect"]) if info2 else None

            # Старт: жмём только зелёные кнопки.
            if s1_start == "green" and info1:
                if not click_final(info1, FINAL_CLICK):
                    return False
            if s2_start == "green" and info2:
                if not click_final(info2, FINAL_CLICK):
                    return False

            timed_out = True
            start_time = time.time()
            while time.time() - start_time < 600:
                if self._is_cancelled():
                    return False

                if AutoAcceptModule.final_clicks_disabled():
                    timed_out = False
                    break

                info1 = get_team_info(self.team1)
                info2 = get_team_info(self.team2)
                if not info1 and not info2:
                    timed_out = False
                    break

                s1 = button_state(FINAL_CLICK[0], FINAL_CLICK[1], info1["rect"]) if info1 else None
                s2 = button_state(FINAL_CLICK[0], FINAL_CLICK[1], info2["rect"]) if info2 else None

                if s1 == "red" and s2 == "green":
                    if info1 and not click_final(info1, FINAL_CLICK):
                        return False

                    # После клика по красной: если обе стали зелёные — нажимаем обе.
                    if self._sleep_with_cancel(0.15):
                        return False
                    info1_new = get_team_info(self.team1)
                    info2_new = get_team_info(self.team2)
                    if info1_new and info2_new:
                        s1_new = button_state(FINAL_CLICK[0], FINAL_CLICK[1], info1_new["rect"])
                        s2_new = button_state(FINAL_CLICK[0], FINAL_CLICK[1], info2_new["rect"])
                        if s1_new == "green" and s2_new == "green":
                            if not click_final(info1_new, FINAL_CLICK):
                                return False
                            if not click_final(info2_new, FINAL_CLICK):
                                return False

                elif s1 == "green" and s2 == "red":
                    if info2 and not click_final(info2, FINAL_CLICK):
                        return False

                    if self._sleep_with_cancel(0.15):
                        return False
                    info1_new = get_team_info(self.team1)
                    info2_new = get_team_info(self.team2)
                    if info1_new and info2_new:
                        s1_new = button_state(FINAL_CLICK[0], FINAL_CLICK[1], info1_new["rect"])
                        s2_new = button_state(FINAL_CLICK[0], FINAL_CLICK[1], info2_new["rect"])
                        if s1_new == "green" and s2_new == "green":
                            if not click_final(info1_new, FINAL_CLICK):
                                return False
                            if not click_final(info2_new, FINAL_CLICK):
                                return False

                elif s1 == "green" and s2 == "green":
                    if info1 and not click_final(info1, FINAL_CLICK):
                        return False
                    if info2 and not click_final(info2, FINAL_CLICK):
                        return False

                # Если обе красные — ничего не делаем по ТЗ.
                elif s1 == "red" and s2 == "red":
                    pass
                else:
                    pass

                if self._sleep_with_cancel(1.0):
                    return False

            if not timed_out or AutoAcceptModule.final_clicks_disabled():
                return True

         
            if not self._recover_after_match_timeout(FINAL_CLICK):
                return False

        self._logManager.add_log("❌ Match was not found after 3 recovery cycles")
        return False
