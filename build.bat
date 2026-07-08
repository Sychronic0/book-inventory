@echo off
cd /d "%~dp0"
echo ╔══════════════════════════════════════════╗
echo ║   Book Library — EXE Builder             ║
echo ╚══════════════════════════════════════════╝
echo.

REM Check PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
)

REM Check Pillow for icon conversion
python -c "import PIL" 2>nul
if errorlevel 1 (
    echo Installing Pillow for icon support...
    python -m pip install Pillow
)

echo.
echo Building EXE...
python -m PyInstaller book_library.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ✗ Build failed. Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo ✓ Build complete!
echo   EXE location: dist\BookLibrary.exe
echo.
echo Copy dist\BookLibrary.exe to wherever you want to run it from.
echo The library.db database will be created next to the EXE on first run.
pause
