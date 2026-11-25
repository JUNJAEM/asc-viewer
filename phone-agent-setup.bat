@echo off
rem Sets up the PLAN VIEWER phone helper on this PC (asks for the server address, your id and password once).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0phone-agent-setup.ps1"
echo.
pause
