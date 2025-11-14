import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from urllib.parse import urlparse
import urllib.request
import random

# --- UI moderne
import customtkinter as ctk
from PIL import Image, ImageTk

# --- Selenium avec undetected-chromedriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

APP_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_DIR = os.path.join(APP_DIR, "cookies")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

os.makedirs(COOKIES_DIR, exist_ok=True)

# ===============================
# Traductions (FR/EN)
# ===============================
BUILTIN_TRANSLATIONS = {
    "fr": {
        "status_ready": "Prêt",
        "title_streams": "Liste des streams",
        "col_minutes": "Objectif (min)",
        "col_elapsed": "Écoulé",
        "btn_add": "Ajouter un lien",
        "btn_remove": "Supprimer",
        "btn_start_queue": "Démarrer la file",
        "btn_stop_sel": "Stop sélection",
        "btn_signin": "Se connecter (cookies)",
        "btn_chromedriver": "Chromedriver...",
        "btn_extension": "Extension Chrome...",
        "switch_mute": "Muet",
        "switch_hide": "Masquer le lecteur",
        "switch_mini": "Mini-lecteur",
        "label_theme": "Thème",
        "theme_dark": "Sombre",
        "theme_light": "Clair",
        "label_language": "Langue",
        "language_fr": "Français",
        "language_en": "English",
        "prompt_live_url_title": "Live URL",
        "prompt_live_url_msg": "Entre l'URL Kick du live :",
        "prompt_minutes_title": "Objectif (minutes)",
        "prompt_minutes_msg": "Minutes à regarder (0 = infini) :",
        "status_link_added": "Lien ajouté",
        "status_link_removed": "Lien supprimé",
        "offline_wait_retry": "Offline: {url} - en attente d'un prochain essai",
        "error": "Erreur",
        "invalid_url": "URL invalide.",
        "cookies_missing_title": "Cookies manquants",
        "cookies_missing_msg": "Aucun cookie sauvegardé. Ouvrir le navigateur pour se connecter ?",
        "status_playing": "Lecture : {url}",
        "queue_running_status": "File en cours - {url}",
        "queue_finished_status": "File terminée",
        "status_stopped": "Arrêté",
        "chrome_start_fail": "Chrome n'a pas pu démarrer : {e}",
        "action_required": "Action requise",
        "sign_in_and_click_ok": "Connecte-toi dans la fenêtre Chrome, puis clique sur OK pour sauvegarder les cookies.",
        "ok": "OK",
        "cookies_saved_for": "Cookies sauvegardés pour {domain}",
        "cannot_save_cookies": "Impossible d'enregistrer les cookies : {e}",
        "connect_title": "Connexion",
        "open_url_to_get_cookies": "Ouvrir {url} pour récupérer les cookies ?",
        "pick_chromedriver_title": "Sélectionne chromedriver (ou binaire ChromeDriver)",
        "executables_filter": "Exécutables",
        "chromedriver_set": "Chromedriver défini : {path}",
        "pick_extension_title": "Sélectionne une extension (.crx) ou un dossier d'extension décompressée",
        "extension_set": "Extension définie : {path}",
        "all_files_filter": "Tous fichiers",
        "tag_live": "EN DIRECT",
        "tag_paused": "PAUSE",
        "tag_finished": "TERMINÉ",
        "tag_stop": "STOP",
        "retry": "Réessayer",
    },
    "en": {
        "status_ready": "Ready",
        "title_streams": "Streams list",
        "col_minutes": "Target (min)",
        "col_elapsed": "Elapsed",
        "btn_add": "Add link",
        "btn_remove": "Remove",
        "btn_start_queue": "Start queue",
        "btn_stop_sel": "Stop selected",
        "btn_signin": "Sign in (cookies)",
        "btn_chromedriver": "Chromedriver...",
        "btn_extension": "Chrome extension...",
        "switch_mute": "Mute",
        "switch_hide": "Hide player",
        "switch_mini": "Mini player",
        "label_theme": "Theme",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "label_language": "Language",
        "language_fr": "Français",
        "language_en": "English",
        "prompt_live_url_title": "Live URL",
        "prompt_live_url_msg": "Enter the Kick live URL:",
        "prompt_minutes_title": "Target (minutes)",
        "prompt_minutes_msg": "Minutes to watch (0 = infinite):",
        "status_link_added": "Link added",
        "status_link_removed": "Link removed",
        "offline_wait_retry": "Offline: {url} - waiting for next retry",
        "error": "Error",
        "invalid_url": "Invalid URL.",
        "cookies_missing_title": "Missing cookies",
        "cookies_missing_msg": "No saved cookies. Open browser to sign in?",
        "status_playing": "Playing: {url}",
        "queue_running_status": "Queue running - {url}",
        "queue_finished_status": "Queue finished",
        "status_stopped": "Stopped",
        "chrome_start_fail": "Chrome could not start: {e}",
        "action_required": "Action required",
        "sign_in_and_click_ok": "Sign in in the Chrome window, then click OK to save cookies.",
        "ok": "OK",
        "cookies_saved_for": "Cookies saved for {domain}",
        "cannot_save_cookies": "Could not save cookies: {e}",
        "connect_title": "Login",
        "open_url_to_get_cookies": "Open {url} to retrieve cookies?",
        "pick_chromedriver_title": "Select chromedriver (or ChromeDriver binary)",
        "executables_filter": "Executables",
        "chromedriver_set": "Chromedriver set: {path}",
        "pick_extension_title": "Select an extension (.crx) or an unpacked extension folder",
        "extension_set": "Extension set: {path}",
        "all_files_filter": "All files",
        "tag_live": "LIVE",
        "tag_paused": "PAUSED",
        "tag_finished": "FINISHED",
        "tag_stop": "STOP",
        "retry": "Retry",
    },
}

