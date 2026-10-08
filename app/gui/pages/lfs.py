from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLabel
from app.services.lfs import PRESETS
from .common import page_layout


class LFSPage(QWidget):
    detect_requested = Signal()
    install_requested = Signal()
    track_requested = Signal(list)
    attributes_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = page_layout(self, 'Git LFS', '大文件版本控制 · 预设追踪类型及 .gitattributes 生成')
        self.status = QLabel('尚未检测 Git LFS')
        self.status.setObjectName('summaryCard')
        layout.addWidget(self.status)
        row = QHBoxLayout()
        detect = QPushButton('检测 Git LFS')
        detect.clicked.connect(self.detect_requested.emit)
        row.addWidget(detect)
        install = QPushButton('git lfs install --local')
        install.clicked.connect(self.install_requested.emit)
        row.addWidget(install)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(QLabel('TRACK TYPES'))
        self.checks = {}
        for name, patterns in PRESETS.items():
            check = QCheckBox(f'{name}   ·   {", ".join(patterns)}')
            self.checks[name] = check
            layout.addWidget(check)
        row = QHBoxLayout()
        track = QPushButton('追踪选中类型（git lfs track）')
        track.clicked.connect(lambda: self.track_requested.emit(self.groups()))
        row.addWidget(track)
        generate = QPushButton('只生成 .gitattributes')
        generate.clicked.connect(lambda: self.attributes_requested.emit(self.groups()))
        row.addWidget(generate)
        row.addStretch(1)
        layout.addLayout(row)
        note = QLabel('提示：Git LFS 追踪仅影响后续 Git 添加的文件，已提交的大文件需要单独迁移。')
        note.setObjectName('mutedLabel')
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

    def groups(self) -> list[str]:
        return [name for name, check in self.checks.items() if check.isChecked()]

    def set_status(self, text: str) -> None:
        self.status.setText(text)
