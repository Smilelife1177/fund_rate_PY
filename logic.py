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
    """Fetch current (live) funding rate and next funding time via tickers endpoint."""
    try:
        print(f"Fetching funding rate for {symbol}...")
        if exchange == "Bybit":
            response = session.get_tickers(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                ticker = response["result"]["list"][0]
                funding_rate = float(ticker["fundingRate"]) * 100
                # nextFundingTime is ms timestamp
                next_ft_ms = int(ticker.get("nextFundingTime") or 0)
                funding_time = next_ft_ms / 1000.0
                print(f"Funding rate for {symbol}: {funding_rate:.4f}%, next at {funding_time}")
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
            print(f"Funding rate for {symbol}: {funding_rate:.4f}%, next at {funding_time}")
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

def get_candle_open_price(session, symbol, exchange):
    """Fetch the open price of the latest 1-minute candle."""
    try:
        print(f"Fetching 1-minute candle open price for {symbol}...")
        if exchange == "Bybit":
            response = session.get_kline(
                category="linear",
                symbol=symbol,
                interval="1",
                limit=1
            )
            if response["retCode"] == 0 and response["result"]["list"]:
                open_price = float(response["result"]["list"][0][1])  # Open price is second element in kline
                print(f"1-minute candle open price for {symbol}: {open_price}")
                return open_price
            else:
                print(f"Error fetching candle data: {response['retMsg']}")
                return None
        else:  # Binance
            response = session.get_klines(symbol=symbol, interval="1m", limit=1)
            open_price = float(response[0][1])  # Open price is second element in kline
            print(f"1-minute candle open price for {symbol}: {open_price}")
            return open_price
    except Exception as e:
        print(f"Error fetching candle open price: {e}")
        return None

def place_stop_loss_order(session, symbol, side, qty, stop_price, tick_size, exchange):
    try:
        qty_step = get_qty_step(session, symbol, exchange)
        qty = round_qty(qty, qty_step)
        close_side = "Buy" if side == "Sell" else "Sell"
        if tick_size:
            decimal_places = abs(int(math.log10(tick_size)))
            stop_price = round(stop_price, decimal_places)
        print(f"Placing stop-loss {close_side} order for {symbol} at {stop_price} with quantity {qty}...")
        if exchange == "Bybit":
            response = session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(qty),
                stopPrice=str(stop_price),
                triggerDirection=1 if side == "Buy" else 2,
                timeInForce="GTC",
                reduceOnly=True
            )
            if response["retCode"] == 0:
                print(f"Stop-loss order placed: {response['result']}")
                return response["result"]["orderId"]
            else:
                print(f"Error placing stop-loss order: {response['retMsg']}")
                return None
        else:  # Binance
            response = session.create_order(
                symbol=symbol,
                side=close_side.upper(),
                type="STOP_MARKET",
                quantity=qty,
                stopPrice=str(stop_price),
                reduceOnly=True
            )
            print(f"Stop-loss order placed: {response}")
            return response["orderId"]
    except Exception as e:
        print(f"Error placing stop-loss order: {e}")
        return None

def get_optimal_limit_price(session, symbol, side, current_price, exchange, profit_percentage, tick_size):
    """Покращена версія з правильним боком ордербуку."""
    try:
        print(f"Fetching order book for {symbol} to determine optimal limit price...")

        if exchange == "Bybit":
            response = session.get_orderbook(category="linear", symbol=symbol, limit=50)
            if response["retCode"] != 0 or not response["result"]:
                return None
            bids = [(float(p), float(q)) for p, q in response["result"]["b"]]
            asks = [(float(p), float(q)) for p, q in response["result"]["a"]]
        else:  # Binance
            response = session.get_order_book(symbol=symbol, limit=50)
            bids = [(float(p), float(q)) for p, q in response["bids"]]
            asks = [(float(p), float(q)) for p, q in response["asks"]]

        # Правильний бік ордербуку
        if side == "Buy":   # Лонг → Sell limit → шукаємо в bids
            target = current_price * (1 + profit_percentage / 100)
            min_p = target * 0.992
            max_p = target * 1.018
            relevant = [(price, qty) for price, qty in bids if min_p <= price <= max_p]
        else:               # Шорт → Buy limit → шукаємо в asks
            target = current_price * (1 - profit_percentage / 100)
            min_p = target * 0.982
            max_p = target * 1.008
            relevant = [(price, qty) for price, qty in asks if min_p <= price <= max_p]

        if not relevant:
            print(f"No liquidity in target range for {symbol}")
            return None

        decimal_places = abs(int(math.log10(tick_size))) if tick_size else 4
        price_volumes = {}
        for price, qty in relevant:
            rounded = round(price, decimal_places)
            price_volumes[rounded] = price_volumes.get(rounded, 0) + qty

        optimal_price = max(price_volumes, key=price_volumes.get)
        print(f"Optimal limit price: {optimal_price} (volume: {price_volumes[optimal_price]:.1f})")

        actual_profit = abs((optimal_price - current_price) / current_price * 100)
        if abs(actual_profit - profit_percentage) <= 0.20:
            return optimal_price
        else:
            return None

    except Exception as e:
        print(f"Error in get_optimal_limit_price: {e}")
        return None