def _load_external_translations():
    data = {}
    locale_dir = os.path.join(APP_DIR, "locales")
    if not os.path.exists(locale_dir):
        return data
    for lang in os.listdir(locale_dir):
        path = os.path.join(locale_dir, lang, "messages.json")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data[lang] = json.load(f)
            except Exception:
                data[lang] = {}
    return data

def _merge_fallback(external, builtin):
    result = {}
    all_langs = set(external.keys()) | set(builtin.keys())
    for lang in all_langs:
        merged = dict(builtin.get(lang, {}))
        merged.update(external.get(lang, {}))
        result[lang] = merged
    return result

# Loads translations from files if present, with fallback to embedded values
TRANSLATIONS = _merge_fallback(_load_external_translations(), BUILTIN_TRANSLATIONS)
def translate(lang: str, key: str) -> str:
    return TRANSLATIONS.get(lang or "fr", TRANSLATIONS.get("fr", {})).get(key, key)

# ===============================
# Utilitaires / données
# ===============================
def domain_from_url(url):
    p = urlparse(url)
    return p.netloc

def cookie_file_for_domain(domain):
    safe = domain.replace(":", "_")
    return os.path.join(COOKIES_DIR, f"{safe}.json")

def kick_is_live_by_api(url: str) -> bool:
    """Renvoie True si la chaîne Kick est en direct (via API).
       En cas d’erreur réseau, on renvoie True pour ne pas bloquer la file.
    """
    try:
        p = urlparse(url)
        if "kick.com" not in p.netloc:
            return True
        username = p.path.strip("/").split("/")[0]
        if not username:
            return True
        api_url = f"https://kick.com/api/v2/channels/{username}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
        livestream = data.get("livestream")
        return bool(livestream and livestream.get("is_live"))
    except Exception:
        return True

