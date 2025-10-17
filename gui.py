import os
import json
import time
import math
from trade_stats import record_last_closed_trade
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel, QDoubleSpinBox, QSlider, QComboBox, QCheckBox, QMessageBox, QTabWidget, QToolButton
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon
from logic import get_account_balance, get_funding_data, get_current_price, get_next_funding_time, place_market_order, get_symbol_info, place_limit_close_order, update_ping, initialize_client, close_all_positions, get_optimal_limit_price, get_candle_open_price, place_stop_loss_order, get_order_execution_price
from PyQt6.QtWidgets import QTabBar
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl  
from PyQt6.QtWidgets import QScrollArea, QHBoxLayout, QTableWidget, QTableWidgetItem, QButtonGroup
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage


class FundingTraderApp(QMainWindow):
    translations = {
        "en": {
            "window_title": "{} Funding Trader",
            "stop_loss_enabled_label": "Enable Stop Loss:",
            "trade_side_label": "Trade Direction:",
            "stop_loss_enabled_checkbox": "Enable Stop Loss",
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
            "stop_loss_percentage_label": "Stop Loss Percentage (%):",
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
            "tab_title": "Coin {}",
            "price_mismatch_warning_title": "Price Mismatch Warning",
            "price_mismatch_warning_text": "Limit price for {symbol} results in {actual_profit:.2f}% profit, expected {expected_profit:.2f}%",
            "price_validation_warning_title": "Price Validation Warning",
            "price_validation_warning_text": "Significant price discrepancy for {symbol}: Entry={entry_price:.6f}, Candle={candle_price:.6f}, Pre-Funding={pre_funding_price:.6f}. Using {selected_price:.6f}."
        },
        "uk": {
            "window_title": "{} Трейдер Фінансування",
            "exchange_label": "Біржа:",
            "trade_side_label": "Напрямок торгівлі:",
            "stop_loss_enabled_label": "Увімкнути стоп-лосс:",
            "stop_loss_enabled_checkbox": "Увімкнути стоп-лосс",
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
            "stop_loss_percentage_label": "Відсоток стоп-лоссу (%):",
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
            "tab_title": "Монета {}",
            "price_mismatch_warning_title": "Попередження про невідповідність ціни",
            "price_mismatch_warning_text": "Лімітна ціна для {symbol} призводить до прибутку {actual_profit:.2f}%, очікувалось {expected_profit:.2f}%",
            "price_validation_warning_title": "Попередження про перевірку ціни",
            "price_validation_warning_text": "Значна розбіжність цін для {symbol}: Вхід={entry_price:.6f}, Свічка={candle_price:.6f}, Перед фандингом={pre_funding_price:.6f}. Використовується {selected_price:.6f}."
        }
    }
#
    def update_stats_table(self):
        import csv
        if not os.path.exists("trade_stats.csv"):
            self.stats_table.clear()
            return
        
        with open("trade_stats.csv", 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            data = list(reader)
            if not data:
                return
            
            headers = data[0]
            self.stats_table.setColumnCount(len(headers))
            self.stats_table.setHorizontalHeaderLabels(headers)
            self.stats_table.setRowCount(len(data) - 1)
            
            for row_idx, row in enumerate(data[1:]):
                for col_idx, val in enumerate(row):
                    self.stats_table.setItem(row_idx, col_idx, QTableWidgetItem(val))
            
            self.stats_table.resizeColumnsToContents()
#
    def __init__(self, session, testnet, exchange):
        super().__init__()
        self.language = "en"
        self.setWindowTitle(self.translations[self.language]["window_title"].format(exchange))
        self.setGeometry(100, 100, 1200, 900)

        icon_path = r"images\log.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Icon file not found at: {icon_path}")
#
# Створюємо віджет для вмісту
        self.central_widget = QWidget()
        self.main_layout = QVBoxLayout(self.central_widget)

        # Створюємо QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.central_widget)
        scroll_area.setWidgetResizable(True)  # Дозволяє віджету змінювати розмір
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # Прокрутка по горизонталі за потреби
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)   # Прокрутка по вертикалі за потреби

        # Встановлюємо QScrollArea як центральний віджет
        self.setCentralWidget(scroll_area)
