import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QTimer
from pybit.unified_trading import HTTP
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

class FundingStatsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit Funding Rates")
        self.setGeometry(100, 100, 600, 400)


        load_dotenv()
        API_KEY = os.getenv('BYBIT_API_KEY')
        API_SECRET = os.getenv('BYBIT_API_SECRET')

        # Ініціалізація клієнта Bybit
        self.session = HTTP(testnet=True) ### 
        self.session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

        # Список торгових пар для відображення
        self.symbols = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "ADAUSDT"]

        # Налаштування інтерфейсу
        self.setup_ui()

        # Таймер для автоматичного оновлення кожні 60 секунд
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_funding_data)
        self.timer.start(60000)  # 60 секунд

        # Початкове оновлення даних
        self.update_funding_data()

    def setup_ui(self):
        # Основний віджет і лейаут
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Таблиця для відображення даних
        self.table = QTableWidget()
        self.table.setRowCount(len(self.symbols))
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

    def update_funding_data(self):
        try:
            # Отримання даних про фандинг
            funding_data = self.session.get_funding_rate_history(
                category="linear",
                symbol=""
            )["result"]["list"]

            # Фільтрація даних для обраних символів
            symbol_data = {symbol: None for symbol in self.symbols}
            for data in funding_data:
                if data["symbol"] in self.symbols and symbol_data[data["symbol"]] is None:
                    symbol_data[data["symbol"]] = data

            # Оновлення таблиці
            for row, symbol in enumerate(self.symbols):
                # Символ
                self.table.setItem(row, 0, QTableWidgetItem(symbol))

                data = symbol_data.get(symbol)
                if data:
                    # Відсоток фандингу
                    funding_rate = float(data["fundingRate"]) * 100  # Перетворення у відсотки
                    self.table.setItem(row, 1, QTableWidgetItem(f"{funding_rate:.4f}%"))

                    # Час до наступної виплати
                    funding_time = int(data["fundingRateTimestamp"]) / 1000  # У секундах
                    next_funding = datetime.fromtimestamp(funding_time) + timedelta(hours=8)
                    time_diff = next_funding - datetime.now()
                    hours, remainder = divmod(time_diff.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    self.table.setItem(row, 2, QTableWidgetItem(time_str))
                else:
                    self.table.setItem(row, 1, QTableWidgetItem("N/A"))
                    self.table.setItem(row, 2, QTableWidgetItem("N/A"))

        except Exception as e:
            print(f"Error updating funding data: {e}")
            for row in range(len(self.symbols)):
                self.table.setItem(row, 1, QTableWidgetItem("Error"))
                self.table.setItem(row, 2, QTableWidgetItem("Error"))

    def closeEvent(self, event):
        self.timer.stop()
        self.session.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FundingStatsApp()
    window.show()
    sys.exit(app.exec())