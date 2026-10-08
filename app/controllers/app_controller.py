"""UI-to-services adapter. All blocking work runs outside the Qt GUI thread."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
import re
import json
import logging

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (QFileDialog, QInputDialog, QMessageBox, QDialog,
                              QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView)

from app.bootstrap import ApplicationServices
from app.core.runner import CommandResult, CommandEvent
from app.core.terminal_session import TerminalSession, needs_confirmation
from app.gui.main_window import MainWindow
from app.services.lfs import PRESETS

log = logging.getLogger(__name__)


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class ServiceTask(QRunnable):
    def __init__(self, work: Callable[[], object]):
        super().__init__()
        self.work = work
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            self.signals.done.emit(self.work())
        except Exception as exc:
            log.exception('Background task failed')
            self.signals.failed.emit(str(exc))


class AppController(QObject):
    command_event = Signal(object)
    def __init__(self, window: MainWindow, services: ApplicationServices):
        super().__init__(window)
        self.window = window
        self.s = services
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(4)
        self.tasks: set[ServiceTask] = set()
        self.terminal_session = TerminalSession()
        self.command_event.connect(self._on_command_event)
        self.s.runner.event_sink = self.command_event.emit
        self.active: str = str(self.s.store.setting('active_project', ''))
        self._connect()
        self.refresh_projects()
        self._load_settings()
        # Persist terminal ↑/↓ history across application restarts.
        rows = self.s.store.history(200)
        self.terminal_session.history = [r['command'] for r in reversed(rows) if r.get('source') == 'terminal']
        self.terminal_session.history_index = len(self.terminal_session.history)
        learning = self.window.pages['learning']
        learning.set_catalog(self.s.learning.list_commands(), self.s.learning.explain)
        self.refresh_git()

    def _connect(self) -> None:
        win = self.window
        pages = win.pages
        win.project_changed.connect(self.select_project)
        win.refresh_requested.connect(self.refresh_current)
        win.theme_toggle_requested.connect(self.toggle_theme)
        win.search_requested.connect(self.search)
        win.terminal.history_requested.connect(self.show_history)
        win.terminal.command_submitted.connect(self.run_terminal_command)
        win.terminal.cancel_requested.connect(self.cancel_command)
        win.terminal.history_previous.connect(self._previous_command)
        win.terminal.history_next.connect(self._next_command)
        dashboard = pages['dashboard']
        dashboard.add_project_requested.connect(self.add_project)
        dashboard.open_project_requested.connect(self.select_project)
        dashboard.sync_project_requested.connect(self.pull_project)
        projects = pages['projects']
        projects.add_requested.connect(self.add_project)
        projects.select_requested.connect(self.select_project)
        projects.remove_requested.connect(self.remove_project)
        git = pages['git']
        git.init_requested.connect(lambda: self.git_command('init'))
        git.refresh_requested.connect(self.refresh_git)
        git.stage_all_requested.connect(lambda: self.git_command('add'))
        git.stage_selected_requested.connect(self.stage_selected)
        git.unstage_selected_requested.connect(self.unstage_selected)
        git.history_requested.connect(lambda: self.git_command('log'))
        git.stash_requested.connect(lambda: self.git_command('stash_push'))
        git.stash_pop_requested.connect(self.stash_pop)
        git.remotes_requested.connect(lambda: self.git_command('remotes'))
        git.remote_add_requested.connect(self.remote_add)
        git.remote_remove_requested.connect(self.remote_remove)
        git.config_requested.connect(self.config_get)
        git.config_set_requested.connect(self.config_set)
        git.commit_requested.connect(self.commit)
        git.push_requested.connect(lambda: self.git_command('push'))
        git.pull_requested.connect(lambda: self.git_command('pull'))
        git.fetch_requested.connect(lambda: self.git_command('fetch'))
        git.discard_all_requested.connect(self.discard_all)
        git.diff_requested.connect(self.show_diff)
        git.branch_action_requested.connect(self.branch_action)
        env = pages['environment']
        env.detect_requested.connect(self.detect_environment)
        env.export_requested.connect(self.export_environment)
        env.restore_requested.connect(self.restore_environment)
        lfs = pages['lfs']
        lfs.detect_requested.connect(self.detect_lfs)
        lfs.install_requested.connect(self.install_lfs)
        lfs.track_requested.connect(self.track_lfs)
        lfs.attributes_requested.connect(self.attributes_lfs)
        pages['learning'].example_requested.connect(
            lambda example: win.terminal.append_output('示例（未执行）：' + example) if example else None)
        generator = pages['generator']
        generator.browse_requested.connect(self.browse_parent)
        generator.generate_requested.connect(self.generate_project)
        more = pages['more']
        more.github_remotes_requested.connect(lambda: self.github_command('remotes'))
        more.github_templates_requested.connect(lambda: self.github_command('templates'))
        more.github_clone_requested.connect(lambda url, target: self.github_command('clone', url, target))
        more.github_create_requested.connect(lambda name, private: self.github_command('create', name, private))
        more.ssh_detect_requested.connect(self.ssh_detect)
        more.ssh_generate_requested.connect(self.ssh_generate)
        more.ssh_test_requested.connect(self.ssh_test)
        more.docker_requested.connect(self.docker_command)
        more.health_requested.connect(self.check_health)
        more.ignore_requested.connect(self.generate_ignore)
        more.plugin_install_requested.connect(self.plugin_install)
        more.plugin_list_requested.connect(self.plugin_list)
        more.plugin_toggle_requested.connect(self.plugin_toggle)
        settings = pages['settings']
        settings.theme_changed.connect(self.set_theme)
        settings.history_requested.connect(self.show_history)
        settings.learning_mode_changed.connect(self.set_learning_mode)

    def _command_source(self, caption: str) -> str:
        caption = caption.lower()
        if caption.startswith('git lfs'):
            return 'lfs_ui'
        if caption.startswith('git '):
            return 'git_ui'
        if caption.startswith('docker'):
            return 'docker_ui'
        if caption.startswith('ssh'):
            return 'ssh_ui'
        if caption.startswith('gh ') or caption.startswith('github'):
            return 'github_ui'
        if 'environment' in caption or 'requirements' in caption or 'conda' in caption:
            return 'environment_ui'
        return 'system'

    @Slot(object)
    def _on_command_event(self, event: CommandEvent) -> None:
        terminal = self.window.terminal
        if event.kind == 'started':
            terminal.append_command(event.command, event.cwd, event.source)
            if event.source == 'git_ui' and self.s.store.setting('learning_mode', True):
                match = re.match(r'^git\s+([a-z-]+)', event.command, re.I)
                if match:
                    info = self.s.learning.explain('git ' + match.group(1).lower())
                    if info.get('description'):
                        terminal.append_output('  ⓘ ' + info['description'])
        elif event.kind in ('stdout', 'stderr'):
            terminal.append_chunk(event.text, event.kind == 'stderr')
        elif event.kind == 'finished':
            terminal.append_exit(event.exit_code if event.exit_code is not None else -1,
                                 event.duration_seconds)

    def _task(self, caption: str, work: Callable[[], object],
              callback: Callable[[object], None] | None = None,
              *, quiet: bool = False, project: str = '',
              source: str | None = None) -> None:
        self.window.statusBar().showMessage('正在执行 · ' + caption)
        command_source = source or self._command_source(caption)

        def in_context():
            with self.s.runner.from_source(command_source):
                return work()

        task = ServiceTask(in_context)
        self.tasks.add(task)

        def completed(value: object) -> None:
            self.tasks.discard(task)
            if not quiet:
                self._write_result(value)
            try:
                if callback:
                    callback(value)
            except Exception as exc:
                log.exception('UI result handler failed')
                self.window.terminal.append_output(str(exc), True)
            self.window.statusBar().showMessage('就绪')

        def failed(message: str) -> None:
            self.tasks.discard(task)
            self.window.terminal.append_output('执行失败: ' + message, True)
            self.window.statusBar().showMessage('执行失败')

        task.signals.done.connect(completed)
        task.signals.failed.connect(failed)
        self.pool.start(task)

    def _write_result(self, result: object) -> None:
        # Commands were already streamed and audited by the unified runner.
        if isinstance(result, CommandResult):
            return
        if isinstance(result, list) and all(isinstance(x, CommandResult) for x in result):
            return
        if isinstance(result, (dict, list)):
            self.window.terminal.append_output(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:12000])
        elif result is not None:
            self.window.terminal.append_output(str(result))

    def _previous_command(self, current: str) -> None:
        self.window.terminal.set_history_input(self.terminal_session.previous(current))

    def _next_command(self) -> None:
        self.window.terminal.set_history_input(self.terminal_session.next())

    def cancel_command(self) -> None:
        if not self.s.runner.cancel_active():
            self.window.terminal.append_output('没有正在执行的命令。')

    def run_terminal_command(self, text: str) -> None:
        if needs_confirmation(text):
            if QMessageBox.warning(self.window, '确认危险命令',
                    '这条命令可能不可逆地删除或覆盖数据：\n' + text + '\n确定执行吗？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                self.window.terminal.append_output('命令已取消。')
                return
        previous_cwd = self.terminal_session.cwd
        try:
            action = self.terminal_session.plan(text)
        except ValueError as exc:
            self.window.terminal.append_command(text, str(previous_cwd), 'terminal')
            self.window.terminal.append_output(str(exc), True)
            self.s.store.record(CommandResult(text, '', str(exc), 1, str(previous_cwd)), 'terminal')
            return
        if action.kind in ('clear', 'builtin'):
            if action.kind == 'clear':
                self.window.terminal.clear()
            else:
                self.window.terminal.append_command(text, str(previous_cwd), 'terminal')
                self.window.terminal.append_output(action.output)
            self.s.store.record(CommandResult(text, action.output, '', 0, str(previous_cwd)), 'terminal')
            self.window.terminal.set_cwd(str(self.terminal_session.cwd))
            return
        self._task(text, lambda: self.s.runner.run(action.argv, cwd=action.cwd,
                   timeout=600, display_command=text), source='terminal')

    def set_learning_mode(self, enabled: bool) -> None:
        self.s.store.set_setting('learning_mode', enabled)

    def _active(self) -> str | None:
        if self.active and Path(self.active).is_dir():
            return self.active
        QMessageBox.information(self.window, '选择项目', '请先添加并选择一个本地项目。')
        self.window.navigate('projects')
        return None

    def refresh_projects(self) -> None:
        projects = self.s.store.projects()
        paths = {p['path'] for p in projects}
        if self.active not in paths:
            self.active = ''
            self.s.store.set_setting('active_project', '')
        self.window.set_projects(projects, self.active)
        self.window.pages['environment'].set_manifests(self.s.environment.project_manifests(self.active) if self.active else [])

    def add_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self.window, '选择项目文件夹')
        if not folder:
            return
        language, ok = QInputDialog.getItem(self.window, '项目语言', '主要语言',
                                             ['Python', 'Java', 'Node', 'AI', 'Other'], 0, False)
        if not ok:
            return
        try:
            result = self.s.store.add_project(folder, language)
            self.select_project(result['path'])
        except Exception as exc:
            QMessageBox.warning(self.window, '项目添加失败', str(exc))

    def select_project(self, path: str) -> None:
        if path not in {p['path'] for p in self.s.store.projects()}:
            return
        self.active = path
        self.s.store.set_setting('active_project', path)
        self.refresh_projects()
        self.window.statusBar().showMessage('当前项目：' + path)
        self.terminal_session.change_to_project(path)
        self.window.terminal.set_cwd(str(self.terminal_session.cwd))
        self.refresh_git()

    def remove_project(self, path: str) -> None:
        reply = QMessageBox.question(self.window, '移除项目', '只移除列表记录？磁盘文件不会删除。')
        if reply == QMessageBox.StandardButton.Yes:
            self.s.store.remove_project(path)
            self.refresh_projects()
            self.refresh_git()

    def refresh_current(self) -> None:
        self.refresh_projects()
        key = next((k for k, widget in self.window.pages.items() if widget is self.window.stack.currentWidget()), 'dashboard')
        if key == 'environment':
            self.detect_environment()
        elif key == 'lfs':
            self.detect_lfs()
        elif key == 'more':
            self.plugin_list()
        else:
            self.refresh_git()

    def refresh_git(self) -> None:
        path = self.active
        if not path or not Path(path).is_dir():
            self.window.pages['git'].set_status({'ok': False, 'branch': '-', 'files': [], 'error': '请先选择项目'})
            return
        self._task('git status --porcelain', lambda: self.s.git.details(path),
                   lambda value: self.window.pages['git'].set_status(value), quiet=True, project=path)

    def git_command(self, method: str, *args) -> None:
        folder = self._active()
        if not folder:
            return
        func = getattr(self.s.git, method)
        self._task('git ' + method, lambda: func(folder, *args),
                   lambda value: self.refresh_git() if isinstance(value, CommandResult) and value.ok else None,
                   project=folder)

    def stage_selected(self, paths: list[str]) -> None:
        if not paths:
            QMessageBox.information(self.window, 'Stage Selected', '请先选择文件。')
            return
        self.git_command('add', paths)

    def unstage_selected(self, paths: list[str]) -> None:
        if not paths:
            QMessageBox.information(self.window, 'Unstage Selected', '请先选择文件。')
            return
        self.git_command('unstage', paths)

    def stash_pop(self) -> None:
        if QMessageBox.question(self.window, '应用 Stash',
            'git stash pop 可能导致冲突。确定继续吗？') == QMessageBox.StandardButton.Yes:
            self.git_command('stash_pop')

    def remote_add(self, name: str, url: str) -> None:
        folder = self._active()
        if folder:
            self._task('git remote add', lambda: self.s.git.remote_add(folder, name, url),
                       project=folder)

    def remote_remove(self, name: str) -> None:
        folder = self._active()
        if folder and QMessageBox.question(self.window, '删除 Remote',
                f'确定删除 Remote：{name}？（不会删除远程仓库）') == QMessageBox.StandardButton.Yes:
            self._task('git remote remove', lambda: self.s.git.remote_remove(folder, name),
                       project=folder)

    def config_set(self, key: str, value: str, scope: str) -> None:
        folder = self._active()
        if not folder:
            return
        if scope == 'global' and QMessageBox.question(self.window, '全局 Git 配置',
                '将修改此电脑所有仓库使用的 Git 用户身份，确定吗？') != QMessageBox.StandardButton.Yes:
            return
        self._task('git config ' + key,
                   lambda: self.s.git.config_set(folder, key, value, scope == 'global'),
                   project=folder)

    def config_get(self, key: str, scope: str) -> None:
        folder = self._active()
        if folder:
            self._task('git config ' + key,
                       lambda: self.s.git.config_get(folder, key, scope == 'global'),
                       project=folder)

    def commit(self, message: str) -> None:
        if not message.strip():
            QMessageBox.warning(self.window, '提交失败', '提交信息不能为空。')
            return
        folder = self._active()
        if not folder:
            return
        def finish(result):
            if result.ok:
                self.window.pages['git'].clear_commit()
                self.refresh_git()
        self._task('git commit -m ' + repr(message.strip()),
                   lambda: self.s.git.commit(folder, message), finish, project=folder)

    def discard_all(self) -> None:
        folder = self._active()
        if not folder:
            return
        if QMessageBox.warning(self.window, '确认丢弃改动',
                               '将不可恢复地丢弃已跟踪文件的工作区改动（不删除未跟踪文件）。确定继续？',
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                               QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.git_command('discard_tracked')

    def branch_action(self, action: str, value: str) -> None:
        if action != 'list' and (not value or value.startswith('-') or '\n' in value):
            QMessageBox.warning(self.window, '无效名称', '分支或 Tag 名称无效。')
            return
        if action == 'list':
            self.git_command('branch')
        else:
            method = {'create': 'branch', 'checkout': 'checkout', 'merge': 'merge', 'tag': 'tag'}.get(action)
            if method:
                self.git_command(method, value)

    def show_diff(self, filename: str) -> None:
        folder = self._active()
        if not folder:
            return
        info = self.window.pages['git'].file_codes.get(filename, '')
        staged = bool(info and info[0] not in (' ', '?'))
        self._task('git diff -- ' + filename,
                   lambda: self.s.git.diff(folder, filename, staged=staged),
                   lambda r: self.window.pages['git'].set_diff(filename, r.stdout if r.ok else r.stderr),
                   quiet=True, project=folder)

    def pull_project(self, folder: str) -> None:
        self.select_project(folder)
        self.git_command('pull')

    def detect_environment(self) -> None:
        self._task('detect environment', self.s.environment.detect,
                   lambda info: self.window.pages['environment'].set_environment(info), quiet=True)

    def export_environment(self, kind: str) -> None:
        folder = self._active()
        if not folder:
            return
        func = self.s.environment.export_python if kind == 'Python' else self.s.environment.export_conda
        self._task('export ' + kind, lambda: func(folder),
                   lambda _: self.refresh_projects(), project=folder)

    def restore_environment(self, manifest: str) -> None:
        folder = self._active()
        if not folder or not manifest:
            return
        if QMessageBox.warning(self.window, '确认安装依赖',
                f'即将执行依赖恢复：{manifest}\n依赖构建可能执行第三方代码，请确认该项目可信。',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._task('restore ' + manifest,
                   lambda: self.s.environment.restore(folder, manifest), project=folder)

    def detect_lfs(self) -> None:
        self._task('git lfs version', self.s.lfs.detect,
                   lambda result: self.window.pages['lfs'].set_status(result.stdout.strip() if result.ok else 'Git LFS 未安装'),
                   project=self.active)

    def install_lfs(self) -> None:
        folder = self._active()
        if folder:
            self._task('git lfs install --local', lambda: self.s.lfs.install(folder), project=folder)

    def track_lfs(self, groups: list[str]) -> None:
        folder = self._active()
        if not folder or not groups:
            return
        patterns = [pattern for group in groups for pattern in PRESETS[group]]
        self._task('git lfs track ' + ', '.join(patterns),
                   lambda: self.s.lfs.track(folder, patterns), project=folder)

    def attributes_lfs(self, groups: list[str]) -> None:
        folder = self._active()
        if folder and groups:
            self._task('generate .gitattributes', lambda: self.s.lfs.generate_attributes(folder, groups), project=folder)

    def browse_parent(self) -> None:
        path = QFileDialog.getExistingDirectory(self.window, '选择项目父目录')
        if path:
            self.window.pages['generator'].parent_path.setText(path)

    def generate_project(self, parent: str, name: str, kind: str) -> None:
        if not parent or not name:
            QMessageBox.warning(self.window, '参数不足', '请填写父目录和项目名称。')
            return
        def finish(path):
            self.s.store.add_project(str(path), kind)
            self.select_project(str(path))
            self.window.navigate('projects')
        self._task('generate ' + kind + ' project',
                   lambda: self.s.generator.generate(parent, name, kind), finish)

    def github_command(self, method: str, *args) -> None:
        if method == 'clone':
            url, path = args
            if not url or not path:
                return
            self._task('git clone ' + url,
                       lambda: self.s.github.clone(url, path), project=str(Path(path).parent))
            return
        folder = self._active()
        if not folder:
            return
        if method == 'remotes':
            self._task('git remote -v', lambda: self.s.github.remotes(folder), project=folder)
        elif method == 'templates':
            self._task('generate .github templates', lambda: self.s.github.generate_files(folder), project=folder)
        elif method == 'create':
            name, private = args
            if not name:
                return
            if QMessageBox.question(self.window, 'GitHub 仓库创建',
                                    f'将使用本机 gh 认证创建仓库 {name}。继续？') == QMessageBox.StandardButton.Yes:
                self._task('gh repo create ' + name, lambda: self.s.github.create_repository(folder, name, private), project=folder)

    def ssh_detect(self) -> None:
        keys = self.s.ssh.public_keys()
        self.window.pages['more'].ssh_keys.setPlainText('\n'.join(keys) if keys else '未找到公钥。')

    def ssh_generate(self, name: str) -> None:
        if QMessageBox.question(self.window, '生成 SSH Key',
                                '将创建新的 ED25519 密钥（本版本不设置口令）。私钥仅留在本机，确定吗？') == QMessageBox.StandardButton.Yes:
            self._task('ssh-keygen -t ed25519', lambda: self.s.ssh.generate(name),
                       lambda _: self.ssh_detect())

    def ssh_test(self, host: str) -> None:
        self._task('ssh -T ' + host, lambda: self.s.ssh.test(host))

    def docker_command(self, method: str, arg: str) -> None:
        folder = self.active
        actions = {
            'version': lambda: self.s.docker.version(),
            'compose_version': lambda: self.s.docker.compose_version(),
            'containers': lambda: self.s.docker.containers(),
            'images': lambda: self.s.docker.images(),
            'start': lambda: self.s.docker.start(arg),
            'stop': lambda: self.s.docker.stop(arg),
            'build': lambda: self.s.docker.build(folder, arg),
            'compose_up': lambda: self.s.docker.compose_up(folder),
        }
        if method not in actions:
            return
        if method in ('compose_up', 'build') and not self._active():
            return
        if method in ('start', 'stop', 'build') and not arg:
            QMessageBox.warning(self.window, '参数不足', '请填写容器名称或镜像 Tag。')
            return
        if method in ('start', 'stop', 'build', 'compose_up'):
            if QMessageBox.question(self.window, '确认 Docker 操作', f'确定执行 docker {method} 吗？') != QMessageBox.StandardButton.Yes:
                return
        self._task('docker ' + method, actions[method], project=folder)

    def check_health(self) -> None:
        folder = self._active()
        if not folder:
            return
        self._task('project health check', lambda: self.s.health.check(folder),
                   lambda info: self.window.pages['more'].health_output.setPlainText(
                       json.dumps(info, ensure_ascii=False, indent=2)), quiet=True, project=folder)

    def generate_ignore(self, groups: list[str]) -> None:
        folder = self._active()
        if folder and groups:
            self._task('generate .gitignore', lambda: self.s.ignore.generate(folder, groups), project=folder)

    def plugin_list(self) -> None:
        result = self.s.plugins.list_plugins()
        self.window.pages['more'].plugin_list.setPlainText(
            '\n'.join(f"{p['name']}  v{p['version']}  {'Enabled' if p['enabled'] else 'Disabled'}" for p in result)
            or '尚未安装本地插件。')

    def plugin_install(self) -> None:
        path = QFileDialog.getExistingDirectory(self.window, '选择本地插件文件夹（manifest.json + main.py）')
        if path:
            self._task('install plugin from local folder', lambda: self.s.plugins.install(path),
                       lambda _: self.plugin_list())

    def plugin_toggle(self, name: str, enabled: bool) -> None:
        if not name:
            return
        try:
            self.s.plugins.set_enabled(name, enabled)
            self.plugin_list()
        except Exception as exc:
            QMessageBox.warning(self.window, '插件操作失败', str(exc))

    def _load_settings(self) -> None:
        current = self.s.store.setting('theme', 'Dark')
        settings = self.window.pages['settings'].theme
        settings.blockSignals(True)
        settings.setCurrentText(current)
        settings.blockSignals(False)
        self.window.apply_theme(current)
        enabled = bool(self.s.store.setting('learning_mode', True))
        cb = self.window.pages['settings'].learning_mode
        cb.blockSignals(True)
        cb.setChecked(enabled)
        cb.blockSignals(False)
        self.window.terminal.set_cwd(str(self.terminal_session.cwd))

    def set_theme(self, name: str) -> None:
        if name not in ('Dark', 'Light'):
            return
        self.s.store.set_setting('theme', name)
        self.window.apply_theme(name)

    def toggle_theme(self) -> None:
        current = self.s.store.setting('theme', 'Dark')
        theme = 'Light' if current == 'Dark' else 'Dark'
        self.window.pages['settings'].theme.setCurrentText(theme)

    def search(self, query: str) -> None:
        q = query.lower()
        aliases = {'project': 'projects', 'git': 'git', 'env': 'environment',
                   'lfs': 'lfs', 'learn': 'learning', 'docker': 'more',
                   'ssh': 'more', 'plugin': 'more', 'generate': 'generator'}
        found = next((key for alias, key in aliases.items() if alias in q), None)
        if found:
            self.window.navigate(found)
        elif query:
            self.window.statusBar().showMessage('未找到相关页面：' + query)

    def show_history(self) -> None:
        rows = self.s.store.history()
        dialog = QDialog(self.window)
        dialog.setWindowTitle('Terminal History · SQLite')
        dialog.resize(980, 480)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(rows), 6)
        table.setHorizontalHeaderLabels(['时间 (UTC)', '来源', '项目', '命令', '退出码', '耗时 (s)'])
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for r, data in enumerate(rows):
            for c, text in enumerate((data['created_at'], data['source'], data['project_path'], data['command'],
                                      str(data['exit_code']), str(data['duration_seconds']))):
                table.setItem(r, c, QTableWidgetItem(text))
        layout.addWidget(table)
        dialog.exec()
