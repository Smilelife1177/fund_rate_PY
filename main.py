import sys
from PyQt6.QtWidgets import QApplication
from gui import FundingTraderApp
from logic import initialize_bybit_client

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication(sys.argv)
    # Initialize Bybit client
    session = initialize_bybit_client()
    window = FundingTraderApp(session)
    window.show()
    sys.exit(app.exec())