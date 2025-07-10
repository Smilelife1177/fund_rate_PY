import os
import time
import math
from datetime import datetime, timedelta, timezone
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')

class FundingTraderLogic:
    def __init__(self):
        self.session = HTTP(
            testnet=False,
            api_key=API_KEY,
            api_secret=API_SECRET
        )
        self.funding_data = None
        self.open_order_id = None
        self.funding_time_price = None

    def get_account_balance(self):
        try:
            response = self.session.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            if response["retCode"] == 0 and response["result"]["list"]:
                balance = float(response["result"]["list"][0]["coin"][0]["walletBalance"])
                return balance
            else:
                return None
        except Exception as e:
            return None

    def get_funding_data(self, symbol):
        try:
            response = self.session.get_funding_rate_history(
                category="linear",
                symbol=symbol,
                limit=1
            )
            if response["retCode"] == 0 and response["result"]["list"]:
                funding_data = response["result"]["list"][0]
                funding_rate = float(funding_data["fundingRate"]) * 100
                funding_time = int(funding_data["fundingRateTimestamp"]) / 1000
                self.funding_data = {
                    "symbol": symbol,
                    "funding_rate": funding_rate,
                    "funding_time": funding_time
                }
                return self.funding_data
            else:
                return None
        except Exception as e:
            return None

    def get_current_price(self, symbol):
        try:
            response = self.session.get_tickers(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                price = float(response["result"]["list"][0]["lastPrice"])
                return price
            else:
                return None
        except Exception as e:
            return None

    def place_market_order(self, symbol, side, qty):
        try:
            response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
                timeInForce="GTC"
            )
            if response["retCode"] == 0:
                return response["result"]["orderId"]
            else:
                return None
        except Exception as e:
            return None

    def get_next_funding_time(self, funding_time, funding_interval_hours):
        funding_dt = datetime.fromtimestamp(funding_time, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        hours_since_last = (current_time - funding_dt).total_seconds() / 3600
        intervals_passed = int(hours_since_last / funding_interval_hours) + 1
        next_funding = funding_dt + timedelta(hours=intervals_passed * funding_interval_hours)
        time_diff = next_funding - current_time
        return time_diff.total_seconds(), time_diff

    def place_limit_close_order(self, symbol, side, qty, price):
        try:
            close_side = "Buy" if side == "Sell" else "Sell"
            tick_size = self.get_symbol_info(symbol)
            if tick_size:
                decimal_places = abs(int(math.log10(tick_size)))
                price = round(price, decimal_places)
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
                return response["result"]["orderId"]
            else:
                return None
        except Exception as e:
            return None

    def get_symbol_info(self, symbol):
        try:
            response = self.session.get_instruments_info(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                price_filter = response["result"]["list"][0]["priceFilter"]
                tick_size = float(price_filter["tickSize"])
                return tick_size
            else:
                return None
        except Exception as e:
            return None