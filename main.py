"""Dev Assistant desktop entrypoint: python main.py"""
from __future__ import annotations
import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from app.bootstrap import create_services
from app.gui.main_window import MainWindow
from app.controllers.app_controller import AppController
from app.utils.logging_setup import configure_logging


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName('Dev Assistant')
    app.setOrganizationName('DevAssistantLab')
    app.setFont(QFont('Segoe UI', 10))
    services = create_services()
    configure_logging(services.store.path.parent)
    window = MainWindow()
    controller = AppController(window, services)
    window.controller = controller  # keep signals/controllers alive for the window lifetime
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
