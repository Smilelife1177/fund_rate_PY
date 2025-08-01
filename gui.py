import os
import json
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel, QDoubleSpinBox, QSlider, QComboBox, QCheckBox, QMessageBox, QTabWidget, QToolButton
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon
from logic import get_account_balance, get_funding_data, get_current_price, get_next_funding_time, place_market_order, get_symbol_info, place_limit_close_order, update_ping, initialize_client, close_all_positions, get_optimal_limit_price, get_candle_open_price, place_stop_loss_order
from PyQt6.QtWidgets import QTabBar
import time
import math

class FundingTraderApp(QMainWindow):
    translations = {
        "en": {
            "window_title": "{} Funding Trader",
            "exchange_label": "Exchange:",
            "testnet_label": "Testnet Mode:",
            "testnet_checkbox": "Enable Testnet",
            "coin_input_label": "Enter Coin (e.g., BTCUSDT):",
            "update_coin_button": "Update Coin",
            "funding_interval_label": "Funding Interval (hours):",
            "entry_time_label": "Entry Time Before Funding (seconds):",
            "qty_label": "Order Quantity (qty):",
            "profit_percentage_label": "Desired Profit Percentage (%):",
            "auto_limit_label": "Automatic Limit Order:",
            "auto_limit_checkbox": "Enable Auto Limit",
            "leverage_label": "Leverage (x):",
            "stop_loss_percentage_label": "Stop Loss Percentage (%):",  # New translation
            "funding_info_label": "Funding Rate: N/A | Time to Next Funding: N/A",
            "price_label": "Current Price: N/A",
            "balance_label": "Account Balance: N/A",
            "leveraged_balance_label": "Leveraged Balance: N/A",
            "volume_label": "Order Volume: N/A",
            "ping_label": "Ping: N/A",
            "refresh_button": "Refresh Data",
            "language_label": "Language:",
            "close_all_trades_button": "Close All Trades",
            "close_all_trades_warning_title": "Confirm Close All Trades",
            "close_all_trades_warning_text": "Are you sure you want to close all open trades? This action cannot be undone.",
            "close_all_trades_success": "All open trades have been closed.",
            "close_all_trades_no_positions": "No open trades to close.",
            "close_all_trades_error": "Error closing trades: {}",
            "new_tab_button": "New Tab",
            "tab_title": "Coin {}"
        },
        "uk": {
            "window_title": "{} Трейдер Фінансування",
            "exchange_label": "Біржа:",
            "testnet_label": "Режим тестування:",
            "testnet_checkbox": "Увімкнути тестовий режим",
            "coin_input_label": "Введіть монету (наприклад, BTCUSDT):",
            "update_coin_button": "Оновити монету",
            "funding_interval_label": "Інтервал фінансування (години):",
            "entry_time_label": "Час входу до фінансування (секунди):",
            "qty_label": "Кількість замовлення (qty):",
            "profit_percentage_label": "Бажаний відсоток прибутку (%):",
            "auto_limit_label": "Автоматичний лімітний ордер:",
            "auto_limit_checkbox": "Увімкнути автоматичний ліміт",
            "leverage_label": "Кредитне плече (x):",
            "stop_loss_percentage_label": "Відсоток стоп-лоссу (%):",  # New translation
            "funding_info_label": "Ставка фінансування: N/A | Час до наступного фінансування: N/A",
            "price_label": "Поточна ціна: N/A",
            "balance_label": "Баланс рахунку: N/A",
            "leveraged_balance_label": "Баланс з урахуванням плеча: N/A",
            "volume_label": "Обсяг замовлення: N/A",
            "ping_label": "Пінг: N/A",
            "refresh_button": "Оновити дані",
            "language_label": "Мова:",
            "close_all_trades_button": "Закрити всі угоди",
            "close_all_trades_warning_title": "Підтвердження закриття всіх угод",
            "close_all_trades_warning_text": "Ви впевнені, що хочете закрити всі відкриті угоди? Цю дію неможливо скасувати.",
            "close_all_trades_success": "Усі відкриті угоди закрито.",
            "close_all_trades_no_positions": "Немає відкритих угод для закриття.",
            "close_all_trades_error": "Помилка при закритті угод: {}",
            "new_tab_button": "Нова вкладка",
            "tab_title": "Монета {}"
        }
    }

    def __init__(self, session, testnet, exchange):
        super().__init__()
        self.language = "en"  # Default to English
        self.setWindowTitle(self.translations[self.language]["window_title"].format(exchange))
        self.setGeometry(100, 100, 400, 600)

        icon_path = r"images\log.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Icon file not found at: {icon_path}")

        # Initialize main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Language selector
        self.language_label = QLabel(self.translations[self.language]["language_label"])
        self.language_combobox = QComboBox()
        self.language_combobox.addItems(["English", "Українська"])
        self.language_combobox.setCurrentText("English" if self.language == "en" else "Українська")
        self.language_combobox.currentTextChanged.connect(self.update_language)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        # List to store tab_data for each tab
        self.tab_data_list = []

        # Add new tab button as a tab
        self.add_tab_button = QToolButton()
        self.add_tab_button.setText("+")
        self.add_tab_button.setFixedWidth(30)
        self.add_tab_button.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.add_tab_button.clicked.connect(self.add_new_tab)
        self.tab_widget.addTab(QWidget(), "+")
        self.tab_widget.setTabEnabled(self.tab_widget.count() - 1, False)
        self.tab_widget.tabBar().setTabButton(self.tab_widget.count() - 1, QTabBar.ButtonPosition.RightSide, self.add_tab_button)

        # Add initial tab with loaded settings
        self.tab_count = 0
        loaded_settings = self.load_settings()
        initial_settings = loaded_settings[0] if loaded_settings else None
        self.add_new_tab(
            session=session,
            testnet=testnet,
            exchange=exchange,
            settings=initial_settings
        )

        # Update data for all tabs after initialization
        for tab_data in self.tab_data_list:
            self.update_tab_funding_data(tab_data)

        # Add widgets to main layout
        self.main_layout.addWidget(self.language_label)
        self.main_layout.addWidget(self.language_combobox)
        self.main_layout.addWidget(self.tab_widget)

        # Save settings
        self.save_settings()

    def add_new_tab(self, session=None, testnet=None, exchange=None, settings=None):
        """Add a new tab with its own settings and UI."""
        self.tab_count += 1
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_data = self.create_tab_ui(tab_layout, session, testnet, exchange, settings)
        self.tab_data_list.append(tab_data)
        self.tab_widget.insertTab(self.tab_widget.count() - 1, tab, self.translations[self.language]["tab_title"].format(self.tab_count))
        self.tab_widget.setCurrentWidget(tab)
        tab_data["tab_index"] = self.tab_count
        return tab_data

    def create_tab_ui(self, layout, session, testnet, exchange, settings=None):
        """Create UI elements for a single tab."""
        # Load default settings or use provided settings
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
            "stop_loss_percentage": 0.5  # New default setting
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
            "stop_loss_percentage": default_settings["stop_loss_percentage"],  # New setting
            "funding_data": None,
            "open_order_id": None,
            "funding_time_price": None,
            "limit_price": None
        }

        # Exchange selector
        exchange_label = QLabel(self.translations[self.language]["exchange_label"])
        exchange_combobox = QComboBox()
        exchange_combobox.addItems(["Bybit", "Binance"])
        exchange_combobox.setCurrentText(tab_data["exchange"])
        exchange_combobox.currentTextChanged.connect(lambda value: self.update_tab_exchange(tab_data, value))

        # Testnet toggle
        testnet_label = QLabel(self.translations[self.language]["testnet_label"])
        testnet_checkbox = QCheckBox(self.translations[self.language]["testnet_checkbox"])
        testnet_checkbox.setChecked(tab_data["testnet"])
        testnet_checkbox.stateChanged.connect(lambda state: self.update_tab_testnet(tab_data, state))

        # Coin input
        coin_input_label = QLabel(self.translations[self.language]["coin_input_label"])
        coin_input = QLineEdit()
        coin_input.setText(tab_data["selected_symbol"])
        
        update_coin_button = QPushButton(self.translations[self.language]["update_coin_button"])
        update_coin_button.clicked.connect(lambda: self.update_tab_symbol(tab_data, coin_input.text()))

        # Funding interval
        funding_interval_label = QLabel(self.translations[self.language]["funding_interval_label"])
        funding_interval_combobox = QComboBox()
        funding_intervals = ["0.01", "1", "4", "8"] if tab_data["exchange"] == "Bybit" else ["8"]
        funding_interval_combobox.addItems(funding_intervals)
        formatted_interval = str(float(tab_data["funding_interval_hours"]))
        if formatted_interval.endswith(".0"):
            formatted_interval = formatted_interval[:-2]
        funding_interval_combobox.setCurrentText(formatted_interval)
        funding_interval_combobox.currentTextChanged.connect(lambda value: self.update_tab_funding_interval(tab_data, value))

        # Entry time
        entry_time_label = QLabel(self.translations[self.language]["entry_time_label"])
        entry_time_spinbox = QDoubleSpinBox()
        entry_time_spinbox.setRange(0.5, 60.0)
        entry_time_spinbox.setValue(tab_data["entry_time_seconds"])
        entry_time_spinbox.setSingleStep(0.1)
        entry_time_spinbox.valueChanged.connect(lambda value: self.update_tab_entry_time(tab_data, value))

        # Quantity
        qty_label = QLabel(self.translations[self.language]["qty_label"])
        qty_spinbox = QDoubleSpinBox()
        qty_spinbox.setRange(0.001, 10000.0)
        qty_spinbox.setValue(tab_data["qty"])
        qty_spinbox.setSingleStep(0.001)
        qty_spinbox.valueChanged.connect(lambda value: self.update_tab_qty(tab_data, value))

        # Profit percentage
        profit_percentage_label = QLabel(self.translations[self.language]["profit_percentage_label"])
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

        # Automatic limit order toggle
        auto_limit_label = QLabel(self.translations[self.language]["auto_limit_label"])
        auto_limit_checkbox = QCheckBox(self.translations[self.language]["auto_limit_checkbox"])
        auto_limit_checkbox.setChecked(tab_data["auto_limit"])
        auto_limit_checkbox.stateChanged.connect(lambda state: self.update_tab_auto_limit(tab_data, state))

        # Leverage
        leverage_label = QLabel(self.translations[self.language]["leverage_label"])
        leverage_spinbox = QDoubleSpinBox()
        leverage_spinbox.setRange(1.0, 100.0)
        leverage_spinbox.setValue(tab_data["leverage"])
        leverage_spinbox.setSingleStep(0.1)
        leverage_spinbox.valueChanged.connect(lambda value: self.update_tab_leverage(tab_data, value))

        # Stop loss percentage
        stop_loss_percentage_label = QLabel(self.translations[self.language]["stop_loss_percentage_label"])
        stop_loss_percentage_spinbox = QDoubleSpinBox()
        stop_loss_percentage_spinbox.setRange(0.1, 10.0)
        stop_loss_percentage_spinbox.setValue(tab_data["stop_loss_percentage"])
        stop_loss_percentage_spinbox.setSingleStep(0.1)
        stop_loss_percentage_spinbox.valueChanged.connect(lambda value: self.update_tab_stop_loss_percentage(tab_data, value))

        # Info labels
        funding_info_label = QLabel(self.translations[self.language]["funding_info_label"])
        price_label = QLabel(self.translations[self.language]["price_label"])
        balance_label = QLabel(self.translations[self.language]["balance_label"])
        leveraged_balance_label = QLabel(self.translations[self.language]["leveraged_balance_label"])
        volume_label = QLabel(self.translations[self.language]["volume_label"])
        ping_label = QLabel(self.translations[self.language]["ping_label"])

        # Refresh button
        refresh_button = QPushButton(self.translations[self.language]["refresh_button"])
        refresh_button.clicked.connect(lambda: self.update_tab_funding_data(tab_data))

        # Close all trades button
        close_all_trades_button = QPushButton(self.translations[self.language]["close_all_trades_button"])
        close_all_trades_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        close_all_trades_button.clicked.connect(lambda: self.handle_tab_close_all_trades(tab_data))

        # Add widgets to layout
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

        # Store UI elements in tab_data
        tab_data.update({
            "exchange_label": exchange_label,
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
            "stop_loss_percentage_label": stop_loss_percentage_label,
            "stop_loss_percentage_spinbox": stop_loss_percentage_spinbox,
            "funding_info_label": funding_info_label,
            "price_label": price_label,
            "balance_label": balance_label,
            "leveraged_balance_label": leveraged_balance_label,
            "volume_label": volume_label,
            "ping_label": ping_label,
            "refresh_button": refresh_button,
            "close_all_trades_button": close_all_trades_button,
        })

        # Timers for the tab
        timer = QTimer()
        timer.timeout.connect(lambda: self.check_tab_funding_time(tab_data))
        timer.start(1000)

        ping_timer = QTimer()
        ping_timer.timeout.connect(lambda: self.update_tab_ping(tab_data))
        ping_timer.start(30000)

        tab_data["timer"] = timer
        tab_data["ping_timer"] = ping_timer

        # Initial data update
        self.update_tab_funding_data(tab_data)
        print(f"Created UI for tab {self.tab_count}")
        return tab_data

    def close_tab(self, index):
        """Close a tab and stop its timers."""
        if self.tab_widget.count() > 1:  # Prevent closing the last tab
            tab_data = self.tab_data_list[index]
            tab_data["timer"].stop()
            tab_data["ping_timer"].stop()
            self.tab_widget.removeTab(index)
            self.tab_data_list.pop(index)
            print(f"Closed tab {index + 1}")
            self.save_settings()

    def load_settings(self):
        """Load settings from settings.json or set defaults."""
        default_settings = {
            "tabs": [{
                "selected_symbol": "HYPERUSDT",
                "funding_interval_hours": 1.0,
                "entry_time_seconds": 5.0,
                "qty": 45.0,
                "profit_percentage": 1.0,
                "leverage": 1.0,
                "exchange": "Bybit",
                "testnet": False,
                "auto_limit": False,
                "stop_loss_percentage": 0.5  # New default setting
            }],
            "language": "en"
        }
        try:
            if os.path.exists(r"scripts\settings.json"):
                with open(r"scripts\settings.json", "r") as f:
                    settings = json.load(f)
                    self.language = settings.get("language", default_settings["language"])
                    tabs = settings.get("tabs", default_settings["tabs"])
                    return tabs
            else:
                print("No settings file found, using defaults")
                return default_settings["tabs"]
        except Exception as e:
            print(f"Error loading settings: {e}, using defaults")
            return default_settings["tabs"]

    def save_settings(self):
        """Save current settings to settings.json."""
        tabs = []
        for tab_data in self.tab_data_list:
            tabs.append({
                "selected_symbol": tab_data["selected_symbol"],
                "funding_interval_hours": tab_data["funding_interval_hours"],
                "entry_time_seconds": tab_data["entry_time_seconds"],
                "qty": tab_data["qty"],
                "profit_percentage": tab_data["profit_percentage"],
                "leverage": tab_data["leverage"],
                "exchange": tab_data["exchange"],
                "testnet": tab_data["testnet"],
                "auto_limit": tab_data["auto_limit"],
                "stop_loss_percentage": tab_data["stop_loss_percentage"]  # New setting
            })
        settings = {
            "tabs": tabs,
            "language": self.language
        }
        try:
            with open(r"scripts\settings.json", "w") as f:
                json.dump(settings, f, indent=4)
                print("Settings saved successfully")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def update_language(self, language_text):
        """Update the language of the UI."""
        self.language = "en" if language_text == "English" else "uk"
        print(f"Updated language: {self.language}")
        self.setWindowTitle(self.translations[self.language]["window_title"].format("Multi-Coin"))
        self.language_label.setText(self.translations[self.language]["language_label"])
        for tab_data in self.tab_data_list:
            tab_data["exchange_label"].setText(self.translations[self.language]["exchange_label"])
            tab_data["testnet_label"].setText(self.translations[self.language]["testnet_label"])
            tab_data["testnet_checkbox"].setText(self.translations[self.language]["testnet_checkbox"])
            tab_data["coin_input_label"].setText(self.translations[self.language]["coin_input_label"])
            tab_data["update_coin_button"].setText(self.translations[self.language]["update_coin_button"])
            tab_data["funding_interval_label"].setText(self.translations[self.language]["funding_interval_label"])
            tab_data["entry_time_label"].setText(self.translations[self.language]["entry_time_label"])
            tab_data["qty_label"].setText(self.translations[self.language]["qty_label"])
            tab_data["profit_percentage_label"].setText(self.translations[self.language]["profit_percentage_label"])
            tab_data["auto_limit_label"].setText(self.translations[self.language]["auto_limit_label"])
            tab_data["auto_limit_checkbox"].setText(self.translations[self.language]["auto_limit_checkbox"])
            tab_data["leverage_label"].setText(self.translations[self.language]["leverage_label"])
            tab_data["stop_loss_percentage_label"].setText(self.translations[self.language]["stop_loss_percentage_label"])
            tab_data["close_all_trades_button"].setText(self.translations[self.language]["close_all_trades_button"])
            self.update_tab_funding_data(tab_data)
        self.save_settings()

    def update_tab_exchange(self, tab_data, exchange):
        """Update exchange for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["exchange"] = exchange
        tab_data["funding_interval_hours"] = 1.0 if exchange == "Bybit" else 8.0
        tab_data["funding_interval_combobox"].blockSignals(True)
        tab_data["funding_interval_combobox"].clear()
        funding_intervals = ["0.01", "1", "4", "8"] if exchange == "Bybit" else ["8"]
        tab_data["funding_interval_combobox"].addItems(funding_intervals)
        formatted_interval = str(float(tab_data["funding_interval_hours"]))
        if formatted_interval.endswith(".0"):
            formatted_interval = formatted_interval[:-2]
        tab_data["funding_interval_combobox"].setCurrentText(formatted_interval)
        tab_data["funding_interval_combobox"].blockSignals(False)
        tab_data["session"] = initialize_client(tab_data["exchange"], tab_data["testnet"])
        self.save_settings()
        self.update_tab_funding_data(tab_data)
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Switched to exchange: {exchange}")

    def update_tab_testnet(self, tab_data, state):
        """Update testnet mode for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["testnet"] = state == Qt.CheckState.Checked.value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Testnet mode: {'Enabled' if tab_data['testnet'] else 'Disabled'}")
        tab_data["session"] = initialize_client(tab_data["exchange"], tab_data["testnet"])
        self.save_settings()
        self.update_tab_funding_data(tab_data)

    def update_tab_symbol(self, tab_data, symbol):
        """Update symbol for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["selected_symbol"] = symbol.strip().upper()
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated symbol: {tab_data['selected_symbol']}")
        self.tab_widget.setTabText(self.tab_data_list.index(tab_data), f"{tab_data['selected_symbol']}")
        self.save_settings()
        self.update_tab_funding_data(tab_data)

    def update_tab_funding_interval(self, tab_data, value):
        """Update funding interval for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        if value:
            tab_data["funding_interval_hours"] = float(value)
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated funding interval: {tab_data['funding_interval_hours']} hours")
            self.save_settings()
            self.update_tab_funding_data(tab_data)

    def update_tab_entry_time(self, tab_data, value):
        """Update entry time for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["entry_time_seconds"] = value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated entry time: {tab_data['entry_time_seconds']} seconds")
        self.save_settings()

    def update_tab_qty(self, tab_data, value):
        """Update order quantity for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["qty"] = value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated order quantity: {tab_data['qty']}")
        self.save_settings()
        self.update_tab_volume_label(tab_data)

    def update_tab_profit_percentage(self, tab_data, value):
        """Update profit percentage for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["profit_percentage"] = value
        tab_data["profit_percentage_slider"].setValue(int(value * 100))
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated profit percentage: {tab_data['profit_percentage']}%")
        self.save_settings()

    def update_tab_profit_percentage_from_slider(self, tab_data, value):
        """Update profit percentage from slider for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["profit_percentage"] = value / 100.0
        tab_data["profit_percentage_spinbox"].setValue(tab_data["profit_percentage"])
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated profit percentage from slider: {tab_data['profit_percentage']}%")
        self.save_settings()

    def update_tab_auto_limit(self, tab_data, state):
        """Update automatic limit order setting for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["auto_limit"] = state == Qt.CheckState.Checked.value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Auto limit mode: {'Enabled' if tab_data['auto_limit'] else 'Disabled'}")
        self.save_settings()

    def update_tab_leverage(self, tab_data, value):
        """Update leverage for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["leverage"] = value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated leverage: {tab_data['leverage']}x")
        self.save_settings()
        self.update_tab_leveraged_balance_label(tab_data)

    def update_tab_stop_loss_percentage(self, tab_data, value):
        """Update stop loss percentage for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["stop_loss_percentage"] = value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated stop loss percentage: {tab_data['stop_loss_percentage']}%")
        self.save_settings()

    def update_tab_volume_label(self, tab_data):
        """Update volume label for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        current_price = get_current_price(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])
        balance = get_account_balance(tab_data["session"], tab_data["exchange"])
        leveraged_balance = balance * tab_data["leverage"] if balance is not None and tab_data["leverage"] is not None else None
        if current_price is not None and tab_data["qty"] is not None:
            volume = tab_data["qty"] * current_price
            tab_data["volume_label"].setText(f"{self.translations[self.language]['volume_label'].split(':')[0]}: ${volume:.2f} USD")
            if volume < 5.0 or (leveraged_balance is not None and volume > leveraged_balance):
                tab_data["volume_label"].setStyleSheet("color: red;")
            else:
                tab_data["volume_label"].setStyleSheet("color: black;")
        else:
            tab_data["volume_label"].setText(self.translations[self.language]["volume_label"])
            tab_data["volume_label"].setStyleSheet("color: black;")

    def update_tab_leveraged_balance_label(self, tab_data):
        """Update leveraged balance label for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        balance = get_account_balance(tab_data["session"], tab_data["exchange"])
        if balance is not None and tab_data["leverage"] is not None:
            leveraged_balance = balance * tab_data["leverage"]
            tab_data["leveraged_balance_label"].setText(f"{self.translations[self.language]['leveraged_balance_label'].split(':')[0]}: ${leveraged_balance:.2f} USDT")
        else:
            tab_data["leveraged_balance_label"].setText(self.translations[self.language]["leveraged_balance_label"])

    def update_tab_ping(self, tab_data):
        """Update ping for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        update_ping(tab_data["session"], tab_data["ping_label"], tab_data["exchange"])

    def check_tab_funding_time(self, tab_data):
        """Check funding time for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping funding check")
            return
        if not tab_data["funding_data"] or not all(key in tab_data["funding_data"] for key in ["symbol", "funding_rate", "funding_time"]):
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Funding data unavailable or incomplete")
            tab_data["funding_info_label"].setText(self.translations[self.language]["funding_info_label"])
            tab_data["price_label"].setText(self.translations[self.language]["price_label"])
            tab_data["balance_label"].setText(self.translations[self.language]["balance_label"])
            tab_data["leveraged_balance_label"].setText(self.translations[self.language]["leveraged_balance_label"])
            tab_data["volume_label"].setText(self.translations[self.language]["volume_label"])
            tab_data["volume_label"].setStyleSheet("color: black;")
            tab_data["ping_label"].setText(self.translations[self.language]["ping_label"])
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

        tab_data["funding_info_label"].setText(f"{self.translations[self.language]['funding_info_label'].split(':')[0]}: {funding_rate:.4f}% | {self.translations[self.language]['funding_info_label'].split('|')[1].strip()}: {time_str}")
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Time to next funding for {symbol}: {time_str}")

        if tab_data["entry_time_seconds"] - 1.0 <= time_to_funding <= tab_data["entry_time_seconds"] and not tab_data["open_order_id"]:
            side = "Buy" if funding_rate > 0 else "Sell"
            tab_data["open_order_id"] = place_market_order(tab_data["session"], symbol, side, tab_data["qty"], tab_data["exchange"])
            if tab_data["open_order_id"]:
                QTimer.singleShot(int((time_to_funding - 1.0) * 1000), lambda: self.capture_tab_funding_price(tab_data, symbol, side))

    def log_limit_price_diff(self, tab_data, symbol, side):
        """Log the percentage difference between the 1-minute candle open price and the limit price."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping limit price diff logging")
            return
        tab_index = self.tab_data_list.index(tab_data) + 1
        open_price = get_candle_open_price(tab_data["session"], symbol, tab_data["exchange"])
        limit_price = tab_data.get("limit_price")
        if open_price is None or limit_price is None:
            print(f"Tab {tab_index}: Failed to log limit price difference for {symbol}: open_price={open_price}, limit_price={limit_price}")
            return
        if side == "Sell":
            # For Sell position, limit order is Buy, so limit_price is below open_price
            profit_percentage = (open_price - limit_price) / open_price * 100
        else:
            # For Buy position, limit order is Sell, so limit_price is above open_price
            profit_percentage = (limit_price - open_price) / open_price * 100
        print(f"Tab {tab_index}: {symbol} | Open price (1m candle): {open_price:.6f} | Limit price: {limit_price:.6f} | Profit percentage: {profit_percentage:.4f}% | Expected profit: {tab_data['profit_percentage']}%")

    def capture_tab_funding_price(self, tab_data, symbol, side):
        """Capture funding price and place limit and stop-loss orders for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping funding price capture")
            return
        tab_data["funding_time_price"] = get_current_price(tab_data["session"], symbol, tab_data["exchange"])
        if tab_data["funding_time_price"] is None:
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Failed to get price at funding time for {symbol}")
            tab_data["open_order_id"] = None
            return

        tick_size = get_symbol_info(tab_data["session"], symbol, tab_data["exchange"])
        if tab_data["auto_limit"]:
            limit_price = get_optimal_limit_price(
                tab_data["session"],
                symbol,
                side,
                tab_data["funding_time_price"],
                tab_data["exchange"],
                tab_data["profit_percentage"],
                tick_size
            )
            if limit_price is None:
                print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Failed to determine optimal limit price for {symbol}, falling back to manual")
                limit_price = (tab_data["funding_time_price"] * (1 + tab_data["profit_percentage"] / 100) if side == "Buy" 
                              else tab_data["funding_time_price"] * (1 - tab_data["profit_percentage"] / 100))
        else:
            limit_price = (tab_data["funding_time_price"] * (1 + tab_data["profit_percentage"] / 100) if side == "Buy" 
                          else tab_data["funding_time_price"] * (1 - tab_data["profit_percentage"] / 100))

        # Round limit price to tick size
        if tick_size:
            decimal_places = abs(int(math.log10(tick_size)))
            limit_price = round(limit_price, decimal_places)

        tab_data["limit_price"] = limit_price
        order_id = place_limit_close_order(tab_data["session"], symbol, side, tab_data["qty"], limit_price, tick_size, tab_data["exchange"])
        tab_data["open_order_id"] = None

        # Place stop-loss order
        stop_price = (tab_data["funding_time_price"] * (1 - tab_data["stop_loss_percentage"] / 100) if side == "Buy" 
                      else tab_data["funding_time_price"] * (1 + tab_data["stop_loss_percentage"] / 100))
        if tick_size:
            decimal_places = abs(int(math.log10(tick_size)))
            stop_price = round(stop_price, decimal_places)
        stop_order_id = place_stop_loss_order(tab_data["session"], symbol, side, tab_data["qty"], stop_price, tick_size, tab_data["exchange"])
        if stop_order_id:
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Stop-loss order placed for {symbol} at {stop_price}")
        else:
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Failed to place stop-loss order for {symbol}")

        QTimer.singleShot(1000, lambda: self.log_limit_price_diff(tab_data, symbol, side))

    def handle_tab_close_all_trades(self, tab_data):
        """Handle close all trades for a specific tab."""
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping close all trades")
            return
        warning = QMessageBox()
        warning.setWindowTitle(self.translations[self.language]["close_all_trades_warning_title"])
        warning.setText(self.translations[self.language]["close_all_trades_warning_text"])
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
                result.setText(self.translations[self.language]["close_all_trades_success"])
            else:
                result.setWindowTitle("Error" if self.language == "en" else "Помилка")
                result.setText(self.translations[self.language]["close_all_trades_error"].format("No positions found or API error"))
            result.exec()
            self.update_tab_funding_data(tab_data)

    def update_tab_funding_data(self, tab_data, retry_count=3, retry_delay=2):
        """Update funding data for a specific tab with retry mechanism."""
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
                    tab_data["price_label"].setText(f"{self.translations[self.language]['price_label'].split(':')[0]}: ${current_price:.6f}")
                else:
                    tab_data["price_label"].setText(self.translations[self.language]["price_label"])

                balance = get_account_balance(tab_data["session"], tab_data["exchange"])
                if balance is not None:
                    tab_data["balance_label"].setText(f"{self.translations[self.language]['balance_label'].split(':')[0]}: ${balance:.2f} USDT")
                    self.update_tab_leveraged_balance_label(tab_data)
                else:
                    tab_data["balance_label"].setText(self.translations[self.language]["balance_label"])
                    tab_data["leveraged_balance_label"].setText(self.translations[self.language]["leveraged_balance_label"])

                if tab_data["funding_data"]:
                    funding_rate = tab_data["funding_data"]["funding_rate"]
                    funding_time = tab_data["funding_data"]["funding_time"]
                    _, time_str = get_next_funding_time(funding_time, tab_data["funding_interval_hours"])
                    tab_data["funding_info_label"].setText(f"{self.translations[self.language]['funding_info_label'].split(':')[0]}: {funding_rate:.4f}% | {self.translations[self.language]['funding_info_label'].split('|')[1].strip()}: {time_str}")
                else:
                    tab_data["funding_info_label"].setText(self.translations[self.language]["funding_info_label"])
                    tab_data["price_label"].setText(self.translations[self.language]["price_label"])
                    tab_data["balance_label"].setText(self.translations[self.language]["balance_label"])
                    tab_data["leveraged_balance_label"].setText(self.translations[self.language]["leveraged_balance_label"])
                    tab_data["volume_label"].setText(self.translations[self.language]["volume_label"])
                    tab_data["volume_label"].setStyleSheet("color: black;")
                    tab_data["ping_label"].setText(self.translations[self.language]["ping_label"])
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
                    tab_data["funding_info_label"].setText(f"{self.translations[self.language]['funding_info_label'].split(':')[0]}: Error | {self.translations[self.language]['funding_info_label'].split('|')[1].strip()}: Error")
                    tab_data["price_label"].setText(f"{self.translations[self.language]['price_label'].split(':')[0]}: Error")
                    tab_data["balance_label"].setText(f"{self.translations[self.language]['balance_label'].split(':')[0]}: Error")
                    tab_data["leveraged_balance_label"].setText(f"{self.translations[self.language]['leveraged_balance_label'].split(':')[0]}: Error")
                    tab_data["volume_label"].setText(f"{self.translations[self.language]['volume_label'].split(':')[0]}: Error")
                    tab_data["volume_label"].setStyleSheet("color: black;")
                    tab_data["ping_label"].setText(f"{self.translations[self.language]['ping_label'].split(':')[0]}: Error")
                    tab_data["ping_label"].setStyleSheet("color: red;")

    def closeEvent(self, event):
        """Handle window close event."""
        for tab_data in self.tab_data_list:
            tab_data["timer"].stop()
            tab_data["ping_timer"].stop()
        self.save_settings()
        event.accept()