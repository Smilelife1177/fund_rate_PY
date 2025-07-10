from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel, QDoubleSpinBox, QSlider, QComboBox
from PyQt6.QtCore import QTimer, Qt

class FundingTraderGUI(QMainWindow):
    def __init__(self, logic):
        super().__init__()
        self.setWindowTitle("Bybit Funding Trader")
        self.setGeometry(100, 100, 400, 500)
        self.logic = logic
        self.setup_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_funding_time)
        self.timer.start(1000)
        self.ping_timer = QTimer()
        self.ping_timer.timeout.connect(self.update_ping)
        self.ping_timer.start(15000)
        print("Initializing GUI...")
        self.update_funding_data()

    def setup_ui(self):
        print("Setting up UI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.coin_input_label = QLabel("Enter Coin (e.g., BTCUSDT):")
        self.coin_input = QLineEdit()
        self.coin_input.setText(self.logic.selected_symbol)
        
        self.update_coin_button = QPushButton("Update Coin")
        self.update_coin_button.clicked.connect(self.handle_update_coin)

        self.funding_interval_label = QLabel("Funding Interval (hours):")
        self.funding_interval_combobox = QComboBox()
        self.funding_intervals = ["0.01", "1", "4", "8"]
        self.funding_interval_combobox.addItems(self.funding_intervals)
        self.funding_interval_combobox.setCurrentText(str(int(self.logic.funding_interval_hours)))
        self.funding_interval_combobox.currentTextChanged.connect(self.update_funding_interval)

        self.entry_time_label = QLabel("Entry Time Before Funding (seconds):")
        self.entry_time_spinbox = QDoubleSpinBox()
        self.entry_time_spinbox.setRange(0.5, 10.0)
        self.entry_time_spinbox.setValue(self.logic.entry_time_seconds)
        self.entry_time_spinbox.setSingleStep(0.1)
        self.entry_time_spinbox.valueChanged.connect(self.update_entry_time)

        self.qty_label = QLabel("Order Quantity (qty):")
        self.qty_spinbox = QDoubleSpinBox()
        self.qty_spinbox.setRange(0.001, 10000.0)
        self.qty_spinbox.setValue(self.logic.qty)
        self.qty_spinbox.setSingleStep(0.001)
        self.qty_spinbox.valueChanged.connect(self.update_qty)

        self.profit_percentage_label = QLabel("Desired Profit Percentage (%):")
        self.profit_percentage_spinbox = QDoubleSpinBox()
        self.profit_percentage_spinbox.setRange(0.1, 2.0)
        self.profit_percentage_spinbox.setValue(self.logic.profit_percentage)
        self.profit_percentage_spinbox.setSingleStep(0.1)
        self.profit_percentage_spinbox.valueChanged.connect(self.update_profit_percentage)

        self.profit_percentage_slider = QSlider(Qt.Orientation.Horizontal)
        self.profit_percentage_slider.setRange(10, 200)
        self.profit_percentage_slider.setValue(int(self.logic.profit_percentage * 100))
        self.profit_percentage_slider.setSingleStep(10)
        self.profit_percentage_slider.valueChanged.connect(self.update_profit_percentage_from_slider)

        self.leverage_label = QLabel("Leverage (x):")
        self.leverage_spinbox = QDoubleSpinBox()
        self.leverage_spinbox.setRange(1.0, 100.0)
        self.leverage_spinbox.setValue(self.logic.leverage)
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

    def handle_update_coin(self):
        symbol = self.coin_input.text()
        self.logic.update_symbol(symbol)
        self.update_funding_data()

    def update_funding_interval(self, value):
        self.logic.funding_interval_hours = float(value)
        print(f"Updated funding interval: {self.logic.funding_interval_hours} hours")
        self.update_funding_data()

    def update_entry_time(self, value):
        self.logic.entry_time_seconds = value
        print(f"Updated entry time: {self.logic.entry_time_seconds} seconds")

    def update_qty(self, value):
        self.logic.qty = value
        print(f"Updated order quantity: {self.logic.qty}")
        self.update_volume_label()

    def update_profit_percentage(self, value):
        self.logic.profit_percentage = value
        self.profit_percentage_slider.setValue(int(value * 100))
        print(f"Updated profit percentage: {self.logic.profit_percentage}%")

    def update_profit_percentage_from_slider(self, value):
        self.logic.profit_percentage = value / 100.0
        self.profit_percentage_spinbox.setValue(self.logic.profit_percentage)
        print(f"Updated profit percentage from slider: {self.logic.profit_percentage}%")

    def update_leverage(self, value):
        self.logic.leverage = value
        print(f"Updated leverage: {self.logic.leverage}x")
        self.update_leveraged_balance_label()

    def update_volume_label(self):
        current_price = self.logic.get_current_price(self.logic.selected_symbol)
        if current_price is not None and self.logic.qty is not None:
            volume = self.logic.qty * current_price
            self.volume_label.setText(f"Order Volume: ${volume:.2f} USD")
            if volume < 5.0:
                self.volume_label.setStyleSheet("color: red;")
            else:
                self.volume_label.setStyleSheet("color: black;")
        else:
            self.volume_label.setText("Order Volume: N/A")
            self.volume_label.setStyleSheet("color: black;")

    def update_leveraged_balance_label(self):
        balance = self.logic.get_account_balance()
        if balance is not None and self.logic.leverage is not None:
            leveraged_balance = balance * self.logic.leverage
            self.leveraged_balance_label.setText(f"Leveraged Balance: ${leveraged_balance:.2f} USDT")
        else:
            self.leveraged_balance_label.setText("Leveraged Balance: N/A")

    def update_ping(self):
        ping_ms = self.logic.update_ping()
        if ping_ms is not None:
            self.ping_label.setText(f"Ping: {ping_ms:.2f} ms")
            if ping_ms > 500:
                self.ping_label.setStyleSheet("color: red;")
            else:
                self.ping_label.setStyleSheet("color: black;")
        else:
            self.ping_label.setText("Ping: Error")
            self.ping_label.setStyleSheet("color: red;")

    def check_funding_time(self):
        if not self.logic.funding_data:
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

        symbol = self.logic.funding_data["symbol"]
        funding_rate = self.logic.funding_data["funding_rate"]
        funding_time = self.logic.funding_data["funding_time"]

        time_to_funding, time_str = self.logic.get_next_funding_time(funding_time)
        self.funding_info_label.setText(f"Funding Rate: {funding_rate:.4f}% | Time to Next Funding: {time_str}")
        print(f"Time to next funding for {symbol}: {time_str}")

        if self.logic.entry_time_seconds - 1.0 <= time_to_funding <= self.logic.entry_time_seconds and not self.logic.open_order_id:
            side = "Buy" if funding_rate > 0 else "Sell"
            self.logic.open_order_id = self.logic.place_market_order(symbol, side, self.logic.qty)
            if self.logic.open_order_id:
                QTimer.singleShot(int((time_to_funding - 1.0) * 1000), lambda: self.capture_funding_price(symbol, side))

    def capture_funding_price(self, symbol, side):
        self.logic.funding_time_price = self.logic.get_current_price(symbol)
        if self.logic.funding_time_price is None:
            print(f"Failed to get price at funding time for {symbol}")
            self.logic.open_order_id = None
            return
        limit_price = (self.logic.funding_time_price * (1 + self.logic.profit_percentage / 100) if side == "Buy" 
                      else self.logic.funding_time_price * (1 - self.logic.profit_percentage / 100))
        self.logic.place_limit_close_order(symbol, side, self.logic.qty, limit_price)
        self.logic.open_order_id = None

    def update_funding_data(self):
        try:
            print("Updating funding data...")
            self.logic.funding_data = self.logic.get_funding_data()
            current_price = self.logic.get_current_price(self.logic.selected_symbol)
            if current_price is not None:
                self.price_label.setText(f"Current Price: ${current_price:.6f}")
            else:
                self.price_label.setText("Current Price: N/A")

            balance = self.logic.get_account_balance()
            if balance is not None:
                self.balance_label.setText(f"Account Balance: ${balance:.2f} USDT")
                self.update_leveraged_balance_label()
            else:
                self.balance_label.setText("Account Balance: N/A")
                self.leveraged_balance_label.setText("Leveraged Balance: N/A")

            if self.logic.funding_data:
                funding_rate = self.logic.funding_data["funding_rate"]
                funding_time = self.logic.funding_data["funding_time"]
                _, time_str = self.logic.get_next_funding_time(funding_time)
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
        event.accept()