import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPushButton
from pybit.unified_trading import HTTP
from datetime import datetime, timedelta
import time

class FundingStatsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit Funding Rates (Top 5 Active by Deviation)")
        self.setGeometry(100, 100, 600, 400)

        # Ініціалізація клієнта Bybit (основний API)
        self.session = HTTP(testnet=False)  # Використовуємо основний API

        # Кількість пар для відображення
        self.top_n = 10
        self.symbols = []  # Буде заповнено динамічно

        # Налаштування інтерфейсу
        self.setup_ui()

        # Початкове оновлення даних при запуску
        print("Initializing application...")
        self.update_funding_data()

    def setup_ui(self):
        print("Setting up UI...")
        # Основний віджет і лейаут
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Таблиця для відображення даних
        self.table = QTableWidget()
        self.table.setRowCount(self.top_n)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Symbol", "Funding Rate (%)", "Time to Next Funding"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Заборона редагування
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 250)

        # Кнопка для ручного оновлення
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.update_funding_data)

        # Додавання елементів до лейауту
        layout.addWidget(self.table)
        layout.addWidget(self.refresh_button)
        print("UI setup completed")

    def get_top_funding_symbols(self):
        try:
            print("Fetching tickers...")
            response = self.session.get_tickers(category="linear")
            if response["retCode"] != 0:
                print(f"Error fetching tickers: {response['retMsg']}")
                return []

            # Debug: Print response to inspect structure
            # print(response["result"]["list"][:2])  # Print first two items for brevity

            # Filter USDT pairs with sufficient volume and turnover
            min_volume = 100000
            min_turnover = 1000000
            symbols = [
                item["symbol"] for item in response["result"]["list"]
                if item["symbol"].endswith("USDT") and
                float(item.get("volume24h", 0)) > min_volume and
                float(item.get("turnover24h", 0)) > min_turnover
            ]
            print(f"Found {len(symbols)} active USDT pairs after filtering")

            # Limit to 50 symbols
            symbols = symbols[:10]
            print(f"Processing {len(symbols)} symbols for funding rates...")

            # Fetch funding rates
            funding_rates = []
            for i, symbol in enumerate(symbols):
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
                    time.sleep(1)  # Delay after every 10 requests

            # Sort by absolute funding rate
            funding_rates.sort(key=lambda x: abs(x["funding_rate"]), reverse=True)
            top_symbols = funding_rates[:self.top_n]
            print(f"Top {self.top_n} symbols: {[item['symbol'] for item in top_symbols]}")
            return top_symbols

        except Exception as e:
            print(f"Error in get_top_funding_symbols: {e}")
            return []

    def update_funding_data(self):
        try:
            print("Updating funding data...")
            # Отримання топ-5 символів
            self.symbols = self.get_top_funding_symbols()

            # Оновлення таблиці
            self.table.setRowCount(len(self.symbols))
            for row, data in enumerate(self.symbols):
                symbol = data["symbol"]
                funding_rate = data["funding_rate"]
                funding_time = data["funding_time"]

                # Символ
                self.table.setItem(row, 0, QTableWidgetItem(symbol))

                # Відсоток фандингу
                self.table.setItem(row, 1, QTableWidgetItem(f"{funding_rate:.4f}%"))

                # Час до наступної виплати
                next_funding = datetime.fromtimestamp(funding_time) + timedelta(hours=4)
                time_diff = next_funding - datetime.now()
                if time_diff.total_seconds() < 0:
                    time_str = "N/A"  # Якщо час виплати минув
                else:
                    hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.table.setItem(row, 2, QTableWidgetItem(time_str))

            # Заповнення порожніх рядків
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
        self.session.close()
        event.accept()

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication(sys.argv)
    window = FundingStatsApp()
    window.show()
    sys.exit(app.exec())