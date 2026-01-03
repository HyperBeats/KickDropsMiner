"""Translation system for KickDropsMiner"""
import json
import os
import sys

# Import helpers to get APP_DIR and DATA_DIR
from .helpers import APP_DIR, DATA_DIR

# Keep the fallback translations as a JSON blob to avoid emitting hundreds of
# individual LOAD_CONST entries (PyInstaller trips over those on Python 3.10).
_BUILTIN_TRANSLATIONS_JSON = r'''
{
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
    "switch_force_160p": "Forcer 160p",
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
    "drops_tab_campaigns": "Campagnes",
    "drops_tab_progress": "Ma progression",
    "drops_progress_loading": "Chargement de la progression...",
    "drops_progress_error": "Erreur lors du chargement",
    "drops_progress_no_data": "Aucune donnée de progression disponible",
    "drops_progress_loaded": "{total} campagne(s) chargée(s) ({active} active(s))",
    "drops_progress_in_progress": "En cours",
    "drops_progress_claimed": "Réclamés",
    "btn_refresh_progress": "Actualiser la progression",
    "drops_completed_campaigns": "Campagnes terminées"
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
    "switch_force_160p": "Force 160p",
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
    "drops_tab_campaigns": "Campaigns",
    "drops_tab_progress": "My Progress",
    "drops_progress_loading": "Loading progress...",
    "drops_progress_error": "Error loading progress",
    "drops_progress_no_data": "No progress data available",
    "drops_progress_loaded": "Loaded {total} campaigns ({active} active)",
    "drops_progress_in_progress": "In Progress",
    "drops_progress_claimed": "Claimed",
    "btn_refresh_progress": "Refresh Progress",
    "drops_completed_campaigns": "Completed Campaigns"
  }
}
'''
BUILTIN_TRANSLATIONS = json.loads(_BUILTIN_TRANSLATIONS_JSON)


def _load_external_translations():
    """Load translations from external files"""
    data = {}
    candidate_roots = []
    # Bundled resources (PyInstaller onefile: _MEIPASS)
    candidate_roots.append(os.path.join(APP_DIR, "locales"))
    # Folder next to the executable (useful when shipping a locales/ dir alongside the EXE)
    candidate_roots.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "locales"))
    # Workspace/data directory (allows portable overrides)
    candidate_roots.append(os.path.join(DATA_DIR, "locales"))

    for locales_dir in candidate_roots:
        try:
            for entry in os.scandir(locales_dir):
                if not entry.is_dir():
                    continue
                lang = entry.name
                path = os.path.join(entry.path, "messages.json")
                if not os.path.isfile(path):
                    continue
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data[lang] = json.load(f)
                except Exception:
                    # Ignore malformed translation files so the app can still start
                    pass
        except FileNotFoundError:
            continue
    return data


def _merge_fallback(external, builtin):
    """Merge external translations with builtin fallbacks"""
    result = {}
    languages = set(builtin.keys()) | set(external.keys())
    for lang in sorted(languages):
        merged = dict(builtin.get(lang, {}))
        merged.update(external.get(lang, {}))
        result[lang] = merged
    return result


# Load translations from files if present, with fallback to built-in values
TRANSLATIONS = _merge_fallback(_load_external_translations(), BUILTIN_TRANSLATIONS)


def translate(lang: str, key: str) -> str:
    """Translate a key for a given language"""
    return TRANSLATIONS.get(lang or "fr", TRANSLATIONS.get("fr", {})).get(key, key)

