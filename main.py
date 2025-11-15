import json
import os
import sys
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from urllib.parse import urlparse
import urllib.request
import random
from io import BytesIO
import base64
import re


# --- UI moderne
import customtkinter as ctk
from PIL import Image, ImageTk

# --- Selenium avec undetected-chromedriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


def _resolve_app_dir():
    """Directory that contains bundled resources/assets."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _resolve_data_dir(resource_dir):
    """Writable directory used for config, cookies and persistent Chrome data."""
    data_dir = resource_dir
    if getattr(sys, "frozen", False):
        # Store alongside the executable for a fully portable setup
        data_dir = os.path.dirname(sys.executable)
    try:
        os.makedirs(data_dir, exist_ok=True)
    except Exception:
        # Fallback to a writable location if the portable directory is locked
        fallback = os.environ.get("APPDATA") or resource_dir
        data_dir = os.path.join(fallback, "KickDropsMiner") if fallback != resource_dir else resource_dir
        os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _migrate_portable_data(resource_dir, data_dir):
    """Copies existing config/cookies from the exe folder on first run of a bundled build."""
    if resource_dir == data_dir:
        return

    # Copy config.json once so prior portable installs keep their data
    src_config = os.path.join(resource_dir, "config.json")
    dst_config = os.path.join(data_dir, "config.json")
    if os.path.exists(src_config) and not os.path.exists(dst_config):
        try:
            os.makedirs(os.path.dirname(dst_config), exist_ok=True)
            shutil.copy2(src_config, dst_config)
        except Exception:
            pass

    # Copy cookies/ and chrome_data/ if the new profile dirs are empty
    for folder in ("cookies", "chrome_data"):
        src = os.path.join(resource_dir, folder)
        dst = os.path.join(data_dir, folder)
        if not os.path.isdir(src):
            continue
        try:
            has_existing = os.path.isdir(dst) and any(os.scandir(dst))
        except Exception:
            has_existing = False
        if has_existing:
            continue
        try:
            shutil.copytree(src, dst, dirs_exist_ok=True)
        except Exception:
            pass


APP_DIR = _resolve_app_dir()
DATA_DIR = _resolve_data_dir(APP_DIR)
_migrate_portable_data(APP_DIR, DATA_DIR)
COOKIES_DIR = os.path.join(DATA_DIR, "cookies")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
CHROME_DATA_DIR = os.path.join(DATA_DIR, "chrome_data")

os.makedirs(COOKIES_DIR, exist_ok=True)
os.makedirs(CHROME_DATA_DIR, exist_ok=True)

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
        "language_tr": "Turc",
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
        "btn_drops": "Campagnes Drops",
        "drops_title": "Campagnes de Drops Actives",
        "drops_game": "Jeu",
        "drops_campaign": "Campagne",
        "drops_channels": "Chaînes",
        "btn_refresh_drops": "Actualiser",
        "btn_add_channel": "Ajouter cette chaîne",
        "btn_add_all_channels": "Ajouter toutes les chaînes",
        "btn_remove_all_channels": "Supprimer toutes les chaînes",
        "drops_loading": "Chargement des campagnes...",
        "drops_loaded": "{count} campagne(s) trouvée(s)",
        "drops_error": "Erreur lors du chargement des campagnes",
        "drops_no_channels": "Aucune chaîne disponible pour cette campagne",
        "drops_added": "Ajouté: {channel}",
        "drops_watch_minutes": "Minutes à regarder:",
        "warning": "Attention",
        "cannot_edit_active_stream": "Impossible de modifier la durée d'un stream actif. Veuillez d'abord l'arrêter.",
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
        "language_tr": "Turkish",
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
        "btn_drops": "Drops Campaigns",
        "drops_title": "Active Drop Campaigns",
        "drops_game": "Game",
        "drops_campaign": "Campaign",
        "drops_channels": "Channels",
        "btn_refresh_drops": "Refresh",
        "btn_add_channel": "Add This Channel",
        "btn_add_all_channels": "Add All Channels",
        "btn_remove_all_channels": "Remove All Channels",
        "drops_loading": "Loading campaigns...",
        "drops_loaded": "{count} campaign(s) found",
        "drops_error": "Error loading campaigns",
        "drops_no_channels": "No channels available for this campaign (or it is a Global Drop)",
        "drops_added": "Added: {channel}",
        "drops_watch_minutes": "Minutes to watch:",
        "warning": "Warning",
        "cannot_edit_active_stream": "Cannot edit the duration of an active stream. Please stop it first.",
    },
}


def _load_external_translations():
    data = {}
    for lang in ("fr", "en", "tr"):
        path = os.path.join(APP_DIR, "locales", lang, "messages.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data[lang] = json.load(f)
        except Exception:
            data[lang] = {}
    return data


def _merge_fallback(external, builtin):
    result = {}
    for lang in ("fr", "en", "tr"):
        merged = dict(builtin.get(lang, {}))
        merged.update(external.get(lang, {}))
        result[lang] = merged
    return result


# Load translations from files if present, with fallback to built-in values
TRANSLATIONS = _merge_fallback(_load_external_translations(), BUILTIN_TRANSLATIONS)


def translate(lang: str, key: str) -> str:
    return TRANSLATIONS.get(lang or "fr", TRANSLATIONS.get("fr", {})).get(key, key)


# ===============================
# Utilities / Data
# ===============================
def domain_from_url(url):
    p = urlparse(url)
    return p.netloc


def cookie_file_for_domain(domain):
    safe = domain.replace(":", "_")
    return os.path.join(COOKIES_DIR, f"{safe}.json")


def kick_is_live_by_api(url: str) -> bool:
    """Returns True if the Kick channel is live (via API).
     In case of network error, returns True to avoid blocking the queue.
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

