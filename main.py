import sys
from PyQt6.QtWidgets import QApplication
from gui import FundingTraderApp

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication(sys.argv)
    window = FundingTraderApp()
    window.show()
    sys.exit(app.exec())