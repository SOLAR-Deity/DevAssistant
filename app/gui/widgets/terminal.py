"""Git-Bash-like output plus a real command input, with signals only (no subprocess)."""
from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QKeyEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QPlainTextEdit, QLineEdit)


class CommandInput(QLineEdit):
    history_previous = Signal(str)
    history_next = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Up:
            self.history_previous.emit(self.text())
        elif event.key() == Qt.Key.Key_Down:
            self.history_next.emit()
        else:
            super().keyPressEvent(event)


class TerminalWidget(QWidget):
    history_requested = Signal()
    command_submitted = Signal(str)
    cancel_requested = Signal()
    history_previous = Signal(str)
    history_next = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('terminal')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(14, 6, 12, 6)
        bar.addWidget(QLabel('⌘  TERMINAL · CMD / Git'))
        bar.addStretch(1)
        for caption, callback in [('历史', self.history_requested.emit),
                                  ('复制', self.copy), ('清空', self.clear),
                                  ('停止', self.cancel_requested.emit)]:
            btn = QPushButton(caption)
            btn.clicked.connect(callback)
            bar.addWidget(btn)
        layout.addLayout(bar)
        self.text_area = QPlainTextEdit()
        self.text_area.setObjectName('terminalOutput')
        self.text_area.setReadOnly(True)
        self.text_area.setMaximumBlockCount(3500)
        self.text_area.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text_area.setFont(QFont('Consolas', 10))
        layout.addWidget(self.text_area)
        footer = QHBoxLayout()
        footer.setContentsMargins(12, 5, 12, 7)
        self.cwd_label = QLabel('>')
        self.cwd_label.setObjectName('mutedLabel')
        self.cwd_label.setMinimumWidth(160)
        footer.addWidget(self.cwd_label)
        self.command_input = CommandInput()
        self.command_input.setObjectName('terminalCommandInput')
        self.command_input.setPlaceholderText('输入 Git / Python / Docker / CMD 命令；↑↓ 历史，Enter 执行…')
        self.command_input.returnPressed.connect(self._submit)
        self.command_input.history_previous.connect(self.history_previous.emit)
        self.command_input.history_next.connect(self.history_next.emit)
        footer.addWidget(self.command_input, stretch=1)
        run_btn = QPushButton('运行 ↵')
        run_btn.clicked.connect(self._submit)
        footer.addWidget(run_btn)
        layout.addLayout(footer)
        self.append_output('Dev Assistant · 可在下方输入命令。选择项目后自动切换工作目录。')

    def _submit(self) -> None:
        text = self.command_input.text().strip()
        if text:
            self.command_input.clear()
            self.command_submitted.emit(text)

    def set_cwd(self, cwd: str) -> None:
        self.cwd_label.setText(('…' + cwd[-35:] if len(cwd) > 37 else cwd) + '>')
        self.cwd_label.setToolTip(cwd)

    def set_history_input(self, text: str) -> None:
        self.command_input.setText(text)
        self.command_input.setCursorPosition(len(text))

    def _insert(self, message: str, color: str, bold: bool = False, newline: bool = True) -> None:
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        # Streaming chunks should not append a newline every time a child writes.
        if newline or not message:
            message = message.rstrip('\r\n') + '\n'
        cursor.insertText(message.replace('\0', '␀'), fmt)
        self.text_area.setTextCursor(cursor)
        self.text_area.ensureCursorVisible()

    def append_command(self, command: str, project: str = '', source: str = '') -> None:
        stamp = datetime.now().strftime('%H:%M:%S')
        origin = {'terminal': 'YOU', 'git_ui': 'UI · Git',
                  'environment_ui': 'UI · Env', 'docker_ui': 'UI · Docker',
                  'ssh_ui': 'UI · SSH', 'github_ui': 'UI · GitHub',
                  'lfs_ui': 'UI · LFS', 'system': 'SYSTEM'}.get(source, source or 'UI')
        prompt = f'{project}> ' if project else '> '
        self._insert(f'[{stamp}] [{origin}] {prompt}{command}', '#4ade80', True)

    def append_chunk(self, content: str, is_error: bool = False) -> None:
        if content:
            self._insert(content, '#fb7185' if is_error else '#cbd5e1', newline=False)

    def append_output(self, message: str, is_error: bool = False) -> None:
        if message:
            self._insert(message, '#fb7185' if is_error else '#cbd5e1')

    def append_exit(self, exit_code: int, duration_seconds: float) -> None:
        if not self.text_area.toPlainText().endswith('\n'):
            self._insert('', '#cbd5e1')
        self._insert(f'  ↳ exit {exit_code} · {duration_seconds:.2f}s',
                     '#86efac' if exit_code == 0 else '#fda4af')

    def clear(self) -> None:
        self.text_area.clear()

    def copy(self) -> None:
        if self.text_area.textCursor().hasSelection():
            self.text_area.copy()
        else:
            self.text_area.selectAll()
            self.text_area.copy()
            cursor = self.text_area.textCursor()
            cursor.clearSelection()
            self.text_area.setTextCursor(cursor)
