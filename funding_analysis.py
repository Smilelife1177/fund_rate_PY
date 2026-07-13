import csv
import math
import os
from collections import defaultdict
from statistics import mean

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def _to_float(value, default=0.0):
    try:
        return float(str(value).replace("%", "").replace("+", "").replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


def _safe_mean(values):
    values = [v for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    return mean(values) if values else 0.0


class BarChartWidget(QWidget):
    def __init__(self, title, data, value_suffix="", parent=None):
        super().__init__(parent)
        self.title = title
        self.data = data
        self.value_suffix = value_suffix
        self.setMinimumHeight(260)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(16, 16, -16, -28)

        text_color = self.palette().windowText().color()
        muted_color = QColor(text_color)
        muted_color.setAlpha(180)

        painter.setPen(QPen(text_color))
        painter.drawText(rect.left(), rect.top(), self.title)

        if not self.data:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No data")
            return

        plot = rect.adjusted(0, 28, 0, -12)
        values = [abs(v) for _, v in self.data]
        max_value = max(values) if values else 1
        max_value = max(max_value, 0.000001)
        gap = 8
        bar_width = max(10, (plot.width() - gap * (len(self.data) - 1)) / len(self.data))

        for i, (label, value) in enumerate(self.data):
            x = plot.left() + i * (bar_width + gap)
            h = (abs(value) / max_value) * max(1, plot.height() - 36)
            y = plot.bottom() - h - 20
            color = QColor("#1f8f4d") if value >= 0 else QColor("#c0392b")
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(x), int(y), int(bar_width), int(h))

            painter.setPen(QPen(muted_color))
            painter.drawText(int(x), plot.bottom() - 16, int(bar_width), 16, Qt.AlignmentFlag.AlignCenter, str(label))
            painter.setPen(QPen(text_color))
            painter.drawText(
                int(x) - 10,
                int(y) - 18,
                int(bar_width) + 20,
                16,
                Qt.AlignmentFlag.AlignCenter,
                f"{value:.3f}{self.value_suffix}",
            )


class ScatterChartWidget(QWidget):
    def __init__(self, title, points, parent=None):
        super().__init__(parent)
        self.title = title
        self.points = points
        self.setMinimumHeight(260)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(18, 16, -18, -24)
        text_color = self.palette().windowText().color()
        axis_color = QColor(text_color)
        axis_color.setAlpha(120)

        painter.setPen(QPen(text_color))
        painter.drawText(rect.left(), rect.top(), self.title)

        plot = rect.adjusted(0, 30, 0, -8)
        painter.setPen(QPen(axis_color))
        painter.drawRect(plot)

        if not self.points:
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "No data")
            return

        max_x = max(abs(x) for x, _ in self.points) or 1
        max_y = max(abs(y) for _, y in self.points) or 1
        mid_y = plot.center().y()
        painter.setPen(QPen(axis_color))
        painter.drawLine(plot.left(), mid_y, plot.right(), mid_y)

        for x_val, y_val in self.points:
            x = plot.left() + (abs(x_val) / max_x) * plot.width()
            y = mid_y - (y_val / max_y) * (plot.height() / 2 - 8)
            color = QColor("#1f8f4d") if y_val >= 0 else QColor("#c0392b")
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)


