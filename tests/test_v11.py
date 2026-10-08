"""Regression tests for v1.1 terminal session, event bus, Git and history migration."""
from pathlib import Path
import os
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

from app.bootstrap import create_services
from app.core.runner import CommandRunner
from app.core.terminal_session import TerminalSession, needs_confirmation, parse_user_command
from app.database.store import Store


def test_terminal_cd_and_pwd(tmp_path):
    cwd = tmp_path / 'a'
    cwd.mkdir()
    s = TerminalSession(tmp_path)
    assert s.plan('cd a').output == str(cwd)
    assert s.plan('pwd').output == str(cwd)
    assert s.plan('cd ..').output == str(tmp_path)
    assert s.plan('clear').kind == 'clear'


def test_terminal_commands_are_not_executed_while_planning(tmp_path):
    s = TerminalSession(tmp_path)
    p = s.plan('git add . && git commit -m "test"')
    assert p.kind == 'external' and p.cwd == tmp_path
    assert p.argv[-1] == 'git add . && git commit -m "test"'


def test_terminal_history_boundaries(tmp_path):
    s = TerminalSession(tmp_path)
    assert s.previous('hello') == 'hello'
    s.plan('pwd')
    s.plan('clear')
    assert s.previous('') == 'clear'
    assert s.previous('') == 'pwd'
    assert s.previous('') == 'pwd'
    assert s.next() == 'clear'
    assert s.next() == ''
    assert s.next() == ''


@pytest.mark.parametrize('bad', ['cd missing_folder', 'cd "missing dir"'])
def test_terminal_invalid_cd(tmp_path, bad):
    s = TerminalSession(tmp_path)
    with pytest.raises(ValueError):
        s.plan(bad)
    assert s.cwd == tmp_path


@pytest.mark.parametrize('text', [
    'git reset --hard HEAD', 'git clean -fd', 'del /Q important.txt',
    'rmdir /s folder', 'rm -rf foo', 'docker system prune',
])
def test_dangerous_commands_require_confirmation(text):
    assert needs_confirmation(text)


@pytest.mark.parametrize('text', ['git status', 'git add -A', 'python main.py', 'npm install'])
def test_safe_examples_are_not_blocked(text):
    assert not needs_confirmation(text)


def test_streaming_events_and_source(tmp_path):
    events = []
    runner = CommandRunner(event_sink=events.append)
    with runner.from_source('terminal'):
        result = runner.run([sys.executable, '-c', 'print("hello")'], cwd=tmp_path,
                            display_command='python test.py')
    assert result.ok and result.stdout.strip() == 'hello'
    assert events[0].kind == 'started' and events[0].command == 'python test.py'
    assert any(e.kind == 'stdout' and 'hello' in e.text for e in events)
    assert events[-1].kind == 'finished' and events[-1].exit_code == 0
    assert {e.source for e in events} == {'terminal'}
    assert runner.current_source == 'system'


def test_stream_stderr_and_failed_exit(tmp_path):
    events = []
    r = CommandRunner(event_sink=events.append).run(
        [sys.executable, '-c', 'import sys;sys.stderr.write("bad\\n");sys.exit(3)'],
        cwd=tmp_path)
    assert r.exit_code == 3 and 'bad' in r.stderr
    assert any(e.kind == 'stderr' and 'bad' in e.text for e in events)
    assert events[-1].exit_code == 3


def test_runner_timeout_event(tmp_path):
    events = []
    r = CommandRunner(event_sink=events.append).run(
        [sys.executable, '-c', 'import time;time.sleep(4)'], cwd=tmp_path, timeout=1)
    assert r.exit_code == 124 and events[-1].kind == 'finished'
    assert 'timed out' in r.stderr


def test_runner_can_cancel(tmp_path):
    runner = CommandRunner()
    received = []
    worker = threading.Thread(target=lambda: received.append(runner.run(
        [sys.executable, '-c', 'import time;time.sleep(8)'], cwd=tmp_path, timeout=12)))
    worker.start()
    for _ in range(200):
        with runner._running_lock:
            ready = bool(runner._running)
        if ready:
            break
        time.sleep(.01)
    assert runner.cancel_active()
    worker.join(3)
    assert not worker.is_alive()
    assert received[0].exit_code == 130


def test_db_source_and_existing_v1_db_migration(tmp_path):
    db_path = tmp_path / 'database.db'
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE command_history (
     id INTEGER PRIMARY KEY AUTOINCREMENT, command TEXT NOT NULL,
     project_path TEXT NOT NULL, stdout TEXT NOT NULL, stderr TEXT NOT NULL,
     exit_code INTEGER NOT NULL, duration_seconds REAL NOT NULL, created_at TEXT NOT NULL)''')
    conn.execute("INSERT INTO command_history(command,project_path,stdout,stderr,exit_code,duration_seconds,created_at) VALUES ('old','','','',0,0,'yesterday')")
    conn.commit()
    conn.close()
    store = Store(db_path)
    assert store.history()[0]['source'] == 'system'
    assert store.history()[0]['command'] == 'old'
    services = create_services(tmp_path / 'fresh')
    with services.runner.from_source('git_ui'):
        services.runner.run([sys.executable, '-c', 'print(123)'])
    assert services.store.history()[0]['source'] == 'git_ui'


@pytest.mark.skipif(subprocess.run(['git','--version'], capture_output=True).returncode != 0, reason='Git absent')
def test_git_staged_diff_unstage_log_stash(tmp_path):
    s = create_services(tmp_path / 'data')
    repo = tmp_path / 'repo'
    repo.mkdir()
    git = s.git
    assert git.init(str(repo)).ok
    assert git.execute(str(repo), 'config', 'user.name', 'Demo User').ok
    assert git.execute(str(repo), 'config', 'user.email', 'test@example.org').ok
    f = repo / 'sample.txt'
    f.write_text('one\n', encoding='utf8')
    assert git.add(str(repo)).ok
    assert git.commit(str(repo), 'first').ok
    f.write_text('one\ntwo\n', encoding='utf8')
    assert git.add(str(repo), ['sample.txt']).ok
    assert '+two' in git.diff(str(repo), 'sample.txt', staged=True).stdout
    assert git.unstage(str(repo), ['sample.txt']).ok
    assert '+two' in git.diff(str(repo), 'sample.txt', staged=False).stdout
    assert git.stash_push(str(repo)).ok
    assert f.read_text() == 'one\n'
    assert git.stash_pop(str(repo)).ok
    assert 'two' in f.read_text()
    assert 'first' in git.log(str(repo)).stdout
    assert git.remote_add(str(repo), 'origin', 'https://example.invalid/demo.git').ok
    assert 'origin' in git.remotes(str(repo)).stdout
    assert git.remote_remove(str(repo), 'origin').ok
    assert 'Demo User' in git.config_get(str(repo), 'user.name').stdout


def test_remote_rejects_credential_url(tmp_path):
    s = create_services(tmp_path / 'data')
    repo = tmp_path / 'repo'
    repo.mkdir()
    with pytest.raises(ValueError):
        s.git.remote_add(str(repo), 'origin', 'https://user:pass@github.com/a/b')


def test_windows_known_commands_quote_arguments_without_shell():
    assert parse_user_command('git commit -m "fix terminal history"', windows=True) == (
        'git', 'commit', '-m', 'fix terminal history')
    assert parse_user_command('python "C:\\Program Files\\demo.py"', windows=True)[1] == r'C:\Program Files\demo.py'
    assert parse_user_command('dir', windows=True) == ('cmd.exe', '/D', '/C', 'dir')
    assert parse_user_command('git status && echo done', windows=True)[0] == 'cmd.exe'