def _find_reward_cards(driver):
    """Retourne la liste des cartes de drops dans /drops/inventory."""
    return driver.find_elements(
        By.XPATH,
        "//li[.//img[contains(@src, 'drops/reward-image')]"
        "     and .//span[@class and contains(@class,'font-semibold')]]"
    )


def _parse_reward_card(card):
    """Extrait les infos utiles d'une carte de drop."""
    # Titre
    title_el = card.find_element(
        By.XPATH,
        ".//span[@class and contains(@class,'font-semibold')]"
    )
    title = title_el.text.strip()

    # Barre de progression
    progress_ratio = None
    progress_text = None
    try:
        pb = card.find_element(By.XPATH, ".//div[@role='progressbar']")
        val_now = pb.get_attribute("aria-valuenow")
        val_text = pb.get_attribute("aria-valuetext")
        if val_now:
            try:
                progress_ratio = float(val_now)
            except ValueError:
                progress_ratio = None
        if val_text:
            progress_text = val_text.strip()
    except Exception:
        pass

    # Bloc bas (bouton ou texte)
    bottom_div = card.find_element(
        By.XPATH,
        ".//div[contains(@class,'flex') and contains(@class,'flex-col') "
        "       and contains(@class,'h-10')]"
    )

    has_claim_button = False
    raw_status_text = ""

    try:
        btn = bottom_div.find_element(
            By.XPATH,
            ".//button[contains(., 'Réclamer') or contains(., 'Claim')]"
        )
        if btn.is_displayed():
            has_claim_button = True
            raw_status_text = btn.text.strip()
    except Exception:
        has_claim_button = False

    if not has_claim_button:
        try:
            span = bottom_div.find_element(By.XPATH, ".//span")
            raw_status_text = span.text.strip()
        except Exception:
            raw_status_text = ""

    txt_lower = raw_status_text.lower()

    if has_claim_button:
        status = "ready_to_claim"
    elif "réclamé" in txt_lower or "reclamé" in txt_lower or "claimed" in txt_lower:
        status = "claimed"
    elif "%" in raw_status_text:
        status = "in_progress"
    else:
        status = "unknown"

    return {
        "title": title,
        "status": status,
        "raw_status_text": raw_status_text,
        "progress_ratio": progress_ratio,
        "progress_text": progress_text,
    }


