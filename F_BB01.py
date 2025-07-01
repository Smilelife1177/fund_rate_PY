import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QComboBox, QLabel, QDoubleSpinBox, QSlider
from PyQt6.QtCore import QTimer, Qt
from pybit.unified_trading import HTTP
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import math

API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')

class FundingTraderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit Funding Trader")
        self.setGeometry(100, 100, 400, 500)
        # Initialize Bybit client
        self.session = HTTP(
            testnet=False,
            api_key=API_KEY,
            api_secret=API_SECRET
        )

        # Trading parameters
        self.selected_symbol = "XEMUSDT" 
        self.funding_interval_hours = 1.0  # Bybit funding interval
        self.entry_time_seconds = 5.0  # Time before funding to enter
        self.qty = 1800  # Order quantity
        self.profit_percentage = 0.3  # Desired profit percentage
        self.funding_data = None
        self.open_order_id = None
        self.funding_time_price = None

        # Setup UI
        self.setup_ui()

        # Timer for checking funding time
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_funding_time)
        self.timer.start(1000)  # Check every second

        # Initial data update
        print("Initializing application...")
        self.update_funding_data()

    def setup_ui(self):
        print("Setting up UI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Coin selector
        self.coin_selector_label = QLabel("Select Coin:")
        self.coin_selector = QComboBox()
        self.coins = ["BTCUSDT", "XEMUSDT", "INJUSDT", "XRPUSDT", "CUDISUSDT"]
        self.coin_selector.addItems(self.coins)
        self.coin_selector.setCurrentText(self.selected_symbol)
        self.coin_selector.currentTextChanged.connect(self.update_symbol)

        # Funding interval
        self.funding_interval_label = QLabel("Funding Interval (hours):")
        self.funding_interval_combobox = QComboBox()
        self.funding_intervals = ["1", "4", "8"]
        self.funding_interval_combobox.addItems(self.funding_intervals)
        self.funding_interval_combobox.setCurrentText(str(int(self.funding_interval_hours)))
        self.funding_interval_combobox.currentTextChanged.connect(self.update_funding_interval)

        # Entry time
        self.entry_time_label = QLabel("Entry Time Before Funding (seconds):")
        self.entry_time_spinbox = QDoubleSpinBox()
        self.entry_time_spinbox.setRange(0.5, 10.0)
        self.entry_time_spinbox.setValue(self.entry_time_seconds)
        self.entry_time_spinbox.setSingleStep(0.1)
        self.entry_time_spinbox.valueChanged.connect(self.update_entry_time)

        # Order quantity
        self.qty_label = QLabel("Order Quantity (qty):")
        self.qty_spinbox = QDoubleSpinBox()
        self.qty_spinbox.setRange(0.001, 10000.0)
        self.qty_spinbox.setValue(self.qty)
        self.qty_spinbox.setSingleStep(0.001)
        self.qty_spinbox.valueChanged.connect(self.update_qty)

        # Profit percentage
        self.profit_percentage_label = QLabel("Desired Profit Percentage (%):")
        self.profit_percentage_spinbox = QDoubleSpinBox()
        self.profit_percentage_spinbox.setRange(0.1, 2.0)
        self.profit_percentage_spinbox.setValue(self.profit_percentage)
        self.profit_percentage_spinbox.setSingleStep(0.1)
        self.profit_percentage_spinbox.valueChanged.connect(self.update_profit_percentage)

        # Profit percentage slider
        self.profit_percentage_slider = QSlider(Qt.Orientation.Horizontal)
        self.profit_percentage_slider.setRange(10, 200)  # 0.1% to 2.0% (multiplied by 100 for integer steps)
        self.profit_percentage_slider.setValue(int(self.profit_percentage * 100))
        self.profit_percentage_slider.setSingleStep(10)  # 0.1% steps
        self.profit_percentage_slider.valueChanged.connect(self.update_profit_percentage_from_slider)

        # Display labels
        self.funding_info_label = QLabel("Funding Rate: N/A | Time to Next Funding: N/A")
        self.price_label = QLabel("Current Price: N/A")
        self.balance_label = QLabel("Account Balance: N/A")
        self.volume_label = QLabel("Order Volume: N/A")

        # Refresh button
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.update_funding_data)

        # Add widgets to layout
        layout.addWidget(self.coin_selector_label)
        layout.addWidget(self.coin_selector)
        layout.addWidget(self.funding_interval_label)
        layout.addWidget(self.funding_interval_combobox)
        layout.addWidget(self.entry_time_label)
        layout.addWidget(self.entry_time_spinbox)
        layout.addWidget(self.qty_label)
        layout.addWidget(self.qty_spinbox)
        layout.addWidget(self.profit_percentage_label)
        layout.addWidget(self.profit_percentage_spinbox)
        layout.addWidget(self.profit_percentage_slider)
        layout.addWidget(self.funding_info_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.balance_label)
        layout.addWidget(self.volume_label)
        layout.addWidget(self.refresh_button)
        print("UI setup completed")

    def update_symbol(self, symbol):
        self.selected_symbol = symbol
        print(f"Updated symbol: {self.selected_symbol}")
        self.update_funding_data()

    def update_funding_interval(self, value):
        self.funding_interval_hours = float(value)
        print(f"Updated funding interval: {self.funding_interval_hours} hours")
        self.update_funding_data()

    def update_entry_time(self, value):
        self.entry_time_seconds = value
        print(f"Updated entry time: {self.entry_time_seconds} seconds")

    def update_qty(self, value):
        self.qty = value
        print(f"Updated order quantity: {self.qty}")
        self.update_volume_label()

    def update_profit_percentage(self, value):
        self.profit_percentage = value
        self.profit_percentage_slider.setValue(int(value * 100))  # Sync slider
        print(f"Updated profit percentage: {self.profit_percentage}%")

    def update_profit_percentage_from_slider(self, value):
        self.profit_percentage = value / 100.0  # Convert back to percentage
        self.profit_percentage_spinbox.setValue(self.profit_percentage)  # Sync spinbox
        print(f"Updated profit percentage from slider: {self.profit_percentage}%")

    def update_volume_label(self):
        current_price = self.get_current_price(self.selected_symbol)
        if current_price is not None and self.qty is not None:
            volume = self.qty * current_price
            self.volume_label.setText(f"Order Volume: ${volume:.2f} USD")
            if volume < 5.0:
                self.volume_label.setStyleSheet("color: red;")
            else:
                self.volume_label.setStyleSheet("color: black;")
        else:
            self.volume_label.setText("Order Volume: N/A")
            self.volume_label.setStyleSheet("color: black;")

    def get_account_balance(self):
        try:
            print("Fetching account balance...")
            response = self.session.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            if response["retCode"] == 0 and response["result"]["list"]:
                balance = float(response["result"]["list"][0]["coin"][0]["walletBalance"])
                print(f"Account balance: {balance:.2f} USDT")
                return balance
            else:
                print(f"Error fetching balance: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return None

    def get_funding_data(self):
        try:
            print(f"Fetching funding rate for {self.selected_symbol}...")
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
                print(f"Processed {self.selected_symbol}: {funding_rate:.4f}%")
                return self.funding_data
            else:
                print(f"Error fetching funding rate: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Error fetching funding rate: {e}")
            return None

    def get_current_price(self, symbol):
        try:
            print(f"Fetching current price for {symbol}...")
            response = self.session.get_tickers(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                price = float(response["result"]["list"][0]["lastPrice"])
                print(f"Raw price fetched for {symbol}: {price}")
                return price
            else:
                print(f"Error fetching price: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Error fetching price: {e}")
            return None

    def get_next_funding_time(self, funding_time):
        funding_dt = datetime.fromtimestamp(funding_time, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        hours_since_last = (current_time - funding_dt).total_seconds() / 3600
        intervals_passed = int(hours_since_last / self.funding_interval_hours) + 1
        next_funding = funding_dt + timedelta(hours=intervals_passed * self.funding_interval_hours)
        time_diff = next_funding - current_time
        hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return time_diff.total_seconds(), f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def place_market_order(self, symbol, side, qty):
        try:
            print(f"Placing market {side} order for {symbol} with quantity {qty}...")
            response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
                timeInForce="GTC"
            )
            if response["retCode"] == 0:
                print(f"Market order placed: {response['result']}")
                return response["result"]["orderId"]
            else:
                print(f"Error placing market order: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Error placing market order: {e}")
            return None

    def get_symbol_info(self, symbol):
        try:
            response = self.session.get_instruments_info(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                price_filter = response["result"]["list"][0]["priceFilter"]
                tick_size = float(price_filter["tickSize"])
                print(f"Tick size for {symbol}: {tick_size}")
                return tick_size
            else:
                print(f"Error fetching symbol info: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Error fetching symbol info: {e}")
            return None

    def place_limit_close_order(self, symbol, side, qty, price):
        try:
            close_side = "Buy" if side == "Sell" else "Sell"
            # Adjust price to tick size
            tick_size = self.get_symbol_info(symbol)
            if tick_size:
                decimal_places = abs(int(math.log10(tick_size)))  # Calculate required decimal places
                price = round(price, decimal_places)
            print(f"Placing limit {close_side} order for {symbol} at {price} with quantity {qty}...")
            response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Limit",
                qty=str(qty),
                price=str(price),
                timeInForce="GTC",
                reduceOnly=True
            )
            if response["retCode"] == 0:
                print(f"Limit close order placed: {response['result']}")
                return response["result"]["orderId"]
            else:
                print(f"Error placing limit order: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Error placing limit order: {e}")
            return None

    def check_funding_time(self):
        if not self.funding_data:
            print("Funding data unavailable")
            self.funding_info_label.setText("Funding Rate: N/A | Time to Next Funding: N/A")
            self.price_label.setText("Current Price: N/A")
            self.balance_label.setText("Account Balance: N/A")
            self.volume_label.setText("Order Volume: N/A")
            self.volume_label.setStyleSheet("color: black;")
            return

        symbol = self.funding_data["symbol"]
        funding_rate = self.funding_data["funding_rate"]
        funding_time = self.funding_data["funding_time"]

        time_to_funding, time_str = self.get_next_funding_time(funding_time)
        self.funding_info_label.setText(f"Funding Rate: {funding_rate:.4f}% | Time to Next Funding: {time_str}")
        print(f"Time to next funding for {symbol}: {time_str}")

        # Check if within entry window
        if self.entry_time_seconds - 1.0 <= time_to_funding <= self.entry_time_seconds and not self.open_order_id:
            side = "Buy" if funding_rate > 0 else "Sell"
            self.open_order_id = self.place_market_order(symbol, side, self.qty)
            if self.open_order_id:
                # Schedule price capture 1 second before funding
                QTimer.singleShot(int((time_to_funding - 1.0) * 1000), lambda: self.capture_funding_price(symbol, side))

    def capture_funding_price(self, symbol, side):
        self.funding_time_price = self.get_current_price(symbol)
        if self.funding_time_price is None:
            print(f"Failed to get price at funding time for {symbol}")
            self.open_order_id = None
            return

        funding_rate = abs(self.funding_data["funding_rate"])
        # Calculate limit price: funding price ± (|funding_rate| + user-defined profit_percentage%)
        limit_price = (self.funding_time_price * (1 + (funding_rate + self.profit_percentage)/100) if side == "Buy" 
                      else self.funding_time_price * (1 - (funding_rate + self.profit_percentage)/100))
        self.place_limit_close_order(symbol, side, self.qty, limit_price)
        self.open_order_id = None

    def update_funding_data(self):
        try:
            print("Updating funding data...")
            self.funding_data = self.get_funding_data()

            current_price = self.get_current_price(self.selected_symbol)
            if current_price is not None:
                self.price_label.setText(f"Current Price: ${current_price:.6f}")
            else:
                self.price_label.setText("Current Price: N/A")

            balance = self.get_account_balance()
            if balance is not None:
                self.balance_label.setText(f"Account Balance: ${balance:.2f} USDT")
            else:
                self.balance_label.setText("Account Balance: N/A")

            if self.funding_data:
                funding_rate = self.funding_data["funding_rate"]
                funding_time = self.funding_data["funding_time"]
                _, time_str = self.get_next_funding_time(funding_time)
                self.funding_info_label.setText(f"Funding Rate: {funding_rate:.4f}% | Time to Next Funding: {time_str}")
            else:
                self.funding_info_label.setText("Funding Rate: N/A | Time to Next Funding: N/A")
                self.price_label.setText("Current Price: N/A")
                self.balance_label.setText("Account Balance: N/A")
                self.volume_label.setText("Order Volume: N/A")
                self.volume_label.setStyleSheet("color: black;")

            self.update_volume_label()

            print("Data updated successfully")

        except Exception as e:
            print(f"Error updating funding data: {e}")
            self.funding_info_label.setText("Funding Rate: Error | Time to Next Funding: Error")
            self.price_label.setText("Current Price: Error")
            self.balance_label.setText("Account Balance: Error")
            self.volume_label.setText("Order Volume: Error")
            self.volume_label.setStyleSheet("color: black;")

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication(sys.argv)
    window = FundingTraderApp()
    window.show()
    sys.exit(app.exec())