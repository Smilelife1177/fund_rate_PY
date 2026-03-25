"""
gui.py — головне вікно застосунку FundingTrader.

Залежності:
    settings_manager  — завантаження / збереження JSON-налаштувань
    stats_manager     — робота з CSV-статистикою угод
    auto_scanner      — сканування монет за фандинг-ставкою
    tab_data          — ініціалізація стану вкладки
    logic             — API-виклики до бірж
    translations      — словники перекладів
"""

import os
import math
import time
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLineEdit, QLabel, QDoubleSpinBox, QSlider,
    QComboBox, QCheckBox, QMessageBox, QTabWidget, QToolButton,
    QTabBar, QScrollArea, QTableWidget, QTableWidgetItem,
    QDialog, QDialogButtonBox, QTextEdit,
)
from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from logic import (
    get_account_balance, get_funding_data, get_current_price,
    get_next_funding_time, place_market_order, get_symbol_info,
    place_limit_close_order, update_ping, initialize_client,
    close_all_positions, get_optimal_limit_price, get_candle_open_price,
    place_stop_loss_order, get_order_execution_price,
)
from translations import translations
import settings_manager as sm
import stats_manager as stats
from auto_scanner import scan_funding_opportunities, format_funding_time
from tab_data import build_tab_data


# ---------------------------------------------------------------------------
# Головне вікно
# ---------------------------------------------------------------------------