def get_drop_info(driver, drop_title: str):

    if driver is None:
        print("[INVENTORY] driver is None, abort")
        return None

    if not drop_title:
        print("[INVENTORY] no drop_title given, abort")
        return None

    print(f"[INVENTORY] checking '{drop_title}' (DOM mode)")

    current_handle = None
    existing_handles = []

    try:
        current_handle = driver.current_window_handle
        existing_handles = driver.window_handles[:]

        # Ouvre un NOUVEL onglet pour l'inventaire
        driver.execute_script(
            "window.open('https://kick.com/drops/inventory', '_blank');"
        )
        time.sleep(1)

        # Trouver le nouvel onglet
        new_handles = driver.window_handles
        inv_handle = None
        for h in new_handles:
            if h not in existing_handles:
                inv_handle = h
                break
        if inv_handle is None and new_handles:
            inv_handle = new_handles[-1]

        if not inv_handle:
            print("[INVENTORY] no new tab handle found")
            return None

        driver.switch_to.window(inv_handle)

        # Attendre que les cartes de drops soient présentes (DOM)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//li[.//img[contains(@src, 'drops/reward-image')]]")
                )
            )
        except TimeoutException:
            print("[INVENTORY] Timeout waiting for drop cards on inventory page")
            # on essaie quand même de lire ce qu'on trouve
            pass

        cards = _find_reward_cards(driver)
        if not cards:
            print("[INVENTORY] no reward cards found in DOM")
        
        # Chercher la carte dont le titre contient drop_title
        matched_info = None
        for c in cards:
            info = _parse_reward_card(c)
            if drop_title.lower() in info["title"].lower():
                matched_info = info
                break

        if not matched_info:
            print("[INVENTORY] drop title not found in cards")
            result = {
                "status": "not_found",
                "raw_status_text": "Drop introuvable dans l'inventaire",
                "friendly_status": "",
            }
        else:
            # Construire friendly_status style "99% de 2h"
            text_for_regex = " ".join(
                t for t in [
                    matched_info.get("raw_status_text") or "",
                    matched_info.get("progress_text") or "",
                ] if t
            )

            pct = None
            # 1) Essayer de récupérer le % dans le texte
            m_pct = re.search(r"(\d+)\s*%", text_for_regex)
            if m_pct:
                try:
                    pct = int(m_pct.group(1))
                except ValueError:
                    pct = None
            # 2) Sinon utiliser progress_ratio (aria-valuenow)
            if pct is None and matched_info.get("progress_ratio") is not None:
                try:
                    pct = int(round(float(matched_info["progress_ratio"])))
                except Exception:
                    pct = None

            # Durée type "2h" / "2 h 30 min"
            m_time = re.search(
                r"(\d+\s*h(?:\s*\d+\s*(?:m|min))?)",
                text_for_regex,
                re.IGNORECASE,
            )

            friendly = ""
            if pct is not None and m_time:
                friendly = f"{pct}% de {m_time.group(1)}"
            elif pct is not None:
                friendly = f"{pct}%"
            elif matched_info["status"] in ("claimed", "ready_to_claim"):
                friendly = matched_info["status"]

            result = {
                "status": matched_info["status"],
                "raw_status_text": text_for_regex.strip()
                    or matched_info.get("raw_status_text", ""),
                "friendly_status": friendly or "",
            }

            if friendly:
                print(f"[INVENTORY] parsed friendly_status = '{friendly}'")
            else:
                print("[INVENTORY] could not parse friendly_status from DOM text.")

        # Fermer l'onglet inventaire et revenir sur le stream
        try:
            driver.close()
        except Exception:
            pass

        if current_handle in driver.window_handles:
            driver.switch_to.window(current_handle)

        return result

    except Exception as e:
        print("[INVENTORY] error:", e)
        try:
            if current_handle and current_handle in driver.window_handles:
                driver.switch_to.window(current_handle)
        except Exception:
            pass
        return None


def is_drop_really_acquired(info):
    """
    Utilitaire pour savoir si un drop est réellement acquis,
    au cas où on passe un dict avec une clé 'status'.
    """
    if not info:
        return False
    status = (info.get("status") or "").lower()
    return status in ("ready_to_claim", "claimed")



