import os
import dotenv
import asyncio
import aiomysql
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from pybit.unified_trading import HTTP
from datetime import datetime, timedelta, timezone
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ініціалізація бота
BOT_TOKEN = os.getenv('YOUR_BOT_TOKEN')  # Замініть на ваш токен від @BotFather
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Налаштування MySQL
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",  # Замініть на вашого користувача MySQL
    "password": "1212",  # Замініть на ваш пароль MySQL
    "db": "bybit_funding"
}

# Список доступних монет
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT"]

# Клавіатура для запиту номера телефону
phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Поділитися номером телефону", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клас для управління даними користувача та торгівлею
class UserFundingBot:
    def __init__(self, user_id):
        self.user_id = user_id
        self.api_key = None
        self.api_secret = None
        self.phone_number = None
        self.session = None
        self.funding_data = None
        self.open_funding_order_id = None
        self.open_post_funding_order_id = None
        self.selected_symbol = "BTCUSDT"
        self.funding_interval_hours = 8.0
        self.trade_duration_ms = 2000
        self.take_profit_percent = 2.0
        self.entry_time_seconds = 1.0
        self.leverage = 1
        self.qty = 1.0
        self.enable_funding_trade = True
        self.enable_post_funding_trade = True

    async def load_user_data(self):
        async with aiomysql.connect(**DB_CONFIG) as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT * FROM users WHERE user_id = %s', (self.user_id,))
                row = await cursor.fetchone()
                if row:
                    self.api_key = row[1]
                    self.api_secret = row[2]
                    self.phone_number = row[3]
                    self.selected_symbol = row[4]
                    self.funding_interval_hours = row[5]
                    self.trade_duration_ms = row[6]
                    self.take_profit_percent = row[7]
                    self.entry_time_seconds = row[8]
                    self.leverage = row[9]
                    self.qty = row[10]
                    self.enable_funding_trade = bool(row[11])
                    self.enable_post_funding_trade = bool(row[12])
                    logger.info(f"Завантажено дані для user_id {self.user_id}: api_key={self.api_key}, api_secret={'***' if self.api_secret else None}")
                    if self.api_key and self.api_secret:
                        try:
                            self.session = HTTP(
                                testnet=False,
                                api_key=self.api_key,
                                api_secret=self.api_secret
                            )
                            logger.info(f"Сесію Bybit для user_id {self.user_id} ініціалізовано")
                        except Exception as e:
                            logger.error(f"Помилка ініціалізації сесії Bybit для user_id {self.user_id}: {e}")
                            self.session = None
                    else:
                        logger.warning(f"API-ключі відсутні для user_id {self.user_id}")
                else:
                    logger.info(f"Дані для user_id {self.user_id} не знайдено в базі")
                return row is not None

    async def save_user_data(self):
        async with aiomysql.connect(**DB_CONFIG) as db:
            async with db.cursor() as cursor:
                await cursor.execute('''
                    INSERT INTO users (
                        user_id, api_key, api_secret, phone_number, selected_symbol, funding_interval_hours,
                        trade_duration_ms, take_profit_percent, entry_time_seconds, leverage,
                        qty, enable_funding_trade, enable_post_funding_trade
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        api_key = %s, api_secret = %s, phone_number = %s, selected_symbol = %s, funding_interval_hours = %s,
                        trade_duration_ms = %s, take_profit_percent = %s, entry_time_seconds = %s,
                        leverage = %s, qty = %s, enable_funding_trade = %s, enable_post_funding_trade = %s
                ''', (
                    self.user_id, self.api_key, self.api_secret, self.phone_number, self.selected_symbol, self.funding_interval_hours,
                    self.trade_duration_ms, self.take_profit_percent, self.entry_time_seconds, self.leverage,
                    self.qty, self.enable_funding_trade, self.enable_post_funding_trade,
                    self.api_key, self.api_secret, self.phone_number, self.selected_symbol, self.funding_interval_hours,
                    self.trade_duration_ms, self.take_profit_percent, self.entry_time_seconds, self.leverage,
                    self.qty, self.enable_funding_trade, self.enable_post_funding_trade
                ))
                await db.commit()

    async def log_trade(self, symbol, side, qty, take_profit, status, result="Pending"):
        async with aiomysql.connect(**DB_CONFIG) as db:
            async with db.cursor() as cursor:
                await cursor.execute('''
                    INSERT INTO trades (user_id, symbol, side, qty, take_profit, order_time, status, result)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (self.user_id, symbol, side, qty, take_profit, datetime.now(timezone.utc), status, result))
                await db.commit()

    async def get_funding_data(self):
        if not self.session:
            return None
        try:
            logger.info(f"Отримання ставки фандингу для {self.selected_symbol}...")
            response = self.session.get_funding_rate_history(
                category="linear",
                symbol=self.selected_symbol,
                limit=1
            )
            if response["retCode"] == 0 and response["result"]["list"]:
                funding_data = response["result"]["list"][0]
                funding_rate = float(funding_data["fundingRate"]) * 100
                funding_time = int(funding_data["fundingRateTimestamp"]) / 1000
                self.funding_data = {
                    "symbol": self.selected_symbol,
                    "funding_rate": funding_rate,
                    "funding_time": funding_time
                }
                logger.info(f"Оброблено {self.selected_symbol}: {funding_rate:.4f}%")
                return self.funding_data
            else:
                logger.error(f"Помилка отримання ставки фандингу для {self.selected_symbol}: {response['retMsg']}")
                return None
        except Exception as e:
            logger.error(f"Помилка отримання ставки фандингу для {self.selected_symbol}: {e}")
            return None

    async def get_current_price(self):
        if not self.session:
            return None
        try:
            logger.info(f"Отримання поточної ціни для {self.selected_symbol}...")
            response = self.session.get_tickers(category="linear", symbol=self.selected_symbol)
            if response["retCode"] == 0 and response["result"]["list"]:
                price = float(response["result"]["list"][0]["lastPrice"])
                logger.info(f"Поточна ціна {self.selected_symbol}: {price}")
                return price
            else:
                logger.error(f"Помилка отримання ціни для {self.selected_symbol}: {response['retMsg']}")
                return None
        except Exception as e:
            logger.error(f"Помилка отримання ціни для {self.selected_symbol}: {e}")
            return None

    async def set_leverage(self):
        if not self.session:
            return False
        try:
            logger.info(f"Встановлення плеча {self.leverage}x для {self.selected_symbol}...")
            response = self.session.set_leverage(
                category="linear",
                symbol=self.selected_symbol,
                buyLeverage=str(self.leverage),
                sellLeverage=str(self.leverage)
            )
            if response["retCode"] == 0:
                logger.info(f"Плече успішно встановлено: {self.leverage}x")
                return True
            else:
                logger.error(f"Помилка встановлення плеча для {self.selected_symbol}: {response['retMsg']}")
                return False
        except Exception as e:
            logger.error(f"Помилка встановлення плеча для {self.selected_symbol}: {e}")
            return False

    async def place_order(self, side, qty, take_profit=None):
        if not self.session:
            return None
        try:
            if not await self.set_leverage():
                logger.error(f"Не вдалося встановити плече для {self.selected_symbol}, ордер не розміщено")
                return None
            logger.info(f"Розміщення ордера {side} для {self.selected_symbol} з кількістю {qty}...")
            params = {
                "category": "linear",
                "symbol": self.selected_symbol,
                "side": side,
                "orderType": "Market",
                "qty": str(qty),
                "timeInForce": "GTC"
            }
            if take_profit is not None:
                params["takeProfit"] = str(take_profit)
            response = self.session.place_order(**params)
            if response["retCode"] == 0:
                logger.info(f"Ордер успішно розміщено: {response['result']}")
                await self.log_trade(self.selected_symbol, side, qty, take_profit, "Opened")
                return response["result"]["orderId"]
            else:
                logger.error(f"Помилка розміщення ордера для {self.selected_symbol}: {response['retMsg']}")
                await self.log_trade(self.selected_symbol, side, qty, take_profit, "Failed", response["retMsg"])
                return None
        except Exception as e:
            logger.error(f"Помилка розміщення ордера для {self.selected_symbol}: {e}")
            await self.log_trade(self.selected_symbol, side, qty, take_profit, "Failed", str(e))
            return None

    async def close_position(self, side):
        if not self.session:
            return
        try:
            if not await self.set_leverage():
                logger.error(f"Не вдалося встановити плече для {self.selected_symbol}, закриття не виконано")
                return
            close_side = "Buy" if side == "Sell" else "Sell"
            logger.info(f"Закриття позиції {side} для {self.selected_symbol} через розміщення ордера {close_side}...")
            response = self.session.place_order(
                category="linear",
                symbol=self.selected_symbol,
                side=close_side,
                orderType="Market",
                qty=str(self.qty),
                timeInForce="GTC",
                reduceOnly=True
            )
            if response["retCode"] == 0:
                logger.info(f"Позицію успішно закрито: {response['result']}")
                await self.log_trade(self.selected_symbol, close_side, self.qty, None, "Closed", "Success")
                if self.enable_post_funding_trade:
                    await self.open_post_funding_position()
            else:
                logger.error(f"Помилка закриття позиції для {self.selected_symbol}: {response['retMsg']}")
                await self.log_trade(self.selected_symbol, close_side, self.qty, None, "Failed", response["retMsg"])
        except Exception as e:
            logger.error(f"Помилка закриття позиції для {self.selected_symbol}: {e}")
            await self.log_trade(self.selected_symbol, close_side, self.qty, None, "Failed", str(e))

    async def open_post_funding_position(self):
        if not self.funding_data:
            logger.error("Дані фандингу відсутні для відкриття позиції після фандингу")
            return
        funding_rate = self.funding_data["funding_rate"]
        side = "Sell" if funding_rate < 0 else "Buy"
        current_price = await self.get_current_price()
        if current_price is None:
            logger.error(f"Не вдалося отримати ціну для {self.selected_symbol}, пропускаємо відкриття позиції")
            return
        take_profit = current_price * (1 + self.take_profit_percent / 100) if side == "Buy" else current_price * (1 - self.take_profit_percent / 100)
        take_profit = round(take_profit, 2)
        self.open_post_funding_order_id = await self.place_order(side, self.qty, take_profit=take_profit)

    def get_next_funding_time(self, funding_time):
        funding_dt = datetime.fromtimestamp(funding_time, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        hours_since_last = (current_time - funding_dt).total_seconds() / 3600
        intervals_passed = int(hours_since_last / self.funding_interval_hours) + 1
        next_funding = funding_dt + timedelta(hours=intervals_passed * self.funding_interval_hours)
        time_diff = next_funding - current_time
        hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return time_diff.total_seconds(), f"{hours:02d}:{minutes:02d}:{seconds:02d}"

##
    async def check_funding_time(self):
        if not self.funding_data:
            logger.info("Дані фандингу відсутні")
            return
        symbol = self.funding_data["symbol"]
        funding_rate = self.funding_data["funding_rate"]
        funding_time = self.funding_data["funding_time"]
        time_to_funding, time_str = self.get_next_funding_time(funding_time)
        logger.info(f"Час до наступного фандингу для {symbol}: {time_str}")
        if self.enable_funding_trade:
            entry_window_start = self.entry_time_seconds - 1.0
            if entry_window_start <= time_to_funding <= self.entry_time_seconds and not self.open_funding_order_id:
                side = "Sell" if funding_rate > 0 else "Buy"
                self.open_funding_order_id = await self.place_order(side, self.qty)
                if self.open_funding_order_id:
                    asyncio.get_event_loop().call_later(
                        self.trade_duration_ms / 1000,
                        lambda: asyncio.create_task(self.close_position(side) or setattr(self, 'open_funding_order_id', None))
                    )
##
async def send_message(self, message_text, reply_markup=None):
    try:
        await bot.send_message(self.user_id, message_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Помилка надсилання повідомлення користувачу {self.user_id}: {e}")

# Додаємо метод send_message до класу
UserFundingBot.send_message = send_message

# Словник для зберігання екземплярів бота для кожного користувача
user_bots = {}

# Inline-кнопки для головного меню
def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статус", callback_data="status")],
        [InlineKeyboardButton(text="🔧 Налаштування", callback_data="settings")],
        [InlineKeyboardButton(text="💹 Фандингова угода: Увімкнути", callback_data="enable_trade"),
         InlineKeyboardButton(text="🚫 Вимкнути", callback_data="disable_trade")],
        [InlineKeyboardButton(text="📈 Угода після фандингу: Увімкнути", callback_data="enable_post_trade"),
         InlineKeyboardButton(text="🚫 Вимкнути", callback_data="disable_post_trade")],
        [InlineKeyboardButton(text="🪙 Вибрати монету", callback_data="select_coin")]
    ])
    return keyboard

# Inline-кнопки для вибору монети
def get_coin_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=coin, callback_data=f"coin_{coin}")] for coin in COINS
    ])
    return keyboard

# Перевірка наявності номера телефону
async def check_phone_number(bot_instance, message):
    if not bot_instance.phone_number:
        await message.reply("Будь ласка, поділіться номером телефону для продовження.", reply_markup=phone_keyboard)
        return False
    return True

##
async def check_api_keys(bot_instance, message):
    if not bot_instance.api_key or not bot_instance.api_secret or not bot_instance.session:
        await message.reply("Будь ласка, встановіть API-ключі за допомогою команди: /setkeys <api_key> <api_secret>", reply_markup=get_main_menu())
        return False
    return True
##
# Обробник контакту (номера телефону)
@dp.message(lambda message: message.contact)
async def process_contact(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_bots:
        user_bots[user_id] = UserFundingBot(user_id)
    bot_instance = user_bots[user_id]
    bot_instance.phone_number = message.contact.phone_number
    await bot_instance.save_user_data()
    await message.reply(
        f"Номер телефону {message.contact.phone_number} збережено!\n"
        "Тепер встановіть API ключі: /setkeys <api_key> <api_secret>",
        reply_markup=get_main_menu()
    )

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_bots[user_id] = UserFundingBot(user_id)
    await user_bots[user_id].load_user_data()
    if not user_bots[user_id].phone_number:
        await message.reply("Будь ласка, поділіться номером телефону для початку роботи.", reply_markup=phone_keyboard)
    else:
        await message.reply(
            "Вітаю! Це бот для моніторингу фандингу Bybit.\n"
            "Встановіть API ключі: /setkeys <api_key> <api_secret>\n"
            "Використовуйте меню нижче для керування:", reply_markup=get_main_menu()
        )

# Команда /setkeys
@dp.message(Command("setkeys"))
async def cmd_setkeys(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_bots:
        user_bots[user_id] = UserFundingBot(user_id)
    bot_instance = user_bots[user_id]
    if not await check_phone_number(bot_instance, message):
        return
    if bot_instance.api_key and bot_instance.api_secret and bot_instance.session:
        await message.reply("API-ключі вже встановлено! Використовуйте меню для керування.", reply_markup=get_main_menu())
        return
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Використовуйте: /setkeys <api_key> <api_secret>", reply_markup=get_main_menu())
        return
    bot_instance.api_key = args[1]
    bot_instance.api_secret = args[2]
    await bot_instance.save_user_data()
    await bot_instance.load_user_data()
    if bot_instance.session:
        await message.reply("API-ключі збережено та сесію ініціалізовано!", reply_markup=get_main_menu())
    else:
        await message.reply("Помилка ініціалізації API-ключів. Перевірте їх правильність.", reply_markup=get_main_menu())

# Команда /settings
@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_bots:
        await message.reply("Спочатку виконайте /start")
        return
    bot_instance = user_bots[user_id]
    if not await check_phone_number(bot_instance, message):
        return
    args = message.text.split()
    if len(args) == 1:
        await message.reply(
            f"Поточні налаштування:\n"
            f"Монета: {bot_instance.selected_symbol}\n"
            f"Інтервал фандингу: {bot_instance.funding_interval_hours} годин\n"
            f"Час угоди: {bot_instance.trade_duration_ms} мс\n"
            f"Тейк-профіт: {bot_instance.take_profit_percent}%\n"
            f"Час входження: {bot_instance.entry_time_seconds} секунд\n"
            f"Плече: {bot_instance.leverage}x\n"
            f"Кількість: {bot_instance.qty}\n"
            f"Фандингова угода: {'увімкнена' if bot_instance.enable_funding_trade else 'вимкнена'}\n"
            f"Угода після фандингу: {'увімкнена' if bot_instance.enable_post_funding_trade else 'вимкнена'}\n"
            "Щоб змінити, використовуйте: /settings <symbol> <funding_interval> <trade_duration> <take_profit> <entry_time> <leverage> <qty>",
            reply_markup=get_main_menu()
        )
        return
    if len(args) != 8:
        await message.reply("Використовуйте: /settings <symbol> <funding_interval> <trade_duration> <take_profit> <entry_time> <leverage> <qty>", reply_markup=get_main_menu())
        return
    try:
        bot_instance.selected_symbol = args[1].upper()
        bot_instance.funding_interval_hours = float(args[2])
        bot_instance.trade_duration_ms = int(args[3])
        bot_instance.take_profit_percent = float(args[4])
        bot_instance.entry_time_seconds = float(args[5])
        bot_instance.leverage = int(args[6])
        bot_instance.qty = float(args[7])
        await bot_instance.save_user_data()
        await bot_instance.get_funding_data()
        await message.reply("Налаштування оновлено!", reply_markup=get_main_menu())
    except ValueError:
        await message.reply("Невірний формат параметрів!", reply_markup=get_main_menu())

# Команда /status
@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_bots:
        await message.reply("Спочатку виконайте /start")
        return
    bot_instance = user_bots[user_id]
    if not await check_phone_number(bot_instance, message):
        return
    if not await check_api_keys(bot_instance, message):
        return
    if not bot_instance.funding_data:
        await bot_instance.get_funding_data()
    if bot_instance.funding_data:
        funding_rate = bot_instance.funding_data["funding_rate"]
        funding_time = bot_instance.funding_data["funding_time"]
        _, time_str = bot_instance.get_next_funding_time(funding_time)
        price = await bot_instance.get_current_price()
        price_str = f"${price:.2f}" if price else "N/A"
        await message.reply(
            f"Монета: {bot_instance.selected_symbol}\n"
            f"Ставка фандингу: {funding_rate:.4f}%\n"
            f"Час до наступного фандингу: {time_str}\n"
            f"Поточна ціна: {price_str}",
            reply_markup=get_main_menu()
        )
    else:
        await message.reply("Не вдалося отримати дані фандингу", reply_markup=get_main_menu())

# Обробка inline-кнопок
@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_bots:
        logger.info(f"Користувач {user_id} відсутній у user_bots, ініціалізуємо...")
        user_bots[user_id] = UserFundingBot(user_id)
        await user_bots[user_id].load_user_data()
    bot_instance = user_bots[user_id]
    logger.info(f"Обробка callback для user_id {user_id}, phone_number={bot_instance.phone_number}")
    if not bot_instance.phone_number:
        await callback.message.reply("Будь ласка, поділіться номером телефону для продовження.", reply_markup=phone_keyboard)
        await callback.answer()
        return
    if not await check_api_keys(bot_instance, callback.message):
        await callback.answer()
        return
    data = callback.data

    if data == "status":
        await cmd_status(callback.message)
    elif data == "settings":
        await cmd_settings(callback.message)
    elif data == "enable_trade":
        bot_instance.enable_funding_trade = True
        await bot_instance.save_user_data()
        await callback.message.reply("Фандингова угода увімкнена", reply_markup=get_main_menu())
    elif data == "disable_trade":
        bot_instance.enable_funding_trade = False
        await bot_instance.save_user_data()
        await callback.message.reply("Фандингова угода вимкнена", reply_markup=get_main_menu())
    elif data == "enable_post_trade":
        bot_instance.enable_post_funding_trade = True
        await bot_instance.save_user_data()
        await callback.message.reply("Угода після фандингу увімкнена", reply_markup=get_main_menu())
    elif data == "disable_post_trade":
        bot_instance.enable_post_funding_trade = False
        await bot_instance.save_user_data()
        await callback.message.reply("Угода після фандингу вимкнена", reply_markup=get_main_menu())
    elif data == "select_coin":
        await callback.message.reply("Виберіть монету:", reply_markup=get_coin_menu())
    elif data.startswith("coin_"):
        coin = data.split("_")[1]
        bot_instance.selected_symbol = coin
        await bot_instance.save_user_data()
        await bot_instance.get_funding_data()
        await callback.message.reply(f"Вибрано монету: {coin}", reply_markup=get_main_menu())
    await callback.answer()

# Фонова задача для перевірки часу фандингу
async def check_funding_loop():
    while True:
        for user_id, bot_instance in user_bots.items():
            if bot_instance.phone_number:  # Перевірка наявності номера телефону
                await bot_instance.check_funding_time()
                if bot_instance.funding_data and bot_instance.enable_funding_trade:
                    funding_rate = bot_instance.funding_data["funding_rate"]
                    time_to_funding, _ = bot_instance.get_next_funding_time(bot_instance.funding_data["funding_time"])
                    if bot_instance.entry_time_seconds - 1.0 <= time_to_funding <= bot_instance.entry_time_seconds:
                        await bot_instance.send_message(
                            f"Відкрито угоду для {bot_instance.selected_symbol} (ставка: {funding_rate:.4f}%)",
                            reply_markup=get_main_menu()
                        )
        await asyncio.sleep(1)

async def main():
    async with aiomysql.create_pool(**DB_CONFIG) as pool:
        async with pool.acquire() as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT 1")  # Перевірка підключення
        asyncio.create_task(check_funding_loop())
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())