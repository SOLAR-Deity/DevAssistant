# Dev Assistant v1.1 构建与发布

## 安装包的真实类型

`DevAssistant-Setup-v1.1.exe` 是 Go 编写的 Windows x64 安装引导程序：内嵌完整 Python/PySide6 项目源码和 Windows 启动器/卸载器，初次安装根据需要下载 Python 3.12.10 x64，创建 venv，然后通过 pip 安装依赖。**不是 PyInstaller 离线单文件程序**，需要联网。

## Python UI 本地验收

在 Windows 安装 Python 3.12 后执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py
```

本测试环境缺少 PySide6 且不能下载，因此 Linux 测试通过不等同 Windows GUI 验收通过。

## 发布复现步骤

1. 安装 Go 1.22+，准备源码仓库与安装器 Go 项目。
2. 生成 `installer/payload/app.zip`：ZIP 根目录包含 `main.py`, `requirements.txt`, `app/` 等源码，不要再额外嵌套一层项目目录。
3. 在 Windows/交叉编译环境中，分别编译：

```powershell
$env:GOOS='windows'; $env:GOARCH='amd64'; $env:CGO_ENABLED='0'
cd installer

go build -trimpath -ldflags '-s -w -H=windowsgui' -o payload/DevAssistant.exe ./cmd/launcher
go build -trimpath -ldflags '-s -w -H=windowsgui' -o payload/Uninstall.exe ./cmd/uninstaller
go test ./internal/bundle

go build -trimpath -ldflags '-s -w' -o DevAssistant-Setup-v1.1.exe .
```

4. 通过 Windows 测试机验证：下载、安装/升级回滚、GUI 运行、Stage/Commit/History、CLI 输入/`cd`、卸载；为正式发布做代码签名。

Installer Go 源码位于交付 ZIP 的 `installer/`，打包前须生成 `payload` 内容。
