from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QPushButton, QFrame
from .common import page_layout


class DashboardPage(QWidget):
    open_project_requested = Signal(str)
    sync_project_requested = Signal(str)
    add_project_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = page_layout(self, 'Workspace Dashboard', '项目、Git 与开发环境的一站式工作台')
        self.count_label = QLabel('暂无项目')
        self.count_label.setObjectName('summaryCard')
        layout.addWidget(self.count_label)
        row = QHBoxLayout()
        row.addWidget(QLabel('ACTIVE PROJECTS'))
        row.addStretch(1)
        add = QPushButton('＋ 添加项目')
        add.clicked.connect(self.add_project_requested.emit)
        row.addWidget(add)
        layout.addLayout(row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.items = QVBoxLayout(self.container)
        self.items.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.container)
        layout.addWidget(scroll)

    def set_projects(self, projects: list[dict], active: str) -> None:
        while self.items.count():
            child = self.items.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.count_label.setText(f'{len(projects)} 项目   ·   ' + ('当前项目：' + next((p['name'] for p in projects if p['path'] == active), '未选择')))
        for p in projects:
            card = QFrame()
            card.setObjectName('projectCard')
            col = QVBoxLayout(card)
            label = QLabel(('●  ' if p['path'] == active else '○  ') + p['name'] + '     ' + p['language'])
            label.setObjectName('cardTitle')
            col.addWidget(label)
            path = QLabel(p['path'])
            path.setObjectName('mutedLabel')
            path.setWordWrap(True)
            col.addWidget(path)
            row = QHBoxLayout()
            open_btn = QPushButton('选择项目')
            open_btn.clicked.connect(lambda _, path=p['path']: self.open_project_requested.emit(path))
            sync_btn = QPushButton('Git Pull')
            sync_btn.clicked.connect(lambda _, path=p['path']: self.sync_project_requested.emit(path))
            row.addWidget(open_btn)
            row.addWidget(sync_btn)
            row.addStretch(1)
            col.addLayout(row)
            self.items.addWidget(card)
