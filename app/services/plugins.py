"""Local plugin installation / opt-in enablement. Plugins are NOT auto-imported."""
from __future__ import annotations
from pathlib import Path
import json
import re
import shutil

from app.database.store import Store


class PluginManager:
    def __init__(self, directory: str | Path, store: Store) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.store = store

    @staticmethod
    def manifest(path: Path) -> dict:
        f = path / 'manifest.json'
        if not f.is_file() or f.is_symlink() or not (path / 'main.py').is_file():
            raise ValueError('插件必须包含 manifest.json 和 main.py')
        data = json.loads(f.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', str(data.get('name', ''))):
            raise ValueError('插件名称不合法')
        if not isinstance(data.get('version'), str) or not data['version']:
            raise ValueError('manifest.json 缺少 version')
        return data

    def install(self, source: str) -> dict:
        folder = Path(source).expanduser().resolve()
        data = self.manifest(folder)
        dest = self.directory / data['name']
        if dest.exists():
            raise ValueError('该插件已安装，拒绝覆盖')
        if any(p.is_symlink() for p in folder.rglob('*')):
            raise ValueError('插件不允许携带符号链接')
        if len(list(folder.rglob('*'))) > 500:
            raise ValueError('插件文件数量过多')
        shutil.copytree(folder, dest)
        self.store.update_plugin(data['name'], str(dest), data['version'], False)
        return {'name': data['name'], 'version': data['version'], 'enabled': False}

    def set_enabled(self, name: str, enabled: bool) -> None:
        folder = self.directory / name
        data = self.manifest(folder)
        if data['name'] != name:
            raise ValueError('插件名称不一致')
        self.store.update_plugin(name, str(folder), data['version'], enabled)
        # Intentional: never execute or import untrusted main.py automatically.

    def list_plugins(self) -> list[dict]:
        states = self.store.plugin_states()
        results = []
        for folder in sorted(self.directory.iterdir()):
            if not folder.is_dir() or folder.is_symlink():
                continue
            try:
                data = self.manifest(folder)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            results.append({'name': data['name'], 'version': data['version'],
                            'enabled': bool(states.get(data['name'], {}).get('enabled', 0))})
        return results