class CookieManager:
    @staticmethod
    def save_cookies(driver, domain):
        path = cookie_file_for_domain(domain)
        cookies = driver.get_cookies()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        return path

    @staticmethod
    def load_cookies(driver, domain):
        path = cookie_file_for_domain(domain)
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        for c in cookies:
            # Corrige certains champs qui posent problème
            if "expiry" in c and c["expiry"] is None:
                del c["expiry"]
            try:
                driver.add_cookie(c)
            except Exception:
                pass
        return True

    @staticmethod
    def import_from_browser(domain: str) -> bool:
        """Tente d'importer les cookies existants depuis les navigateurs (Chrome/Edge/Firefox)
        à l'aide de browser_cookie3. Renvoie True si un fichier a été écrit.
        """
        try:
            import browser_cookie3 as bc3  # type: ignore
        except Exception:
            return False

        try:
            cj = bc3.load(domain_name=domain)
        except Exception:
            cj = None

        if not cj:
            return False

        cookies = []
        try:
            for c in cj:
                if not getattr(c, "name", None):
                    continue
                cookie = {
                    "name": c.name,
                    "value": c.value,
                    "domain": getattr(c, "domain", domain) or domain,
                    "path": getattr(c, "path", "/") or "/",
                    "secure": bool(getattr(c, "secure", False)),
                }
                exp = getattr(c, "expires", None)
                if exp is not None:
                    try:
                        cookie["expiry"] = int(exp)
                    except Exception:
                        pass
                cookies.append(cookie)
        except Exception:
            return False

        if not cookies:
            return False

        path = cookie_file_for_domain(domain)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            return True
        except Exception:
            return False

def make_chrome_driver(
    headless=True,
    visible_width=1280,
    visible_height=800,
    driver_path=None,
    extension_path=None,
):
    opts = uc.ChromeOptions()  # Utilise les options d'undetected-chromedriver

    # Configuration headless (adaptée pour uc)
    if headless:
        try:
            opts.add_argument("--headless=new")
        except Exception:
            opts.add_argument("--headless")
        opts.add_argument("--disable-gpu")
    else:
        opts.add_argument(f"--window-size={visible_width},{visible_height}")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    # Suppression des options expérimentales redondantes pour éviter l'erreur de parsing
    # (undetected-chromedriver gère déjà cela nativement)
    opts.add_argument("--log-level=3")
    opts.add_argument("--silent")

    user_data_dir = os.path.join(APP_DIR, "chrome_data")
    os.makedirs(user_data_dir, exist_ok=True)
    opts.add_argument(f"--user-data-dir={user_data_dir}")

    # Chargement d'extension (compatible avec uc)
    if extension_path:
        try:
            if extension_path.lower().endswith(".crx"):
                opts.add_extension(extension_path)
            else:
                opts.add_argument(f"--load-extension={extension_path}")
        except Exception:
            pass

    # Création du driver avec undetected-chromedriver
    # (driver_path n'est plus nécessaire, car uc gère le téléchargement automatique)
    driver = uc.Chrome(options=opts, version_main=None)  # version_main=None pour la dernière version

    return driver

