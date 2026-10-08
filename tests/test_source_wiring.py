"""AST/source-level GUI wiring guards, useful even without PySide6 installed."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse(relative: str):
    return ast.parse((ROOT / relative).read_text(encoding='utf-8'))


def test_terminal_emits_user_input_and_has_history_navigation():
    module = parse('app/gui/widgets/terminal.py')
    names = {node.name for node in ast.walk(module) if isinstance(node, ast.FunctionDef)}
    assert {'_submit', 'set_cwd', 'set_history_input', 'append_chunk', 'append_exit'} <= names
    source = (ROOT/'app/gui/widgets/terminal.py').read_text(encoding='utf8')
    assert 'command_submitted.emit' in source and 'history_previous.emit' in source


def test_controller_handles_terminal_and_records_real_runner_events():
    module = parse('app/controllers/app_controller.py')
    names = {node.name for node in ast.walk(module) if isinstance(node, ast.FunctionDef)}
    assert {'run_terminal_command', '_on_command_event', 'stage_selected',
            'unstage_selected', 'stash_pop', 'remote_add', 'config_set'} <= names
    source = (ROOT/'app/controllers/app_controller.py').read_text(encoding='utf8')
    assert 'runner.event_sink = self.command_event.emit' in source
    assert 'runner.from_source(command_source)' in source
