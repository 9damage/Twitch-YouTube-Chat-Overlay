@echo off
setlocal
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Create .venv and install requirements first.
  exit /b 1
)
if not exist "assets" mkdir assets
".venv\Scripts\python.exe" build\generate_ico.py assets\app-icon.png assets\app.ico
if errorlevel 1 exit /b %errorlevel%
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --noconsole --onefile --name TwitchYouTubeChatOverlay --icon assets\app.ico --version-file build\version_info.txt --add-data "assets;assets" --distpath dist --workpath build\pyinstaller --paths . main.py
if errorlevel 1 exit /b %errorlevel%
echo Built dist\TwitchYouTubeChatOverlay.exe
