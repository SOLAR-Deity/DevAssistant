"""Presentation-only Git source control page."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
                              QPlainTextEdit, QSplitter, QListWidget, QListWidgetItem,
                              QInputDialog, QGridLayout, QAbstractItemView)
from .common import page_layout


class GitPage(QWidget):
    refresh_requested = Signal()
    commit_requested = Signal(str)
    push_requested = Signal()
    pull_requested = Signal()
    fetch_requested = Signal()
    stage_all_requested = Signal()
    stage_selected_requested = Signal(list)
    unstage_selected_requested = Signal(list)
    history_requested = Signal()
    stash_requested = Signal()
    stash_pop_requested = Signal()
    remotes_requested = Signal()
    remote_add_requested = Signal(str, str)
    remote_remove_requested = Signal(str)
    config_requested = Signal(str, str)
    config_set_requested = Signal(str, str, str)
    discard_all_requested = Signal()
    diff_requested = Signal(str)
    branch_action_requested = Signal(str, str)
    init_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = page_layout(self, 'Source Control: Git', '真实 Git 工作区状态 · 所有操作通过 Command Runner 执行')
        self.branch_label = QLabel('Current Branch: —')
        self.branch_label.setObjectName('mutedLabel')
        layout.addWidget(self.branch_label)
        top = QHBoxLayout()
        for title, signal in [('初始化 Git', self.init_requested), ('刷新状态', self.refresh_requested),
                              ('Fetch', self.fetch_requested), ('Pull', self.pull_requested), ('Push', self.push_requested)]:
            btn = QPushButton(title)
            btn.clicked.connect(signal.emit)
            top.addWidget(btn)
        top.addStretch(1)
        layout.addLayout(top)
        operations = QHBoxLayout()
        for label, action in [('查看分支', 'list'), ('创建分支', 'create'), ('切换分支', 'checkout'),
                              ('合并分支', 'merge'), ('创建 Tag', 'tag')]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, a=action: self._branch(a))
            operations.addWidget(btn)
        operations.addStretch(1)
        layout.addLayout(operations)
        extras = QGridLayout()
        extras.setHorizontalSpacing(8)
        buttons = [
            ('提交历史', self.history_requested.emit),
            ('Stash', self.stash_requested.emit),
            ('Stash Pop', self.stash_pop_requested.emit),
            ('Remote 列表', self.remotes_requested.emit),
            ('添加 Remote', self._add_remote),
            ('删除 Remote', self._remove_remote),
            ('Git 用户信息', self._get_git_config),
            ('设置 Git 用户', self._set_git_config),
        ]
        for n, (caption, callback) in enumerate(buttons):
            button = QPushButton(caption)
            button.clicked.connect(callback)
            extras.addWidget(button, n // 4, n % 4)
        layout.addLayout(extras)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 10, 0)
        self.commit_input = QPlainTextEdit()
        self.commit_input.setPlaceholderText('提交信息（不能为空）')
        self.commit_input.setMaximumHeight(72)
        ll.addWidget(self.commit_input)
        commit = QPushButton('✓ Commit Staged Changes')
        commit.clicked.connect(lambda: self.commit_requested.emit(self.commit_input.toPlainText()))
        ll.addWidget(commit)
        row = QHBoxLayout()
        self.changes_label = QLabel('CHANGES (0)')
        row.addWidget(self.changes_label)
        row.addStretch(1)
        stage = QPushButton('＋ Stage All')
        stage.clicked.connect(self.stage_all_requested.emit)
        row.addWidget(stage)
        stage_selected = QPushButton('Stage Selected')
        stage_selected.clicked.connect(lambda: self.stage_selected_requested.emit(self.selected_files()))
        row.addWidget(stage_selected)
        unstage = QPushButton('Unstage Selected')
        unstage.clicked.connect(lambda: self.unstage_selected_requested.emit(self.selected_files()))
        row.addWidget(unstage)
        discard = QPushButton('↶ Discard Tracked')
        discard.clicked.connect(self.discard_all_requested.emit)
        row.addWidget(discard)
        ll.addLayout(row)
        self.file_codes: dict[str, str] = {}
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.itemClicked.connect(self._file_clicked)
        ll.addWidget(self.file_list)
        split.addWidget(left)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        self.diff_label = QLabel('Diff Preview')
        rl.addWidget(self.diff_label)
        self.diff_content = QPlainTextEdit()
        self.diff_content.setReadOnly(True)
        self.diff_content.setFont(QFont('Consolas', 10))
        self.diff_content.setPlaceholderText('选择改动的文件后显示差异。')
        rl.addWidget(self.diff_content)
        split.addWidget(right)
        split.setSizes([370, 500])
        layout.addWidget(split)

    def set_status(self, info: dict) -> None:
        self.file_list.clear()
        self.file_codes.clear()
        self.diff_content.clear()
        self.branch_label.setText('Current Branch: ' + info.get('branch', '—') if info.get('ok') else 'Git 未初始化 / 无法读取')
        files = info.get('files', [])
        self.changes_label.setText(f'CHANGES ({len(files)})')
        for file in files:
            self.file_codes[file['path']] = file['code']
            item = QListWidgetItem(f"[{file['code']}]  {file['path']}")
            item.setData(Qt.ItemDataRole.UserRole, file['path'])
            self.file_list.addItem(item)
        if not info.get('ok'):
            self.diff_content.setPlainText(info.get('error', 'Git 仓库不可用'))

    def set_diff(self, filename: str, diff: str) -> None:
        self.diff_label.setText('Diff Preview: ' + filename)
        self.diff_content.setPlainText(diff or '(没有可显示的未暂存差异；文件可能已暂存或尚未跟踪)')

    def clear_commit(self) -> None:
        self.commit_input.clear()

    def _file_clicked(self, item: QListWidgetItem) -> None:
        self.diff_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    def _branch(self, action: str) -> None:
        if action == 'list':
            self.branch_action_requested.emit(action, '')
            return
        captions = {'create': '新分支名称', 'checkout': '切换到分支', 'merge': '合并的分支名称', 'tag': 'Tag 名称'}
        value, ok = QInputDialog.getText(self, 'Git Branch / Tag', captions[action])
        if ok and value.strip():
            self.branch_action_requested.emit(action, value.strip())

    def selected_files(self) -> list[str]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.file_list.selectedItems()]

    def _add_remote(self) -> None:
        name, ok = QInputDialog.getText(self, '添加 Remote', 'Remote 名称（如 origin）')
        if not ok or not name.strip():
            return
        url, ok = QInputDialog.getText(self, '添加 Remote', '远程仓库 URL（不能带密码）')
        if ok and url.strip():
            self.remote_add_requested.emit(name.strip(), url.strip())

    def _get_git_config(self) -> None:
        self.config_requested.emit('user.name', 'local')
        self.config_requested.emit('user.email', 'local')

    def _remove_remote(self) -> None:
        name, ok = QInputDialog.getText(self, '删除 Remote', 'Remote 名称（如 origin）')
        if ok and name.strip():
            self.remote_remove_requested.emit(name.strip())

    def _set_git_config(self) -> None:
        key, ok = QInputDialog.getItem(self, '设置 Git 身份', '要设置的项目',
                                       ['user.name', 'user.email'], 0, False)
        if not ok:
            return
        scope, ok = QInputDialog.getItem(self, '设置 Git 身份', '配置作用域',
                                         ['当前项目 (Local)', '全局 (Global)'], 0, False)
        if not ok:
            return
        value, ok = QInputDialog.getText(self, '设置 Git 身份', key)
        if ok and value.strip():
            self.config_set_requested.emit(key, value.strip(),
                                           'global' if scope.startswith('全局') else 'local')