class FundingAnalysisDialog(QDialog):
    def __init__(self, csv_path, title="Funding Analysis", parent=None):
        super().__init__(parent)
        self.csv_path = csv_path
        self.rows = self._load_rows()

        self.setWindowTitle(title)
        self.resize(1200, 820)

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.status_label = QLabel(self._status_text())
        header.addWidget(self.status_label)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._build_tabs()

    def _load_rows(self):
        if not os.path.exists(self.csv_path):
            return []
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception as e:
            print(f"Error reading analysis CSV: {e}")
            return []

    def _status_text(self):
        if not self.rows:
            return f"No records found in {self.csv_path}"
        symbols = {row.get("symbol", "") for row in self.rows if row.get("symbol")}
        return f"Records: {len(self.rows)} | Symbols: {len(symbols)} | Source: {self.csv_path}"

    def _refresh(self):
        self.rows = self._load_rows()
        self.status_label.setText(self._status_text())
        self.tabs.clear()
        self._build_tabs()

    def _build_tabs(self):
        self.tabs.addTab(self._summary_tab(), "Summary")
        self.tabs.addTab(self._charts_tab(), "Charts")
        self.tabs.addTab(self._patterns_tab(), "Patterns")

    def _summary_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(self._summary_text())
        layout.addWidget(text)
        return tab

    def _charts_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(BarChartWidget("Average post-funding price move", self._avg_move_data(), "%"))
        layout.addWidget(BarChartWidget("Win rate by absolute funding bucket", self._bucket_winrate_data(), "%"))
        layout.addWidget(ScatterChartWidget("|Funding %| vs 5m price move", self._scatter_points()))
        layout.addStretch()
        return tab

    def _patterns_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        table = QTableWidget()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        headers = ["Pattern", "Count", "Avg 1m %", "Avg 5m %", "Avg 10m %", "Win 5m %"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        rows = self._pattern_rows()
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        layout.addWidget(table)
        return tab

    def _summary_text(self):
        if not self.rows:
            return "No data to analyze yet. Enable funding stats collection and wait for records."

        f_rates = [_to_float(r.get("funding_rate_pct")) for r in self.rows]
        move_1m = [_to_float(r.get("price_1m_%")) for r in self.rows]
        move_5m = [_to_float(r.get("price_5m_%")) for r in self.rows]
        move_10m = [_to_float(r.get("price_10m_%")) for r in self.rows]
        symbols = {r.get("symbol") for r in self.rows if r.get("symbol")}

        best_symbols = self._top_symbols()
        lines = [
            "Funding data analysis",
            "",
            f"Total records: {len(self.rows)}",
            f"Unique symbols: {len(symbols)}",
            f"Average funding rate: {_safe_mean(f_rates):+.4f}%",
            f"Average absolute funding rate: {_safe_mean([abs(v) for v in f_rates]):.4f}%",
            f"Average move after 1m: {_safe_mean(move_1m):+.4f}%",
            f"Average move after 5m: {_safe_mean(move_5m):+.4f}%",
            f"Average move after 10m: {_safe_mean(move_10m):+.4f}%",
            "",
            "Top symbols by average 5m move:",
        ]
        lines.extend([f"- {symbol}: {avg:+.4f}% ({count} records)" for symbol, avg, count in best_symbols])
        lines.extend([
            "",
            "Interpretation:",
            "- Positive average post-funding moves show where price tended to rise after funding.",
            "- Bucket win rate checks whether stronger funding values produced more reliable movement.",
            "- Use this as a research view only; it does not account for fees, slippage, or live liquidity.",
        ])
        return "\n".join(lines)

    def _avg_move_data(self):
        return [
            ("1m", _safe_mean([_to_float(r.get("price_1m_%")) for r in self.rows])),
            ("5m", _safe_mean([_to_float(r.get("price_5m_%")) for r in self.rows])),
            ("10m", _safe_mean([_to_float(r.get("price_10m_%")) for r in self.rows])),
        ]

    def _bucket_for_rate(self, rate):
        ar = abs(rate)
        if ar < 0.10:
            return "<0.10"
        if ar < 0.20:
            return "0.10-0.20"
        if ar < 0.50:
            return "0.20-0.50"
        return ">=0.50"

    def _bucket_winrate_data(self):
        buckets = defaultdict(list)
        for row in self.rows:
            rate = _to_float(row.get("funding_rate_pct"))
            move = _to_float(row.get("price_5m_%"))
            buckets[self._bucket_for_rate(rate)].append(move)
        ordered = ["<0.10", "0.10-0.20", "0.20-0.50", ">=0.50"]
        result = []
        for key in ordered:
            values = buckets.get(key, [])
            win_rate = (sum(1 for v in values if v > 0) / len(values) * 100) if values else 0.0
            result.append((key, win_rate))
        return result

    def _scatter_points(self):
        return [
            (abs(_to_float(row.get("funding_rate_pct"))), _to_float(row.get("price_5m_%")))
            for row in self.rows
            if row.get("funding_rate_pct") is not None and row.get("price_5m_%") is not None
        ][:600]

    def _pattern_rows(self):
        groups = defaultdict(list)
        for row in self.rows:
            rate = _to_float(row.get("funding_rate_pct"))
            spread = _to_float(row.get("spread_pct"))
            volatility = _to_float(row.get("volatility_1h_pct"))
            label = self._bucket_for_rate(rate)
            if spread <= 0.05:
                label += " | tight spread"
            if volatility >= 1.0:
                label += " | high volatility"
            groups[label].append(row)

        result = []
        for label, rows in groups.items():
            move_1m = [_to_float(r.get("price_1m_%")) for r in rows]
            move_5m = [_to_float(r.get("price_5m_%")) for r in rows]
            move_10m = [_to_float(r.get("price_10m_%")) for r in rows]
            win_5m = (sum(1 for v in move_5m if v > 0) / len(move_5m) * 100) if move_5m else 0.0
            result.append([
                label,
                len(rows),
                f"{_safe_mean(move_1m):+.4f}",
                f"{_safe_mean(move_5m):+.4f}",
                f"{_safe_mean(move_10m):+.4f}",
                f"{win_5m:.1f}",
            ])
        result.sort(key=lambda row: int(row[1]), reverse=True)
        return result

    def _top_symbols(self):
        by_symbol = defaultdict(list)
        for row in self.rows:
            symbol = row.get("symbol")
            if symbol:
                by_symbol[symbol].append(_to_float(row.get("price_5m_%")))
        ranked = [
            (symbol, _safe_mean(values), len(values))
            for symbol, values in by_symbol.items()
            if values
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:10]
