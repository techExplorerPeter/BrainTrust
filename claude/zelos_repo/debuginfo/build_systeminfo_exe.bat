@echo off
REM ============================================================================
REM  Rebuild sysinfo_parser.exe  (standalone Windows x64, no Python on target)
REM  One-time setup:  python -m pip install pyinstaller
REM  Run this whenever sysinfo_parser.py changes, then ship dist\sysinfo_parser.exe
REM
REM  Symbolization still needs llvm-symbolizer/llvm-nm on the target PC:
REM    set R5F_CLANG_INSTALL_PATH=<ti-arm-clang install dir>
REM  Without the toolchain, the exe still decodes raw fault registers/addresses.
REM ============================================================================
cd /d "%~dp0"
set "ELF_FILE=%~dp0..\awr2x44P_mmw_demo_mssDDM.xer5f"

if not exist "%ELF_FILE%" (
    echo.
    echo BUILD FAILED: default ELF not found:
    echo   %ELF_FILE%
    pause
    exit /b 1
)

python -m PyInstaller --onefile --console --name sysinfo_parser ^
    --distpath dist --workpath build_tmp --specpath build_tmp ^
    --add-data "%ELF_FILE%;." ^
    --noconfirm sysinfo_parser.py
if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

rmdir /s /q build_tmp 2>nul

echo.
echo ============================================================
echo  Done  -^>  dist\sysinfo_parser.exe
echo ============================================================
pause
