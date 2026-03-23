"""
auto_scanner.py — логіка авто-сканування монет за фандинг-ставкою.
"""
from datetime import datetime, timezone
import requests


def fetch_bybit_tickers(timeout: int = 8) -> list[dict] | None:
    """Отримує список тикерів лінійних контрактів з Bybit API."""
    try:
        resp = requests.get(
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "linear"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            return None
        return data["result"]["list"]
    except Exception as e:
        print(f"fetch_bybit_tickers error: {e}")
        return None


def scan_funding_opportunities(
    threshold_pct: float,
    near_window_secs: float = 60.0,
) -> tuple[list[dict], list[dict]]:
    """
    Сканує USDT-перп монети.

    Повертає:
        all_above  — всі монети де |rate| >= threshold_pct, відсортовані за |rate| DESC
        near_now   — з all_above тільки ті де до фандингу <= near_window_secs сек
    """
    tickers = fetch_bybit_tickers()
    if tickers is None:
        return [], []

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    all_above: list[dict] = []
    near_now: list[dict] = []

    for item in tickers:
        symbol = item.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        try:
            rate = float(item.get("fundingRate") or 0)
            next_ft_ms = int(item.get("nextFundingTime") or 0)
        except (ValueError, TypeError):
            continue

        if next_ft_ms == 0:
            continue

        rate_pct = rate * 100
        if abs(rate_pct) < threshold_pct:
            continue

        secs_to_funding = (next_ft_ms - now_ms) / 1000.0
        entry = {"symbol": symbol, "rate": rate_pct, "secs": secs_to_funding}
        all_above.append(entry)

        if 0 <= secs_to_funding <= near_window_secs:
            near_now.append(entry)

    all_above.sort(key=lambda x: abs(x["rate"]), reverse=True)
    near_now.sort(key=lambda x: abs(x["rate"]), reverse=True)
    return all_above, near_now


def format_funding_time(secs: float, language: str = "en") -> str:
    """Конвертує секунди в читабельний рядок (мова: 'en' або 'uk')."""
    uk = language == "uk"
    if secs < 1:
        return "скоро" if uk else "soon"
    total = int(secs)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}{'г' if uk else 'h'} {m:02d}{'хв' if uk else 'm'} {s:02d}{'с' if uk else 's'}"
    if m > 0:
        return f"{m}{'хв' if uk else 'm'} {s:02d}{'с' if uk else 's'}"
    return f"{s}{'с' if uk else 's'}"