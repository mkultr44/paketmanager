"""Widget zur Visualisierung der Lagerzonen."""

from __future__ import annotations

from typing import Dict

from PyQt6 import QtCore, QtWidgets


class ZoneIndicatorWidget(QtWidgets.QWidget):
    """Zeigt den Zustand aller Zonen mit Farbmarkierung an."""

    def __init__(self, zones: list[str], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._zones = zones
        self._labels: Dict[str, QtWidgets.QLabel] = {}
        layout = QtWidgets.QGridLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        columns = max(1, len(zones) // 3)
        for index, zone in enumerate(zones):
            label = QtWidgets.QLabel(zone)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setMinimumSize(120, 80)
            label.setStyleSheet(self._style_for(False))
            self._labels[zone] = label
            row = index // columns
            column = index % columns
            layout.addWidget(label, row, column)

    def _style_for(self, active: bool) -> str:
        if active:
            return (
                "background-color: #d32f2f; color: white; border-radius: 12px;"
                "font-size: 20px; font-weight: bold;"
            )
        return "background-color: #37474f; color: white; border-radius: 12px; font-size: 18px;"

    def highlight_zone(self, zone: str | None) -> None:
        for name, label in self._labels.items():
            label.setStyleSheet(self._style_for(name == zone))

    def zones(self) -> list[str]:
        return self._zones
