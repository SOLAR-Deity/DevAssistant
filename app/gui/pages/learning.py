from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QListWidget, QPlainTextEdit, QPushButton
from .common import page_layout


class LearningPage(QWidget):
    example_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = page_layout(self, 'Git Learning', '离线 Git 命令说明：语义、用法、示例、相关命令。')
        row = QHBoxLayout()
        self.commands = QListWidget()
        self.commands.setMaximumWidth(220)
        self.commands.currentTextChanged.connect(self._selected)
        row.addWidget(self.commands)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        row.addWidget(self.details, stretch=1)
        layout.addLayout(row)
        self.explanation = {}
        example = QPushButton('将示例显示到终端（不执行）')
        example.clicked.connect(lambda: self.example_requested.emit(self.explanation.get('example', '')))
        layout.addWidget(example)

    def set_catalog(self, commands: list[str], explain) -> None:
        self._explain = explain
        self.commands.addItems(commands)
        self.commands.setCurrentRow(0)

    def _selected(self, command: str) -> None:
        if not command or not hasattr(self, '_explain'):
            return
        info = self._explain(command)
        self.explanation = info
        self.details.setPlainText(f"COMMAND\n{info['command']}\n\nDESCRIPTION\n{info['description']}\n\nUSAGE\n{info['usage']}\n\nEXAMPLE\n{info['example']}\n\nRELATED COMMANDS\n" + ', '.join(info['related_commands']))
