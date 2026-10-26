# Fund Rate PY

![Alt text](images/example.jpg)

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)[![License: GPL v3](<https://img.shields.io/badge/License-GPL%20v3-blue.svg>)](https://www.gnu.org/licenses/gpl-3.0)[![Issues](https://img.shields.io/github/issues/Smilelife1177/fund_rate_PY.svg)](https://github.com/Smilelife1177/fund_rate_PY/issues)[![Last Commit](https://img.shields.io/github/last-commit/Smilelife1177/fund_rate_PY/main.svg)](https://github.com/username/repo/commits/main)

Fund Rate PY is a PyQt6 desktop application for monitoring Bybit USDT perpetual funding rates and managing funding-based trades. It supports Bybit mainnet and testnet. Binance is not currently supported.

## Features

- Monitor funding rate, next funding time, price, account balance, and connection latency.
- Open a market position near the funding event and place a reduce-only profit limit order.
- Configure symbol, order quantity, leverage, entry window, profit target, and trade direction per tab.
- Scan Bybit USDT perpetual contracts for negative funding rates above a configurable threshold. The scanner can show candidates manually or run in automatic mode; automatic scans can add tabs for upcoming opportunities.
- Block funding trades globally with the control at the top of the window. This blocks automatic funding entries; it does not prevent manual position-closing actions.
- Import closed Bybit trades into the Statistics tab and keep trade records in SQLite.
- Optionally collect funding-event market data in the Observation tab and inspect it with the built-in analysis view. The collector writes to SQLite.
- Use the interface in English or Ukrainian.

## Requirements

- Windows, Linux, or macOS
- Python 3.9 or newer
- Bybit API keys for the account and network mode you plan to use

## Installation

Clone the repository and enter its directory:

```powershell
git clone https://github.com/Smilelife1177/fund_rate_PY.git
cd fund_rate_PY
```

Create and activate a virtual environment, then install the pinned dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Linux or macOS, activate the environment with:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## API Configuration

Create a local `.env` template from Bash:

```bash
bash ./scripts/env_api.sh
```

Alternatively, create `.env` in the repository root yourself. Add the keys for the network mode you intend to use:

```dotenv
BYBIT_API_KEY=your_mainnet_key
BYBIT_API_SECRET=your_mainnet_secret
BYBIT_API_KEY_TEST=your_testnet_key
BYBIT_API_SECRET_TEST=your_testnet_secret
```

The application reads `.env` and does not store API secrets in its settings file. Use testnet credentials while checking order behavior. Enable Testnet in the trading tab before placing test orders.

## Run

From the activated environment, run:

```bash
python main.py
```

The application opens with the saved tab settings, or creates a Bybit tab with defaults. Settings are stored in `scripts/settings.json`.

## Trading Controls

Each trading tab has its own symbol, testnet setting, order quantity, leverage, entry window, profit target, and direction settings. By default, the entry window specifies seconds before funding. Enable **Enter after funding** below this field to change it to seconds after the most recent funding payout; the setting is saved independently for each tab. The global trade-block control prevents automatic funding entries while enabled. The Close All Trades button asks for confirmation and closes open positions for that tab's selected symbol.

The automatic funding scanner only considers negative funding rates. It uses Bybit's public market ticker endpoint. Automatic trading uses the credentials and network mode configured for the selected trading tab.

## Statistics

The Statistics tab displays records from `funding_trader.db`, supports manual entries, and can import recent closed Bybit trades. The Observation tab can start or stop a separate recorder process that writes to the same SQLite database; its analysis view summarizes collected records. On first launch after this update, existing `trade_stats.csv` and `funding_stats.csv` files are imported once and are left untouched as backups.

The funding statistics recorder currently initializes a Bybit mainnet client (`testnet=False`) regardless of the trading tab's Testnet checkbox. Configure appropriate mainnet API credentials before enabling collection. The generated SQLite database and settings are local application data and are excluded from version control.

## Project Layout

- `main.py`: application entry point
- `gui.py`: PyQt6 interface, tabs, and trading workflow
- `logic.py`: Bybit API calls and order helpers
- `auto_scanner.py`: funding opportunity scanner
- `stats_funding.py`: standalone funding-event data collector
- `database.py`, `stats_manager.py`, `funding_analysis.py`: SQLite storage and statistics analysis
- `settings_manager.py`, `tab_data.py`: persisted settings and tab state
- `translations.py`: English and Ukrainian interface strings

## License

This project is distributed under the GNU General Public License v3. See [LICENCE.md](LICENCE.md).
