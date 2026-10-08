"""User-entered command planning, persistent current directory and safety hints.

This is a *command terminal*, not a full ConPTY/PTY emulator. Programs that
require a raw TTY (vim, python REPL, SSH interactive prompts) are unsupported.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shlex


@dataclass(frozen=True)
class TerminalAction:
    kind: str
    input: str
    cwd: Path
    argv: tuple[str, ...] = ()
    output: str = ''


_DESTRUCTIVE = re.compile(
    r'(?i)(?:\b(?:git\s+(?:reset\s+--hard|clean\s+-\w*f|push\s+--force|restore\s+))|'
    r'\b(?:del|erase|rmdir|rd|format|diskpart)\b|'
    r'\brm\s+-\w*[rf]|\bremove-item\b|'
    r'\bgit\s+checkout\s+--|\bdocker\s+(?:system\s+prune|compose\s+down\s+--volumes))'
)


def needs_confirmation(text: str) -> bool:
    return bool(_DESTRUCTIVE.search(text))


class TerminalSession:
    def __init__(self, cwd: str | Path | None = None) -> None:
        self.cwd = Path(cwd or Path.home()).expanduser().resolve()
        if not self.cwd.is_dir():
            self.cwd = Path.home().resolve()
        self.history: list[str] = []
        self.history_index = 0

    def change_to_project(self, folder: str | Path) -> None:
        path = Path(folder).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f'目录不存在: {path}')
        self.cwd = path

    def plan(self, command: str) -> TerminalAction:
        text = command.strip()
        if not text:
            raise ValueError('请输入命令')
        self.history.append(text)
        self.history_index = len(self.history)
        if text.lower() in ('cls', 'clear'):
            return TerminalAction('clear', text, self.cwd)
        if text.lower() in ('pwd', 'cd'):
            if text.lower() == 'pwd':
                return TerminalAction('builtin', text, self.cwd, output=str(self.cwd))
            target = Path.home()
        elif re.match(r'(?is)^cd\s+', text):
            arg = re.sub(r'(?is)^cd\s+', '', text).strip()
            if arg.lower().startswith('/d '):
                arg = arg[3:].strip()
            arg = os.path.expandvars(arg.strip('"\''))
            target = Path(arg).expanduser()
        else:
            argv = parse_user_command(text, windows=(os.name == 'nt'))
            return TerminalAction('external', text, self.cwd, argv)
        if not target.is_absolute():
            target = self.cwd / target
        target = target.resolve()
        if not target.is_dir():
            raise ValueError(f'目录不存在: {target}')
        self.cwd = target
        return TerminalAction('builtin', text, self.cwd, output=str(self.cwd))

    def previous(self, current: str) -> str:
        if not self.history:
            return current
        self.history_index = max(0, self.history_index-1)
        return self.history[self.history_index]

    def next(self) -> str:
        self.history_index = min(len(self.history), self.history_index+1)
        return self.history[self.history_index] if self.history_index < len(self.history) else ''


# Common developer commands bypass cmd.exe's fragile Windows quote-stripping.
# Explicit pipes, redirects and CMD builtins use cmd.exe on Windows.
_DIRECT = frozenset(('git', 'python', 'python3', 'py', 'pip', 'pip3',
                     'conda', 'node', 'npm', 'npx', 'docker', 'ssh', 'gh',
                     'mvn', 'gradle', 'java', 'javac', 'git-lfs'))


def parse_user_command(text: str, *, windows: bool) -> tuple[str, ...]:
    if windows:
        if re.search(r'[|&<>\n\r]', text):
            return ('cmd.exe', '/D', '/C', text)
        parts = shlex.split(text, posix=False)
        if not parts:
            raise ValueError('请输入命令')
        if parts[0].lower().removesuffix('.exe') in _DIRECT:
            # shlex(posix=False) keeps wrapping quotes; strip only paired quotes.
            def strip_quotes(t):
                return t[1:-1] if len(t) >= 2 and t[0] == t[-1] == '"' else t
            return tuple(strip_quotes(part) for part in parts)
        return ('cmd.exe', '/D', '/C', text)
    return ('/bin/sh', '-c', text)
