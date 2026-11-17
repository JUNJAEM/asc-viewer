@echo off
rem Removes the .asc -> ASC bay plan viewer link (current user only).
reg delete "HKCU\Software\Classes\ASCViewer.File" /f >nul 2>&1
reg delete "HKCU\Software\Classes\.asc\OpenWithProgids" /v "ASCViewer.File" /f >nul 2>&1
for /f "tokens=2,*" %%a in ('reg query "HKCU\Software\Classes\.asc" /ve 2^>nul ^| find "ASCViewer.File"') do reg delete "HKCU\Software\Classes\.asc" /ve /f >nul 2>&1
echo  Removed.
pause
