@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [Dev Assistant] Creating Python 3.12 virtual environment...
  py -3.12 -m venv .venv || goto :error
)
echo [Dev Assistant] Checking dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
echo [Dev Assistant] Starting desktop application...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto :error
exit /b 0
:error
echo.
echo [Dev Assistant] Unable to start. Check Python 3.12 and internet access.
pause
exit /b 1
