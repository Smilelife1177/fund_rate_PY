"""
stats_manager.py — робота зі статистикою угод (CSV).
"""
import os
import re
import csv
from datetime import datetime


STATS_CSV_FILE = "trade_stats.csv"
STATS_HEADERS = ["Дата_Час", "Процент", "Фандинг", "%_Фандингу", "Прибиль", "Доход", "Комисия", "Обєм", "В-сделке", "Тикер", "openFee", "closeFee", "totalCommission", "pricePnL", "fundingMethod", "durationSec"]


def initialize_stats_csv(filepath: str = STATS_CSV_FILE):
    """Створює файл статистики, якщо його ще немає."""
    if not os.path.exists(filepath):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(STATS_HEADERS)


def parse_stats_input(raw: str) -> list[str] | None:
    """
    Розбирає рядок з даними угоди.
    Повертає список із 8 значень або None при помилці.
    """
    cleaned = re.sub(r"\s*\$\s*", " ", raw)
    values = [v.strip() for v in re.split(r"\s+", cleaned.strip()) if v.strip()]
    if len(values) != 8:
        return None
    return values


def write_stats_row(values: list[str], filepath: str = STATS_CSV_FILE):
    """
    Записує рядок угоди в CSV.
    values: [Процент, Фандинг, Прибиль, Доход, Комисия, Обєм, В-сделке, Тикер] (8 значень)
    """
    try:
        # values[1] is Фандинг, values[5] is Обєм
        funding = float(values[1].replace(',', '.').replace('—', '0'))
        volume = float(values[5].replace(',', '.'))
        if volume != 0:
            funding_pct = (funding / volume) * 100
            funding_pct_str = f"{funding_pct:.4f}%"
        else:
            funding_pct_str = "0.0000%"
    except Exception:
        funding_pct_str = "0.0000%"

    # Вставляємо %_Фандингу після Фандинг (індекс 1 у вхідному списку values)
    new_values = values[:2] + [funding_pct_str] + values[2:]

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        writer.writerow([current_time] + new_values)


def read_stats_csv(filepath: str = STATS_CSV_FILE) -> list[list[str]]:
    """Повертає всі рядки CSV (включаючи заголовок) або порожній список."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.reader(f))


def write_imported_trades(trades: list[dict], filepath: str = STATS_CSV_FILE) -> int:
    """
    Записує імпортовані угоди в CSV з розширеними полями.
    """
    existing = read_stats_csv(filepath)
    existing_keys = set()
    for row in existing[1:]:
        if len(row) >= 10: # Було 9, стало 10 (до Тикер)
            existing_keys.add((row[0], row[9]))  # Дата_Час + Тикер

    written = 0
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for t in trades:
            key = (t["datetime"], t["symbol"])
            if key in existing_keys:
                continue

            funding = t["funding"]
            volume = t["volume"]
            if volume != 0:
                funding_pct = (funding / volume) * 100
                funding_pct_str = f"{funding_pct:.4f}%"
            else:
                funding_pct_str = "0.0000%"

            writer.writerow([
                t["datetime"],
                t["profit_pct"],
                t["funding"],
                funding_pct_str, # <--- NEW
                t["pnl"],
                t["income"],
                t["commission"],
                t["volume"],
                t["in_trade"],
                t["symbol"],
                # Нові поля
                t.get("open_fee", 0),
                t.get("close_fee", 0),
                t.get("total_commission", 0),
                t.get("price_pnl", 0),
                t.get("funding_method", ""),
                t.get("duration_sec", 0),
            ])
            existing_keys.add(key)
            written += 1

    return written