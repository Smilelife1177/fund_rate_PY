import csv
from datetime import datetime
import os
import time

CSV_FILE = "trade_stats.csv"

HEADERS = ["Дата_Час", "Процент", "Фандинг", "Прибиль", "Доход", "Комисия", "Обєм", "В-сделке", "Тикер"]

def initialize_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(HEADERS)

def record_last_closed_trade(session, exchange, symbol):
    initialize_csv()
    if exchange != "Bybit":
        print(f"Automatic trade stats recording is currently supported only for Bybit. Skipping for {exchange}.")
        return  # For now, implement only for Bybit to avoid complexity with Binance

    try:
        # Get the last closed PNL
        response_pnl = session.get_closed_pnl(category="linear", symbol=symbol, limit=1)
        if response_pnl["retCode"] != 0 or not response_pnl["result"]["list"]:
            print(f"Error fetching closed PNL for {symbol}: {response_pnl.get('retMsg', 'No data')}")
            return

        pnl = response_pnl["result"]["list"][0]
        created_time = int(pnl["createdTime"])  # ms
        updated_time = int(pnl["updatedTime"])  # ms
        date_time = datetime.fromtimestamp(updated_time / 1000).strftime("%Y-%m-%d %H:%M")
        ticker = pnl["symbol"]
        qty = float(pnl["qty"])
        avg_entry_price = float(pnl["avgEntryPrice"])
        avg_exit_price = float(pnl["avgExitPrice"])
        leverage = float(pnl.get("leverage", 1.0))  # Default to 1 if not present
        side = pnl["side"]
        cum_entry_value = float(pnl["cumEntryValue"])
        cum_exit_value = float(pnl["cumExitValue"])
        cum_entry_fee = float(pnl.get("cumEntryFee", 0.0))
        cum_exit_fee = float(pnl.get("cumExitFee", 0.0))
        closed_pnl = float(pnl["closedPnl"])

        # Gross profit
        gross_profit = cum_exit_value - cum_entry_value

        # Fees
        fee = cum_entry_fee + cum_exit_fee

        # Income (net PNL)
        income = closed_pnl

        # Percent (leveraged profit percentage)
        if qty > 0 and avg_entry_price > 0:
            if side == "Buy":
                percent = ((avg_exit_price - avg_entry_price) / avg_entry_price) * 100 * leverage
            else:
                percent = ((avg_entry_price - avg_exit_price) / avg_entry_price) * 100 * leverage
        else:
            percent = 0.0

        # Funding fees during the position
        funding = 0.0
        response_funding = session.get_income_history(
            category="linear",
            symbol=symbol,
            incomeType="FUNDING_FEE",
            startTime=created_time,
            endTime=updated_time,
            limit=50
        )
        if response_funding["retCode"] == 0:
            funding = sum(float(item["income"]) for item in response_funding["result"]["list"])

        # Volume (entry value)
        volume = cum_entry_value

        # Time in trade
        time_in_trade_sec = (updated_time - created_time) / 1000
        if time_in_trade_sec < 60:
            time_str = f"{int(time_in_trade_sec)}с"
        elif time_in_trade_sec < 3600:
            time_str = f"{int(time_in_trade_sec / 60)}м"
        else:
            time_str = f"{int(time_in_trade_sec / 3600)}г"

        # Format values as in example
        values = [
            f"{percent:.2f}%",
            f"{funding:.2f} $",
            f"{gross_profit:.2f} $",
            f"{income:.2f} $",
            f"{fee:.2f} $",
            f"{volume:.0f} $",
            time_str,
            ticker
        ]

        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            row = [date_time] + values
            writer.writerow(row)

        print(f"Trade stats recorded for {symbol}: {values}")

    except Exception as e:
        print(f"Error recording trade stats for {symbol}: {e}")