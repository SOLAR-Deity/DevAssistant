# Dev Assistant

基于 **Python 3.12 + PySide6 + SQLite + Git CLI** 的 Windows 开源开发者助手。界面参照提供的 Dev Assistant UI 设计；GUI 只呈现数据和发送 Signals，所有 CLI 命令均经过 `CommandRunner`，数据库和业务在 Service 层。

## 在 Windows 运行

```powershell
cd dev-assistant-final
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

建议预先安装 [Git for Windows](https://git-scm.com/download/win)。Git LFS、Docker Desktop、Conda、JDK、Node、GitHub CLI 仅在使用其相应功能时需要安装；`git` / `ssh` / `docker` 等命令需可在 PATH 中找到。

## 已集成的页面

- **Dashboard / Projects**：SQLite 保存项目、切换当前目录、从控制台对指定项目 Pull。
- **Git**：初始化、实时改动列表、Diff、Stage All、Commit、Push、Pull、Fetch、分支管理、Checkout、Merge、Tag；Discard 需二次确认，且仅针对已跟踪文件的工作区修改。
- **Terminal**：Git Bash 风格的只读输出，时间、项目、错误码；复制、清屏、SQLite 历史。
- **Environment**：Python/pip/venv/Conda、Java/Maven/Gradle、Node/npm、Docker 检测；导出 requirements/environment.yml 和显式确认后恢复依赖。
- **Git LFS**：检测、仓库级安装、Office/AI/Dataset/Video 扩展名预设追踪、增量 `.gitattributes` 生成。
- **Learning**：离线 Git 命令词典、用法、实例与相关命令；示例展示不会自动执行。
- **Generator**：Python/Java/Node/AI 模板，生成 README、MIT LICENSE、.gitignore、.env.example；拒绝覆盖已存在项目目录。
- **More Tools**：GitHub Remotes/Clone/创建仓库（依赖本机 gh CLI 已认证）和 .github 模板；SSH 公钥检测/生成/测试；Docker 容器/镜像/构建/Compose；项目健康检查；忽略规则合并；本地插件安装、启用、禁用。
- **Settings**：明暗主题、SQLite 历史查看。

## 安全特性与边界

- 所有外部命令走 `app/core/runner.py`：**argv 数组 + `shell=False` + 超时**，不使用任意 shell 命令模板。
- 命令执行在 Qt 工作线程中，避免阻塞 UI；日志与 SQLite 连接按线程短生命周期写入。
- 高风险恢复依赖、删除已跟踪的改动、构建等需要 UI 确认。
- SSH 私钥不读取；新生成密钥默认不带口令，请自行采取适当保护措施。
- GitHub 登录使用本机已配置的 Git Credential Manager / `gh`；本项目不保存账号密码。
- 插件的启用/禁用仅维护元数据与状态；**不会自动执行任何第三方 `main.py`**。完整的隔离插件运行时留给后续版本。
- 提醒：安装依赖、克隆仓库与执行构建来自用户所选项目，需自己确认代码来源可信。

## 本地数据

SQLite、日志、用户插件保存到系统用户数据目录（Windows 通常是 `%LOCALAPPDATA%\DevAssistantLab\DevAssistant`），不会写入源代码工作区。

## 项目结构

```text
main.py
app/
  bootstrap.py
  controllers/app_controller.py
  core/runner.py
  database/store.py
  services/       # Git/LFS/Environment/GitHub/SSH/Docker/Generator/Health/Plugins
  gui/
    main_window.py
    pages/         # Dashboard/Projects/Git/Environment/LFS/Learning/Generator/More/Settings
    widgets/terminal.py
  utils/logging_setup.py
tests/
```

## 运行测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app main.py
```

GUI 自动测试使用离屏 Qt 插件 (`QT_QPA_PLATFORM=offscreen`)。未安装 PySide6 的测试环境可运行不依赖 GUI 的服务层测试。

## 已知限制

此项目是从 UI 参考文档和功能需求重建的完整可运行源码，而非对之前历史下载包的逐字节续写。原有 Phase 1–3 ZIP 未包含在当前环境中。生成环境缺少 PySide6，因而不能宣称在 Windows/GUI 中完成真实启动验收；请在 Windows Python 3.12 安装依赖后运行，项目包含可执行的 GUI smoke test 供检查。

- Terminal 为**命令输出面板**，不是可输入任意指令的交互 shell。
- Git Diff 仅显示文本差异，对未跟踪文件不做内容预览。
- GitHub Repository Creation 依赖用户自行运行 `gh auth login`，不接收密码。
- Git LFS 不自动迁移仓库历史中的大文件。
- 插件系统采用“安全安装 + 状态管理”，不内置任意第三方代码执行器。
