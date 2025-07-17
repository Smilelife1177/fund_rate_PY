import os
import json
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel, QDoubleSpinBox, QSlider, QComboBox, QCheckBox
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon
from logic import get_account_balance, get_funding_data, get_current_price, get_next_funding_time, place_market_order, get_symbol_info, place_limit_close_order, update_ping, initialize_client

class FundingTraderApp(QMainWindow):
    def __init__(self, session, testnet, exchange):
        super().__init__()
        self.session = session
        self.testnet = testnet
        self.exchange = exchange
        self.setWindowTitle(f"{self.exchange} Funding Trader")
        self.setGeometry(100, 100, 400, 500)

        icon_path = r"images\log.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Icon file not found at: {icon_path}")

        # Load settings from file or use defaults
        self.load_settings()

        # Setup UI
        self.setup_ui()

        # Sync funding interval combobox after loading settings
        self.funding_interval_combobox.blockSignals(True)
        self.funding_interval_combobox.clear()
        self.funding_intervals = ["0.01", "1", "4", "8"] if self.exchange == "Bybit" else ["8"]
        self.funding_interval_combobox.addItems(self.funding_intervals)
        formatted_interval = str(float(self.funding_interval_hours))
        if formatted_interval.endswith(".0"):
            formatted_interval = formatted_interval[:-2]
        self.funding_interval_combobox.setCurrentText(formatted_interval)
        self.funding_interval_combobox.blockSignals(False)

        # Timer for checking funding time
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_funding_time)
        self.timer.start(1000)

        # Timer for updating ping
        self.ping_timer = QTimer()
        self.ping_timer.timeout.connect(self.update_ping)
        self.ping_timer.start(15000)

        # Initial data update
        print("Initializing application...")
        self.update_funding_data()

    def load_settings(self):
        """Load settings from settings.json or set defaults."""
        default_settings = {
            "selected_symbol": "HYPERUSDT",
            "funding_interval_hours": 1.0 if self.exchange == "Bybit" else 8.0,
            "entry_time_seconds": 5.0,
            "qty": 45.0,
            "profit_percentage": 1.0,
            "leverage": 5.0,
            "exchange": self.exchange,
            "testnet": self.testnet
        }
        try:
            if os.path.exists(r"scripts\settings.json"): #r"scripts\settings.json"
                with open(r"scripts\settings.json", "r") as f:
                    settings = json.load(f)
                    self.selected_symbol = settings.get("selected_symbol", default_settings["selected_symbol"])
                    self.funding_interval_hours = settings.get("funding_interval_hours", default_settings["funding_interval_hours"])
                    self.entry_time_seconds = settings.get("entry_time_seconds", default_settings["entry_time_seconds"])
                    self.qty = settings.get("qty", default_settings["qty"])
                    self.profit_percentage = settings.get("profit_percentage", default_settings["profit_percentage"])
                    self.leverage = settings.get("leverage", default_settings["leverage"])
                    self.exchange = settings.get("exchange", default_settings["exchange"])
                    self.testnet = settings.get("testnet", default_settings["testnet"])
                    print("Settings loaded successfully")
            else:
                print("No settings file found, using defaults")
                self.selected_symbol = default_settings["selected_symbol"]
                self.funding_interval_hours = default_settings["funding_interval_hours"]
                self.entry_time_seconds = default_settings["entry_time_seconds"]
                self.qty = default_settings["qty"]
                self.profit_percentage = default_settings["profit_percentage"]
                self.leverage = default_settings["leverage"]
                self.exchange = default_settings["exchange"]
                self.testnet = default_settings["testnet"]
        except Exception as e:
            print(f"Error loading settings: {e}, using defaults")
            self.selected_symbol = default_settings["selected_symbol"]
            self.funding_interval_hours = default_settings["funding_interval_hours"]
            self.entry_time_seconds = default_settings["entry_time_seconds"]
            self.qty = default_settings["qty"]
            self.profit_percentage = default_settings["profit_percentage"]
            self.leverage = default_settings["leverage"]
            self.exchange = default_settings["exchange"]
            self.testnet = default_settings["testnet"]
        self.funding_data = None
        self.open_order_id = None
        self.funding_time_price = None

    def save_settings(self):
        """Save current settings to settings.json."""
        settings = {
            "selected_symbol": self.selected_symbol,
            "funding_interval_hours": self.funding_interval_hours,
            "entry_time_seconds": self.entry_time_seconds,
            "qty": self.qty,
            "profit_percentage": self.profit_percentage,
            "leverage": self.leverage,
            "exchange": self.exchange,
            "testnet": self.testnet
        }
        try:
            with open(r"scripts\settings.json", "w") as f:
                json.dump(settings, f, indent=4)
                print("Settings saved successfully")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def setup_ui(self):
        print("Setting up UI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Exchange selector
        self.exchange_label = QLabel("Exchange:")
        self.exchange_combobox = QComboBox()
        self.exchange_combobox.addItems(["Bybit", "Binance"])
        self.exchange_combobox.setCurrentText(self.exchange)
        self.exchange_combobox.currentTextChanged.connect(self.update_exchange)

        # Testnet toggle
        self.testnet_label = QLabel("Testnet Mode:")
        self.testnet_checkbox = QCheckBox("Enable Testnet")
        self.testnet_checkbox.setChecked(self.testnet)
        self.testnet_checkbox.stateChanged.connect(self.update_testnet)

        self.coin_input_label = QLabel("Enter Coin (e.g., BTCUSDT):")
        self.coin_input = QLineEdit()
        self.coin_input.setText(self.selected_symbol)
        
        self.update_coin_button = QPushButton("Update Coin")
        self.update_coin_button.clicked.connect(self.handle_update_coin)

        self.funding_interval_label = QLabel("Funding Interval (hours):")
        self.funding_interval_combobox = QComboBox()
        self.funding_intervals = ["0.01", "1", "4", "8"] if self.exchange == "Bybit" else ["8"]
        self.funding_interval_combobox.addItems(self.funding_intervals)
        self.funding_interval_combobox.setCurrentText(str(self.funding_interval_hours))
        self.funding_interval_combobox.currentTextChanged.connect(self.update_funding_interval)

        self.entry_time_label = QLabel("Entry Time Before Funding (seconds):")
        self.entry_time_spinbox = QDoubleSpinBox()
        self.entry_time_spinbox.setRange(0.5, 10.0)
        self.entry_time_spinbox.setValue(self.entry_time_seconds)
        self.entry_time_spinbox.setSingleStep(0.1)
        self.entry_time_spinbox.valueChanged.connect(self.update_entry_time)

        self.qty_label = QLabel("Order Quantity (qty):")
        self.qty_spinbox = QDoubleSpinBox()
        self.qty_spinbox.setRange(0.001, 10000.0)
        self.qty_spinbox.setValue(self.qty)
        self.qty_spinbox.setSingleStep(0.001)
        self.qty_spinbox.valueChanged.connect(self.update_qty)

        self.profit_percentage_label = QLabel("Desired Profit Percentage (%):")
        self.profit_percentage_spinbox = QDoubleSpinBox()
        self.profit_percentage_spinbox.setRange(0.1, 10.0)
        self.profit_percentage_spinbox.setValue(self.profit_percentage)
        self.profit_percentage_spinbox.setSingleStep(0.1)
        self.profit_percentage_spinbox.valueChanged.connect(self.update_profit_percentage)

        self.profit_percentage_slider = QSlider(Qt.Orientation.Horizontal)
        self.profit_percentage_slider.setRange(10, 1000)
        self.profit_percentage_slider.setValue(int(self.profit_percentage * 100))
        self.profit_percentage_slider.setSingleStep(10)
        self.profit_percentage_slider.valueChanged.connect(self.update_profit_percentage_from_slider)

        self.leverage_label = QLabel("Leverage (x):")
        self.leverage_spinbox = QDoubleSpinBox()
        self.leverage_spinbox.setRange(1.0, 100.0)
        self.leverage_spinbox.setValue(self.leverage)
        self.leverage_spinbox.setSingleStep(0.1)
        self.leverage_spinbox.valueChanged.connect(self.update_leverage)

        self.funding_info_label = QLabel("Funding Rate: N/A | Time to Next Funding: N/A")
        self.price_label = QLabel("Current Price: N/A")
        self.balance_label = QLabel("Account Balance: N/A")
        self.leveraged_balance_label = QLabel("Leveraged Balance: N/A")
        self.volume_label = QLabel("Order Volume: N/A")
        self.ping_label = QLabel("Ping: N/A")

        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.update_funding_data)

        layout.addWidget(self.exchange_label)
        layout.addWidget(self.exchange_combobox)
        layout.addWidget(self.testnet_label)
        layout.addWidget(self.testnet_checkbox)
        layout.addWidget(self.coin_input_label)
        layout.addWidget(self.coin_input)
        layout.addWidget(self.update_coin_button)
        layout.addWidget(self.funding_interval_label)
        layout.addWidget(self.funding_interval_combobox)
        layout.addWidget(self.entry_time_label)
        layout.addWidget(self.entry_time_spinbox)
        layout.addWidget(self.qty_label)
        layout.addWidget(self.qty_spinbox)
        layout.addWidget(self.profit_percentage_label)
        layout.addWidget(self.profit_percentage_spinbox)
        layout.addWidget(self.profit_percentage_slider)
        layout.addWidget(self.leverage_label)
        layout.addWidget(self.leverage_spinbox)
        layout.addWidget(self.funding_info_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.balance_label)
        layout.addWidget(self.leveraged_balance_label)
        layout.addWidget(self.volume_label)
        layout.addWidget(self.ping_label)
        layout.addWidget(self.refresh_button)
        print("UI setup completed")

    def update_exchange(self, exchange):
        self.exchange = exchange
        self.setWindowTitle(f"{self.exchange} Funding Trader")
        self.funding_interval_hours = 1.0 if self.exchange == "Bybit" else 8.0
        # Block signals to prevent empty string emission
        self.funding_interval_combobox.blockSignals(True)
        self.funding_interval_combobox.clear()
        self.funding_intervals = ["0.01", "1", "4", "8"] if self.exchange == "Bybit" else ["8"]
        self.funding_interval_combobox.addItems(self.funding_intervals)
        self.funding_interval_combobox.setCurrentText(str(self.funding_interval_hours))
        self.funding_interval_combobox.blockSignals(False)
        self.session = initialize_client(self.exchange, self.testnet)
        self.save_settings()
        self.update_funding_data()
        print(f"Switched to exchange: {self.exchange}")

    def update_testnet(self, state):
        self.testnet = state == Qt.CheckState.Checked.value
        print(f"Testnet mode: {'Enabled' if self.testnet else 'Disabled'}")
        self.session = initialize_client(self.exchange, self.testnet)
        self.save_settings()
        self.update_funding_data()

    def handle_update_coin(self):
        symbol = self.coin_input.text()
        self.update_symbol(symbol)

    def update_symbol(self, symbol):
        self.selected_symbol = symbol.strip().upper()
        print(f"Updated symbol: {self.selected_symbol}")
        self.save_settings()
        self.update_funding_data()

    def update_funding_interval(self, value):
        if value:  # Only process non-empty values
            self.funding_interval_hours = float(value)
            print(f"Updated funding interval: {self.funding_interval_hours} hours")
            self.save_settings()
            self.update_funding_data()

    def update_entry_time(self, value):
        self.entry_time_seconds = value
        print(f"Updated entry time: {self.entry_time_seconds} seconds")
        self.save_settings()

    def update_qty(self, value):
        self.qty = value
        print(f"Updated order quantity: {self.qty}")
        self.save_settings()
        self.update_volume_label()

    def update_profit_percentage(self, value):
        self.profit_percentage = value
        self.profit_percentage_slider.setValue(int(value * 100))
        print(f"Updated profit percentage: {self.profit_percentage}%")
        self.save_settings()

    def update_profit_percentage_from_slider(self, value):
        self.profit_percentage = value / 100.0
        self.profit_percentage_spinbox.setValue(self.profit_percentage)
        print(f"Updated profit percentage from slider: {self.profit_percentage}%")
        self.save_settings()

    def update_leverage(self, value):
        self.leverage = value
        print(f"Updated leverage: {self.leverage}x")
        self.save_settings()
        self.update_leveraged_balance_label()

    def update_volume_label(self):
        current_price = get_current_price(self.session, self.selected_symbol, self.exchange)
        balance = get_account_balance(self.session, self.exchange)
        leveraged_balance = balance * self.leverage if balance is not None and self.leverage is not None else None
        if current_price is not None and self.qty is not None:
            volume = self.qty * current_price
            self.volume_label.setText(f"Order Volume: ${volume:.2f} USD")
            if volume < 5.0 or (leveraged_balance is not None and volume > leveraged_balance):
                self.volume_label.setStyleSheet("color: red;")
            else:
                self.volume_label.setStyleSheet("color: black;")
        else:
            self.volume_label.setText("Order Volume: N/A")
            self.volume_label.setStyleSheet("color: black;")

    def update_leveraged_balance_label(self):
        balance = get_account_balance(self.session, self.exchange)
        if balance is not None and self.leverage is not None:
            leveraged_balance = balance * self.leverage
            self.leveraged_balance_label.setText(f"Leveraged Balance: ${leveraged_balance:.2f} USDT")
        else:
            self.leveraged_balance_label.setText("Leveraged Balance: N/A")

    def update_ping(self):
        update_ping(self.session, self.ping_label, self.exchange)

    def check_funding_time(self):
        if not self.funding_data:
            print("Funding data unavailable")
            self.funding_info_label.setText("Funding Rate: N/A | Time to Next Funding: N/A")
            self.price_label.setText("Current Price: N/A")
            self.balance_label.setText("Account Balance: N/A")
            self.leveraged_balance_label.setText("Leveraged Balance: N/A")
            self.volume_label.setText("Order Volume: N/A")
            self.volume_label.setStyleSheet("color: black;")
            self.ping_label.setText("Ping: N/A")
            self.ping_label.setStyleSheet("color: black;")
            return

        symbol = self.funding_data["symbol"]
        funding_rate = self.funding_data["funding_rate"]
        funding_time = self.funding_data["funding_time"]

        time_to_funding, time_str = get_next_funding_time(funding_time, self.funding_interval_hours)
        self.funding_info_label.setText(f"Funding Rate: {funding_rate:.4f}% | Time to Next Funding: {time_str}")
        print(f"Time to next funding for {symbol}: {time_str}")

        if self.entry_time_seconds - 1.0 <= time_to_funding <= self.entry_time_seconds and not self.open_order_id:
            side = "Buy" if funding_rate > 0 else "Sell"
            self.open_order_id = place_market_order(self.session, symbol, side, self.qty, self.exchange)
            if self.open_order_id:
                QTimer.singleShot(int((time_to_funding - 1.0) * 1000), lambda: self.capture_funding_price(symbol, side))

    def capture_funding_price(self, symbol, side):
        self.funding_time_price = get_current_price(self.session, symbol, self.exchange)
        if self.funding_time_price is None:
            print(f"Failed to get price at funding time for {symbol}")
            self.open_order_id = None
            return

        limit_price = (self.funding_time_price * (1 + self.profit_percentage / 100) if side == "Buy" 
                      else self.funding_time_price * (1 - self.profit_percentage / 100))
        tick_size = get_symbol_info(self.session, symbol, self.exchange)
        place_limit_close_order(self.session, symbol, side, self.qty, limit_price, tick_size, self.exchange)
        self.open_order_id = None

    def update_funding_data(self):
        try:
            print("Updating funding data...")
            self.funding_data = get_funding_data(self.session, self.selected_symbol, self.exchange)

            current_price = get_current_price(self.session, self.selected_symbol, self.exchange)
            if current_price is not None:
                self.price_label.setText(f"Current Price: ${current_price:.6f}")
            else:
                self.price_label.setText("Current Price: N/A")

            balance = get_account_balance(self.session, self.exchange)
            if balance is not None:
                self.balance_label.setText(f"Account Balance: ${balance:.2f} USDT")
                self.update_leveraged_balance_label()
            else:
                self.balance_label.setText("Account Balance: N/A")
                self.leveraged_balance_label.setText("Leveraged Balance: N/A")

            if self.funding_data:
                funding_rate = self.funding_data["funding_rate"]
                funding_time = self.funding_data["funding_time"]
                _, time_str = get_next_funding_time(funding_time, self.funding_interval_hours)
                self.funding_info_label.setText(f"Funding Rate: {funding_rate:.4f}% | Time to Next Funding: {time_str}")
            else:
                self.funding_info_label.setText("Funding Rate: N/A | Time to Next Funding: N/A")
                self.price_label.setText("Current Price: N/A")
                self.balance_label.setText("Account Balance: N/A")
                self.leveraged_balance_label.setText("Leveraged Balance: N/A")
                self.volume_label.setText("Order Volume: N/A")
                self.volume_label.setStyleSheet("color: black;")
                self.ping_label.setText("Ping: N/A")
                self.ping_label.setStyleSheet("color: black;")

            self.update_volume_label()
            self.update_ping()

            print("Data updated successfully")

        except Exception as e:
            print(f"Error updating funding data: {e}")
            self.funding_info_label.setText("Funding Rate: Error | Time to Next Funding: Error")
            self.price_label.setText("Current Price: Error")
            self.balance_label.setText("Account Balance: Error")
            self.leveraged_balance_label.setText("Leveraged Balance: Error")
            self.volume_label.setText("Order Volume: Error")
            self.volume_label.setStyleSheet("color: black;")
            self.ping_label.setText("Ping: Error")
            self.ping_label.setStyleSheet("color: red;")

    def closeEvent(self, event):
        self.timer.stop()
        self.ping_timer.stop()
        self.save_settings()
        event.accept()