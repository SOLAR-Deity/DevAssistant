"""Developer environment discovery, export and opt-in restore."""
from __future__ import annotations
from pathlib import Path
from dataclasses import asdict
import shutil
import re
import sys

from app.core.runner import CommandRunner, CommandResult

TOOLS = {
    'Python': ('python', ['python', '--version']),
    'pip': ('pip', [sys.executable, '-m', 'pip', '--version']),
    'Conda': ('conda', ['conda', '--version']),
    'Java': ('java', ['java', '-version']),
    'Maven': ('mvn', ['mvn', '-version']),
    'Gradle': ('gradle', ['gradle', '--version']),
    'Node': ('node', ['node', '--version']),
    'npm': ('npm', ['npm', '--version']),
    'Docker': ('docker', ['docker', '--version']),
}


class EnvironmentService:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def detect(self) -> dict:
        result = {}
        for name, (executable, args) in TOOLS.items():
            present = bool(shutil.which(executable)) or (name == 'pip' and bool(sys.executable))
            version = self.runner.run(args, timeout=12) if present else None
            output = (version.stdout or version.stderr).strip().splitlines() if version else []
            result[name] = {'installed': bool(version and version.ok),
                            'version': (output[0][:150] if output else ''),
                            'executable': shutil.which(executable) or (sys.executable if name == 'pip' else '')}
        result['venv'] = {'installed': sys.prefix != sys.base_prefix,
                          'version': sys.prefix if sys.prefix != sys.base_prefix else '',
                          'executable': sys.executable}
        return result

    def export_python(self, folder: str) -> Path:
        dest = Path(folder).resolve() / 'requirements.txt'
        result = self.runner.run([sys.executable, '-m', 'pip', 'freeze'], cwd=folder, timeout=90)
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout or 'pip freeze failed')
        dest.write_text(result.stdout, encoding='utf-8')
        return dest

    def export_conda(self, folder: str) -> Path:
        result = self.runner.run(['conda', 'env', 'export', '--no-builds'], cwd=folder, timeout=120)
        if not result.ok:
            raise RuntimeError(result.stderr or 'conda env export failed')
        dest = Path(folder).resolve() / 'environment.yml'
        dest.write_text(result.stdout, encoding='utf-8')
        return dest

    def project_manifests(self, folder: str) -> list[str]:
        names = ['requirements.txt', 'environment.yml', 'pom.xml', 'build.gradle',
                 'build.gradle.kts', 'package.json']
        return [n for n in names if (Path(folder).resolve() / n).is_file()]

    def restore(self, folder: str, manifest: str) -> CommandResult:
        """Must be triggered after a GUI confirmation; installation is not automatic."""
        allowed = {
            'requirements.txt': [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
            'environment.yml': ['conda', 'env', 'create', '-f', 'environment.yml'],
            'pom.xml': ['mvn', '-f', 'pom.xml', 'dependency:resolve'],
            'build.gradle': ['gradle', 'dependencies'],
            'build.gradle.kts': ['gradle', 'dependencies'],
            'package.json': ['npm', 'install', '--ignore-scripts'],
        }
        if manifest not in allowed or not (Path(folder).resolve() / manifest).is_file():
            raise ValueError('不支持的配置文件或文件不存在')
        return self.runner.run(allowed[manifest], cwd=folder, timeout=600)
