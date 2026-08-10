@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Grab + Gojek Historical Refresh
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install Python 3.12 or later and select "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating private Python environment...
  python -m venv .venv
  if errorlevel 1 goto :failed
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  if errorlevel 1 goto :failed
) else (
  call ".venv\Scripts\activate.bat"
)

if not exist "config\private_aliases.json" (
  echo.
  echo Private aliases are not configured yet.
  echo Running one-time setup...
  python scripts\setup_private_aliases.py
  if errorlevel 1 goto :failed
)

python scripts\refresh_history.py
if errorlevel 1 goto :failed

echo.
echo Refresh completed successfully.
pause
exit /b 0

:failed
echo.
echo The refresh stopped before a safe update could be completed.
pause
exit /b 1
