"""Einstiegspunkt für die Paketmanager-Anwendung."""

from __future__ import annotations

import sys

from PyQt6 import QtWidgets

from .config import CONFIG
from .database import init_database
from .ocr_fetcher import OcrFetcher, ensure_logging_setup
from .ui import MainWindow


def main() -> int:
    ensure_logging_setup()
    init_database()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(OcrFetcher(CONFIG.webdav_url))
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
