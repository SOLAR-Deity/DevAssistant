"""Docker and Compose wrapper."""
from __future__ import annotations
from pathlib import Path
from app.core.runner import CommandRunner, CommandResult


class DockerService:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def version(self) -> CommandResult:
        return self.runner.run(['docker', 'version', '--format', '{{json .}}'], timeout=20)

    def compose_version(self) -> CommandResult:
        return self.runner.run(['docker', 'compose', 'version'], timeout=20)

    def containers(self) -> CommandResult:
        return self.runner.run(['docker', 'ps', '-a', '--format', '{{json .}}'], timeout=20)

    def images(self) -> CommandResult:
        return self.runner.run(['docker', 'images', '--format', '{{json .}}'], timeout=20)

    def start(self, container: str) -> CommandResult:
        if not container.strip() or container.startswith('-'):
            raise ValueError('请填写有效的容器名称')
        return self.runner.run(['docker', 'start', container], timeout=90)

    def stop(self, container: str) -> CommandResult:
        if not container.strip() or container.startswith('-'):
            raise ValueError('请填写有效的容器名称')
        return self.runner.run(['docker', 'stop', container], timeout=90)

    def build(self, folder: str, tag: str) -> CommandResult:
        if not tag or tag.startswith('-'):
            raise ValueError('镜像 Tag 无效')
        return self.runner.run(['docker', 'build', '-t', tag, '.'], cwd=folder, timeout=600)

    def compose_up(self, folder: str) -> CommandResult:
        p = Path(folder).resolve()
        if not any((p / n).is_file() for n in ('compose.yaml', 'compose.yml', 'docker-compose.yml', 'docker-compose.yaml')):
            raise ValueError('没有找到 Compose 配置文件')
        return self.runner.run(['docker', 'compose', 'up', '-d'], cwd=folder, timeout=600)
