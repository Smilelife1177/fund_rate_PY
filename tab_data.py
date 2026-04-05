"""
tab_data.py — ініціалізація стану вкладки (tab_data dict).
"""
from logic import initialize_client


DEFAULT_TAB_STATE = {
    "selected_symbol": "HYPERUSDT",
    "position_open": False,
    "reverse_side": False,
    "update_count": 0,
    "funding_interval_hours": 1.0,
    "entry_time_seconds": 5.0,
    "qty": 45.0,
    "profit_percentage": 1.0,
    "leverage": 1.0,
    "exchange": "Bybit",
    "testnet": False,
    "auto_limit": False,
    "stop_loss_percentage": 0.5,
    "stop_loss_enabled": True,
    "funding_data": None,
    "open_order_id": None,
    "funding_time_price": None,
    "limit_price": None,
    "pre_funding_price": None,
    "auto_mode": False,
    "auto_min_funding": 0.05,
    "auto_scan_done_this_minute": False,
    "auto_scan_results": [],
    "auto_selected_symbol": None,
    "auto_profit_addon": 0.3,
    "auto_balance_pct": 30.0,
    "auto_leverage_calc": 10.0,
    "order_placed_this_cycle": False,
}


def build_tab_data(settings: dict, session=None, testnet=None, exchange=None) -> dict:
    """
    Повертає словник стану нової вкладки.
    Пріоритет: явні аргументи > settings > DEFAULT_TAB_STATE.
    """
    state = DEFAULT_TAB_STATE.copy()
    state.update(settings)

    # Явні аргументи перезаписують settings
    if exchange is not None:
        state["exchange"] = exchange
    if testnet is not None:
        state["testnet"] = testnet

    # Дефолтний інтервал фандингу залежить від біржі
    if "funding_interval_hours" not in settings:
        state["funding_interval_hours"] = 1.0 if state["exchange"] == "Bybit" else 8.0

    state["session"] = session or initialize_client(state["exchange"], state["testnet"])
    return state