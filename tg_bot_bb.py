import asyncio
import aiomysql
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pybit.unified_trading import HTTP
from datetime import datetime, timedelta, timezone
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ініціалізація бота
BOT_TOKEN = "YOUR_BOT_TOKEN"  # Замініть на ваш токен від @BotFather
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Налаштування MySQL
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "your_mysql_user",  # Замініть на вашого користувача MySQL
    "password": "your_mysql_password",  # Замініть на ваш пароль MySQL
    "db": "bybit_funding"
}

# Список доступних монет
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT"]

# Клас для управління даними користувача та торгівлею
class UserFundingBot:
    def __init__(self, user_id):
        self.user_id = user_id
        self.api_key = None
        self.api_secret = None
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
                    self.selected_symbol = row[3]
                    self.funding_interval_hours = row[4]
                    self.trade_duration_ms = row[5]
                    self.take_profit_percent = row[6]
                    self.entry_time_seconds = row[7]
                    self.leverage = row[8]
                    self.qty = row[9]
                    self.enable_funding_trade = bool(row[10])
                    self.enable_post_funding_trade = bool(row[11])
                    if self.api_key and self.api_secret:
                        self.session = HTTP(
                            testnet=False,
                            api_key=self.api_key,
                            api_secret=self.api_secret
                        )
                return row is not None

    async def save_user_data(self):
        async with aiomysql.connect(**DB_CONFIG) as db:
            async with db.cursor() as cursor:
                await cursor.execute('''
                    INSERT INTO users (
                        user_id, api_key, api_secret, selected_symbol, funding_interval_hours,
                        trade_duration_ms, take_profit_percent, entry_time_seconds, leverage,
                        qty, enable_funding_trade, enable_post_funding_trade
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        api_key = %s, api_secret = %s, selected_symbol = %s, funding_interval_hours = %s,
                        trade_duration_ms = %s, take_profit_percent = %s, entry_time_seconds = %s,
                        leverage = %s, qty = %s, enable_funding_trade = %s, enable_post_funding_trade = %s
                ''', (
                    self.user_id, self.api_key, self.api_secret, self.selected_symbol, self.funding_interval_hours,
                    self.trade_duration_ms, self.take_profit_percent, self.entry_time_seconds, self.leverage,
                    self.qty, self.enable_funding_trade, self.enable_post_funding_trade,
                    self.api_key, self.api_secret, self.selected_symbol, self.funding_interval_hours,
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

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_bots[user_id] = UserFundingBot(user_id)
    if not await user_bots[user_id].load_user_data():
        await user_bots[user_id].save_user_data()
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
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Використовуйте: /setkeys <api_key> <api_secret>")
        return
    user_bots[user_id].api_key = args[1]
    user_bots[user_id].api_secret = args[2]
    await user_bots[user_id].save_user_data()
    await user_bots[user_id].load_user_data()
    await message.reply("API ключі збережено!", reply_markup=get_main_menu())

# Команда /settings
@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_bots:
        await message.reply("Спочатку виконайте /start")
        return
    bot = user_bots[user_id]
    args = message.text.split()
    if len(args) == 1:
        await message.reply(
            f"Поточні налаштування:\n"
            f"Монета: {bot.selected_symbol}\n"
            f"Інтервал фандингу: {bot.funding_interval_hours} годин\n"
            f"Час угоди: {bot.trade_duration_ms} мс\n"
            f"Тейк-профіт: {bot.take_profit_percent}%\n"
            f"Час входження: {bot.entry_time_seconds} секунд\n"
            f"Плече: {bot.leverage}x\n"
            f"Кількість: {bot.qty}\n"
            f"Фандингова угода: {'увімкнена' if bot.enable_funding_trade else 'вимкнена'}\n"
            f"Угода після фандингу: {'увімкнена' if bot.enable_post_funding_trade else 'вимкнена'}\n"
            "Щоб змінити, використовуйте: /settings <symbol> <funding_interval> <trade_duration> <take_profit> <entry_time> <leverage> <qty>",
            reply_markup=get_main_menu()
        )
        return
    if len(args) != 8:
        await message.reply("Використовуйте: /settings <symbol> <funding_interval> <trade_duration> <take_profit> <entry_time> <leverage> <qty>")
        return
    try:
        bot.selected_symbol = args[1].upper()
        bot.funding_interval_hours = float(args[2])
        bot.trade_duration_ms = int(args[3])
        bot.take_profit_percent = float(args[4])
        bot.entry_time_seconds = float(args[5])
        bot.leverage = int(args[6])
        bot.qty = float(args[7])
        await bot.save_user_data()
        await bot.get_funding_data()
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
    bot = user_bots[user_id]
    if not bot.funding_data:
        await bot.get_funding_data()
    if bot.funding_data:
        funding_rate = bot.funding_data["funding_rate"]
        funding_time = bot.funding_data["funding_time"]
        _, time_str = bot.get_next_funding_time(funding_time)
        price = await bot.get_current_price()
        price_str = f"${price:.2f}" if price else "N/A"
        await message.reply(
            f"Монета: {bot.selected_symbol}\n"
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
        await callback.message.reply("Спочатку виконайте /start")
        return
    bot = user_bots[user_id]
    data = callback.data

    if data == "status":
        await cmd_status(callback.message)
    elif data == "settings":
        await cmd_settings(callback.message)
    elif data == "enable_trade":
        bot.enable_funding_trade = True
        await bot.save_user_data()
        await callback.message.reply("Фандингова угода увімкнена", reply_markup=get_main_menu())
    elif data == " disable_trade":
        bot.enable_funding_trade = False
        await bot.save_user_data()
        await callback.message.reply("Фандингова угода вимкнена", reply_markup=get_main_menu())
    elif data == "enable_post_trade":
        bot.enable_post_funding_trade = True
        await bot.save_user_data()
        await callback.message.reply("Угода після фандингу увімкнена", reply_markup=get_main_menu())
    elif data == "disable_post_trade":
        bot.enable_post_funding_trade = False
        await bot.save_user_data()
        await callback.message.reply("Угода після фандингу вимкнена", reply_markup=get_main_menu())
    elif data == "select_coin":
        await callback.message.reply("Виберіть монету:", reply_markup=get_coin_menu())
    elif data.startswith("coin_"):
        coin = data.split("_")[1]
        bot.selected_symbol = coin
        await bot.save_user_data()
        await bot.get_funding_data()
        await callback.message.reply(f"Вибрано монету: {coin}", reply_markup=get_main_menu())
    await callback.answer()

# Фонова задача для перевірки часу фандингу
async def check_funding_loop():
    while True:
        for user_id, bot in user_bots.items():
            await bot.check_funding_time()
            if bot.funding_data and bot.enable_funding_trade:
                funding_rate = bot.funding_data["funding_rate"]
                time_to_funding, _ = bot.get_next_funding_time(bot.funding_data["funding_time"])
                if bot.entry_time_seconds - 1.0 <= time_to_funding <= bot.entry_time_seconds:
                    await bot.send_message(f"Відкрито угоду для {bot.selected_symbol} (ставка: {funding_rate:.4f}%)")
        await asyncio.sleep(1)

# Надсилання сповіщень користувачу
async def send_message(self, message_text):
    try:
        await bot.send_message(self.user_id, message_text, reply_markup=get_main_menu())
    except Exception as e:
        logger.error(f"Помилка надсилання повідомлення користувачу {self.user_id}: {e}")

UserFundingBot.send_message = send_message

async def main():
    # Ініціалізація пулу підключень до MySQL
    async with aiomysql.create_pool(**DB_CONFIG) as pool:
        async with pool.acquire() as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT 1")  # Перевірка підключення
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())