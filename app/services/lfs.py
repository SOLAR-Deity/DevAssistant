"""Git LFS detection and curated attributes templates."""
from __future__ import annotations
from pathlib import Path
import re
from app.core.runner import CommandRunner, CommandResult

PRESETS = {
    'Office': ['*.docx', '*.xlsx', '*.pptx'],
    'AI': ['*.pth', '*.pt', '*.onnx', '*.bin'],
    'Dataset': ['*.csv', '*.sqlite'],
    'Video': ['*.mp4', '*.mov'],
}


class LFSService:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def detect(self) -> CommandResult:
        return self.runner.run(['git', 'lfs', 'version'], timeout=10)

    def install(self, repo: str) -> CommandResult:
        return self.runner.run(['git', 'lfs', 'install', '--local'], cwd=repo)

    def track(self, repo: str, patterns: list[str]) -> list[CommandResult]:
        if not patterns or any(not re.fullmatch(r'\*\.[a-zA-Z0-9]{1,12}', p) for p in patterns):
            raise ValueError('只允许 *.extension 格式的文件扩展名')
        return [self.runner.run(['git', 'lfs', 'track', p], cwd=repo) for p in patterns]

    def generate_attributes(self, repo: str, groups: list[str]) -> Path:
        """Append safe LFS rules, never truncate existing custom .gitattributes."""
        selected = [p for name in groups for p in PRESETS[name]]
        dest = Path(repo).resolve() / '.gitattributes'
        existing = dest.read_text(encoding='utf-8') if dest.exists() else ''
        extra = [f'{p} filter=lfs diff=lfs merge=lfs -text' for p in selected
                 if not any(line.split(' ', 1)[0] == p for line in existing.splitlines())]
        if extra:
            with dest.open('a', encoding='utf-8', newline='\n') as f:
                if existing and not existing.endswith('\n'):
                    f.write('\n')
                f.write('\n'.join(extra) + '\n')
        return dest
