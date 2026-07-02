@echo off
REM ============================================================================
REM  Rebuild debuginfo_parser.exe  (standalone Windows x64, no Python on target)
REM  One-time setup:  python -m pip install pyinstaller
REM  Run this whenever debuginfo_parser.py changes, then ship dist\debuginfo_parser.exe
REM ============================================================================
cd /d "%~dp0"
set "DBC_FILE=%~dp0..\mss\dbc\MCR1+MFR1+objects_list CAN Matrix to Zelos_V3.0.2_07_TX.dbc"

python -m PyInstaller --onefile --console --name debuginfo_parser ^
    --distpath dist --workpath build_tmp --specpath build_tmp ^
    --add-data "%DBC_FILE%;mss\dbc" ^
    --noconfirm debuginfo_parser.py
if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

rmdir /s /q build_tmp 2>nul

echo.
echo ============================================================
echo  Done  -^>  dist\debuginfo_parser.exe
echo ============================================================
pause
