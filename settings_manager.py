"""
settings_manager.py — завантаження та збереження налаштувань застосунку.
"""
import os
import json


SETTINGS_PATH = r"scripts\settings.json"

DEFAULT_TAB_SETTINGS = {
    "selected_symbol": "HYPERUSDT",
    "funding_interval_hours": 1.0,
    "reverse_side": False,
    "entry_time_seconds": 5.0,
    "qty": 45.0,
    "profit_percentage": 1.0,
    "leverage": 1.0,
    "exchange": "Bybit",
    "testnet": False,
    "auto_limit": False,
    "stop_loss_percentage": 0.5,
    "stop_loss_enabled": True,
    "auto_mode": False,
    "auto_min_funding": 0.05,
}


def load_language(settings_path: str = SETTINGS_PATH) -> str:
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
                return settings.get("language", "en")
        except Exception as e:
            print(f"Error loading language: {e}")
    return "en"


def load_settings(settings_path: str = SETTINGS_PATH) -> list[dict]:
    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                settings = json.load(f)
                tabs = settings.get("tabs", [DEFAULT_TAB_SETTINGS.copy()])
                for tab in tabs:
                    tab.setdefault("reverse_side", False)
                return tabs
        return [DEFAULT_TAB_SETTINGS.copy()]
    except Exception as e:
        print(f"Error loading settings: {e}")
        return [DEFAULT_TAB_SETTINGS.copy()]


def save_settings(tab_data_list: list[dict], language: str, settings_path: str = SETTINGS_PATH):
    tabs = [
        {
            "selected_symbol": td["selected_symbol"],
            "reverse_side": td["reverse_side"],
            "funding_interval_hours": td["funding_interval_hours"],
            "entry_time_seconds": td["entry_time_seconds"],
            "qty": td["qty"],
            "profit_percentage": td["profit_percentage"],
            "leverage": td["leverage"],
            "exchange": td["exchange"],
            "testnet": td["testnet"],
            "auto_limit": td["auto_limit"],
            "stop_loss_percentage": td["stop_loss_percentage"],
            "stop_loss_enabled": td["stop_loss_enabled"],
            "auto_mode": td.get("auto_mode", False),
            "auto_min_funding": td.get("auto_min_funding", 0.05),
        }
        for td in tab_data_list
    ]
    data = {"tabs": tabs, "language": language}
    try:
        with open(settings_path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")