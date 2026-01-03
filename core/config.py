"""Configuration management for KickDropsMiner"""
import json
import os
from utils.helpers import CONFIG_FILE


class Config:
    """Manages application configuration and queue items"""
    
    def __init__(self):
        self.items = []
        self.chromedriver_path = None
        self.extension_path = None
        self.mute = True
        self.hide_player = False
        self.mini_player = False
        self.force_160p = False
        self.dark_mode = True  # Dark by default
        self.language = "fr"  # default language code
        self.auto_start = False  # Auto-start queue on launch
        self.debug = False  # Debug messages disabled by default
        self.load()

    def load(self):
        """Load configuration from file"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.items = data.get("items", [])
            # Migrate old items format to new format with campaign info
            for item in self.items:
                if "campaign_id" not in item:
                    item["campaign_id"] = None
                if "campaign_channels" not in item:
                    item["campaign_channels"] = []
                if "required_category_id" not in item:
                    item["required_category_id"] = None
                if "is_global_drop" not in item:
                    item["is_global_drop"] = False
                if "cumulative_time" not in item:
                    item["cumulative_time"] = 0
                # Add tried_channels tracking to prevent switching loops
                if "tried_channels" not in item:
                    item["tried_channels"] = []
            self.chromedriver_path = data.get("chromedriver_path")
            self.extension_path = data.get("extension_path")
            self.mute = data.get("mute", True)
            self.hide_player = data.get("hide_player", False)
            self.mini_player = data.get("mini_player", False)
            self.force_160p = data.get("force_160p", False)
            self.dark_mode = data.get("dark_mode", True)
            self.language = data.get("language", "fr")
            self.auto_start = data.get("auto_start", False)
            self.debug = data.get("debug", False)
        else:
            self.items = []

    def save(self):
        """Save configuration to file"""
        data = {
            "items": self.items,
            "chromedriver_path": self.chromedriver_path,
            "extension_path": self.extension_path,
            "mute": self.mute,
            "hide_player": self.hide_player,
            "mini_player": self.mini_player,
            "force_160p": self.force_160p,
            "dark_mode": self.dark_mode,
            "language": self.language,
            "auto_start": self.auto_start,
            "debug": self.debug,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add(self, url, minutes, campaign_id=None, campaign_channels=None, required_category_id=None, is_global_drop=False):
        """Add item with optional campaign grouping"""
        item = {
            "url": url,
            "minutes": minutes,
            "campaign_id": campaign_id,
            "campaign_channels": campaign_channels or [],
            "required_category_id": required_category_id,
            "is_global_drop": is_global_drop,
            "cumulative_time": 0,  # Track cumulative time across all streamers in campaign
        }
        self.items.append(item)
        self.save()

    def remove(self, idx):
        """Remove item at index"""
        del self.items[idx]
        self.save()

