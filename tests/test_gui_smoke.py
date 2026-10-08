"""Run on Windows or any system with PySide6 and an offscreen Qt backend."""
import os
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from app.bootstrap import create_services
from app.gui.main_window import MainWindow
from app.controllers.app_controller import AppController


def test_main_window_boots_and_pages_switch(tmp_path):
    app = QApplication.instance() or QApplication([])
    s = create_services(tmp_path / 'data')
    window = MainWindow()
    controller = AppController(window, s)
    window.controller = controller
    assert window.stack.count() == 9
    window.navigate('git')
    assert window.stack.currentWidget() is window.pages['git']
    window.apply_theme('Light')
    window.close()
