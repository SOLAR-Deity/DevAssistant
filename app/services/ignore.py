"""Additive .gitignore template builder."""
from pathlib import Path

PRESETS = {
    'Python': ['venv/', '.venv/', '__pycache__/', '*.py[cod]', '.pytest_cache/', '.mypy_cache/'],
    'Java': ['target/', '.gradle/', '*.class', '.idea/'],
    'Node': ['node_modules/', 'dist/', 'build/', '.npm/'],
    'AI': ['datasets/', 'checkpoints/', 'runs/', 'wandb/'],
    'IDE': ['.vscode/', '.idea/', '*.swp'],
}


class IgnoreService:
    def generate(self, folder: str, groups: list[str]) -> Path:
        dest = Path(folder).expanduser().resolve() / '.gitignore'
        if not dest.parent.is_dir():
            raise ValueError('项目目录不存在')
        existing = dest.read_text(encoding='utf-8') if dest.is_file() else ''
        lines = set(existing.splitlines())
        additions = []
        for group in groups:
            if group not in PRESETS:
                raise ValueError(f'Unknown template: {group}')
            rules = [r for r in PRESETS[group] if r not in lines]
            if rules:
                additions.extend([f'# {group}', *rules, ''])
                lines.update(rules)
        if additions:
            dest.write_text(existing.rstrip('\n') + ('\n\n' if existing.strip() else '') + '\n'.join(additions).rstrip() + '\n',
                            encoding='utf-8')
        return dest