#
        # In gui.py, in __init__ method, replace the initial settings loading and language_combobox initialization with:

        # Load settings and language
        settings_path = r"scripts\settings.json"
        loaded_settings = []
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    loaded_settings = settings.get("tabs", [])
                    self.language = settings.get("language", "en")  # Load language from settings, default to "en"
            except Exception as e:
                print(f"Error loading settings: {e}")
                self.language = "en"  # Fallback to English if error occurs
        else:
            self.language = "en"  # Default language if no settings file

        self.setWindowTitle(self.translations[self.language]["window_title"].format(exchange))
        self.setGeometry(100, 100, 1200, 900)

        icon_path = r"images\log.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Icon file not found at: {icon_path}")

        # Create language selection
        self.language_label = QLabel(self.translations[self.language]["language_label"])
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
#
        # Add Statistics tab
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)

        self.stats_table = QTableWidget()
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Read-only
        stats_layout.addWidget(self.stats_table)

        refresh_stats_button = QPushButton(self.translations[self.language]["refresh_button"])  # Reuse refresh translation or add new
        refresh_stats_button.clicked.connect(self.update_stats_table)
        stats_layout.addWidget(refresh_stats_button)

        self.tab_widget.addTab(stats_tab, "Statistics" if self.language == "en" else "Статистика")

        self.update_stats_table()
