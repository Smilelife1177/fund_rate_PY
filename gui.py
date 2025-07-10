import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel, QDoubleSpinBox, QSlider, QComboBox
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon
from logic import FundingTraderLogic  # Importing the logic class

class FundingTraderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit Funding Trader")
        self.setGeometry(100, 100, 400, 500)

        icon_path = r"images\log.jpg"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Icon file not found at: {icon_path}")

        # Initialize logic
        self.logic = FundingTraderLogic()

        # Setup UI
        self.setup_ui()

        # Timer for checking funding time
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_funding_time)
        self.timer.start(1000)  # Check every second

        # Timer for updating ping
        self.ping_timer = QTimer()
        self.ping_timer.timeout.connect(self.update_ping)
        self.ping_timer.start(15000)  # Update ping every 15 seconds

        # Initial data update
        print("Initializing application...")
        self.update_funding_data()
        self.update_ping()

    def setup_ui(self):
        print("Setting up UI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Coin input
        self.coin_input_label = QLabel("Enter Coin (e.g., BTCUSDT):")
        self.coin_input = QLineEdit()
        self.coin_input.setText(self.logic.selected_symbol)
        
        # Update coin button
        self.update_coin_button = QPushButton("Update Coin")
        self.update_coin_button.clicked.connect(self.handle_update_coin)

        # Funding interval
        self.funding_interval_label = QLabel("Funding Interval (hours):")
        self.funding_interval_combobox = QComboBox()
        self.funding_intervals = ["0.01", "1", "4", "8"]
        self.funding_interval_combobox.addItems(self.funding_intervals)
        self.funding_interval_combobox.setCurrentText(str(int(self.logic.funding_interval_hours)))
        self.funding_interval_combobox.currentTextChanged.connect(self.update_funding_interval)

        # Entry time
        self.entry_time_label = QLabel("Entry Time Before Funding (seconds):")
        self.entry_time_spinbox = QDoubleSpinBox()
        self.entry_time_spinbox.setRange(0.5, 10.0)
        self.entry_time_spinbox.setValue(self.logic.entry_time_seconds)
        self.entry_time_spinbox.setSingleStep(0.1)
        self.entry_time_spinbox.valueChanged.connect(self.update_entry_time)

        # Order quantity
        self.qty_label = QLabel("Order Quantity (qty):")
        self.qty_spinbox = QDoubleSpinBox()
        self.qty_spinbox.setRange(0.001, 10000.0)
        self.qty_spinbox.setValue(self.logic.qty)
        self.qty_spinbox.setSingleStep(0.001)
        self.qty_spinbox.valueChanged.connect(self.update_qty)

        # Profit percentage
        self.profit_percentage_label = QLabel("Desired Profit Percentage (%):")
        self.profit_percentage_spinbox = QDoubleSpinBox()
        self.profit_percentage_spinbox.setRange(0.1, 2.0)
        self.profit_percentage_spinbox.setValue(self.logic.profit_percentage)
        self.profit_percentage_spinbox.setSingleStep(0.1)
        self.profit_percentage_spinbox.valueChanged.connect(self.update_profit_percentage)

        # Profit percentage slider
        self.profit_percentage_slider = QSlider(Qt.Orientation.Horizontal)
        self.profit_percentage_slider.setRange(10, 200)  # 0.1% to 2.0% (multiplied by 100 for integer steps)
        self.profit_percentage_slider.setValue(int(self.logic.profit_percentage * 100))
        self.profit_percentage_slider.setSingleStep(10)  # 0.1% steps
        self.profit_percentage_slider.valueChanged.connect(self.update_profit_percentage_from_slider)

        # Leverage
        self.leverage_label = QLabel("Leverage (x):")
        self.leverage_spinbox = QDoubleSpinBox()
        self.leverage_spinbox.setRange(1.0, 100.0)
        self.leverage_spinbox.setValue(self.logic.leverage)
        self.leverage_spinbox.setSingleStep(0.1)
        self.leverage_spinbox.valueChanged.connect(self.update_leverage)

        # Display labels
        self.funding_info_label = QLabel("Funding Rate: N/A | Time to Next Funding: N/A")
        self.price_label = QLabel("Current Price: N/A")
        self.balance_label = QLabel("Account Balance: N/A")
        self.leveraged_balance_label = QLabel("Leveraged Balance: N/A")
        self.volume_label = QLabel("Order Volume: N/A")
        self.ping_label = QLabel("Ping: N/A")

        # Refresh button
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.update_funding_data)

        # Add widgets to layout
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

    def update_funding_interval(self, value):
        self.logic.update_funding_interval(float(value))

    def update_entry_time(self, value):
        self.logic.entry_time_seconds = value
        print(f"Updated entry time: {self.logic.entry_time_seconds} seconds")

    def update_qty(self, value):
        self.logic.qty = value
        print(f"Updated order quantity: {self.logic.qty}")
        self.update_volume_label()

    def update_profit_percentage(self, value):
        self.logic.profit_percentage = value
        self.profit_percentage_slider.setValue(int(value * 100))  # Sync slider
        print(f"Updated profit percentage: {self.logic.profit_percentage}%")

    def update_profit_percentage_from_slider(self, value):
        self.logic.profit_percentage = value / 100.0  # Convert back to percentage
        self.profit_percentage_spinbox.setValue(self.logic.profit_percentage)  # Sync spinbox
        print(f"Updated profit percentage from slider: {self.logic.profit_percentage}%")

    def update_leverage(self, value):
        self.logic.leverage = value
        print(f"Updated leverage: {self.logic.leverage}x")
        self.update_leveraged_balance_label()

    def update_volume_label(self):
        current_price = self.logic.get_current_price(self.logic.selected_symbol)
        balance = self.logic.get_account_balance()
        leveraged_balance = balance * self.logic.leverage if balance is not None and self.logic.leverage is not None else None
        if current_price is not None and self.logic.qty is not None:
            volume = self.logic.qty * current_price
            self.volume_label.setText(f"Order Volume: ${volume:.2f} USD")
            if volume < 5.0 or (leveraged_balance is not None and volume > leveraged_balance):
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
        self.logic.update_ping(self.ping_label)

    def check_funding_time(self):
        self.logic.check_funding_time(self.update_volume_label)

    def update_funding_data(self):
        self.logic.update_funding_data(self.price_label, self.balance_label, self.leveraged_balance_label, self.funding_info_label, self.volume_label, self.ping_label)

    def closeEvent(self, event):
        self.timer.stop()
        self.ping_timer.stop()
        event.accept()