def fetch_drop_campaigns():
    """Fetches active drop campaigns from the Kick API.
     Uses undetected_chromedriver to bypass Cloudflare and handle compression.
    """
    driver = None
    try:
        api_url = "https://web.kick.com/api/v1/drops/campaigns"

        print(f"Fetching drops...")

        # ONLY for fetching campaigns: uses a small off-screen window
        # (headless is detected by Kick, so we use a real window but hidden)
        # Note: StreamWorkers use their own user-configured parameters
        driver = make_chrome_driver(
            headless=False, visible_width=400, visible_height=300, profile_name="chrome_campaigns", 
        )

        # Position the window off-screen to make it invisible
        try:
            driver.set_window_position(-2000, -2000)
        except:
            pass
        
        # Visit kick.com and load cookies
        print("Establishing Session on kick.com...")
        driver.get("https://kick.com")
        time.sleep(1)

        # Load saved cookies
        cookie_path = cookie_file_for_domain("kick.com")
        if os.path.exists(cookie_path):
            print("Loading saved cookies...")
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            for cookie in cookies:
                try:
                    if "expiry" in cookie and cookie["expiry"] is None:
                        del cookie["expiry"]
                    driver.add_cookie(cookie)
                except:
                    pass
            driver.refresh()
            time.sleep(1)

        # Use JavaScript to make the fetch request from the page context
        print(f"Fetching Drops from API...")
        #print(f"Fetching API data via JavaScript: {api_url}")

        fetch_script = f"""
        return fetch('{api_url}', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/json',
            }},
            credentials: 'include'
        }})
        .then(response => response.text())
        .then(data => data)
        .catch(error => JSON.stringify({{error: error.toString()}}));
        """

        # Execute the script and get the result
        page_text = driver.execute_script(fetch_script)

        #print(f"Response (first 200 chars): {page_text[:200]}")

        # Check if blocked
        if "blocked by security policy" in page_text.lower():
            print(f"Request blocked! Response: {page_text}")
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            return {"campaigns": [], "driver": None}

        # Parse le JSON
        response = json.loads(page_text)
        print(f"Successfully fetched campaign data!")
        print(f"We have found {len(response.get('data', []))} campaigns")

        # Return data AND driver (to load images)
        campaigns = []
        data = response.get("data", [])

        if isinstance(data, list):
            for campaign in data:
                # Extract relevant information
                category = campaign.get("category", {})
                campaign_info = {
                    "id": campaign.get("id"),
                    "name": campaign.get("name", "Unknown Campaign"),
                    "game": category.get("name", "Unknown Game"),
                    "game_slug": category.get("slug", ""),
                    "game_image": category.get("image_url", ""),
                    "status": campaign.get("status", "unknown"),
                    "starts_at": campaign.get("starts_at"),
                    "ends_at": campaign.get("ends_at"),
                    "rewards": campaign.get("rewards", []),
                    "channels": [],
                }

                # Get participating channels
                channels = campaign.get("channels", [])
                for channel in channels:
                    if isinstance(channel, dict):
                        slug = channel.get("slug")
                        user = channel.get("user", {})
                        username = user.get("username") or slug
                        if slug:
                            campaign_info["channels"].append(
                                {
                                    "slug": slug,
                                    "username": username,
                                    "url": f"https://kick.com/{slug}",
                                    "profile_picture": user.get("profile_picture", ""),
                                }
                            )

                # Only add campaigns with at least one channel
                if campaign_info["channels"] or campaign.get("status") == "active":
                    campaigns.append(campaign_info)

        # Retourne les campagnes ET le driver
        return {"campaigns": campaigns, "driver": driver}
    except Exception as e:
        print(f"Error fetching drop campaigns: {e}")
        import traceback

        traceback.print_exc()
        # On error, close driver and return empty
        if driver:
            try:
                driver.quit()
            except:
                pass
        return {"campaigns": [], "driver": None}


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
            # Fix certain fields that cause problems
            if "expiry" in c and c["expiry"] is None:
                del c["expiry"]
            try:
                driver.add_cookie(c)
            except Exception:
                pass
        return True

    @staticmethod
    def import_from_browser(domain: str) -> bool:
        """Attempts to import existing cookies from browsers (Chrome/Edge/Firefox)
        using browser_cookie3. Returns True if a file was written.
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
    profile_name="chrome_data",   # <--- nouveau paramètre
):
    opts = uc.ChromeOptions()  # Use undetected-chromedriver options

    # Headless configuration (adapted for uc)
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
    opts.add_argument("--log-level=3")
    opts.add_argument("--silent")

    # >>> profil séparé selon profile_name
    user_data_dir = os.path.join(DATA_DIR, profile_name)
    os.makedirs(user_data_dir, exist_ok=True)
    opts.add_argument(f"--user-data-dir={user_data_dir}")

    # Extension loading (compatible with uc)
    if extension_path:
        try:
            if extension_path.lower().endswith(".crx"):
                opts.add_extension(extension_path)
            else:
                opts.add_argument(f"--load-extension={extension_path}")
        except Exception:
            pass

    driver = uc.Chrome(
        options=opts,
        version_main=0,   # évite le message "could not detect version_main..."
    )
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
        drop_title="",    
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
        # --- suivi drop ---
        self.drop_title = drop_title or ""
        self.drop_info = None
        self._last_inventory_check = 0.0
        self._inventory_check_interval = 600  # check inventaire toutes les 10 min

    def run(self):
        domain = domain_from_url(self.url)
        try:
            # If loading a .crx, Chrome cannot be headless
            use_headless = bool(self.hide_player)
            # If mini_player enabled, force visible to show the small window
            if self.mini_player:
                use_headless = False
            # If hide_player enabled, force headless to hide the entire window (unless mini_player has priority)
            if self.extension_path and self.extension_path.endswith(".crx"):
                use_headless = False

            self.driver = make_chrome_driver(
                headless=use_headless,
                driver_path=self.driver_path,
                extension_path=self.extension_path,
                profile_name="chrome_streams",
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
                if (
                    self.minutes_target
                    and self.elapsed_seconds >= self.minutes_target * 60
                ):
                    self.completed = True
                    break

                # --- suivi inventaire Kick pour un drop précis ---
                now = time.time()
                if self.drop_title and now - self._last_inventory_check >= self._inventory_check_interval:
                    self._last_inventory_check = now
                    try:
                        info = get_drop_info(self.driver, self.drop_title)
                        self.drop_info = info
                        if info:
                            status = (info.get("status") or "").lower()
                            if status in ("ready_to_claim", "claimed"):
                                print(f"[WORKER] Drop '{self.drop_title}' status={status} -> stop worker.")
                                self.completed = True
                                break
                    except Exception as inv_e:
                        print("[INVENTORY] error:", inv_e)

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
            # Combine API + fallback DOM
            if kick_is_live_by_api(self.url):
                self._last_live_value = True
                return True
            body = self.driver.find_element(By.TAG_NAME, "body").text
            self._last_live_value = "LIVE" in body.upper()
            return self._last_live_value
        except Exception:
            self._last_live_value = False
            return False
        finally:
            # Add slight jitter to desync multiple workers
            jitter = random.uniform(-5, 5)
            self._live_check_interval = max(10, 30 + jitter)
            self._last_live_check = now

    def ensure_player_state(self):
        try:
            hide = "true" if self.hide_player else "false"
            muted = "true" if self.mute else "false"
            volume = "0" if self.mute else "1"
            mini = "true" if (not self.hide_player and self.mini_player) else "false"
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
        self.dark_mode = True  # Dark by default
        self.language = "fr"  # fr or en
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

    def add(self, url, minutes, drop_title=""):
        self.items.append({
            "url": url,
            "minutes": minutes,
            "drop_title": drop_title or "",
        })
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
        self.geometry("1000x750")
        self.minsize(900, 700)

        self.config_data = Config()
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
        # Properly close all browsers when closing the app
        try:
            self.protocol("WM_DELETE_WINDOW", self.on_close)
        except Exception:
            pass

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
            command=self.remove_selected,
            width=180,
        )
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

        # Fichiers
        btn_chromedriver = ctk.CTkButton(
            self.sidebar,
            text=self.t("btn_chromedriver"),
            command=self.choose_chromedriver,
            width=180,
        )
        btn_chromedriver.grid(row=7, column=0, padx=14, pady=(18, 6), sticky="w")

        btn_extension = ctk.CTkButton(
            self.sidebar,
            text=self.t("btn_extension"),
            command=self.choose_extension,
            width=180,
        )
        btn_extension.grid(row=8, column=0, padx=14, pady=6, sticky="w")

        # Toggles
        self.mute_var = tk.BooleanVar(value=bool(self.config_data.mute))
        self.hide_player_var = tk.BooleanVar(value=bool(self.config_data.hide_player))
        self.mini_player_var = tk.BooleanVar(value=bool(self.config_data.mini_player))

        sw_mute = ctk.CTkSwitch(
            self.sidebar,
            text=self.t("switch_mute"),
            command=self.on_toggle_mute,
            variable=self.mute_var,
        )
        sw_mute.grid(row=9, column=0, padx=14, pady=(18, 6), sticky="w")

        sw_hide = ctk.CTkSwitch(
            self.sidebar,
            text=self.t("switch_hide"),
            command=self.on_toggle_hide,
            variable=self.hide_player_var,
        )
        sw_hide.grid(row=10, column=0, padx=14, pady=6, sticky="w")

        sw_mini = ctk.CTkSwitch(
            self.sidebar,
            text=self.t("switch_mini"),
            command=self.on_toggle_mini,
            variable=self.mini_player_var,
        )
        sw_mini.grid(row=11, column=0, padx=14, pady=6, sticky="w")

        # Thème
        self.theme_var = tk.StringVar(
            value=self.t("theme_dark")
            if self.config_data.dark_mode
            else self.t("theme_light")
        )
        theme_label = ctk.CTkLabel(self.sidebar, text=self.t("label_theme"))
        theme_label.grid(row=12, column=0, padx=14, pady=(18, 4), sticky="w")
        theme_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=[self.t("theme_dark"), self.t("theme_light")],
            command=self.change_theme,
            variable=self.theme_var,
            width=180,
        )
        theme_menu.grid(row=13, column=0, padx=14, pady=(0, 14), sticky="w")

        # Language (only FR/EN in dropdown for now)
        self.lang_var = tk.StringVar(
            value=self.t("language_fr")
            if self.config_data.language == "fr"
            else self.t("language_en")
        )
        lang_label = ctk.CTkLabel(self.sidebar, text=self.t("label_language"))
        lang_label.grid(row=14, column=0, padx=14, pady=(4, 4), sticky="w")
        lang_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=[self.t("language_fr"), self.t("language_en")],
            command=self.change_language,
            variable=self.lang_var,
            width=180,
        )
        lang_menu.grid(row=15, column=0, padx=14, pady=(0, 14), sticky="w")

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
            columns=("url", "minutes", "elapsed", "drop"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("url", text="URL")
        self.tree.heading("minutes", text=self.t("col_minutes"))
        self.tree.heading("elapsed", text=self.t("col_elapsed"))
        self.tree.heading("drop", text="Drop")

        self.tree.column("url", width=300, minwidth=250, anchor="w", stretch=True)
        self.tree.column("minutes", width=100, minwidth=70, anchor="center", stretch=False)
        self.tree.column("elapsed", width=100, minwidth=90, anchor="center", stretch=False)
        self.tree.column("drop", width=200, minwidth=200, anchor="w", stretch=False)
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
        # Map the choice to fr/en
        new_lang = "fr" if "français" in choice.lower() else "en"
        
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
            if self.status_var.get() in (
                translate("fr", "status_ready"),
                translate("en", "status_ready"),
            ):
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

            # Texte pour la colonne Drop
            drop_title = item.get("drop_title", "") or ""
            drop_state = ""
            if i in self.workers:
                worker = self.workers[i]
                info = getattr(worker, "drop_info", None)
                if info:
                    drop_state = (
                        info.get("friendly_status")
                        or info.get("raw_status_text")
                        or info.get("status", "")
                    )

            if drop_title or drop_state:
                drop_text = drop_title if not drop_state else f"{drop_title} ({drop_state})"
            else:
                drop_text = ""

            tags = ["odd" if i % 2 else "even"]
            if item.get("finished"):
                tags.append("finished")

            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(item["url"], item["minutes"], f"{elapsed}s", drop_text),
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

        drop_title = simpledialog.askstring(
            "Drop title",
            "Nom (ou une partie) du drop à surveiller\n"
            "(ex: 'KICK Hazmat' ; laisse vide si aucun suivi spécifique) :"
        )
        if not drop_title:
            drop_title = ""

        self.config_data.add(url, minutes or 0, drop_title)
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
        item = self.config_data.items[idx]
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
            # First try to automatically import from browser
            try:
                if CookieManager.import_from_browser(domain):
                    self.status_var.set(self.t("cookies_saved_for", domain=domain))
                else:
                    if messagebox.askyesno(
                        self.t("cookies_missing_title"), self.t("cookies_missing_msg")
                    ):
                        self.obtain_cookies_interactively(item["url"], domain)
            except Exception:
                if messagebox.askyesno(
                    self.t("cookies_missing_title"), self.t("cookies_missing_msg")
                ):
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
            drop_title=item.get("drop_title", ""),
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
                profile_name="chrome_cookies", 
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

        # Header with refresh button - larger and more visible
        header_frame = ctk.CTkFrame(main_frame, fg_color=("gray86", "gray17"), corner_radius=0, height=60)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)

        status_label = ctk.CTkLabel(
            header_frame, text=self.t("drops_loading"), 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        status_label.grid(row=0, column=0, sticky="w", padx=20, pady=15)

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

        # Frame scrollable pour les campagnes
        scrollable_frame = ctk.CTkScrollableFrame(
            main_frame, 
            label_text="",
            fg_color=("gray92", "gray14")
        )
        scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=15)
        scrollable_frame.grid_columnconfigure(0, weight=1)

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
        """Refreshes the list of drop campaigns"""

        # Clean the frame
        def clear_frame():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            status_label.configure(text=self.t("drops_loading"))

        self.after(0, clear_frame)

        # Get campaigns (with driver)
        result = fetch_drop_campaigns()
        campaigns = result.get("campaigns", [])
        driver = result.get("driver")

        def display_campaigns():
            try:
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

                # Group campaigns by game
                games = {}
                for campaign in campaigns:
                    game_name = campaign["game"]
                    if game_name not in games:
                        games[game_name] = {
                            "image": campaign.get("game_image", ""),
                            "campaigns": [],
                        }
                    games[game_name]["campaigns"].append(campaign)

                status_label.configure(
                    text=self.t("drops_loaded", count=len(campaigns))
                )

                # Display each game with its campaigns
                row_idx = 0
                for game_name, game_data in games.items():
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

                    # Display each campaign of the game
                    for camp_idx, campaign in enumerate(game_data["campaigns"]):
                        campaign_frame = ctk.CTkFrame(
                            campaigns_container,
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

                        status_badge = ctk.CTkLabel(
                            header,
                            text=campaign["status"].upper(),
                            font=ctk.CTkFont(size=10, weight="bold"),
                            fg_color=("#10b981", "#059669")
                            if campaign["status"] == "active"
                            else ("#6b7280", "#4b5563"),
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
                                            tooltip_text = f"{reward_name}\n⏱️ {required_mins} minutes"

                                            # Frame with border for each reward
                                            rew_container = ctk.CTkFrame(
                                                images_frame,
                                                fg_color=("white", "#0f172a"),
                                                border_width=2,
                                                border_color=("#d1d5db", "#374151"),
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
                            no_channels_label = ctk.CTkLabel(
                                channels_frame,
                                text=self.t("drops_no_channels"),
                                text_color=("#6b7280", "#9ca3af"),
                                font=ctk.CTkFont(size=11, slant="italic"),
                            )
                            no_channels_label.grid(row=0, column=0, sticky="w", pady=5)
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
                                def toggle_channel(url=channel_url, btn=action_btn, label=ch_label, username=channel['username']):
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
                                        self._add_drop_channel(url)
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
                                        for ch in c["channels"]:
                                            if not self._is_channel_in_list(ch['url']):
                                                self._add_drop_channel(ch['url'])
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
                                            self._add_drop_channel(url)
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

                    row_idx += 1
                
                # Force update
                scrollable_frame.update_idletasks()
            except Exception as e:
                status_label.configure(text=f"Error: {str(e)}")
            finally:
                # Close driver after displaying all campaigns
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass

        # Call on UI thread
        self.after(0, display_campaigns)

    def _is_channel_in_list(self, url):
        """Check if a URL is already in the list"""
        return any(item["url"] == url for item in self.config_data.items)
    
    def _find_channel_index(self, url):
        """Find the index of a URL in the list"""
        for idx, item in enumerate(self.config_data.items):
            if item["url"] == url:
                return idx
        return None

    def _add_drop_channel(self, url, minutes=120):
        """Add a drop channel to the queue"""
        try:
            self.config_data.add(url, minutes)
            self.refresh_list()
            self.status_var.set(self.t("drops_added", channel=url.split("/")[-1]))
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
        """Add all channels from a campaign"""
        count = 0
        for channel in campaign["channels"]:
            try:
                self.config_data.add(channel["url"], 120)  # 120 minutes by default
                count += 1
            except Exception as e:
                print(f"Error adding channel {channel['username']}: {e}")

        self.refresh_list()
        self.status_var.set(f"Added {count} channel(s) from {campaign['name']}")

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

    # ----------- Callbacks Worker -----------
    def on_worker_update(self, idx, seconds, live):
        def ui_update():
            # Ligne existante
            if str(idx) in self.tree.get_children():
                values = list(self.tree.item(str(idx), "values"))

                # S'assurer qu'on a bien 4 colonnes
                if len(values) < 4:
                    values += [""] * (4 - len(values))

                # Colonne Écoulé
                tag = self.t("tag_live") if live else self.t("tag_paused")
                values[2] = f"{seconds}s ({tag})"

                # Colonne Drop
                try:
                    item = self.config_data.items[idx]
                except IndexError:
                    item = {}

                drop_title = item.get("drop_title", "") or ""
                drop_state = ""
                w = self.workers.get(idx)
                if w is not None:
                    info = getattr(w, "drop_info", None)
                    if info:
                        drop_state = (
                            info.get("friendly_status")
                            or info.get("raw_status_text")
                            or info.get("status", "")
                        )

                if drop_title or drop_state:
                    drop_text = drop_title if not drop_state else f"{drop_title} ({drop_state})"
                else:
                    drop_text = ""
                values[3] = drop_text

                self.tree.item(str(idx), values=values)

                current_tags = set(self.tree.item(str(idx), "tags") or [])
                if live:
                    current_tags.discard("paused")
                else:
                    current_tags.add("paused")
                self.tree.item(str(idx), tags=tuple(current_tags))

            # Update status bar with elapsed tim
            if idx < len(self.config_data.items):
                item = self.config_data.items[idx]
                minutes = seconds // 60
                secs = seconds % 60
                time_str = f"{minutes}m {secs}s" if minutes > 0 else f"{secs}s"
                status = self.t("tag_live") if live else self.t("tag_paused")

                if self.queue_running and self.queue_current_idx == idx:
                    self.status_var.set(
                        f"{self.t('queue_running_status', url=item['url'])} - {time_str} ({status})"
                    )
                else:
                    self.status_var.set(
                        f"{self.t('status_playing', url=item['url'])} - {time_str} ({status})"
                    )

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
                    current_tags = set(self.tree.item(str(idx), "tags") or [])
                    current_tags.add("finished")
                    current_tags.discard("paused")
                    current_tags.discard("redo")
                    self.tree.item(str(idx), values=values, tags=tuple(current_tags))

            # Continue queue if applicable
            if getattr(self, "queue_running", False) and self.queue_current_idx == idx:
                self._run_queue_from(idx + 1)

        self.after(0, ui_finish)


# ===============================
# Main
# ===============================
if __name__ == "__main__":
    app = App()
    app.mainloop()
