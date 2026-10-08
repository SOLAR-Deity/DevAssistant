"""Git functionality; all subprocess calls delegate to CommandRunner."""
from __future__ import annotations
from pathlib import Path
import re
from app.core.runner import CommandRunner, CommandResult


class GitService:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def execute(self, repo: str | Path, *args: str, timeout: int = 90) -> CommandResult:
        folder = Path(repo).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError(f'Project directory not found: {folder}')
        return self.runner.run(['git', *args], cwd=folder, timeout=timeout)

    def init(self, repo: str) -> CommandResult:
        return self.execute(repo, 'init')

    def status(self, repo: str) -> CommandResult:
        return self.execute(repo, 'status', '--short', '--branch')

    def details(self, repo: str) -> dict:
        status = self.execute(repo, 'status', '--porcelain=v1', '-z')
        if not status.ok:
            return {'ok': False, 'error': status.stderr or status.stdout, 'branch': '-', 'files': []}
        branch = self.execute(repo, 'branch', '--show-current')
        files = []
        parts = status.stdout.split('\0')
        i = 0
        while i < len(parts):
            line = parts[i]
            i += 1
            if not line:
                continue
            code, name = line[:2], line[3:]
            if ('R' in code or 'C' in code) and i < len(parts) and parts[i]:
                i += 1  # porcelain -z: original path is a second NUL field
            files.append({'code': code, 'path': name})
        return {'ok': True, 'branch': branch.stdout.strip() or '(detached)', 'files': files}

    def diff(self, repo: str, path: str | None = None, staged: bool = False) -> CommandResult:
        args = ['diff', '--no-ext-diff']
        if staged:
            args.append('--cached')
        if path:
            args.extend(['--', path])
        return self.execute(repo, *args)

    def add(self, repo: str, paths: list[str] | None = None) -> CommandResult:
        if not paths:
            return self.execute(repo, 'add', '-A')
        return self.execute(repo, 'add', '--', *paths)

    def commit(self, repo: str, message: str) -> CommandResult:
        if not message.strip():
            raise ValueError('提交信息不能为空')
        return self.execute(repo, 'commit', '-m', message.strip(), timeout=120)

    def push(self, repo: str) -> CommandResult:
        return self.execute(repo, 'push', timeout=180)

    def pull(self, repo: str) -> CommandResult:
        return self.execute(repo, 'pull', timeout=180)

    def fetch(self, repo: str) -> CommandResult:
        return self.execute(repo, 'fetch', '--all', timeout=180)

    def branch(self, repo: str, name: str | None = None) -> CommandResult:
        return self.execute(repo, 'branch', name) if name else self.execute(repo, 'branch', '-a')

    def checkout(self, repo: str, name: str) -> CommandResult:
        return self.execute(repo, 'checkout', name)

    def merge(self, repo: str, name: str) -> CommandResult:
        return self.execute(repo, 'merge', name, timeout=180)

    def tag(self, repo: str, name: str) -> CommandResult:
        return self.execute(repo, 'tag', name)

    def discard_tracked(self, repo: str) -> CommandResult:
        """Only tracked changes; caller must confirm; never deletes untracked files."""
        return self.execute(repo, 'restore', '--worktree', '--', '.')

    def remotes(self, repo: str) -> CommandResult:
        return self.execute(repo, 'remote', '-v')

    def log(self, repo: str) -> CommandResult:
        return self.execute(repo, 'log', '--oneline', '--decorate', '--graph', '-n', '50')

    def unstage(self, repo: str, paths: list[str]) -> CommandResult:
        if not paths:
            raise ValueError('请选择需要取消暂存的文件')
        return self.execute(repo, 'restore', '--staged', '--', *paths)

    def stash_push(self, repo: str) -> CommandResult:
        return self.execute(repo, 'stash', 'push', '-m', 'Dev Assistant stash')

    def stash_pop(self, repo: str) -> CommandResult:
        return self.execute(repo, 'stash', 'pop')

    def remote_add(self, repo: str, name: str, url: str) -> CommandResult:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name):
            raise ValueError('无效远程仓库名称')
        if not url or '\n' in url or re.search(r'(?i)^https?://[^/]*@', url):
            raise ValueError('远程地址无效；不要在 URL 中包含账号密码')
        return self.execute(repo, 'remote', 'add', name, url)

    def remote_remove(self, repo: str, name: str) -> CommandResult:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name):
            raise ValueError('无效远程仓库名称')
        return self.execute(repo, 'remote', 'remove', name)

    def config_get(self, repo: str, key: str, global_scope: bool = False) -> CommandResult:
        if key not in ('user.name', 'user.email'):
            raise ValueError('只支持读取用户身份配置')
        return self.execute(repo, 'config', *(['--global'] if global_scope else []), key)

    def config_set(self, repo: str, key: str, value: str,
                   global_scope: bool = False) -> CommandResult:
        if key not in ('user.name', 'user.email') or not value.strip() or '\n' in value:
            raise ValueError('无效用户身份配置')
        return self.execute(repo, 'config', *(['--global'] if global_scope else []), key, value)
