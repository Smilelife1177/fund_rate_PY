import os
import logging
import asyncio
from pybit.unified_trading import WebSocket, HTTP
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')
SYMBOL = 'BTCUSDT'

if not API_KEY or not API_SECRET:
    logging.error("API_KEY or API_SECRET is missing in .env file")
    exit(1)

session = HTTP(testnet=True, api_key=API_KEY, api_secret=API_SECRET)
ws = WebSocket(testnet=True, channel_type="linear")

def handle_funding_rate_message(message):
    try:
        if 'topic' in message and message['topic'] == f'ticker.{SYMBOL}':
            funding_rate = float(message['data']['fundingRate'])
            logging.info(f"Funding Rate via WebSocket for {SYMBOL}: {funding_rate*100:.4f}%")
            trade_logic(funding_rate)
        else:
            logging.debug(f"Received WebSocket message: {message}")
    except Exception as e:
        logging.error(f"Error processing WebSocket message: {e}")

def get_funding_rate():
    try:
        response = session.get_tickers(category="linear", symbol=SYMBOL)
        if response['retCode'] == 0:
            funding_rate = float(response['result']['list'][0]['fundingRate'])
            return funding_rate
        else:
            logging.error(f"Error fetching funding rate: {response['retMsg']}")
            return None
    except Exception as e:
        logging.error(f"Error in get_funding_rate: {e}")
        return None

def check_api_permissions():
    try:
        response = session.get_api_key_information()
        if response['retCode'] == 0:
            logging.info(f"API key permissions: {response['result']}")
            return True
        else:
            logging.error(f"Invalid API key or permissions: {response['retMsg']}")
            return False
    except Exception as e:
        logging.error(f"Error checking API permissions: {e}")
        return False

def trade_logic(funding_rate):
    try:
        if funding_rate is None:
            return

        logging.info(f"Funding Rate for {SYMBOL}: {funding_rate*100:.4f}%")

        ticker = session.get_tickers(category="linear", symbol=SYMBOL)
        if ticker['retCode'] != 0:
            logging.error(f"Error fetching ticker: {ticker['retMsg']}")
            return
        last_price = float(ticker['result']['list'][0]['lastPrice'])

        balance = session.get_wallet_balance(accountType="UNIFIED")
        if balance['retCode'] == 0:
            available_balance = float(balance['result']['list'][0]['totalEquity'])
            if available_balance < (last_price * 0.001):
                logging.error("Insufficient balance to open position")
                return

        if funding_rate > 0.0005:
            logging.info(f"High funding rate detected: {funding_rate*100:.4f}%. Opening SHORT position.")
            order = session.place_order(
                category="linear",
                symbol=SYMBOL,
                side="Sell",
                orderType="Limit",
                qty=0.001,
                price=last_price * 0.99,  # 1% below last price
                timeInForce="GTC"
            )
            logging.info(f"Short position opened: {order}")
        elif funding_rate < -0.0005:
            logging.info(f"Low funding rate detected: {funding_rate*100:.4f}%. Opening LONG position.")
            order = session.place_order(
                category="linear",
                symbol=SYMBOL,
                side="Buy",
                orderType="Limit",
                qty=0.001,
                price=last_price * 1.01,  # 1% above last price
                timeInForce="GTC"
            )
            logging.info(f"Long position opened: {order}")
    except Exception as e:
        logging.error(f"Error in trade_logic: {e}")

async def main():
    if not check_api_permissions():
        logging.error("Stopping bot due to invalid API key")
        return

    try:
        ws.ticker_stream(callback=handle_funding_rate_message, symbol=SYMBOL)
        logging.info(f"Subscribed to WebSocket ticker stream for {SYMBOL}")
    except Exception as e:
        logging.error(f"Error subscribing to WebSocket: {e}")

    while True:
        funding_rate = get_funding_rate()
        trade_logic(funding_rate)
        await asyncio.sleep(28800)  # 8 hours

if __name__ == "__main__":
    logging.info("Starting Bybit funding rate trading bot...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        ws.exit()
        logging.info("WebSocket connection closed")