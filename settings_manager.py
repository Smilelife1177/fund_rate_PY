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
    "auto_profit_addon": 0.3,
    "auto_balance_pct": 30.0,
    "auto_leverage_calc": 10.0,
}


def load_language(settings_path: str = SETTINGS_PATH) -> str:
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
                return settings.get("language", "en")
        except Exception as e:
            print(f"Error loading language: {e}")
    return "en"


def load_settings(settings_path: str = SETTINGS_PATH) -> list[dict]:
    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
                tabs = settings.get("tabs", [DEFAULT_TAB_SETTINGS.copy()])
                
                for tab in tabs:
                    # Заповнюємо нові поля, якщо їх немає в старому файлі
                    tab.setdefault("auto_profit_addon", 0.3)
                    tab.setdefault("auto_balance_pct", 30.0)
                    tab.setdefault("auto_leverage_calc", 10.0)
                    tab.setdefault("reverse_side", False)
                    tab.setdefault("auto_mode", False)
                    tab.setdefault("auto_min_funding", 0.05)
                
                return tabs
        return [DEFAULT_TAB_SETTINGS.copy()]
    except Exception as e:
        print(f"Error loading settings: {e}")
        return [DEFAULT_TAB_SETTINGS.copy()]


def save_settings(tab_data_list: list[dict], language: str, settings_path: str = SETTINGS_PATH):
    """Зберігає всі налаштування, включаючи Auto Calculation."""
    tabs = []
    for td in tab_data_list:
        tab_dict = {
            "selected_symbol": td["selected_symbol"],
            "reverse_side": td.get("reverse_side", False),
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

            # === Зберігаємо Auto Calculation ===
            "auto_profit_addon": td.get("auto_profit_addon", 0.3),
            "auto_balance_pct": td.get("auto_balance_pct", 30.0),
            "auto_leverage_calc": td.get("auto_leverage_calc", 10.0),
        }
        tabs.append(tab_dict)

    data = {"tabs": tabs, "language": language}

    try:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"Settings saved successfully to {settings_path}")
    except Exception as e:
        print(f"Error saving settings: {e}")