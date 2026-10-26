"""SQLite-backed storage for the Statistics tab."""
import re
from datetime import datetime

from database import DATABASE_FILE, TRADE_HEADERS, connection, fetch_rows, initialize_database, insert_rows


STATS_DB_FILE = DATABASE_FILE
STATS_HEADERS = [
    "Date/Time", "Profit %", "Funding", "Funding %", "Profit", "Income",
    "Commission", "Volume", "In trade", "Symbol", "Change% after 5m",
]


def initialize_stats_database():
    initialize_database()


def parse_stats_input(raw: str) -> list[str] | None:
    cleaned = re.sub(r"\s*\$\s*", " ", raw)
    values = [value.strip() for value in re.split(r"\s+", cleaned.strip()) if value.strip()]
    return values if len(values) == 8 else None


def write_stats_row(values: list[str]):
    try:
        funding = float(values[1].replace(",", ".").replace("—", "0"))
        volume = float(values[5].replace(",", "."))
        funding_pct = "{:.4f}%".format(funding / volume * 100) if volume else "0.0000%"
    except (IndexError, ValueError):
        funding_pct = "0.0000%"

    row = [datetime.now().strftime("%Y-%m-%d %H:%M")] + values[:2] + [funding_pct] + values[2:]
    row.extend([""] * (len(TRADE_HEADERS) - len(row)))
    insert_rows("trade_stats", TRADE_HEADERS, [row])


def read_stats() -> list[list[str]]:
    return fetch_rows("trade_stats", TRADE_HEADERS)


def write_imported_trades(trades: list[dict]) -> int:
    initialize_database()
    with connection() as conn:
        existing_keys = {
            (row["trade_datetime"], row["symbol"])
            for row in conn.execute("SELECT trade_datetime, symbol FROM trade_stats")
        }

    rows = []
    for trade in reversed(trades):
        key = (trade["datetime"], trade["symbol"])
        if key in existing_keys:
            continue
        volume = trade["volume"]
        funding_pct = "{:.4f}%".format(trade["funding"] / volume * 100) if volume else "0.0000%"
        rows.append([
            trade["datetime"], trade["profit_pct"], trade["funding"], funding_pct,
            trade["pnl"], trade["income"], trade["commission"], volume,
            trade["in_trade"], trade["symbol"], trade.get("change_after_5m", ""),
        ])
        existing_keys.add(key)
    insert_rows("trade_stats", TRADE_HEADERS, rows)
    return len(rows)


def update_trade_after_5m(symbol: str, trade_datetime: str, change_pct: float):
    initialize_database()
    with connection() as conn:
        cursor = conn.execute(
            """UPDATE trade_stats SET change_after_5m = ?
               WHERE id = (
                   SELECT id FROM trade_stats
                   WHERE symbol = ? AND trade_datetime = ?
                   ORDER BY id DESC LIMIT 1
               )""",
            ("{:+.2f}%".format(change_pct), symbol, trade_datetime),
        )
        return cursor.rowcount > 0
