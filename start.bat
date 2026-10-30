@echo off
title HR-MIS
cd /d "%~dp0"

rem Prefer the Python launcher (installed by python.org), then python.exe on PATH.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 run.py %*
  goto end
)
where python >nul 2>nul
if not errorlevel 1 (
  python run.py %*
  goto end
)

echo.
echo   Python was not found on this PC.
echo   Install Python 3.10 or newer from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" on the first installer screen.
echo.

:end
pause
