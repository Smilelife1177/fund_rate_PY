import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QComboBox, QLabel
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
        self.setWindowTitle("Bybit Funding Rate Monitor")
        self.setGeometry(100, 100, 400, 200)

        # Ініціалізація клієнта Bybit з API ключами
        self.session = HTTP(
            testnet=False,
            api_key=API_KEY,
            api_secret=API_SECRET
        )

        # Вказана користувачем монета та параметри угоди
        self.selected_symbol = "LPTUSDT"  # Змініть на потрібну монету
        self.funding_interval_hours = 1  # Змініть на 8 для реального розкладу Bybit (00:00, 08:00, 16:00 UTC)
        self.trade_duration_ms = 1000  # Загальний час фандингової угоди в мілісекундах (наприклад, 1 секунда)
        self.take_profit_percent = 1.0  # Тейк-профіт для нової позиції: 1% руху ціни
        self.funding_data = None
        self.open_funding_order_id = None  # Для зберігання ID фандингового ордера
        self.open_post_funding_order_id = None  # Для зберігання ID позиції після фандингу

        # Налаштування інтерфейсу
        self.setup_ui()

        # Таймер для перевірки часу фандингу (кожну 1 секунду для точності)
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_funding_time)
        self.timer.start(1000)  # 1000 мс = 1 секунда

        # Початкове оновлення даних
        print("Ініціалізація програми...")
        self.update_funding_data()

    def setup_ui(self):
        print("Налаштування інтерфейсу...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Вибір монети (лише одна монета)
        self.coin_selector = QComboBox()
        self.coin_selector.addItem(self.selected_symbol)
        self.coin_selector.setEnabled(False)  # Вимкнено, бо лише одна монета

        # Мітка для відображення ставки фандингу та часу
        self.funding_info_label = QLabel("Ставка фандингу: N/A | Час до наступного фандингу: N/A")

        # Кнопка для оновлення даних
        self.refresh_button = QPushButton("Оновити дані")
        self.refresh_button.clicked.connect(self.update_funding_data)

        # Додавання віджетів до лейауту
        layout.addWidget(self.coin_selector)
        layout.addWidget(self.funding_info_label)
        layout.addWidget(self.refresh_button)
        print("Налаштування інтерфейсу завершено")

    def get_funding_data(self):
        try:
            print(f"Отримання ставки фандингу для {self.selected_symbol}...")
            response = self.session.get_funding_rate_history(
                category="linear",
                symbol=self.selected_symbol,
                limit=1
            )
            if response["retCode"] == 0 and response["result"]["list"]:
                funding_data = response["result"]["list"][0]
                funding_rate = float(funding_data["fundingRate"]) * 100
                funding_time = int(funding_data["fundingRateTimestamp"]) / 1000
                self.funding_data = {
                    "symbol": self.selected_symbol,
                    "funding_rate": funding_rate,
                    "funding_time": funding_time
                }
                print(f"Оброблено {self.selected_symbol}: {funding_rate:.4f}%")
                return self.funding_data
            else:
                print(f"Помилка отримання ставки фандингу для {self.selected_symbol}: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Помилка отримання ставки фандингу для {self.selected_symbol}: {e}")
            return None

    def get_current_price(self, symbol):
        try:
            print(f"Отримання поточної ціни для {symbol}...")
            response = self.session.get_tickers(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                price = float(response["result"]["list"][0]["lastPrice"])
                print(f"Поточна ціна {symbol}: {price}")
                return price
            else:
                print(f"Помилка отримання ціни для {symbol}: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Помилка отримання ціни для {symbol}: {e}")
            return None

    def get_next_funding_time(self, funding_time):
        funding_dt = datetime.fromtimestamp(funding_time, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        # Розрахунок наступного часу фандингу на основі кастомного інтервалу
        hours_since_last = (current_time - funding_dt).total_seconds() / 3600
        intervals_passed = int(hours_since_last / self.funding_interval_hours) + 1
        next_funding = funding_dt + timedelta(hours=intervals_passed * self.funding_interval_hours)
        time_diff = next_funding - current_time
        hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return time_diff.total_seconds(), f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def place_order(self, symbol, side, qty=1.0, take_profit=None):
        try:
            print(f"Розміщення ордера {side} для {symbol} з кількістю {qty} і тейк-профітом {take_profit}...")
            params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": "Market",
                "qty": str(qty),  # Bybit API вимагає qty як string
                "timeInForce": "GTC"
            }
            if take_profit is not None:
                params["takeProfit"] = str(take_profit)  # Bybit API вимагає takeProfit як string
            response = self.session.place_order(**params)
            if response["retCode"] == 0:
                print(f"Ордер успішно розміщено: {response['result']}")
                return response["result"]["orderId"]
            else:
                print(f"Помилка розміщення ордера для {symbol}: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Помилка розміщення ордера для {symbol}: {e}")
            return None

    def close_position(self, symbol, side):
        try:
            # Визначаємо протилежну сторону для закриття
            close_side = "Buy" if side == "Sell" else "Sell"
            print(f"Закриття позиції {side} для {symbol} через розміщення ордера {close_side}...")
            response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=1.0,  # Така ж кількість, що й при відкритті
                timeInForce="GTC",
                reduceOnly=True  # Вказуємо, що це ордер для закриття позиції
            )
            if response["retCode"] == 0:
                print(f"Позицію успішно закрито: {response['result']}")
                # Відкриваємо нову позицію після закриття фандингової
                self.open_post_funding_position(symbol)
            else:
                print(f"Помилка закриття позиції для {symbol}: {response['retMsg']}")
        except Exception as e:
            print(f"Помилка закриття позиції для {symbol}: {e}")

    def open_post_funding_position(self, symbol):
        if not self.funding_data:
            print("Дані фандингу відсутні для відкриття позиції після фандингу")
            return

        funding_rate = self.funding_data["funding_rate"]
        # Визначаємо сторону для нової позиції: шорт при мінусовому фандингу, лонг при плюсовому
        side = "Sell" if funding_rate < 0 else "Buy"

        # Отримуємо поточну ринкову ціну
        current_price = self.get_current_price(symbol)
        if current_price is None:
            print(f"Не вдалося отримати ціну для {symbol}, пропускаємо відкриття позиції")
            return

        # Розраховуємо тейк-профіт: +1% для лонгу, -1% для шорту
        take_profit = current_price * (1 + 0.01) if side == "Buy" else current_price * (1 - 0.01)
        # Округляємо тейк-профіт до 2 знаків після коми (залежить від монети)
        take_profit = round(take_profit, 3)

        # Відкриваємо нову позицію з тейк-профітом
        self.open_post_funding_order_id = self.place_order(symbol, side, qty=1.0, take_profit=take_profit)

    def check_funding_time(self):
        if not self.funding_data:
            print("Дані фандингу відсутні")
            self.funding_info_label.setText("Ставка фандингу: N/A | Час до наступного фандингу: N/A")
            return

        symbol = self.funding_data["symbol"]
        funding_rate = self.funding_data["funding_rate"]
        funding_time = self.funding_data["funding_time"]

        time_to_funding, time_str = self.get_next_funding_time(funding_time)
        self.funding_info_label.setText(f"Ставка фандингу: {funding_rate:.4f}% | Час до наступного фандингу: {time_str}")
        print(f"Час до наступного фандингу для {symbol}: {time_str}")

        # Відкриття фандингового ордера за 1-2 секунди до фандингу
        if 1 <= time_to_funding <= 2 and not self.open_funding_order_id:
            side = "Sell" if funding_rate > 0 else "Buy"
            self.open_funding_order_id = self.place_order(symbol, side, qty=1.0)
            if self.open_funding_order_id:
                # Запланувати закриття фандингової позиції через заданий час
                QTimer.singleShot(self.trade_duration_ms, lambda: self.close_position(symbol, side) or setattr(self, 'open_funding_order_id', None))

    def update_funding_data(self):
        try:
            print("Оновлення даних фандингу...")
            self.funding_data = self.get_funding_data()

            if self.funding_data:
                funding_rate = self.funding_data["funding_rate"]
                funding_time = self.funding_data["funding_time"]
                _, time_str = self.get_next_funding_time(funding_time)
                self.funding_info_label.setText(f"Ставка фандингу: {funding_rate:.4f}% | Час до наступного фандингу: {time_str}")
            else:
                self.funding_info_label.setText("Ставка фандингу: N/A | Час до наступного фандингу: N/A")

            print("Дані успішно оновлено")

        except Exception as e:
            print(f"Помилка оновлення даних фандингу: {e}")
            self.funding_info_label.setText("Ставка фандингу: Помилка | Час до наступного фандингу: Помилка")

    def closeEvent(self, event):
        self.timer.stop()
        self.session.close()
        event.accept()

if __name__ == "__main__":
    print("Запуск програми...")
    app = QApplication(sys.argv)
    window = FundingStatsApp()
    window.show()
    sys.exit(app.exec())