# ===============================
# Worker streaming
# ===============================
class StreamWorker(threading.Thread):
    def __init__(
        self,
        url,
        minutes_target,
        on_update=None,
        on_finish=None,
        stop_event=None,
        driver_path=None,
        extension_path=None,
        hide_player=False,
        mute=True,
        mini_player=False,
    ):
        super().__init__(daemon=True)
        self.url = url
        self.minutes_target = minutes_target
        self.on_update = on_update
        self.on_finish = on_finish
        self.stop_event = stop_event or threading.Event()
        self.elapsed_seconds = 0
        self.driver = None
        self.driver_path = driver_path
        self.extension_path = extension_path
        self.hide_player = hide_player
        self.mute = mute
        self.mini_player = mini_player
        self.completed = False
        # Anti rate-limit: cache "is live" checks
        self._last_live_check = 0.0
        self._last_live_value = True
        self._live_check_interval = 30  # seconds

    def run(self):
        domain = domain_from_url(self.url)
        try:
            # Si on charge un .crx, Chrome ne peut pas être headless
            use_headless = bool(self.hide_player)
            # Si mini_player activé, force visible pour afficher la petite fenêtre
            if self.mini_player:
                use_headless = False
            # Si hide_player activé, force headless pour masquer la fenêtre entière (sauf si mini_player prioritaire)
            if self.extension_path and self.extension_path.endswith(".crx"):
                use_headless = False

            self.driver = make_chrome_driver(
                headless=use_headless,
                driver_path=self.driver_path,
                extension_path=self.extension_path,
            )

            if not use_headless and self.mini_player:
                try:
                    self.driver.set_window_size(360, 360)
                    self.driver.set_window_position(20, 20)
                except Exception:
                    pass

            base = f"https://{domain}" if domain else "about:blank"
            if domain:
                self.driver.get(base)
                CookieManager.load_cookies(self.driver, domain)
            self.driver.get(self.url)

            try:
                self.ensure_player_state()
            except Exception:
                pass

            last_report = 0
            while not self.stop_event.is_set():
                live = self.is_stream_live()
                try:
                    self.ensure_player_state()
                except Exception:
                    pass
                if live:
                    self.elapsed_seconds += 1
                if time.time() - last_report >= 1:
                    last_report = time.time()
                    if self.on_update:
                        self.on_update(self.elapsed_seconds, live)
                if self.minutes_target and self.elapsed_seconds >= self.minutes_target * 60:
                    self.completed = True
                    break
                time.sleep(1)
        except Exception as e:
            print("StreamWorker error:", e)
        finally:
            try:
                if self.driver:
                    self.driver.quit()
            except Exception:
                pass
            try:
                if self.on_finish:
                    self.on_finish(self.elapsed_seconds, self.completed)
            except Exception:
                pass

    def stop(self):
        self.stop_event.set()

    def is_stream_live(self):
        now = time.time()
        # Cache API checks to reduce rate-limit risk
        if now - self._last_live_check < self._live_check_interval:
            return self._last_live_value
        try:
            # On combine API + fallback DOM
            if kick_is_live_by_api(self.url):
                self._last_live_value = True
                return True
            body = self.driver.find_element(By.TAG_NAME, "body").text
            self._last_live_value = ("LIVE" in body.upper())
            return self._last_live_value
        except Exception:
            self._last_live_value = False
            return False
        finally:
            # add slight jitter to desync multiple workers
            jitter = random.uniform(-5, 5)
            self._live_check_interval = max(10, 30 + jitter)
            self._last_live_check = now

    def ensure_player_state(self):
        try:
            hide = 'true' if self.hide_player else 'false'
            muted = 'true' if self.mute else 'false'
            volume = '0' if self.mute else '1'
            mini = 'true' if (not self.hide_player and self.mini_player) else 'false'
            js = f"""
            (function(){{
              var v = document.querySelector('video');
              if (v) {{
                try {{ v.muted = {muted}; v.volume = {volume}; }} catch(e) {{}}
                if ({hide}) {{
                  v.style.opacity='0';
                  v.style.width='1px';
                  v.style.height='1px';
                  v.style.position='fixed';
                  v.style.bottom='0';
                  v.style.right='0';
                  v.style.pointerEvents='none';
                }} else if ({mini}) {{
                  v.style.opacity='1';
                  v.style.width='100px';
                  v.style.height='100px';
                  v.style.position='fixed';
                  v.style.bottom='6px';
                  v.style.right='6px';
                  v.style.pointerEvents='none';
                  v.style.zIndex='999999';
                }} else {{
                  v.style.opacity='';
                  v.style.width='';
                  v.style.height='';
                  v.style.position='';
                  v.style.bottom='';
                  v.style.right='';
                  v.style.pointerEvents='';
                }}
              }}
            }})();
            """
            self.driver.execute_script(js)
        except Exception:
            pass

