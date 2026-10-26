"""SQLite storage and one-time migration for local application statistics."""
import csv
import os
import sqlite3
from contextlib import contextmanager


DATABASE_FILE = "funding_trader.db"
TRADE_CSV_FILE = "trade_stats.csv"
FUNDING_CSV_FILE = "funding_stats.csv"

TRADE_HEADERS = [
    "trade_datetime", "percent", "funding", "funding_pct", "profit", "income",
    "commission", "volume", "in_trade", "symbol", "change_after_5m",
]
FUNDING_HEADERS = [
    "funding_timestamp", "symbol", "funding_rate_pct", "volume_24h",
    "relative_volume_1h", "open_interest_value", "spread_pct",
    "liquidity_depth_1pct_usdt", "volatility_1h_pct", "price_change_1h_pct",
    "price_change_12h_pct", "price_change_24h_pct", "price_pre_5s", "price_1m",
    "price_1m_%", "price_5m", "price_5m_%", "price_10m", "price_10m_%",
]


def _connection(db_path=DATABASE_FILE):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


@contextmanager
def connection(db_path=DATABASE_FILE):
    conn = _connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database(db_path=DATABASE_FILE):
    """Create tables and import legacy CSV data once, when present."""
    with connection(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_stats (
                id INTEGER PRIMARY KEY,
                trade_datetime TEXT, percent TEXT, funding TEXT, funding_pct TEXT,
                profit TEXT, income TEXT, commission TEXT, volume TEXT, in_trade TEXT,
                symbol TEXT, change_after_5m TEXT
            )
        """)
        funding_columns = ", ".join('"{}" TEXT'.format(header) for header in FUNDING_HEADERS)
        conn.execute("CREATE TABLE IF NOT EXISTS funding_stats (id INTEGER PRIMARY KEY, {})".format(funding_columns))
        _migrate_csv_once(conn, "trade_csv_migrated", TRADE_CSV_FILE, "trade_stats", TRADE_HEADERS)
        _migrate_csv_once(conn, "funding_csv_migrated", FUNDING_CSV_FILE, "funding_stats", FUNDING_HEADERS)


def _migrate_csv_once(conn, migration_key, csv_path, table, headers):
    if conn.execute("SELECT 1 FROM metadata WHERE key = ?", (migration_key,)).fetchone():
        return
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as csv_file:
                reader = csv.reader(csv_file)
                next(reader, None)  # Legacy header names may have a different encoding.
                rows = [
                    tuple((row + [""] * len(headers))[:len(headers)])
                    for row in reader
                ]
            if rows:
                columns = ", ".join('"{}"'.format(header) for header in headers)
                placeholders = ", ".join("?" for _ in headers)
                conn.executemany(
                    "INSERT INTO {} ({}) VALUES ({})".format(table, columns, placeholders), rows
                )
            print("Migrated {} records from {} to SQLite.".format(len(rows), csv_path))
        except (OSError, csv.Error) as error:
            print("Could not migrate {}: {}".format(csv_path, error))
            return
    conn.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", (migration_key, "1"))


def fetch_rows(table, headers, db_path=DATABASE_FILE, newest_first=False):
    initialize_database(db_path)
    columns = ", ".join('"{}"'.format(header) for header in headers)
    order = " ORDER BY id DESC" if newest_first else " ORDER BY id"
    with connection(db_path) as conn:
        return [list(row) for row in conn.execute("SELECT {} FROM {}{}".format(columns, table, order))]


def insert_rows(table, headers, rows, db_path=DATABASE_FILE):
    if not rows:
        return
    initialize_database(db_path)
    columns = ", ".join('"{}"'.format(header) for header in headers)
    placeholders = ", ".join("?" for _ in headers)
    with connection(db_path) as conn:
        conn.executemany(
            "INSERT INTO {} ({}) VALUES ({})".format(table, columns, placeholders), rows
        )
