import os
import logging
import asyncio
from datetime import datetime, timezone
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Завантаження API ключів із .env файлу
load_dotenv()
API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')

# Символ для торгівлі
SYMBOL = 'BTCUSDT'

# Час виплат funding rate (UTC)
FUNDING_TIMES = [
    (0, 0),  # 00:00 UTC
    (8, 0),  # 08:00 UTC
    (16, 0)  # 16:00 UTC
]

# Ініціалізація HTTP клієнта Bybit
session = HTTP(
    testnet=True,  # Змініть на False для реальної торгівлі
    api_key=API_KEY,
    api_secret=API_SECRET
)

# Функція для отримання funding rate
def get_funding_rate():
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

        # Якщо funding rate > 0.05%, відкриваємо коротку позицію
        if funding_rate > 0.0005:  # 0.05%
            logging.info(f"High funding rate detected: {funding_rate*100:.4f}%. Opening SHORT position.")
            try:
                order = session.place_order(
                    category="linear",
                    symbol=SYMBOL,
                    side="Sell",
                    orderType="Market",
                    qty=0.001,  # Розмір позиції (налаштуйте)
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

# Функція для перевірки, чи настав час для торгівлі
def is_funding_time():
    now = datetime.now(timezone.utc)
    current_hour, current_minute, current_second = now.hour, now.minute, now.second
    
    # Перевіряємо, чи поточний час в межах ±30 секунд до виплати
    for funding_hour, funding_minute in FUNDING_TIMES:
        if current_hour == funding_hour and current_minute == funding_minute and 0 <= current_second <= 30:
            return True
    return False

# Асинхронна функція для періодичної перевірки
async def main_loop():
    while True:
        if is_funding_time():
            logging.info("Funding time detected! Checking funding rate...")
            funding_rate = get_funding_rate()
            trade_logic(funding_rate)
        else:
            now = datetime.now(timezone.utc)
            logging.debug(f"Current time: {now.strftime('%H:%M:%S UTC')}. Waiting for funding time...")
        
        # Перевірка кожні 10 секунд, щоб не пропустити вікно
        await asyncio.sleep(10)

# Запуск програми
if __name__ == "__main__":
    logging.info("Starting Bybit funding rate trading bot...")
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")