"""Safe project scaffolding; refuses to replace existing nonempty projects."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json
import re

from app.services.ignore import PRESETS

MIT = '''MIT License\n\nCopyright (c) {year} {name}\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the "Software"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n'''


class ProjectGenerator:
    KINDS = ('Python', 'Java', 'Node', 'AI')

    def generate(self, parent: str, name: str, kind: str) -> Path:
        if kind not in self.KINDS:
            raise ValueError('未知项目模板')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', name) or name in ('.', '..'):
            raise ValueError('项目名只能包含字母、数字、点、横线和下划线')
        base = Path(parent).expanduser().resolve()
        if not base.is_dir():
            raise ValueError('项目父目录不存在')
        root = base / name
        if root.exists():
            raise ValueError('项目路径已存在，拒绝覆盖')
        rules = PRESETS['Python' if kind in ('Python', 'AI') else kind]
        files = {
            'README.md': f'# {name}\n\nCreated with Dev Assistant ({kind}).\n',
            'LICENSE': MIT.format(year=datetime.now().year, name=name),
            '.gitignore': '\n'.join(rules) + '\n',
            '.env.example': '# Copy to .env and set your own values. Never commit secrets.\n',
        }
        if kind == 'Python':
            files.update({'pyproject.toml': f'[project]\nname = "{name}"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n',
                          'src/__init__.py': '',
                          'tests/test_smoke.py': 'def test_smoke():\n    assert True\n'})
        elif kind == 'Java':
            files['pom.xml'] = f'''<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">\n  <modelVersion>4.0.0</modelVersion><groupId>local.devassistant</groupId><artifactId>{name}</artifactId><version>0.1.0</version>\n  <properties><maven.compiler.release>17</maven.compiler.release></properties>\n</project>\n'''
            files['src/main/java/.gitkeep'] = ''
        elif kind == 'Node':
            files['package.json'] = json.dumps({'name': name.lower(), 'version': '0.1.0',
                                                  'private': True, 'scripts': {'start': 'node src/index.js'}}, indent=2) + '\n'
            files['src/index.js'] = "console.log('Hello from Dev Assistant');\n"
        elif kind == 'AI':
            files['requirements.txt'] = '# Add dependencies here\n'
            files['src/train.py'] = '"""Your model training entry point."""\n\nif __name__ == "__main__":\n    print("Ready")\n'
            for folder in ('models', 'datasets', 'checkpoints'):
                files[f'{folder}/.gitkeep'] = ''
        root.mkdir(parents=False)
        try:
            for relative, text in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding='utf-8')
        except Exception:
            import shutil
            shutil.rmtree(root)
            raise
        return root
