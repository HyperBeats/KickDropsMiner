"""Helper utility functions"""
import os
import sys
import shutil
from urllib.parse import urlparse

# Global debug config reference (set when App initializes)
_DEBUG_CONFIG = None

def set_debug_config(config):
    """Set the global debug config reference"""
    global _DEBUG_CONFIG
    _DEBUG_CONFIG = config

def debug_print(*args, **kwargs):
    """Print debug messages only if debug mode is enabled"""
    if _DEBUG_CONFIG and _DEBUG_CONFIG.debug:
        print(*args, **kwargs)


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


# Initialize paths
APP_DIR = _resolve_app_dir()
DATA_DIR = _resolve_data_dir(APP_DIR)
_migrate_portable_data(APP_DIR, DATA_DIR)
COOKIES_DIR = os.path.join(DATA_DIR, "cookies")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
CHROME_DATA_DIR = os.path.join(DATA_DIR, "chrome_data")

os.makedirs(COOKIES_DIR, exist_ok=True)
os.makedirs(CHROME_DATA_DIR, exist_ok=True)


def domain_from_url(url):
    """Extract domain from URL"""
    p = urlparse(url)
    return p.netloc


def cookie_file_for_domain(domain):
    """Get cookie file path for a domain"""
    safe = domain.replace(":", "_")
    return os.path.join(COOKIES_DIR, f"{safe}.json")


def _kick_username_from_url(url: str):
    """Extract Kick username from URL"""
    try:
        p = urlparse(url)
        if "kick.com" not in p.netloc:
            return None
        username = p.path.strip("/").split("/")[0]
        return username or None
    except Exception:
        return None

