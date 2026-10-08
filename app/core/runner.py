"""One audited, streaming subprocess gateway for UI actions and terminal input.

All commands are argv arrays; the terminal *explicitly* launches the platform
shell for user-provided input. Other services never call a shell implicitly.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
import codecs
import logging
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid


_CREDENTIALS = re.compile(r'(?i)(https?://)([^\s/@:]+):([^\s/@]+)@')
_SENSITIVE = re.compile(r'(?i)(--(?:password|token|secret|api-key)(?:=|\s+))([^\s]+)')
_CURRENT_SOURCE: ContextVar[str] = ContextVar('command_source', default='system')


def redact(value: str) -> str:
    return _SENSITIVE.sub(r'\1[REDACTED]', _CREDENTIALS.sub(r'\1\2:[REDACTED]@', value))


@dataclass(frozen=True)
class CommandResult:
    command: str
    stdout: str
    stderr: str
    exit_code: int
    cwd: str = ''
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CommandEvent:
    kind: str           # started / stdout / stderr / finished
    source: str         # git_ui / terminal / docker_ui / ...
    command: str
    cwd: str
    text: str = ''
    exit_code: int | None = None
    duration_seconds: float = 0.0
    request_id: str = ''


class CommandRunner:
    """Launch, stream, time out, cancel and audit subprocesses in worker threads."""
    def __init__(self, observer: Callable[[CommandResult], None] | None = None,
                 default_timeout: int = 90,
                 event_sink: Callable[[CommandEvent], None] | None = None) -> None:
        self.observer = observer
        self.event_sink = event_sink
        self.default_timeout = default_timeout
        self._running: dict[str, subprocess.Popen] = {}
        self._running_lock = threading.Lock()
        self._cancelled: set[str] = set()

    @property
    def current_source(self) -> str:
        return _CURRENT_SOURCE.get()

    @contextmanager
    def from_source(self, source: str):
        token = _CURRENT_SOURCE.set(source)
        try:
            yield
        finally:
            _CURRENT_SOURCE.reset(token)

    def _notify(self, event: CommandEvent) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink(event)
            except Exception:
                logging.getLogger(__name__).exception('Command display event failed')

    def cancel_active(self) -> bool:
        """Stop most recently started process (used by the UI Cancel button)."""
        with self._running_lock:
            if not self._running:
                return False
            key = next(reversed(self._running))
            self._cancelled.add(key)
            p = self._running[key]
        try:
            p.kill()
        except OSError:
            pass
        return True

    def run(self, argv: Sequence[str], *, cwd: str | Path | None = None,
            timeout: int | None = None, env: Mapping[str, str] | None = None,
            input_text: str | None = None,
            display_command: str | None = None) -> CommandResult:
        if not argv or any(not isinstance(x, str) or not x for x in argv):
            raise ValueError('argv must contain nonempty strings')
        folder = str(Path(cwd).expanduser().resolve()) if cwd is not None else ''
        command = redact(display_command if display_command is not None else subprocess.list2cmdline(list(argv)))
        source = self.current_source
        request_id = str(uuid.uuid4())
        started = time.monotonic()
        effective_timeout = timeout if timeout is not None else self.default_timeout
        self._notify(CommandEvent('started', source, command, folder, request_id=request_id))
        popen_kwargs = {}
        if os.name == 'nt':
            popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        output: dict[str, list[str]] = {'stdout': [], 'stderr': []}
        readers: list[threading.Thread] = []
        timed_out = False
        cancelled = False
        code = 127
        try:
            with subprocess.Popen(
                list(argv), shell=False, cwd=folder or None,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                env=dict(env) if env else None, **popen_kwargs,
            ) as process:
                with self._running_lock:
                    self._running[request_id] = process

                def consume(channel: str, stream) -> None:
                    # os.read delivers incremental bytes; codecs preserves split UTF-8 characters.
                    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
                    try:
                        while True:
                            raw = os.read(stream.fileno(), 4096)
                            if not raw:
                                break
                            piece = decoder.decode(raw)
                            if piece:
                                output[channel].append(piece)
                                self._notify(CommandEvent(channel, source, command, folder,
                                                          redact(piece), request_id=request_id))
                        tail = decoder.decode(b'', final=True)
                        if tail:
                            output[channel].append(tail)
                            self._notify(CommandEvent(channel, source, command, folder,
                                                      redact(tail), request_id=request_id))
                    except OSError as exc:
                        logging.getLogger(__name__).warning('Stream read failed: %s', exc)

                for channel, stream in (('stdout', process.stdout), ('stderr', process.stderr)):
                    thread = threading.Thread(target=consume, args=(channel, stream), daemon=True)
                    readers.append(thread)
                    thread.start()
                if input_text is not None and process.stdin is not None:
                    try:
                        process.stdin.write(input_text.encode('utf-8'))
                        process.stdin.close()
                    except BrokenPipeError:
                        pass
                try:
                    code = process.wait(timeout=effective_timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    process.kill()
                    process.wait()
                    code = 124
                for thread in readers:
                    thread.join(timeout=5)
                with self._running_lock:
                    self._running.pop(request_id, None)
                    cancelled = request_id in self._cancelled
                    self._cancelled.discard(request_id)
        except OSError as exc:
            output['stderr'].append(f'Command unavailable: {exc}')
            self._notify(CommandEvent('stderr', source, command, folder,
                                      redact(output['stderr'][-1]), request_id=request_id))
        if timed_out:
            msg = f'\nCommand timed out after {effective_timeout}s'
            output['stderr'].append(msg)
            self._notify(CommandEvent('stderr', source, command, folder, msg, request_id=request_id))
        if cancelled:
            code = 130
            output['stderr'].append('\nCommand cancelled by user')
            self._notify(CommandEvent('stderr', source, command, folder, '\nCommand cancelled by user', request_id=request_id))
        result = CommandResult(command, ''.join(output['stdout']), ''.join(output['stderr']),
                               code, folder, round(time.monotonic()-started, 3))
        if self.observer is not None:
            try:
                self.observer(result)
            except Exception:
                logging.getLogger(__name__).exception('Command history failed')
        self._notify(CommandEvent('finished', source, command, folder, exit_code=code,
                                  duration_seconds=result.duration_seconds, request_id=request_id))
        return result
