import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import math
import time
from pybit.unified_trading import HTTP
from binance.client import Client as BinanceClient

def initialize_client(exchange, testnet=False):
    load_dotenv()
    
    if exchange == "Bybit":
        if testnet:
            api_key = os.getenv('BYBIT_API_KEY_TEST')
            api_secret = os.getenv('BYBIT_API_SECRET_TEST')
        else:
            api_key = os.getenv('BYBIT_API_KEY')
            api_secret = os.getenv('BYBIT_API_SECRET')
        if not api_key or not api_secret:
            raise ValueError("Bybit API key or secret not found in environment variables")
        return HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)
    else:  # Binance
        if testnet:
            api_key = os.getenv('BINANCE_API_KEY_TEST')
            api_secret = os.getenv('BINANCE_API_SECRET_TEST')
        else:
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_API_SECRET')
        if not api_key or not api_secret:
            raise ValueError("Binance API key or secret not found in environment variables")
        return BinanceClient(api_key, api_secret, testnet=testnet)

def get_account_balance(session, exchange):
    try:
        print("Fetching account balance...")
        if exchange == "Bybit":
            response = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
            if response["retCode"] == 0 and response["result"]["list"]:
                balance = float(response["result"]["list"][0]["coin"][0]["walletBalance"])
                print(f"Account balance: {balance:.2f} USDT")
                return balance
            else:
                print(f"Error fetching balance: {response['retMsg']}")
                return None
        else:  # Binance
            response = session.get_account()
            for asset in response["balances"]:
                if asset["asset"] == "USDT":
                    balance = float(asset["free"]) + float(asset["locked"])
                    print(f"Account balance: {balance:.2f} USDT")
                    return balance
            print("USDT balance not found")
            return None
    except Exception as e:
        print(f"Error fetching balance: {e}")
        return None

def get_funding_data(session, symbol, exchange):
    try:
        print(f"Fetching funding rate for {symbol}...")
        if exchange == "Bybit":
            response = session.get_funding_rate_history(category="linear", symbol=symbol, limit=1)
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
        else:  # Binance
            response = session.get_premium_index(symbol=symbol)
            funding_rate = float(response["lastFundingRate"]) * 100
            funding_time = int(response["nextFundingTime"]) / 1000
            return {
                "symbol": symbol,
                "funding_rate": funding_rate,
                "funding_time": funding_time
            }
    except Exception as e:
        print(f"Error fetching funding rate: {e}")
        return None

