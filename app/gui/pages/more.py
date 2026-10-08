"""Extra tools page: UI emits intentions; controller owns every operation."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QLineEdit,
                              QPushButton, QComboBox, QCheckBox, QPlainTextEdit)
from app.services.ignore import PRESETS
from .common import page_layout


class MoreToolsPage(QWidget):
    github_remotes_requested = Signal()
    github_templates_requested = Signal()
    github_clone_requested = Signal(str, str)
    github_create_requested = Signal(str, bool)
    ssh_detect_requested = Signal()
    ssh_generate_requested = Signal(str)
    ssh_test_requested = Signal(str)
    docker_requested = Signal(str, str)
    health_requested = Signal()
    ignore_requested = Signal(list)
    plugin_install_requested = Signal()
    plugin_toggle_requested = Signal(str, bool)
    plugin_list_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = page_layout(self, 'More Tools', 'GitHub · SSH · Docker · 健康检查 · Ignore · 插件管理')
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self._github_tab()
        self._ssh_tab()
        self._docker_tab()
        self._health_tab()
        self._ignore_tab()
        self._plugins_tab()

    def _tab(self, label: str):
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(12)
        self.tabs.addTab(parent, label)
        return layout

    def _button(self, layout, title, callback):
        btn = QPushButton(title)
        btn.clicked.connect(callback)
        layout.addWidget(btn)
        return btn

    def _github_tab(self):
        layout = self._tab('GitHub')
        self._button(layout, '检测 Git Remotes', self.github_remotes_requested.emit)
        self._button(layout, '生成 .github 模板', self.github_templates_requested.emit)
        layout.addWidget(QLabel('Clone URL (HTTPS 或 SSH)'))
        self.clone_url = QLineEdit()
        self.clone_url.setPlaceholderText('https://github.com/organization/repository.git')
        layout.addWidget(self.clone_url)
        layout.addWidget(QLabel('克隆目标完整目录（必须不存在）'))
        self.clone_dest = QLineEdit()
        layout.addWidget(self.clone_dest)
        self._button(layout, 'Clone', lambda: self.github_clone_requested.emit(self.clone_url.text().strip(), self.clone_dest.text().strip()))
        layout.addWidget(QLabel('使用本机 gh CLI 创建远程仓库（需事先登录）'))
        self.repo_name = QLineEdit()
        self.repo_name.setPlaceholderText('new-repository')
        layout.addWidget(self.repo_name)
        self.repo_private = QCheckBox('Private repository')
        self.repo_private.setChecked(True)
        layout.addWidget(self.repo_private)
        self._button(layout, 'gh repo create', lambda: self.github_create_requested.emit(self.repo_name.text().strip(), self.repo_private.isChecked()))
        layout.addStretch(1)

    def _ssh_tab(self):
        layout = self._tab('SSH')
        self.ssh_keys = QPlainTextEdit()
        self.ssh_keys.setReadOnly(True)
        self.ssh_keys.setPlaceholderText('点击检测后显示 .pub 公钥文件路径；不读取私钥。')
        layout.addWidget(self.ssh_keys)
        self._button(layout, '检测 SSH 公钥', self.ssh_detect_requested.emit)
        self.key_name = QLineEdit('id_ed25519_dev_assistant')
        layout.addWidget(self.key_name)
        self._button(layout, '生成 ED25519 Key（不覆盖已有密钥）', lambda: self.ssh_generate_requested.emit(self.key_name.text().strip()))
        row = QHBoxLayout()
        for host in ('GitHub', 'GitLab'):
            btn = QPushButton('测试 ' + host)
            btn.clicked.connect(lambda _, h=host: self.ssh_test_requested.emit(h))
            row.addWidget(btn)
        layout.addLayout(row)
        layout.addStretch(1)

    def _docker_tab(self):
        layout = self._tab('Docker')
        row = QHBoxLayout()
        for title, action in [('Version', 'version'), ('Compose Version', 'compose_version'),
                              ('Containers', 'containers'), ('Images', 'images'), ('Compose Up', 'compose_up')]:
            btn = QPushButton(title)
            btn.clicked.connect(lambda _, a=action: self.docker_requested.emit(a, ''))
            row.addWidget(btn)
        layout.addLayout(row)
        layout.addWidget(QLabel('容器名 / ID（用于 Start / Stop）'))
        self.container_name = QLineEdit()
        layout.addWidget(self.container_name)
        row2 = QHBoxLayout()
        for title, action in [('Start', 'start'), ('Stop', 'stop')]:
            btn = QPushButton(title)
            btn.clicked.connect(lambda _, a=action: self.docker_requested.emit(a, self.container_name.text().strip()))
            row2.addWidget(btn)
        layout.addLayout(row2)
        layout.addWidget(QLabel('Docker Build 镜像标签'))
        self.image_tag = QLineEdit()
        self.image_tag.setPlaceholderText('my-app:latest')
        layout.addWidget(self.image_tag)
        self._button(layout, 'Docker Build', lambda: self.docker_requested.emit('build', self.image_tag.text().strip()))
        layout.addStretch(1)

    def _health_tab(self):
        layout = self._tab('Project Health')
        self._button(layout, '运行项目健康检查', self.health_requested.emit)
        self.health_output = QPlainTextEdit()
        self.health_output.setReadOnly(True)
        layout.addWidget(self.health_output)

    def _ignore_tab(self):
        layout = self._tab('Ignore Generator')
        self.ignore_checks = {}
        for name, patterns in PRESETS.items():
            cb = QCheckBox(name + '    (' + ', '.join(patterns[:3]) + ')')
            layout.addWidget(cb)
            self.ignore_checks[name] = cb
        self._button(layout, '合并选中规则到 .gitignore',
                     lambda: self.ignore_requested.emit([name for name, c in self.ignore_checks.items() if c.isChecked()]))
        layout.addStretch(1)

    def _plugins_tab(self):
        layout = self._tab('Plugins')
        layout.addWidget(QLabel('插件从本地文件夹安装；启用状态保存在 SQLite，不自动执行不受信任代码。'))
        self.plugin_list = QPlainTextEdit()
        self.plugin_list.setReadOnly(True)
        layout.addWidget(self.plugin_list)
        self._button(layout, '刷新插件列表', self.plugin_list_requested.emit)
        self._button(layout, '从文件夹安装插件', self.plugin_install_requested.emit)
        layout.addWidget(QLabel('插件名称'))
        self.plugin_name = QLineEdit()
        layout.addWidget(self.plugin_name)
        row = QHBoxLayout()
        for value, title in ((True, '启用'), (False, '禁用')):
            btn = QPushButton(title)
            btn.clicked.connect(lambda _, enabled=value: self.plugin_toggle_requested.emit(self.plugin_name.text().strip(), enabled))
            row.addWidget(btn)
        layout.addLayout(row)
