-- Створення бази даних
CREATE DATABASE IF NOT EXISTS bybit_funding;
USE bybit_funding;

-- Таблиця для зберігання даних користувачів
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    api_key VARCHAR(255),
    api_secret VARCHAR(255),
    phone_number VARCHAR(50), -- Додано поле для номера телефону
    selected_symbol VARCHAR(50) DEFAULT 'BTCUSDT',
    funding_interval_hours DOUBLE DEFAULT 8.0,
    trade_duration_ms INT DEFAULT 2000,
    take_profit_percent DOUBLE DEFAULT 2.0,
    entry_time_seconds DOUBLE DEFAULT 1.0,
    leverage INT DEFAULT 1,
    qty DOUBLE DEFAULT 1.0,
    enable_funding_trade BOOLEAN DEFAULT TRUE,
    enable_post_funding_trade BOOLEAN DEFAULT TRUE
);

-- Таблиця для логування угод
CREATE TABLE IF NOT EXISTS trades (
    trade_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    symbol VARCHAR(50),
    side VARCHAR(10),
    qty DOUBLE,
    take_profit DOUBLE,
    order_time DATETIME,
    status VARCHAR(50),
    result VARCHAR(255),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Індекс для швидшого пошуку за user_id у таблиці trades
CREATE INDEX idx_user_id ON trades(user_id);