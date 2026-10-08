"""Bounded static health checks; scans neither files outside the repo nor private keys."""
from __future__ import annotations
from pathlib import Path
import re
from app.services.git import GitService

SECRET_PATTERNS = {
    'Possible AWS access key': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    'Possible private key': re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
    'Possible committed token': re.compile(r'(?i)\b(?:api_key|secret_key|access_token)\s*[:=]\s*["\']?[a-z0-9_-]{20,}'),
}
OMIT_DIRS = {'.git', '.venv', 'venv', 'node_modules', 'target', 'dist', 'build', '__pycache__'}
SCAN_SUFFIXES = {'.py', '.js', '.ts', '.json', '.yml', '.yaml', '.toml', '.env', '.txt', '.properties'}


class HealthService:
    def __init__(self, git: GitService) -> None:
        self.git = git

    def check(self, folder: str) -> dict:
        root = Path(folder).expanduser().resolve()
        if not root.is_dir():
            raise ValueError('Project directory not found')
        report = {'path': str(root), 'git': '', 'missing': [], 'large_files': [],
                  'lfs_suggestions': [], 'security_warnings': [], 'environment_warnings': []}
        result = self.git.status(str(root))
        report['git'] = 'ok' if result.ok else 'not_initialized'
        if result.ok and len(result.stdout.strip().splitlines()) > 1:
            report['git'] = 'changes_detected'
        for name in ('README.md', '.gitignore'):
            if not (root / name).is_file():
                report['missing'].append(name)
        if not any((root / n).is_file() for n in ('pyproject.toml', 'requirements.txt', 'package.json', 'pom.xml', 'build.gradle')):
            report['environment_warnings'].append('未找到常见环境依赖配置')
        n = 0
        for path in root.rglob('*'):
            if any(part in OMIT_DIRS for part in path.relative_to(root).parts):
                continue
            if path.is_symlink() or not path.is_file():
                continue
            n += 1
            if n > 5000:
                report['environment_warnings'].append('扫描文件过多，已截断')
                break
            try:
                size = path.stat().st_size
                rel = path.relative_to(root).as_posix()
                if size > 10 * 1024 * 1024:
                    report['large_files'].append({'path': rel, 'mb': round(size / 1024 / 1024, 1)})
                    if path.suffix.lower() in ('.onnx', '.pth', '.pt', '.mp4', '.mov', '.bin', '.zip'):
                        report['lfs_suggestions'].append(rel)
                if size < 120_000 and (path.suffix.lower() in SCAN_SUFFIXES or path.name == '.env'):
                    text = path.read_text(encoding='utf-8', errors='replace')
                    for label, pattern in SECRET_PATTERNS.items():
                        if pattern.search(text):
                            report['security_warnings'].append(f'{rel}: {label}')
            except OSError:
                continue
        if (root / '.env').is_file() and not (root / '.gitignore').is_file():
            report['security_warnings'].append('存在 .env，但没有 .gitignore')
        return report
