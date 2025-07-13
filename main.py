import sys
from PyQt6.QtWidgets import QApplication
from gui import FundingTraderApp
from logic import initialize_bybit_client

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication(sys.argv)
    testnet = False  
    session = initialize_bybit_client(testnet)
    window = FundingTraderApp(session, testnet)
    window.show()
    sys.exit(app.exec())