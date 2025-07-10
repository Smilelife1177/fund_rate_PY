import sys
from PyQt6.QtWidgets import QApplication
from logic_f_bb import FundingTraderLogic
from gui_f_bb import FundingTraderGUI
from dotenv import load_dotenv

if __name__ == "__main__":
    print("Starting application...")
    load_dotenv()
    app = QApplication(sys.argv)
    logic = FundingTraderLogic()
    window = FundingTraderGUI(logic)
    window.show()
    sys.exit(app.exec())