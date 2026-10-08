from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QHBoxLayout, QComboBox
from .common import page_layout


class GeneratorPage(QWidget):
    browse_requested = Signal()
    generate_requested = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = page_layout(self, 'Project Generator', '创建标准结构：README、LICENSE、.gitignore、.env.example 和语言模板。')
        layout.addWidget(QLabel('项目父目录'))
        row = QHBoxLayout()
        self.parent_path = QLineEdit()
        self.parent_path.setPlaceholderText('选择用于创建新项目的目录')
        row.addWidget(self.parent_path)
        browse = QPushButton('浏览…')
        browse.clicked.connect(self.browse_requested.emit)
        row.addWidget(browse)
        layout.addLayout(row)
        layout.addWidget(QLabel('新项目名称'))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('my-awesome-project')
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel('模板类型'))
        self.kind = QComboBox()
        self.kind.addItems(['Python', 'Java', 'Node', 'AI'])
        layout.addWidget(self.kind)
        create = QPushButton('＋ 创建新项目')
        create.clicked.connect(lambda: self.generate_requested.emit(
            self.parent_path.text().strip(), self.name_input.text().strip(), self.kind.currentText()))
        layout.addWidget(create)
        note = QLabel('安全措施：如果目标路径已经存在，生成器将拒绝覆盖。')
        note.setObjectName('mutedLabel')
        layout.addWidget(note)
        layout.addStretch(1)
