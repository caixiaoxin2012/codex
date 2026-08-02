@echo off
setlocal

cd /d %~dp0

if not exist .venv (
    py -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --clean --onefile --windowed ^
  --name EPLAN-Tag-Exporter ^
  run_gui.pyw

echo.
echo Build complete: dist\EPLAN-Tag-Exporter.exe
pause
