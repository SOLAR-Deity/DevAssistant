from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QPlainTextEdit, QComboBox, QTableWidget, QTableWidgetItem,
                              QHeaderView)
from .common import page_layout


class EnvironmentPage(QWidget):
    detect_requested = Signal()
    export_requested = Signal(str)
    restore_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = page_layout(self, 'Environment Manager', '检测 Python / Java / Node / Docker；导出与恢复项目依赖。')
        row = QHBoxLayout()
        detect = QPushButton('↻ 检测开发环境')
        detect.clicked.connect(self.detect_requested.emit)
        row.addWidget(detect)
        row.addStretch(1)
        layout.addLayout(row)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['工具', '状态', '版本 / 路径'])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(QLabel('导出配置：'))
        export_py = QPushButton('pip freeze → requirements.txt')
        export_py.clicked.connect(lambda: self.export_requested.emit('Python'))
        row.addWidget(export_py)
        export_conda = QPushButton('Conda → environment.yml')
        export_conda.clicked.connect(lambda: self.export_requested.emit('Conda'))
        row.addWidget(export_conda)
        row.addStretch(1)
        layout.addLayout(row)
        restore = QHBoxLayout()
        restore.addWidget(QLabel('恢复配置：'))
        self.manifest = QComboBox()
        self.manifest.setMinimumWidth(220)
        restore.addWidget(self.manifest)
        restore_btn = QPushButton('恢复选中的依赖（需确认）')
        restore_btn.clicked.connect(lambda: self.restore_requested.emit(self.manifest.currentText()))
        restore.addWidget(restore_btn)
        restore.addStretch(1)
        layout.addLayout(restore)
        note = QLabel('注意：依赖安装可能运行第三方构建脚本；只对信任的项目执行。')
        note.setObjectName('mutedLabel')
        layout.addWidget(note)

    def set_environment(self, result: dict) -> None:
        self.table.setRowCount(len(result))
        for row, (name, item) in enumerate(result.items()):
            for col, value in enumerate((name, '✓ Installed' if item['installed'] else '— Not found', item['version'] or item['executable'])):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def set_manifests(self, names: list[str]) -> None:
        self.manifest.clear()
        self.manifest.addItems(names)
