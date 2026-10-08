"""Offline Git command learning catalogue."""
from __future__ import annotations

_CATALOG = {
    'git init': ('初始化一个新的 Git 仓库。', 'git init', 'git init', ['git status', 'git add']),
    'git status': ('查看分支、暂存区和工作区状态。', 'git status', 'git status --short --branch', ['git add', 'git diff']),
    'git add': ('将文件变更加入暂存区。', 'git add <path>', 'git add .', ['git status', 'git commit']),
    'git commit': ('将暂存区中的更改记录为一次提交。', 'git commit -m "message"', 'git commit -m "Fix issue"', ['git add', 'git log']),
    'git push': ('向远程仓库推送本地提交。', 'git push [remote] [branch]', 'git push origin main', ['git pull', 'git fetch']),
    'git pull': ('从远程获取并集成更新。', 'git pull [remote] [branch]', 'git pull origin main', ['git fetch', 'git merge']),
    'git fetch': ('获取远程提交和引用，但不自动合并。', 'git fetch [remote]', 'git fetch --all', ['git pull', 'git merge']),
    'git branch': ('查看或创建分支。', 'git branch [name]', 'git branch feature/login', ['git checkout', 'git merge']),
    'git checkout': ('切换分支或恢复指定文件。', 'git checkout <branch>', 'git checkout feature/login', ['git branch', 'git switch']),
    'git merge': ('将指定分支的历史合并到当前分支。', 'git merge <branch>', 'git merge feature/login', ['git branch', 'git log']),
    'git tag': ('列出或创建提交标签。', 'git tag [name]', 'git tag v1.0.0', ['git push', 'git log']),
    'git diff': ('查看工作区或暂存区的代码差异。', 'git diff [--staged]', 'git diff --staged', ['git status', 'git add']),
    'git clone': ('从远程仓库复制项目。', 'git clone <url> [directory]', 'git clone https://github.com/org/repo.git', ['git remote', 'git pull']),
    'git lfs track': ('追踪大文件类型并更新 .gitattributes。', 'git lfs track "*.ext"', 'git lfs track "*.onnx"', ['git add', 'git lfs install']),
}


class LearningService:
    def list_commands(self) -> list[str]:
        return list(_CATALOG)

    def explain(self, command: str) -> dict:
        key = ' '.join(command.strip().lower().split())
        if key not in _CATALOG:
            return {'command': key, 'description': '暂未收录此命令。', 'usage': '',
                    'example': '', 'related_commands': []}
        description, usage, example, related = _CATALOG[key]
        return {'command': key, 'description': description, 'usage': usage,
                'example': example, 'related_commands': related}
