import os
import logging
from pybit.unified_trading import WebSocket
from dotenv import load_dotenv
import time
import asyncio

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Завантаження API ключів із .env файлу
load_dotenv()
API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')

# Символ для торгівлі
SYMBOL = 'BTCUSDT'

# Ініціалізація WebSocket клієнта
ws = WebSocket(
    testnet=False,  # Встановіть True для тестування на Testnet
    channel_type="linear",  # Для USDT-M ф’ючерсів
    api_key=API_KEY,
    api_secret=API_SECRET
)

# Функція обробки WebSocket повідомлень
def handle_funding_rate_message(message):
    try:
        if 'data' in message and message['topic'] == f'publicTrade.{SYMBOL}':
            # Bybit не передає funding rate напряму через publicTrade, тому використовуємо REST API для отримання funding rate
            # Для прикладу, викликаємо REST API періодично
            pass
        else:
            logging.debug(f"Received message: {message}")
    except Exception as e:
        logging.error(f"Error processing message: {e}")

# Функція для отримання funding rate через REST API
def get_funding_rate():
    from pybit.unified_trading import HTTP
    session = HTTP(
        testnet=False,
        api_key=API_KEY,
        api_secret=API_SECRET
    )
    try:
        response = session.get_funding_rate(symbol=SYMBOL)
        if response['retCode'] == 0:
            funding_rate = float(response['result']['list'][0]['fundingRate'])
            return funding_rate
        else:
            logging.error(f"Error fetching funding rate: {response['retMsg']}")
            return None
    except Exception as e:
        logging.error(f"Error in get_funding_rate: {e}")
        return None

# Торгова логіка
def trade_logic(funding_rate):
    try:
        if funding_rate is None:
            return

        logging.info(f"Funding Rate for {SYMBOL}: {funding_rate*100:.4f}%")

        from pybit.unified_trading import HTTP
        session = HTTP(
            testnet=False,
            api_key=API_KEY,
            api_secret=API_SECRET
        )

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

# Асинхронна функція для періодичного отримання funding rate
async def main_loop():
    while True:
        funding_rate = get_funding_rate()
        trade_logic(funding_rate)
        await asyncio.sleep(300)  # Оновлення кожні 5 хвилин (funding rate оновлюється кожні 8 годин на Bybit)

# Запуск програми
if __name__ == "__main__":
    logging.info("Starting Bybit funding rate trading bot...")
    
    # Запуск WebSocket (для прикладу, хоча funding rate краще брати через REST)
    ws.public_trade_stream(callback=handle_funding_rate_message, symbol=SYMBOL)
    
    # Запуск асинхронного циклу для перевірки funding rate
    asyncio.run(main_loop())