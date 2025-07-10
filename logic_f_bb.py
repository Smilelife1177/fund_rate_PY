import os
from datetime import datetime, timedelta, timezone
from pybit.unified_trading import HTTP
import math
import time

API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')

class FundingTraderLogic:
    def __init__(self):
        self.session = HTTP(
            testnet=False,
            api_key=API_KEY,
            api_secret=API_SECRET
        )
        self.selected_symbol = "MAGICUSDT"
        self.funding_interval_hours = 1.0
        self.entry_time_seconds = 5.0
        self.qty = 45
        self.profit_percentage = 1.0
        self.leverage = 4.0
        self.funding_data = None
        self.open_order_id = None
        self.funding_time_price = None

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
            tick_size = self.get_symbol_info(symbol)
            if tick_size:
                decimal_places = abs(int(math.log10(tick_size)))
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

    def update_ping(self):
        try:
            print("Pinging Bybit server...")
            start_time = time.time()
            response = self.session.get_server_time()
            end_time = time.time()
            if response["retCode"] == 0:
                ping_ms = (end_time - start_time) * 1000
                print(f"Ping: {ping_ms:.2f} ms")
                return ping_ms
            else:
                print(f"Error pinging server: {response['retMsg']}")
                return None
        except Exception as e:
            print(f"Error pinging server: {e}")
            return None