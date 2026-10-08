"""GitHub helpers. Use git/gh installed credentials; never request or save passwords."""
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlparse
from app.core.runner import CommandRunner, CommandResult


class GitHubService:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def remotes(self, folder: str) -> CommandResult:
        return self.runner.run(['git', 'remote', '-v'], cwd=folder)

    def clone(self, url: str, destination: str) -> CommandResult:
        url = url.strip()
        parsed = urlparse(url)
        valid = (parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password)
        valid |= url.startswith('git@github.com:') or url.startswith('git@gitlab.com:')
        if not valid:
            raise ValueError('仅允许无凭据 HTTPS URL 或 GitHub/GitLab SSH URL')
        dest = Path(destination).expanduser().resolve()
        if dest.exists():
            raise ValueError('目标路径已存在，避免覆盖')
        if not dest.parent.is_dir():
            raise ValueError('目标父目录不存在')
        return self.runner.run(['git', 'clone', '--', url, str(dest)], cwd=dest.parent, timeout=300)

    def create_repository(self, folder: str, name: str, private: bool = True) -> CommandResult:
        if not name or not all(c.isalnum() or c in '._-' for c in name):
            raise ValueError('无效的仓库名称')
        return self.runner.run(['gh', 'repo', 'create', name, '--private' if private else '--public', '--source', '.', '--remote', 'origin'], cwd=folder, timeout=120)

    def generate_files(self, folder: str) -> list[Path]:
        root = Path(folder).resolve()
        files = {
            '.github/workflows/python-ci.yml': '''name: Python CI\non:\n  push:\n  pull_request:\njobs:\n  tests:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n      - run: python -m pip install -r requirements.txt\n      - run: python -m pytest -q\n''',
            '.github/ISSUE_TEMPLATE/bug_report.md': '---\nname: Bug report\nabout: Report a reproducible bug\n---\n\n### Steps to reproduce\n\n### Expected behavior\n',
            '.github/PULL_REQUEST_TEMPLATE.md': '## Summary\n\n## Testing\n\n## Checklist\n- [ ] Tests pass\n',
        }
        created = []
        for name, data in files.items():
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_text(data, encoding='utf-8')
                created.append(dest)
        return created
