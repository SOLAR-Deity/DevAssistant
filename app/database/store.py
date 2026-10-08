"""SQLite persistence using short-lived connections, safe across worker threads."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import sqlite3
from typing import Iterator

from app.core.runner import CommandResult, redact


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.path), timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA busy_timeout = 15000')
        connection.execute('PRAGMA foreign_keys = ON')
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS projects (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
                  language TEXT NOT NULL DEFAULT 'Other',
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS command_history (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  command TEXT NOT NULL, project_path TEXT NOT NULL,
                  stdout TEXT NOT NULL, stderr TEXT NOT NULL,
                  exit_code INTEGER NOT NULL, duration_seconds REAL NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                  key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plugin_state (
                  name TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
                  path TEXT NOT NULL, version TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS history_recent ON command_history(id DESC);
            ''')
            # Upgrade existing databases without deleting user history.
            columns = {row['name'] for row in db.execute('PRAGMA table_info(command_history)')}
            if 'source' not in columns:
                db.execute("ALTER TABLE command_history ADD COLUMN source TEXT NOT NULL DEFAULT 'system'")

    def add_project(self, path: str | Path, language: str = 'Other') -> dict:
        project = Path(path).expanduser().resolve()
        if not project.is_dir():
            raise ValueError('请选择存在的项目文件夹')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO projects (name, path, language, created_at) VALUES (?, ?, ?, ?)',
                       (project.name, str(project), language, utcnow()))
        return {'name': project.name, 'path': str(project), 'language': language}

    def remove_project(self, path: str) -> None:
        with self.connect() as db:
            db.execute('DELETE FROM projects WHERE path=?', (path,))

    def projects(self) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM projects ORDER BY id DESC')]

    def record(self, result: CommandResult, source: str = 'system') -> None:
        with self.connect() as db:
            db.execute('''INSERT INTO command_history
              (command, project_path, stdout, stderr, exit_code, duration_seconds, created_at, source)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (redact(result.command), result.cwd,
               redact(result.stdout)[:6000], redact(result.stderr)[:6000],
               result.exit_code, result.duration_seconds, utcnow(), source))

    def history(self, limit: int = 200) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM command_history ORDER BY id DESC LIMIT ?',
                                                   (max(1, min(limit, 1000)),))]

    def setting(self, key: str, default=None):
        with self.connect() as db:
            row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return json.loads(row['value']) if row else default

    def set_setting(self, key: str, value) -> None:
        with self.connect() as db:
            db.execute('INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                       (key, json.dumps(value, ensure_ascii=False)))

    def update_plugin(self, name: str, path: str, version: str, enabled: bool) -> None:
        with self.connect() as db:
            db.execute('''INSERT INTO plugin_state(name, path, version, enabled) VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET path=excluded.path,version=excluded.version,enabled=excluded.enabled''',
                (name, path, version, int(enabled)))

    def plugin_states(self) -> dict[str, dict]:
        with self.connect() as db:
            return {r['name']: dict(r) for r in db.execute('SELECT * FROM plugin_state')}
