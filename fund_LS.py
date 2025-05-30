# import os
# from dotenv import load_dotenv
# from pybit.unified_trading import HTTP
# import time
# from datetime import datetime

# # Завантаження змінних середовища з .env файлу
# load_dotenv()
# api_key = os.getenv("BYBIT_API_KEY")
# api_secret = os.getenv("BYBIT_API_SECRET")

# # Ініціалізація клієнта Bybit
# client = HTTP(
#     testnet=False,  # Використовуємо testnet, змініть на False для основної мережі
#     api_key=api_key,
#     api_secret=api_secret
# )

# # Налаштування
# SYMBOL = "BTCUSDT"  # Торгова пара
# LEVERAGE = 10  # Кредитне плече
# AMOUNT = 0.001  # Кількість монет для угоди
# PRICE_MOVEMENT = 0.01  # 1% руху ціни
# CHECK_INTERVAL = 60  # Інтервал перевірки фандингу (секунди)

# def get_funding_rate():
#     """Отримання поточного фандинг рейту"""
#     try:
#         response = client.get_funding_rate(symbol=SYMBOL)
#         funding_rate = float(response['result']['list'][0]['fundingRate'])
#         return funding_rate
#     except Exception as e:
#         print(f"Помилка отримання фандинг рейту: {e}")
#         return None

# def place_order(side, price):
#     """Відкриття позиції"""
#     try:
#         client.place_order(
#             category="linear",
#             symbol=SYMBOL,
#             side=side,  # "Buy" для лонг, "Sell" для шорт
#             order_type="Market",
#             qty=AMOUNT,
#             leverage=LEVERAGE
#         )
#         print(f"{datetime.now()}: Відкрито {side} позицію за ціною {price}")
#         return True
#     except Exception as e:
#         print(f"Помилка відкриття позиції: {e}")
#         return False

# def close_position(side, entry_price):
#     """Закриття позиції після руху на 1%"""
#     target_price = entry_price * (1 + PRICE_MOVEMENT) if side == "Buy" else entry_price * (1 - PRICE_MOVEMENT)
#     print(f"Цільова ціна для закриття: {target_price}")

#     while True:
#         try:
#             current_price = float(client.get_tickers(category="linear", symbol=SYMBOL)['result']['list'][0]['lastPrice'])
#             print(f"Поточна ціна: {current_price}")

#             # Перевірка умови закриття
#             if (side == "Buy" and current_price >= target_price) or (side == "Sell" and current_price <= target_price):
#                 client.place_order(
#                     category="linear",
#                     symbol=SYMBOL,
#                     side="Sell" if side == "Buy" else "Buy",
#                     order_type="Market",
#                     qty=AMOUNT,
#                     reduce_only=True
#                 )
#                 print(f"{datetime.now()}: Позицію закрито за ціною {current_price}")
#                 break
#             time.sleep(5)  # Перевірка кожні 5 секунд
#         except Exception as e:
#             print(f"Помилка при закритті позиції: {e}")
#             time.sleep(5)

# def main():
#     client.set_leverage(
#         category="linear",
#         symbol=SYMBOL,
#         buy_leverage=LEVERAGE,
#         sell_leverage=LEVERAGE
#     )

#     while True:
#         funding_rate = get_funding_rate()
#         if funding_rate is None:
#             time.sleep(CHECK_INTERVAL)
#             continue

#         print(f"{datetime.now()}: Фандинг рейт: {funding_rate*100:.4f}%")
        
#         try:
#             current_price = float(client.get_tickers(category="linear", symbol=SYMBOL)['result']['list'][0]['lastPrice'])
            
#             # Відкриття позиції залежно від фандинг рейту
#             if funding_rate > 0:
#                 # Позитивний фандинг -> відкриваємо лонг
#                 if place_order("Buy", current_price):
#                     close_position("Buy", current_price)
#             elif funding_rate < 0:
#                 # Негативний фандинг -> відкриваємо шорт
#                 if place_order("Sell", current_price):
#                     close_position("Sell", current_price)
            
#             # Очікування до наступної перевірки
#             time.sleep(CHECK_INTERVAL)
        
#         except Exception as e:
#             print(f"Помилка: {e}")
#             time.sleep(CHECK_INTERVAL)

# if __name__ == "__main__":
#     try:
#         main()
#     except KeyboardInterrupt:
#         print("Програму зупинено користувачем")
#         client.close()