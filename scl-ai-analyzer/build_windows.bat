@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo SCL AI Analyzer V0.11.1 Windows EXE Build
echo ========================================

if not exist ".venv-build\Scripts\python.exe" (
    echo [1/4] Creating build virtual environment...
    python -m venv .venv-build
    if errorlevel 1 goto :error
)

call .venv-build\Scripts\activate.bat
if errorlevel 1 goto :error

echo [2/4] Installing build dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -e ".[gui,ai,packaging]"
if errorlevel 1 goto :error

echo [3/4] Cleaning old build output...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/4] Building standalone EXE...
python -m PyInstaller --noconfirm --clean packaging\SCL_AI_Analyzer.spec
if errorlevel 1 goto :error

echo.
echo Build complete:
echo %CD%\dist\SCL_AI_Analyzer.exe
echo.
echo NOTE: XML files are limited to 500 MB and pass secure input checks before TIA parsing.
echo NOTE: PLC Code Review rules work offline. AI Chinese explanation requires OPENAI_API_KEY at runtime.
echo.
pause
exit /b 0

:error
echo.
echo BUILD FAILED. Check the error message above.
echo.
pause
exit /b 1
