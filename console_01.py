import os
import logging
import threading
import asyncio
from pybit.unified_trading import WebSocket, HTTP
from dotenv import load_dotenv
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Кастомний обробник логування для Tkinter
class TkinterLogHandler(logging.Handler):
    def __init__(self, text_widget, root):
        super().__init__()
        self.text_widget = text_widget
        self.root = root

    def emit(self, record):
        msg = self.format(record)
        # Виконуємо оновлення GUI в основному потоці через root.after
        self.root.after_idle(self._update_text_widget, msg)

    def _update_text_widget(self, msg):
        try:
            self.text_widget.config(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.config(state='disabled')
        except tk.TclError:
            pass  # Ігноруємо помилки, якщо GUI вже закрито

# Завантаження API ключів
load_dotenv()
API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')
SYMBOL = 'BTCUSDT'

if not API_KEY or not API_SECRET:
    logging.error("API_KEY or API_SECRET is missing in .env file")
    exit(1)

# Ініціалізація HTTP та WebSocket клієнтів
session = HTTP(testnet=True, api_key=API_KEY, api_secret=API_SECRET)
ws = WebSocket(testnet=True, channel_type="linear")

# Tkinter GUI
class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bybit Funding Rate Bot")
        self.root.geometry("600x400")
        self.running = True
        self.shutdown_event = asyncio.Event()

        # Поля для відображення даних
        self.funding_rate_var = tk.StringVar(value="Funding Rate: N/A")
        self.last_price_var = tk.StringVar(value="Last Price: N/A")
        self.balance_var = tk.StringVar(value="Balance: N/A")

        # Макет GUI
        tk.Label(root, textvariable=self.funding_rate_var).pack(pady=5)
        tk.Label(root, textvariable=self.last_price_var).pack(pady=5)
        tk.Label(root, textvariable=self.balance_var).pack(pady=5)

        # Лог-вікно
        self.log_text = scrolledtext.ScrolledText(root, height=15, width=70, state='disabled')
        self.log_text.pack(pady=10)

        # Кнопка зупинки
        tk.Button(root, text="Stop Bot", command=self.stop_bot).pack(pady=5)

        # Налаштування логування в GUI
        handler = TkinterLogHandler(self.log_text, self.root)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)

        # Запуск торгової логіки в окремому потоці
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.thread.start()

        # Періодичне оновлення GUI
        self.update_gui()

    def run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(main(self))
        except asyncio.CancelledError:
            pass  # Очікувана помилка при скасуванні
        except Exception as e:
            self.root.after_idle(lambda: logging.error(f"Error in async loop: {e}"))
        finally:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()

    def update_gui(self):
        if self.running:
            self.root.after(1000, self.update_gui)

    def stop_bot(self):
        self.running = False
        logging.info("Initiating bot shutdown...")
        # Сигналізуємо main зупинитися
        self.loop.call_soon_threadsafe(self.shutdown_event.set)
        # Скасовуємо всі задачі в event loop
        tasks = [task for task in asyncio.all_tasks(self.loop) if task is not asyncio.current_task(self.loop)]
        for task in tasks:
            task.cancel()
        # Зупиняємо WebSocket
        self.loop.call_soon_threadsafe(lambda: ws.exit())
        # Закриваємо GUI після завершення всіх задач
        self.root.after(100, self.root.quit)

# Обробка WebSocket повідомлень
def handle_funding_rate_message(message, gui):
    try:
        if 'topic' in message and message['topic'] == f'ticker.{SYMBOL}':
            funding_rate = float(message['data']['fundingRate'])
            gui.root.after_idle(lambda: logging.info(f"Funding Rate via WebSocket for {SYMBOL}: {funding_rate*100:.4f}%"))
            gui.root.after_idle(lambda: gui.funding_rate_var.set(f"Funding Rate: {funding_rate*100:.4f}%"))
            trade_logic(funding_rate, gui)
        else:
            gui.root.after_idle(lambda: logging.debug(f"Received WebSocket message: {message}"))
    except Exception as e:
        gui.root.after_idle(lambda: logging.error(f"Error processing WebSocket message: {e}"))

# Отримання funding rate через REST API
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

# Перевірка API дозволів
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
def trade_logic(funding_rate, gui):
    try:
        if funding_rate is None:
            return

        gui.root.after_idle(lambda: logging.info(f"Funding Rate for {SYMBOL}: {funding_rate*100:.4f}%"))

        ticker = session.get_tickers(category="linear", symbol=SYMBOL)
        if ticker['retCode'] != 0:
            gui.root.after_idle(lambda: logging.error(f"Error fetching ticker: {ticker['retMsg']}"))
            return
        last_price = float(ticker['result']['list'][0]['lastPrice'])
        gui.root.after_idle(lambda: gui.last_price_var.set(f"Last Price: {last_price:.2f} USDT"))

        balance = session.get_wallet_balance(accountType="UNIFIED")
        if balance['retCode'] == 0:
            available_balance = float(balance['result']['list'][0]['totalEquity'])
            gui.root.after_idle(lambda: gui.balance_var.set(f"Balance: {available_balance:.2f} USDT"))
            if available_balance < (last_price * 0.001):
                gui.root.after_idle(lambda: logging.error("Insufficient balance to open position"))
                return

        if funding_rate > 0.0005:
            gui.root.after_idle(lambda: logging.info(f"High funding rate detected: {funding_rate*100:.4f}%. Opening SHORT position."))
            order = session.place_order(
                category="linear",
                symbol=SYMBOL,
                side="Sell",
                orderType="Limit",
                qty=0.001,
                price=last_price * 0.99,
                timeInForce="GTC"
            )
            gui.root.after_idle(lambda: logging.info(f"Short position opened: {order}"))
        elif funding_rate < -0.0005:
            gui.root.after_idle(lambda: logging.info(f"Low funding rate detected: {funding_rate*100:.4f}%. Opening LONG position."))
            order = session.place_order(
                category="linear",
                symbol=SYMBOL,
                side="Buy",
                orderType="Limit",
                qty=0.001,
                price=last_price * 1.01,
                timeInForce="GTC"
            )
            gui.root.after_idle(lambda: logging.info(f"Long position opened: {order}"))
    except Exception as e:
        gui.root.after_idle(lambda: logging.error(f"Error in trade_logic: {e}"))

# Асинхронна функція
async def main(gui):
    if not check_api_permissions():
        gui.root.after_idle(lambda: logging.error("Stopping bot due to invalid API key"))
        return

    try:
        ws.ticker_stream(callback=lambda msg: handle_funding_rate_message(msg, gui), symbol=SYMBOL)
        gui.root.after_idle(lambda: logging.info(f"Subscribed to WebSocket ticker stream for {SYMBOL}"))
    except Exception as e:
        gui.root.after_idle(lambda: logging.error(f"Error subscribing to WebSocket: {e}"))

    while gui.running and not gui.shutdown_event.is_set():
        funding_rate = get_funding_rate()
        trade_logic(funding_rate, gui)
        try:
            await asyncio.wait_for(gui.shutdown_event.wait(), timeout=28800)  # 8 годин
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            gui.root.after_idle(lambda: logging.info("Main coroutine cancelled"))
            break

# Запуск програми
if __name__ == "__main__":
    logging.info("Starting Bybit funding rate trading bot...")
    root = tk.Tk()
    app = TradingBotGUI(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        ws.exit()
        logging.info("WebSocket connection closed")