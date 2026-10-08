from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QListWidget, QLabel
from .common import page_layout


class ProjectsPage(QWidget):
    add_requested = Signal()
    remove_requested = Signal(str)
    select_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = page_layout(self, 'Projects', '管理本地项目目录；项目列表和选择状态从 SQLite 加载。')
        row = QHBoxLayout()
        btn_add = QPushButton('＋ 添加本地项目')
        btn_add.clicked.connect(self.add_requested.emit)
        row.addWidget(btn_add)
        btn_select = QPushButton('切换到选中项目')
        btn_select.clicked.connect(self._select)
        row.addWidget(btn_select)
        btn_remove = QPushButton('从列表移除')
        btn_remove.clicked.connect(self._remove)
        row.addWidget(btn_remove)
        row.addStretch(1)
        layout.addLayout(row)
        self.projects = QListWidget()
        self.projects.itemDoubleClicked.connect(lambda _: self._select())
        layout.addWidget(self.projects)
        note = QLabel('移除仅删除 Dev Assistant 的记录，不会删除磁盘中的项目。')
        note.setObjectName('mutedLabel')
        layout.addWidget(note)

    def set_projects(self, projects: list[dict], active: str) -> None:
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        self.projects.clear()
        for p in projects:
            label = ('● ' if p['path'] == active else '   ') + p['name'] + '  ·  ' + p['path']
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, p['path'])
            self.projects.addItem(item)

    def _current(self) -> str:
        from PySide6.QtCore import Qt
        item = self.projects.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ''

    def _select(self) -> None:
        if self._current():
            self.select_requested.emit(self._current())

    def _remove(self) -> None:
        if self._current():
            self.remove_requested.emit(self._current())
