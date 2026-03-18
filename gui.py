import os
from datetime import datetime, timezone
import json
import time
import math
import csv
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel, QDoubleSpinBox, QSlider, QComboBox, QCheckBox, 
    QMessageBox, QTabWidget, QToolButton, QTabBar, QScrollArea, QHBoxLayout, QTableWidget, QTableWidgetItem, QDialog, QDialogButtonBox, QTextEdit
)
from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from logic import (
    get_account_balance, get_funding_data, get_current_price, get_next_funding_time, place_market_order, 
    get_symbol_info, place_limit_close_order, update_ping, initialize_client, close_all_positions, 
    get_optimal_limit_price, get_candle_open_price, place_stop_loss_order, get_order_execution_price
)
from translations import translations 
import requests
from PyQt6.QtCore import QThread, pyqtSignal

class FundingTraderApp(QMainWindow):
    def __init__(self, session, testnet, exchange):
        super().__init__()
        self.settings_path = r"scripts\settings.json"
        self.language = self.load_language()
        self.trans = translations[self.language]
        self.setWindowTitle(self.trans["window_title"].format(exchange))
        self.setGeometry(100, 100, 1800, 1000)   # n n ширина висота
        self.set_window_icon()

        self.central_widget = QWidget()
        self.main_layout = QVBoxLayout(self.central_widget)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.central_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCentralWidget(scroll_area)

        self.init_language_selection()
        self.init_tab_widget()
        self.tab_data_list = []
        self.tab_count = 0
        loaded_settings = self.load_settings()
        initial_settings = loaded_settings[0] if loaded_settings else None
        self.add_new_tab(session=session, testnet=testnet, exchange=exchange, settings=initial_settings)
        self.init_stats_tab()
        self.initialize_stats_csv()
        self.update_stats_table()
        self.main_layout.addWidget(self.language_label)
        self.main_layout.addWidget(self.language_combobox)
        self.main_layout.addWidget(self.tab_widget)
        self.save_settings()

    def set_window_icon(self):
        icon_path = r"images\log.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Icon file not found at: {icon_path}")

    def init_language_selection(self):
        self.language_label = QLabel(self.trans["language_label"])
        self.language_combobox = QComboBox()
        self.language_combobox.addItems(["English", "Українська"])
        self.language_combobox.setCurrentText("English" if self.language == "en" else "Українська")
        self.language_combobox.currentTextChanged.connect(self.update_language)

    def init_tab_widget(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.add_tab_button = QToolButton()
        self.add_tab_button.setText("+")
        self.add_tab_button.setFixedWidth(30)
        self.add_tab_button.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.add_tab_button.clicked.connect(self.add_new_tab)
        self.tab_widget.addTab(QWidget(), "+")
        self.tab_widget.setTabEnabled(self.tab_widget.count() - 1, False)
        self.tab_widget.tabBar().setTabButton(self.tab_widget.count() - 1, QTabBar.ButtonPosition.RightSide, self.add_tab_button)

    def init_stats_tab(self):
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)

        self.stats_table = QTableWidget()
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        stats_layout.addWidget(self.stats_table)

        # Кнопки в рядок
        btn_layout = QHBoxLayout()
        
        refresh_stats_button = QPushButton(self.trans["refresh_button"])
        refresh_stats_button.clicked.connect(self.update_stats_table)
        btn_layout.addWidget(refresh_stats_button)

        # Нова кнопка
        add_trade_button = QPushButton("Додати угоду вручну" if self.language == "en" else "Додати угоду вручну")
        add_trade_button.clicked.connect(self.open_stats_input_dialog)
        btn_layout.addWidget(add_trade_button)

        stats_layout.addLayout(btn_layout)

        self.tab_widget.addTab(stats_tab, "Statistics" if self.language == "en" else "Статистика")