def get_next_funding_time(funding_time, funding_interval_hours):
    funding_dt = datetime.fromtimestamp(funding_time, tz=timezone.utc)
    current_time = datetime.now(timezone.utc)

    # Якщо час з API вже в майбутньому — це і є наступний фандинг
    if funding_dt > current_time:
        next_funding = funding_dt
    else:
        # Час в минулому — рахуємо наступний через інтервал
        hours_since_last = (current_time - funding_dt).total_seconds() / 3600
        intervals_passed = int(hours_since_last / funding_interval_hours) + 1
        next_funding = funding_dt + timedelta(hours=intervals_passed * funding_interval_hours)

    time_diff = next_funding - current_time
    hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return time_diff.total_seconds(), f"{hours:02d}:{minutes:02d}:{seconds:02d}"
#
def place_market_order(session, symbol, side, qty, exchange):
    try:
        qty_step = get_qty_step(session, symbol, exchange)
        rounded_qty = round_qty(qty, qty_step)
        
        print(f"Placing market {side} order for {symbol} with quantity {rounded_qty} (original: {qty}, step: {qty_step})...")
        
        if exchange == "Bybit":
            response = session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(rounded_qty),
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

def get_order_execution_price(session, symbol, order_id, exchange):
    try:
        if exchange == "Bybit":
            response = session.get_order_history(category="linear", symbol=symbol, orderId=order_id)
            if response["retCode"] != 0 or not response["result"]["list"]:
                print(f"Error fetching order execution price for {symbol}: {response['retMsg']}")
                return None
            order = response["result"]["list"][0]
            execution_price = float(order.get("avgPrice", 0.0))
            return execution_price if execution_price > 0 else None
        else:  # Binance
            response = session.get_order(symbol=symbol, orderId=order_id)
            if "avgPrice" in response:
                execution_price = float(response["avgPrice"])
                return execution_price if execution_price > 0 else None
            else:
                print(f"Error fetching order execution price for {symbol}: No avgPrice in response")
                return None
    except Exception as e:
        print(f"Error fetching order execution price for {symbol}: {e}")
        return None

def place_limit_close_order(session, symbol, side, qty, price, tick_size, exchange):
    try:
        qty_step = get_qty_step(session, symbol, exchange)
        qty = round_qty(qty, qty_step)
        print(f"Placing limit {side} order for {symbol} with quantity {rounded_qty} (original: {qty}, step: {qty_step})...")
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
                qty=str(rounded_qty),
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
        qty_step = get_qty_step(session, symbol, exchange)
        qty = round_qty(qty, qty_step)
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
                            time.sleep(1)  # Wait for execution
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


def set_leverage(session, symbol, leverage, exchange):
    try:
        lev = int(leverage)
        if exchange == "Bybit":
            response = session.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(lev),
                sellLeverage=str(lev),
            )
            if response["retCode"] == 0:
                print(f"Leverage set to {lev}x for {symbol}")
                return True
            else:
                print(f"Error setting leverage: {response['retMsg']}")
                return False
        else:  # Binance
            response = session.futures_change_leverage(symbol=symbol, leverage=lev)
            print(f"Leverage set to {lev}x for {symbol}")
            return True
    except Exception as e:
        print(f"Error setting leverage: {e}")
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

