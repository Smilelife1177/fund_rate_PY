import sys
from PyQt6.QtWidgets import QApplication
from gui import FundingTraderApp
from logic import initialize_client

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication(sys.argv)
    testnet = False
    exchange = "Bybit"  # Default to Bybit
    session = initialize_client(exchange, testnet)
    window = FundingTraderApp(session, testnet, exchange)
    window.show()
    sys.exit(app.exec())