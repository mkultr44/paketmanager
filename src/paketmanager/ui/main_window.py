"""Hauptfenster der Anwendung."""

from __future__ import annotations

from typing import List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from .. import database
from ..config import CONFIG
from ..fuzzy import best_tracking_match, fuzzy_filter
from ..models import OcrEntry, Shipment
from ..ocr_fetcher import OcrFetcher
from .zone_indicator import ZoneIndicatorWidget


class MainWindow(QtWidgets.QWidget):
    """Touch-optimiertes Hauptfenster."""

    def __init__(self, fetcher: Optional[OcrFetcher] = None) -> None:
        super().__init__()
        self.setWindowTitle("Paketmanager")
        self.setMinimumSize(1200, 800)
        self.fetcher = fetcher or OcrFetcher()
        self.ocr_entries: List[OcrEntry] = self.fetcher.load_cached()
        self.shipments: List[Shipment] = []
        self.filtered_indices: List[int] = []
        self.current_zone: Optional[str] = None
        self.mode = "standard"

        self._build_ui()
        self._connect_signals()

        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(CONFIG.polling_seconds * 1000)
        self._poll_timer.timeout.connect(self.poll_ocr_source)
        self._poll_timer.start()

        self.refresh_shipments()
        self.poll_ocr_source()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        mode_layout = QtWidgets.QHBoxLayout()
        self.standard_button = QtWidgets.QPushButton("Standardmodus")
        self.standard_button.setCheckable(True)
        self.standard_button.setChecked(True)
        self.checkin_button = QtWidgets.QPushButton("Einbuchen")
        self.checkin_button.setCheckable(True)
        mode_layout.addWidget(self.standard_button)
        mode_layout.addWidget(self.checkin_button)
        layout.addLayout(mode_layout)

        self.status_label = QtWidgets.QLabel("Bereit")
        self.status_label.setStyleSheet("font-size: 18px; color: #4caf50;")
        layout.addWidget(self.status_label)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack)

        # Standardmodus Seite
        standard_widget = QtWidgets.QWidget()
        standard_layout = QtWidgets.QHBoxLayout(standard_widget)
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Kunde oder Sendungsnummer suchen / scannen")
        self.search_input.setClearButtonEnabled(False)
        self.clear_button = QtWidgets.QPushButton("Clear")
        standard_layout.addWidget(self.search_input)
        standard_layout.addWidget(self.clear_button)
        self.stack.addWidget(standard_widget)

        # Einbuchen Seite
        checkin_widget = QtWidgets.QWidget()
        checkin_layout = QtWidgets.QVBoxLayout(checkin_widget)
        zone_label = QtWidgets.QLabel("Zone auswählen")
        zone_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        checkin_layout.addWidget(zone_label)

        self.zone_button_group = QtWidgets.QButtonGroup(self)
        zone_buttons_layout = QtWidgets.QHBoxLayout()
        zone_buttons_layout.setSpacing(8)
        for zone in CONFIG.zone_names:
            button = QtWidgets.QPushButton(zone)
            button.setCheckable(True)
            button.setMinimumHeight(60)
            self.zone_button_group.addButton(button)
            zone_buttons_layout.addWidget(button)
        zone_buttons_layout.addStretch(1)
        checkin_layout.addLayout(zone_buttons_layout)

        self.scan_input = QtWidgets.QLineEdit()
        self.scan_input.setPlaceholderText("Sendung scannen")
        self.scan_input.setMinimumHeight(60)
        self.scan_input.setStyleSheet("font-size: 20px;")
        checkin_layout.addWidget(self.scan_input)

        self.finish_button = QtWidgets.QPushButton("Fertig")
        self.finish_button.setMinimumHeight(60)
        checkin_layout.addWidget(self.finish_button)

        self.stack.addWidget(checkin_widget)

        # Tabelle und Zone Indikator
        content_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(content_layout, stretch=1)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Sendungsnummer", "Kunde", "Zone", "Eingelagert"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        content_layout.addWidget(self.table, stretch=3)

        self.zone_indicator = ZoneIndicatorWidget(CONFIG.zone_names)
        content_layout.addWidget(self.zone_indicator, stretch=2)
        self.search_input.setFocus()

    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.standard_button.clicked.connect(lambda: self.set_mode("standard"))
        self.checkin_button.clicked.connect(lambda: self.set_mode("checkin"))
        self.clear_button.clicked.connect(self.search_input.clear)
        self.finish_button.clicked.connect(self.finish_checkin)
        self.search_input.textChanged.connect(self.apply_filter)
        self.search_input.returnPressed.connect(self.handle_standard_scan)
        self.scan_input.returnPressed.connect(self.handle_checkin_scan)
        self.zone_button_group.buttonToggled.connect(self.handle_zone_toggle)
        self.table.itemSelectionChanged.connect(self.handle_table_selection)

    # ------------------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self.standard_button.setChecked(mode == "standard")
        self.checkin_button.setChecked(mode == "checkin")
        self.stack.setCurrentIndex(0 if mode == "standard" else 1)
        if mode == "standard":
            self.status("Standardmodus aktiv", success=True)
            self.search_input.setFocus()
        else:
            self.status("Einbuchen-Modus aktiv", success=True)
            self.scan_input.clear()
            self.scan_input.setFocus()

    # ------------------------------------------------------------------
    def status(self, message: str, *, success: bool = True) -> None:
        color = "#4caf50" if success else "#f44336"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"font-size: 18px; color: {color};")

    # ------------------------------------------------------------------
    def poll_ocr_source(self) -> None:
        try:
            updated = self.fetcher.fetch()
        except Exception as exc:  # pragma: no cover - defensive
            self.status(f"Fehler beim Laden der Liste: {exc}", success=False)
            return
        if updated:
            self.ocr_entries = updated
            self.status(f"OCR-Liste aktualisiert ({len(updated)} Einträge)")
        elif not self.ocr_entries:
            self.status("Keine OCR-Daten vorhanden", success=False)
        else:
            self.status("OCR-Liste unverändert")

    # ------------------------------------------------------------------
    def refresh_shipments(self) -> None:
        self.shipments = database.fetch_shipments()
        self.apply_filter(self.search_input.text())

    # ------------------------------------------------------------------
    def apply_filter(self, text: str) -> None:
        pairs = [(shipment.tracking_number, shipment.customer) for shipment in self.shipments]
        indices = fuzzy_filter(text.strip(), pairs, score_cutoff=CONFIG.fuzzy_score_cutoff)
        self.filtered_indices = indices
        self.render_table()

    # ------------------------------------------------------------------
    def render_table(self) -> None:
        self.table.setRowCount(len(self.filtered_indices))
        for row_index, shipment_index in enumerate(self.filtered_indices):
            shipment = self.shipments[shipment_index]
            self.table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(shipment.tracking_number))
            self.table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(shipment.customer))
            self.table.setItem(row_index, 2, QtWidgets.QTableWidgetItem(shipment.zone))
            timestamp = shipment.created_at.strftime("%d.%m.%Y %H:%M")
            self.table.setItem(row_index, 3, QtWidgets.QTableWidgetItem(timestamp))
        if len(self.filtered_indices) == 1:
            only_shipment = self.shipments[self.filtered_indices[0]]
            self.zone_indicator.highlight_zone(only_shipment.zone)
        elif not self.table.selectedItems():
            self.zone_indicator.highlight_zone(None)

    # ------------------------------------------------------------------
    def handle_standard_scan(self) -> None:
        self.apply_filter(self.search_input.text())
        if len(self.filtered_indices) == 1:
            shipment = self.shipments[self.filtered_indices[0]]
            self.zone_indicator.highlight_zone(shipment.zone)
        else:
            self.zone_indicator.highlight_zone(None)

    # ------------------------------------------------------------------
    def handle_checkin_scan(self) -> None:
        code = self.scan_input.text().strip()
        self.scan_input.clear()
        if not code:
            return
        if not self.current_zone:
            self.status("Bitte Zone auswählen", success=False)
            return
        match = best_tracking_match(
            code,
            [entry.tracking_number for entry in self.ocr_entries],
            score_cutoff=CONFIG.fuzzy_score_cutoff,
        )
        if not match:
            self.status("Keine passende Sendung gefunden", success=False)
            return
        matched_tracking, score = match
        entry = next((item for item in self.ocr_entries if item.tracking_number == matched_tracking), None)
        customer = entry.customer if entry else "Unbekannt"
        try:
            database.insert_shipment(
                tracking_number=code,
                customer=customer,
                zone=self.current_zone,
                source_tracking_number=matched_tracking,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.status(f"Fehler beim Speichern: {exc}", success=False)
            return
        self.status(f"Sendung für {customer} in {self.current_zone} gebucht (Score {score:.0f})")
        self.refresh_shipments()
        self.zone_indicator.highlight_zone(self.current_zone)

    # ------------------------------------------------------------------
    def handle_zone_toggle(self, button: QtWidgets.QAbstractButton, checked: bool) -> None:
        if checked:
            self.current_zone = button.text()
            self.status(f"Zone {self.current_zone} ausgewählt")
            for other_button in self.zone_button_group.buttons():
                if other_button is not button:
                    other_button.setChecked(False)
        elif button.text() == self.current_zone:
            self.current_zone = None
            self.zone_indicator.highlight_zone(None)

    # ------------------------------------------------------------------
    def finish_checkin(self) -> None:
        self.current_zone = None
        for button in self.zone_button_group.buttons():
            button.setChecked(False)
        self.zone_indicator.highlight_zone(None)
        self.set_mode("standard")

    # ------------------------------------------------------------------
    def handle_table_selection(self) -> None:
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
        row = selected_items[0].row()
        if row < 0 or row >= len(self.filtered_indices):
            return
        shipment = self.shipments[self.filtered_indices[row]]
        self.zone_indicator.highlight_zone(shipment.zone)