class FundingTraderApp(QMainWindow):
    def __init__(self, session, testnet, exchange):
        super().__init__()
        self.settings_path = sm.SETTINGS_PATH
        self.language = sm.load_language(self.settings_path)
        self.trans = translations[self.language]

        self.setWindowTitle(self.trans["window_title"].format(exchange))
        self.setGeometry(100, 100, 1800, 1000)
        self._set_window_icon()

        # Центральний скролюємий віджет
        self.central_widget = QWidget()
        self.main_layout = QVBoxLayout(self.central_widget)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.central_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCentralWidget(scroll_area)

        self._init_language_selection()
        self._init_tab_widget()

        self.tab_data_list: list[dict] = []
        self.tab_count = 0

        # Додати поля для глобального авто-сканера
        self._auto_scan_results: list = []
        self._auto_scan_near_now: list = []
        self._auto_scan_done_this_minute: bool = False

        # Один глобальний таймер сканування
        self._global_scan_timer = QTimer()
        self._global_scan_timer.timeout.connect(self._global_auto_scan_tick)
        self._global_scan_timer.start(1000)

        loaded = sm.load_settings(self.settings_path)
        initial = loaded[0] if loaded else {}
        self.add_new_tab(session=session, testnet=testnet, exchange=exchange, settings=initial)

        self._init_stats_tab()
        stats.initialize_stats_csv()
        self._update_stats_table()

        self.main_layout.addWidget(self.language_label)
        self.main_layout.addWidget(self.language_combobox)
        self.main_layout.addWidget(self.tab_widget)
        self._save()

    # ------------------------------------------------------------------ #
    #  Ініціалізація вікна                                                #
    # ------------------------------------------------------------------ #

    def _set_window_icon(self):
        path = r"images\log.ico"
        if os.path.exists(path):
            self.setWindowIcon(QIcon(path))
        else:
            print(f"Icon not found: {path}")

    def _init_language_selection(self):
        self.language_label = QLabel(self.trans["language_label"])
        self.language_combobox = QComboBox()
        self.language_combobox.addItems(["English", "Українська"])
        self.language_combobox.setCurrentText("English" if self.language == "en" else "Українська")
        self.language_combobox.currentTextChanged.connect(self._on_language_changed)

    def _init_tab_widget(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setFixedWidth(30)
        add_btn.setStyleSheet("font-weight: bold; font-size: 16px;")
        add_btn.clicked.connect(self.add_new_tab)
        self.add_tab_button = add_btn

        self.tab_widget.addTab(QWidget(), "+")
        last = self.tab_widget.count() - 1
        self.tab_widget.setTabEnabled(last, False)
        self.tab_widget.tabBar().setTabButton(last, QTabBar.ButtonPosition.RightSide, add_btn)

    # ------------------------------------------------------------------ #
    #  Вкладка статистики                                                 #
    # ------------------------------------------------------------------ #

    def _init_stats_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.stats_table = QTableWidget()
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.stats_table)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton(self.trans["refresh_button"])
        refresh_btn.clicked.connect(self._update_stats_table)
        btn_row.addWidget(refresh_btn)

        add_btn = QPushButton("Додати угоду вручну")
        add_btn.clicked.connect(self._open_stats_input_dialog)
        btn_row.addWidget(add_btn)

        layout.addLayout(btn_row)

        idx = self.tab_widget.addTab(tab, "Statistics" if self.language == "en" else "Статистика")
        self.tab_widget.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)
        self.tab_widget.tabBar().setTabButton(idx, QTabBar.ButtonPosition.LeftSide, None)

    def _update_stats_table(self):
        rows = stats.read_stats_csv()
        if not rows:
            self.stats_table.clear()
            return
        headers, data_rows = rows[0], rows[1:]
        self.stats_table.setColumnCount(len(headers))
        self.stats_table.setHorizontalHeaderLabels(headers)
        self.stats_table.setRowCount(len(data_rows))
        for r, row in enumerate(data_rows):
            for c, val in enumerate(row):
                self.stats_table.setItem(r, c, QTableWidgetItem(val))
        self.stats_table.resizeColumnsToContents()

    def _open_stats_input_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Запис нової угоди")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(
            "Введіть дані у форматі:\nПроцент Фандинг Прибиль Доход Комисия Обєм В-сделке Тикер"
        ))
        hint = QLabel("Приклад:\n2,43% -2,77 0,39 3,37 0,21 137 11с MYXUSDT")
        hint.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(hint)

        text_edit = QTextEdit()
        text_edit.setAcceptRichText(False)
        text_edit.setPlaceholderText("Вставте сюди дані...")
        text_edit.setFixedHeight(80)
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        raw = text_edit.toPlainText().strip()
        if not raw:
            return

        values = stats.parse_stats_input(raw)
        if values is None:
            QMessageBox.warning(self, "Помилка введення", "Очікується 8 значень. Перевірте формат.")
            return

        stats.initialize_stats_csv()
        stats.write_stats_row(values)
        QMessageBox.information(self, "Успіх", "Дані успішно записано в trade_stats.csv")
        self._update_stats_table()

    # ------------------------------------------------------------------ #
    #  Вкладки з торговими налаштуваннями                                 #
    # ------------------------------------------------------------------ #

    def add_new_tab(self, session=None, testnet=None, exchange=None, settings=None):
        self.tab_count += 1
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_data = build_tab_data(settings or {}, session, testnet, exchange)
        self._create_tab_ui(tab_layout, tab_data)
        self.tab_data_list.append(tab_data)
        self.tab_widget.insertTab(
            self.tab_widget.count() - 1, tab,
            self.trans["tab_title"].format(self.tab_count),
        )
        self.tab_widget.setCurrentWidget(tab)
        tab_data["tab_index"] = self.tab_count
        self._init_tab_timers(tab_data)
        self._update_tab_funding_data(tab_data)
        return tab_data

    # ---- Компоновка UI вкладки ---------------------------------------- #

    def _create_tab_ui(self, layout, tab_data):
        # Ліва колонка — налаштування
        left = QWidget()
        left.setFixedWidth(320)
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        self._add_exchange_ui(left_l, tab_data)
        self._add_testnet_ui(left_l, tab_data)
        self._add_coin_ui(left_l, tab_data)
        self._add_funding_interval_ui(left_l, tab_data)
        self._add_entry_time_ui(left_l, tab_data)
        self._add_qty_ui(left_l, tab_data)
        self._add_profit_percentage_ui(left_l, tab_data)
        self._add_auto_limit_ui(left_l, tab_data)
        self._add_leverage_ui(left_l, tab_data)
        self._add_stop_loss_ui(left_l, tab_data)
        self._add_reverse_side_ui(left_l, tab_data)
        self._add_info_labels(left_l, tab_data)
        self._add_action_buttons(left_l, tab_data)
        left_l.addStretch()

        # Центральна колонка — WebView Bybit
        center = QWidget()
        center.setFixedWidth(600)
        center_l = QVBoxLayout(center)
        center_l.setContentsMargins(4, 0, 4, 0)
        self._add_funding_web_view(center_l, tab_data)

        # Права колонка — авто-сканування
        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(8, 4, 4, 4)
        self._add_auto_scan_ui(right_l, tab_data)
        tab_data["future_panel"] = right

        hbox = QHBoxLayout()
        hbox.setSpacing(8)
        hbox.addWidget(left)
        hbox.addWidget(center)
        hbox.addWidget(right, 1)
        layout.addLayout(hbox)

    # ---- Ліва панель: окремі UI-блоки --------------------------------- #

    def _add_exchange_ui(self, layout, tab_data):
        label = QLabel(self.trans["exchange_label"])
        combo = QComboBox()
        combo.addItems(["Bybit", "Binance"])
        combo.setCurrentText(tab_data["exchange"])
        combo.currentTextChanged.connect(lambda v: self._on_exchange_changed(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(combo)
        tab_data["exchange_label"] = label
        tab_data["exchange_combobox"] = combo

    def _add_testnet_ui(self, layout, tab_data):
        label = QLabel(self.trans["testnet_label"])
        cb = QCheckBox(self.trans["testnet_checkbox"])
        cb.setChecked(tab_data["testnet"])
        cb.stateChanged.connect(lambda s: self._on_testnet_changed(tab_data, s))
        layout.addWidget(label)
        layout.addWidget(cb)
        tab_data["testnet_label"] = label
        tab_data["testnet_checkbox"] = cb

    def _add_coin_ui(self, layout, tab_data):
        label = QLabel(self.trans["coin_input_label"])
        field = QLineEdit(tab_data["selected_symbol"])
        btn = QPushButton(self.trans["update_coin_button"])
        btn.clicked.connect(lambda: self._on_symbol_changed(tab_data, field.text()))
        layout.addWidget(label)
        layout.addWidget(field)
        layout.addWidget(btn)
        tab_data["coin_input_label"] = label
        tab_data["coin_input"] = field
        tab_data["update_coin_button"] = btn

    def _add_funding_interval_ui(self, layout, tab_data):
        label = QLabel(self.trans["funding_interval_label"])
        combo = QComboBox()
        intervals = ["0.01", "1", "4", "8"] if tab_data["exchange"] == "Bybit" else ["8"]
        combo.addItems(intervals)
        formatted = str(float(tab_data["funding_interval_hours"])).rstrip(".0")
        combo.setCurrentText(formatted)
        combo.currentTextChanged.connect(lambda v: self._on_funding_interval_changed(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(combo)
        tab_data["funding_interval_label"] = label
        tab_data["funding_interval_combobox"] = combo

    def _add_entry_time_ui(self, layout, tab_data):
        label = QLabel(self.trans["entry_time_label"])
        spin = QDoubleSpinBox()
        spin.setRange(0.5, 60.0)
        spin.setValue(tab_data["entry_time_seconds"])
        spin.setSingleStep(0.1)
        spin.valueChanged.connect(lambda v: self._on_entry_time_changed(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(spin)
        tab_data["entry_time_label"] = label
        tab_data["entry_time_spinbox"] = spin

    def _add_qty_ui(self, layout, tab_data):
        label = QLabel(self.trans["qty_label"])
        spin = QDoubleSpinBox()
        spin.setRange(0.001, 1_000_000.0)
        spin.setValue(tab_data["qty"])
        spin.setSingleStep(0.001)
        spin.valueChanged.connect(lambda v: self._on_qty_changed(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(spin)
        tab_data["qty_label"] = label
        tab_data["qty_spinbox"] = spin

    def _add_profit_percentage_ui(self, layout, tab_data):
        label = QLabel(self.trans["profit_percentage_label"])
        spin = QDoubleSpinBox()
        spin.setRange(0.1, 10.0)
        spin.setValue(tab_data["profit_percentage"])
        spin.setSingleStep(0.1)
        spin.valueChanged.connect(lambda v: self._on_profit_pct_changed(tab_data, v))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(10, 1000)
        slider.setValue(int(tab_data["profit_percentage"] * 100))
        slider.setSingleStep(10)
        slider.valueChanged.connect(lambda v: self._on_profit_slider_changed(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(spin)
        layout.addWidget(slider)
        tab_data["profit_percentage_label"] = label
        tab_data["profit_percentage_spinbox"] = spin
        tab_data["profit_percentage_slider"] = slider

    def _add_auto_limit_ui(self, layout, tab_data):
        label = QLabel(self.trans["auto_limit_label"])
        cb = QCheckBox(self.trans["auto_limit_checkbox"])
        cb.setChecked(tab_data["auto_limit"])
        cb.stateChanged.connect(lambda s: self._on_auto_limit_changed(tab_data, s))
        layout.addWidget(label)
        layout.addWidget(cb)
        tab_data["auto_limit_label"] = label
        tab_data["auto_limit_checkbox"] = cb

    def _add_leverage_ui(self, layout, tab_data):
        label = QLabel(self.trans["leverage_label"])
        spin = QDoubleSpinBox()
        spin.setRange(1.0, 100.0)
        spin.setValue(tab_data["leverage"])
        spin.setSingleStep(0.1)
        spin.valueChanged.connect(lambda v: self._on_leverage_changed(tab_data, v))
        layout.addWidget(label)
        layout.addWidget(spin)
        tab_data["leverage_label"] = label
        tab_data["leverage_spinbox"] = spin

    def _add_stop_loss_ui(self, layout, tab_data):
        en_label = QLabel(self.trans["stop_loss_enabled_label"])
        en_cb = QCheckBox(self.trans["stop_loss_enabled_checkbox"])
        en_cb.setChecked(tab_data["stop_loss_enabled"])
        en_cb.stateChanged.connect(lambda s: self._on_stop_loss_enabled_changed(tab_data, s))
        pct_label = QLabel(self.trans["stop_loss_percentage_label"])
        pct_spin = QDoubleSpinBox()
        pct_spin.setRange(0.1, 10.0)
        pct_spin.setValue(tab_data["stop_loss_percentage"])
        pct_spin.setSingleStep(0.1)
        pct_spin.valueChanged.connect(lambda v: self._on_stop_loss_pct_changed(tab_data, v))
        layout.addWidget(en_label)
        layout.addWidget(en_cb)
        layout.addWidget(pct_label)
        layout.addWidget(pct_spin)
        tab_data["stop_loss_enabled_label"] = en_label
        tab_data["stop_loss_enabled_checkbox"] = en_cb
        tab_data["stop_loss_percentage_label"] = pct_label
        tab_data["stop_loss_percentage_spinbox"] = pct_spin

    def _add_reverse_side_ui(self, layout, tab_data):
        label = QLabel(self.trans["reverse_side_label"])
        cb = QCheckBox(self.trans["reverse_side_checkbox"])
        cb.setChecked(tab_data["reverse_side"])
        cb.stateChanged.connect(lambda s: self._on_reverse_side_changed(tab_data, s))
        layout.addWidget(label)
        layout.addWidget(cb)
        tab_data["reverse_side_label"] = label
        tab_data["reverse_side_checkbox"] = cb

    def _add_info_labels(self, layout, tab_data):
        fields = {
            "funding_info_label": self.trans["funding_info_label"],
            "price_label":        self.trans["price_label"],
            "balance_label":      self.trans["balance_label"],
            "leveraged_balance_label": self.trans["leveraged_balance_label"],
            "volume_label":       self.trans["volume_label"],
            "ping_label":         self.trans["ping_label"],
        }
        for key, text in fields.items():
            lbl = QLabel(text)
            layout.addWidget(lbl)
            tab_data[key] = lbl

    def _add_action_buttons(self, layout, tab_data):
        refresh = QPushButton(self.trans["refresh_button"])
        refresh.clicked.connect(lambda: self._update_tab_funding_data(tab_data))
        close_all = QPushButton(self.trans["close_all_trades_button"])
        close_all.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        close_all.clicked.connect(lambda: self._handle_close_all_trades(tab_data))
        layout.addWidget(refresh)
        layout.addWidget(close_all)
        tab_data["refresh_button"] = refresh
        tab_data["close_all_trades_button"] = close_all

    # ---- WebView ------------------------------------------------------- #

    def _add_funding_web_view(self, layout, tab_data):
        profile = QWebEngineProfile(f"BybitProfile_{self.tab_count}", self)
        cache_path = os.path.join(os.getcwd(), "webcache", f"tab_{self.tab_count}")
        os.makedirs(cache_path, exist_ok=True)
        profile.setCachePath(cache_path)
        profile.setPersistentStoragePath(cache_path)
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        view = QWebEngineView()
        view.setPage(QWebEnginePage(profile, view))
        view.setMinimumHeight(150)
        tab_data["funding_web_view"] = view
        tab_data["web_profile"] = profile
        layout.addWidget(view)
        self._refresh_web_view(tab_data)

    def _refresh_web_view(self, tab_data):
        if tab_data not in self.tab_data_list:
            return
        symbol = tab_data["selected_symbol"]
        if tab_data["exchange"] == "Bybit":
            tab_data["funding_web_view"].setUrl(QUrl(f"https://www.bybit.com/trade/usdt/{symbol}"))
            tab_data["funding_web_view"].setVisible(True)
        else:
            tab_data["funding_web_view"].setVisible(False)

    # ---- Авто-сканування UI ------------------------------------------- #

    def _global_auto_scan_tick(self):
        """Один глобальний тік — замість N тіків по вкладках."""
        now = datetime.now(timezone.utc)
        secs_into_hour = now.minute * 60 + now.second
        secs_left = 3600 - secs_into_hour

        if secs_left > 60:
            self._auto_scan_done_this_minute = False
            return

        if self._auto_scan_done_this_minute:
            return

        # Перевіряємо, чи є хоча б одна вкладка з auto_mode=True
        auto_tabs = [td for td in self.tab_data_list if td.get("auto_mode")]
        if not auto_tabs:
            return

        self._auto_scan_done_this_minute = True

        # Один спільний скан для всіх
        threshold = min(td.get("auto_min_funding", 0.05) for td in auto_tabs)
        try:
            all_above, near_now = scan_funding_opportunities(threshold)
            self._auto_scan_results = all_above
            self._auto_scan_near_now = near_now
        except Exception as e:
            print(f"Global auto scan error: {e}")
            return

        # Роздаємо результати кожній вкладці з auto_mode=True
        used_symbols = set()
        # for td in auto_tabs:
        #     self._apply_scan_result_to_tab(td, all_above, near_now, used_symbols)
        # СТАЛО:
        self._spawn_tabs_from_scan(near_now)

        # Оновити статус у всіх авто-вкладках
        for td in auto_tabs:
            td["auto_scan_results"] = all_above
            self._update_auto_scan_table(td)
            if near_now:
                td["auto_status_label"].setText(
                    self.trans["auto_status_found"].format(n=len(all_above), symbol=near_now[0]["symbol"])
                )
            elif all_above:
                td["auto_status_label"].setText(
                    self.trans["auto_status_watching"].format(n=len(all_above))
                )
            else:
                td["auto_status_label"].setText(self.trans["auto_status_none"])
    #

    def _spawn_tabs_from_scan(self, near_now: list):
        """Створює нові вкладки під кожну знайдену монету (якщо вкладки ще немає)."""
        # Збираємо символи що вже відкриті
        existing_symbols = {td["selected_symbol"] for td in self.tab_data_list}
        created = 0
        MAX_AUTO_TABS = 5

        for coin in near_now:
            if created >= MAX_AUTO_TABS:
                break
            symbol = coin["symbol"]
            if symbol in existing_symbols:
                continue  # вкладка вже є — не дублюємо

            # Беремо налаштування з першої вкладки як шаблон
            template = self.tab_data_list[0] if self.tab_data_list else {}
            new_settings = {
                "exchange":               template.get("exchange", "Bybit"),
                "testnet":                template.get("testnet", False),
                "selected_symbol":        symbol,
                "funding_interval_hours": template.get("funding_interval_hours", 8),
                "entry_time_seconds":     template.get("entry_time_seconds", 5),
                "qty":                    template.get("qty", 1.0),
                "profit_percentage":      template.get("profit_percentage", 1.0),
                "auto_limit":             template.get("auto_limit", False),
                "leverage":               template.get("leverage", 1.0),
                "stop_loss_percentage":   template.get("stop_loss_percentage", 1.0),
                "stop_loss_enabled":      template.get("stop_loss_enabled", False),
                "reverse_side":           template.get("reverse_side", False),
                "auto_mode":              False,  # нові вкладки — ручний режим
                "auto_min_funding":       template.get("auto_min_funding", 0.05),
            }

            session = template.get("session") if template else None
            testnet = new_settings["testnet"]
            exchange = new_settings["exchange"]

            new_td = self.add_new_tab(
                session=session,
                testnet=testnet,
                exchange=exchange,
                settings=new_settings,
            )
            # Явно виставляємо символ після створення вкладки
            new_td["selected_symbol"] = symbol
            new_td["coin_input"].setText(symbol)
            self._refresh_web_view(new_td)
            self.tab_widget.setTabText(self.tab_data_list.index(new_td), symbol)

            existing_symbols.add(symbol)
            created += 1


    def _add_auto_scan_ui(self, layout, tab_data):
        t = self.trans

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
        mode_combo.currentIndexChanged.connect(
            lambda i: (self._set_auto_mode(tab_data, i == 1), self._save())
        )
        mode_row.addWidget(mode_label)
        mode_row.addWidget(mode_combo)
        layout.addLayout(mode_row)
        tab_data["auto_mode_combo"] = mode_combo
        tab_data["auto_mode_label_widget"] = mode_label

        # Мінімальний поріг
        thr_row = QHBoxLayout()
        thr_label = QLabel(t["auto_min_funding_label"])
        thr_spin = QDoubleSpinBox()
        thr_spin.setRange(0.001, 5.0)
        thr_spin.setSingleStep(0.005)
        thr_spin.setDecimals(3)
        thr_spin.setValue(tab_data.get("auto_min_funding", 0.05))
        thr_spin.valueChanged.connect(
            lambda v: (tab_data.update({"auto_min_funding": v}), self._save())
        )
        thr_row.addWidget(thr_label)
        thr_row.addWidget(thr_spin)
        layout.addLayout(thr_row)
        tab_data["auto_threshold_spin"] = thr_spin
        tab_data["auto_threshold_label"] = thr_label

        status_label = QLabel(t["auto_status_disabled"])
        status_label.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(status_label)
        tab_data["auto_status_label"] = status_label

        chosen_label = QLabel(t["auto_chosen_none"])
        chosen_label.setStyleSheet("font-weight: bold; color: #1a6e1a;")
        layout.addWidget(chosen_label)
        tab_data["auto_chosen_label"] = chosen_label

        results_label = QLabel(t["auto_results_label"])
        layout.addWidget(results_label)
        tab_data["auto_results_label"] = results_label

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels([
            t["auto_col_symbol"], t["auto_col_rate"],
            t["auto_col_time"], t["auto_col_select"],
        ])
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, table.horizontalHeader().ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setMinimumHeight(300)
        layout.addWidget(table)
        tab_data["auto_scan_table"] = table

        scan_btn = QPushButton(t["auto_scan_now_btn"])
        scan_btn.clicked.connect(lambda: self._run_auto_scan(tab_data))
        layout.addWidget(scan_btn)
        tab_data["auto_scan_btn"] = scan_btn
#

        # ── Налаштування авто-розрахунку ──────────────────────────────
        calc_group_label = QLabel("── Авто-розрахунок ──")
        calc_group_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(calc_group_label)

        # Profit addon
        profit_addon_row = QHBoxLayout()
        profit_addon_label = QLabel("+% до фандингу:")
        profit_addon_spin = QDoubleSpinBox()
        profit_addon_spin.setRange(0.0, 5.0)
        profit_addon_spin.setSingleStep(0.05)
        profit_addon_spin.setDecimals(2)
        profit_addon_spin.setValue(tab_data.get("auto_profit_addon", 0.3))
        profit_addon_spin.valueChanged.connect(
            lambda v: (tab_data.update({"auto_profit_addon": v}), self._save())
        )
        profit_addon_row.addWidget(profit_addon_label)
        profit_addon_row.addWidget(profit_addon_spin)
        layout.addLayout(profit_addon_row)
        tab_data["auto_profit_addon_spin"] = profit_addon_spin

        # Balance %
        balance_pct_row = QHBoxLayout()
        balance_pct_label = QLabel("% від балансу:")
        balance_pct_spin = QDoubleSpinBox()
        balance_pct_spin.setRange(1.0, 100.0)
        balance_pct_spin.setSingleStep(5.0)
        balance_pct_spin.setDecimals(1)
        balance_pct_spin.setValue(tab_data.get("auto_balance_pct", 30.0))
        balance_pct_spin.valueChanged.connect(
            lambda v: (tab_data.update({"auto_balance_pct": v}), self._save())
        )
        balance_pct_row.addWidget(balance_pct_label)
        balance_pct_row.addWidget(balance_pct_spin)
        layout.addLayout(balance_pct_row)
        tab_data["auto_balance_pct_spin"] = balance_pct_spin

        # Leverage для розрахунку qty
        leverage_calc_row = QHBoxLayout()
        leverage_calc_label = QLabel("Плече для qty:")
        leverage_calc_spin = QDoubleSpinBox()
        leverage_calc_spin.setRange(1.0, 100.0)
        leverage_calc_spin.setSingleStep(1.0)
        leverage_calc_spin.setDecimals(1)
        leverage_calc_spin.setValue(tab_data.get("auto_leverage_calc", 10.0))
        leverage_calc_spin.valueChanged.connect(
            lambda v: (tab_data.update({"auto_leverage_calc": v}), self._save())
        )
        leverage_calc_row.addWidget(leverage_calc_label)
        leverage_calc_row.addWidget(leverage_calc_spin)
        layout.addLayout(leverage_calc_row)
        tab_data["auto_leverage_calc_spin"] = leverage_calc_spin

#
        layout.addStretch()

    def _set_auto_mode(self, tab_data, enabled: bool):
        tab_data["auto_mode"] = enabled
        tab_data["auto_scan_done_this_minute"] = False
        t = self.trans
        if enabled:
            tab_data["auto_status_label"].setText(t["auto_status_waiting"])
            tab_data["auto_status_label"].setStyleSheet("color: #1a6e1a; font-style: italic;")
        else:
            tab_data["auto_status_label"].setText(t["auto_status_disabled"])
            tab_data["auto_status_label"].setStyleSheet("color: #555; font-style: italic;")
        self._update_auto_scan_table(tab_data)

    def _run_auto_scan(self, tab_data):
        try:
            threshold = tab_data.get("auto_min_funding", 0.05)
            all_above, near_now = scan_funding_opportunities(threshold)

            tab_data["auto_scan_results"] = all_above
            self._update_auto_scan_table(tab_data)

            t = self.trans
            best = near_now[0] if near_now else (all_above[0] if all_above else None)

            if best:
                symbol = best["symbol"]
                tab_data["auto_selected_symbol"] = symbol
                tab_data["selected_symbol"] = symbol
                tab_data["coin_input"].setText(symbol)
                self._refresh_web_view(tab_data)
                self.tab_widget.setTabText(self.tab_data_list.index(tab_data), symbol)

                # ── Розрахунок profit percentage ──────────────────────────────
                funding_rate = abs(best["rate"])
                profit_addon = tab_data.get("auto_profit_addon", 0.3)
                calculated_profit = round(funding_rate + profit_addon, 4)
                # calculated_profit = round(funding_rate + 0.3, 4)
                tab_data["profit_percentage"] = calculated_profit
                tab_data["profit_percentage_spinbox"].setValue(calculated_profit)
                tab_data["profit_percentage_slider"].setValue(int(calculated_profit * 100))

                # ── Розрахунок qty ────────────────────────────────────────────
                try:
                    balance = get_account_balance(tab_data["session"], tab_data["exchange"])
                    price   = get_current_price(tab_data["session"], symbol, tab_data["exchange"])
                    if balance and price and price > 0:
                        balance_pct    = tab_data.get("auto_balance_pct", 30.0) / 100
                        leverage_calc  = tab_data.get("auto_leverage_calc", 10.0)
                        usdt_to_use    = balance * balance_pct
                        leveraged      = usdt_to_use * leverage_calc
                        # usdt_to_use = balance * 0.30
                        # leveraged   = usdt_to_use * 10
                        qty         = round(leveraged / price, 3)
                        tab_data["qty"] = qty
                        tab_data["qty_spinbox"].setValue(qty)
                except Exception as e:
                    print(f"Qty calc error: {e}")

                self._save()
                self._update_tab_funding_data(tab_data)

                tab_data["auto_chosen_label"].setText(
                    t["auto_chosen_selected"].format(symbol=symbol, rate=best["rate"])
                )
                tab_data["auto_chosen_label"].setStyleSheet("font-weight: bold; color: #1a6e1a;")
                tab_data["auto_status_label"].setText(
                    t["auto_status_found"].format(n=len(all_above), symbol=symbol)
                )
                tab_data["auto_status_label"].setStyleSheet("color: #1a6e1a; font-weight: bold;")
            else:
                tab_data["auto_chosen_label"].setText(t["auto_chosen_not_found"])
                tab_data["auto_chosen_label"].setStyleSheet("font-weight: bold; color: #b00;")
                tab_data["auto_status_label"].setText(t["auto_status_none"])
                tab_data["auto_status_label"].setStyleSheet("color: #b00; font-style: italic;")

        except Exception as e:
            print(f"Auto scan error: {e}")
            tab_data["auto_status_label"].setText(self.trans["auto_error"].format(e=e))
            tab_data["auto_status_label"].setStyleSheet("color: red;")

    def _update_auto_scan_table(self, tab_data):
        results = tab_data.get("auto_scan_results", [])
        table = tab_data.get("auto_scan_table")
        if table is None:
            return
        is_manual = not tab_data.get("auto_mode", False)
        table.setRowCount(len(results))
        for row, item in enumerate(results):
            sym_item = QTableWidgetItem(item["symbol"])
            rate_item = QTableWidgetItem(f"{item['rate']:+.4f}%")
            time_item = QTableWidgetItem(format_funding_time(item["secs"], self.language))

            if item["symbol"] == tab_data.get("auto_selected_symbol"):
                for cell in (sym_item, rate_item, time_item):
                    cell.setBackground(Qt.GlobalColor.green)

            rate_item.setForeground(
                Qt.GlobalColor.darkGreen if item["rate"] > 0 else Qt.GlobalColor.darkRed
            )
            table.setItem(row, 0, sym_item)
            table.setItem(row, 1, rate_item)
            table.setItem(row, 2, time_item)

            if is_manual:
                symbol = item["symbol"]
                btn = QPushButton(self.trans["auto_col_select"])
                btn.setFixedHeight(22)
                btn.clicked.connect(lambda _, s=symbol: self._on_symbol_changed(tab_data, s))
                table.setCellWidget(row, 3, btn)
            else:
                table.setCellWidget(row, 3, None)

        table.resizeColumnsToContents()
        table.setColumnWidth(3, 80)

    def _check_auto_scan_trigger(self, tab_data):
        if not tab_data.get("auto_mode"):
            return
        now = datetime.now(timezone.utc)
        secs_into_hour = now.minute * 60 + now.second
        secs_left = 3600 - secs_into_hour
        t = self.trans
        if secs_left > 60:
            mins = (secs_left - 60) // 60
            secs = (secs_left - 60) % 60
            tab_data["auto_status_label"].setText(t["auto_status_countdown"].format(mins=mins, secs=secs))
            tab_data["auto_status_label"].setStyleSheet("color: #555; font-style: italic;")
            tab_data["auto_scan_done_this_minute"] = False
        elif not tab_data.get("auto_scan_done_this_minute"):
            tab_data["auto_status_label"].setText(t["auto_status_scanning"])
            tab_data["auto_status_label"].setStyleSheet("color: #e07b00; font-weight: bold;")
            tab_data["auto_scan_done_this_minute"] = True
            self._run_auto_scan(tab_data)

    # ------------------------------------------------------------------ #
    #  Таймери                                                            #
    # ------------------------------------------------------------------ #

    def _init_tab_timers(self, tab_data):
        timer = QTimer()
        timer.timeout.connect(lambda: self._check_funding_time(tab_data))
        timer.start(1000)

        refresh_timer = QTimer()
        refresh_timer.timeout.connect(lambda: self._update_tab_funding_data(tab_data))
        refresh_timer.start(5 * 60 * 1000)

        ping_timer = QTimer()
        ping_timer.timeout.connect(lambda: self._update_ping(tab_data))
        ping_timer.start(30_000)

        tab_data["timer"] = timer
        tab_data["funding_refresh_timer"] = refresh_timer
        tab_data["ping_timer"] = ping_timer

    # ------------------------------------------------------------------ #
    #  Торгова логіка                                                     #
    # ------------------------------------------------------------------ #

    def _check_funding_time(self, tab_data):
        if tab_data not in self.tab_data_list or not tab_data["funding_data"]:
            self._reset_tab_labels(tab_data)
            return
        # self._check_auto_scan_trigger(tab_data)

        symbol = tab_data["funding_data"]["symbol"]
        rate   = tab_data["funding_data"]["funding_rate"]
        time_val = tab_data["funding_data"]["funding_time"]

        try:
            time_to_funding, time_str = get_next_funding_time(time_val, tab_data["funding_interval_hours"])
        except Exception as e:
            print(f"Error calculating funding time: {e}")
            return

        tab_data["funding_info_label"].setText(
            f"{self.trans['funding_info_label'].split(':')[0]}: {rate:.4f}% | "
            f"{self.trans['funding_info_label'].split('|')[1].strip()}: {time_str}"
        )

        if 0.5 <= time_to_funding <= 1.5 and tab_data["pre_funding_price"] is None:
            tab_data["pre_funding_price"] = get_current_price(
                tab_data["session"], symbol, tab_data["exchange"]
            )

        entry_window = tab_data["entry_time_seconds"]
        if entry_window - 1.0 <= time_to_funding <= entry_window and not tab_data["open_order_id"]:
            side = (
                ("Sell" if rate > 0 else "Buy") if tab_data["reverse_side"]
                else ("Buy" if rate > 0 else "Sell")
            )
            tab_data["open_order_id"] = place_market_order(
                tab_data["session"], symbol, side, tab_data["qty"], tab_data["exchange"]
            )
            if tab_data["open_order_id"]:
                delay_ms = int((time_to_funding - 0.5) * 1000)
                QTimer.singleShot(delay_ms, lambda: self._capture_funding_price(tab_data, symbol, side))
            tab_data["pre_funding_price"] = None

        tab_data["update_count"] += 1
        if tab_data.get("position_open") and tab_data["update_count"] % 10 == 0:
            self._check_position_status(tab_data)

    def _check_position_status(self, tab_data):
        try:
            symbol = tab_data["selected_symbol"]
            if tab_data["exchange"] == "Bybit":
                pos = tab_data["session"].get_positions(category="linear", symbol=symbol)
                if pos["retCode"] == 0:
                    position = next(
                        (p for p in pos["result"]["list"]
                         if p["symbol"] == symbol and float(p["size"]) > 0),
                        None,
                    )
            else:
                pos = tab_data["session"].get_position_information(symbol=symbol)
                position = next(
                    (p for p in pos if p["symbol"] == symbol and abs(float(p["positionAmt"])) > 0),
                    None,
                )
            if not position:
                tab_data["position_open"] = False
                self._update_stats_table()
        except Exception as e:
            print(f"Error checking position: {e}")

    def _capture_funding_price(self, tab_data, symbol, side):
        if tab_data not in self.tab_data_list:
            return
        entry_price  = get_order_execution_price(tab_data["session"], symbol, tab_data["open_order_id"], tab_data["exchange"])
        candle_price = get_candle_open_price(tab_data["session"], symbol, tab_data["exchange"])
        pre_funding  = tab_data["pre_funding_price"]

        if entry_price:
            tab_data["position_open"] = True

        prices = [p for p in [entry_price, candle_price, pre_funding] if p]
        if not prices:
            tab_data["open_order_id"] = None
            return

        avg = sum(prices) / len(prices)
        deviations = [abs(p - avg) / avg * 100 for p in prices]
        if max(deviations) > 0.5:
            valid = [p for i, p in enumerate(prices) if deviations[i] <= 0.5]
            selected = sum(valid) / len(valid) if valid else candle_price or avg
            print(
                f"Price validation warning {symbol}: entry={entry_price}, "
                f"candle={candle_price}, pre={pre_funding}. Using {selected}"
            )
        else:
            selected = avg

        tab_data["funding_time_price"] = selected
        tick_size = get_symbol_info(tab_data["session"], symbol, tab_data["exchange"])
        target = selected * (
            1 + tab_data["profit_percentage"] / 100 if side == "Buy"
            else 1 - tab_data["profit_percentage"] / 100
        )

        if tab_data["auto_limit"]:
            optimal = get_optimal_limit_price(
                tab_data["session"], symbol, side, selected,
                tab_data["exchange"], tab_data["profit_percentage"], tick_size,
            )
            if optimal:
                actual_profit = abs((optimal - selected) / selected * 100)
                limit_price = optimal if abs(actual_profit - tab_data["profit_percentage"]) <= 0.1 else target
            else:
                limit_price = target
        else:
            limit_price = target

        decimal_places = 0
        if tick_size:
            decimal_places = abs(int(math.log10(tick_size)))
            limit_price = round(limit_price, decimal_places)

        tab_data["limit_price"] = limit_price
        place_limit_close_order(
            tab_data["session"], symbol, side, tab_data["qty"], limit_price, tick_size, tab_data["exchange"]
        )
        tab_data["open_order_id"] = None

        if tab_data["stop_loss_enabled"] and tab_data["stop_loss_percentage"] > 0:
            stop_price = selected * (
                1 - tab_data["stop_loss_percentage"] / 100 if side == "Buy"
                else 1 + tab_data["stop_loss_percentage"] / 100
            )
            if tick_size:
                stop_price = round(stop_price, decimal_places)
            place_stop_loss_order(
                tab_data["session"], symbol, side, tab_data["qty"], stop_price, tick_size, tab_data["exchange"]
            )

        QTimer.singleShot(1000, lambda: self._log_limit_price_diff(tab_data, symbol))

    def _log_limit_price_diff(self, tab_data, symbol):
        if tab_data not in self.tab_data_list:
            return
        open_price = tab_data["funding_time_price"]
        limit = tab_data.get("limit_price")
        if open_price is None or limit is None:
            return
        profit = abs((limit - open_price) / open_price * 100)
        if abs(profit - tab_data["profit_percentage"]) > 0.5:
            QMessageBox.warning(
                self,
                self.trans["price_mismatch_warning_title"],
                self.trans["price_mismatch_warning_text"].format(
                    symbol=symbol,
                    actual_profit=profit,
                    expected_profit=tab_data["profit_percentage"],
                ),
            )

    def _handle_close_all_trades(self, tab_data):
        if tab_data not in self.tab_data_list:
            return
        msg = QMessageBox()
        msg.setWindowTitle(self.trans["close_all_trades_warning_title"])
        msg.setText(self.trans["close_all_trades_warning_text"])
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if self.language == "uk":
            msg.button(QMessageBox.StandardButton.Yes).setText("Так")
            msg.button(QMessageBox.StandardButton.No).setText("Ні")
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return

        success = close_all_positions(tab_data["session"], tab_data["exchange"], symbol=tab_data["selected_symbol"])
        result = QMessageBox()
        if success:
            result.setWindowTitle("Успіх" if self.language == "uk" else "Success")
            result.setText(self.trans["close_all_trades_success"])
            tab_data["open_order_id"] = None
        else:
            result.setWindowTitle("Помилка" if self.language == "uk" else "Error")
            result.setText(self.trans["close_all_trades_error"].format("No positions found or API error"))
        result.exec()
        self._update_tab_funding_data(tab_data)

    # ------------------------------------------------------------------ #
    #  Оновлення даних вкладки                                            #
    # ------------------------------------------------------------------ #

    def _update_tab_funding_data(self, tab_data, retry_count=3, retry_delay=2):
        if tab_data not in self.tab_data_list:
            return
        for attempt in range(retry_count):
            try:
                tab_data["funding_data"] = get_funding_data(
                    tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"]
                )
                price = get_current_price(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])
                tab_data["price_label"].setText(
                    f"{self.trans['price_label'].split(':')[0]}: ${price:.6f}" if price else self.trans["price_label"]
                )
                balance = get_account_balance(tab_data["session"], tab_data["exchange"])
                tab_data["balance_label"].setText(
                    f"{self.trans['balance_label'].split(':')[0]}: ${balance:.2f} USDT" if balance else self.trans["balance_label"]
                )
                self._update_leveraged_balance(tab_data)
                if tab_data["funding_data"]:
                    rate = tab_data["funding_data"]["funding_rate"]
                    _, time_str = get_next_funding_time(tab_data["funding_data"]["funding_time"], tab_data["funding_interval_hours"])
                    tab_data["funding_info_label"].setText(
                        f"{self.trans['funding_info_label'].split(':')[0]}: {rate:.4f}% | "
                        f"{self.trans['funding_info_label'].split('|')[1].strip()}: {time_str}"
                    )
                else:
                    self._reset_tab_labels(tab_data)
                self._update_volume_label(tab_data)
                self._update_ping(tab_data)
                self._refresh_web_view(tab_data)
                return
            except Exception as e:
                print(f"Error updating funding data (attempt {attempt + 1}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
        self._set_tab_labels_error(tab_data)

    def _update_volume_label(self, tab_data):
        if tab_data not in self.tab_data_list:
            return
        price   = get_current_price(tab_data["session"], tab_data["selected_symbol"], tab_data["exchange"])
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

    def _update_leveraged_balance(self, tab_data):
        if tab_data not in self.tab_data_list:
            return
        balance = get_account_balance(tab_data["session"], tab_data["exchange"])
        if balance and tab_data["leverage"]:
            leveraged = balance * tab_data["leverage"]
            tab_data["leveraged_balance_label"].setText(
                f"{self.trans['leveraged_balance_label'].split(':')[0]}: ${leveraged:.2f} USDT"
            )
        else:
            tab_data["leveraged_balance_label"].setText(self.trans["leveraged_balance_label"])

    def _update_ping(self, tab_data):
        if tab_data not in self.tab_data_list:
            return
        update_ping(tab_data["session"], tab_data["ping_label"], tab_data["exchange"])

    def _reset_tab_labels(self, tab_data):
        t = self.trans
        tab_data["funding_info_label"].setText(t["funding_info_label"])
        tab_data["price_label"].setText(t["price_label"])
        tab_data["balance_label"].setText(t["balance_label"])
        tab_data["leveraged_balance_label"].setText(t["leveraged_balance_label"])
        tab_data["volume_label"].setText(t["volume_label"])
        tab_data["volume_label"].setStyleSheet("color: black;")
        tab_data["ping_label"].setText(t["ping_label"])
        tab_data["ping_label"].setStyleSheet("color: black;")

    def _set_tab_labels_error(self, tab_data):
        t = self.trans
        def _err(key):
            return f"{t[key].split(':')[0]}: Error"
        tab_data["funding_info_label"].setText(
            f"{t['funding_info_label'].split(':')[0]}: Error | {t['funding_info_label'].split('|')[1].strip()}: Error"
        )
        tab_data["price_label"].setText(_err("price_label"))
        tab_data["balance_label"].setText(_err("balance_label"))
        tab_data["leveraged_balance_label"].setText(_err("leveraged_balance_label"))
        tab_data["volume_label"].setText(_err("volume_label"))
        tab_data["volume_label"].setStyleSheet("color: black;")
        tab_data["ping_label"].setText(_err("ping_label"))
        tab_data["ping_label"].setStyleSheet("color: red;")

    # ------------------------------------------------------------------ #
    #  Обробники змін налаштувань                                         #
    # ------------------------------------------------------------------ #

    def _on_exchange_changed(self, tab_data, exchange):
        if tab_data not in self.tab_data_list:
            return
        tab_data["exchange"] = exchange
        self._refresh_web_view(tab_data)
        tab_data["funding_interval_hours"] = 1.0 if exchange == "Bybit" else 8.0
        combo = tab_data["funding_interval_combobox"]
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(["0.01", "1", "4", "8"] if exchange == "Bybit" else ["8"])
        combo.setCurrentText(str(float(tab_data["funding_interval_hours"])).rstrip(".0"))
        combo.blockSignals(False)
        tab_data["session"] = initialize_client(exchange, tab_data["testnet"])
        self._save()
        self._update_tab_funding_data(tab_data)

    def _on_testnet_changed(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            return
        tab_data["testnet"] = state == Qt.CheckState.Checked.value
        tab_data["session"] = initialize_client(tab_data["exchange"], tab_data["testnet"])
        self._save()
        self._update_tab_funding_data(tab_data)

    def _on_symbol_changed(self, tab_data, symbol):
        if tab_data not in self.tab_data_list:
            return
        tab_data["selected_symbol"] = symbol.strip().upper()
        self._refresh_web_view(tab_data)
        self.tab_widget.setTabText(self.tab_data_list.index(tab_data), tab_data["selected_symbol"])
        self._save()
        self._update_tab_funding_data(tab_data)

    def _on_funding_interval_changed(self, tab_data, value):
        if tab_data not in self.tab_data_list or not value:
            return
        tab_data["funding_interval_hours"] = float(value)
        self._save()
        self._update_tab_funding_data(tab_data)

    def _on_entry_time_changed(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            return
        tab_data["entry_time_seconds"] = value
        self._save()

    def _on_qty_changed(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            return
        tab_data["qty"] = value
        self._save()
        self._update_volume_label(tab_data)

    def _on_profit_pct_changed(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            return
        tab_data["profit_percentage"] = value
        tab_data["profit_percentage_slider"].setValue(int(value * 100))
        self._save()

    def _on_profit_slider_changed(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            return
        tab_data["profit_percentage"] = value / 100.0
        tab_data["profit_percentage_spinbox"].setValue(tab_data["profit_percentage"])
        self._save()

    def _on_auto_limit_changed(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            return
        tab_data["auto_limit"] = state == Qt.CheckState.Checked.value
        self._save()

    def _on_leverage_changed(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            return
        tab_data["leverage"] = value
        self._save()
        self._update_leveraged_balance(tab_data)

    def _on_stop_loss_pct_changed(self, tab_data, value):
        if tab_data not in self.tab_data_list:
            return
        tab_data["stop_loss_percentage"] = value
        self._save()

    def _on_stop_loss_enabled_changed(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            return
        tab_data["stop_loss_enabled"] = state == Qt.CheckState.Checked.value
        self._save()

    def _on_reverse_side_changed(self, tab_data, state):
        if tab_data not in self.tab_data_list:
            return
        tab_data["reverse_side"] = state == Qt.CheckState.Checked.value
        self._save()

    # ------------------------------------------------------------------ #
    #  Локалізація                                                        #
    # ------------------------------------------------------------------ #

    def _on_language_changed(self, language_text):
        self.language = "en" if language_text == "English" else "uk"
        self.trans = translations[self.language]
        self.setWindowTitle(self.trans["window_title"].format("Multi-Coin"))
        self.language_label.setText(self.trans["language_label"])
        for td in self.tab_data_list:
            self._update_tab_labels(td)
            self._update_tab_funding_data(td)
        self.tab_widget.setTabText(
            self.tab_widget.count() - 2,
            "Statistics" if self.language == "en" else "Статистика",
        )
        self._save()

    def _update_tab_labels(self, tab_data):
        t = self.trans
        mappings = {
            "exchange_label":            t["exchange_label"],
            "testnet_label":             t["testnet_label"],
            "reverse_side_label":        t["reverse_side_label"],
            "coin_input_label":          t["coin_input_label"],
            "funding_interval_label":    t["funding_interval_label"],
            "entry_time_label":          t["entry_time_label"],
            "qty_label":                 t["qty_label"],
            "profit_percentage_label":   t["profit_percentage_label"],
            "auto_limit_label":          t["auto_limit_label"],
            "leverage_label":            t["leverage_label"],
            "stop_loss_percentage_label":t["stop_loss_percentage_label"],
            "stop_loss_enabled_label":   t["stop_loss_enabled_label"],
            "auto_mode_title_label":     t["auto_mode_title"],
            "auto_mode_label_widget":    t["auto_mode_label"],
            "auto_threshold_label":      t["auto_min_funding_label"],
            "auto_results_label":        t["auto_results_label"],
        }
        for key, text in mappings.items():
            if key in tab_data:
                tab_data[key].setText(text)

        checkboxes = {
            "testnet_checkbox":           t["testnet_checkbox"],
            "reverse_side_checkbox":      t["reverse_side_checkbox"],
            "auto_limit_checkbox":        t["auto_limit_checkbox"],
            "stop_loss_enabled_checkbox": t["stop_loss_enabled_checkbox"],
        }
        for key, text in checkboxes.items():
            if key in tab_data:
                tab_data[key].setText(text)

        buttons = {
            "update_coin_button":         t["update_coin_button"],
            "close_all_trades_button":    t["close_all_trades_button"],
            "auto_scan_btn":              t["auto_scan_now_btn"],
        }
        for key, text in buttons.items():
            if key in tab_data:
                tab_data[key].setText(text)

        # Таблиця авто-сканування
        tab_data["auto_scan_table"].setHorizontalHeaderLabels([
            t["auto_col_symbol"], t["auto_col_rate"], t["auto_col_time"], t["auto_col_select"]
        ])

        # Комбо-бокс режиму
        combo = tab_data["auto_mode_combo"]
        combo.blockSignals(True)
        idx = combo.currentIndex()
        combo.clear()
        combo.addItems([t["auto_mode_manual"], t["auto_mode_auto"]])
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)

        if not tab_data.get("auto_mode"):
            tab_data["auto_status_label"].setText(t["auto_status_disabled"])
            tab_data["auto_chosen_label"].setText(t["auto_chosen_none"])

    # ------------------------------------------------------------------ #
    #  Управління вкладками                                               #
    # ------------------------------------------------------------------ #

    def close_tab(self, index):
        if index >= len(self.tab_data_list):
            return
        if self.tab_widget.count() <= 1:
            return
        td = self.tab_data_list[index]
        for timer_key in ("timer", "funding_refresh_timer", "ping_timer"):
            td[timer_key].stop()
        self.tab_widget.removeTab(index)
        self.tab_data_list.pop(index)
        self._save()

    def closeEvent(self, event):
        self._global_scan_timer.stop()  
        for td in self.tab_data_list:
            for timer_key in ("timer", "funding_refresh_timer", "ping_timer"):
                td[timer_key].stop()
        self._save()
        event.accept()

    # ------------------------------------------------------------------ #
    #  Хелпер збереження                                                  #
    # ------------------------------------------------------------------ #

    def _save(self):
        sm.save_settings(self.tab_data_list, self.language, self.settings_path)