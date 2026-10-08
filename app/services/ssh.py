"""SSH public key discovery and managed generation; never read private keys."""
from __future__ import annotations
from pathlib import Path
import re
from app.core.runner import CommandRunner, CommandResult


class SSHService:
    HOSTS = {'GitHub': 'git@github.com', 'GitLab': 'git@gitlab.com'}

    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def public_keys(self) -> list[str]:
        directory = Path.home() / '.ssh'
        return [str(p) for p in sorted(directory.glob('*.pub')) if p.is_file()] if directory.is_dir() else []

    def generate(self, name: str = 'id_ed25519_dev_assistant') -> CommandResult:
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', name) or name.startswith('.'):
            raise ValueError('SSH Key 文件名无效')
        directory = Path.home() / '.ssh'
        directory.mkdir(mode=0o700, exist_ok=True)
        dest = directory / name
        if dest.exists() or Path(str(dest) + '.pub').exists():
            raise ValueError('密钥已存在，拒绝覆盖')
        return self.runner.run(['ssh-keygen', '-t', 'ed25519', '-f', str(dest), '-N', '',
                                '-C', 'dev-assistant'], timeout=30)

    def test(self, host: str) -> CommandResult:
        if host not in self.HOSTS:
            raise ValueError('不支持的 SSH 站点')
        # GitHub's successful auth test may return code 1 with success text.
        return self.runner.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                                '-o', 'ConnectTimeout=8', '-T', self.HOSTS[host]], timeout=20)
