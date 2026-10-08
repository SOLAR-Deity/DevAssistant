from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QPushButton, QComboBox, QLabel, QCheckBox
from .common import page_layout


class SettingsPage(QWidget):
    theme_changed = Signal(str)
    history_requested = Signal()
    learning_mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = page_layout(self, 'Settings', '应用设置保存在本地 SQLite 中。')
        layout.addWidget(QLabel('主题'))
        self.theme = QComboBox()
        self.theme.addItems(['Dark', 'Light'])
        self.theme.currentTextChanged.connect(self.theme_changed.emit)
        layout.addWidget(self.theme)
        self.learning_mode = QCheckBox('Git 学习模式：GUI 操作时解释对应命令（默认开启）')
        self.learning_mode.toggled.connect(self.learning_mode_changed.emit)
        layout.addWidget(self.learning_mode)
        history = QPushButton('查看终端命令历史')
        history.clicked.connect(self.history_requested.emit)
        layout.addWidget(history)
        layout.addWidget(QLabel('Dev Assistant v1.1 · Windows · Python 3.12 · PySide6'))
        layout.addStretch(1)
