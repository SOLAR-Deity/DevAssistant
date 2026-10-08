import json
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

from app.bootstrap import create_services
from app.core.runner import CommandRunner, CommandResult, redact
from app.services.ignore import IgnoreService
from app.services.generator import ProjectGenerator
from app.services.learning import LearningService
from app.services.github import GitHubService
from app.services.docker import DockerService
from app.services.ssh import SSHService
from app.services.lfs import LFSService
from app.services.environment import EnvironmentService


@pytest.fixture
def services(tmp_path):
    return create_services(tmp_path / 'user-data')


def test_command_result_schema():
    r = CommandRunner().run([sys.executable, '-c', 'print("hello")'])
    assert r.exit_code == 0 and r.stdout.strip() == 'hello'
    assert {'command', 'stdout', 'stderr', 'exit_code'} <= set(r.as_dict())


def test_cmd_argv_not_shell():
    r = CommandRunner().run([sys.executable, '-c', 'import sys;print(repr(sys.argv[1:]))', '; echo INJECT'])
    assert r.ok and "'; echo INJECT'" in r.stdout


def test_missing_executable():
    r = CommandRunner().run(['this_cli_is_missing_123456789'])
    assert r.exit_code == 127 and r.stderr


def test_timeout():
    r = CommandRunner().run([sys.executable, '-c', 'import time;time.sleep(2)'], timeout=1)
    assert r.exit_code == 124


def test_redactor():
    s = redact('git clone https://joe:password@github.com/foo --token abc123')
    assert 'password' not in s and 'abc123' not in s


def test_projects_and_settings(services, tmp_path):
    project = tmp_path / 'app'
    project.mkdir()
    services.store.add_project(project, 'Python')
    services.store.add_project(project, 'Python')
    assert len(services.store.projects()) == 1
    services.store.set_setting('theme', 'Light')
    assert services.store.setting('theme') == 'Light'
    services.store.remove_project(str(project))
    assert services.store.projects() == []


def test_nonexistent_project(services, tmp_path):
    with pytest.raises(ValueError):
        services.store.add_project(tmp_path / 'missing')


def test_sqlite_history_from_runner(services):
    services.runner.run([sys.executable, '-c', 'print(42)'])
    rows = services.store.history()
    assert len(rows) == 1 and rows[0]['exit_code'] == 0 and '42' in rows[0]['stdout']


def test_learning(services):
    assert 'git add' in services.learning.list_commands()
    info = services.learning.explain('  git   add  ')
    assert info['example'] == 'git add .'
    assert services.learning.explain('missing')['example'] == ''


@pytest.mark.parametrize('kind', ['Python', 'Java', 'Node', 'AI'])
def test_project_generate(services, tmp_path, kind):
    path = services.generator.generate(str(tmp_path), 'sample-project', kind)
    assert (path / 'README.md').is_file()
    assert (path / 'LICENSE').is_file()
    assert (path / '.gitignore').is_file()
    assert (path / '.env.example').is_file()
    with pytest.raises(ValueError):
        services.generator.generate(str(tmp_path), 'sample-project', kind)


@pytest.mark.parametrize('name', ['', '../oops', '-wrong', '.'])
def test_project_generator_rejects_unsafe_name(services, tmp_path, name):
    with pytest.raises(ValueError):
        services.generator.generate(str(tmp_path), name, 'Python')


def test_ignore_merges_not_overwrites(tmp_path):
    file = tmp_path / '.gitignore'
    file.write_text('custom-rules/\n', encoding='utf8')
    service = IgnoreService()
    service.generate(str(tmp_path), ['Python', 'Node'])
    first = file.read_text(encoding='utf8')
    assert 'custom-rules/' in first and 'node_modules/' in first
    service.generate(str(tmp_path), ['Python', 'Node'])
    assert file.read_text(encoding='utf8') == first


def test_lfs_attributes_idempotent(tmp_path):
    service = LFSService(CommandRunner())
    service.generate_attributes(str(tmp_path), ['Office', 'AI'])
    first = (tmp_path / '.gitattributes').read_text()
    service.generate_attributes(str(tmp_path), ['Office', 'AI'])
    assert (tmp_path / '.gitattributes').read_text() == first
    assert '*.onnx' in first