#
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
        self.tab_widget.insertTab(self.tab_widget.count() - 1, tab, self.translations[self.language]["tab_title"].format(self.tab_count))
        self.tab_widget.setCurrentWidget(tab)
        tab_data["tab_index"] = self.tab_count
        return tab_data

    def create_tab_ui(self, layout, session, testnet, exchange, settings=None):
        default_settings = {
            "selected_symbol": "HYPERUSDT",
            "position_open": False,
            "update_count": 0,
            "funding_interval_hours": 1.0 if exchange == "Bybit" else 8.0,
            "entry_time_seconds": 5.0,
            "qty": 45.0,
            "profit_percentage": 1.0,
            "leverage": 1.0,
            "exchange": exchange or "Bybit",
            "testnet": testnet or False,
            "auto_limit": False,
            "stop_loss_percentage": 0.5,
            "stop_loss_enabled": True,
            "trade_side": None  # Initialize trade_side here
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
            "trade_side": default_settings["trade_side"],  # Add trade_side to tab_data
            "funding_data": None,
            "open_order_id": None,
            "funding_time_price": None,
            "limit_price": None,
            "pre_funding_price": None
        }

        exchange_label = QLabel(self.translations[self.language]["exchange_label"])
        exchange_combobox = QComboBox()
        exchange_combobox.addItems(["Bybit", "Binance"])
        exchange_combobox.setCurrentText(tab_data["exchange"])
        exchange_combobox.currentTextChanged.connect(lambda value: self.update_tab_exchange(tab_data, value))

        testnet_label = QLabel(self.translations[self.language]["testnet_label"])
        testnet_checkbox = QCheckBox(self.translations[self.language]["testnet_checkbox"])
        testnet_checkbox.setChecked(tab_data["testnet"])
        testnet_checkbox.stateChanged.connect(lambda state: self.update_tab_testnet(tab_data, state))

        coin_input_label = QLabel(self.translations[self.language]["coin_input_label"])
        coin_input = QLineEdit()
        coin_input.setText(tab_data["selected_symbol"])
        
        update_coin_button = QPushButton(self.translations[self.language]["update_coin_button"])
        update_coin_button.clicked.connect(lambda: self.update_tab_symbol(tab_data, coin_input.text()))

        funding_interval_label = QLabel(self.translations[self.language]["funding_interval_label"])
        funding_interval_combobox = QComboBox()
        funding_intervals = ["0.01", "1", "4", "8"] if tab_data["exchange"] == "Bybit" else ["8"]
        funding_interval_combobox.addItems(funding_intervals)
        formatted_interval = str(float(tab_data["funding_interval_hours"]))
        if formatted_interval.endswith(".0"):
            formatted_interval = formatted_interval[:-2]
        funding_interval_combobox.setCurrentText(formatted_interval)
        funding_interval_combobox.currentTextChanged.connect(lambda value: self.update_tab_funding_interval(tab_data, value))

        entry_time_label = QLabel(self.translations[self.language]["entry_time_label"])
        entry_time_spinbox = QDoubleSpinBox()
        entry_time_spinbox.setRange(0.5, 60.0)
        entry_time_spinbox.setValue(tab_data["entry_time_seconds"])
        entry_time_spinbox.setSingleStep(0.1)
        entry_time_spinbox.valueChanged.connect(lambda value: self.update_tab_entry_time(tab_data, value))

        qty_label = QLabel(self.translations[self.language]["qty_label"])
        qty_spinbox = QDoubleSpinBox()
        qty_spinbox.setRange(0.001, 1000000.0)
        qty_spinbox.setValue(tab_data["qty"])
        qty_spinbox.setSingleStep(0.001)
        qty_spinbox.valueChanged.connect(lambda value: self.update_tab_qty(tab_data, value))

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

        auto_limit_label = QLabel(self.translations[self.language]["auto_limit_label"])
        auto_limit_checkbox = QCheckBox(self.translations[self.language]["auto_limit_checkbox"])
        auto_limit_checkbox.setChecked(tab_data["auto_limit"])
        auto_limit_checkbox.stateChanged.connect(lambda state: self.update_tab_auto_limit(tab_data, state))

        leverage_label = QLabel(self.translations[self.language]["leverage_label"])
        leverage_spinbox = QDoubleSpinBox()
        leverage_spinbox.setRange(1.0, 100.0)
        leverage_spinbox.setValue(tab_data["leverage"])
        leverage_spinbox.setSingleStep(0.1)
        leverage_spinbox.valueChanged.connect(lambda value: self.update_tab_leverage(tab_data, value))

        stop_loss_enabled_label = QLabel(self.translations[self.language]["stop_loss_enabled_label"])
        stop_loss_enabled_checkbox = QCheckBox(self.translations[self.language]["stop_loss_enabled_checkbox"])
        stop_loss_enabled_checkbox.setChecked(tab_data["stop_loss_enabled"])
        stop_loss_enabled_checkbox.stateChanged.connect(lambda state: self.update_tab_stop_loss_enabled(tab_data, state))

        stop_loss_percentage_label = QLabel(self.translations[self.language]["stop_loss_percentage_label"])
        stop_loss_percentage_spinbox = QDoubleSpinBox()
        stop_loss_percentage_spinbox.setRange(0.1, 10.0)
        stop_loss_percentage_spinbox.setValue(tab_data["stop_loss_percentage"])
        stop_loss_percentage_spinbox.setSingleStep(0.1)
        stop_loss_percentage_spinbox.valueChanged.connect(lambda value: self.update_tab_stop_loss_percentage(tab_data, value))
        trade_side_label = QLabel(self.translations[self.language]["trade_side_label"])
        trade_side_layout = QHBoxLayout()
        long_button = QPushButton("Long")
        long_button.setCheckable(True)
        long_button.setStyleSheet("background-color: green; color: white;")
        short_button = QPushButton("Short")
        short_button.setCheckable(True)
        short_button.setStyleSheet("background-color: red; color: white;")
        trade_side_layout.addWidget(long_button)
        trade_side_layout.addWidget(short_button)

        button_group = QButtonGroup()
        button_group.addButton(long_button)
        button_group.addButton(short_button)
        button_group.setExclusive(True)

        # Set initial state from tab_data
        if tab_data["trade_side"] == "Long":
            long_button.setChecked(True)
        elif tab_data["trade_side"] == "Short":
            short_button.setChecked(True)

        # Connect signal
        button_group.buttonToggled.connect(lambda button, checked: self.update_tab_trade_side(tab_data, button, checked))

        layout.addWidget(trade_side_label)
        layout.addLayout(trade_side_layout)

        tab_data["long_button"] = long_button
        tab_data["short_button"] = short_button
        #
        funding_info_label = QLabel(self.translations[self.language]["funding_info_label"])
#
        # Налаштування профілю для збереження cookies
        profile = QWebEngineProfile(f"BybitProfile_{self.tab_count}", self)
        cache_path = os.path.join(os.getcwd(), "webcache", f"tab_{self.tab_count}")
        os.makedirs(cache_path, exist_ok=True)  # Створюємо папку, якщо вона не існує
        profile.setCachePath(cache_path)
        profile.setPersistentStoragePath(cache_path)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)

        funding_web_view = QWebEngineView()
        page = QWebEnginePage(profile, funding_web_view)  # Створюємо сторінку з профілем
        funding_web_view.setPage(page)  # Призначаємо сторінку з профілем до QWebEngineView
        funding_web_view.setMinimumHeight(150)  # Зменшуємо висоту
        tab_data["funding_web_view"] = funding_web_view
        tab_data["web_profile"] = profile  # Зберігаємо профіль у tab_data для подальшого використання
        self.update_tab_funding_web_view(tab_data)
