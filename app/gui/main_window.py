"""Modern PySide6 shell, no CLI or database business logic."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                              QPushButton, QComboBox, QLineEdit, QSplitter, QStackedWidget,
                              QButtonGroup)
from app.gui.widgets.terminal import TerminalWidget
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.projects import ProjectsPage
from app.gui.pages.git import GitPage
from app.gui.pages.environment import EnvironmentPage
from app.gui.pages.lfs import LFSPage
from app.gui.pages.learning import LearningPage
from app.gui.pages.generator import GeneratorPage
from app.gui.pages.more import MoreToolsPage
from app.gui.pages.settings import SettingsPage


DARK = '''
QMainWindow, QWidget {background: #121217; color: #ededf5; font-family: "Segoe UI"; font-size: 12px;}
QWidget#topToolbar, QWidget#sidebar {background: #191920;}
QWidget#sidebar {border-right: 1px solid #33333c;}
QLabel#brand {font-size: 17px; font-weight: 700; color: #a5a7ff; padding: 8px;}
QLabel#pageTitle {font-size: 23px; font-weight: 700; margin-bottom: 1px;}
QLabel#mutedLabel {color: #9797ac;}
QLabel#summaryCard {font-size: 16px; font-weight: 600; padding: 16px; background: #252531; border: 1px solid #393948; border-radius: 9px;}
QLabel#cardTitle {font-size: 15px; font-weight: 600;}
QFrame#projectCard {background: #1b1b25; border: 1px solid #32323e; border-radius: 9px;}
QPushButton {background: #2a2a36; border: 1px solid #424252; border-radius: 6px; padding: 7px 11px; color: #eeeeff;}
QPushButton:hover {background: #393950; border-color: #6d70cc;}
QPushButton:disabled {color: #797985;}
QPushButton#navButton {text-align: left; font-size: 13px; background: transparent; border: 0; padding: 10px 16px;}
QPushButton#navButton:checked {background: #30304a; border-left: 3px solid #818cf8; font-weight: 600;}
QComboBox, QLineEdit, QPlainTextEdit, QListWidget, QTableWidget, QTabWidget, QScrollArea {
    background: #1c1c26; color: #ededf5; border: 1px solid #383846; border-radius: 6px; padding: 5px; selection-background-color: #51528c;}
QHeaderView::section {background: #282835; color: #eee; padding: 7px; border: 0;}
QTabBar::tab {background: #252533; padding: 10px 14px; margin-right: 3px; border-radius: 5px;}
QTabBar::tab:selected {background: #48486c;}
QSplitter::handle {background: #353540;}
QWidget#terminal {background: #15151b; border-top: 1px solid #363644;}
QPlainTextEdit#terminalOutput {background: #0d0d12; border: none; color: #cbd5e1;}
'''
LIGHT = '''
QMainWindow, QWidget {background: #f4f5fa; color: #22243a; font-family: "Segoe UI"; font-size: 12px;}
QWidget#topToolbar, QWidget#sidebar {background: #e9eaf4;}
QWidget#sidebar {border-right: 1px solid #d1d3e2;}
QLabel#brand {font-size: 17px; font-weight: 700; color: #4f46e5; padding: 8px;}
QLabel#pageTitle {font-size: 23px; font-weight: 700;}
QLabel#mutedLabel {color: #5f6276;}
QLabel#summaryCard {font-size: 16px; font-weight: 600; padding: 16px; background: #fff; border: 1px solid #d0d3e7; border-radius: 9px;}
QLabel#cardTitle {font-size: 15px; font-weight: 600;}
QFrame#projectCard {background: #fff; border: 1px solid #d8d9e8; border-radius: 9px;}
QPushButton {background: #fff; border: 1px solid #c4c8db; border-radius: 6px; padding: 7px 11px;}
QPushButton:hover {background: #e4e7ff;}
QPushButton#navButton {text-align: left; font-size: 13px; background: transparent; border: 0; padding: 10px 16px;}
QPushButton#navButton:checked {background: #d8dbf4; border-left: 3px solid #4f46e5; font-weight: 600;}
QComboBox, QLineEdit, QPlainTextEdit, QListWidget, QTableWidget, QTabWidget, QScrollArea {background: #fff; color: #22243a; border: 1px solid #c9cada; border-radius: 6px; padding: 5px;}
QHeaderView::section {background: #e2e5ef; color: #22243a; padding: 7px; border: 0;}
QTabBar::tab {background: #e4e7f2; padding: 10px 14px; margin-right: 3px; border-radius: 5px;}
QTabBar::tab:selected {background: #cdd2fb;}
QSplitter::handle {background: #c9cada;}
QWidget#terminal {background: #15151b;}
QPlainTextEdit#terminalOutput {background: #0d0d12; color: #cbd5e1; border: none;}
'''


class MainWindow(QMainWindow):
    project_changed = Signal(str)
    refresh_requested = Signal()
    theme_toggle_requested = Signal()
    search_requested = Signal(str)

    NAV = [
        ('dashboard', '▦   Dashboard'), ('projects', '▤   Projects'),
        ('git', '⌥   Git'), ('environment', '⚡   Environment'),
        ('lfs', '◈   Git LFS'), ('learning', '☷   Learning'),
        ('generator', '＋   Generator'), ('more', '◇   More Tools'),
        ('settings', '⚙   Settings'),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dev Assistant v1.1 · Developer Workspace')
        self.resize(1240, 800)
        self.setMinimumSize(960, 620)
        self.pages = {
            'dashboard': DashboardPage(), 'projects': ProjectsPage(),
            'git': GitPage(), 'environment': EnvironmentPage(),
            'lfs': LFSPage(), 'learning': LearningPage(),
            'generator': GeneratorPage(), 'more': MoreToolsPage(),
            'settings': SettingsPage(),
        }
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        toolbar = QWidget()
        toolbar.setObjectName('topToolbar')
        top = QHBoxLayout(toolbar)
        top.setContentsMargins(16, 7, 16, 7)
        top.addWidget(QLabel('ACTIVE PROJECT:'))
        self.project_selector = QComboBox()
        self.project_selector.setMinimumWidth(220)
        self.project_selector.currentIndexChanged.connect(self._project_selected)
        top.addWidget(self.project_selector)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('搜索页面 / Git 学习命令…  Ctrl+K')
        self.search_input.returnPressed.connect(lambda: self.search_requested.emit(self.search_input.text().strip()))
        top.addWidget(self.search_input, stretch=1)
        refresh = QPushButton('↻ Refresh')
        refresh.clicked.connect(self.refresh_requested.emit)
        top.addWidget(refresh)
        theme = QPushButton('◐ Theme')
        theme.clicked.connect(self.theme_toggle_requested.emit)
        top.addWidget(theme)
        outer.addWidget(toolbar)
        inner = QHBoxLayout()
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(10, 12, 10, 10)
        side.setSpacing(5)
        label = QLabel('◆  Dev Assistant')
        label.setObjectName('brand')
        side.addWidget(label)
        self.nav_buttons = {}
        buttons = QButtonGroup(self)
        buttons.setExclusive(True)
        for index, (key, caption) in enumerate(self.NAV):
            button = QPushButton(caption)
            button.setObjectName('navButton')
            button.setCheckable(True)
            buttons.addButton(button)
            button.clicked.connect(lambda _, i=index: self.stack.setCurrentIndex(i))
            if key == 'settings':
                side.addStretch(1)
            side.addWidget(button)
            self.nav_buttons[key] = button
        self.nav_buttons['dashboard'].setChecked(True)
        inner.addWidget(sidebar)
        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        self.stack = QStackedWidget()
        for key, _ in self.NAV:
            self.stack.addWidget(self.pages[key])
        split.addWidget(self.stack)
        self.terminal = TerminalWidget()
        self.terminal.setMinimumHeight(125)
        split.addWidget(self.terminal)
        split.setSizes([545, 180])
        inner.addWidget(split, stretch=1)
        outer.addLayout(inner, stretch=1)
        self.statusBar().showMessage('就绪 · 请选择项目')
        QShortcut(QKeySequence('Ctrl+K'), self, activated=self.search_input.setFocus)
        self.apply_theme('Dark')

    def _project_selected(self, index: int) -> None:
        if index >= 0:
            path = self.project_selector.itemData(index)
            if path:
                self.project_changed.emit(path)

    def set_projects(self, projects: list[dict], active: str) -> None:
        self.project_selector.blockSignals(True)
        self.project_selector.clear()
        self.project_selector.addItem('— 选择项目 —', '')
        for project in projects:
            self.project_selector.addItem(project['name'], project['path'])
        for index in range(self.project_selector.count()):
            if self.project_selector.itemData(index) == active:
                self.project_selector.setCurrentIndex(index)
                break
        self.project_selector.blockSignals(False)
        self.pages['dashboard'].set_projects(projects, active)
        self.pages['projects'].set_projects(projects, active)

    def navigate(self, key: str) -> None:
        if key not in self.pages:
            return
        index = [name for name, _ in self.NAV].index(key)
        self.stack.setCurrentIndex(index)
        self.nav_buttons[key].setChecked(True)

    def apply_theme(self, name: str) -> None:
        self.setStyleSheet(LIGHT if name == 'Light' else DARK)