def test_lfs_invalid_pattern(tmp_path):
    with pytest.raises(ValueError):
        LFSService(CommandRunner()).track(str(tmp_path), ['../../evil'])


def test_github_clone_rejects_inline_credentials(tmp_path):
    with pytest.raises(ValueError):
        GitHubService(CommandRunner()).clone('https://user:pass@github.com/example/repo.git', str(tmp_path / 'dest'))


def test_github_templates_dont_overwrite(tmp_path):
    github = GitHubService(CommandRunner())
    paths = github.generate_files(str(tmp_path))
    assert len(paths) == 3
    assert not github.generate_files(str(tmp_path))


def test_docker_validation():
    service = DockerService(CommandRunner())
    with pytest.raises(ValueError):
        service.start('--rm')
    with pytest.raises(ValueError):
        service.compose_up('.')


def test_ssh_validation():
    service = SSHService(CommandRunner())
    with pytest.raises(ValueError):
        service.generate('../wrong')
    with pytest.raises(ValueError):
        service.test('not-a-host')


def test_environment_missing_manifest(tmp_path):
    env = EnvironmentService(CommandRunner())
    with pytest.raises(ValueError):
        env.restore(str(tmp_path), 'requirements.txt')
    assert env.project_manifests(str(tmp_path)) == []


def test_plugin_install_disable_enable(services, tmp_path):
    src = tmp_path / 'plugin-source'
    src.mkdir()
    (src / 'manifest.json').write_text(json.dumps({'name': 'demo', 'version': '0.0.1'}))
    (src / 'main.py').write_text("raise RuntimeError('must not run')\n")
    installed = services.plugins.install(str(src))
    assert installed['enabled'] is False
    services.plugins.set_enabled('demo', True)
    assert services.plugins.list_plugins()[0]['enabled'] is True
    services.plugins.set_enabled('demo', False)
    assert services.plugins.list_plugins()[0]['enabled'] is False
    with pytest.raises(ValueError):
        services.plugins.install(str(src))


def test_plugin_rejects_invalid_name(services, tmp_path):
    src = tmp_path / 'bad-plugin'
    src.mkdir()
    (src / 'manifest.json').write_text(json.dumps({'name': '../escape', 'version': '1'}))
    (src / 'main.py').write_text('pass')
    with pytest.raises(ValueError):
        services.plugins.install(str(src))


@pytest.mark.skipif(not shutil.which('git'), reason='git executable unavailable')
def test_git_end_to_end(services, tmp_path):
    folder = tmp_path / 'repo'
    folder.mkdir()
    git = services.git
    assert git.init(str(folder)).ok
    assert git.execute(str(folder), 'config', 'user.email', 'test@example.com').ok
    assert git.execute(str(folder), 'config', 'user.name', 'Test User').ok
    (folder / 'hello.txt').write_text('Hello\n', encoding='utf8')
    assert git.details(str(folder))['files'][0]['code'] == '??'
    assert git.add(str(folder)).ok
    assert git.commit(str(folder), 'Initial commit').ok
    assert git.status(str(folder)).ok
    assert git.tag(str(folder), 'v0.1.0').ok
    assert git.branch(str(folder), 'new-feature').ok
    assert git.checkout(str(folder), 'new-feature').ok
    (folder / 'hello.txt').write_text('Updated\n', encoding='utf8')
    assert 'Updated' in git.diff(str(folder), 'hello.txt').stdout
    git.discard_tracked(str(folder))
    assert (folder / 'hello.txt').read_text() == 'Hello\n'
    assert git.details(str(folder))['files'] == []


@pytest.mark.skipif(not shutil.which('git'), reason='git executable unavailable')
def test_health_checks(services, tmp_path):
    (tmp_path / '.env').write_text('MY_SECRET=something')
    (tmp_path / 'app.py').write_text('api_key = "' + 'a' * 30 + '"')
    report = services.health.check(str(tmp_path))
    assert 'README.md' in report['missing']
    assert '.gitignore' in report['missing']
    assert any('token' in warning.lower() for warning in report['security_warnings'])
