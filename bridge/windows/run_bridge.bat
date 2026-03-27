@echo off
cd /d %~dp0
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
for /f "usebackq tokens=1,* delims==" %%A in (".env") do set %%A=%%B
python mt5_bridge.py
pause