# ===============================
# Config
# ===============================
class Config:
    def __init__(self):
        self.items = []
        self.chromedriver_path = None
        self.extension_path = None
        self.mute = True
        self.hide_player = False
        self.mini_player = False
        self.dark_mode = True  # par défaut sombre
        self.language = "fr"   # fr ou en
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.items = data.get("items", [])
            self.chromedriver_path = data.get("chromedriver_path")
            self.extension_path = data.get("extension_path")
            self.mute = data.get("mute", True)
            self.hide_player = data.get("hide_player", False)
            self.mini_player = data.get("mini_player", False)
            self.dark_mode = data.get("dark_mode", True)
            self.language = data.get("language", "fr")
        else:
            self.items = []

    def save(self):
        data = {
            "items": self.items,
            "chromedriver_path": self.chromedriver_path,
            "extension_path": self.extension_path,
            "mute": self.mute,
            "hide_player": self.hide_player,
            "mini_player": self.mini_player,
            "dark_mode": self.dark_mode,
            "language": self.language,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add(self, url, minutes):
        self.items.append({"url": url, "minutes": minutes})
        self.save()

    def remove(self, idx):
        del self.items[idx]
        self.save()

# ===============================
# Application (CustomTkinter UI)
# ===============================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Kick Drop Miner")
        self.geometry("1000x650")
        self.minsize(900, 580)

        self.config_data = Config()
        self.workers = {}
        self._interactive_driver = None  # Chrome pour capture de cookies
        self.queue_running = False
        self.queue_current_idx = None

        # Helper traduction
        def _t(key: str, **kwargs):
            return translate(self.config_data.language, key).format(**kwargs)
        self.t = _t

        # Apparence / thème
        ctk.set_appearance_mode("Dark" if self.config_data.dark_mode else "Light")
        ctk.set_default_color_theme("dark-blue")

        # Layout principal: 2 colonnes (sidebar gauche, contenu droit)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        # Laisse l'espace libre en bas pour éviter de couper les contrôles
        # (utilise une ligne vide élevée pour servir d'espace extensible)
        self.sidebar.grid_rowconfigure(99, weight=1)

        self._build_sidebar()

        # Contenu principal
        self.content = ctk.CTkFrame(self, corner_radius=12)
        self.content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self._build_content()

        # Barre d'état
        self.status_var = tk.StringVar(value=self.t("status_ready"))
        self.status = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w", height=26)
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,10))

        self.refresh_list()
        # Fermer proprement tous les navigateurs à la fermeture de l'app
        try:
            self.protocol("WM_DELETE_WINDOW", self.on_close)
        except Exception:
            pass

    # ----------- UI construction -----------
    def _build_sidebar(self):
        header = ctk.CTkFrame(self.sidebar, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, padx=10, pady=(10,6), sticky="w")
        header.grid_columnconfigure(1, weight=1)

        # Logo (assets/logo.png) + titre
        try:
            logo_path = os.path.join(APP_DIR, "assets", "logo.png")
            img = Image.open(logo_path)
            self._logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(24,24))
            logo_lbl = ctk.CTkLabel(header, image=self._logo_img, text="")
            logo_lbl.grid(row=0, column=0, padx=(4,6), pady=4, sticky="w")
        except Exception:
            pass

        title = ctk.CTkLabel(header, text="Kick Drop Miner", font=ctk.CTkFont(size=18, weight="bold"))
        title.grid(row=0, column=1, padx=0, pady=4, sticky="w")

        # Actions principales
        btn_add = ctk.CTkButton(self.sidebar, text=self.t("btn_add"), command=self.add_link, width=180)
        btn_add.grid(row=1, column=0, padx=14, pady=6, sticky="w")

        btn_remove = ctk.CTkButton(self.sidebar, text=self.t("btn_remove"), command=self.remove_selected, width=180)
        btn_remove.grid(row=2, column=0, padx=14, pady=6, sticky="w")

        btn_start_queue = ctk.CTkButton(self.sidebar, text=self.t("btn_start_queue"), command=self.start_all_in_order, width=180)
        btn_start_queue.grid(row=3, column=0, padx=14, pady=(6,2), sticky="w")

        btn_stop = ctk.CTkButton(self.sidebar, text=self.t("btn_stop_sel"), command=self.stop_selected, fg_color="#E74C3C", hover_color="#C0392B", width=180)
        btn_stop.grid(row=4, column=0, padx=14, pady=6, sticky="w")

        btn_signin = ctk.CTkButton(self.sidebar, text=self.t("btn_signin"), command=self.connect_to_kick, width=180)
        btn_signin.grid(row=5, column=0, padx=14, pady=6, sticky="w")

        # Fichiers
        btn_chromedriver = ctk.CTkButton(self.sidebar, text=self.t("btn_chromedriver"), command=self.choose_chromedriver, width=180)
        btn_chromedriver.grid(row=6, column=0, padx=14, pady=(18,6), sticky="w")

        btn_extension = ctk.CTkButton(self.sidebar, text=self.t("btn_extension"), command=self.choose_extension, width=180)
        btn_extension.grid(row=7, column=0, padx=14, pady=6, sticky="w")

        # Toggles
        self.mute_var = tk.BooleanVar(value=bool(self.config_data.mute))
        self.hide_player_var = tk.BooleanVar(value=bool(self.config_data.hide_player))
        self.mini_player_var = tk.BooleanVar(value=bool(self.config_data.mini_player))

        sw_mute = ctk.CTkSwitch(self.sidebar, text=self.t("switch_mute"), command=self.on_toggle_mute, variable=self.mute_var)
        sw_mute.grid(row=8, column=0, padx=14, pady=(18,6), sticky="w")

        sw_hide = ctk.CTkSwitch(self.sidebar, text=self.t("switch_hide"), command=self.on_toggle_hide, variable=self.hide_player_var)
        sw_hide.grid(row=9, column=0, padx=14, pady=6, sticky="w")

        sw_mini = ctk.CTkSwitch(self.sidebar, text=self.t("switch_mini"), command=self.on_toggle_mini, variable=self.mini_player_var)
        sw_mini.grid(row=10, column=0, padx=14, pady=6, sticky="w")

        # Thème
        self.theme_var = tk.StringVar(value=self.t("theme_dark") if self.config_data.dark_mode else self.t("theme_light"))
        theme_label = ctk.CTkLabel(self.sidebar, text=self.t("label_theme"))
        theme_label.grid(row=11, column=0, padx=14, pady=(18,4), sticky="w")
        theme_menu = ctk.CTkOptionMenu(self.sidebar, values=[self.t("theme_dark"), self.t("theme_light")], command=self.change_theme, variable=self.theme_var, width=180)
        theme_menu.grid(row=12, column=0, padx=14, pady=(0,14), sticky="w")

        # Language
        locale_dir = os.path.join(APP_DIR, "locales")
        langs = [d for d in os.listdir(locale_dir) 
                if os.path.isfile(os.path.join(locale_dir, d, "messages.json"))]

        names = [self.t(f"language_{code}") if self.t(f"language_{code}") != f"language_{code}" else code.upper() 
                for code in langs]

        self.lang_var = tk.StringVar(value=self.t(f"language_{self.config_data.language}") or self.config_data.language.upper())

        lang_label = ctk.CTkLabel(self.sidebar, text=self.t("label_language"))
        lang_label.grid(row=13, column=0, padx=14, pady=(4,4), sticky="w")

        self.lang_menu = ctk.CTkOptionMenu(self.sidebar,
                                        values=names,
                                        command=self.change_language,
                                        variable=self.lang_var,
                                        width=180)
        self.lang_menu.grid(row=14, column=0, padx=14, pady=(0,14), sticky="w")

        self.lang_map = dict(zip(names, langs))

    def _build_content(self):
        header = ctk.CTkFrame(self.content, corner_radius=12)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,6))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text=self.t("title_streams"), font=ctk.CTkFont(size=16, weight="bold"))
        title.grid(row=0, column=0, sticky="w", padx=10, pady=10)

        # Tableau (ttk.Treeview) dans un CTkFrame
        table_frame = ctk.CTkFrame(self.content, corner_radius=12)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        # Thème clair/sombre automatique
        if ctk.get_appearance_mode() == "Dark":
            style.theme_use("clam")
            style.configure("Treeview",
                            background="#1f2125",
                            fieldbackground="#1f2125",
                            foreground="#e6e6e6",
                            rowheight=26,
                            bordercolor="#2b2d31")
            style.configure("Treeview.Heading",
                            background="#2b2d31",
                            foreground="#e6e6e6",
                            font=("Segoe UI", 10, "bold"))
            sel_bg = "#3b82f6"
            style.map("Treeview", background=[("selected", sel_bg)], foreground=[("selected", "white")])
        else:
            style.theme_use("clam")
            style.configure("Treeview",
                            background="#ffffff",
                            fieldbackground="#ffffff",
                            foreground="#111111",
                            rowheight=26,
                            bordercolor="#e9ecef")
            style.configure("Treeview.Heading",
                            background="#eef2f7",
                            foreground="#111111",
                            font=("Segoe UI", 10, "bold"))
            sel_bg = "#2d8cff"
            style.map("Treeview", background=[("selected", sel_bg)], foreground=[("selected", "white")])

        self.tree = ttk.Treeview(table_frame, columns=("url", "minutes", "elapsed"), show="headings", selectmode="browse")
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

        # Lignes colorées via tags
        try:
            self.tree.tag_configure("odd", background="#0f0f11" if ctk.get_appearance_mode() == "Dark" else "#f7f7f7")
            self.tree.tag_configure("even", background="#1f2125" if ctk.get_appearance_mode() == "Dark" else "#ffffff")
            self.tree.tag_configure("redo", background="#3a3a00" if ctk.get_appearance_mode() == "Dark" else "#fff3cd")
            self.tree.tag_configure("paused", background="#3a2e2a" if ctk.get_appearance_mode() == "Dark" else "#fde2e2")
            self.tree.tag_configure("finished", background="#22352a" if ctk.get_appearance_mode() == "Dark" else "#e6f7e8")
        except Exception:
            pass

    # ----------- Thème -----------
    def change_theme(self, choice):
        # Accepte FR/EN
        dark = (choice in (self.t("theme_dark"), "Sombre", "Dark"))
        self.config_data.dark_mode = dark
        self.config_data.save()
        ctk.set_appearance_mode("Dark" if dark else "Light")
        # Rebuild contenu (pour recalculer styles Treeview)
        for w in self.content.winfo_children():
            w.destroy()
        self._build_content()
        self.refresh_list()

    # ----------- Language -----------
    def change_language(self, choice):
        new_lang = self.lang_map.get(choice) or "en"
        if self.config_data.language == new_lang:
            return

        self.config_data.language = new_lang
        self.config_data.save()

        # Rebuild UI
        for w in self.sidebar.winfo_children():
            w.destroy()
        self._build_sidebar()
        for w in self.content.winfo_children():
            w.destroy()
        self._build_content()

        # Update status
        if self.status_var.get() in [translate(l, "status_ready") for l in self.lang_map.values()]:
            self.status_var.set(self.t("status_ready"))
        else:
            self.status_var.set(self.t("status_ready") or "Ready")

    # ----------- Actions -----------
    def refresh_list(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for i, item in enumerate(self.config_data.items):
            elapsed = self.workers[i].elapsed_seconds if i in self.workers else 0
            tags = ["odd" if i % 2 else "even"]
            if item.get("finished"):
                tags.append("finished")
            self.tree.insert("", "end", iid=str(i),
                             values=(item["url"], item["minutes"], f"{elapsed}s"),
                             tags=tuple(tags))

    def add_link(self):
        url = simpledialog.askstring(self.t("prompt_live_url_title"), self.t("prompt_live_url_msg"))
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        minutes = simpledialog.askinteger(self.t("prompt_minutes_title"), self.t("prompt_minutes_msg"), minvalue=0)
        self.config_data.add(url, minutes or 0)
        self.refresh_list()
        self.status_var.set(self.t("status_link_added"))

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.config_data.remove(idx)
        if idx in self.workers:
            self.workers[idx].stop()
            del self.workers[idx]
        # Réindexer les workers (car les indices ont bougé)
        self.workers = {new_i: self.workers[old_i]
                        for new_i, old_i in enumerate(sorted(self.workers.keys()))
                        if old_i < len(self.config_data.items)}
        self.refresh_list()
        self.status_var.set(self.t("status_link_removed"))

    def start_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self._start_index(idx)

    def _start_index(self, idx):
        item = self.config_data.items[idx]
        if not kick_is_live_by_api(item["url"]):
            try:
                values = list(self.tree.item(str(idx), "values"))
                values[2] = self.t("retry")
                self.tree.item(str(idx), values=values, tags=("redo",))
            except Exception:
                pass
            self.status_var.set(self.t("offline_wait_retry", url=item['url']))
            return

        domain = domain_from_url(item["url"])
        if not domain:
            messagebox.showerror(self.t("error"), self.t("invalid_url"))
            return

        cookie_path = cookie_file_for_domain(domain)
        if not os.path.exists(cookie_path):
            # Essaye d'abord d'importer automatiquement depuis le navigateur
            try:
                if CookieManager.import_from_browser(domain):
                    self.status_var.set(self.t("cookies_saved_for", domain=domain))
                else:
                    if messagebox.askyesno(self.t("cookies_missing_title"), self.t("cookies_missing_msg")):
                        self.obtain_cookies_interactively(item["url"], domain)
            except Exception:
                if messagebox.askyesno(self.t("cookies_missing_title"), self.t("cookies_missing_msg")):
                    self.obtain_cookies_interactively(item["url"], domain)

        stop_event = threading.Event()
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
        )
        self.workers[idx] = worker
        worker.start()
        self.tree.selection_set(str(idx))
        self.status_var.set(self.t("status_playing", url=item['url']))

    def start_all_in_order(self):
        self.queue_running = True
        self.queue_current_idx = None
        self._run_queue_from(0)

    def _run_queue_from(self, start_idx: int):
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
                self.status_var.set(self.t("queue_running_status", url=item['url']))
                return
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
            # Met à jour l'affichage
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
            messagebox.showinfo(self.t("ok"), self.t("cookies_saved_for", domain=domain))
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
        # Arrête la file et ferme toutes les fenêtres de navigateur
        try:
            self.queue_running = False
        except Exception:
            pass

        # Ferme la fenêtre Chrome d'import cookies si ouverte
        try:
            if self._interactive_driver:
                try:
                    self._interactive_driver.quit()
                except Exception:
                    pass
                self._interactive_driver = None
        except Exception:
            pass

        # Stoppe et ferme tous les drivers Selenium des workers
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

        # Attend brièvement l'arrêt des threads
        for idx, w in list(self.workers.items()):
            try:
                w.join(timeout=2.5)
            except Exception:
                pass

        # Ferme l'application
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
        # Tentative d'import automatique des cookies depuis le navigateur
        try:
            if CookieManager.import_from_browser(domain):
                messagebox.showinfo(self.t("ok"), self.t("cookies_saved_for", domain=domain))
                return
        except Exception:
            pass
        # Sinon, repli sur la méthode interactive existante
        if messagebox.askyesno(self.t("connect_title"), self.t("open_url_to_get_cookies", url=url)):
            self.obtain_cookies_interactively(url, domain)

    def choose_chromedriver(self):
        path = filedialog.askopenfilename(title=self.t("pick_chromedriver_title"),
                                          filetypes=[(self.t("executables_filter"), "*.exe;*")])
        if not path:
            return
        self.config_data.chromedriver_path = path
        self.config_data.save()
        messagebox.showinfo(self.t("ok"), self.t("chromedriver_set", path=path))

    def choose_extension(self):
        path = filedialog.askopenfilename(title=self.t("pick_extension_title"),
                                          filetypes=[("CRX", "*.crx"), (self.t("all_files_filter"), "*.*")])
        if not path:
            return
        self.config_data.extension_path = path
        self.config_data.save()
        messagebox.showinfo(self.t("ok"), self.t("extension_set", path=path))

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

    # ----------- Callbacks Worker -----------
    def on_worker_update(self, idx, seconds, live):
        def ui_update():
            if str(idx) in self.tree.get_children():
                values = list(self.tree.item(str(idx), "values"))
                tag = self.t("tag_live") if live else self.t("tag_paused")
                values[2] = f"{seconds}s ({tag})"
                current_tags = set(self.tree.item(str(idx), 'tags') or [])
                if live:
                    current_tags.discard('paused')
                else:
                    current_tags.add('paused')
                self.tree.item(str(idx), values=values, tags=tuple(current_tags))
        self.after(0, ui_update)

    def on_worker_finish(self, idx, elapsed, completed):
        def ui_finish():
            if idx < 0 or idx >= len(self.config_data.items):
                return
            if completed:
                self.config_data.items[idx]["finished"] = True
                self.config_data.save()
                if str(idx) in self.tree.get_children():
                    values = list(self.tree.item(str(idx), "values"))
                    values[2] = f"{elapsed}s ({self.t('tag_finished')})"
                    current_tags = set(self.tree.item(str(idx), 'tags') or [])
                    current_tags.add('finished')
                    current_tags.discard('paused')
                    current_tags.discard('redo')
                    self.tree.item(str(idx), values=values, tags=tuple(current_tags))

            # Enchaîne la file le cas échéant
            if getattr(self, "queue_running", False) and self.queue_current_idx == idx:
                self._run_queue_from(idx + 1)

        self.after(0, ui_finish)

# ===============================
# Main
# ===============================
if __name__ == "__main__":
    app = App()
    app.mainloop()
