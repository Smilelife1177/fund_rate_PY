"""
stats_manager.py — робота зі статистикою угод (CSV).
"""
import os
import re
import csv
from datetime import datetime


STATS_CSV_FILE = "trade_stats.csv"
STATS_HEADERS = ["Дата_Час", "Процент", "Фандинг", "%_Фандингу", "Прибиль", "Доход", "Комисия", "Обєм", "В-сделке", "Тикер", "Change%_after5m"]


def initialize_stats_csv(filepath: str = STATS_CSV_FILE):
    """Створює файл статистики, якщо його ще немає."""
    if not os.path.exists(filepath):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(STATS_HEADERS)
    else:
        # Перевірка на наявність нових заголовків
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header and ("Change%_after5m" not in header or len(header) != len(STATS_HEADERS)):
                # Додаємо або прибираємо колонки до існуючого файлу
                rows = list(reader)
                new_header = STATS_HEADERS
                with open(filepath, "w", newline="", encoding="utf-8") as f_out:
                    writer = csv.writer(f_out)
                    writer.writerow(new_header)
                    for row in rows:
                        # Створюємо новий рядок на основі старого, враховуючи зміну структури
                        # Якщо рядків менше — обрізаємо, якщо більше — доповнюємо
                        new_row = row[:len(new_header)]
                        if len(new_row) < len(new_header):
                            new_row.extend([""] * (len(new_header) - len(new_row)))
                        writer.writerow(new_row)


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
    
    # Дозаповнюємо рядок до довжини STATS_HEADERS (додаємо пустий Change%_after5m)
    extended_values = new_values + [""] * (len(STATS_HEADERS) - 1 - len(new_values))

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        writer.writerow([current_time] + extended_values)


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
        if len(row) >= 10: 
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
                funding_pct_str, 
                t["pnl"],
                t["income"],
                t["commission"],
                t["volume"],
                t["in_trade"],
                t["symbol"],
                t.get("change_after_5m", "") 
            ])
            existing_keys.add(key)
            written += 1

    return written

def update_trade_after_5m(symbol: str, trade_datetime: str, change_pct: float, filepath: str = STATS_CSV_FILE):
    """Оновлює поле Change%_after5m для конкретної угоди."""
    if not os.path.exists(filepath):
        return

    rows = []
    updated = False
    with open(filepath, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows:
        return

    header = rows[0]
    try:
        col_idx = header.index("Change%_after5m")
        time_idx = header.index("Дата_Час")
        symbol_idx = header.index("Тикер")
    except ValueError:
        return

    for i in range(1, len(rows)):
        if rows[i][symbol_idx] == symbol and rows[i][time_idx] == trade_datetime:
            rows[i][col_idx] = f"{change_pct:+.2f}%"
            updated = True
            break
    
    if updated:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
    return updated

def update_trade_after_5m(symbol: str, trade_datetime: str, change_pct: float, filepath: str = STATS_CSV_FILE):
    """Оновлює поле Change%_after5m для конкретної угоди."""
    if not os.path.exists(filepath):
        return

    rows = []
    updated = False
    with open(filepath, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows:
        return

    header = rows[0]
    try:
        col_idx = header.index("Change%_after5m")
        time_idx = header.index("Дата_Час")
        symbol_idx = header.index("Тикер")
    except ValueError:
        return

    for i in range(1, len(rows)):
        # Шукаємо збіг по тикеру та часу
        # trade_datetime може бути трохи іншим через секунди, але зазвичай ми порівнюємо хвилини
        if rows[i][symbol_idx] == symbol and rows[i][time_idx] == trade_datetime:
            rows[i][col_idx] = f"{change_pct:+.2f}%"
            updated = True
            break
    
    if updated:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
    return updated