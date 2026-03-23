"""
stats_manager.py — робота зі статистикою угод (CSV).
"""
import os
import re
import csv
from datetime import datetime


STATS_CSV_FILE = "trade_stats.csv"
STATS_HEADERS = ["Дата_Час", "Процент", "Фандинг", "Прибиль", "Доход", "Комисия", "Обєм", "В-сделке", "Тикер"]


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
    """Записує рядок угоди в CSV."""
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        writer.writerow([current_time] + values)


def read_stats_csv(filepath: str = STATS_CSV_FILE) -> list[list[str]]:
    """Повертає всі рядки CSV (включаючи заголовок) або порожній список."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.reader(f))