@echo off
setlocal
cd /d "%~dp0"
set PORT=8000

where python >nul 2>nul
if %errorlevel%==0 (
  set PYCMD=python
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    set PYCMD=py
  ) else (
    echo Python was not found on your PATH.
    echo Install Python 3 from https://python.org/downloads then try again.
    pause
    exit /b 1
  )
)

echo Starting the Elden Ring Loadout Optimizer at http://localhost:%PORT%/
echo Press Ctrl+C in this window to stop the server.
start "" http://localhost:%PORT%/
%PYCMD% -m http.server %PORT%
