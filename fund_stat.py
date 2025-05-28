import os
from dotenv import load_dotenv
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QTimer
from pybit.unified_trading import HTTP
import time
from datetime import datetime, timedelta

class FundingStatsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit Funding Rates")
        self.setGeometry(100, 100, 600, 400)

        # Ініціалізація клієнта Bybit
        self.session = HTTP(testnet=True)

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
            for row, symbol in enumerate(self.symbols):
                # Отримання даних про фандинг для конкретного символу
                response = self.session.get_funding_rate_history(
                    category="linear",
                    symbol=symbol,
                    limit=1  # Отримуємо лише останній запис
                )
                
                # Перевірка, чи запит успішний
                if response["retCode"] == 0:
                    funding_data = response["result"]["list"][0]
                    
                    # Символ
                    self.table.setItem(row, 0, QTableWidgetItem(symbol))

                    # Відсоток фандингу
                    funding_rate = float(funding_data["fundingRate"]) * 100  # Перетворення у відсотки
                    self.table.setItem(row, 1, QTableWidgetItem(f"{funding_rate:.4f}%"))

                    # Час до наступної виплати
                    funding_time = int(funding_data["fundingRateTimestamp"]) / 1000  # У секундах
                    next_funding = datetime.fromtimestamp(funding_time) + timedelta(hours=8)
                    time_diff = next_funding - datetime.now()
                    hours, remainder = divmod(time_diff.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    self.table.setItem(row, 2, QTableWidgetItem(time_str))
                else:
                    # Якщо помилка для конкретного символу
                    self.table.setItem(row, 0, QTableWidgetItem(symbol))
                    self.table.setItem(row, 1, QTableWidgetItem("N/A"))
                    self.table.setItem(row, 2, QTableWidgetItem("N/A"))

        except Exception as e:
            print(f"Error updating funding data: {e}")
            for row in range(len(self.symbols)):
                self.table.setItem(row, 0, QTableWidgetItem(self.symbols[row]))
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