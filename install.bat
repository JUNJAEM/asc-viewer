@echo off
rem Registers .asc files to open with the ASC bay plan viewer (current user only).
rem "conhost.exe --headless" keeps the black console window from flashing when a file is opened.
reg add "HKCU\Software\Classes\ASCViewer.File" /ve /d "CASP ASC stowage plan" /f >nul
reg add "HKCU\Software\Classes\ASCViewer.File\shell\open\command" /ve /d "conhost.exe --headless powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%~dp0open-asc.ps1\" \"%%1\"" /f >nul
if exist "%~dp0local\icon.ico" reg add "HKCU\Software\Classes\ASCViewer.File\DefaultIcon" /ve /d "%~dp0local\icon.ico" /f >nul
reg add "HKCU\Software\Classes\.asc" /ve /d "ASCViewer.File" /f >nul
reg add "HKCU\Software\Classes\.asc\OpenWithProgids" /v "ASCViewer.File" /t REG_NONE /f >nul
echo.
echo  Done. .asc files now open in the ASC bay plan viewer.
echo  (If another program still opens them: right-click an .asc file - Open with - choose another app.)
echo.
pause
