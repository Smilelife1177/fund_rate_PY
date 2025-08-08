import os
import json
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel, QDoubleSpinBox, QSlider, QComboBox, QCheckBox, QMessageBox, QTabWidget, QToolButton
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QTabBar
from logic import get_account_balance, get_funding_data, get_current_price, get_next_funding_time, place_market_order, get_symbol_info, place_limit_close_order, update_ping, initialize_client, close_all_positions, get_optimal_limit_price, get_candle_open_price, place_stop_loss_order, get_order_execution_price
from translations import translations
import time
import math

class FundingTraderApp(QMainWindow):
    def __init__(self, session, testnet, exchange):
        super().__init__()
        self.language = "en"
        self.setWindowTitle(translations[self.language]["window_title"].format(exchange))
        self.setGeometry(100, 100, 400, 600)

        icon_path = r"images\log.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Icon file not found at: {icon_path}")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.language_label = QLabel(translations[self.language]["language_label"])
        self.language_combobox = QComboBox()
        self.language_combobox.addItems(["English", "Українська"])
        self.language_combobox.setCurrentText("English" if self.language == "en" else "Українська")
        self.language_combobox.currentTextChanged.connect(self.update_language)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        self.tab_data_list = []

        self.add_tab_button = QToolButton()
        self.add_tab_button.setText("+")
        self.add_tab_button.setFixedWidth(30)
        self.add_tab_button.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.add_tab_button.clicked.connect(self.add_new_tab)
        self.tab_widget.addTab(QWidget(), "+")
        self.tab_widget.setTabEnabled(self.tab_widget.count() - 1, False)
        self.tab_widget.tabBar().setTabButton(self.tab_widget.count() - 1, QTabBar.ButtonPosition.RightSide, self.add_tab_button)

        self.tab_count = 0
        loaded_settings = self.load_settings()
        initial_settings = loaded_settings[0] if loaded_settings else None
        self.add_new_tab(
            session=session,
            testnet=testnet,
            exchange=exchange,
            settings=initial_settings
        )

        for tab_data in self.tab_data_list:
            self.update_tab_funding_data(tab_data)

        self.main_layout.addWidget(self.language_label)
        self.main_layout.addWidget(self.language_combobox)
        self.main_layout.addWidget(self.tab_widget)

        self.save_settings()

    def add_new_tab(self, session=None, testnet=None, exchange=None, settings=None):
        self.tab_count += 1
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_data = self.create_tab_ui(tab_layout, session, testnet, exchange, settings)
        self.tab_data_list.append(tab_data)
        self.tab_widget.insertTab(self.tab_widget.count() - 1, tab, translations[self.language]["tab_title"].format(self.tab_count))
        self.tab_widget.setCurrentWidget(tab)
        tab_data["tab_index"] = self.tab_count
        return tab_data

    def create_tab_ui(self, layout, session, testnet, exchange, settings=None):
        default_settings = {
            "selected_symbol": "HYPERUSDT",
            "funding_interval_hours": 1.0 if exchange == "Bybit" else 8.0,
            "entry_time_seconds": 5.0,
            "qty": 45.0,
            "profit_percentage": 1.0,
            "leverage": 1.0,
            "exchange": exchange or "Bybit",
            "testnet": testnet or False,
            "auto_limit": False,
            "stop_loss_percentage": 0.5,
            "stop_loss_enabled": True
        }
        if settings:
            default_settings.update(settings)
        tab_data = {
            "session": session or initialize_client(default_settings["exchange"], default_settings["testnet"]),
            "testnet": default_settings["testnet"],
            "exchange": default_settings["exchange"],
            "selected_symbol": default_settings["selected_symbol"],
            "funding_interval_hours": default_settings["funding_interval_hours"],
            "entry_time_seconds": default_settings["entry_time_seconds"],
            "qty": default_settings["qty"],
            "profit_percentage": default_settings["profit_percentage"],
            "leverage": default_settings["leverage"],
            "auto_limit": default_settings["auto_limit"],
            "stop_loss_percentage": default_settings["stop_loss_percentage"],
            "stop_loss_enabled": default_settings["stop_loss_enabled"],
            "funding_data": None,
            "open_order_id": None,
            "funding_time_price": None,
            "limit_price": None,
            "pre_funding_price": None  # Додаємо для зберігання ціни за 1 секунду до фандингу
        }

        exchange_label = QLabel(translations[self.language]["exchange_label"])
        exchange_combobox = QComboBox()
        exchange_combobox.addItems(["Bybit", "Binance"])
        exchange_combobox.setCurrentText(tab_data["exchange"])
        exchange_combobox.currentTextChanged.connect(lambda value: self.update_tab_exchange(tab_data, value))

        testnet_label = QLabel(translations[self.language]["testnet_label"])
        testnet_checkbox = QCheckBox(translations[self.language]["testnet_checkbox"])
        testnet_checkbox.setChecked(tab_data["testnet"])
        testnet_checkbox.stateChanged.connect(lambda state: self.update_tab_testnet(tab_data, state))

        coin_input_label = QLabel(translations[self.language]["coin_input_label"])
        coin_input = QLineEdit()
        coin_input.setText(tab_data["selected_symbol"])

        update_coin_button = QPushButton(translations[self.language]["update_coin_button"])
        update_coin_button.clicked.connect(lambda: self.update_tab_symbol(tab_data, coin_input.text()))

        funding_interval_label = QLabel(translations[self.language]["funding_interval_label"])
        funding_interval_combobox = QComboBox()
        funding_intervals = ["0.01", "1", "4", "8"] if tab_data["exchange"] == "Bybit" else ["8"]
        funding_interval_combobox.addItems(funding_intervals)
        formatted_interval = str(float(tab_data["funding_interval_hours"]))
        if formatted_interval.endswith(".0"):
            formatted_interval = formatted_interval[:-2]
        funding_interval_combobox.setCurrentText(formatted_interval)
        funding_interval_combobox.currentTextChanged.connect(lambda value: self.update_tab_funding_interval(tab_data, value))

        entry_time_label = QLabel(translations[self.language]["entry_time_label"])
        entry_time_spinbox = QDoubleSpinBox()
        entry_time_spinbox.setRange(0.5, 60.0)
        entry_time_spinbox.setValue(tab_data["entry_time_seconds"])
        entry_time_spinbox.setSingleStep(0.1)
        entry_time_spinbox.valueChanged.connect(lambda value: self.update_tab_entry_time(tab_data, value))

        qty_label = QLabel(translations[self.language]["qty_label"])
        qty_spinbox = QDoubleSpinBox()
        qty_spinbox.setRange(0.001, 10000.0)
        qty_spinbox.setValue(tab_data["qty"])
        qty_spinbox.setSingleStep(0.001)
        qty_spinbox.valueChanged.connect(lambda value: self.update_tab_qty(tab_data, value))

        profit_percentage_label = QLabel(translations[self.language]["profit_percentage_label"])
        profit_percentage_spinbox = QDoubleSpinBox()
        profit_percentage_spinbox.setRange(0.1, 10.0)
        profit_percentage_spinbox.setValue(tab_data["profit_percentage"])
        profit_percentage_spinbox.setSingleStep(0.1)
        profit_percentage_spinbox.valueChanged.connect(lambda value: self.update_tab_profit_percentage(tab_data, value))

        profit_percentage_slider = QSlider(Qt.Orientation.Horizontal)
        profit_percentage_slider.setRange(10, 1000)
        profit_percentage_slider.setValue(int(tab_data["profit_percentage"] * 100))
        profit_percentage_slider.setSingleStep(10)
        profit_percentage_slider.valueChanged.connect(lambda value: self.update_tab_profit_percentage_from_slider(tab_data, value))

        auto_limit_label = QLabel(translations[self.language]["auto_limit_label"])
        auto_limit_checkbox = QCheckBox(translations[self.language]["auto_limit_checkbox"])
        auto_limit_checkbox.setChecked(tab_data["auto_limit"])
        auto_limit_checkbox.stateChanged.connect(lambda state: self.update_tab_auto_limit(tab_data, state))

        leverage_label = QLabel(translations[self.language]["leverage_label"])
        leverage_spinbox = QDoubleSpinBox()
        leverage_spinbox.setRange(1.0, 100.0)
        leverage_spinbox.setValue(tab_data["leverage"])
        leverage_spinbox.setSingleStep(0.1)
        leverage_spinbox.valueChanged.connect(lambda value: self.update_tab_leverage(tab_data, value))

        stop_loss_enabled_label = QLabel(translations[self.language]["stop_loss_enabled_label"])
        stop_loss_enabled_checkbox = QCheckBox(translations[self.language]["stop_loss_enabled_checkbox"])
        stop_loss_enabled_checkbox.setChecked(tab_data["stop_loss_enabled"])
        stop_loss_enabled_checkbox.stateChanged.connect(lambda state: self.update_tab_stop_loss_enabled(tab_data, state))

        stop_loss_percentage_label = QLabel(translations[self.language]["stop_loss_percentage_label"])
        stop_loss_percentage_spinbox = QDoubleSpinBox()
        stop_loss_percentage_spinbox.setRange(0.1, 10.0)
        stop_loss_percentage_spinbox.setValue(tab_data["stop_loss_percentage"])
        stop_loss_percentage_spinbox.setSingleStep(0.1)
        stop_loss_percentage_spinbox.valueChanged.connect(lambda value: self.update_tab_stop_loss_percentage(tab_data, value))

        funding_info_label = QLabel(translations[self.language]["funding_info_label"])
        price_label = QLabel(translations[self.language]["price_label"])
        balance_label = QLabel(translations[self.language]["balance_label"])
        leveraged_balance_label = QLabel(translations[self.language]["leveraged_balance_label"])
        volume_label = QLabel(translations[self.language]["volume_label"])
        ping_label = QLabel(translations[self.language]["ping_label"])

        refresh_button = QPushButton(translations[self.language]["refresh_button"])
        refresh_button.clicked.connect(lambda: self.update_tab_funding_data(tab_data))

        close_all_trades_button = QPushButton(translations[self.language]["close_all_trades_button"])
        close_all_trades_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        close_all_trades_button.clicked.connect(lambda: self.handle_tab_close_all_trades(tab_data))

        layout.addWidget(exchange_label)
        layout.addWidget(exchange_combobox)
        layout.addWidget(testnet_label)
        layout.addWidget(testnet_checkbox)
        layout.addWidget(coin_input_label)
        layout.addWidget(coin_input)
        layout.addWidget(update_coin_button)
        layout.addWidget(funding_interval_label)
        layout.addWidget(funding_interval_combobox)
        layout.addWidget(entry_time_label)
        layout.addWidget(entry_time_spinbox)
        layout.addWidget(qty_label)
        layout.addWidget(qty_spinbox)
        layout.addWidget(profit_percentage_label)
        layout.addWidget(profit_percentage_spinbox)
        layout.addWidget(profit_percentage_slider)
        layout.addWidget(auto_limit_label)
        layout.addWidget(auto_limit_checkbox)
        layout.addWidget(leverage_label)
        layout.addWidget(leverage_spinbox)
        layout.addWidget(stop_loss_enabled_label)
        layout.addWidget(stop_loss_enabled_checkbox)
        layout.addWidget(stop_loss_percentage_label)
        layout.addWidget(stop_loss_percentage_spinbox)
        layout.addWidget(funding_info_label)
        layout.addWidget(price_label)
        layout.addWidget(balance_label)
        layout.addWidget(leveraged_balance_label)
        layout.addWidget(volume_label)
        layout.addWidget(ping_label)
        layout.addWidget(refresh_button)
        layout.addWidget(close_all_trades_button)

        tab_data.update({
            "exchange_label": exchange_label,
            "stop_loss_enabled_label": stop_loss_enabled_label,
            "stop_loss_enabled_checkbox": stop_loss_enabled_checkbox,
            "stop_loss_percentage_label": stop_loss_percentage_label,
            "stop_loss_percentage_spinbox": stop_loss_percentage_spinbox,
            "exchange_combobox": exchange_combobox,
            "testnet_label": testnet_label,
            "testnet_checkbox": testnet_checkbox,
            "coin_input_label": coin_input_label,
            "coin_input": coin_input,
            "update_coin_button": update_coin_button,
            "funding_interval_label": funding_interval_label,
            "funding_interval_combobox": funding_interval_combobox,
            "entry_time_label": entry_time_label,
            "entry_time_spinbox": entry_time_spinbox,
            "qty_label": qty_label,
            "qty_spinbox": qty_spinbox,
            "profit_percentage_label": profit_percentage_label,
            "profit_percentage_spinbox": profit_percentage_spinbox,
            "profit_percentage_slider": profit_percentage_slider,
            "auto_limit_label": auto_limit_label,
            "auto_limit_checkbox": auto_limit_checkbox,
            "leverage_label": leverage_label,
            "leverage_spinbox": leverage_spinbox,
            "funding_info_label": funding_info_label,
            "price_label": price_label,
            "balance_label": balance_label,
            "leveraged_balance_label": leveraged_balance_label,
            "volume_label": volume_label,
            "ping_label": ping_label,
            "refresh_button": refresh_button,
            "close_all_trades_button": close_all_trades_button
        })

        timer = QTimer()
        timer.timeout.connect(lambda: self.check_tab_funding_time(tab_data))
        timer.start(1000)

        ping_timer = QTimer()
        ping_timer.timeout.connect(lambda: self.update_tab_ping(tab_data))
        ping_timer.start(5000)

        tab_data.update({
            "timer": timer,
            "ping_timer": ping_timer
        })

        return tab_data

    def update_language(self, language_text):
        self.language = "en" if language_text == "English" else "uk"
        self.setWindowTitle(translations[self.language]["window_title"].format(self.tab_data_list[0]["exchange"] if self.tab_data_list else "Funding Trader"))
        self.language_label.setText(translations[self.language]["language_label"])
        for tab_data in self.tab_data_list:
            tab_index = self.tab_data_list.index(tab_data)
            self.tab_widget.setTabText(tab_index, translations[self.language]["tab_title"].format(tab_data["tab_index"]))
            tab_data["exchange_label"].setText(translations[self.language]["exchange_label"])
            tab_data["testnet_label"].setText(translations[self.language]["testnet_label"])
            tab_data["testnet_checkbox"].setText(translations[self.language]["testnet_checkbox"])
            tab_data["coin_input_label"].setText(translations[self.language]["coin_input_label"])
            tab_data["update_coin_button"].setText(translations[self.language]["update_coin_button"])
            tab_data["funding_interval_label"].setText(translations[self.language]["funding_interval_label"])
            tab_data["entry_time_label"].setText(translations[self.language]["entry_time_label"])
            tab_data["qty_label"].setText(translations[self.language]["qty_label"])
            tab_data["profit_percentage_label"].setText(translations[self.language]["profit_percentage_label"])
            tab_data["auto_limit_label"].setText(translations[self.language]["auto_limit_label"])
            tab_data["auto_limit_checkbox"].setText(translations[self.language]["auto_limit_checkbox"])
            tab_data["leverage_label"].setText(translations[self.language]["leverage_label"])
            tab_data["stop_loss_enabled_label"].setText(translations[self.language]["stop_loss_enabled_label"])
            tab_data["stop_loss_enabled_checkbox"].setText(translations[self.language]["stop_loss_enabled_checkbox"])
            tab_data["stop_loss_percentage_label"].setText(translations[self.language]["stop_loss_percentage_label"])
            tab_data["refresh_button"].setText(translations[self.language]["refresh_button"])
            tab_data["close_all_trades_button"].setText(translations[self.language]["close_all_trades_button"])
            self.update_tab_funding_data(tab_data)
        self.save_settings()

    def update_tab_exchange(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping exchange update")
            return
        tab_data["exchange"] = value
        tab_data["session"] = initialize_client(value, tab_data["testnet"])
        tab_data["funding_interval_hours"] = 1.0 if value == "Bybit" else 8.0
        tab_data["funding_interval_combobox"].clear()
        funding_intervals = ["0.01", "1", "4", "8"] if value == "Bybit" else ["8"]
        tab_data["funding_interval_combobox"].addItems(funding_intervals)
        tab_data["funding_interval_combobox"].setCurrentText(str(float(tab_data["funding_interval_hours"])))
        self.update_tab_funding_data(tab_data)
        self.save_settings()

    def update_tab_testnet(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping testnet update")
            return
        tab_data["testnet"] = state == Qt.CheckState.Checked.value
        tab_data["session"] = initialize_client(tab_data["exchange"], tab_data["testnet"])
        self.update_tab_funding_data(tab_data)
        self.save_settings()

    def update_tab_symbol(self, tab_data, symbol):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping symbol update")
            return
        tab_data["selected_symbol"] = symbol.upper()
        tab_data["open_order_id"] = None
        tab_data["funding_time_price"] = None
        tab_data["limit_price"] = None
        tab_data["pre_funding_price"] = None
        self.update_tab_funding_data(tab_data)
        self.save_settings()

    def update_tab_funding_interval(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping funding interval update")
            return
        tab_data["funding_interval_hours"] = float(value)
        self.update_tab_funding_data(tab_data)
        self.save_settings()

    def update_tab_entry_time(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping entry time update")
            return
        tab_data["entry_time_seconds"] = value
        self.save_settings()

    def update_tab_qty(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping qty update")
            return
        tab_data["qty"] = value
        self.update_tab_volume_label(tab_data)
        self.save_settings()

    def update_tab_profit_percentage(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping profit percentage update")
            return
        tab_data["profit_percentage"] = value
        tab_data["profit_percentage_slider"].setValue(int(value * 100))
        self.save_settings()

    def update_tab_profit_percentage_from_slider(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping profit percentage slider update")
            return
        tab_data["profit_percentage"] = value / 100.0
        tab_data["profit_percentage_spinbox"].setValue(tab_data["profit_percentage"])
        self.save_settings()

    def update_tab_auto_limit(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping auto limit update")
            return
        tab_data["auto_limit"] = state == Qt.CheckState.Checked.value
        self.save_settings()

    def update_tab_leverage(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping leverage update")
            return
        tab_data["leverage"] = value
        self.update_tab_leveraged_balance_label(tab_data)
        self.save_settings()

    def update_tab_stop_loss_enabled(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping stop loss enabled update")
            return
        tab_data["stop_loss_enabled"] = state == Qt.CheckState.Checked.value
        self.save_settings()

    def update_tab_stop_loss_percentage(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping stop loss percentage update")
            return
        tab_data["stop_loss_percentage"] = value
        self.save_settings()

    def load_settings(self):
        settings_path = r"scripts\settings.json"
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    return settings.get("tabs", [])
            return []
        except Exception as e:
            print(f"Error loading settings: {e}")
            return []

    def save_settings(self):
        settings_path = r"scripts\settings.json"
        settings = {
            "tabs": [
                {
                    "selected_symbol": tab_data["selected_symbol"],
                    "funding_interval_hours": tab_data["funding_interval_hours"],
                    "entry_time_seconds": tab_data["entry_time_seconds"],
                    "qty": tab_data["qty"],
                    "profit_percentage": tab_data["profit_percentage"],
                    "leverage": tab_data["leverage"],
                    "exchange": tab_data["exchange"],
                    "testnet": tab_data["testnet"],
                    "auto_limit": tab_data["auto_limit"],
                    "stop_loss_percentage": tab_data["stop_loss_percentage"],
                    "stop_loss_enabled": tab_data["stop_loss_enabled"]
                } for tab_data in self.tab_data_list
            ],
            "language": self.language
        }
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def close_tab(self, index):
        if index < len(self.tab_data_list):
            tab_data = self.tab_data_list[index]
            tab_data["timer"].stop()
            tab_data["ping_timer"].stop()
            del self.tab_data_list[index]
            self.tab_widget.removeTab(index)
            self.save_settings()

    def update_tab_volume_label(self, tab_data):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping volume label update")
            return
        current_price = get_current_price(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])
        if current_price is not None and tab_data["qty"] is not None:
            volume = current_price * tab_data["qty"] * tab_data["leverage"]
            tab_data["volume_label"].setText(f"{translations[self.language]['volume_label'].split(':')[0]}: ${volume:.2f} USD")
            if volume < 5.0 or (leveraged_balance := get_account_balance(tab_data["session"], tab_data["exchange"]) * tab_data["leverage"]) and volume > leveraged_balance:
                tab_data["volume_label"].setStyleSheet("color: red;")
            else:
                tab_data["volume_label"].setStyleSheet("color: black;")
        else:
            tab_data["volume_label"].setText(translations[self.language]["volume_label"])
            tab_data["volume_label"].setStyleSheet("color: black;")

    def update_tab_leveraged_balance_label(self, tab_data):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping leveraged balance update")
            return
        balance = get_account_balance(tab_data["session"], tab_data["exchange"])
        if balance is not None and tab_data["leverage"] is not None:
            leveraged_balance = balance * tab_data["leverage"]
            tab_data["leveraged_balance_label"].setText(f"{translations[self.language]['leveraged_balance_label'].split(':')[0]}: ${leveraged_balance:.2f} USDT")
        else:
            tab_data["leveraged_balance_label"].setText(translations[self.language]["leveraged_balance_label"])

    def update_tab_ping(self, tab_data):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping ping update")
            return
        update_ping(tab_data["session"], tab_data["ping_label"], tab_data["exchange"])

    def check_tab_funding_time(self, tab_data):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping funding check")
            return
        if not tab_data["funding_data"] or not all(key in tab_data["funding_data"] for key in ["symbol", "funding_rate", "funding_time"]):
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Funding data unavailable or incomplete")
            tab_data["funding_info_label"].setText(translations[self.language]["funding_info_label"])
            tab_data["price_label"].setText(translations[self.language]["price_label"])
            tab_data["balance_label"].setText(translations[self.language]["balance_label"])
            tab_data["leveraged_balance_label"].setText(translations[self.language]["leveraged_balance_label"])
            tab_data["volume_label"].setText(translations[self.language]["volume_label"])
            tab_data["volume_label"].setStyleSheet("color: black;")
            tab_data["ping_label"].setText(translations[self.language]["ping_label"])
            tab_data["ping_label"].setStyleSheet("color: black;")
            return

        symbol = tab_data["funding_data"]["symbol"]
        funding_rate = tab_data["funding_data"]["funding_rate"]
        funding_time = tab_data["funding_data"]["funding_time"]

        try:
            time_to_funding, time_str = get_next_funding_time(funding_time, tab_data["funding_interval_hours"])
        except Exception as e:
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Error calculating funding time: {e}")
            return

        tab_data["funding_info_label"].setText(f"{translations[self.language]['funding_info_label'].split(':')[0]}: {funding_rate:.4f}% | {translations[self.language]['funding_info_label'].split('|')[1].strip()}: {time_str}")
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Time to next funding for {symbol}: {time_str}")

        # Фіксуємо ціну за 1 секунду до фандингу
        if 0.5 <= time_to_funding <= 1.5 and tab_data["pre_funding_price"] is None:
            tab_data["pre_funding_price"] = get_current_price(tab_data["session"], symbol, tab_data["exchange"])
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Captured pre-funding price for {symbol}: {tab_data['pre_funding_price']}")

        if tab_data["entry_time_seconds"] - 1.0 <= time_to_funding <= tab_data["entry_time_seconds"] and not tab_data["open_order_id"]:
            side = "Buy" if funding_rate > 0 else "Sell"
            tab_data["open_order_id"] = place_market_order(tab_data["session"], symbol, side, tab_data["qty"], tab_data["exchange"])
            if tab_data["open_order_id"]:
                QTimer.singleShot(int((time_to_funding - 0.5) * 1000), lambda: self.capture_tab_funding_price(tab_data, symbol, side))
            tab_data["pre_funding_price"] = None  # Скидаємо після входу в угоду

    def capture_tab_funding_price(self, tab_data, symbol, side):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping funding price capture")
            return

        tab_index = self.tab_data_list.index(tab_data) + 1

        # Отримання трьох цін
        entry_price = get_order_execution_price(tab_data["session"], symbol, tab_data["open_order_id"], tab_data["exchange"])
        candle_price = get_candle_open_price(tab_data["session"], symbol, tab_data["exchange"])
        pre_funding_price = tab_data["pre_funding_price"]

        print(f"Tab {tab_index}: Prices for {symbol} - Entry: {entry_price}, Candle: {candle_price}, Pre-Funding: {pre_funding_price}")

        # Валідація цін
        prices = [p for p in [entry_price, candle_price, pre_funding_price] if p is not None]
        if not prices:
            print(f"Tab {tab_index}: No valid prices available for {symbol}, cancelling order")
            tab_data["open_order_id"] = None
            return

        # Перевірка розбіжності цін
        max_diff_percentage = 0.5  # Максимальна допустима різниця між цінами (0.5%)
        if len(prices) > 1:
            avg_price = sum(prices) / len(prices)
            deviations = [abs(p - avg_price) / avg_price * 100 for p in prices]
            if max(deviations) > max_diff_percentage:
                # Виключаємо ціну з найбільшою відхиленням
                valid_prices = [p for i, p in enumerate(prices) if deviations[i] <= max_diff_percentage]
                if valid_prices:
                    selected_price = sum(valid_prices) / len(valid_prices)
                else:
                    selected_price = candle_price or avg_price  # Повертаємося до ціни свічки
                warning = QMessageBox()
                warning.setWindowTitle(translations[self.language]["price_validation_warning_title"])
                warning.setText(translations[self.language]["price_validation_warning_text"].format(
                    symbol=symbol,
                    entry_price=entry_price or 0.0,
                    candle_price=candle_price or 0.0,
                    pre_funding_price=pre_funding_price or 0.0,
                    selected_price=selected_price
                ))
                warning.exec()
            else:
                selected_price = avg_price
        else:
            selected_price = prices[0]

        tab_data["funding_time_price"] = selected_price
        print(f"Tab {tab_index}: Selected price for {symbol}: {selected_price:.6f}")

        tick_size = get_symbol_info(tab_data["session"], symbol, tab_data["exchange"])

        # Розрахунок лімітної ціни
        target_limit_price = (selected_price * (1 + tab_data["profit_percentage"] / 100) if side == "Buy"
                            else selected_price * (1 - tab_data["profit_percentage"] / 100))

        if tab_data["auto_limit"]:
            limit_price = get_optimal_limit_price(
                tab_data["session"],
                symbol,
                side,
                selected_price,
                tab_data["exchange"],
                tab_data["profit_percentage"],
                tick_size
            )
            if limit_price is not None:
                actual_profit = ((selected_price - limit_price) / selected_price * 100 if side == "Sell"
                                else (limit_price - selected_price) / selected_price * 100)
                if abs(actual_profit - tab_data["profit_percentage"]) > 0.1:
                    print(f"Tab {tab_index}: Optimal limit price {limit_price} gives {actual_profit:.2f}% profit, falling back to manual calculation")
                    limit_price = target_limit_price
            else:
                print(f"Tab {tab_index}: Failed to determine optimal limit price for {symbol}, using manual calculation")
                limit_price = target_limit_price
        else:
            limit_price = target_limit_price

        if tick_size:
            decimal_places = abs(int(math.log10(tick_size)))
            limit_price = round(limit_price, decimal_places)

        tab_data["limit_price"] = limit_price
        print(f"Tab {tab_index}: Calculated limit price for {symbol}: {limit_price:.6f} (selected_price: {selected_price:.6f}, profit_percentage: {tab_data['profit_percentage']}%")
        order_id = place_limit_close_order(tab_data["session"], symbol, side, tab_data["qty"], limit_price, tick_size, tab_data["exchange"])
        tab_data["open_order_id"] = None

        if tab_data["stop_loss_enabled"] and tab_data["stop_loss_percentage"] > 0:
            stop_price = (selected_price * (1 - tab_data["stop_loss_percentage"] / 100) if side == "Buy"
                        else selected_price * (1 + tab_data["stop_loss_percentage"] / 100))
            if tick_size:
                decimal_places = abs(int(math.log10(tick_size)))
                stop_price = round(stop_price, decimal_places)
            print(f"Tab {tab_index}: Placing stop-loss order for {symbol} at {stop_price}...")
            stop_order_id = place_stop_loss_order(tab_data["session"], symbol, side, tab_data["qty"], stop_price, tick_size, tab_data["exchange"])
            if stop_order_id:
                print(f"Tab {tab_index}: Stop-loss order placed for {symbol} at {stop_price} with orderId {stop_order_id}")
            else:
                print(f"Tab {tab_index}: Failed to place stop-loss order for {symbol} at {stop_price}")
        else:
            print(f"Tab {tab_index}: Stop-loss disabled or percentage is {tab_data['stop_loss_percentage']}%, skipping stop-loss order")

        QTimer.singleShot(1000, lambda: self.log_limit_price_diff(tab_data, symbol, side))

    def log_limit_price_diff(self, tab_data, symbol, side):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping limit price diff logging")
            return
        tab_index = self.tab_data_list.index(tab_data) + 1
        open_price = tab_data["funding_time_price"]
        limit_price = tab_data.get("limit_price")
        if open_price is None or limit_price is None:
            print(f"Tab {tab_index}: Failed to log limit price difference for {symbol}: open_price={open_price}, limit_price={limit_price}")
            return
        if side == "Sell":
            profit_percentage = (open_price - limit_price) / open_price * 100
        else:
            profit_percentage = (limit_price - open_price) / open_price * 100
        print(f"Tab {tab_index}: {symbol} | Open price: {open_price:.6f} | Limit price: {limit_price:.6f} | Profit percentage: {profit_percentage:.4f}% | Expected profit: {tab_data['profit_percentage']}%")
        if abs(profit_percentage - tab_data["profit_percentage"]) > 0.5:
            warning = QMessageBox()
            warning.setWindowTitle(translations[self.language]["price_mismatch_warning_title"])
            warning.setText(translations[self.language]["price_mismatch_warning_text"].format(
                symbol=symbol, actual_profit=profit_percentage, expected_profit=tab_data["profit_percentage"]))
            warning.exec()

    def handle_tab_close_all_trades(self, tab_data):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping close all trades")
            return
        warning = QMessageBox()
        warning.setWindowTitle(translations[self.language]["close_all_trades_warning_title"])
        warning.setText(translations[self.language]["close_all_trades_warning_text"])
        warning.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        warning.setDefaultButton(QMessageBox.StandardButton.No)
        if self.language == "uk":
            warning.button(QMessageBox.StandardButton.Yes).setText("Так")
            warning.button(QMessageBox.StandardButton.No).setText("Ні")
        else:
            warning.button(QMessageBox.StandardButton.Yes).setText("Yes")
            warning.button(QMessageBox.StandardButton.No).setText("No")

        if warning.exec() == QMessageBox.StandardButton.Yes:
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Calling close_all_positions for {tab_data['exchange']} with symbol {tab_data['selected_symbol']}")
            success = close_all_positions(tab_data["session"], tab_data["exchange"], symbol=tab_data["selected_symbol"])
            result = QMessageBox()
            if success:
                tab_data["open_order_id"] = None
                result.setWindowTitle("Success" if self.language == "en" else "Успіх")
                result.setText(translations[self.language]["close_all_trades_success"])
            else:
                result.setWindowTitle("Error" if self.language == "en" else "Помилка")
                result.setText(translations[self.language]["close_all_trades_error"].format("No positions found or API error"))
            result.exec()
            self.update_tab_funding_data(tab_data)

    def update_tab_funding_data(self, tab_data, retry_count=3, retry_delay=2):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping funding data update")
            return
        for attempt in range(retry_count):
            try:
                tab_index = self.tab_data_list.index(tab_data) + 1
                print(f"Tab {tab_index}: Updating funding data (attempt {attempt + 1}/{retry_count})...")
                tab_data["funding_data"] = get_funding_data(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])

                current_price = get_current_price(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])
                if current_price is not None:
                    tab_data["price_label"].setText(f"{translations[self.language]['price_label'].split(':')[0]}: ${current_price:.6f}")
                else:
                    tab_data["price_label"].setText(translations[self.language]["price_label"])

                balance = get_account_balance(tab_data["session"], tab_data["exchange"])
                if balance is not None:
                    tab_data["balance_label"].setText(f"{translations[self.language]['balance_label'].split(':')[0]}: ${balance:.2f} USDT")
                    self.update_tab_leveraged_balance_label(tab_data)
                else:
                    tab_data["balance_label"].setText(translations[self.language]["balance_label"])
                    tab_data["leveraged_balance_label"].setText(translations[self.language]["leveraged_balance_label"])

                if tab_data["funding_data"]:
                    funding_rate = tab_data["funding_data"]["funding_rate"]
                    funding_time = tab_data["funding_data"]["funding_time"]
                    _, time_str = get_next_funding_time(funding_time, tab_data["funding_interval_hours"])
                    tab_data["funding_info_label"].setText(f"{translations[self.language]['funding_info_label'].split(':')[0]}: {funding_rate:.4f}% | {translations[self.language]['funding_info_label'].split('|')[1].strip()}: {time_str}")
                else:
                    tab_data["funding_info_label"].setText(translations[self.language]["funding_info_label"])
                    tab_data["price_label"].setText(translations[self.language]["price_label"])
                    tab_data["balance_label"].setText(translations[self.language]["balance_label"])
                    tab_data["leveraged_balance_label"].setText(translations[self.language]["leveraged_balance_label"])
                    tab_data["volume_label"].setText(translations[self.language]["volume_label"])
                    tab_data["volume_label"].setStyleSheet("color: black;")
                    tab_data["ping_label"].setText(translations[self.language]["ping_label"])
                    tab_data["ping_label"].setStyleSheet("color: black;")

                self.update_tab_volume_label(tab_data)
                self.update_tab_ping(tab_data)

                print(f"Tab {tab_index}: Data updated successfully")
                return

            except Exception as e:
                tab_index = self.tab_data_list.index(tab_data) + 1 if tab_data in self.tab_data_list else "Unknown"
                print(f"Tab {tab_index}: Error updating funding data (attempt {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                else:
                    tab_data["funding_info_label"].setText(f"{translations[self.language]['funding_info_label'].split(':')[0]}: Error | {translations[self.language]['funding_info_label'].split('|')[1].strip()}: Error")
                    tab_data["price_label"].setText(f"{translations[self.language]['price_label'].split(':')[0]}: Error")
                    tab_data["balance_label"].setText(f"{translations[self.language]['balance_label'].split(':')[0]}: Error")
                    tab_data["leveraged_balance_label"].setText(f"{translations[self.language]['leveraged_balance_label'].split(':')[0]}: Error")
                    tab_data["volume_label"].setText(f"{translations[self.language]['volume_label'].split(':')[0]}: Error")
                    tab_data["volume_label"].setStyleSheet("color: black;")
                    tab_data["ping_label"].setText(f"{translations[self.language]['ping_label'].split(':')[0]}: Error")
                    tab_data["ping_label"].setStyleSheet("color: red;")

    def closeEvent(self, event):
        for tab_data in self.tab_data_list:
            tab_data["timer"].stop()
            tab_data["ping_timer"].stop()
        self.save_settings()
        event.accept()