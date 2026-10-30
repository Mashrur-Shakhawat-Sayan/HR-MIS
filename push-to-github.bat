@echo off
title HR-MIS - upload to GitHub
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\push_to_github.ps1"
echo.
pause
