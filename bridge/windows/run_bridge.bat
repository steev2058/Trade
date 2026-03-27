@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d %~dp0

if not exist .env (
  copy .env.example .env >nul
  echo [INFO] Created .env from .env.example - please fill MT5 and bridge values.
)

if not exist .venv (
  py -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

REM Avoid broken/hash-constrained global pip configs by using isolated install flags
python -m pip install --no-cache-dir --isolated -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
if errorlevel 1 (
  echo [WARN] install failed, retrying without dependency cache...
  python -m pip install --isolated --no-cache-dir MetaTrader5 requests --trusted-host pypi.org --trusted-host files.pythonhosted.org
)

for /f "usebackq tokens=1,* delims==" %%A in (".env") do set %%A=%%B

python mt5_bridge.py
pause
