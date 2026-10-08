"""Application dependency container; replace services here, not inside the UI."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
from platformdirs import user_data_dir

from app.core.runner import CommandRunner
from app.database.store import Store
from app.services.git import GitService
from app.services.environment import EnvironmentService
from app.services.lfs import LFSService
from app.services.ignore import IgnoreService
from app.services.github import GitHubService
from app.services.ssh import SSHService
from app.services.docker import DockerService
from app.services.generator import ProjectGenerator
from app.services.health import HealthService
from app.services.learning import LearningService
from app.services.plugins import PluginManager


@dataclass
class ApplicationServices:
    store: Store
    runner: CommandRunner
    git: GitService
    lfs: LFSService
    ignore: IgnoreService
    environment: EnvironmentService
    github: GitHubService
    ssh: SSHService
    docker: DockerService
    generator: ProjectGenerator
    health: HealthService
    learning: LearningService
    plugins: PluginManager


def create_services(home: Path | None = None) -> ApplicationServices:
    base = Path(home) if home is not None else Path(user_data_dir('DevAssistant', 'DevAssistantLab'))
    store = Store(base / 'dev_assistant.sqlite3')
    runner = CommandRunner()
    runner.observer = lambda result: store.record(result, source=runner.current_source)
    git = GitService(runner)
    return ApplicationServices(
        store=store, runner=runner, git=git, lfs=LFSService(runner),
        ignore=IgnoreService(), environment=EnvironmentService(runner),
        github=GitHubService(runner), ssh=SSHService(runner),
        docker=DockerService(runner), generator=ProjectGenerator(),
        health=HealthService(git), learning=LearningService(),
        plugins=PluginManager(base / 'plugins', store),
    )
