import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPushButton, QCheckBox
from PyQt6.QtCore import QTimer
from pybit.unified_trading import HTTP
from datetime import datetime, timedelta, timezone
import time
from dotenv import load_dotenv

API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')

class FundingStatsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit Funding Rates (Top 50 Active by Deviation)")
        self.setGeometry(100, 100, 600, 400)

        # Ініціалізація клієнта Bybit з API ключами
        self.session = HTTP(
            testnet=False,
            api_key=API_KEY,  # Замініть на ваш API ключ
            api_secret=API_SECRET  # Замініть на ваш API секрет
        )

        # Кількість пар для відображення
        self.top_n = 50
        self.symbols = []
        self.top_funding_symbol = None  # Для зберігання монети з найбільшим фандингом

        # Налаштування інтерфейсу
        self.setup_ui()

        # Таймер для перевірки часу до виплати (кожні 10 секунд)
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_funding_time)
        self.timer.start(10000)  # 10000 мс = 10 секунд

        # Початкове оновлення даних
        print("Initializing application...")
        self.update_funding_data()

    def setup_ui(self):
        print("Setting up UI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Чекбокс для сортування
        self.checkBox = QCheckBox("Sort by funding rate")
        self.checkBox.setChecked(True)
        self.checkBox.stateChanged.connect(self.update_funding_data)

        # Таблиця для відображення даних
        self.table = QTableWidget()
        self.table.setRowCount(self.top_n)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Symbol", "Funding Rate (%)", "Time to Next Funding"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 250)

        # Кнопка для ручного оновлення
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.update_funding_data)

        # Додавання елементів до лейауту
        layout.addWidget(self.checkBox)
        layout.addWidget(self.table)
        layout.addWidget(self.refresh_button)
        print("UI setup completed")

    def get_top_funding_symbols(self):
        try:
            print("Fetching funding rates for custom symbols...")
            custom_symbols = [
                "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
                "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
                "MATICUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "XLMUSDT",
                "NEARUSDT", "ALGOUSDT", "ATOMUSDT", "ETCUSDT", "VETUSDT",
                "SHIBUSDT", "PEPEUSDT", "WLDUSDT", "APTUSDT", "ARBUSDT",
                "OPUSDT", "SUIUSDT", "INJUSDT", "FTMUSDT", "AAVEUSDT",
                "UNIUSDT", "MKRUSDT", "LDOUSDT", "CRVUSDT", "COMPUSDT",
                "RUNEUSDT", "GRTUSDT", "SNXUSDT", "ZECUSDT", "DASHUSDT",
                "EOSUSDT", "XMRUSDT", "NEOUSDT", "XTZUSDT", "ZILUSDT",
                "WAVESUSDT", "KAVAUSDT", "ARUSDT", "DYDXUSDT", "GALAUSDT"
            ][:50]

            print(f"Processing {len(custom_symbols)} custom symbols for funding rates...")

            funding_rates = []
            for i, symbol in enumerate(custom_symbols):
                if not symbol.endswith("USDT"):
                    print(f"Skipping invalid symbol: {symbol}")
                    continue
                try:
                    response = self.session.get_funding_rate_history(
                        category="linear",
                        symbol=symbol,
                        limit=1
                    )
                    if response["retCode"] == 0 and response["result"]["list"]:
                        funding_data = response["result"]["list"][0]
                        funding_rate = float(funding_data["fundingRate"]) * 100
                        funding_time = int(funding_data["fundingRateTimestamp"]) / 1000
                        funding_rates.append({
                            "symbol": symbol,
                            "funding_rate": funding_rate,
                            "funding_time": funding_time
                        })
                        print(f"Processed {symbol}: {funding_rate:.4f}%")
                    else:
                        print(f"Error fetching funding rate for {symbol}: {response['retMsg']}")
                except Exception as e:
                    print(f"Error fetching funding rate for {symbol}: {e}")
                if i % 10 == 9:
                    time.sleep(1)  # Затримка після кожних 10 запитів

            # Сортування за абсолютною величиною ставки фандингу
            if self.checkBox.isChecked():
                funding_rates.sort(key=lambda x: abs(x["funding_rate"]), reverse=True)
            else:
                funding_rates.sort(key=lambda x: x["symbol"])

            # Зберегти монету з найбільшим фандингом
            self.top_funding_symbol = funding_rates[0] if funding_rates else None
            top_symbols = funding_rates[:self.top_n]
            print(f"Top {self.top_n} symbols: {[item['symbol'] for item in top_symbols]}")
            return top_symbols

        except Exception as e:
            print(f"Error in get_top_funding_symbols: {e}")
            return []

    def get_next_funding_time(self, funding_time):
        funding_dt = datetime.fromtimestamp(funding_time, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        next_funding_hour = (funding_dt.hour // 8 + 1) * 8 % 24
        next_funding = funding_dt.replace(hour=next_funding_hour, minute=0, second=0, microsecond=0)
        if next_funding < current_time:
            next_funding += timedelta(days=1)
        time_diff = next_funding - current_time
        hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return time_diff.total_seconds(), f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def place_order(self, symbol, side, qty=0.001):
        try:
            print(f"Placing {side} order for {symbol} with qty {qty}...")
            response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side,  # "Buy" для лонг, "Sell" для шорт
                orderType="Market",
                qty=qty,  # Кількість контрактів (налаштуйте за потреби)
                timeInForce="GTC"
            )
            if response["retCode"] == 0:
                print(f"Order placed successfully: {response['result']}")
                return response["result"]["orderId"]
            else:
                print(f"Error placing order for {symbol}: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Error placing order for {symbol}: {e}")
            return None

    def close_position(self, symbol, side):
        try:
            print(f"Closing {side} position for {symbol}...")
            response = self.session.set_position_auto_cancel(
                category="linear",
                symbol=symbol,
                side=side  # "Buy" або "Sell" для закриття позиції
            )
            if response["retCode"] == 0:
                print(f"Position closed successfully: {response['result']}")
            else:
                print(f"Error closing position for {symbol}: {response['retMsg']}")
        except Exception as e:
            print(f"Error closing position for {symbol}: {e}")

    def check_funding_time(self):
        if not self.top_funding_symbol:
            print("No top funding symbol available")
            return

        symbol = self.top_funding_symbol["symbol"]
        funding_rate = self.top_funding_symbol["funding_rate"]
        funding_time = self.top_funding_symbol["funding_time"]

        time_to_funding, time_str = self.get_next_funding_time(funding_time)
        print(f"Time to next funding for {symbol}: {time_str}")

        # Відкрити угоду за 1 хвилину (60 секунд) до виплати
        if 30 <= time_to_funding <= 60:
            side = "Sell" if funding_rate > 0 else "Buy"  # Шорт для позитивного, лонг для негативного
            order_id = self.place_order(symbol, side, qty=0.001)  # Налаштуйте qty
            if order_id:
                # Запланувати закриття позиції через 10 секунд після виплати
                QTimer.singleShot(70000, lambda: self.close_position(symbol, side))  # 60с до виплати + 10с після

    def update_funding_data(self):
        try:
            print("Updating funding data...")
            self.symbols = self.get_top_funding_symbols()

            self.table.setRowCount(len(self.symbols))
            for row, data in enumerate(self.symbols):
                symbol = data["symbol"]
                funding_rate = data["funding_rate"]
                funding_time = data["funding_time"]

                self.table.setItem(row, 0, QTableWidgetItem(symbol))
                self.table.setItem(row, 1, QTableWidgetItem(f"{funding_rate:.4f}%"))
                _, time_str = self.get_next_funding_time(funding_time)
                self.table.setItem(row, 2, QTableWidgetItem(time_str))

            for row in range(len(self.symbols), self.top_n):
                self.table.setItem(row, 0, QTableWidgetItem("N/A"))
                self.table.setItem(row, 1, QTableWidgetItem("N/A"))
                self.table.setItem(row, 2, QTableWidgetItem("N/A"))

            print("Table updated successfully")

        except Exception as e:
            print(f"Error updating funding data: {e}")
            for row in range(self.top_n):
                self.table.setItem(row, 0, QTableWidgetItem("Error"))
                self.table.setItem(row, 1, QTableWidgetItem("Error"))
                self.table.setItem(row, 2, QTableWidgetItem("Error"))

    def closeEvent(self, event):
        self.timer.stop()
        self.session.close()
        event.accept()

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication(sys.argv)
    window = FundingStatsApp()
    window.show()
    sys.exit(app.exec())