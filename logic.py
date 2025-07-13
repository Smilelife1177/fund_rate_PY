import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import math
import time
from pybit.unified_trading import HTTP

def initialize_bybit_client(testnet=False):
    load_dotenv()
    
    if testnet:
        api_key = os.getenv('BYBIT_API_KEY_TEST')
        api_secret = os.getenv('BYBIT_API_SECRET_TEST')
    else:
        api_key = os.getenv('BYBIT_API_KEY')
        api_secret = os.getenv('BYBIT_API_SECRET')
    
    if not api_key or not api_secret:
        raise ValueError("API key or secret not found in environment variables")
    
    return HTTP(
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret
    )

def get_account_balance(session):
    try:
        print("Fetching account balance...")
        response = session.get_wallet_balance(
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

def get_funding_data(session, symbol):
    try:
        print(f"Fetching funding rate for {symbol}...")
        response = session.get_funding_rate_history(
            category="linear",
            symbol=symbol,
            limit=1
        )
        if response["retCode"] == 0 and response["result"]["list"]:
            funding_data = response["result"]["list"][0]
            funding_rate = float(funding_data["fundingRate"]) * 100
            funding_time = int(funding_data["fundingRateTimestamp"]) / 1000
            return {
                "symbol": symbol,
                "funding_rate": funding_rate,
                "funding_time": funding_time
            }
        else:
            print(f"Error fetching funding rate: {response['retMsg']}")
            return None
    except Exception as e:
        print(f"Error fetching funding rate: {e}")
        return None

def get_current_price(session, symbol):
    try:
        print(f"Fetching current price for {symbol}...")
        response = session.get_tickers(category="linear", symbol=symbol)
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

def get_next_funding_time(funding_time, funding_interval_hours):
    funding_dt = datetime.fromtimestamp(funding_time, tz=timezone.utc)
    current_time = datetime.now(timezone.utc)
    hours_since_last = (current_time - funding_dt).total_seconds() / 3600
    intervals_passed = int(hours_since_last / funding_interval_hours) + 1
    next_funding = funding_dt + timedelta(hours=intervals_passed * funding_interval_hours)
    time_diff = next_funding - current_time
    hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return time_diff.total_seconds(), f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def place_market_order(session, symbol, side, qty):
    try:
        print(f"Placing market {side} order for {symbol} with quantity {qty}...")
        response = session.place_order(
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

def get_symbol_info(session, symbol):
    try:
        response = session.get_instruments_info(category="linear", symbol=symbol)
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

def place_limit_close_order(session, symbol, side, qty, price, tick_size):
    try:
        close_side = "Buy" if side == "Sell" else "Sell"
        if tick_size:
            decimal_places = abs(int(math.log10(tick_size)))
            price = round(price, decimal_places)
        print(f"Placing limit {close_side} order for {symbol} at {price} with quantity {qty}...")
        response = session.place_order(
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

def update_ping(session, ping_label):
    try:
        print("Pinging Bybit server...")
        start_time = time.time()
        response = session.get_server_time()
        end_time = time.time()
        if response["retCode"] == 0:
            ping_ms = (end_time - start_time) * 1000
            ping_label.setText(f"Ping: {ping_ms:.2f} ms")
            if ping_ms > 500:
                ping_label.setStyleSheet("color: red;")
            else:
                ping_label.setStyleSheet("color: black;")
            print(f"Ping: {ping_ms:.2f} ms")
        else:
            ping_label.setText("Ping: Error")
            ping_label.setStyleSheet("color: red;")
            print(f"Error pinging server: {response['retMsg']}")
    except Exception as e:
        ping_label.setText("Ping: Error")
        ping_label.setStyleSheet("color: red;")
        print(f"Error pinging server: {e}")