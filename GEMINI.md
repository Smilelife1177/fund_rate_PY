# Project: Fund_rate_py

A specialized Python tool for funding rate arbitrage on Bybit and Binance exchanges. It provides a real-time GUI for monitoring funding rates, scanning for opportunities, and executing trades.

## Project Overview
- **Purpose**: Automate or assist in funding rate arbitrage between USDT-Margined perpetual contracts.
- **Exchanges**: Bybit and Binance (supports both Mainnet and Testnet).
- **Core Technologies**:
  - **Language**: Python 3.7+
  - **GUI Framework**: PyQt6
  - **Exchange APIs**: `pybit` (Bybit V5), `python-binance`.
  - **Data Handling**: `python-dotenv` for secrets, CSV for trade statistics, JSON for settings.
- **Architecture**:
  - `main.py`: Entry point for the PyQt6 application.
  - `gui.py`: Centralized UI logic and tab management.
  - `logic.py`: Encapsulated exchange interaction logic (price fetching, order placement, balance checks).
  - `auto_scanner.py`: Background scanning of funding rates across all available USDT pairs.
  - `settings_manager.py`: Persistence of application state and user preferences.
  - `stats_manager.py`: Management of trade history and performance metrics in `trade_stats.csv`.
  - `translations.py`: Multi-language support (English, Ukrainian).

## Building and Running
1.  **Environment Setup**:
    - Install Python 3.7+.
    - Create a virtual environment: `python -m venv venv`.
    - Activate it: `source venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\activate` (Windows).
    - Install dependencies: `pip install -r requirements.txt`.
2.  **API Configuration**:
    - Run the setup script to create a template: `bash scripts/env_api.sh`.
    - Fill in your API keys in the generated `.env` file.
3.  **Run Application**:
    - Execute `python main.py`.

## Development Conventions
- **Secrets Management**: Always use the `.env` file for API keys. Never hardcode credentials.
- **Modularity**: Keep exchange-specific logic in `logic.py` to ensure `gui.py` remains focused on presentation.
- **Error Handling**: Use the built-in printing and GUI message boxes for user-facing errors.
- **Translations**: UI strings should be sourced from `translations.py` to maintain multi-language support.
- **State Persistence**: User settings should be managed via `settings_manager.py` and stored in `scripts/settings.json`.

## Key Files
- `main.py`: Main application loop and window initialization.
- `gui.py`: The largest file (1600+ lines), containing all interactive UI components.
- `logic.py`: API wrappers for Bybit and Binance.
- `auto_scanner.py`: Logic for periodic background scans of funding rates.
- `trade_stats.csv`: Local database of closed trades.
- `audio/`: Contains WAV files for trade notifications (`trade_open.wav`, `trade_closed.wav`, etc.).