#
        # Додаємо Coinglass view
        coinglass_profile = QWebEngineProfile(f"CoinglassProfile_{self.tab_count}", self)
        coinglass_cache_path = os.path.join(os.getcwd(), "webcache", f"coinglass_tab_{self.tab_count}")
        os.makedirs(coinglass_cache_path, exist_ok=True)
        coinglass_profile.setCachePath(coinglass_cache_path)
        coinglass_profile.setPersistentStoragePath(coinglass_cache_path)
        coinglass_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)

        coinglass_view = QWebEngineView()
        coinglass_page = QWebEnginePage(coinglass_profile, coinglass_view)
        coinglass_view.setPage(coinglass_page)
        coinglass_view.setMinimumHeight(150)
        coinglass_view.setUrl(QUrl("https://www.coinglass.com/FundingRate"))
        tab_data["coinglass_view"] = coinglass_view
        tab_data["coinglass_profile"] = coinglass_profile
#
        price_label = QLabel(self.translations[self.language]["price_label"])
        balance_label = QLabel(self.translations[self.language]["balance_label"])
        leveraged_balance_label = QLabel(self.translations[self.language]["leveraged_balance_label"])
        volume_label = QLabel(self.translations[self.language]["volume_label"])
        ping_label = QLabel(self.translations[self.language]["ping_label"])


        refresh_button = QPushButton(self.translations[self.language]["refresh_button"])
        refresh_button.clicked.connect(lambda: self.update_tab_funding_data(tab_data))

        close_all_trades_button = QPushButton(self.translations[self.language]["close_all_trades_button"])
        close_all_trades_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        close_all_trades_button.clicked.connect(lambda: self.handle_tab_close_all_trades(tab_data))

        left_layout = QVBoxLayout()

        left_layout.addWidget(exchange_label)
        left_layout.addWidget(exchange_combobox)
        left_layout.addWidget(testnet_label)
        left_layout.addWidget(testnet_checkbox)
        left_layout.addWidget(coin_input_label)
        left_layout.addWidget(coin_input)
        left_layout.addWidget(update_coin_button)
        left_layout.addWidget(funding_interval_label)
        left_layout.addWidget(funding_interval_combobox)
        left_layout.addWidget(entry_time_label)
        left_layout.addWidget(entry_time_spinbox)
        left_layout.addWidget(qty_label)
        left_layout.addWidget(qty_spinbox)
        left_layout.addWidget(profit_percentage_label)
        left_layout.addWidget(profit_percentage_spinbox)
        left_layout.addWidget(profit_percentage_slider)
        left_layout.addWidget(auto_limit_label)
        left_layout.addWidget(auto_limit_checkbox)
        left_layout.addWidget(leverage_label)
        left_layout.addWidget(leverage_spinbox)
        left_layout.addWidget(stop_loss_enabled_label)
        left_layout.addWidget(stop_loss_enabled_checkbox)
        left_layout.addWidget(stop_loss_percentage_label)
        left_layout.addWidget(stop_loss_percentage_spinbox)
        left_layout.addWidget(funding_info_label)
        left_layout.addWidget(price_label)
        left_layout.addWidget(balance_label)
        left_layout.addWidget(leveraged_balance_label)
        left_layout.addWidget(volume_label)
        left_layout.addWidget(ping_label)
        left_layout.addWidget(refresh_button)
        left_layout.addWidget(close_all_trades_button)

        hbox = QHBoxLayout()
        hbox.addLayout(left_layout, 1)

        right_layout = QVBoxLayout()
        right_layout.addWidget(funding_web_view)
        right_layout.addWidget(coinglass_view)

        hbox.addLayout(right_layout, 1)

        layout.addLayout(hbox)
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

        timer = QTimer()
        timer.timeout.connect(lambda: self.check_tab_funding_time(tab_data))
        timer.start(1000)

        ping_timer = QTimer()
        ping_timer.timeout.connect(lambda: self.update_tab_ping(tab_data))
        ping_timer.start(30000)

        tab_data["timer"] = timer
        tab_data["ping_timer"] = ping_timer

        self.update_tab_funding_data(tab_data)
        print(f"Created UI for tab {self.tab_count}")
        return tab_data


    def update_tab_trade_side(self, tab_data, button, checked):
        if checked:
            tab_data["trade_side"] = button.text()
        else:
            # If no button is checked (possible if manually unchecked)
            if not tab_data["long_button"].isChecked() and not tab_data["short_button"].isChecked():
                tab_data["trade_side"] = None
        self.save_settings()

    def close_tab(self, index):
        if self.tab_widget.count() > 1:
            tab_data = self.tab_data_list[index]
            tab_data["timer"].stop()
            tab_data["ping_timer"].stop()
            self.tab_widget.removeTab(index)
            self.tab_data_list.pop(index)
            print(f"Closed tab {index + 1}")
            self.save_settings()

    def load_settings(self):
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
                "stop_loss_percentage": 0.5,
                "stop_loss_enabled": True
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
        tabs = []
        for tab_data in self.tab_data_list:
            tabs.append({
                "selected_symbol": tab_data["selected_symbol"],
                "funding_interval_hours": tab_data["funding_interval_hours"],
                "trade_side": tab_data["trade_side"],
                "entry_time_seconds": tab_data["entry_time_seconds"],
                "qty": tab_data["qty"],
                "profit_percentage": tab_data["profit_percentage"],
                "leverage": tab_data["leverage"],
                "exchange": tab_data["exchange"],
                "testnet": tab_data["testnet"],
                "auto_limit": tab_data["auto_limit"],
                "stop_loss_percentage": tab_data["stop_loss_percentage"],
                "stop_loss_enabled": tab_data["stop_loss_enabled"]
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
            tab_data["trade_side_label"].setText(self.translations[self.language]["trade_side_label"])
            self.update_tab_funding_data(tab_data)
        self.save_settings()

    def update_tab_exchange(self, tab_data, exchange):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["exchange"] = exchange
        self.update_tab_funding_web_view(tab_data)
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
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["testnet"] = state == Qt.CheckState.Checked.value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Testnet mode: {'Enabled' if tab_data['testnet'] else 'Disabled'}")
        tab_data["session"] = initialize_client(tab_data["exchange"], tab_data["testnet"])
        self.save_settings()
        self.update_tab_funding_data(tab_data)

    def update_tab_symbol(self, tab_data, symbol):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["selected_symbol"] = symbol.strip().upper()
        self.update_tab_funding_web_view(tab_data)
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated symbol: {tab_data['selected_symbol']}")
        self.tab_widget.setTabText(self.tab_data_list.index(tab_data), f"{tab_data['selected_symbol']}")
        self.save_settings()
        self.update_tab_funding_data(tab_data)

    def update_tab_funding_interval(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        if value:
            tab_data["funding_interval_hours"] = float(value)
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated funding interval: {tab_data['funding_interval_hours']} hours")
            self.save_settings()
            self.update_tab_funding_data(tab_data)

    def update_tab_entry_time(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["entry_time_seconds"] = value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated entry time: {tab_data['entry_time_seconds']} seconds")
        self.save_settings()

    def update_tab_qty(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["qty"] = value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated order quantity: {tab_data['qty']}")
        self.save_settings()
        self.update_tab_volume_label(tab_data)

    def update_tab_profit_percentage(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["profit_percentage"] = value
        tab_data["profit_percentage_slider"].setValue(int(value * 100))
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated profit percentage: {tab_data['profit_percentage']}%")
        self.save_settings()

    def update_tab_profit_percentage_from_slider(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["profit_percentage"] = value / 100.0
        tab_data["profit_percentage_spinbox"].setValue(tab_data["profit_percentage"])
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated profit percentage from slider: {tab_data['profit_percentage']}%")
        self.save_settings()

    def update_tab_auto_limit(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["auto_limit"] = state == Qt.CheckState.Checked.value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Auto limit mode: {'Enabled' if tab_data['auto_limit'] else 'Disabled'}")
        self.save_settings()

    def update_tab_leverage(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["leverage"] = value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated leverage: {tab_data['leverage']}x")
        self.save_settings()
        self.update_tab_leveraged_balance_label(tab_data)

    def update_tab_stop_loss_percentage(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["stop_loss_percentage"] = value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Updated stop loss percentage: {tab_data['stop_loss_percentage']}%")
        self.save_settings()

    def update_tab_stop_loss_enabled(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        tab_data["stop_loss_enabled"] = state == Qt.CheckState.Checked.value
        print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Stop loss enabled: {'Enabled' if tab_data['stop_loss_enabled'] else 'Disabled'}")
        self.save_settings()

    def update_tab_volume_label(self, tab_data):
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
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping update")
            return
        update_ping(tab_data["session"], tab_data["ping_label"], tab_data["exchange"])

    def check_tab_funding_time(self, tab_data):
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

        # Фіксуємо ціну за 1 секунду до фандингу
        if 0.5 <= time_to_funding <= 1.5 and tab_data["pre_funding_price"] is None:
            tab_data["pre_funding_price"] = get_current_price(tab_data["session"], symbol, tab_data["exchange"])
            print(f"Tab {self.tab_data_list.index(tab_data) + 1}: Captured pre-funding price for {symbol}: {tab_data['pre_funding_price']}")

        if tab_data["entry_time_seconds"] - 1.0 <= time_to_funding <= tab_data["entry_time_seconds"] and not tab_data["open_order_id"]:
            if tab_data["trade_side"] is None:
                print(f"Tab {self.tab_data_list.index(tab_data) + 1}: No trade side selected, skipping entry for {symbol}")
                return  # Skip entry if no side selected

            side = "Buy" if tab_data["trade_side"] == "Long" else "Sell"


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
        if entry_price:
            tab_data["position_open"] = True
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
                warning.setWindowTitle(self.translations[self.language]["price_validation_warning_title"])
                warning.setText(self.translations[self.language]["price_validation_warning_text"].format(
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
            warning.setWindowTitle(self.translations[self.language]["price_mismatch_warning_title"])
            warning.setText(self.translations[self.language]["price_mismatch_warning_text"].format(
                symbol=symbol, actual_profit=profit_percentage, expected_profit=tab_data["profit_percentage"]))
            warning.exec()

    def handle_tab_close_all_trades(self, tab_data):
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
                self.update_tab_funding_web_view(tab_data)

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

        tab_data["update_count"] = tab_data.get("update_count", 0) + 1
        if tab_data.get("position_open", False) and tab_data["update_count"] % 10 == 0:  # Check every 10 updates (~10s)
            try:
                symbol = tab_data["selected_symbol"]
                if tab_data["exchange"] == "Bybit":
                    pos_response = tab_data["session"].get_positions(category="linear", symbol=symbol)
                    if pos_response["retCode"] == 0:
                        positions = pos_response["result"]["list"]
                        position = next((p for p in positions if p["symbol"] == symbol and float(p["size"]) > 0), None)
                        if not position:
                            record_last_closed_trade(tab_data["session"], tab_data["exchange"], symbol)
                            tab_data["position_open"] = False
                            self.update_stats_table()  # Refresh stats table automatically
                else:  # Binance (partial support)
                    pos_response = tab_data["session"].get_position_information(symbol=symbol)
                    position = next((p for p in pos_response if p["symbol"] == symbol and abs(float(p["positionAmt"])) > 0), None)
                    if not position:
                        record_last_closed_trade(tab_data["session"], tab_data["exchange"], symbol)
                        tab_data["position_open"] = False
                        self.update_stats_table()
            except Exception as e:
                print(f"Error checking position status: {e}")

#
    def update_tab_funding_web_view(self, tab_data):
        if tab_data not in self.tab_data_list:
            print(f"Tab data not found in tab_data_list, skipping web view update")
            return
        symbol = tab_data["selected_symbol"]
        if tab_data["exchange"] == "Bybit":
            url = f"https://www.bybit.com/trade/usdt/{symbol}"
            tab_data["funding_web_view"].setUrl(QUrl(url))
            tab_data["funding_web_view"].setVisible(True)
        else:
            tab_data["funding_web_view"].setVisible(False)
        tab_data["coinglass_view"].setVisible(True)  # Завжди показувати Coinglass
#
    def closeEvent(self, event):
        for tab_data in self.tab_data_list:
            tab_data["timer"].stop()
            tab_data["ping_timer"].stop()
        self.save_settings()
        event.accept()