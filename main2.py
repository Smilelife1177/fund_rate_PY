import os
import logging
import asyncio
from pybit.unified_trading import WebSocket, HTTP
from dotenv import load_dotenv

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Завантаження API ключів із .env файлу
load_dotenv()
API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')

# Символ для торгівлі
SYMBOL = 'BTCUSDT'

# Перевірка API ключів
if not API_KEY or not API_SECRET:
    logging.error("API_KEY or API_SECRET is missing in .env file")
    exit(1)

# Ініціалізація HTTP клієнта для REST API
session = HTTP(
    testnet=True,  # Використовуємо Testnet
    api_key=API_KEY,
    api_secret=API_SECRET
)

# Ініціалізація WebSocket клієнта
ws = WebSocket(
    testnet=True,  # Використовуємо Testnet
    channel_type="linear"  # Для USDT-M ф’ючерсів
)

# Функція обробки WebSocket повідомлень
def handle_funding_rate_message(message):
    try:
        if 'topic' in message and message['topic'] == f'publicTrade.{SYMBOL}':
            logging.info(f"Trade data for {SYMBOL}: {message['data']}")
        else:
            logging.debug(f"Received WebSocket message: {message}")
    except Exception as e:
        logging.error(f"Error processing WebSocket message: {e}")

# Функція для отримання funding rate через REST API
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

# Функція для перевірки API дозволів
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

# Торгова логіка
def trade_logic(funding_rate):
    try:
        if funding_rate is None:
            return

        logging.info(f"Funding Rate for {SYMBOL}: {funding_rate*100:.4f}%")

        # Якщо funding rate > 0.05%, відкриваємо коротку позицію
        if funding_rate > 0.0005:  # 0.05%
            logging.info(f"High funding rate detected: {funding_rate*100:.4f}%. Opening SHORT position.")
            try:
                order = session.place_order(
                    category="linear",
                    symbol=SYMBOL,
                    side="Sell",
                    orderType="Market",
                    qty=0.001,  # Розмір позиції (налаштуйте відповідно)
                    timeInForce="GTC"
                )
                logging.info(f"Short position opened: {order}")
            except Exception as e:
                logging.error(f"Error opening short position: {e}")
        # Якщо funding rate < -0.05%, відкриваємо довгу позицію
        elif funding_rate < -0.0005:  # -0.05%
            logging.info(f"Low funding rate detected: {funding_rate*100:.4f}%. Opening LONG position.")
            try:
                order = session.place_order(
                    category="linear",
                    symbol=SYMBOL,
                    side="Buy",
                    orderType="Market",
                    qty=0.001,  # Розмір позиції
                    timeInForce="GTC"
                )
                logging.info(f"Long position opened: {order}")
            except Exception as e:
                logging.error(f"Error opening long position: {e}")
    except Exception as e:
        logging.error(f"Error in trade_logic: {e}")

# Асинхронна функція для WebSocket і періодичного отримання funding rate
async def main():
    # Перевірка API дозволів
    if not check_api_permissions():
        logging.error("Stopping bot due to invalid API key")
        return

    # Підписка на WebSocket publicTrade
    try:
        ws.subscribe([f"publicTrade.{SYMBOL}"], callback=handle_funding_rate_message)
        logging.info(f"Subscribed to WebSocket stream for {SYMBOL}")
    except Exception as e:
        logging.error(f"Error subscribing to WebSocket: {e}")

    # Періодична перевірка funding rate
    while True:
        funding_rate = get_funding_rate()
        trade_logic(funding_rate)
        await asyncio.sleep(300)  # Оновлення кожні 5 хвилин (funding rate оновлюється кожні 8 годин)

# Запуск програми
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