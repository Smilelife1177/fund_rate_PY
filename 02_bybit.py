# Bybit Funding Rate Monitor with PyQt6
import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QComboBox, QLabel, QDoubleSpinBox, QSpinBox, QCheckBox
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
        self.setGeometry(100, 100, 400, 600)  # Збільшено висоту для нового віджета balance

        # Ініціалізація клієнта Bybit з API ключами
        self.session = HTTP(
            testnet=False,
            api_key=API_KEY,
            api_secret=API_SECRET
        )

        # Початкові параметри угоди
        self.selected_symbol = "XEMUSDT"  # Змінено на активну пару
        self.funding_interval_hours = 1.0  # Реальний інтервал фандингу Bybit (8 годин)
        self.trade_duration_ms = 1000  # Час угоди (переконайтеся, що > entry_time_seconds * 1000)
        self.take_profit_percent = 0.3  # Початковий тейк-профіт (%)
        self.entry_time_seconds = 1.0  # Час входження (секунди до фандингу)
        self.qty = 1300.0  #  кількість ордера 
        self.enable_funding_trade = True  # Увімкнення фандингової угоди
        self.enable_post_funding_trade = True  # Увімкнення позиції після фандингу
        self.funding_data = None
        self.open_funding_order_id = None  # Для фандингового ордера
        self.open_post_funding_order_id = None  # Для позиції після фандингу

        # Налаштування інтерфейсу
        self.setup_ui()

        # Таймер для перевірки часу фандингу (кожну 1 секунду)
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

        # Вибір монети
        self.coin_selector_label = QLabel("Виберіть монету:")
        self.coin_selector = QComboBox()
        self.coins = ["APEXUSDT", "LPTUSDT", "INJUSDT", "XRPUSDT", "XEMUSDT"]  # Оновлено список активних монет
        self.coin_selector.addItems(self.coins)
        self.coin_selector.setCurrentText(self.selected_symbol)
        self.coin_selector.currentTextChanged.connect(self.update_symbol)

        # Інтервал фандингу (години)
        self.funding_interval_label = QLabel("Інтервал фандингу 1, 4, 8 годин:")
        self.funding_interval_spinbox = QDoubleSpinBox()
        self.funding_interval_spinbox.setRange(0.1, 24.0)  # Від 0.1 до 24 годин
        self.funding_interval_spinbox.setValue(self.funding_interval_hours)
        self.funding_interval_spinbox.setSingleStep(0.1)
        self.funding_interval_spinbox.valueChanged.connect(self.update_funding_interval)

        # Час угоди (мс)
        self.trade_duration_label = QLabel("Час угоди після фандингу (мс):")
        self.trade_duration_spinbox = QSpinBox()
        self.trade_duration_spinbox.setRange(500, 60000)  # Від 500 мс до 60 секунд
        self.trade_duration_spinbox.setValue(self.trade_duration_ms)
        self.trade_duration_spinbox.setSingleStep(100)
        self.trade_duration_spinbox.valueChanged.connect(self.update_trade_duration)

        # Тейк-профіт (%)
        self.take_profit_label = QLabel("Тейк-профіт (%):")
        self.take_profit_spinbox = QDoubleSpinBox()
        self.take_profit_spinbox.setRange(0.1, 10.0)  # Від 0.1% до 10%
        self.take_profit_spinbox.setValue(self.take_profit_percent)
        self.take_profit_spinbox.setSingleStep(0.1)
        self.take_profit_spinbox.valueChanged.connect(self.update_take_profit)

        # Час входження (секунди до фандингу)
        self.entry_time_label = QLabel("(секунди до фандингу):")
        self.entry_time_spinbox = QDoubleSpinBox()
        self.entry_time_spinbox.setRange(0.5, 10.0)  # Від 0.5 до 10 секунд
        self.entry_time_spinbox.setValue(self.entry_time_seconds)
        self.entry_time_spinbox.setSingleStep(0.1)
        self.entry_time_spinbox.valueChanged.connect(self.update_entry_time)

        # Вибір кількості ордера (qty)
        self.qty_label = QLabel("Кількість ордера (qty):")
        self.qty_spinbox = QDoubleSpinBox()
        self.qty_spinbox.setRange(0.001, 10000.0)  # Змінено діапазон для відповідності мінімальним вимогам
        self.qty_spinbox.setValue(self.qty)
        self.qty_spinbox.setSingleStep(0.001)
        self.qty_spinbox.valueChanged.connect(self.update_qty)

        # Чекбокс для фандингової угоди
        self.funding_trade_checkbox = QCheckBox("Увімкнути фандингову угоду")
        self.funding_trade_checkbox.setChecked(self.enable_funding_trade)
        self.funding_trade_checkbox.stateChanged.connect(self.update_funding_trade_enabled)

        # Чекбокс для позиції після фандингу
        self.post_funding_trade_checkbox = QCheckBox("Увімкнути угоду після фандингу з тейк-профітом")
        self.post_funding_trade_checkbox.setChecked(self.enable_post_funding_trade)
        self.post_funding_trade_checkbox.stateChanged.connect(self.update_post_funding_trade_enabled)

        # Мітка для відображення ставки фандингу та часу
        self.funding_info_label = QLabel("Ставка фандингу: N/A | Час до наступного фандингу: N/A")

        # Мітка для відображення поточної ціни
        self.price_label = QLabel("Поточна ціна: N/A")

        # Мітка для відображення балансу акаунту
        self.balance_label = QLabel("Баланс акаунту: N/A")

        # Кнопка для оновлення даних
        self.refresh_button = QPushButton("Оновити дані")
        self.refresh_button.clicked.connect(self.update_funding_data)

        # Додавання віджетів до лейауту
        layout.addWidget(self.coin_selector_label)
        layout.addWidget(self.coin_selector)
        layout.addWidget(self.funding_interval_label)
        layout.addWidget(self.funding_interval_spinbox)
        layout.addWidget(self.trade_duration_label)
        layout.addWidget(self.trade_duration_spinbox)
        layout.addWidget(self.take_profit_label)
        layout.addWidget(self.take_profit_spinbox)
        layout.addWidget(self.entry_time_label)
        layout.addWidget(self.entry_time_spinbox)
        layout.addWidget(self.qty_label)
        layout.addWidget(self.qty_spinbox)
        layout.addWidget(self.funding_trade_checkbox)
        layout.addWidget(self.post_funding_trade_checkbox)
        layout.addWidget(self.funding_info_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.balance_label)
        layout.addWidget(self.refresh_button)
        print("Налаштування інтерфейсу завершено")

    def update_symbol(self, symbol):
        self.selected_symbol = symbol
        print(f"Оновлено монету: {self.selected_symbol}")
        self.update_funding_data()

    def update_funding_interval(self, value):
        self.funding_interval_hours = value
        print(f"Оновлено інтервал фандингу: {self.funding_interval_hours} годин")
        self.update_funding_data()

    def update_trade_duration(self, value):
        self.trade_duration_ms = value
        print(f"Оновлено час угоди: {self.trade_duration_ms} мс")
        if self.trade_duration_ms < self.entry_time_seconds * 1000:
            print("Попередження: Час угоди менший за час входження, позиція може закритися до фандингу!")

    def update_take_profit(self, value):
        self.take_profit_percent = value
        print(f"Оновлено тейк-профіт: {self.take_profit_percent}%")

    def update_entry_time(self, value):
        self.entry_time_seconds = value
        print(f"Оновлено час входження: {self.entry_time_seconds} секунд")
        if self.trade_duration_ms < self.entry_time_seconds * 1000:
            print("Попередження: Час угоди менший за час входження, позиція може закритися до фандингу!")

    def update_qty(self, value):
        self.qty = value
        print(f"Оновлено кількість ордера: {self.qty}")

    def update_funding_trade_enabled(self, state):
        self.enable_funding_trade = state == 2  # 2 = Qt.Checked
        print(f"Фандингова угода {'увімкнена' if self.enable_funding_trade else 'вимкнена'}")

    def update_post_funding_trade_enabled(self, state):
        self.enable_post_funding_trade = state == 2  # 2 = Qt.Checked
        print(f"Угода після фандингу {'увімкнена' if self.enable_post_funding_trade else 'вимкнена'}")

    def get_account_balance(self):
        try:
            print("Отримання балансу акаунту...")
            response = self.session.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            if response["retCode"] == 0 and response["result"]["list"]:
                balance_data = response["result"]["list"][0]
                balance = float(balance_data["coin"][0]["walletBalance"])
                print(f"Баланс акаунту: {balance:.2f} USDT")
                return balance
            else:
                print(f"Помилка отримання балансу: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Помилка отримання балансу: {e}")
            return None

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

    def place_order(self, symbol, side, qty, take_profit=None):
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
                qty=str(self.qty),  # Використовуємо ту саму кількість
                timeInForce="GTC",
                reduceOnly=True  # Вказуємо, що це ордер для закриття позиції
            )
            if response["retCode"] == 0:
                print(f"Позицію успішно закрито: {response['result']}")
                # Відкриваємо нову позицію після закриття фандингової, якщо увімкнено
                if self.enable_post_funding_trade:
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

        # Розраховуємо тейк-профіт: +take_profit_percent% для лонгу, -take_profit_percent% для шорту
        take_profit = current_price * (1 + self.take_profit_percent / 100) if side == "Buy" else current_price * (1 - self.take_profit_percent / 100)
        # Округляємо тейк-профіт до 2 знаків після коми (залежить від монети)
        take_profit = round(take_profit, 2)

        # Відкриваємо нову позицію з тейк-профітом
        self.open_post_funding_order_id = self.place_order(symbol, side, qty=self.qty, take_profit=take_profit)

    def check_funding_time(self):
        if not self.funding_data:
            print("Дані фандингу відсутні")
            self.funding_info_label.setText("Ставка фандингу: N/A | Час до наступного фандингу: N/A")
            self.price_label.setText("Поточна ціна: N/A")
            self.balance_label.setText("Баланс акаунту: N/A")
            return

        symbol = self.funding_data["symbol"]
        funding_rate = self.funding_data["funding_rate"]
        funding_time = self.funding_data["funding_time"]

        time_to_funding, time_str = self.get_next_funding_time(funding_time)
        self.funding_info_label.setText(f"Ставка фандингу: {funding_rate:.4f}% | Час до наступного фандингу: {time_str}")
        print(f"Час до наступного фандингу для {symbol}: {time_str}")

        # Відкриття фандингового ордера, якщо увімкнено
        if self.enable_funding_trade:
            entry_window_start = self.entry_time_seconds - 1.0  # Вікно входження: [entry_time_seconds-1, entry_time_seconds]
            if entry_window_start <= time_to_funding <= self.entry_time_seconds and not self.open_funding_order_id:
                side = "Sell" if funding_rate > 0 else "Buy"
                self.open_funding_order_id = self.place_order(symbol, side, qty=self.qty)
                if self.open_funding_order_id:
                    # Запланувати закриття фандингової позиції через заданий час
                    QTimer.singleShot(self.trade_duration_ms, lambda: self.close_position(symbol, side) or setattr(self, 'open_funding_order_id', None))

    def update_funding_data(self):
        try:
            print("Оновлення даних фандингу...")
            self.funding_data = self.get_funding_data()

            # Оновлення поточної ціни
            current_price = self.get_current_price(self.selected_symbol)
            if current_price is not None:
                self.price_label.setText(f"Поточна ціна: ${current_price:.2f}")
            else:
                self.price_label.setText("Поточна ціна: N/A")

            # Оновлення балансу акаунту
            balance = self.get_account_balance()
            if balance is not None:
                self.balance_label.setText(f"Баланс акаунту: ${balance:.2f} USDT")
            else:
                self.balance_label.setText("Баланс акаунту: N/A")

            if self.funding_data:
                funding_rate = self.funding_data["funding_rate"]
                funding_time = self.funding_data["funding_time"]
                _, time_str = self.get_next_funding_time(funding_time)
                self.funding_info_label.setText(f"Ставка фандингу: {funding_rate:.4f}% | Час до наступного фандингу: {time_str}")
            else:
                self.funding_info_label.setText("Ставка фандингу: N/A | Час до наступного фандингу: N/A")
                self.price_label.setText("Поточна ціна: N/A")
                self.balance_label.setText("Баланс акаунту: N/A")

            print("Дані успішно оновлено")

        except Exception as e:
            print(f"Помилка оновлення даних фандингу: {e}")
            self.funding_info_label.setText("Ставка фандингу: Помилка | Час до наступного фандингу: Помилка")
            self.price_label.setText("Поточна ціна: Помилка")
            self.balance_label.setText("Баланс акаунту: Помилка")

    def closeEvent(self, event):
        self.timer.stop()
        # self.session.close() не потрібен, оскільки pybit HTTP клієнт не має методу close
        event.accept()

if __name__ == "__main__":
    print("Запуск програми...")
    app = QApplication(sys.argv)
    window = FundingStatsApp()
    window.show()
    sys.exit(app.exec())