def get_qty_step(session, symbol, exchange):
    """Повертає мінімальний крок qty для символу."""
    try:
        if exchange == "Bybit":
            response = session.get_instruments_info(category="linear", symbol=symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                lot_filter = response["result"]["list"][0]["lotSizeFilter"]
                return float(lot_filter["qtyStep"])
        else:  # Binance
            info = session.get_symbol_info(symbol)
            for f in info["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    return float(f["stepSize"])
        return None
    except Exception as e:
        print(f"Error fetching qty step: {e}")
        return None

def get_closed_trades(session, exchange, limit=50):
    """Оновлена версія імпорту — ближче до ручного введення (крапка, без лапок)."""
    try:
        if exchange == "Bybit":
            pnl_resp = session.get_closed_pnl(category="linear", limit=limit)
            if pnl_resp["retCode"] != 0:
                print(f"Error fetching closed pnl: {pnl_resp['retMsg']}")
                return []

            log_resp = session.get_transaction_log(category="linear", limit=400)  # збільшили ліміт
            log_entries = log_resp["result"]["list"] if log_resp.get("retCode") == 0 else []

            trades = []
            for pos in pnl_resp["result"]["list"]:
                symbol      = pos["symbol"]
                qty         = float(pos.get("qty", 0))
                entry_price = float(pos.get("avgEntryPrice", 0))
                exit_price  = float(pos.get("avgExitPrice", 0))
                closed_pnl  = float(pos.get("closedPnl", 0))      # net pnl після всіх fee
                created_ms  = int(pos.get("createdTime", 0))
                updated_ms  = int(pos.get("updatedTime", 0))

                # === В-сделке (тривалість) ===
                duration_sec = (updated_ms - created_ms) / 1000.0
                if duration_sec < 1:
                    in_trade = "0с"
                elif duration_sec < 60:
                    in_trade = f"{int(duration_sec)}с"
                else:
                    in_trade = f"{int(duration_sec // 60)}хв"

                trade_time = datetime.fromtimestamp(created_ms / 1000).strftime("%Y-%m-%d %H:%M")

                volume = round(qty * entry_price, 2)

                # === Процент (від об'єму угоди) ===
                profit_pct = round((closed_pnl / volume) * 100, 2) if volume > 0 else 0.0

                # === Комісія + Фандинг ===
                commission = 0.0
                funding    = 0.0

                for entry in log_entries:
                    if entry.get("symbol") != symbol:
                        continue
                    entry_ms = int(entry.get("transactionTime", 0))
                    # Розширили вікно, бо funding може приходити з невеликою затримкою
                    if not (created_ms - 30000 <= entry_ms <= updated_ms + 30000):
                        continue

                    tx_type = entry.get("type", "")
                    if tx_type == "TRADE":
                        commission += abs(float(entry.get("fee", 0)))
                    elif tx_type == "SETTLEMENT":
                        funding += float(entry.get("cashFlow", 0))

                # === Доход (gross прибуток без комісії та фандингу) ===
                # closed_pnl вже включає вирахування fee і funding, тому gross ≈ closed_pnl + commission + funding (з урахуванням знаків)
                gross_income = closed_pnl + commission + funding   # funding може бути негативним

                trades.append({
                    "datetime":   trade_time,
                    "profit_pct": f"{profit_pct:+.2f}%",           # +0.95% або -0.53%
                    "funding":    f"{round(funding, 2):.2f}",      # -0.53
                    "pnl":        f"{round(closed_pnl, 3):.3f}",   # 0.040
                    "income":     f"{round(gross_income, 2):.2f}", # головне поле, яке треба виправити
                    "commission": f"{round(commission, 2):.2f}",
                    "volume":     f"{volume:.2f}",
                    "in_trade":   in_trade,
                    "symbol":     symbol,
                })

            return trades

        else:
            print("Binance import not implemented yet")
            return []

    except Exception as e:
        print(f"Error fetching closed trades: {e}")
        return []



def round_qty(qty: float, qty_step: float) -> float:
    """Округляє кількість до дозволеного кроку біржі."""
    if not qty_step or qty_step <= 0:
        return round(qty, 3)
    return math.floor(qty / qty_step) * qty_step