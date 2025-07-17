import sys
import json
import os
from PyQt6.QtWidgets import QApplication
from gui import FundingTraderApp
from logic import initialize_client

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication(sys.argv)
    exchange = "Bybit"  # Default to Bybit
    testnet = False  # Default value
    settings_path = r"scripts\settings.json"
    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                settings = json.load(f)
                testnet = settings.get("testnet", testnet)
    except Exception as e:
        print(f"Error loading settings in main.py: {e}, using default testnet={testnet}")
    session = initialize_client(exchange, testnet)
    window = FundingTraderApp(session, testnet, exchange)
    window.show()
    sys.exit(app.exec())