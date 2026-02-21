import sys
from pathlib import Path

import customtkinter

from Managers.AccountsManager import AccountManager
from Managers.LogManager import LogManager
from Managers.SettingsManager import SettingsManager
from .accounts_list_frame import AccountsListFrame
from .accounts_tab import AccountsControl
from .config_tab import ConfigTab
from .control_frame import ControlFrame
from .main_menu import MainMenu

customtkinter.set_appearance_mode("Dark")
customtkinter.set_default_color_theme("blue")

BG_MAIN = "#0b1020"
BG_PANEL = "#121a30"
BG_CARD = "#151d34"
BG_CARD_ALT = "#10182d"
BG_BORDER = "#242d48"
TXT_MAIN = "#e9edf7"
TXT_MUTED = "#8f9bb8"
ACCENT_BLUE = "#2f6dff"
ACCENT_BLUE_DARK = "#214ebe"
ACCENT_GREEN = "#1f9d55"
ACCENT_RED = "#c83a4a"
ACCENT_PURPLE = "#252b4f"
ACCENT_ORANGE = "#ff9500"


class App(customtkinter.CTk):
    def __init__(self, gsi_manager=None, startup_gpu_info=None):
        super().__init__()
        self.title("FSN Replic Panel | v.4.0")
        self.gsi_manager = gsi_manager
        self.window_position_file = Path("window_position.txt")

        self.geometry("1100x600")
        self.minsize(1100, 600)
        self.maxsize(1100, 600)
        self.configure(fg_color=BG_MAIN)
        self._load_window_position()

        if hasattr(sys, "_MEIPASS"):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent
        icon_path = Path(base_path) / "Icon1.ico"
        if icon_path.exists():
            self.iconbitmap(icon_path)

        self.account_manager = AccountManager()
        self.log_manager = LogManager()
        self.settings_manager = SettingsManager()
        self.account_row_items = []
        self.account_badges = {}

        self._create_hidden_legacy_controllers()
        self._build_layout()
        self._connect_gsi_to_ui()
        self._log_startup_gpu_info(startup_gpu_info)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.show_section("license")
        self._start_runtime_status_tracking()

    def _create_hidden_legacy_controllers(self):
        self.legacy_host = customtkinter.CTkFrame(self, fg_color="transparent")

        self.accounts_list = AccountsListFrame(self.legacy_host)
        self.accounts_control = AccountsControl(self.legacy_host, self.update_label, self.accounts_list)
        self.control_frame = ControlFrame(self.legacy_host)
        self.main_menu = MainMenu(self.legacy_host)
        self.config_tab = ConfigTab(self.legacy_host)

        for widget in [self.accounts_list, self.accounts_control, self.control_frame, self.main_menu, self.config_tab]:
            widget.grid_remove()

        self.control_frame.set_accounts_list_frame(self.accounts_list)
        self.accounts_list.set_control_frame(self.control_frame)

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = customtkinter.CTkFrame(
            self,
            width=200,
            corner_radius=12,
            fg_color=BG_PANEL,
            border_width=1,
            border_color=BG_BORDER,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(7, weight=1)

        customtkinter.CTkLabel(
            self.sidebar,
            text="FSN Replic Panel",
            font=customtkinter.CTkFont(size=20, weight="bold"),
            text_color=TXT_MAIN,
        ).grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")

        self.nav_buttons = {}
        nav_items = [
            ("functional", "Functionals"),
            ("config", "Configurations"),
            ("license", "License"),
            ("stats", "Accs Statistic"),
        ]
        for idx, (key, text) in enumerate(nav_items, start=1):
            btn = customtkinter.CTkButton(
                self.sidebar,
                text=text,
                width=150,
                height=34,
                corner_radius=9,
                font=customtkinter.CTkFont(size=12, weight="bold"),
                fg_color=BG_CARD_ALT,
                hover_color=BG_CARD,
                text_color=TXT_MAIN,
                border_width=1,
                border_color=ACCENT_RED,
                command=lambda k=key: self.show_section(k),
            )
            btn.grid(row=idx, column=0, padx=24, pady=4)
            self.nav_buttons[key] = btn

        logs_wrap = customtkinter.CTkFrame(
            self.sidebar,
            width=180,
            fg_color=BG_CARD_ALT,
            corner_radius=10,
            border_width=1,
            border_color=BG_BORDER,
        )
        logs_wrap.grid(row=7, column=0, padx=10, pady=(4, 8), sticky="nsew")
        logs_wrap.grid_propagate(False)
        logs_wrap.grid_columnconfigure(0, weight=1)
        logs_wrap.grid_rowconfigure(1, weight=1)

        customtkinter.CTkLabel(
            logs_wrap,
            text="• Logs",
            text_color=TXT_MAIN,
            font=customtkinter.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, padx=8, pady=(6, 2), sticky="w")

        self.logs_box = customtkinter.CTkTextbox(
            logs_wrap,
            width=250,
            fg_color="#0e1428",
            text_color="#98a7cf",
            border_width=0,
            corner_radius=8,
            wrap="word",
            font=customtkinter.CTkFont(size=11),
        )
        self.logs_box.grid(row=1, column=0, padx=6, pady=(0, 6), sticky="nsew")
        self.log_manager.textbox = self.logs_box

        self.content = customtkinter.CTkFrame(
            self,
            fg_color=BG_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=BG_BORDER,
        )
        self.content.grid(row=0, column=1, padx=(6, 10), pady=10, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.sections = {
            "functional": self._build_functional_section(self.content),
            "config": self._build_config_section(self.content),
            "license": self._build_license_section(self.content),
            "stats": self._build_stats_section(self.content),
        }

    def _build_functional_section(self, parent):
        frame = customtkinter.CTkFrame(parent, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        top = customtkinter.CTkFrame(frame, fg_color="transparent")
        top.grid(row=0, column=0, padx=10, pady=(8, 6), sticky="ew")
        title_frame = customtkinter.CTkFrame(top, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")
        customtkinter.CTkLabel(
            title_frame,
            text="Accounts",
            text_color=TXT_MAIN,
            font=customtkinter.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 10))

        self.accounts_info = customtkinter.CTkLabel(
            title_frame,
            text="0 accounts • 0 selected • 0 launched",
            text_color=TXT_MUTED,
            font=customtkinter.CTkFont(size=12),
        )
        self.accounts_info.grid(row=0, column=1)

        search_wrap = customtkinter.CTkFrame(title_frame, fg_color="transparent")
        search_wrap.grid(row=0, column=2, padx=(14, 0), sticky="w")
        self.search_var = customtkinter.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_account_filter())

        customtkinter.CTkEntry(
            search_wrap,
            textvariable=self.search_var,
            placeholder_text="Search",
            width=220,
            height=32,
            fg_color=BG_CARD,
            border_color=BG_BORDER,
            text_color=TXT_MAIN,
        ).grid(row=0, column=0)

        actions = customtkinter.CTkFrame(
            frame,
            fg_color=BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=BG_BORDER,
        )
        actions.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        for i in range(4):
            actions.grid_columnconfigure(i, weight=1)

        common_btn = {"height": 34, "font": customtkinter.CTkFont(size=12, weight="bold")}
        customtkinter.CTkButton(actions, text="Launch Selected", command=self._action_start_selected, fg_color=ACCENT_BLUE, hover_color=ACCENT_BLUE_DARK, **common_btn).grid(row=0, column=0, padx=6, pady=8, sticky="ew")
        customtkinter.CTkButton(actions, text="Select 4 accs", command=self._action_select_first_4, fg_color=ACCENT_PURPLE, hover_color="#313866", **common_btn).grid(row=0, column=1, padx=6, pady=8, sticky="ew")
        customtkinter.CTkButton(actions, text="Select all accs", command=self._action_select_all_toggle, fg_color=BG_CARD_ALT, hover_color=BG_BORDER, **common_btn).grid(row=0, column=2, padx=6, pady=8, sticky="ew")
        customtkinter.CTkButton(actions, text="Kill selected", command=self._action_kill_selected, fg_color=BG_CARD_ALT, hover_color=BG_BORDER, **common_btn).grid(row=0, column=3, padx=6, pady=8, sticky="ew")

        main = customtkinter.CTkFrame(frame, fg_color="transparent")
        main.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="nsew")
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1)
        main.grid_columnconfigure(2, weight=1)
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=0)

        accounts_block = customtkinter.CTkFrame(main, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BG_BORDER)
        accounts_block.grid(row=0, column=0, rowspan=2, padx=(0, 6), pady=0, sticky="nsew")
        accounts_block.grid_rowconfigure(1, weight=1)
        accounts_block.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(accounts_block, text="Accounts", font=customtkinter.CTkFont(size=20, weight="bold"), text_color=TXT_MAIN).grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.accounts_scroll = customtkinter.CTkScrollableFrame(accounts_block, fg_color=BG_CARD_ALT)
        self.accounts_scroll.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.accounts_scroll.grid_columnconfigure(0, weight=1)
        self._create_account_rows()

        self.srt_placeholder = customtkinter.CTkFrame(main, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BG_BORDER)
        self.srt_placeholder.grid(row=0, column=1, padx=6, pady=0, sticky="nsew")
        customtkinter.CTkLabel(self.srt_placeholder, text="SRT & SDR", text_color="#2ee66f", font=customtkinter.CTkFont(size=14, weight="bold")).pack(pady=(10, 6))
        customtkinter.CTkLabel(self.srt_placeholder, text="(empty integration block)", text_color=TXT_MUTED, font=customtkinter.CTkFont(size=11)).pack(pady=4)

        tools = customtkinter.CTkFrame(main, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BG_BORDER)
        tools.grid(row=0, column=2, padx=(6, 0), pady=0, sticky="nsew")
        tools.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(tools, text="Extra Tools", text_color=TXT_MAIN, font=customtkinter.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=8, pady=(8, 6), sticky="w")
        extra_buttons = [
            ("Move all CS windows", self._action_move_all_cs_windows, BG_CARD_ALT),
            ("Kill ALL CS & Steam", self._action_kill_all_cs_and_steam, ACCENT_PURPLE),
            ("Send trade", self._action_send_trade_selected, ACCENT_GREEN),
            ("Settings trade", self._action_open_looter_settings, ACCENT_RED),
            ("Marked farmer", self._action_marked_farmer, ACCENT_ORANGE),
            ("Launch BES", self._action_launch_bes, BG_CARD_ALT),
        ]
        for idx, (text, cmd, color) in enumerate(extra_buttons, start=1):
            customtkinter.CTkButton(tools, text=text, command=cmd, fg_color=color, hover_color=BG_BORDER, height=34, font=customtkinter.CTkFont(size=11, weight="bold")).grid(row=idx, column=0, padx=8, pady=4, sticky="ew")

        lobby = customtkinter.CTkFrame(main, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BG_BORDER)
        lobby.grid(row=1, column=1, columnspan=2, padx=(6, 0), pady=(0, 0), sticky="ew")
        customtkinter.CTkLabel(lobby, text="Lobby Management", text_color=TXT_MAIN, font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 4), sticky="w")
        for i in range(2):
            lobby.grid_columnconfigure(i, weight=1)

        lobby_buttons = [
            ("Make Lobbies", self._action_make_lobbies, BG_CARD_ALT),
            ("Make Lobbes & Search Game", self._action_make_lobbies_and_search, ACCENT_BLUE),
            ("Disband lobbies", self._action_disband_lobbies, BG_CARD_ALT),
            ("Get level", self._action_try_get_level, BG_CARD_ALT),
            ("Shuffle Lobbies", self._action_shuffle_lobbies, BG_CARD_ALT),
            ("Support Developer", self._action_support_developer, BG_CARD_ALT),
        ]
        for idx, (text, cmd, color) in enumerate(lobby_buttons):
            r, c = divmod(idx, 2)
            customtkinter.CTkButton(lobby, text=text, command=cmd, fg_color=color, hover_color=BG_BORDER, height=32, font=customtkinter.CTkFont(size=11, weight="bold")).grid(row=r + 1, column=c, padx=6, pady=4, sticky="ew")

        self._update_accounts_info()
        return frame

    def _create_account_rows(self):
        self.account_row_items.clear()
        levels_cache = getattr(self.accounts_list, "levels_cache", {})

        for idx, account in enumerate(self.account_manager.accounts):
            row = customtkinter.CTkFrame(self.accounts_scroll, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BG_BORDER)
            row.grid(row=idx, column=0, padx=4, pady=3, sticky="ew")
            row.grid_columnconfigure(1, weight=1)

            sw = customtkinter.CTkSwitch(
                row,
                text="",
                width=24,
                command=lambda a=account: self._toggle_account(a),
                fg_color="#2d3b60",
                progress_color=ACCENT_BLUE,
            )
            sw.grid(row=0, column=0, rowspan=2, padx=(6, 5), pady=6, sticky="w")
            if account in self.account_manager.selected_accounts:
                sw.select()

            lvl_data = levels_cache.get(account.login, {})
            level_text = lvl_data.get("level", "-")
            xp_text = lvl_data.get("xp", "-")

            level_label = customtkinter.CTkLabel(
                row,
                text=f"lvl: {level_text} | xp: {xp_text}",
                anchor="w",
                text_color=TXT_MUTED,
                font=customtkinter.CTkFont(size=11),
            )
            level_label.grid(row=1, column=1, padx=3, pady=(0, 5), sticky="w")

            is_running = account.isCSValid()
            badge_text = "Running" if is_running else "idle"
            badge_color = ACCENT_GREEN if is_running else ACCENT_BLUE
            badge = customtkinter.CTkLabel(
                row,
                text=badge_text,
                text_color="#dbe8ff",
                font=customtkinter.CTkFont(size=10),
                fg_color=badge_color,
                corner_radius=8,
                width=62,
                height=20,
            )
            badge.grid(row=0, column=2, rowspan=2, padx=6, pady=6)

            login_label = customtkinter.CTkLabel(
                row,
                text=account.login,
                anchor="w",
                text_color=TXT_MAIN,
                font=customtkinter.CTkFont(size=12, weight="bold"),
            )
            login_label.grid(row=0, column=1, padx=3, pady=(5, 0), sticky="w")

            account.setColorCallback(lambda color, a=account: self._handle_account_color_change(a, color))
            self.account_badges[account.login] = badge

            self.account_row_items.append({
                "row": row,
                "account": account,
                "login_lower": account.login.lower(),
                "switch": sw,
                "login_label": login_label,
                "level_label": level_label,
                "badge": badge,
            })

    def _refresh_level_labels(self):
        try:
            if hasattr(self.accounts_list, "_load_levels_from_json"):
                self.accounts_list.levels_cache = self.accounts_list._load_levels_from_json()
            levels_cache = getattr(self.accounts_list, "levels_cache", {})
            for item in self.account_row_items:
                login = item["account"].login
                lvl_data = levels_cache.get(login, {})
                level_text = lvl_data.get("level", "-")
                xp_text = lvl_data.get("xp", "-")
                item["level_label"].configure(text=f"lvl: {level_text} | xp: {xp_text}")
        except Exception:
            pass

    def _normalize_account_color(self, color):
        color_map = {"green": ACCENT_GREEN, "yellow": "#f5c542", "white": "#DCE4EE"}
        return color_map.get(str(color).lower(), color)

    def _handle_account_color_change(self, account, color):
        normalized = self._normalize_account_color(color)

        def apply_change():
            for item in self.account_row_items:
                if item["account"] is account:
                    item["login_label"].configure(text_color=normalized)
                    break
            self._refresh_account_badge(account)
            self._update_accounts_info()

        self.after(0, apply_change)

    def _refresh_account_badge(self, account):
        for item in self.account_row_items:
            if item["account"] is not account:
                continue
            is_running = account.isCSValid()
            item["badge"].configure(text="Running" if is_running else "idle", fg_color=ACCENT_GREEN if is_running else ACCENT_BLUE)
            return

    def _refresh_all_runtime_states(self):
        for item in self.account_row_items:
            account = item["account"]
            current_color = self._normalize_account_color(getattr(account, "_color", TXT_MAIN))
            item["login_label"].configure(text_color=current_color)
            self._refresh_account_badge(account)
        self._refresh_level_labels()
        self._sync_switches_with_selection()
        self._update_accounts_info()

    def _start_runtime_status_tracking(self):
        def poll():
            try:
                self._refresh_all_runtime_states()
            except Exception:
                pass
            finally:
                if self.winfo_exists():
                    self.after(1500, poll)
        self.after(500, poll)

    def _apply_account_filter(self):
        filter_text = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        render_idx = 0
        for item in self.account_row_items:
            show = not filter_text or filter_text in item["login_lower"]
            if show:
                item["row"].grid(row=render_idx, column=0, padx=4, pady=3, sticky="ew")
                render_idx += 1
            else:
                item["row"].grid_remove()

    def _toggle_account(self, account):
        if account in self.account_manager.selected_accounts:
            self.account_manager.selected_accounts.remove(account)
        else:
            self.account_manager.selected_accounts.append(account)
        self._sync_switches_with_selection()
        self._update_accounts_info()

    def _sync_switches_with_selection(self):
        selected = set(self.account_manager.selected_accounts)
        for item in self.account_row_items:
            if item["account"] in selected:
                item["switch"].select()
            else:
                item["switch"].deselect()

    def _update_accounts_info(self):
        total = len(self.account_manager.accounts)
        selected = len(self.account_manager.selected_accounts)
        launched = self.account_manager.count_launched_accounts()
        if hasattr(self, "accounts_info"):
            self.accounts_info.configure(text=f"{total} accounts • {selected} selected • {launched} launched")

    def _build_config_section(self, parent):
        frame = customtkinter.CTkFrame(parent, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(frame, text="Configurations", font=customtkinter.CTkFont(size=28, weight="bold"), text_color=TXT_MAIN).grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")
        return frame

    def _build_license_section(self, parent):
        frame = customtkinter.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BG_BORDER)
        frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(frame, text="License", font=customtkinter.CTkFont(size=30, weight="bold"), text_color=TXT_MAIN).grid(row=0, column=0, padx=16, pady=(20, 8), sticky="w")
        return frame

    def _build_stats_section(self, parent):
        frame = customtkinter.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BG_BORDER)
        frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(frame, text="Accs Stats", font=customtkinter.CTkFont(size=30, weight="bold"), text_color=TXT_MAIN).grid(row=0, column=0, padx=16, pady=(20, 8), sticky="w")
        return frame

    def _action_start_selected(self):
        self.accounts_control.start_selected()

    def _action_select_first_4(self):
        non_farmed = [acc for acc in self.account_manager.accounts if not self.accounts_list.is_farmed_account(acc)]
        target = non_farmed[:4]
        current = self.account_manager.selected_accounts
        if len(current) == len(target) and all(a in current for a in target):
            self.account_manager.selected_accounts.clear()
        else:
            self.account_manager.selected_accounts.clear()
            self.account_manager.selected_accounts.extend(target)
        self._sync_switches_with_selection()
        self._update_accounts_info()

    def _action_select_all_toggle(self):
        if len(self.account_manager.selected_accounts) == len(self.account_manager.accounts):
            self.account_manager.selected_accounts.clear()
        else:
            self.account_manager.selected_accounts.clear()
            self.account_manager.selected_accounts.extend(self.account_manager.accounts)
        self._sync_switches_with_selection()
        self._update_accounts_info()

    def _action_kill_selected(self):
        self.accounts_control.kill_selected()

    def _action_try_get_level(self):
        self.accounts_control.try_get_level()
        self.after(300, self._refresh_level_labels)

    def _action_kill_all_cs_and_steam(self):
        self.control_frame.kill_all_cs_and_steam()

    def _action_move_all_cs_windows(self):
        self.control_frame.move_all_cs_windows()

    def _action_launch_bes(self):
        self.control_frame.launch_bes()

    def _action_support_developer(self):
        self.control_frame.sendCasesMe()

    def _action_send_trade_selected(self):
        self.config_tab.send_trade_selected()

    def _action_open_looter_settings(self):
        self.config_tab.open_looter_settings()

    def _action_marked_farmer(self):
        self.accounts_control.mark_farmed()
        self._sync_switches_with_selection()
        self._refresh_all_runtime_states()

    def _action_make_lobbies_and_search(self):
        self.main_menu.make_lobbies_and_search_game()

    def _action_make_lobbies(self):
        self.main_menu.make_lobbies()

    def _action_shuffle_lobbies(self):
        self.main_menu.shuffle_lobbies()

    def _action_disband_lobbies(self):
        self.main_menu.disband_lobbies()

    def show_section(self, section_key):
        for key, frame in self.sections.items():
            if key == section_key:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

        for key, button in self.nav_buttons.items():
            button.configure(
                fg_color=BG_CARD if key == section_key else BG_CARD_ALT,
                border_color=ACCENT_GREEN if key == section_key else ACCENT_RED,
            )

    def _log_startup_gpu_info(self, startup_gpu_info):
        if not startup_gpu_info:
            return
        vendor_id, device_id, source = startup_gpu_info
        source_label = "detected" if source == "detected" else "settings fallback"
        try:
            self.log_manager.add_log(f"🎮 GPU IDs ({source_label}): VendorID={vendor_id}, DeviceID={device_id}")
        except Exception:
            pass

    def _connect_gsi_to_ui(self):
        try:
            if self.gsi_manager and self.accounts_list:
                self.gsi_manager.set_accounts_list_frame(self.accounts_list)
                print("✅ 🎮 GSIManager подключен к AccountsListFrame!")
            else:
                print("⚠️ GSIManager или AccountsListFrame недоступны")
        except Exception as exc:
            print(f"❌ Ошибка подключения GSIManager: {exc}")

    def _load_window_position(self):
        try:
            if not self.window_position_file.exists():
                return
            raw = self.window_position_file.read_text(encoding="utf-8").strip()
            if not raw:
                return
            parts = raw.split(",")
            if len(parts) != 2:
                return
            x = int(parts[0].strip())
            y = int(parts[1].strip())
            self.geometry(f"1100x600+{x}+{y}")
        except Exception:
            pass

    def _save_window_position(self):
        try:
            x = self.winfo_x()
            y = self.winfo_y()
            self.window_position_file.write_text(f"{x},{y}", encoding="utf-8")
        except Exception:
            pass

    def on_closing(self):
        self._save_window_position()
        self.destroy()

    def update_label(self):
        self._update_accounts_info()
        self._sync_switches_with_selection()
        self._apply_account_filter()


if __name__ == "__main__":
    app = App()
    app.mainloop()