def get_current_price(session, symbol, exchange):
    try:
        print(f"Fetching current price for {symbol}...")
        if exchange == "Bybit":
            response = session.get_tickers(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                price = float(response["result"]["list"][0]["lastPrice"])
                print(f"Raw price fetched for {symbol}: {price}")
                return price
            else:
                print(f"Error fetching price: {response['retMsg']}")
                return None
        else:  # Binance
            response = session.get_symbol_ticker(symbol=symbol)
            price = float(response["price"])
            print(f"Raw price fetched for {symbol}: {price}")
            return price
    except Exception as e:
        print(f"Error fetching price: {e}")
        return None

def get_optimal_limit_price(session, symbol, side, current_price, exchange, profit_percentage, tick_size):
    """Fetch order book and determine optimal limit price based on order density."""
    try:
        print(f"Fetching order book for {symbol} to determine optimal limit price...")
        if exchange == "Bybit":
            response = session.get_orderbook(category="linear", symbol=symbol, limit=50)
            if response["retCode"] != 0 or not response["result"]:
                print(f"Error fetching order book: {response['retMsg']}")
                return None
            orderbook = response["result"]
            bids = [(float(price), float(qty)) for price, qty in orderbook["b"]]
            asks = [(float(price), float(qty)) for price, qty in orderbook["a"]]
        else:  # Binance
            response = session.get_order_book(symbol=symbol, limit=50)
            bids = [(float(price), float(qty)) for price, qty in response["bids"]]
            asks = [(float(price), float(qty)) for price, qty in response["asks"]]

        # Define price range based on side and profit percentage
        if side == "Buy":
            # For Buy, we place a Sell limit order above current price
            min_price = current_price * (1 + profit_percentage / 200)  # Halfway to profit target
            max_price = current_price * (1 + profit_percentage / 50)    # Up to 2x profit target
            relevant_orders = [(price, qty) for price, qty in asks if min_price <= price <= max_price]
        else:  # Sell
            # For Sell, we place a Buy limit order below current price
            max_price = current_price * (1 - profit_percentage / 200)
            min_price = current_price * (1 - profit_percentage / 50)
            relevant_orders = [(price, qty) for price, qty in bids if min_price <= price <= max_price]

        if not relevant_orders:
            print(f"No orders found in the desired price range for {symbol}")
            return None

        # Find price with highest cumulative volume
        price_volumes = {}
        for price, qty in relevant_orders:
            rounded_price = round(price, abs(int(math.log10(tick_size)))) if tick_size else price
            price_volumes[rounded_price] = price_volumes.get(rounded_price, 0) + qty

        if not price_volumes:
            print(f"No valid price levels found after rounding for {symbol}")
            return None

        optimal_price = max(price_volumes, key=price_volumes.get)
        print(f"Optimal limit price for {symbol}: {optimal_price} (volume: {price_volumes[optimal_price]})")
        return optimal_price

    except Exception as e:
        print(f"Error fetching optimal limit price: {e}")
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

def place_market_order(session, symbol, side, qty, exchange):
    try:
        print(f"Placing market {side} order for {symbol} with quantity {qty}...")
        if exchange == "Bybit":
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
        else:  # Binance
            response = session.create_order(
                symbol=symbol,
                side=side.upper(),
                type="MARKET",
                quantity=qty
            )
            print(f"Market order placed: {response}")
            return response["orderId"]
    except Exception as e:
        print(f"Error placing market order: {e}")
        return None

def get_symbol_info(session, symbol, exchange):
    try:
        if exchange == "Bybit":
            response = session.get_instruments_info(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                price_filter = response["result"]["list"][0]["priceFilter"]
                tick_size = float(price_filter["tickSize"])
                print(f"Tick size for {symbol}: {tick_size}")
                return tick_size
            else:
                print(f"Error fetching symbol info: {response['retMsg']}")
                return None
        else:  # Binance
            response = session.get_symbol_info(symbol)
            for filt in response["filters"]:
                if filt["filterType"] == "PRICE_FILTER":
                    tick_size = float(filt["tickSize"])
                    print(f"Tick size for {symbol}: {tick_size}")
                    return tick_size
            print("Price filter not found")
            return None
    except Exception as e:
        print(f"Error fetching symbol info: {e}")
        return None

def place_limit_close_order(session, symbol, side, qty, price, tick_size, exchange):
    try:
        close_side = "Buy" if side == "Sell" else "Sell"
        if tick_size:
            decimal_places = abs(int(math.log10(tick_size)))
            price = round(price, decimal_places)
        print(f"Placing limit {close_side} order for {symbol} at {price} with quantity {qty}...")
        if exchange == "Bybit":
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
        else:  # Binance
            response = session.create_order(
                symbol=symbol,
                side=close_side.upper(),
                type="LIMIT",
                quantity=qty,
                price=str(price),
                timeInForce="GTC",
                reduceOnly=True
            )
            print(f"Limit close order placed: {response}")
            return response["orderId"]
    except Exception as e:
        print(f"Error placing limit order: {e}")
        return None

def close_all_positions(session, exchange, symbol=None):
    """Close all open positions on the exchange."""
    try:
        print(f"Closing all open positions on {exchange}...")
        if exchange == "Bybit":
            response = session.get_positions(category="linear", settleCoin="USDT")
            print(f"Bybit positions response: {response}")
            if response["retCode"] == 0 and response["result"]["list"]:
                for position in response["result"]["list"]:
                    position_symbol = position["symbol"]
                    if symbol and position_symbol != symbol:
                        continue
                    qty = float(position["size"])
                    side = "Sell" if position["side"] == "Buy" else "Buy"
                    if qty > 0:
                        response_order = session.place_order(
                            category="linear",
                            symbol=position_symbol,
                            side=side,
                            orderType="Market",
                            qty=str(qty),
                            timeInForce="GTC",
                            reduceOnly=True
                        )
                        if response_order["retCode"] == 0:
                            print(f"Closed position for {position_symbol}: {response_order['result']}")
                        else:
                            print(f"Error closing position for {position_symbol}: {response_order['retMsg']}")
                return True
            else:
                print(f"No open positions or error: {response.get('retMsg', 'No error message')}")
                return False
        else:  # Binance
            response = session.get_position_information()
            print(f"Binance positions response: {response}")
            if response:
                for position in response:
                    position_symbol = position["symbol"]
                    if symbol and position_symbol != symbol:
                        continue
                    qty = abs(float(position["positionAmt"]))
                    side = "Sell" if float(position["positionAmt"]) > 0 else "Buy"
                    if qty > 0:
                        response_order = session.create_order(
                            symbol=position_symbol,
                            side=side.upper(),
                            type="MARKET",
                            quantity=qty,
                            reduceOnly=True
                        )
                        print(f"Closed position for {position_symbol}: {response_order}")
                return True
            else:
                print("No open positions found or error fetching positions")
                return False
    except Exception as e:
        print(f"Error closing positions: {e}")
        return False

def update_ping(session, ping_label, exchange):
    try:
        print(f"Pinging {exchange} server...")
        start_time = time.time()
        if exchange == "Bybit":
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
        else:  # Binance
            response = session.get_server_time()
            end_time = time.time()
            ping_ms = (end_time - start_time) * 1000
            ping_label.setText(f"Ping: {ping_ms:.2f} ms")
            if ping_ms > 500:
                ping_label.setStyleSheet("color: red;")
            else:
                ping_label.setStyleSheet("color: black;")
            print(f"Ping: {ping_ms:.2f} ms")
    except Exception as e:
        ping_label.setText("Ping: Error")
        ping_label.setStyleSheet("color: red;")
        print(f"Error pinging server: {e}")