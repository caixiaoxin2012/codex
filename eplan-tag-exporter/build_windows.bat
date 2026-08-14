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
  --name EPLAN-Tag-Exporter-v1.1.3 ^
  --icon assets\xilin-app-icon.ico ^
  --add-data "assets\xilin-app-icon.ico;assets" ^
  --add-data "assets\xilin-app-icon.png;assets" ^
  run_gui.pyw

echo.
echo Build complete: dist\EPLAN-Tag-Exporter-v1.1.3.exe
pause
