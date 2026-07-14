@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py windows_launcher.py
  goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
  python windows_launcher.py
  goto :eof
)

set BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
if exist "%BUNDLED_PYTHON%" (
  "%BUNDLED_PYTHON%" windows_launcher.py
  goto :eof
)

echo Python introuvable. Installe Python puis lance:
echo   python windows_launcher.py
pause
