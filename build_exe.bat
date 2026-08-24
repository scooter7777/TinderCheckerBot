@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

echo Installing build dependencies...
%PY% -m pip install --upgrade pyinstaller requests pysocks

echo Building EXE...
%PY% -m PyInstaller --noconfirm --onefile --console --name NodeChecker --hidden-import socks ip2location_proxy_checker.py

echo.
echo Done: %~dp0dist\NodeChecker.exe
pause
