@echo off
rem Registers .asc files to open with PLAN VIEWER MADE BY JUNJAE (current user only).
rem "conhost.exe --headless" keeps the black console window from flashing when a file is opened.
reg add "HKCU\Software\Classes\ASCViewer.File" /ve /d "PLAN VIEWER MADE BY JUNJAE - ASC stowage plan" /f >nul
reg add "HKCU\Software\Classes\ASCViewer.File\shell\open" /v "FriendlyAppName" /d "PLAN VIEWER MADE BY JUNJAE" /f >nul
reg add "HKCU\Software\Classes\ASCViewer.File\shell\open\command" /ve /d "conhost.exe --headless powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%~dp0open-asc.ps1\" \"%%1\"" /f >nul
if exist "%~dp0local\icon.ico" reg add "HKCU\Software\Classes\ASCViewer.File\DefaultIcon" /ve /d "%~dp0local\icon.ico" /f >nul
reg add "HKCU\Software\Classes\.asc" /ve /d "ASCViewer.File" /f >nul
reg add "HKCU\Software\Classes\.asc\OpenWithProgids" /v "ASCViewer.File" /t REG_NONE /f >nul
rem .edi: only added to the "Open with" list (the default program for .edi is left alone)
reg add "HKCU\Software\Classes\.edi\OpenWithProgids" /v "ASCViewer.File" /t REG_NONE /f >nul
echo.
echo  Done. .asc files now open in PLAN VIEWER MADE BY JUNJAE.
echo  (If another program still opens them: right-click an .asc file - Open with - choose another app.)
echo.
pause