###
    STATS_CSV_FILE = "trade_stats.csv"
    STATS_HEADERS = ["Дата_Час", "Процент", "Фандинг", "Прибиль", "Доход", "Комисия", "Обєм", "В-сделке", "Тикер"]

    def initialize_stats_csv(self):
        """Створює файл статистики, якщо його ще немає"""
        if not os.path.exists(self.STATS_CSV_FILE):
            with open(self.STATS_CSV_FILE, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(self.STATS_HEADERS)

    def process_stats_input(self, data):
        """Обробка введеного рядка (майже без змін з stats.py)"""
        import re
        data = re.sub(r'\s*\$\s*', ' ', data)  # Замінюємо $ на пробіл
        values = [v.strip() for v in re.split(r'\s+', data.strip()) if v.strip()]
        if len(values) != 8:
            QMessageBox.warning(
                self,
                "Помилка введення",
                f"Очікується 8 значень, отримано {len(values)}:\n\n{values}"
            )
            return None
        return values

    def write_stats_to_csv(self, values):
        """Запис рядка в CSV"""
        with open(self.STATS_CSV_FILE, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            row = [current_time] + values
            writer.writerow(row)

    def open_stats_input_dialog(self):
        """Відкриває вікно для введення даних угоди"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Запис нової угоди")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        label = QLabel("Введіть дані у форматі:\nПроцент Фандинг Прибиль Доход Комисия Обєм В-сделке Тикер")
        label.setWordWrap(True)
        layout.addWidget(label)

        example = QLabel("Приклад:\n2,43% -2,77 0,39 3,37 0,21 137 11с MYXUSDT")
        example.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(example)

        input_field = QTextEdit()
        input_field.setAcceptRichText(False)
        input_field.setPlaceholderText("Вставте сюди дані...")
        input_field.setFixedHeight(80)
        layout.addWidget(input_field)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            user_input = input_field.toPlainText().strip()
            if not user_input:
                return

            values = self.process_stats_input(user_input)
            if values:
                self.initialize_stats_csv()       # на всяк випадок
                self.write_stats_to_csv(values)
                QMessageBox.information(self, "Успіх", "Дані успішно записано в trade_stats.csv")
                self.update_stats_table()         # оновлюємо таблицю одразу
###
    def update_stats_table(self):
        if not os.path.exists("trade_stats.csv"):
            self.stats_table.clear()
            return
        with open("trade_stats.csv", 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            data = list(reader)
            if not data:
                return
            headers = data[0]
            self.stats_table.setColumnCount(len(headers))
            self.stats_table.setHorizontalHeaderLabels(headers)
            self.stats_table.setRowCount(len(data) - 1)
            for row_idx, row in enumerate(data[1:]):
                for col_idx, val in enumerate(row):
                    self.stats_table.setItem(row_idx, col_idx, QTableWidgetItem(val))
            self.stats_table.resizeColumnsToContents()

    def load_language(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    settings = json.load(f)
                    return settings.get("language", "en")
            except Exception as e:
                print(f"Error loading language: {e}")
        return "en"

    def load_settings(self):
        default_settings = {
            "tabs": [{
                "selected_symbol": "HYPERUSDT",
                "funding_interval_hours": 1.0,
                "reverse_side": False,
                "entry_time_seconds": 5.0,
                "qty": 45.0,
                "profit_percentage": 1.0,
                "leverage": 1.0,
                "exchange": "Bybit",
                "testnet": False,
                "auto_limit": False,
                "stop_loss_percentage": 0.5,
                "stop_loss_enabled": True
            }],
            "language": "en"
        }
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r") as f:
                    settings = json.load(f)
                    # Оновлюємо кожну вкладку, додаючи reverse_side, якщо його немає
                    tabs = settings.get("tabs", default_settings["tabs"])
                    for tab in tabs:
                        tab["reverse_side"] = tab.get("reverse_side", False)
                    return tabs
                
                    # return settings.get("tabs", default_settings["tabs"])
            return default_settings["tabs"]
        except Exception as e:
            print(f"Error loading settings: {e}")
            return default_settings["tabs"]

    def save_settings(self):
        tabs = [
            {
                "selected_symbol": td["selected_symbol"],
                "reverse_side": td["reverse_side"],
                "funding_interval_hours": td["funding_interval_hours"],
                "entry_time_seconds": td["entry_time_seconds"],
                "qty": td["qty"],
                "profit_percentage": td["profit_percentage"],
                "leverage": td["leverage"],
                "exchange": td["exchange"],
                "testnet": td["testnet"],
                "auto_limit": td["auto_limit"],
                "stop_loss_percentage": td["stop_loss_percentage"],
                "stop_loss_enabled": td["stop_loss_enabled"],
                "auto_mode": td.get("auto_mode", False),
                "auto_min_funding": td.get("auto_min_funding", 0.05),
            } for td in self.tab_data_list
        ]
        settings = {"tabs": tabs, "language": self.language}
        try:
            with open(self.settings_path, "w") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def add_new_tab(self, session=None, testnet=None, exchange=None, settings=None):
        self.tab_count += 1
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_data = self.init_tab_data(settings or {}, session, testnet, exchange)
        self.create_tab_ui(tab_layout, tab_data)
        self.tab_data_list.append(tab_data)
        self.tab_widget.insertTab(self.tab_widget.count() - 1, tab, self.trans["tab_title"].format(self.tab_count))
        self.tab_widget.setCurrentWidget(tab)
        tab_data["tab_index"] = self.tab_count
        self.init_tab_timers(tab_data)
        self.update_tab_funding_data(tab_data)
        return tab_data

    def init_tab_data(self, settings, session, testnet, exchange):
        defaults = {
            "selected_symbol": "HYPERUSDT",
            "position_open": False,
            "reverse_side": settings.get("reverse_side", False),
            "update_count": 0,
            "funding_interval_hours": 1.0 if exchange == "Bybit" else 8.0,
            "entry_time_seconds": 5.0,
            "qty": 45.0,
            "profit_percentage": 1.0,
            "leverage": 1.0,
            "exchange": exchange or "Bybit",
            "testnet": testnet or False,
            "auto_limit": False,
            "stop_loss_percentage": 0.5,
            "stop_loss_enabled": True,
            "funding_data": None,
            "open_order_id": None,
            "funding_time_price": None,
            "limit_price": None,
            "pre_funding_price": None,
            # Авто-сканування
            "auto_mode": settings.get("auto_mode", False),
            "auto_min_funding": settings.get("auto_min_funding", 0.05),
            "auto_scan_done_this_minute": False,
            "auto_scan_results": [],
            "auto_selected_symbol": None
        }
        defaults.update(settings)
        defaults["session"] = session or initialize_client(defaults["exchange"], defaults["testnet"])
        return defaults

    def add_reverse_side_ui(self, layout, tab_data):
        label = QLabel(self.trans["reverse_side_label"])
        checkbox = QCheckBox(self.trans["reverse_side_checkbox"])
        checkbox.setChecked(tab_data["reverse_side"])
        checkbox.stateChanged.connect(lambda s: self.update_tab_reverse_side(tab_data, s))
        layout.addWidget(label)
        layout.addWidget(checkbox)
        tab_data["reverse_side_label"] = label
        tab_data["reverse_side_checkbox"] = checkbox

    def update_tab_reverse_side(self, tab_data, state):
        if tab_data not in self.tab_data_list: return
        tab_data["reverse_side"] = state == Qt.CheckState.Checked.value
        self.save_settings()

    # ─── АВТО-РЕЖИМ ────────────────────────────────────────────────────────────

    def add_auto_scan_ui(self, layout, tab_data):
        """Права панель: перемикач ручний/авто + таблиця результатів сканування."""
        t = self.trans

        # Заголовок
        title = QLabel(t["auto_mode_title"])
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)
        tab_data["auto_mode_title_label"] = title

        # Перемикач Ручний / Авто
        mode_row = QHBoxLayout()
        mode_label = QLabel(t["auto_mode_label"])
        mode_combo = QComboBox()
        mode_combo.addItems([t["auto_mode_manual"], t["auto_mode_auto"]])
        mode_combo.setCurrentIndex(1 if tab_data.get("auto_mode") else 0)
        mode_combo.currentIndexChanged.connect(lambda i: (self.set_auto_mode(tab_data, i == 1), self.save_settings()))
        mode_row.addWidget(mode_label)
        mode_row.addWidget(mode_combo)
        layout.addLayout(mode_row)
        tab_data["auto_mode_combo"] = mode_combo
        tab_data["auto_mode_label_widget"] = mode_label

        # Мінімальний поріг фандингу
        threshold_row = QHBoxLayout()
        threshold_label = QLabel(t["auto_min_funding_label"])
        threshold_spin = QDoubleSpinBox()
        threshold_spin.setRange(0.001, 5.0)
        threshold_spin.setSingleStep(0.005)
        threshold_spin.setDecimals(3)
        threshold_spin.setValue(tab_data.get("auto_min_funding", 0.05))
        threshold_spin.valueChanged.connect(lambda v: (tab_data.update({"auto_min_funding": v}), self.save_settings()))
        threshold_row.addWidget(threshold_label)
        threshold_row.addWidget(threshold_spin)
        layout.addLayout(threshold_row)
        tab_data["auto_threshold_spin"] = threshold_spin
        tab_data["auto_threshold_label"] = threshold_label

        # Статус наступного сканування
        status_label = QLabel(t["auto_status_disabled"])
        status_label.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(status_label)
        tab_data["auto_status_label"] = status_label

        # Обрана монета
        chosen_label = QLabel(t["auto_chosen_none"])
        chosen_label.setStyleSheet("font-weight: bold; color: #1a6e1a;")
        layout.addWidget(chosen_label)
        tab_data["auto_chosen_label"] = chosen_label

        # Таблиця результатів
        results_label = QLabel(t["auto_results_label"])
        layout.addWidget(results_label)
        tab_data["auto_results_label"] = results_label

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels([t["auto_col_symbol"], t["auto_col_rate"], t["auto_col_time"], t["auto_col_select"]])
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, table.horizontalHeader().ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setMinimumHeight(300)
        layout.addWidget(table)
        tab_data["auto_scan_table"] = table

        # Кнопка ручного сканування
        scan_btn = QPushButton(t["auto_scan_now_btn"])
        scan_btn.clicked.connect(lambda: self.run_auto_scan(tab_data))
        layout.addWidget(scan_btn)
        tab_data["auto_scan_btn"] = scan_btn

        layout.addStretch()

    def set_auto_mode(self, tab_data, enabled: bool):
        tab_data["auto_mode"] = enabled
        tab_data["auto_scan_done_this_minute"] = False
        if enabled:
            tab_data["auto_status_label"].setText(self.trans["auto_status_waiting"])
            tab_data["auto_status_label"].setStyleSheet("color: #1a6e1a; font-style: italic;")
        else:
            tab_data["auto_status_label"].setText(self.trans["auto_status_disabled"])
            tab_data["auto_status_label"].setStyleSheet("color: #555; font-style: italic;")
        self.update_auto_scan_table(tab_data)


    def check_auto_scan_trigger(self, tab_data):
        """Викликається кожну секунду. Запускає сканування за 60 сек до нового годинника."""
        if not tab_data.get("auto_mode"):
            return

        now = datetime.now(timezone.utc)
        seconds_into_hour = now.minute * 60 + now.second
        seconds_left_in_hour = 3600 - seconds_into_hour   # скільки секунд до нового годинника

        # Оновлюємо статус-лейбл
        if seconds_left_in_hour > 60:
            mins = (seconds_left_in_hour - 60) // 60
            secs = (seconds_left_in_hour - 60) % 60
            tab_data["auto_status_label"].setText(self.trans["auto_status_countdown"].format(mins=mins, secs=secs))
            tab_data["auto_status_label"].setStyleSheet("color: #555; font-style: italic;")
            tab_data["auto_scan_done_this_minute"] = False   # скидаємо прапор для нового циклу
        elif seconds_left_in_hour <= 60 and not tab_data.get("auto_scan_done_this_minute"):
            tab_data["auto_status_label"].setText(self.trans["auto_status_scanning"])
            tab_data["auto_status_label"].setStyleSheet("color: #e07b00; font-weight: bold;")
            tab_data["auto_scan_done_this_minute"] = True
            # Запускаємо сканування в окремому потоці щоб не блокувати UI
            self.run_auto_scan(tab_data)

    def run_auto_scan(self, tab_data):
        """Сканує всі USDT-перп монети.
        Таблиця: всі монети де |фандинг| >= поріг (будь-який час).
        Авто-вибір: серед них тільки ті де фандинг <= 60 сек.
        """
        try:
            threshold = tab_data.get("auto_min_funding", 0.05)
            url = "https://api.bybit.com/v5/market/tickers"
            resp = requests.get(url, params={"category": "linear"}, timeout=8)
            resp.raise_for_status()
            data = resp.json()

            if data.get("retCode") != 0:
                tab_data["auto_status_label"].setText(self.trans["auto_api_error"])
                return

            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            all_above_threshold = []   # всі монети вище порогу — для таблиці
            near_funding = []          # з них тільки де фандинг <= 60 сек — для авто-вибору

            for item in data["result"]["list"]:
                symbol = item.get("symbol", "")
                if not symbol.endswith("USDT"):
                    continue
                try:
                    rate = float(item.get("fundingRate") or 0)
                    next_ft_ms = int(item.get("nextFundingTime") or 0)
                except (ValueError, TypeError):
                    continue

                if next_ft_ms == 0:
                    continue

                rate_pct = rate * 100
                if abs(rate_pct) < threshold:
                    continue

                secs_to_funding = (next_ft_ms - now_ms) / 1000.0

                entry = {"symbol": symbol, "rate": rate_pct, "secs": secs_to_funding}
                all_above_threshold.append(entry)

                if 0 <= secs_to_funding <= 60:
                    near_funding.append(entry)

            all_above_threshold.sort(key=lambda x: abs(x["rate"]), reverse=True)
            near_funding.sort(key=lambda x: abs(x["rate"]), reverse=True)

            tab_data["auto_scan_results"] = all_above_threshold
            self.update_auto_scan_table(tab_data)

            if near_funding:
                best = near_funding[0]
                tab_data["auto_selected_symbol"] = best["symbol"]
                tab_data["auto_chosen_label"].setText(self.trans["auto_chosen_selected"].format(symbol=best["symbol"], rate=best["rate"]))
                tab_data["auto_chosen_label"].setStyleSheet("font-weight: bold; color: #1a6e1a;")
                tab_data["selected_symbol"] = best["symbol"]
                tab_data["coin_input"].setText(best["symbol"])
                self.update_tab_funding_web_view(tab_data)
                self.tab_widget.setTabText(self.tab_data_list.index(tab_data), best["symbol"])
                self.save_settings()
                self.update_tab_funding_data(tab_data)
                tab_data["auto_status_label"].setText(self.trans["auto_status_found"].format(n=len(all_above_threshold), symbol=best["symbol"]))
                tab_data["auto_status_label"].setStyleSheet("color: #1a6e1a; font-weight: bold;")
            elif all_above_threshold:
                tab_data["auto_chosen_label"].setText(self.trans["auto_chosen_waiting"].format(n=len(all_above_threshold)))
                tab_data["auto_chosen_label"].setStyleSheet("font-weight: bold; color: #555;")
                tab_data["auto_status_label"].setText(self.trans["auto_status_watching"].format(n=len(all_above_threshold)))
                tab_data["auto_status_label"].setStyleSheet("color: #555; font-style: italic;")
            else:
                tab_data["auto_chosen_label"].setText(self.trans["auto_chosen_not_found"])
                tab_data["auto_chosen_label"].setStyleSheet("font-weight: bold; color: #b00;")
                tab_data["auto_status_label"].setText(self.trans["auto_status_none"])
                tab_data["auto_status_label"].setStyleSheet("color: #b00; font-style: italic;")

        except Exception as e:
            print(f"Auto scan error: {e}")
            tab_data["auto_status_label"].setText(self.trans["auto_error"].format(e=e))
            tab_data["auto_status_label"].setStyleSheet("color: red;")

    def format_funding_time(self, secs: float) -> str:
        """Converts seconds to hh:mm:ss-style string, language-aware."""
        if secs < 1:
            return self.trans["auto_time_soon"]
        total = int(secs)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        if h > 0:
            return self.trans["auto_time_format"].format(h=h, m=m, s=s)
        t = self.trans["auto_time_format"]
        # Build only m+s part by formatting with h=0 then stripping the hours token
        if m > 0:
            uk = self.language == "uk"
            return f"{m}{'хв' if uk else 'm'} {s:02d}{'с' if uk else 's'}"
        uk = self.language == "uk"
        return f"{s}{'с' if uk else 's'}"

    def update_auto_scan_table(self, tab_data):
        results = tab_data.get("auto_scan_results", [])
        table = tab_data.get("auto_scan_table")
        if table is None:
            return
        table.setRowCount(len(results))
        is_manual = not tab_data.get("auto_mode", False)
        for row, item in enumerate(results):
            sym_item = QTableWidgetItem(item["symbol"])
            rate_item = QTableWidgetItem(f"{item['rate']:+.4f}%")
            secs_item = QTableWidgetItem(self.format_funding_time(item['secs']))

            # Підсвітка обраної монети
            if item["symbol"] == tab_data.get("auto_selected_symbol"):
                for cell in (sym_item, rate_item, secs_item):
                    cell.setBackground(Qt.GlobalColor.green)

            # Колір по знаку фандингу
            color = Qt.GlobalColor.darkGreen if item["rate"] > 0 else Qt.GlobalColor.darkRed
            rate_item.setForeground(color)

            table.setItem(row, 0, sym_item)
            table.setItem(row, 1, rate_item)
            table.setItem(row, 2, secs_item)

            # Кнопка вибору — тільки в ручному режимі
            if is_manual:
                symbol = item["symbol"]
                btn = QPushButton(self.trans["auto_col_select"])
                btn.setFixedHeight(22)
                btn.clicked.connect(lambda checked, s=symbol: self.update_tab_symbol(tab_data, s))
                table.setCellWidget(row, 3, btn)
            else:
                table.setCellWidget(row, 3, None)

        table.resizeColumnsToContents()
        table.setColumnWidth(3, 80)

    def create_tab_ui(self, layout, tab_data):
        # Ліва колонка — контроли (фіксована ширина)
        left_widget = QWidget()
        left_widget.setFixedWidth(320) #розмір самої лівої колонки
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.add_exchange_ui(left_layout, tab_data)
        self.add_testnet_ui(left_layout, tab_data)
        self.add_coin_ui(left_layout, tab_data)
        self.add_funding_interval_ui(left_layout, tab_data)
        self.add_entry_time_ui(left_layout, tab_data)
        self.add_qty_ui(left_layout, tab_data)
        self.add_profit_percentage_ui(left_layout, tab_data)
        self.add_auto_limit_ui(left_layout, tab_data)
        self.add_leverage_ui(left_layout, tab_data)
        self.add_stop_loss_ui(left_layout, tab_data)
        self.add_reverse_side_ui(left_layout, tab_data)
        self.add_info_labels(left_layout, tab_data)
        self.add_buttons(left_layout, tab_data)
        left_layout.addStretch()

        # Центральна колонка — Bybit WebView (фіксована ширина, не розтягується)
        center_widget = QWidget()
        center_widget.setFixedWidth(600)#розмір вкладки байбіта (центральна колонка)
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(4, 0, 4, 0)
        self.add_funding_web_view(center_layout, tab_data)

        # Права колонка — авто-режим сканування
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 4, 4, 4)
        self.add_auto_scan_ui(right_layout, tab_data)
        tab_data["future_panel"] = right_widget

        hbox = QHBoxLayout()
        hbox.setSpacing(8)
        hbox.addWidget(left_widget)
        hbox.addWidget(center_widget)
        hbox.addWidget(right_widget, 1)
        layout.addLayout(hbox)

    def add_exchange_ui(self, layout, tab_data):
        label = QLabel(self.trans["exchange_label"])
        combobox = QComboBox()
        combobox.addItems(["Bybit", "Binance"])
        combobox.setCurrentText(tab_data["exchange"])
        combobox.currentTextChanged.connect(lambda v: self.update_tab_exchange(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(combobox)
        tab_data["exchange_label"] = label
        tab_data["exchange_combobox"] = combobox

    def add_testnet_ui(self, layout, tab_data):
        label = QLabel(self.trans["testnet_label"])
        checkbox = QCheckBox(self.trans["testnet_checkbox"])
        checkbox.setChecked(tab_data["testnet"])
        checkbox.stateChanged.connect(lambda s: self.update_tab_testnet(tab_data, s))
        layout.addWidget(label)
        layout.addWidget(checkbox)
        tab_data["testnet_label"] = label
        tab_data["testnet_checkbox"] = checkbox

    def add_coin_ui(self, layout, tab_data):
        label = QLabel(self.trans["coin_input_label"])
        input_field = QLineEdit(tab_data["selected_symbol"])
        button = QPushButton(self.trans["update_coin_button"])
        button.clicked.connect(lambda: self.update_tab_symbol(tab_data, input_field.text()))
        layout.addWidget(label)
        layout.addWidget(input_field)
        layout.addWidget(button)
        tab_data["coin_input_label"] = label
        tab_data["coin_input"] = input_field
        tab_data["update_coin_button"] = button

    def add_funding_interval_ui(self, layout, tab_data):
        label = QLabel(self.trans["funding_interval_label"])
        combobox = QComboBox()
        intervals = ["0.01", "1", "4", "8"] if tab_data["exchange"] == "Bybit" else ["8"]
        combobox.addItems(intervals)
        formatted = str(float(tab_data["funding_interval_hours"])).rstrip(".0")
        combobox.setCurrentText(formatted)
        combobox.currentTextChanged.connect(lambda v: self.update_tab_funding_interval(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(combobox)
        tab_data["funding_interval_label"] = label
        tab_data["funding_interval_combobox"] = combobox

    def add_entry_time_ui(self, layout, tab_data):
        label = QLabel(self.trans["entry_time_label"])
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0.5, 60.0)
        spinbox.setValue(tab_data["entry_time_seconds"])
        spinbox.setSingleStep(0.1)
        spinbox.valueChanged.connect(lambda v: self.update_tab_entry_time(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(spinbox)
        tab_data["entry_time_label"] = label
        tab_data["entry_time_spinbox"] = spinbox

    def add_qty_ui(self, layout, tab_data):
        label = QLabel(self.trans["qty_label"])
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0.001, 1000000.0)
        spinbox.setValue(tab_data["qty"])
        spinbox.setSingleStep(0.001)
        spinbox.valueChanged.connect(lambda v: self.update_tab_qty(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(spinbox)
        tab_data["qty_label"] = label
        tab_data["qty_spinbox"] = spinbox

    def add_profit_percentage_ui(self, layout, tab_data):
        label = QLabel(self.trans["profit_percentage_label"])
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0.1, 10.0)
        spinbox.setValue(tab_data["profit_percentage"])
        spinbox.setSingleStep(0.1)
        spinbox.valueChanged.connect(lambda v: self.update_tab_profit_percentage(tab_data, v))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(10, 1000)
        slider.setValue(int(tab_data["profit_percentage"] * 100))
        slider.setSingleStep(10)
        slider.valueChanged.connect(lambda v: self.update_tab_profit_percentage_from_slider(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(spinbox)
        layout.addWidget(slider)
        tab_data["profit_percentage_label"] = label
        tab_data["profit_percentage_spinbox"] = spinbox
        tab_data["profit_percentage_slider"] = slider

    def add_auto_limit_ui(self, layout, tab_data):
        label = QLabel(self.trans["auto_limit_label"])
        checkbox = QCheckBox(self.trans["auto_limit_checkbox"])
        checkbox.setChecked(tab_data["auto_limit"])
        checkbox.stateChanged.connect(lambda s: self.update_tab_auto_limit(tab_data, s))
        layout.addWidget(label)
        layout.addWidget(checkbox)
        tab_data["auto_limit_label"] = label
        tab_data["auto_limit_checkbox"] = checkbox

    def add_leverage_ui(self, layout, tab_data):
        label = QLabel(self.trans["leverage_label"])
        spinbox = QDoubleSpinBox()
        spinbox.setRange(1.0, 100.0)
        spinbox.setValue(tab_data["leverage"])
        spinbox.setSingleStep(0.1)
        spinbox.valueChanged.connect(lambda v: self.update_tab_leverage(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(spinbox)
        tab_data["leverage_label"] = label
        tab_data["leverage_spinbox"] = spinbox

    def add_stop_loss_ui(self, layout, tab_data):
        enabled_label = QLabel(self.trans["stop_loss_enabled_label"])
        enabled_checkbox = QCheckBox(self.trans["stop_loss_enabled_checkbox"])
        enabled_checkbox.setChecked(tab_data["stop_loss_enabled"])
        enabled_checkbox.stateChanged.connect(lambda s: self.update_tab_stop_loss_enabled(tab_data, s))
        percentage_label = QLabel(self.trans["stop_loss_percentage_label"])
        percentage_spinbox = QDoubleSpinBox()
        percentage_spinbox.setRange(0.1, 10.0)
        percentage_spinbox.setValue(tab_data["stop_loss_percentage"])
        percentage_spinbox.setSingleStep(0.1)
        percentage_spinbox.valueChanged.connect(lambda v: self.update_tab_stop_loss_percentage(tab_data, v))
        layout.addWidget(enabled_label)
        layout.addWidget(enabled_checkbox)
        layout.addWidget(percentage_label)
        layout.addWidget(percentage_spinbox)
        tab_data["stop_loss_enabled_label"] = enabled_label
        tab_data["stop_loss_enabled_checkbox"] = enabled_checkbox
        tab_data["stop_loss_percentage_label"] = percentage_label
        tab_data["stop_loss_percentage_spinbox"] = percentage_spinbox

    def add_info_labels(self, layout, tab_data):
        funding_info = QLabel(self.trans["funding_info_label"])
        price = QLabel(self.trans["price_label"])
        balance = QLabel(self.trans["balance_label"])
        leveraged_balance = QLabel(self.trans["leveraged_balance_label"])
        volume = QLabel(self.trans["volume_label"])
        ping = QLabel(self.trans["ping_label"])
        layout.addWidget(funding_info)
        layout.addWidget(price)
        layout.addWidget(balance)
        layout.addWidget(leveraged_balance)
        layout.addWidget(volume)
        layout.addWidget(ping)
        tab_data["funding_info_label"] = funding_info
        tab_data["price_label"] = price
        tab_data["balance_label"] = balance
        tab_data["leveraged_balance_label"] = leveraged_balance
        tab_data["volume_label"] = volume
        tab_data["ping_label"] = ping

    def add_buttons(self, layout, tab_data):
        refresh = QPushButton(self.trans["refresh_button"])
        refresh.clicked.connect(lambda: self.update_tab_funding_data(tab_data))
        close_all = QPushButton(self.trans["close_all_trades_button"])
        close_all.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        close_all.clicked.connect(lambda: self.handle_tab_close_all_trades(tab_data))
        layout.addWidget(refresh)
        layout.addWidget(close_all)
        tab_data["refresh_button"] = refresh
        tab_data["close_all_trades_button"] = close_all

    def add_funding_web_view(self, layout, tab_data):
        profile = QWebEngineProfile(f"BybitProfile_{self.tab_count}", self)
        cache_path = os.path.join(os.getcwd(), "webcache", f"tab_{self.tab_count}")
        os.makedirs(cache_path, exist_ok=True)
        profile.setCachePath(cache_path)
        profile.setPersistentStoragePath(cache_path)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        view = QWebEngineView()
        page = QWebEnginePage(profile, view)
        view.setPage(page)
        view.setMinimumHeight(150)
        tab_data["funding_web_view"] = view
        tab_data["web_profile"] = profile
        layout.addWidget(view)
        self.update_tab_funding_web_view(tab_data)

    def init_tab_timers(self, tab_data):
        # Секундний таймер — відлік до фандингу та авто-сканування
        timer = QTimer()
        timer.timeout.connect(lambda: self.check_tab_funding_time(tab_data))
        timer.start(1000)
        # Таймер оновлення фандинг-рейту — кожні 5 хвилин
        funding_refresh_timer = QTimer()
        funding_refresh_timer.timeout.connect(lambda: self.update_tab_funding_data(tab_data))
        funding_refresh_timer.start(5 * 60 * 1000)
        # Таймер пінгу
        ping_timer = QTimer()
        ping_timer.timeout.connect(lambda: self.update_tab_ping(tab_data))
        ping_timer.start(30000)
        tab_data["timer"] = timer
        tab_data["funding_refresh_timer"] = funding_refresh_timer
        tab_data["ping_timer"] = ping_timer

    # Методи оновлення (групуємо)
    def update_language(self, language_text):
        self.language = "en" if language_text == "English" else "uk"
        self.trans = translations[self.language]
        self.setWindowTitle(self.trans["window_title"].format("Multi-Coin"))
        self.language_label.setText(self.trans["language_label"])
        for td in self.tab_data_list:
            self.update_tab_labels(td)
            self.update_tab_funding_data(td)
        self.tab_widget.setTabText(self.tab_widget.count() - 2, "Statistics" if self.language == "en" else "Статистика")
        self.save_settings()

    def update_tab_labels(self, tab_data):
        tab_data["exchange_label"].setText(self.trans["exchange_label"])
        tab_data["testnet_label"].setText(self.trans["testnet_label"])
        tab_data["reverse_side_label"].setText(self.trans["reverse_side_label"])
        tab_data["reverse_side_checkbox"].setText(self.trans["reverse_side_checkbox"])
        tab_data["testnet_checkbox"].setText(self.trans["testnet_checkbox"])
        tab_data["coin_input_label"].setText(self.trans["coin_input_label"])
        tab_data["update_coin_button"].setText(self.trans["update_coin_button"])
        tab_data["funding_interval_label"].setText(self.trans["funding_interval_label"])
        tab_data["entry_time_label"].setText(self.trans["entry_time_label"])
        tab_data["qty_label"].setText(self.trans["qty_label"])
        tab_data["profit_percentage_label"].setText(self.trans["profit_percentage_label"])
        tab_data["auto_limit_label"].setText(self.trans["auto_limit_label"])
        tab_data["auto_limit_checkbox"].setText(self.trans["auto_limit_checkbox"])
        tab_data["leverage_label"].setText(self.trans["leverage_label"])
        tab_data["stop_loss_percentage_label"].setText(self.trans["stop_loss_percentage_label"])
        tab_data["close_all_trades_button"].setText(self.trans["close_all_trades_button"])
        tab_data["stop_loss_enabled_label"].setText(self.trans["stop_loss_enabled_label"])
        tab_data["stop_loss_enabled_checkbox"].setText(self.trans["stop_loss_enabled_checkbox"])
        t = self.trans
        tab_data["auto_mode_title_label"].setText(t["auto_mode_title"])
        tab_data["auto_mode_label_widget"].setText(t["auto_mode_label"])
        tab_data["auto_threshold_label"].setText(t["auto_min_funding_label"])
        tab_data["auto_results_label"].setText(t["auto_results_label"])
        tab_data["auto_scan_btn"].setText(t["auto_scan_now_btn"])
        tab_data["auto_scan_table"].setHorizontalHeaderLabels([t["auto_col_symbol"], t["auto_col_rate"], t["auto_col_time"], t["auto_col_select"]])
        combo = tab_data["auto_mode_combo"]
        combo.blockSignals(True)
        current_idx = combo.currentIndex()
        combo.clear()
        combo.addItems([t["auto_mode_manual"], t["auto_mode_auto"]])
        combo.setCurrentIndex(current_idx)
        combo.blockSignals(False)
        if not tab_data.get("auto_mode"):
            tab_data["auto_status_label"].setText(t["auto_status_disabled"])
            tab_data["auto_chosen_label"].setText(t["auto_chosen_none"])

    def update_tab_exchange(self, tab_data, exchange):
        if tab_data not in self.tab_data_list: return
        tab_data["exchange"] = exchange
        self.update_tab_funding_web_view(tab_data)
        tab_data["funding_interval_hours"] = 1.0 if exchange == "Bybit" else 8.0
        tab_data["funding_interval_combobox"].blockSignals(True)
        tab_data["funding_interval_combobox"].clear()
        intervals = ["0.01", "1", "4", "8"] if exchange == "Bybit" else ["8"]
        tab_data["funding_interval_combobox"].addItems(intervals)
        formatted = str(float(tab_data["funding_interval_hours"])).rstrip(".0")
        tab_data["funding_interval_combobox"].setCurrentText(formatted)
        tab_data["funding_interval_combobox"].blockSignals(False)
        tab_data["session"] = initialize_client(exchange, tab_data["testnet"])
        self.save_settings()
        self.update_tab_funding_data(tab_data)

    def update_tab_testnet(self, tab_data, state):
        if tab_data not in self.tab_data_list: return
        tab_data["testnet"] = state == Qt.CheckState.Checked.value
        tab_data["session"] = initialize_client(tab_data["exchange"], tab_data["testnet"])
        self.save_settings()
        self.update_tab_funding_data(tab_data)

    def update_tab_symbol(self, tab_data, symbol):
        if tab_data not in self.tab_data_list: return
        tab_data["selected_symbol"] = symbol.strip().upper()
        self.update_tab_funding_web_view(tab_data)
        self.tab_widget.setTabText(self.tab_data_list.index(tab_data), f"{tab_data['selected_symbol']}")
        self.save_settings()
        self.update_tab_funding_data(tab_data)

    def update_tab_funding_interval(self, tab_data, value):
        if tab_data not in self.tab_data_list or not value: return
        tab_data["funding_interval_hours"] = float(value)
        self.save_settings()
        self.update_tab_funding_data(tab_data)

    def update_tab_entry_time(self, tab_data, value):
        if tab_data not in self.tab_data_list: return
        tab_data["entry_time_seconds"] = value
        self.save_settings()

    def update_tab_qty(self, tab_data, value):
        if tab_data not in self.tab_data_list: return
        tab_data["qty"] = value
        self.save_settings()
        self.update_tab_volume_label(tab_data)

    def update_tab_profit_percentage(self, tab_data, value):
        if tab_data not in self.tab_data_list: return
        tab_data["profit_percentage"] = value
        tab_data["profit_percentage_slider"].setValue(int(value * 100))
        self.save_settings()

    def update_tab_profit_percentage_from_slider(self, tab_data, value):
        if tab_data not in self.tab_data_list: return
        tab_data["profit_percentage"] = value / 100.0
        tab_data["profit_percentage_spinbox"].setValue(tab_data["profit_percentage"])
        self.save_settings()

    def update_tab_auto_limit(self, tab_data, state):
        if tab_data not in self.tab_data_list: return
        tab_data["auto_limit"] = state == Qt.CheckState.Checked.value
        self.save_settings()

    def update_tab_leverage(self, tab_data, value):
        if tab_data not in self.tab_data_list: return
        tab_data["leverage"] = value
        self.save_settings()
        self.update_tab_leveraged_balance_label(tab_data)

    def update_tab_stop_loss_percentage(self, tab_data, value):
        if tab_data not in self.tab_data_list: return
        tab_data["stop_loss_percentage"] = value
        self.save_settings()

    def update_tab_stop_loss_enabled(self, tab_data, state):
        if tab_data not in self.tab_data_list: return
        tab_data["stop_loss_enabled"] = state == Qt.CheckState.Checked.value
        self.save_settings()

    def update_tab_volume_label(self, tab_data):
        if tab_data not in self.tab_data_list: return
        price = get_current_price(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])
        balance = get_account_balance(tab_data["session"], tab_data["exchange"])
        leveraged = balance * tab_data["leverage"] if balance and tab_data["leverage"] else None
        if price and tab_data["qty"]:
            volume = tab_data["qty"] * price
            tab_data["volume_label"].setText(f"{self.trans['volume_label'].split(':')[0]}: ${volume:.2f} USD")
            color = "red" if volume < 5.0 or (leveraged and volume > leveraged) else "black"
            tab_data["volume_label"].setStyleSheet(f"color: {color};")
        else:
            tab_data["volume_label"].setText(self.trans["volume_label"])
            tab_data["volume_label"].setStyleSheet("color: black;")

    def update_tab_leveraged_balance_label(self, tab_data):
        if tab_data not in self.tab_data_list: return
        balance = get_account_balance(tab_data["session"], tab_data["exchange"])
        if balance and tab_data["leverage"]:
            leveraged = balance * tab_data["leverage"]
            tab_data["leveraged_balance_label"].setText(f"{self.trans['leveraged_balance_label'].split(':')[0]}: ${leveraged:.2f} USDT")
        else:
            tab_data["leveraged_balance_label"].setText(self.trans["leveraged_balance_label"])

    def update_tab_ping(self, tab_data):
        if tab_data not in self.tab_data_list: return
        update_ping(tab_data["session"], tab_data["ping_label"], tab_data["exchange"])

    def update_tab_funding_web_view(self, tab_data):
        if tab_data not in self.tab_data_list: return
        symbol = tab_data["selected_symbol"]
        if tab_data["exchange"] == "Bybit":
            url = f"https://www.bybit.com/trade/usdt/{symbol}"
            tab_data["funding_web_view"].setUrl(QUrl(url))
            tab_data["funding_web_view"].setVisible(True)
        else:
            tab_data["funding_web_view"].setVisible(False)

    def update_tab_funding_data(self, tab_data, retry_count=3, retry_delay=2):
        if tab_data not in self.tab_data_list: return
        for attempt in range(retry_count):
            try:
                tab_data["funding_data"] = get_funding_data(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])
                price = get_current_price(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])
                tab_data["price_label"].setText(f"{self.trans['price_label'].split(':')[0]}: ${price:.6f}" if price else self.trans["price_label"])
                balance = get_account_balance(tab_data["session"], tab_data["exchange"])
                tab_data["balance_label"].setText(f"{self.trans['balance_label'].split(':')[0]}: ${balance:.2f} USDT" if balance else self.trans["balance_label"])
                self.update_tab_leveraged_balance_label(tab_data)
                if tab_data["funding_data"]:
                    rate = tab_data["funding_data"]["funding_rate"]
                    time_val = tab_data["funding_data"]["funding_time"]
                    _, time_str = get_next_funding_time(time_val, tab_data["funding_interval_hours"])
                    tab_data["funding_info_label"].setText(f"{self.trans['funding_info_label'].split(':')[0]}: {rate:.4f}% | {self.trans['funding_info_label'].split('|')[1].strip()}: {time_str}")
                else:
                    self.reset_tab_labels_to_defaults(tab_data)
                self.update_tab_volume_label(tab_data)
                self.update_tab_ping(tab_data)
                self.update_tab_funding_web_view(tab_data)
                return
            except Exception as e:
                print(f"Error updating funding data (attempt {attempt + 1}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
        self.reset_tab_labels_to_error(tab_data)

    def reset_tab_labels_to_defaults(self, tab_data):
        tab_data["funding_info_label"].setText(self.trans["funding_info_label"])
        tab_data["price_label"].setText(self.trans["price_label"])
        tab_data["balance_label"].setText(self.trans["balance_label"])
        tab_data["leveraged_balance_label"].setText(self.trans["leveraged_balance_label"])
        tab_data["volume_label"].setText(self.trans["volume_label"])
        tab_data["volume_label"].setStyleSheet("color: black;")
        tab_data["ping_label"].setText(self.trans["ping_label"])
        tab_data["ping_label"].setStyleSheet("color: black;")

    def reset_tab_labels_to_error(self, tab_data):
        tab_data["funding_info_label"].setText(f"{self.trans['funding_info_label'].split(':')[0]}: Error | {self.trans['funding_info_label'].split('|')[1].strip()}: Error")
        tab_data["price_label"].setText(f"{self.trans['price_label'].split(':')[0]}: Error")
        tab_data["balance_label"].setText(f"{self.trans['balance_label'].split(':')[0]}: Error")
        tab_data["leveraged_balance_label"].setText(f"{self.trans['leveraged_balance_label'].split(':')[0]}: Error")
        tab_data["volume_label"].setText(f"{self.trans['volume_label'].split(':')[0]}: Error")
        tab_data["volume_label"].setStyleSheet("color: black;")
        tab_data["ping_label"].setText(f"{self.trans['ping_label'].split(':')[0]}: Error")
        tab_data["ping_label"].setStyleSheet("color: red;")

    def check_tab_funding_time(self, tab_data):
        if tab_data not in self.tab_data_list or not tab_data["funding_data"]: 
            self.reset_tab_labels_to_defaults(tab_data)
            return
        # Авто-сканування: перевіряємо чи час запускати пошук монет
        self.check_auto_scan_trigger(tab_data)
        symbol = tab_data["funding_data"]["symbol"]
        rate = tab_data["funding_data"]["funding_rate"]
        time_val = tab_data["funding_data"]["funding_time"]
        try:
            time_to_funding, time_str = get_next_funding_time(time_val, tab_data["funding_interval_hours"])
        except Exception as e:
            print(f"Error calculating funding time: {e}")
            return
        tab_data["funding_info_label"].setText(f"{self.trans['funding_info_label'].split(':')[0]}: {rate:.4f}% | {self.trans['funding_info_label'].split('|')[1].strip()}: {time_str}")

        if 0.5 <= time_to_funding <= 1.5 and tab_data["pre_funding_price"] is None:
            tab_data["pre_funding_price"] = get_current_price(tab_data["session"], symbol, tab_data["exchange"])

        if tab_data["entry_time_seconds"] - 1.0 <= time_to_funding <= tab_data["entry_time_seconds"] and not tab_data["open_order_id"]:
            side = ("Sell" if rate > 0 else "Buy") if tab_data["reverse_side"] else ("Buy" if rate > 0 else "Sell")
            tab_data["open_order_id"] = place_market_order(tab_data["session"], symbol, side, tab_data["qty"], tab_data["exchange"])
            if tab_data["open_order_id"]:
                QTimer.singleShot(int((time_to_funding - 0.5) * 1000), lambda: self.capture_tab_funding_price(tab_data, symbol, side))
            tab_data["pre_funding_price"] = None

        tab_data["update_count"] += 1
        if tab_data.get("position_open", False) and tab_data["update_count"] % 10 == 0:
            self.check_position_status(tab_data)

    def check_position_status(self, tab_data):
        try:
            symbol = tab_data["selected_symbol"]
            if tab_data["exchange"] == "Bybit":
                pos = tab_data["session"].get_positions(category="linear", symbol=symbol)
                if pos["retCode"] == 0:
                    position = next((p for p in pos["result"]["list"] if p["symbol"] == symbol and float(p["size"]) > 0), None)
            else:
                pos = tab_data["session"].get_position_information(symbol=symbol)
                position = next((p for p in pos if p["symbol"] == symbol and abs(float(p["positionAmt"])) > 0), None)
            if not position:
                tab_data["position_open"] = False
                self.update_stats_table()
        except Exception as e:
            print(f"Error checking position: {e}")

    def capture_tab_funding_price(self, tab_data, symbol, side):
        if tab_data not in self.tab_data_list: return
        entry_price = get_order_execution_price(tab_data["session"], symbol, tab_data["open_order_id"], tab_data["exchange"])
        if entry_price:
            tab_data["position_open"] = True
        candle_price = get_candle_open_price(tab_data["session"], symbol, tab_data["exchange"])
        pre_funding = tab_data["pre_funding_price"]
        prices = [p for p in [entry_price, candle_price, pre_funding] if p]
        if not prices:
            tab_data["open_order_id"] = None
            return

        avg_price = sum(prices) / len(prices)
        max_diff = 0.5
        deviations = [abs(p - avg_price) / avg_price * 100 for p in prices]
        if max(deviations) > max_diff:
            valid = [p for i, p in enumerate(prices) if deviations[i] <= max_diff]
            selected = sum(valid) / len(valid) if valid else candle_price or avg_price
            print(f"Price validation warning for {symbol}: Significant price discrepancy. Entry={entry_price or 0.0}, Candle={candle_price or 0.0}, Pre-funding={pre_funding or 0.0}. Using {selected}")
        else:
            selected = avg_price

        tab_data["funding_time_price"] = selected
        tick_size = get_symbol_info(tab_data["session"], symbol, tab_data["exchange"])
        target_limit = selected * (1 + tab_data["profit_percentage"] / 100 if side == "Buy" else 1 - tab_data["profit_percentage"] / 100)

        if tab_data["auto_limit"]:
            optimal = get_optimal_limit_price(tab_data["session"], symbol, side, selected, tab_data["exchange"], tab_data["profit_percentage"], tick_size)
            if optimal:
                actual_profit = abs((optimal - selected) / selected * 100)
                if abs(actual_profit - tab_data["profit_percentage"]) > 0.1:
                    limit_price = target_limit
                else:
                    limit_price = optimal
            else:
                limit_price = target_limit
        else:
            limit_price = target_limit

        if tick_size:
            decimal_places = abs(int(math.log10(tick_size)))
            limit_price = round(limit_price, decimal_places)
        tab_data["limit_price"] = limit_price
        place_limit_close_order(tab_data["session"], symbol, side, tab_data["qty"], limit_price, tick_size, tab_data["exchange"])
        tab_data["open_order_id"] = None

        if tab_data["stop_loss_enabled"] and tab_data["stop_loss_percentage"] > 0:
            stop_price = selected * (1 - tab_data["stop_loss_percentage"] / 100 if side == "Buy" else 1 + tab_data["stop_loss_percentage"] / 100)
            if tick_size:
                stop_price = round(stop_price, decimal_places)
            place_stop_loss_order(tab_data["session"], symbol, side, tab_data["qty"], stop_price, tick_size, tab_data["exchange"])

        QTimer.singleShot(1000, lambda: self.log_limit_price_diff(tab_data, symbol, side))

    def log_limit_price_diff(self, tab_data, symbol, side):
        if tab_data not in self.tab_data_list: return
        open_price = tab_data["funding_time_price"]
        limit = tab_data.get("limit_price")
        if open_price is None or limit is None: return
        profit = abs((limit - open_price) / open_price * 100)
        if abs(profit - tab_data["profit_percentage"]) > 0.5:
            QMessageBox.warning(self, self.trans["price_mismatch_warning_title"], self.trans["price_mismatch_warning_text"].format(
                symbol=symbol, actual_profit=profit, expected_profit=tab_data["profit_percentage"]
            ))

    def handle_tab_close_all_trades(self, tab_data):
        if tab_data not in self.tab_data_list: return
        msg = QMessageBox()
        msg.setWindowTitle(self.trans["close_all_trades_warning_title"])
        msg.setText(self.trans["close_all_trades_warning_text"])
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if self.language == "uk":
            msg.button(QMessageBox.StandardButton.Yes).setText("Так")
            msg.button(QMessageBox.StandardButton.No).setText("Ні")
        if msg.exec() == QMessageBox.StandardButton.Yes:
            success = close_all_positions(tab_data["session"], tab_data["exchange"], symbol=tab_data["selected_symbol"])
            result = QMessageBox()
            result.setWindowTitle("Success" if self.language == "en" else "Успіх" if success else "Error" if self.language == "en" else "Помилка")
            result.setText(self.trans["close_all_trades_success"] if success else self.trans["close_all_trades_error"].format("No positions found or API error"))
            result.exec()
            if success:
                tab_data["open_order_id"] = None
            self.update_tab_funding_data(tab_data)

    def close_tab(self, index):
        if self.tab_widget.count() <= 1: return
        tab_data = self.tab_data_list[index]
        tab_data["timer"].stop()
        tab_data["funding_refresh_timer"].stop()
        tab_data["ping_timer"].stop()
        self.tab_widget.removeTab(index)
        self.tab_data_list.pop(index)
        self.save_settings()

    def closeEvent(self, event):
        for td in self.tab_data_list:
            td["timer"].stop()
            td["funding_refresh_timer"].stop()
            td["ping_timer"].stop()
        self.save_settings()
        event.accept()