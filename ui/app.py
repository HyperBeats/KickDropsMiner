"""Main application UI for KickDropsMiner"""
import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from urllib.parse import urlparse
import urllib.request
from io import BytesIO
import customtkinter as ctk
from PIL import Image

from core import (
    Config,
    StreamWorker,
    CookieManager,
    make_chrome_driver,
    kick_is_live_by_api,
    fetch_drops_campaigns_and_progress,
    fetch_live_streamers_by_category,
    is_campaign_expired
)
from utils.helpers import (
    APP_DIR,
    domain_from_url,
    cookie_file_for_domain,
    debug_print,
    set_debug_config
)
from utils.translations import translate, TRANSLATIONS


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Kick Drop Miner")
        self.geometry("1000x750")
        self.minsize(900, 700)

        self.config_data = Config()
        # Set global debug config reference
        set_debug_config(self.config_data)
        self.workers = {}
        self._interactive_driver = None  # Chrome pour capture de cookies
        self.queue_running = False
        self.queue_current_idx = None

        # Helper traduction
        def _t(key: str, **kwargs):
            return translate(self.config_data.language, key).format(**kwargs)

        self.t = _t

        # Appearance / theme
        ctk.set_appearance_mode("Dark" if self.config_data.dark_mode else "Light")
        ctk.set_default_color_theme("dark-blue")

        # Layout principal: 2 colonnes (sidebar gauche, contenu droit)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        # Leave free space at the bottom to avoid cutting off controls
        # (uses a high empty row to serve as expandable space)
        self.sidebar.grid_rowconfigure(99, weight=1)

        self._build_sidebar()

        # Contenu principal
        self.content = ctk.CTkFrame(self, corner_radius=12)
        self.content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self._build_content()

        # Status bar
        self.status_var = tk.StringVar(value=self.t("status_ready"))
        self.status = ctk.CTkLabel(
            self, textvariable=self.status_var, anchor="w", height=26
        )
        self.status.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10)
        )

        self.refresh_list()
        
        # Start offline retry monitor
        self._start_offline_retry_monitor()
        
        # Auto-start queue if enabled
        if self.config_data.auto_start and self.config_data.items:
            # Delay slightly to let UI finish loading
            self.after(1000, self._auto_start_queue)
        
        # Properly close all browsers when closing the app
        try:
            self.protocol("WM_DELETE_WINDOW", self.on_close)
        except Exception:
            pass

    def _available_languages(self):
        codes = list(TRANSLATIONS.keys())
        ordered = []
        for preferred in ("fr", "en"):
            if preferred in codes:
                ordered.append(preferred)
        for code in sorted(c for c in codes if c not in ordered):
            ordered.append(code)
        return ordered

    def _language_label(self, lang_code):
        label_key = f"language_{lang_code}"
        label = translate(self.config_data.language, label_key)
        if label == label_key:
            label = translate(lang_code, label_key)
        if label == label_key:
            label = lang_code
        return label

    def _get_language_choices(self):
        codes = self._available_languages()
        if self.config_data.language not in codes and codes:
            self.config_data.language = codes[0]
            self.config_data.save()
        labels = {code: self._language_label(code) for code in codes}
        self.lang_display_to_code = {label: code for code, label in labels.items()}
        return [labels[code] for code in codes]

    # ----------- UI construction -----------
    def _build_sidebar(self):
        header = ctk.CTkFrame(self.sidebar, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, padx=10, pady=(10, 6), sticky="w")
        header.grid_columnconfigure(1, weight=1)

        # Logo (assets/logo.png) + title
        try:
            logo_path = os.path.join(APP_DIR, "assets", "logo.png")
            img = Image.open(logo_path)
            self._logo_img = ctk.CTkImage(
                light_image=img, dark_image=img, size=(24, 24)
            )
            logo_lbl = ctk.CTkLabel(header, image=self._logo_img, text="")
            logo_lbl.grid(row=0, column=0, padx=(4, 6), pady=4, sticky="w")
        except Exception:
            pass

        title = ctk.CTkLabel(
            header, text="Kick Drop Miner", font=ctk.CTkFont(size=18, weight="bold")
        )
        title.grid(row=0, column=1, padx=0, pady=4, sticky="w")

        # Main actions
        btn_add = ctk.CTkButton(
            self.sidebar, text=self.t("btn_add"), command=self.add_link, width=180
        )
        btn_add.grid(row=1, column=0, padx=14, pady=6, sticky="w")

        btn_remove = ctk.CTkButton(
            self.sidebar,
            text=self.t("btn_remove"),
            width=180,
        )
        # Bind to the underlying tkinter widget to detect Ctrl key
        # We'll handle both normal and Ctrl+click in the bound function
        btn_remove.bind("<Button-1>", self.on_remove_button_click)
        btn_remove.grid(row=2, column=0, padx=14, pady=6, sticky="w")

        btn_start_queue = ctk.CTkButton(
            self.sidebar,
            text=self.t("btn_start_queue"),
            command=self.start_all_in_order,
            width=180,
        )
        btn_start_queue.grid(row=3, column=0, padx=14, pady=(6, 2), sticky="w")

        btn_stop = ctk.CTkButton(
            self.sidebar,
            text=self.t("btn_stop_sel"),
            command=self.stop_selected,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            width=180,
        )
        btn_stop.grid(row=4, column=0, padx=14, pady=6, sticky="w")

        btn_signin = ctk.CTkButton(
            self.sidebar,
            text=self.t("btn_signin"),
            command=self.connect_to_kick,
            width=180,
        )
        btn_signin.grid(row=5, column=0, padx=14, pady=6, sticky="w")

        btn_drops = ctk.CTkButton(
            self.sidebar,
            text=self.t("btn_drops"),
            command=self.show_drops_window,
            fg_color="#9b59b6",
            hover_color="#8e44ad",
            width=180,
        )
        btn_drops.grid(row=6, column=0, padx=14, pady=6, sticky="w")

        # Settings button
        btn_settings = ctk.CTkButton(
            self.sidebar,
            text="⚙️ Settings",
            command=self.show_settings_window,
            width=180,
        )
        btn_settings.grid(row=7, column=0, padx=14, pady=(18, 6), sticky="w")

        # Initialize toggle variables (used in settings window)
        self.mute_var = tk.BooleanVar(value=bool(self.config_data.mute))
        self.hide_player_var = tk.BooleanVar(value=bool(self.config_data.hide_player))
        self.mini_player_var = tk.BooleanVar(value=bool(self.config_data.mini_player))
        self.force_160p_var = tk.BooleanVar(value=bool(self.config_data.force_160p))
        self.auto_start_var = tk.BooleanVar(value=bool(self.config_data.auto_start))
        self.theme_var = tk.StringVar(
            value=self.t("theme_dark")
            if self.config_data.dark_mode
            else self.t("theme_light")
        )
        language_choices = self._get_language_choices()
        current_label = self._language_label(self.config_data.language)
        if current_label not in language_choices and language_choices:
            current_label = language_choices[0]
        self.lang_var = tk.StringVar(value=current_label)

    def _build_content(self):
        header = ctk.CTkFrame(self.content, corner_radius=12)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text=self.t("title_streams"),
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=10, pady=10)

        # Tableau (ttk.Treeview) dans un CTkFrame
        table_frame = ctk.CTkFrame(self.content, corner_radius=12)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        # Automatic light/dark theme
        if ctk.get_appearance_mode() == "Dark":
            style.theme_use("clam")
            style.configure(
                "Treeview",
                background="#1f2125",
                fieldbackground="#1f2125",
                foreground="#e6e6e6",
                rowheight=26,
                bordercolor="#2b2d31",
            )
            style.configure(
                "Treeview.Heading",
                background="#2b2d31",
                foreground="#e6e6e6",
                font=("Segoe UI", 10, "bold"),
            )
            sel_bg = "#3b82f6"
            style.map(
                "Treeview",
                background=[("selected", sel_bg)],
                foreground=[("selected", "white")],
            )
        else:
            style.theme_use("clam")
            style.configure(
                "Treeview",
                background="#ffffff",
                fieldbackground="#ffffff",
                foreground="#111111",
                rowheight=26,
                bordercolor="#e9ecef",
            )
            style.configure(
                "Treeview.Heading",
                background="#eef2f7",
                foreground="#111111",
                font=("Segoe UI", 10, "bold"),
            )
            sel_bg = "#2d8cff"
            style.map(
                "Treeview",
                background=[("selected", sel_bg)],
                foreground=[("selected", "white")],
            )

        self.tree = ttk.Treeview(
            table_frame,
            columns=("url", "minutes", "elapsed"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("url", text="URL")
        self.tree.heading("minutes", text=self.t("col_minutes"))
        self.tree.heading("elapsed", text=self.t("col_elapsed"))
        self.tree.column("url", width=600, anchor="w")
        self.tree.column("minutes", width=130, anchor="center")
        self.tree.column("elapsed", width=140, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")
        
        # Bind double-click to edit minutes
        self.tree.bind("<Double-Button-1>", self.on_tree_double_click)

        # Colored rows via tags
        try:
            self.tree.tag_configure(
                "odd",
                background="#0f0f11"
                if ctk.get_appearance_mode() == "Dark"
                else "#f7f7f7",
            )
            self.tree.tag_configure(
                "even",
                background="#1f2125"
                if ctk.get_appearance_mode() == "Dark"
                else "#ffffff",
            )
            self.tree.tag_configure(
                "redo",
                background="#3a3a00"
                if ctk.get_appearance_mode() == "Dark"
                else "#fff3cd",
            )
            self.tree.tag_configure(
                "paused",
                background="#3a2e2a"
                if ctk.get_appearance_mode() == "Dark"
                else "#fde2e2",
            )
            self.tree.tag_configure(
                "finished",
                background="#22352a"
                if ctk.get_appearance_mode() == "Dark"
                else "#e6f7e8",
            )
        except Exception:
            pass

    # ----------- Theme -----------
    def show_settings_window(self):
        """Open settings window with all toggles and dropdowns"""
        # Create settings window
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("450x650")
        settings_window.resizable(False, False)
        settings_window.transient(self)
        settings_window.grab_set()  # Make it modal
        
        # Center the window
        settings_window.update_idletasks()
        x = (settings_window.winfo_screenwidth() // 2) - (450 // 2)
        y = (settings_window.winfo_screenheight() // 2) - (700 // 2)
        settings_window.geometry(f"450x700+{x}+{y}")
        
        # Consistent theme
        ctk.set_appearance_mode("Dark" if self.config_data.dark_mode else "Light")
        
        # Main frame with padding
        main_frame = ctk.CTkFrame(settings_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(
            main_frame,
            text="⚙️ Settings",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Scrollable frame for settings
        scrollable_frame = ctk.CTkScrollableFrame(main_frame)
        scrollable_frame.pack(fill="both", expand=True)
        
        # Player Settings Section
        player_section = ctk.CTkFrame(scrollable_frame)
        player_section.pack(fill="x", pady=(0, 15))
        
        player_title = ctk.CTkLabel(
            player_section,
            text="Player Settings",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        player_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Mute toggle
        sw_mute = ctk.CTkSwitch(
            player_section,
            text=self.t("switch_mute"),
            command=self.on_toggle_mute,
            variable=self.mute_var,
        )
        sw_mute.pack(anchor="w", padx=15, pady=5)
        
        # Hide player toggle
        sw_hide = ctk.CTkSwitch(
            player_section,
            text=self.t("switch_hide"),
            command=self.on_toggle_hide,
            variable=self.hide_player_var,
        )
        sw_hide.pack(anchor="w", padx=15, pady=5)
        
        # Mini player toggle
        sw_mini = ctk.CTkSwitch(
            player_section,
            text=self.t("switch_mini"),
            command=self.on_toggle_mini,
            variable=self.mini_player_var,
        )
        sw_mini.pack(anchor="w", padx=15, pady=5)
        
        # Force 160p toggle
        sw_force_160p = ctk.CTkSwitch(
            player_section,
            text=self.t("switch_force_160p"),
            command=self.on_toggle_force_160p,
            variable=self.force_160p_var,
        )
        sw_force_160p.pack(anchor="w", padx=15, pady=(5, 15))
        
        # Queue Settings Section
        queue_section = ctk.CTkFrame(scrollable_frame)
        queue_section.pack(fill="x", pady=(0, 15))
        
        queue_title = ctk.CTkLabel(
            queue_section,
            text="Queue Settings",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        queue_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Auto-start toggle
        sw_auto_start = ctk.CTkSwitch(
            queue_section,
            text="Auto-start queue",
            command=self.on_toggle_auto_start,
            variable=self.auto_start_var,
        )
        sw_auto_start.pack(anchor="w", padx=15, pady=(5, 15))
        
        # Appearance Settings Section
        appearance_section = ctk.CTkFrame(scrollable_frame)
        appearance_section.pack(fill="x", pady=(0, 15))
        
        appearance_title = ctk.CTkLabel(
            appearance_section,
            text="Appearance",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        appearance_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Theme dropdown
        theme_label = ctk.CTkLabel(appearance_section, text=self.t("label_theme"))
        theme_label.pack(anchor="w", padx=15, pady=(5, 5))
        theme_menu = ctk.CTkOptionMenu(
            appearance_section,
            values=[self.t("theme_dark"), self.t("theme_light")],
            command=self.change_theme,
            variable=self.theme_var,
            width=350,
        )
        theme_menu.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Language dropdown
        language_choices = self._get_language_choices()
        lang_label = ctk.CTkLabel(appearance_section, text=self.t("label_language"))
        lang_label.pack(anchor="w", padx=15, pady=(5, 5))
        lang_menu = ctk.CTkOptionMenu(
            appearance_section,
            values=language_choices,
            command=self.change_language,
            variable=self.lang_var,
            width=350,
        )
        lang_menu.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Browser Settings Section
        browser_section = ctk.CTkFrame(scrollable_frame)
        browser_section.pack(fill="x", pady=(0, 15))
        
        browser_title = ctk.CTkLabel(
            browser_section,
            text="Browser Settings",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        browser_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        # ChromeDriver button
        def choose_chromedriver_wrapper():
            self.choose_chromedriver()
            settings_window.lift()
            settings_window.focus_force()
            # Refresh the window to update labels
            settings_window.destroy()
            self.show_settings_window()
        
        btn_chromedriver = ctk.CTkButton(
            browser_section,
            text=self.t("btn_chromedriver"),
            command=choose_chromedriver_wrapper,
            width=350,
        )
        btn_chromedriver.pack(anchor="w", padx=15, pady=5)
        
        # Show current chromedriver path if set
        chromedriver_label = ctk.CTkLabel(
            browser_section,
            text=f"Current: {os.path.basename(self.config_data.chromedriver_path) if self.config_data.chromedriver_path else 'Not set'}",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50")
        )
        chromedriver_label.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Chrome Extension button
        def choose_extension_wrapper():
            self.choose_extension()
            settings_window.lift()
            settings_window.focus_force()
            # Refresh the window to update labels
            settings_window.destroy()
            self.show_settings_window()
        
        btn_extension = ctk.CTkButton(
            browser_section,
            text=self.t("btn_extension"),
            command=choose_extension_wrapper,
            width=350,
        )
        btn_extension.pack(anchor="w", padx=15, pady=5)
        
        # Show current extension path if set
        extension_label = ctk.CTkLabel(
            browser_section,
            text=f"Current: {os.path.basename(self.config_data.extension_path) if self.config_data.extension_path else 'Not set'}",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50")
        )
        extension_label.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Close button
        close_btn = ctk.CTkButton(
            settings_window,
            text="Close",
            command=settings_window.destroy,
            width=200,
        )
        close_btn.pack(pady=15)

    def change_theme(self, choice):
        # Accepts FR/EN
        dark = choice in (self.t("theme_dark"), "Sombre", "Dark")
        self.config_data.dark_mode = dark
        self.config_data.save()
        ctk.set_appearance_mode("Dark" if dark else "Light")
        # Rebuild content (to recalculate Treeview styles)
        for w in self.content.winfo_children():
            w.destroy()
        self._build_content()
        self.refresh_list()

    # ----------- Language -----------
    def change_language(self, choice):
        mapping = getattr(self, "lang_display_to_code", {})
        new_lang = None

        if isinstance(choice, str):
            new_lang = mapping.get(choice)
            if not new_lang:
                # Fallback: case-insensitive match
                for label, code in mapping.items():
                    if label.lower() == choice.lower():
                        new_lang = code
                        break

        if not new_lang:
            return

        if new_lang == self.config_data.language:
            return  # No change needed

        self.config_data.language = new_lang
        self.config_data.save()

        # Rebuild sidebar & content to refresh text
        try:
            for w in self.sidebar.winfo_children():
                w.destroy()
            self._build_sidebar()
        except Exception:
            pass

        try:
            for w in self.content.winfo_children():
                w.destroy()
            self._build_content()
        except Exception:
            pass

        # Update status bar if it's at the initial text
        try:
            ready_variants = [translate(lang, "status_ready") for lang in TRANSLATIONS]
            if self.status_var.get() in ready_variants:
                self.status_var.set(self.t("status_ready"))
        except Exception:
            pass

    # ----------- Actions -----------
    def on_tree_double_click(self, event):
        """Handle double-click on tree to edit minutes"""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        
        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        
        if not row_id:
            return
        
        # Check if clicked on minutes column (column #2)
        if column == "#2":
            idx = int(row_id)
            if idx >= len(self.config_data.items):
                return
            
            # Check if this stream is currently running
            if idx in self.workers:
                messagebox.showwarning(
                    self.t("warning"),
                    self.t("cannot_edit_active_stream")
                )
                return
                
            current_minutes = self.config_data.items[idx]["minutes"]
            
            new_minutes = simpledialog.askinteger(
                self.t("prompt_minutes_title"),
                self.t("prompt_minutes_msg"),
                initialvalue=current_minutes,
                minvalue=0
            )
            
            if new_minutes is not None:
                self.config_data.items[idx]["minutes"] = new_minutes
                self.config_data.save()
                self.refresh_list()
                self.status_var.set(f"Updated target to {new_minutes} minutes")
    
    def refresh_list(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for i, item in enumerate(self.config_data.items):
            elapsed = self.workers[i].elapsed_seconds if i in self.workers else 0
            tags = ["odd" if i % 2 else "even"]
            if item.get("finished"):
                tags.append("finished")
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(item["url"], item["minutes"], f"{elapsed}s"),
                tags=tuple(tags),
            )

    def add_link(self):
        url = simpledialog.askstring(
            self.t("prompt_live_url_title"), self.t("prompt_live_url_msg")
        )
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        minutes = simpledialog.askinteger(
            self.t("prompt_minutes_title"), self.t("prompt_minutes_msg"), minvalue=0
        )
        self.config_data.add(url, minutes or 0)
        self.refresh_list()
        self.status_var.set(self.t("status_link_added"))
        # Auto-start if enabled and queue not running
        if self.config_data.auto_start and not self.queue_running:
            self.after(500, self._auto_start_queue)

    def on_remove_button_click(self, event):
        """Handle remove button click - check for Ctrl key"""
        # Check if Ctrl key is pressed (state & 0x4 is Control modifier)
        ctrl_pressed = (event.state & 0x4) != 0
        
        if ctrl_pressed:
            # Ctrl is pressed - show clear all dialog
            self.after(0, self.clear_all_items)
        else:
            # Normal remove action
            self.after(0, self.remove_selected)
    
    def clear_all_items(self):
        """Clear all items from the list after confirmation"""
        if not self.config_data.items:
            return  # Nothing to clear
        
        # Show confirmation dialog
        result = messagebox.askyesno(
            "Clear All Items",
            f"Are you sure you want to remove all {len(self.config_data.items)} item(s) from the list?",
            icon="warning"
        )
        
        if result:
            # Stop all running workers
            for idx, worker in list(self.workers.items()):
                try:
                    worker.stop()
                except Exception:
                    pass
            self.workers.clear()
            
            # Clear all items
            self.config_data.items = []
            self.config_data.save()
            
            # Refresh UI
            self.refresh_list()
            self.status_var.set("All items cleared")
            debug_print(f"DEBUG: Cleared all items from list")
    
    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.config_data.remove(idx)
        if idx in self.workers:
            self.workers[idx].stop()
            del self.workers[idx]
        # Re-index workers (because indices have shifted)
        self.workers = {
            new_i: self.workers[old_i]
            for new_i, old_i in enumerate(sorted(self.workers.keys()))
            if old_i < len(self.config_data.items)
        }
        self.refresh_list()
        self.status_var.set(self.t("status_link_removed"))

    def start_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self._start_index(idx)

    def _start_index(self, idx):
        """Start a stream, ensuring only one runs at a time (Kick limitation)"""
        # Stop any currently running stream (Kick only allows 1 at a time)
        if len(self.workers) > 0:
            # Find and stop the currently running worker
            for running_idx, worker in list(self.workers.items()):
                worker.stop()
                del self.workers[running_idx]
                # Mark as not finished so it can be retried
                if running_idx < len(self.config_data.items):
                    self.config_data.items[running_idx]["finished"] = False
            time.sleep(2)  # Brief pause to let browser close
        
        item = self.config_data.items[idx]
        
        # Try alternative channels from same campaign if current is offline
        if not kick_is_live_by_api(item["url"]):
            campaign_channels = item.get("campaign_channels", [])
            if campaign_channels:
                tried_channels = item.get("tried_channels", [])
                current_url = item["url"]
                
                # Add current URL to tried list if not already there
                if current_url not in tried_channels:
                    tried_channels.append(current_url)
                
                # Get all channel URLs
                all_channel_urls = []
                for ch in campaign_channels:
                    ch_url = ch.get("url") if isinstance(ch, dict) else ch
                    if ch_url:
                        all_channel_urls.append(ch_url)
                if current_url not in all_channel_urls:
                    all_channel_urls.append(current_url)
                
                # Reset if all channels tried
                if len(tried_channels) >= len(all_channel_urls):
                    tried_channels.clear()
                    debug_print(f"DEBUG: Reset tried_channels in _start_index for campaign {item.get('campaign_id')}")
                
                # Try to find a live alternative channel that hasn't been tried
                switched_in_start = False
                for alt_channel in campaign_channels:
                    alt_url = alt_channel.get("url") if isinstance(alt_channel, dict) else alt_channel
                    if alt_url and alt_url != item["url"] and alt_url not in tried_channels:
                        if kick_is_live_by_api(alt_url):
                            # Switch to this alternative channel
                            self.config_data.items[idx]["url"] = alt_url
                            tried_channels.append(alt_url)
                            item["tried_channels"] = tried_channels
                            self.config_data.save()
                            self.refresh_list()
                            item = self.config_data.items[idx]  # Update item reference
                            debug_print(f"DEBUG: Switched to alternative in _start_index: {alt_url} (tried: {len(tried_channels)}/{len(all_channel_urls)})")
                            self.status_var.set(f"Switched to {alt_url.split('/')[-1]} - waiting for page to load...")
                            switched_in_start = True
                            # Wait 8 seconds to allow browser to fully load before checking if stream is live
                            # Use after() to avoid blocking UI thread
                            self.after(8000, lambda i=idx: self._start_index_after_switch(i))
                            return
                
                # If we switched, we already scheduled a callback, so return early
                if switched_in_start:
                    return
        
        # Check again after potential channel switch
        if not kick_is_live_by_api(item["url"]):
            try:
                values = list(self.tree.item(str(idx), "values"))
                values[2] = self.t("retry")
                self.tree.item(str(idx), values=values, tags=("redo",))
            except Exception:
                pass
            self.status_var.set(self.t("offline_wait_retry", url=item["url"]))
            return

        domain = domain_from_url(item["url"])
        if not domain:
            messagebox.showerror(self.t("error"), self.t("invalid_url"))
            return

        cookie_path = cookie_file_for_domain(domain)
        if not os.path.exists(cookie_path):
            # Auto-import cookies silently (no popup for automation)
            try:
                if not CookieManager.import_from_browser(domain):
                    # Only show popup if auto-import fails and we're not in auto mode
                    if not self.config_data.auto_start:
                        if messagebox.askyesno(
                            self.t("cookies_missing_title"), self.t("cookies_missing_msg")
                        ):
                            self.obtain_cookies_interactively(item["url"], domain)
                    else:
                        # In auto mode, skip items without cookies
                        self.status_var.set(f"Skipping {item['url']} - no cookies")
                        return
            except Exception:
                if not self.config_data.auto_start:
                    if messagebox.askyesno(
                        self.t("cookies_missing_title"), self.t("cookies_missing_msg")
                    ):
                        self.obtain_cookies_interactively(item["url"], domain)
                else:
                    return

        stop_event = threading.Event()
        
        # Setup cumulative time callback for global drops
        is_global_drop = item.get("is_global_drop", False)
        cumulative_time_callback = None
        if is_global_drop:
            campaign_id = item.get("campaign_id")
            def get_cumulative_time():
                """Get current cumulative time for this campaign"""
                if not campaign_id:
                    return 0
                total = 0
                for other_item in self.config_data.items:
                    if other_item.get("campaign_id") == campaign_id:
                        total += other_item.get("cumulative_time", 0)
                return total
            cumulative_time_callback = get_cumulative_time
        
        worker = StreamWorker(
            item["url"],
            item["minutes"],
            on_update=lambda s, live: self.on_worker_update(idx, s, live),
            on_finish=lambda e, c: self.on_worker_finish(idx, e, c),
            stop_event=stop_event,
            driver_path=self.config_data.chromedriver_path,
            extension_path=self.config_data.extension_path,
            hide_player=bool(self.hide_player_var.get()),
            mute=bool(self.mute_var.get()),
            mini_player=bool(self.mini_player_var.get()),
            force_160p=bool(self.config_data.force_160p),
            required_category_id=item.get("required_category_id"),
            cumulative_time_callback=cumulative_time_callback,
        )
        self.workers[idx] = worker
        worker.start()
        self.tree.selection_set(str(idx))
        self.status_var.set(self.t("status_playing", url=item["url"]))

    def _start_index_after_switch(self, idx):
        """Continue _start_index after a delay when switching channels"""
        if idx < 0 or idx >= len(self.config_data.items):
            return
        
        item = self.config_data.items[idx]
        
        # Check again after potential channel switch (after delay)
        if not kick_is_live_by_api(item["url"]):
            try:
                values = list(self.tree.item(str(idx), "values"))
                values[2] = self.t("retry")
                self.tree.item(str(idx), values=values, tags=("redo",))
            except Exception:
                pass
            self.status_var.set(self.t("offline_wait_retry", url=item["url"]))
            return

        domain = domain_from_url(item["url"])
        if not domain:
            messagebox.showerror(self.t("error"), self.t("invalid_url"))
            return

        cookie_path = cookie_file_for_domain(domain)
        if not os.path.exists(cookie_path):
            # Auto-import cookies silently (no popup for automation)
            try:
                if not CookieManager.import_from_browser(domain):
                    # Only show popup if auto-import fails and we're not in auto mode
                    if not self.config_data.auto_start:
                        if messagebox.askyesno(
                            self.t("cookies_missing_title"), self.t("cookies_missing_msg")
                        ):
                            self.obtain_cookies_interactively(item["url"], domain)
                    else:
                        # In auto mode, skip items without cookies
                        self.status_var.set(f"Skipping {item['url']} - no cookies")
                        return
            except Exception:
                if not self.config_data.auto_start:
                    if messagebox.askyesno(
                        self.t("cookies_missing_title"), self.t("cookies_missing_msg")
                    ):
                        self.obtain_cookies_interactively(item["url"], domain)
                else:
                    return

        stop_event = threading.Event()
        
        # Setup cumulative time callback for global drops
        is_global_drop = item.get("is_global_drop", False)
        cumulative_time_callback = None
        if is_global_drop:
            campaign_id = item.get("campaign_id")
            def get_cumulative_time():
                """Get current cumulative time for this campaign"""
                if not campaign_id:
                    return 0
                total = 0
                for other_item in self.config_data.items:
                    if other_item.get("campaign_id") == campaign_id:
                        total += other_item.get("cumulative_time", 0)
                return total
            cumulative_time_callback = get_cumulative_time
        
        worker = StreamWorker(
            item["url"],
            item["minutes"],
            on_update=lambda s, live: self.on_worker_update(idx, s, live),
            on_finish=lambda e, c: self.on_worker_finish(idx, e, c),
            stop_event=stop_event,
            driver_path=self.config_data.chromedriver_path,
            extension_path=self.config_data.extension_path,
            hide_player=bool(self.hide_player_var.get()),
            mute=bool(self.mute_var.get()),
            mini_player=bool(self.mini_player_var.get()),
            force_160p=bool(self.config_data.force_160p),
            required_category_id=item.get("required_category_id"),
            cumulative_time_callback=cumulative_time_callback,
        )
        self.workers[idx] = worker
        worker.start()
        self.tree.selection_set(str(idx))
        self.status_var.set(self.t("status_playing", url=item["url"]))

    def start_all_in_order(self):
        self.queue_running = True
        self.queue_current_idx = None
        self._run_queue_from(0)

    def _run_queue_from(self, start_idx: int):
        """Run queue ensuring only one stream at a time"""
        # Ensure no other streams are running
        if len(self.workers) > 0:
            # Wait for current stream to finish
            return
        
        for i in range(start_idx, len(self.config_data.items)):
            item = self.config_data.items[i]
            if item.get("finished"):
                continue
            self.tree.selection_set(str(i))
            before = set(self.workers.keys())
            self._start_index(i)
            after = set(self.workers.keys())
            if i in after:
                self.queue_current_idx = i
                self.status_var.set(self.t("queue_running_status", url=item["url"]))
                return  # Only one stream at a time
        self.queue_running = False
        self.queue_current_idx = None
        self.status_var.set(self.t("queue_finished_status"))

    def stop_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx in self.workers:
            self.workers[idx].stop()
            del self.workers[idx]
            self.status_var.set(self.t("status_stopped"))
            # Update the display
            if str(idx) in self.tree.get_children():
                values = list(self.tree.item(str(idx), "values"))
                values[2] = f"{values[2]} ({self.t('tag_stop')})"
                self.tree.item(str(idx), values=values)

    def obtain_cookies_interactively(self, url, domain):
        try:
            drv = make_chrome_driver(
                headless=False,
                driver_path=self.config_data.chromedriver_path,
                extension_path=self.config_data.extension_path,
            )
            self._interactive_driver = drv
        except Exception as e:
            messagebox.showerror(self.t("error"), self.t("chrome_start_fail", e=e))
            return
        drv.get(url)
        messagebox.showinfo(self.t("action_required"), self.t("sign_in_and_click_ok"))
        try:
            CookieManager.save_cookies(drv, domain)
            messagebox.showinfo(
                self.t("ok"), self.t("cookies_saved_for", domain=domain)
            )
        except Exception as e:
            messagebox.showerror(self.t("error"), self.t("cannot_save_cookies", e=e))
        finally:
            try:
                drv.quit()
            except Exception:
                pass
            finally:
                self._interactive_driver = None

    def on_close(self):
        # Stop the queue and close all browser windows
        try:
            self.queue_running = False
        except Exception:
            pass

        # Close Chrome cookie import window if open
        try:
            if self._interactive_driver:
                try:
                    self._interactive_driver.quit()
                except Exception:
                    pass
                self._interactive_driver = None
        except Exception:
            pass

        # Stop and close all Selenium drivers from workers
        for idx, w in list(self.workers.items()):
            try:
                w.stop()
            except Exception:
                pass
            try:
                if getattr(w, "driver", None):
                    try:
                        w.driver.quit()
                    except Exception:
                        pass
            except Exception:
                pass

        # Wait briefly for threads to stop
        for idx, w in list(self.workers.items()):
            try:
                w.join(timeout=2.5)
            except Exception:
                pass

        # Close the application
        try:
            self.destroy()
        except Exception:
            os._exit(0)

    def connect_to_kick(self):
        sel = self.tree.selection()
        if sel:
            idx = int(sel[0])
            url = self.config_data.items[idx]["url"]
            domain = domain_from_url(url)
        else:
            url = "https://kick.com"
            domain = "kick.com"
        # Attempt automatic cookie import from browser
        try:
            if CookieManager.import_from_browser(domain):
                messagebox.showinfo(
                    self.t("ok"), self.t("cookies_saved_for", domain=domain)
                )
                return
        except Exception:
            pass
        # Otherwise, fall back to existing interactive method
        if messagebox.askyesno(
            self.t("connect_title"), self.t("open_url_to_get_cookies", url=url)
        ):
            self.obtain_cookies_interactively(url, domain)

    def choose_chromedriver(self):
        path = filedialog.askopenfilename(
            title=self.t("pick_chromedriver_title"),
            filetypes=[(self.t("executables_filter"), "*.exe;*")],
        )
        if not path:
            return
        self.config_data.chromedriver_path = path
        self.config_data.save()
        messagebox.showinfo(self.t("ok"), self.t("chromedriver_set", path=path))

    def choose_extension(self):
        path = filedialog.askopenfilename(
            title=self.t("pick_extension_title"),
            filetypes=[("CRX", "*.crx"), (self.t("all_files_filter"), "*.*")],
        )
        if not path:
            return
        self.config_data.extension_path = path
        self.config_data.save()
        messagebox.showinfo(self.t("ok"), self.t("extension_set", path=path))

    def show_drops_window(self):
        """Opens a window to display and select drop campaigns"""
        drops_window = ctk.CTkToplevel(self)
        drops_window.title(self.t("drops_title"))
        drops_window.geometry("1000x700")
        drops_window.minsize(900, 600)
        
        # Keep window on top
        drops_window.attributes('-topmost', True)
        drops_window.lift()
        drops_window.focus_force()

        # Consistent theme
        ctk.set_appearance_mode("Dark" if self.config_data.dark_mode else "Light")

        # Main frame with background color
        main_frame = ctk.CTkFrame(drops_window, fg_color=("gray92", "gray14"))
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # Header with refresh button
        header_frame = ctk.CTkFrame(main_frame, fg_color=("gray86", "gray17"), corner_radius=0, height=60)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)

        status_label = ctk.CTkLabel(
            header_frame, text=self.t("drops_loading"), 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        status_label.grid(row=0, column=0, sticky="w", padx=20, pady=15)

        scrollable_frame = ctk.CTkScrollableFrame(
            main_frame, 
            label_text="",
            fg_color=("gray92", "gray14")
        )
        scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        scrollable_frame.grid_columnconfigure(0, weight=1)

        refresh_btn = ctk.CTkButton(
            header_frame,
            text=self.t("btn_refresh_drops"),
            width=130,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            command=lambda: self._refresh_drops(scrollable_frame, status_label),
        )
        refresh_btn.grid(row=0, column=1, padx=20, pady=15)

        # Refresh function for buttons
        def refresh_callback():
            threading.Thread(target=lambda: self._refresh_drops(scrollable_frame, status_label), daemon=True).start()
        
        # Store reference for buttons
        self._current_drops_refresh = refresh_callback
        
        # Load initial campaigns in a separate thread
        def load_and_focus():
            self._refresh_drops(scrollable_frame, status_label)
            # Bring window to front after loading
            try:
                drops_window.lift()
                drops_window.focus_force()
            except:
                pass
        
        threading.Thread(target=load_and_focus, daemon=True).start()

    def _refresh_drops(self, scrollable_frame, status_label):
        """Refreshes the list of drop campaigns with integrated progress"""

        # Clean the frame
        def clear_frame():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            status_label.configure(text=self.t("drops_loading"))

        self.after(0, clear_frame)

        def display_campaigns():
            driver = None
            try:
                # Fetch both campaigns and progress using a single Chrome instance
                result = fetch_drops_campaigns_and_progress()
                campaigns = result.get("campaigns", [])
                progress_data = result.get("progress", [])
                progress_data = [p for p in progress_data if isinstance(p, dict)]
                driver = result.get("driver")
                
                if not campaigns:
                    status_label.configure(text=self.t("drops_error"))
                    no_data_label = ctk.CTkLabel(
                        scrollable_frame,
                        text=self.t("drops_error"),
                        font=ctk.CTkFont(size=12),
                        text_color="gray",
                    )
                    no_data_label.grid(row=0, column=0, pady=20)
                    return

                # Create a progress lookup by campaign ID
                progress_by_id = {}
                for prog in progress_data:
                    if not isinstance(prog, dict):
                        continue  # Skip unexpected progress entries
                    campaign_id = prog.get("id")
                    if campaign_id:
                        progress_by_id[campaign_id] = prog
                
                # Merge progress data into campaigns
                for campaign in campaigns:
                    campaign_id = campaign.get("id")
                    if campaign_id in progress_by_id:
                        # Campaign has progress - merge progress info
                        prog = progress_by_id[campaign_id]
                        campaign["progress_data"] = prog
                        campaign["progress_status"] = prog.get("status", "not_started")
                        campaign["progress_units"] = prog.get("progress_units", 0)
                        
                        # Merge category from progress data if not already in campaign
                        if "category" in prog and "category" not in campaign:
                            campaign["category"] = prog["category"]
                        elif "category" in prog:
                            # Update category if progress has more complete data
                            campaign["category"] = prog["category"]
                        
                        # Merge reward progress
                        reward_progress = {}
                        for reward in prog.get("rewards", []):
                            reward_id = reward.get("id")
                            if reward_id:
                                reward_progress[reward_id] = {
                                    "progress": reward.get("progress", 0.0),
                                    "claimed": reward.get("claimed", False),
                                    "required_units": reward.get("required_units", 0),
                                }
                        
                        # Attach progress to each reward in campaign
                        for reward in campaign.get("rewards", []):
                            reward_id = reward.get("id")
                            if reward_id in reward_progress:
                                reward["progress"] = reward_progress[reward_id]["progress"]
                                reward["claimed"] = reward_progress[reward_id]["claimed"]
                                reward["progress_required_units"] = reward_progress[reward_id]["required_units"]
                    else:
                        # Campaign has no progress - not started
                        campaign["progress_data"] = None
                        campaign["progress_status"] = "not_started"
                        campaign["progress_units"] = 0
                        for reward in campaign.get("rewards", []):
                            reward["progress"] = 0.0
                            reward["claimed"] = False

                # Filter campaigns into active and expired
                active_campaigns = []
                expired_campaigns = []
                
                for campaign in campaigns:
                    if is_campaign_expired(campaign):
                        expired_campaigns.append(campaign)
                    else:
                        active_campaigns.append(campaign)
                
                # Group active campaigns by game and sort by progress status
                games = {}
                for campaign in active_campaigns:
                    # Double-check: skip if expired (safety check)
                    if is_campaign_expired(campaign):
                        continue
                    game_name = campaign["game"]
                    if game_name not in games:
                        games[game_name] = {
                            "image": campaign.get("game_image", ""),
                            "campaigns": [],
                        }
                    games[game_name]["campaigns"].append(campaign)
                
                # Sort campaigns within each game by progress status
                # Priority: in progress > not started > claimed/completed
                def sort_key(campaign):
                    status = campaign.get("progress_status", "not_started")
                    if status == "in progress":
                        return 0
                    elif status == "not_started":
                        return 1
                    elif status == "claimed":
                        return 2
                    else:
                        return 3
                
                for game_name, game_data in games.items():
                    game_data["campaigns"].sort(key=sort_key)
                
                # Sort games by priority: games with in-progress campaigns first
                def game_priority(game_data):
                    campaigns = game_data["campaigns"]
                    # Check if any campaign is in progress
                    has_in_progress = any(c.get("progress_status") == "in progress" for c in campaigns)
                    if has_in_progress:
                        return 0
                    # Check if any campaign is not started
                    has_not_started = any(c.get("progress_status") == "not_started" for c in campaigns)
                    if has_not_started:
                        return 1
                    return 2
                
                # Convert to list, sort, then back to dict (or use OrderedDict)
                games_list = sorted(games.items(), key=lambda x: game_priority(x[1]))
                games = dict(games_list)

                status_text = self.t("drops_loaded", count=len(active_campaigns))
                if expired_campaigns:
                    status_text += f" ({len(expired_campaigns)} expired)"
                status_label.configure(text=status_text)

                # Add toggle for showing expired campaigns
                if not hasattr(scrollable_frame, "_show_expired_var"):
                    scrollable_frame._show_expired_var = tk.BooleanVar(value=False)
                
                show_expired = scrollable_frame._show_expired_var.get()
                
                # Display each game with its campaigns
                row_idx = 0
                for game_name, game_data in games.items():
                    # Separate campaigns into active and completed
                    game_active_campaigns = []
                    game_completed_campaigns = []
                    
                    for campaign in game_data["campaigns"]:
                        status = campaign.get("progress_status", "not_started")
                        if status == "claimed":
                            game_completed_campaigns.append(campaign)
                        else:
                            game_active_campaigns.append(campaign)
                    # Frame for game (collapsible) - improved style
                    game_frame = ctk.CTkFrame(
                        scrollable_frame, 
                        corner_radius=12,
                        border_width=2,
                        border_color=("#3b82f6", "#2563eb")
                    )
                    game_frame.grid(row=row_idx, column=0, sticky="ew", padx=0, pady=10)
                    game_frame.grid_columnconfigure(0, weight=1)

                    # Variable for toggle collapse
                    is_expanded = tk.BooleanVar(value=True)

                    # Game header (clickable to collapse/expand) - larger and colored
                    game_header = ctk.CTkFrame(
                        game_frame, 
                        fg_color=("#e0f2fe", "#1e3a5f"),
                        cursor="hand2",
                        corner_radius=10
                    )
                    game_header.grid(row=0, column=0, sticky="ew", padx=3, pady=3)
                    # Don't expand any column - let content determine width
                    game_header.grid_columnconfigure(3, weight=1)  # Expand the empty space column

                    # Expand/collapse icon - more visible
                    collapse_icon = ctk.CTkLabel(
                        game_header, 
                        text="▼", 
                        font=ctk.CTkFont(size=14, weight="bold"),
                        text_color=("#3b82f6", "#60a5fa")
                    )
                    collapse_icon.grid(row=0, column=0, padx=(15, 10), pady=12)

                    # Game image (if available) - larger
                    col_offset = 1
                    if game_data["image"]:
                        try:
                            # Download and display game image
                            with urllib.request.urlopen(
                                game_data["image"], timeout=3
                            ) as response:
                                image_data = response.read()
                            game_img = Image.open(BytesIO(image_data))
                            game_img = game_img.resize(
                                (48, 48), Image.Resampling.LANCZOS
                            )
                            game_photo = ctk.CTkImage(
                                light_image=game_img, dark_image=game_img, size=(48, 48)
                            )

                            img_label = ctk.CTkLabel(
                                game_header, image=game_photo, text="", cursor="hand2"
                            )
                            img_label.image = game_photo
                            img_label.grid(row=0, column=1, padx=(0, 12))
                            col_offset = 2
                        except Exception as e:
                            print(f"Could not load game image: {e}")

                    # Game name - larger and colored
                    game_label = ctk.CTkLabel(
                        game_header,
                        text=game_name,
                        font=ctk.CTkFont(size=20, weight="bold"),
                        text_color=("#1e40af", "#93c5fd")
                    )
                    game_label.grid(row=0, column=col_offset, sticky="w", padx=(0, 0))
                    
                    # Spacer column to push badge to the right
                    # (column 3 has weight=1)

                    # Number of campaigns - styled badge, aligned right
                    count_label = ctk.CTkLabel(
                        game_header,
                        text=f"{len(game_data['campaigns'])} campaign{'s' if len(game_data['campaigns']) > 1 else ''}",
                        font=ctk.CTkFont(size=11, weight="bold"),
                        fg_color=("#bfdbfe", "#1e40af"),
                        corner_radius=12,
                        padx=10,
                        pady=4
                    )
                    count_label.grid(row=0, column=4, sticky="e", padx=(15, 15))

                    # Campaigns frame (can be hidden)
                    campaigns_container = ctk.CTkFrame(
                        game_frame, fg_color="transparent"
                    )
                    campaigns_container.grid(row=1, column=0, sticky="ew")
                    campaigns_container.grid_columnconfigure(0, weight=1)

                    # Fonction toggle
                    def toggle_collapse(
                        event=None,
                        icon=collapse_icon,
                        container=campaigns_container,
                        var=is_expanded,
                    ):
                        if var.get():
                            container.grid_remove()
                            icon.configure(text="▶")
                            var.set(False)
                        else:
                            container.grid()
                            icon.configure(text="▼")
                            var.set(True)

                    # Make header clickable
                    game_header.bind("<Button-1>", toggle_collapse)
                    game_label.bind("<Button-1>", toggle_collapse)
                    collapse_icon.bind("<Button-1>", toggle_collapse)
                    count_label.bind("<Button-1>", toggle_collapse)
                    # Bind img_label if it exists
                    for widget in game_header.winfo_children():
                        if isinstance(widget, ctk.CTkLabel) and hasattr(
                            widget, "image"
                        ):
                            widget.bind("<Button-1>", toggle_collapse)

                    # Display active campaigns first
                    camp_idx = 0
                    for campaign in active_campaigns:
                        self._create_campaign_display(campaigns_container, campaign, camp_idx, scrollable_frame, game_data, status_label)
                        camp_idx += 1
                    
                    # Display completed campaigns in a collapsible section
                    if game_completed_campaigns:
                        # Add separator if there are active campaigns
                        if active_campaigns:
                            separator = ctk.CTkFrame(campaigns_container, fg_color="transparent", height=2)
                            separator.grid(row=camp_idx, column=0, sticky="ew", padx=8, pady=6)
                            camp_idx += 1
                        
                        # Collapsible header for completed campaigns
                        completed_header_frame = ctk.CTkFrame(
                            campaigns_container,
                            fg_color=("gray85", "#2d3748"),
                            corner_radius=8,
                            cursor="hand2"
                        )
                        completed_header_frame.grid(row=camp_idx, column=0, sticky="ew", padx=8, pady=6)
                        completed_header_frame.grid_columnconfigure(1, weight=1)
                        
                        completed_expanded = tk.BooleanVar(value=False)  # Collapsed by default
                        
                        completed_collapse_icon = ctk.CTkLabel(
                            completed_header_frame,
                            text="▶",
                            font=ctk.CTkFont(size=12, weight="bold"),
                            text_color=("gray60", "gray40")
                        )
                        completed_collapse_icon.grid(row=0, column=0, padx=(12, 8), pady=8)
                        
                        completed_header_label = ctk.CTkLabel(
                            completed_header_frame,
                            text=f"{self.t('drops_completed_campaigns')} ({len(game_completed_campaigns)})",
                            font=ctk.CTkFont(size=12, weight="bold"),
                            text_color=("gray60", "gray40")
                        )
                        completed_header_label.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=8)
                        
                        # Container for completed campaigns
                        completed_container = ctk.CTkFrame(
                            campaigns_container,
                            fg_color="transparent"
                        )
                        completed_container.grid(row=camp_idx + 1, column=0, sticky="ew")
                        completed_container.grid_columnconfigure(0, weight=1)
                        completed_container.grid_remove()  # Hidden by default
                        
                        def toggle_completed(event=None):
                            if completed_expanded.get():
                                completed_container.grid_remove()
                                completed_collapse_icon.configure(text="▶")
                                completed_expanded.set(False)
                            else:
                                completed_container.grid()
                                completed_collapse_icon.configure(text="▼")
                                completed_expanded.set(True)
                        
                        completed_header_frame.bind("<Button-1>", toggle_completed)
                        completed_collapse_icon.bind("<Button-1>", toggle_completed)
                        completed_header_label.bind("<Button-1>", toggle_completed)
                        
                        # Display completed campaigns
                        for comp_idx, campaign in enumerate(game_completed_campaigns):
                            self._create_campaign_display(completed_container, campaign, comp_idx, scrollable_frame, game_data, status_label)
                        
                        camp_idx += 2  # Skip header and container rows
                    
                    row_idx += 1
                
                # Display expired campaigns section if toggle is on
                if expired_campaigns and hasattr(scrollable_frame, "_show_expired_var") and scrollable_frame._show_expired_var.get():
                        expired_separator = ctk.CTkFrame(scrollable_frame, fg_color=("gray70", "gray30"), height=2)
                        expired_separator.grid(row=row_idx, column=0, sticky="ew", padx=0, pady=15)
                        row_idx += 1
                        
                        expired_label = ctk.CTkLabel(
                            scrollable_frame,
                            text=f"⏰ Expired Campaigns ({len(expired_campaigns)})",
                            font=ctk.CTkFont(size=14, weight="bold"),
                            text_color=("#6b7280", "#9ca3af"),
                        )
                        expired_label.grid(row=row_idx, column=0, sticky="w", padx=15, pady=10)
                        row_idx += 1
                        
                        for exp_idx, campaign in enumerate(expired_campaigns):
                            self._create_campaign_display(scrollable_frame, campaign, exp_idx, scrollable_frame, {"image": ""}, status_label)
                            row_idx += 1
                
                # Force update
                scrollable_frame.update_idletasks()
            except Exception as e:
                status_label.configure(text=f"Error: {str(e)}")
                import traceback
                traceback.print_exc()
            finally:
                # Close driver after displaying all campaigns
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass

        # Call on UI thread in background to avoid blocking
        threading.Thread(target=display_campaigns, daemon=True).start()

    def _auto_find_streamers_for_game(self, campaign, category_id, scrollable_frame, status_label):
        """Auto-find and add live streamers for a global drop campaign"""
        def find_and_add():
            game_name = campaign.get('game', 'game')
            debug_print(f"DEBUG: Starting search for live streamers")
            debug_print(f"DEBUG: Campaign: {campaign.get('name', 'unknown')}")
            debug_print(f"DEBUG: Game: {game_name}")
            debug_print(f"DEBUG: Category ID: {category_id}")
            
            status_label.configure(text=f"🔍 Searching for live streamers of {game_name}...")
            
            # Use existing driver from drops window if available, or create new one
            driver = None
            try:
                debug_print("DEBUG: Attempting to get driver from drops fetch...")
                # Try to get driver from current drops fetch
                result = fetch_drops_campaigns_and_progress()
                driver = result.get("driver")
                if driver:
                    debug_print("DEBUG: Reusing existing driver")
                else:
                    debug_print("DEBUG: No existing driver, will create new one")
            except Exception as e:
                debug_print(f"DEBUG: Error getting driver: {e}")
                pass
            
            debug_print(f"DEBUG: Calling fetch_live_streamers_by_category with category_id={category_id}")
            streamers = fetch_live_streamers_by_category(category_id, limit=24, driver=driver)
            debug_print(f"DEBUG: Found {len(streamers)} streamers")
            
            if not streamers:
                status_label.configure(text=f"❌ No live streamers found for {game_name}")
                debug_print(f"DEBUG: No streamers found, closing driver if needed")
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                return
            
            debug_print(f"DEBUG: Processing {len(streamers)} streamers to add to queue")
            status_label.configure(text=f"📝 Adding {len(streamers)} streamer(s) to queue...")
            
            # Calculate maximum required time from rewards (cumulative drops)
            rewards = campaign.get("rewards", [])
            max_required_minutes = 0
            for reward in rewards:
                required_units = reward.get("required_units", 0)
                if required_units > max_required_minutes:
                    max_required_minutes = required_units
            
            # If no rewards found, default to 120
            if max_required_minutes == 0:
                max_required_minutes = 120
            
            debug_print(f"DEBUG: Campaign has {len(rewards)} rewards, max required: {max_required_minutes} minutes")
            
            # Add all found streamers to queue
            count = 0
            skipped = 0
            campaign_id = campaign.get("id")
            all_streamers = [{"url": s["url"], "username": s["username"]} for s in streamers]
            
            for streamer in streamers:
                try:
                    url = streamer["url"]
                    username = streamer.get("username", "unknown")
                    debug_print(f"DEBUG: Processing streamer: {username} ({url})")
                    
                    if self._is_channel_in_list(url):
                        debug_print(f"DEBUG: Streamer {username} already in list, skipping")
                        skipped += 1
                        continue
                    
                    # Store all streamers as alternatives for each other
                    # Use max_required_minutes for cumulative drops
                    debug_print(f"DEBUG: Adding {username} to queue with target: {max_required_minutes} minutes")
                    self.config_data.add(
                        url, 
                        max_required_minutes, 
                        campaign_id, 
                        all_streamers,
                        required_category_id=category_id,
                        is_global_drop=True
                    )
                    count += 1
                except Exception as e:
                    debug_print(f"DEBUG: Error adding streamer {streamer.get('username', 'unknown')}: {e}")
                    import traceback
                    traceback.print_exc()
            
            debug_print(f"DEBUG: Added {count} streamers, skipped {skipped} (already in list)")
            self.refresh_list()
            status_label.configure(text=f"✅ Added {count} live streamer(s) for {game_name}" + (f" ({skipped} already in list)" if skipped > 0 else ""))
            
            # Auto-start if enabled
            if self.config_data.auto_start and not self.queue_running:
                debug_print("DEBUG: Auto-start enabled, starting queue")
                self.after(500, self._auto_start_queue)
            else:
                debug_print("DEBUG: Auto-start disabled or queue already running")
            
            if driver:
                try:
                    debug_print("DEBUG: Closing driver")
                    driver.quit()
                except Exception as e:
                    debug_print(f"DEBUG: Error closing driver: {e}")
        
        threading.Thread(target=find_and_add, daemon=True).start()

    def _create_campaign_display(self, parent, campaign, camp_idx, scrollable_frame, game_data, status_label=None):
        """Helper function to create a campaign display frame"""
        try:
            campaign_frame = ctk.CTkFrame(
                parent,
                corner_radius=10,
                fg_color=("white", "#1f2937"),
                border_width=1,
                border_color=("#d1d5db", "#374151")
            )
            campaign_frame.grid(
                row=camp_idx, column=0, sticky="ew", padx=8, pady=6
            )
            campaign_frame.grid_columnconfigure(0, weight=1)

            # Campaign header - improved style
            header = ctk.CTkFrame(campaign_frame, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 8))
            header.grid_columnconfigure(1, weight=1)

            campaign_name_label = ctk.CTkLabel(
                header,
                text=campaign["name"],
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w"
            )
            campaign_name_label.grid(
                row=0, column=0, columnspan=2, sticky="w"
            )

            # Status badge - show progress status if available
            progress_status = campaign.get("progress_status", "not_started")
            if progress_status == "not_started":
                status_text = campaign["status"].upper()
                status_color = ("#10b981", "#059669") if campaign["status"] == "active" else ("#6b7280", "#4b5563")
            elif progress_status == "in progress":
                status_text = "IN PROGRESS"
                status_color = ("#f59e0b", "#d97706")
            elif progress_status == "claimed":
                status_text = "CLAIMED"
                status_color = ("#10b981", "#059669")
            else:
                status_text = campaign["status"].upper()
                status_color = ("#6b7280", "#4b5563")
            
            status_badge = ctk.CTkLabel(
                header,
                text=status_text,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=status_color,
                text_color="white",
                corner_radius=6,
                padx=10,
                pady=4,
            )
            status_badge.grid(row=0, column=2, sticky="e")

            # Display rewards (drops) with images
            rewards = campaign.get("rewards", [])
            if rewards:
                rewards_frame = ctk.CTkFrame(
                    campaign_frame, 
                    fg_color=("gray90", "#111827"),
                    corner_radius=8
                )
                rewards_frame.grid(
                    row=1, column=0, sticky="ew", padx=15, pady=(0, 10)
                )
                rewards_frame.grid_columnconfigure(1, weight=1)

                rewards_label = ctk.CTkLabel(
                    rewards_frame,
                    text="🎁 Rewards:",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=("#7c3aed", "#a78bfa")
                )
                rewards_label.grid(row=0, column=0, sticky="w", padx=(12, 10), pady=10)

                # Horizontal frame for drop images
                images_frame = ctk.CTkFrame(
                    rewards_frame, fg_color="transparent"
                )
                images_frame.grid(row=0, column=1, sticky="w", pady=10, padx=(0, 12))

                for rew_idx, reward in enumerate(
                    rewards[:6]
                ):  # Max 6 rewards shown
                    try:
                        # Build complete image URL
                        reward_img_url = reward.get("image_url", "")
                        if reward_img_url and not reward_img_url.startswith(
                            "http"
                        ):
                            reward_img_url = (
                                f"https://ext.cdn.kick.com/{reward_img_url}"
                            )

                        if reward_img_url:
                            # CDN images - use simple urllib request with headers
                            try:
                                req = urllib.request.Request(
                                    reward_img_url,
                                    headers={
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                        "Referer": "https://kick.com/"
                                    }
                                )
                                with urllib.request.urlopen(req, timeout=5) as response:
                                    img_data = response.read()

                                rew_img = Image.open(BytesIO(img_data))
                                rew_img = rew_img.resize(
                                    (50, 50), Image.Resampling.LANCZOS
                                )
                                rew_photo = ctk.CTkImage(
                                    light_image=rew_img,
                                    dark_image=rew_img,
                                    size=(50, 50),
                                )

                                reward_name = reward.get(
                                    "name", "Unknown"
                                )
                                required_mins = reward.get(
                                    "required_units", 0
                                )
                                
                                # Get progress info if available
                                progress = reward.get("progress", 0.0)
                                claimed = reward.get("claimed", False)
                                progress_units = campaign.get("progress_units", 0)
                                
                                # Build tooltip with progress info
                                if progress > 0 or claimed:
                                    progress_percent = int(progress * 100)
                                    if claimed:
                                        tooltip_text = f"{reward_name}\n⏱️ {required_mins} minutes\n✓ CLAIMED ({progress_percent}%)"
                                    else:
                                        tooltip_text = f"{reward_name}\n⏱️ {required_mins} minutes\n📊 {progress_percent}% ({progress_units}/{required_mins})"
                                else:
                                    tooltip_text = f"{reward_name}\n⏱️ {required_mins} minutes\n⏸️ Not started"

                                # Frame with border for each reward - change border color if claimed
                                border_color = ("#10b981", "#059669") if claimed else ("#f59e0b", "#d97706") if progress > 0 else ("#d1d5db", "#374151")
                                border_width = 3 if claimed or progress > 0 else 2
                                
                                rew_container = ctk.CTkFrame(
                                    images_frame,
                                    fg_color=("white", "#0f172a"),
                                    border_width=border_width,
                                    border_color=border_color,
                                    corner_radius=8,
                                    width=60,
                                    height=60
                                )
                                rew_container.grid(row=0, column=rew_idx, padx=4)
                                rew_container.grid_propagate(False)
                                
                                rew_label = ctk.CTkLabel(
                                    rew_container,
                                    image=rew_photo,
                                    text="",
                                )
                                rew_label.image = rew_photo
                                rew_label.place(relx=0.5, rely=0.5, anchor="center")
                                
                                # Add claimed checkmark overlay if claimed
                                if claimed:
                                    claimed_overlay = ctk.CTkLabel(
                                        rew_container,
                                        text="✓",
                                        font=ctk.CTkFont(size=16, weight="bold"),
                                        text_color="#10b981",
                                        fg_color="transparent"
                                    )
                                    claimed_overlay.place(relx=0.85, rely=0.15, anchor="center")

                                # Add tooltip (drop name on hover) - on container for better functionality
                                self._create_tooltip(rew_container, tooltip_text)
                                self._create_tooltip(rew_label, tooltip_text)
                            except Exception:
                                pass  # Silently skip images that fail to load
                    except Exception:
                        pass

            # Participating channels - improved style
            channels_frame = ctk.CTkFrame(
                campaign_frame, fg_color="transparent"
            )
            channels_frame.grid(
                row=2, column=0, sticky="ew", padx=15, pady=(0, 12)
            )
            channels_frame.grid_columnconfigure(0, weight=1)
            
            # Store widget references (defined before if/else to avoid scope error)
            channel_buttons = []

            if not campaign["channels"]:
                # Global drop - show option to auto-find streamers
                global_drop_frame = ctk.CTkFrame(channels_frame, fg_color="transparent")
                global_drop_frame.grid(row=0, column=0, sticky="ew", pady=5)
                global_drop_frame.grid_columnconfigure(0, weight=1)
                
                no_channels_label = ctk.CTkLabel(
                    global_drop_frame,
                    text=self.t("drops_no_channels"),
                    text_color=("#6b7280", "#9ca3af"),
                    font=ctk.CTkFont(size=11, slant="italic"),
                )
                no_channels_label.grid(row=0, column=0, sticky="w")
                
                # Button to auto-find streamers for this game
                # Get category_id from campaign (from progress API or campaigns API)
                category = campaign.get("category", {})
                category_id = category.get("id") if isinstance(category, dict) else None
                
                # Also check in progress_data if category not found
                if not category_id:
                    progress_data = campaign.get("progress_data", {})
                    if isinstance(progress_data, dict):
                        progress_category = progress_data.get("category", {})
                        if isinstance(progress_category, dict):
                            category_id = progress_category.get("id")
                
                # Try alternative structure (if category is not nested)
                if not category_id:
                    category_id = campaign.get("category_id")
                
                # Always show button, but disable if no category_id
                def find_streamers(c=campaign, cid=category_id, sl=status_label):
                    if not cid:
                        if sl:
                            sl.configure(text="Error: No category_id found for this campaign")
                        debug_print(f"DEBUG: Campaign structure: {list(c.keys())}")
                        debug_print(f"DEBUG: Category: {c.get('category')}")
                        debug_print(f"DEBUG: Progress data: {c.get('progress_data', {}).get('category') if isinstance(c.get('progress_data'), dict) else 'N/A'}")
                        return
                    if sl:
                        self._auto_find_streamers_for_game(c, cid, scrollable_frame, sl)
                    else:
                        debug_print("DEBUG: No status_label available")
                
                find_btn = ctk.CTkButton(
                    global_drop_frame,
                    text="🔍 Find Live Streamers",
                    width=180,
                    height=30,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=("#10b981", "#059669") if category_id else ("#6b7280", "#4b5563"),
                    hover_color=("#059669", "#047857") if category_id else ("#4b5563", "#374151"),
                    command=find_streamers,
                    state="normal" if category_id else "disabled",
                )
                find_btn.grid(row=0, column=1, padx=(10, 0), sticky="e")
                
                if not category_id:
                    debug_print(f"DEBUG: No category_id found for campaign {campaign.get('name', 'unknown')}")
                    debug_print(f"DEBUG: Campaign keys: {list(campaign.keys())}")
                    debug_print(f"DEBUG: Category value: {campaign.get('category')}")
            else:
                # List of channels with buttons - improved design
                for ch_idx, channel in enumerate(campaign["channels"][:5]):
                    channel_url = channel["url"]
                    is_added = self._is_channel_in_list(channel_url)
                    
                    channel_row = ctk.CTkFrame(
                        channels_frame, 
                        fg_color=("gray95", "#1f2937"),
                        corner_radius=6
                    )
                    channel_row.grid(
                        row=ch_idx, column=0, sticky="ew", pady=3
                    )
                    channel_row.grid_columnconfigure(0, weight=1)

                    # Icon according to state, but text always normal
                    icon = "✓" if is_added else "📺"
                    ch_label = ctk.CTkLabel(
                        channel_row,
                        text=f"{icon} {channel['username']}",
                        font=ctk.CTkFont(size=12),
                        anchor="w"
                    )
                    ch_label.grid(row=0, column=0, sticky="w", padx=(12, 10), pady=8)

                    # Add or Remove button depending on state
                    action_btn = ctk.CTkButton(
                        channel_row,
                        text="✗ Remove" if is_added else "+ Add",
                        width=90,
                        height=28,
                        font=ctk.CTkFont(size=11, weight="bold"),
                        fg_color=("#ef4444", "#dc2626") if is_added else ("#3b82f6", "#2563eb"),
                        hover_color=("#dc2626", "#b91c1c") if is_added else ("#2563eb", "#1d4ed8"),
                        corner_radius=6,
                    )
                    action_btn.grid(row=0, column=1, sticky="e", padx=8, pady=4)
                    
                    # Store reference to this button
                    channel_buttons.append((channel_url, action_btn, ch_label, channel['username']))
                    
                    # Function to toggle button state
                    def toggle_channel(url=channel_url, btn=action_btn, label=ch_label, username=channel['username'], camp=campaign):
                        if self._is_channel_in_list(url):
                            # Remove
                            self._remove_drop_channel(url)
                            # Update button and label (icon only)
                            btn.configure(
                                text="+ Add",
                                fg_color=("#3b82f6", "#2563eb"),
                                hover_color=("#2563eb", "#1d4ed8")
                            )
                            label.configure(text=f"📺 {username}")
                        else:
                            # Add
                            self._add_drop_channel(url, 120, camp)
                            # Update button and label (icon only)
                            btn.configure(
                                text="✗ Remove",
                                fg_color=("#ef4444", "#dc2626"),
                                hover_color=("#dc2626", "#b91c1c")
                            )
                            label.configure(text=f"✓ {username}")
                    
                    action_btn.configure(command=toggle_channel)

                # "Add/Remove All Channels" button - toggle based on state
                add_all_btn = None
                if len(campaign["channels"]) > 1:
                    # Check if all channels are added
                    all_added = all(self._is_channel_in_list(ch['url']) for ch in campaign["channels"])
                    
                    add_all_btn = ctk.CTkButton(
                        channels_frame,
                        text=f"✨ {self.t('btn_remove_all_channels')}" if all_added else f"✨ {self.t('btn_add_all_channels')}",
                        height=32,
                        font=ctk.CTkFont(size=12, weight="bold"),
                        fg_color=("#ef4444", "#dc2626") if all_added else ("#10b981", "#059669"),
                        hover_color=("#dc2626", "#b91c1c") if all_added else ("#059669", "#047857"),
                        corner_radius=8,
                    )
                    add_all_btn.grid(
                        row=len(campaign["channels"][:5]),
                        column=0,
                        sticky="ew",
                        pady=(8, 0),
                    )
                    
                    # Function for add/remove all with individual button updates
                    def toggle_all_channels(c=campaign, bulk_btn=add_all_btn, btn_refs=channel_buttons):
                        # Check if all are added
                        all_added = all(self._is_channel_in_list(ch['url']) for ch in c["channels"])
                        
                        if all_added:
                            # Remove all
                            for ch in c["channels"]:
                                self._remove_drop_channel(ch['url'])
                            # Update bulk button
                            bulk_btn.configure(
                                text=f"✨ {translate(self.config_data.language, 'btn_add_all_channels')}",
                                fg_color=("#10b981", "#059669"),
                                hover_color=("#059669", "#047857")
                            )
                            # Update all displayed individual buttons
                            for url, btn, label, username in btn_refs:
                                btn.configure(
                                    text="+ Add",
                                    fg_color=("#3b82f6", "#2563eb"),
                                    hover_color=("#2563eb", "#1d4ed8")
                                )
                                label.configure(text=f"📺 {username}")
                        else:
                            # Add all
                            self._add_all_campaign_channels(c)
                            # Update bulk button
                            bulk_btn.configure(
                                text=f"✨ {translate(self.config_data.language, 'btn_remove_all_channels')}",
                                fg_color=("#ef4444", "#dc2626"),
                                hover_color=("#dc2626", "#b91c1c")
                            )
                            # Update all displayed individual buttons
                            for url, btn, label, username in btn_refs:
                                btn.configure(
                                    text="✗ Remove",
                                    fg_color=("#ef4444", "#dc2626"),
                                    hover_color=("#dc2626", "#b91c1c")
                                )
                                label.configure(text=f"✓ {username}")
                    
                    add_all_btn.configure(command=toggle_all_channels)
                
                # Now configure individual button commands (with access to bulk_btn)
                for url, btn, label, username in channel_buttons:
                    def make_toggle(url=url, btn=btn, label=label, username=username, c=campaign, bulk_btn=add_all_btn, btn_refs=channel_buttons):
                        def toggle():
                            if self._is_channel_in_list(url):
                                # Remove
                                self._remove_drop_channel(url)
                                btn.configure(
                                    text="+ Add",
                                    fg_color=("#3b82f6", "#2563eb"),
                                    hover_color=("#2563eb", "#1d4ed8")
                                )
                                label.configure(text=f"📺 {username}")
                            else:
                                # Add
                                self._add_drop_channel(url, 120, c)
                                btn.configure(
                                    text="✗ Remove",
                                    fg_color=("#ef4444", "#dc2626"),
                                    hover_color=("#dc2626", "#b91c1c")
                                )
                                label.configure(text=f"✓ {username}")
                            
                            # Check if all channels are now added and update bulk button
                            if bulk_btn:
                                all_now_added = all(self._is_channel_in_list(ch['url']) for ch in c["channels"])
                                if all_now_added:
                                    bulk_btn.configure(
                                        text=f"✨ {translate(self.config_data.language, 'btn_remove_all_channels')}",
                                        fg_color=("#ef4444", "#dc2626"),
                                        hover_color=("#dc2626", "#b91c1c")
                                    )
                                else:
                                    bulk_btn.configure(
                                        text=f"✨ {translate(self.config_data.language, 'btn_add_all_channels')}",
                                        fg_color=("#10b981", "#059669"),
                                        hover_color=("#059669", "#047857")
                                    )
                        return toggle
                    
                    btn.configure(command=make_toggle())
        except Exception as e:
            print(f"Error creating campaign display: {e}")
            import traceback
            traceback.print_exc()

    def _setup_progress_tab(self, parent, drops_window):
        """Sets up the progress tab UI"""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)
        
        # Header with refresh button
        header_frame = ctk.CTkFrame(parent, fg_color=("gray86", "gray17"), corner_radius=0, height=60)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)
        
        status_label = ctk.CTkLabel(
            header_frame, text=self.t("drops_progress_loading"),
            font=ctk.CTkFont(size=16, weight="bold")
        )
        status_label.grid(row=0, column=0, sticky="w", padx=20, pady=15)
        
        refresh_btn = ctk.CTkButton(
            header_frame,
            text=self.t("btn_refresh_progress"),
            width=130,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            command=lambda: self._refresh_progress(scrollable_frame, status_label),
        )
        refresh_btn.grid(row=0, column=1, padx=20, pady=15)
        
        # Scrollable frame for progress
        scrollable_frame = ctk.CTkScrollableFrame(
            parent,
            label_text="",
            fg_color=("gray92", "gray14")
        )
        scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # Initial load
        self._refresh_progress(scrollable_frame, status_label)
        
        # Bring window to front after loading
        def load_and_focus():
            try:
                drops_window.lift()
                drops_window.focus_force()
            except:
                pass
        
        threading.Thread(target=load_and_focus, daemon=True).start()

    def _refresh_progress(self, scrollable_frame, status_label):
        """Fetches and displays drop progress"""
        # Clear existing content
        def clear_frame():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            status_label.configure(text=self.t("drops_progress_loading"))
        
        self.after(0, clear_frame)
        
        def display_progress():
            try:
                result = fetch_drops_progress()
                progress_data = result.get("progress", [])
                progress_data = [p for p in progress_data if isinstance(p, dict)]
                driver = result.get("driver")
                
                try:
                    if not progress_data:
                        def show_error():
                            status_label.configure(text=self.t("drops_progress_error"))
                            no_data_label = ctk.CTkLabel(
                                scrollable_frame,
                                text=self.t("drops_progress_no_data"),
                                font=ctk.CTkFont(size=12),
                                text_color="gray",
                            )
                            no_data_label.grid(row=0, column=0, pady=20)
                        self.after(0, show_error)
                        return
                    
                    # Group by status
                    in_progress = [p for p in progress_data if p.get("status") == "in progress"]
                    claimed = [p for p in progress_data if p.get("status") == "claimed"]
                    
                    total = len(progress_data)
                    active = len(in_progress)
                    
                    def update_ui():
                        status_label.configure(
                            text=self.t("drops_progress_loaded", total=total, active=active)
                        )
                        
                        row_idx = 0
                        
                        # Display in-progress campaigns
                        if in_progress:
                            section_label = ctk.CTkLabel(
                                scrollable_frame,
                                text=self.t("drops_progress_in_progress"),
                                font=ctk.CTkFont(size=14, weight="bold"),
                            )
                            section_label.grid(row=row_idx, column=0, sticky="w", padx=20, pady=(20, 10))
                            row_idx += 1
                            
                            for campaign in in_progress:
                                self._create_progress_card(scrollable_frame, campaign, row_idx)
                                row_idx += 1
                        
                        # Display claimed campaigns
                        if claimed:
                            if in_progress:
                                row_idx += 1  # Spacing
                            
                            section_label = ctk.CTkLabel(
                                scrollable_frame,
                                text=self.t("drops_progress_claimed"),
                                font=ctk.CTkFont(size=14, weight="bold"),
                            )
                            section_label.grid(row=row_idx, column=0, sticky="w", padx=20, pady=(20, 10))
                            row_idx += 1
                            
                            for campaign in claimed:
                                self._create_progress_card(scrollable_frame, campaign, row_idx)
                                row_idx += 1
                    
                    self.after(0, update_ui)
                            
                finally:
                    # Close driver after UI is rendered
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                            
            except Exception as e:
                print(f"Error displaying progress: {e}")
                import traceback
                traceback.print_exc()
                def show_error():
                    status_label.configure(text=self.t("drops_progress_error"))
                self.after(0, show_error)
        
        # Run in thread to avoid blocking UI
        threading.Thread(target=display_progress, daemon=True).start()

    def _create_progress_card(self, parent, campaign, row):
        """Creates a card displaying campaign progress"""
        card_frame = ctk.CTkFrame(parent, corner_radius=10)
        card_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=10)
        card_frame.grid_columnconfigure(0, weight=1)
        
        # Campaign name
        name_label = ctk.CTkLabel(
            card_frame,
            text=campaign.get("name", "Unknown Campaign"),
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        name_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(15, 5))
        
        # Game info
        category = campaign.get("category", {})
        game_label = ctk.CTkLabel(
            card_frame,
            text=f"Game: {category.get('name', 'Unknown')}",
            font=ctk.CTkFont(size=12),
        )
        game_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=5)
        
        # Status badge
        status = campaign.get("status", "unknown")
        status_color = "#10b981" if status == "claimed" else "#f59e0b"
        status_label = ctk.CTkLabel(
            card_frame,
            text=status.upper(),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=status_color,
        )
        status_label.grid(row=2, column=0, sticky="w", padx=15, pady=5)
        
        # Rewards with progress
        rewards = campaign.get("rewards", [])
        for i, reward in enumerate(rewards):
            reward_frame = ctk.CTkFrame(card_frame, fg_color=("gray90", "gray16"))
            reward_frame.grid(row=3 + i, column=0, columnspan=2, sticky="ew", padx=15, pady=5)
            reward_frame.grid_columnconfigure(1, weight=1)
            
            # Reward name
            reward_name = ctk.CTkLabel(
                reward_frame,
                text=reward.get("name", "Unknown Reward"),
                font=ctk.CTkFont(size=11),
            )
            reward_name.grid(row=0, column=0, sticky="w", padx=10, pady=5)
            
            # Progress information
            progress = reward.get("progress", 0.0)
            required = reward.get("required_units", 0)
            progress_units = campaign.get("progress_units", 0)
            
            progress_percent = int(progress * 100)
            progress_text = f"{progress_percent}% ({progress_units}/{required} units)"
            
            progress_label = ctk.CTkLabel(
                reward_frame,
                text=progress_text,
                font=ctk.CTkFont(size=10),
                text_color="gray",
            )
            progress_label.grid(row=0, column=1, sticky="e", padx=10, pady=5)
            
            # Progress bar
            progress_bar = ctk.CTkProgressBar(reward_frame)
            progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))
            progress_bar.set(progress)
            
            # Claimed status
            if reward.get("claimed"):
                claimed_label = ctk.CTkLabel(
                    reward_frame,
                    text="✓ Claimed",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color="#10b981",
                )
                claimed_label.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 5))

    def _is_channel_in_list(self, url):
        """Check if a URL is already in the list"""
        return any(item["url"] == url for item in self.config_data.items)
    
    def _find_channel_index(self, url):
        """Find the index of a URL in the list"""
        for idx, item in enumerate(self.config_data.items):
            if item["url"] == url:
                return idx
        return None

    def _add_drop_channel(self, url, minutes=120, campaign=None):
        """Add a drop channel to the queue with campaign info"""
        try:
            campaign_id = campaign.get("id") if campaign else None
            campaign_channels = [
                {"url": ch["url"], "username": ch.get("username", "")} 
                for ch in campaign.get("channels", [])
            ] if campaign else []
            
            # Calculate max required time from rewards if campaign has rewards
            if campaign:
                rewards = campaign.get("rewards", [])
                if rewards:
                    max_required = 0
                    for reward in rewards:
                        required_units = reward.get("required_units", 0)
                        if required_units > max_required:
                            max_required = required_units
                    if max_required > 0:
                        minutes = max_required
            
            # Get category_id from campaign
            required_category_id = None
            if campaign:
                category = campaign.get("category", {})
                if isinstance(category, dict):
                    required_category_id = category.get("id")
                else:
                    # Try from progress_data
                    progress_data = campaign.get("progress_data", {})
                    if isinstance(progress_data, dict):
                        progress_category = progress_data.get("category", {})
                        if isinstance(progress_category, dict):
                            required_category_id = progress_category.get("id")
            
            self.config_data.add(
                url, 
                minutes, 
                campaign_id, 
                campaign_channels,
                required_category_id=required_category_id,
                is_global_drop=False  # Regular drop, not global
            )
            self.refresh_list()
            self.status_var.set(self.t("drops_added", channel=url.split("/")[-1]))
            # Auto-start if enabled and queue not running
            if self.config_data.auto_start and not self.queue_running:
                self.after(500, self._auto_start_queue)
        except Exception as e:
            print(f"Error adding channel: {e}")
    
    def _remove_drop_channel(self, url):
        """Remove a channel from the queue"""
        try:
            idx = self._find_channel_index(url)
            if idx is not None:
                self.config_data.remove(idx)
                if idx in self.workers:
                    self.workers[idx].stop()
                    del self.workers[idx]
                # Re-index workers
                self.workers = {
                    new_i: self.workers[old_i]
                    for new_i, old_i in enumerate(sorted(self.workers.keys()))
                    if old_i < len(self.config_data.items)
                }
                self.refresh_list()
                self.status_var.set(f"Removed: {url.split('/')[-1]}")
        except Exception as e:
            print(f"Error removing channel: {e}")

    def _add_all_campaign_channels(self, campaign):
        """Add all channels from a campaign with campaign grouping"""
        count = 0
        campaign_id = campaign.get("id")
        all_channels = campaign.get("channels", [])
        
        # Calculate max required time from rewards if campaign has rewards
        minutes = 120  # Default
        rewards = campaign.get("rewards", [])
        if rewards:
            max_required = 0
            for reward in rewards:
                required_units = reward.get("required_units", 0)
                if required_units > max_required:
                    max_required = required_units
            if max_required > 0:
                minutes = max_required
        
        # Get category_id from campaign
        required_category_id = None
        category = campaign.get("category", {})
        if isinstance(category, dict):
            required_category_id = category.get("id")
        else:
            # Try from progress_data
            progress_data = campaign.get("progress_data", {})
            if isinstance(progress_data, dict):
                progress_category = progress_data.get("category", {})
                if isinstance(progress_category, dict):
                    required_category_id = progress_category.get("id")
        
        for channel in all_channels:
            try:
                url = channel.get("url") if isinstance(channel, dict) else channel
                # Store all channels as alternatives for each other
                campaign_channels = [
                    {"url": ch.get("url") if isinstance(ch, dict) else ch, 
                     "username": ch.get("username", "") if isinstance(ch, dict) else ""}
                    for ch in all_channels
                ]
                self.config_data.add(
                    url, 
                    minutes, 
                    campaign_id, 
                    campaign_channels,
                    required_category_id=required_category_id,
                    is_global_drop=False  # Regular drop, not global
                )
                count += 1
            except Exception as e:
                print(f"Error adding channel {channel.get('username', 'unknown')}: {e}")

        self.refresh_list()
        self.status_var.set(f"Added {count} channel(s) from {campaign['name']}")
        # Auto-start if enabled and queue not running
        if self.config_data.auto_start and not self.queue_running:
            self.after(500, self._auto_start_queue)

    def _create_tooltip(self, widget, text):
        """Create a tooltip that displays on widget hover"""
        tooltip = None

        def on_enter(event):
            nonlocal tooltip
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() - 10

            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_attributes("-topmost", True)
            
            # Frame with shadow (modern effect)
            frame = tk.Frame(
                tooltip,
                background="#1f2937" if self.config_data.dark_mode else "#ffffff",
                relief="flat",
                borderwidth=0
            )
            frame.pack(padx=2, pady=2)
            
            label = tk.Label(
                frame,
                text=text,
                justify="center",
                background="#1f2937" if self.config_data.dark_mode else "#ffffff",
                foreground="#f9fafb" if self.config_data.dark_mode else "#111827",
                font=("Segoe UI", 10, "bold"),
                padx=12,
                pady=8,
            )
            label.pack()
            
            # Center tooltip above widget
            tooltip.update_idletasks()
            tooltip_width = tooltip.winfo_width()
            tooltip.wm_geometry(f"+{x - tooltip_width // 2}+{y - tooltip.winfo_height() - 10}")

        def on_leave(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    # ----------- Toggles -----------
    def on_toggle_mute(self):
        self.config_data.mute = bool(self.mute_var.get())
        self.config_data.save()
        for w in list(self.workers.values()):
            try:
                w.mute = self.config_data.mute
                w.ensure_player_state()
            except Exception:
                pass

    def on_toggle_hide(self):
        self.config_data.hide_player = bool(self.hide_player_var.get())
        self.config_data.save()
        for w in list(self.workers.values()):
            try:
                w.hide_player = self.config_data.hide_player
                w.ensure_player_state()
            except Exception:
                pass

    def on_toggle_mini(self):
        self.config_data.mini_player = bool(self.mini_player_var.get())
        self.config_data.save()
        for w in list(self.workers.values()):
            try:
                w.mini_player = self.config_data.mini_player
                w.ensure_player_state()
            except Exception:
                pass

    def on_toggle_force_160p(self):
        self.config_data.force_160p = bool(self.force_160p_var.get())
        self.config_data.save()
        # Note: force_160p only affects new streams (set during initialization)
        # Existing streams will need to be restarted to apply the change

    def on_toggle_auto_start(self):
        self.config_data.auto_start = bool(self.auto_start_var.get())
        self.config_data.save()
        if self.config_data.auto_start and not self.queue_running:
            # Auto-start if enabled and queue not running
            if self.config_data.items:
                self.start_all_in_order()
    

    def _auto_start_queue(self):
        """Auto-start queue on launch if enabled"""
        if not self.queue_running and self.config_data.items:
            # Check if there are any unfinished items
            unfinished = [i for i, item in enumerate(self.config_data.items) 
                         if not item.get("finished")]
            if unfinished:
                self.start_all_in_order()

    def _start_offline_retry_monitor(self):
        """Background thread that periodically checks offline streams and retries them"""
        def monitor():
            while True:
                time.sleep(30)  # Check every 30 seconds
                try:
                    if not self.queue_running:
                        continue
                    
                    # Only check if we're not currently running a stream
                    # (Kick only allows 1 stream at a time)
                    if len(self.workers) > 0:
                        continue
                    
                    # Find next unfinished item
                    for idx, item in enumerate(self.config_data.items):
                        if item.get("finished"):
                            continue
                        
                        if idx in self.workers:
                            continue  # Already running
                        
                        # Check if stream is now live
                        if kick_is_live_by_api(item["url"]):
                            # Stream is back online, retry it
                            self.after(0, lambda i=idx: self._start_index(i))
                            break  # Only start one at a time
                except Exception as e:
                    print(f"Monitor error: {e}")
                    time.sleep(60)  # Wait longer on error
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    # ----------- Callbacks Worker -----------
    def on_worker_update(self, idx, seconds, live):
        def ui_update():
            if idx < 0 or idx >= len(self.config_data.items):
                return
            
            item = self.config_data.items[idx]
            is_global_drop = item.get("is_global_drop", False)
            
            if str(idx) in self.tree.get_children():
                values = list(self.tree.item(str(idx), "values"))
                tag = self.t("tag_live") if live else self.t("tag_paused")
                
                if is_global_drop:
                    # Show cumulative time for global drops
                    cumulative_seconds = item.get("cumulative_time", 0) + seconds
                    cumulative_minutes = cumulative_seconds // 60
                    values[2] = f"{cumulative_minutes}m ({tag})"
                else:
                    # Regular drop - show individual time
                    values[2] = f"{seconds}s ({tag})"
                
                current_tags = set(self.tree.item(str(idx), "tags") or [])
                if live:
                    current_tags.discard("paused")
                else:
                    current_tags.add("paused")
                self.tree.item(str(idx), values=values, tags=tuple(current_tags))
            
            # Update status bar with elapsed time
            if is_global_drop:
                cumulative_seconds = item.get("cumulative_time", 0) + seconds
                cumulative_minutes = cumulative_seconds // 60
                secs = cumulative_seconds % 60
                time_str = f"{cumulative_minutes}m {secs}s" if cumulative_minutes > 0 else f"{secs}s"
                status = self.t("tag_live") if live else self.t("tag_paused")
                
                if self.queue_running and self.queue_current_idx == idx:
                    self.status_var.set(f"{self.t('queue_running_status', url=item['url'])} - {time_str} cumulative ({status})")
                else:
                    self.status_var.set(f"{self.t('status_playing', url=item['url'])} - {time_str} cumulative ({status})")
            else:
                minutes = seconds // 60
                secs = seconds % 60
                time_str = f"{minutes}m {secs}s" if minutes > 0 else f"{secs}s"
                status = self.t("tag_live") if live else self.t("tag_paused")
                
                if self.queue_running and self.queue_current_idx == idx:
                    self.status_var.set(f"{self.t('queue_running_status', url=item['url'])} - {time_str} ({status})")
                else:
                    self.status_var.set(f"{self.t('status_playing', url=item['url'])} - {time_str} ({status})")

        self.after(0, ui_update)

    def on_worker_finish(self, idx, elapsed, completed):
        def ui_finish():
            if idx < 0 or idx >= len(self.config_data.items):
                return

            worker = self.workers.get(idx)
            ended_offline = bool(worker and getattr(worker, "ended_because_offline", False))
            ended_wrong_category = bool(worker and getattr(worker, "ended_because_wrong_category", False))
            
            item = self.config_data.items[idx]
            is_global_drop = item.get("is_global_drop", False)
            campaign_id = item.get("campaign_id")
            
            # Initialize completed variable
            # For regular drops, use the value passed from worker
            # For global drops, we'll recalculate based on cumulative time
            completed_value = completed  # Store original value from function parameter
            
            # Track cumulative time for global drops
            if is_global_drop and campaign_id:
                # Add elapsed time to cumulative time for all items in this campaign
                debug_print(f"DEBUG: Global drop - adding {elapsed} seconds to cumulative time")
                for other_item in self.config_data.items:
                    if other_item.get("campaign_id") == campaign_id:
                        current_cumulative = other_item.get("cumulative_time", 0)
                        other_item["cumulative_time"] = current_cumulative + elapsed
                        debug_print(f"DEBUG: Item {other_item['url']} cumulative time: {other_item['cumulative_time']}s")
                self.config_data.save()
                
                # Check if cumulative time reached target
                target_minutes = item.get("minutes", 0)
                cumulative_seconds = item.get("cumulative_time", 0)
                cumulative_minutes = cumulative_seconds // 60
                
                debug_print(f"DEBUG: Cumulative time: {cumulative_minutes} minutes / {target_minutes} minutes target")
                
                if target_minutes > 0 and cumulative_minutes >= target_minutes:
                    # Mark all items in campaign as finished
                    debug_print(f"DEBUG: Target reached! Marking all items in campaign as finished")
                    for other_item in self.config_data.items:
                        if other_item.get("campaign_id") == campaign_id:
                            other_item["finished"] = True
                    self.config_data.save()
                    completed_value = True
                else:
                    # Not finished yet, continue with other streamers
                    completed_value = False
                    debug_print(f"DEBUG: Still need {target_minutes - cumulative_minutes} more minutes")
            
            # Use completed_value (always defined - either from function parameter or recalculated for global drops)
            if completed_value:
                if not is_global_drop:
                    # Regular drop - mark individual item as finished
                    self.config_data.items[idx]["finished"] = True
                    self.config_data.save()
                # Reset tried_channels on successful completion
                self.config_data.items[idx]["tried_channels"] = []
                self.config_data.save()
                if str(idx) in self.tree.get_children():
                    values = list(self.tree.item(str(idx), "values"))
                    if is_global_drop:
                        cumulative_minutes = item.get("cumulative_time", 0) // 60
                        values[2] = f"{cumulative_minutes}m ({self.t('tag_finished')})"
                    else:
                        values[2] = f"{elapsed}s ({self.t('tag_finished')})"
                    current_tags = set(self.tree.item(str(idx), "tags") or [])
                    current_tags.add("finished")
                    current_tags.discard("paused")
                    current_tags.discard("redo")
                    self.tree.item(str(idx), values=values, tags=tuple(current_tags))
            elif ended_offline or ended_wrong_category:
                # Try alternative channel from same campaign
                campaign_channels = item.get("campaign_channels", [])
                
                switched = False
                if campaign_id and campaign_channels:
                    current_url = item["url"]
                    tried_channels = item.get("tried_channels", [])
                    
                    # Add current URL to tried list if not already there
                    if current_url not in tried_channels:
                        tried_channels.append(current_url)
                    
                    # Get all channel URLs
                    all_channel_urls = []
                    for ch in campaign_channels:
                        ch_url = ch.get("url") if isinstance(ch, dict) else ch
                        if ch_url:
                            all_channel_urls.append(ch_url)
                    
                    # Also include current URL in the list
                    if current_url not in all_channel_urls:
                        all_channel_urls.append(current_url)
                    
                    # If we've tried all channels, reset the tried list
                    if len(tried_channels) >= len(all_channel_urls):
                        tried_channels.clear()
                        debug_print(f"DEBUG: Reset tried_channels for campaign {campaign_id} - all channels exhausted")
                    
                    # Find next available live channel from same campaign that hasn't been tried
                    for alt_channel in campaign_channels:
                        alt_url = alt_channel.get("url") if isinstance(alt_channel, dict) else alt_channel
                        if alt_url and alt_url != current_url and alt_url not in tried_channels:
                            # Check if this alternative is live
                            if kick_is_live_by_api(alt_url):
                                # Switch to this alternative channel
                                self.config_data.items[idx]["url"] = alt_url
                                tried_channels.append(alt_url)  # Mark as tried
                                item["tried_channels"] = tried_channels  # Update item
                                self.config_data.save()
                                self.refresh_list()
                                switched = True
                                debug_print(f"DEBUG: Switched to alternative: {alt_url} (tried: {len(tried_channels)}/{len(all_channel_urls)})")
                                self.status_var.set(f"Switched to alternative: {alt_url.split('/')[-1]} - waiting for page to load...")
                                
                                # Retry with new channel if queue is running
                                # Wait 8 seconds to allow browser to fully load the new stream
                                if getattr(self, "queue_running", False):
                                    self.after(8000, lambda i=idx: self._start_index(i))
                                    return
                                break
                    
                    # If no live alternative found, but we haven't tried all channels, mark current as tried and wait
                    if not switched and len(tried_channels) < len(all_channel_urls):
                        item["tried_channels"] = tried_channels  # Update tried list even if no switch
                        self.config_data.save()
                        debug_print(f"DEBUG: No live alternatives found, but {len(all_channel_urls) - len(tried_channels)} channels remain untried")
                
                if not switched:
                    # No alternative found, mark for retry
                    if str(idx) in self.tree.get_children():
                        values = list(self.tree.item(str(idx), "values"))
                        values[2] = f"{elapsed}s ({self.t('retry')})"
                        current_tags = set(self.tree.item(str(idx), "tags") or [])
                        current_tags.add("redo")
                        current_tags.discard("paused")
                        current_tags.discard("finished")
                        self.tree.item(str(idx), values=values, tags=tuple(current_tags))
                    try:
                        self.status_var.set(
                            self.t("offline_wait_retry", url=self.config_data.items[idx]["url"])
                        )
                    except Exception:
                        pass

            # Continue queue if applicable
            if getattr(self, "queue_running", False) and self.queue_current_idx == idx:
                self._run_queue_from(idx + 1)

        self.after(0, ui_finish)