@echo off
rem Starts the ASC mail watcher now and at every logon (current user only).
rem It mails a phone-friendly plan page to yourself whenever a mail with an .asc attachment arrives.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\ASC mail watch.lnk'); $s.TargetPath='powershell.exe'; $s.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%~dp0asc-mail-watch.ps1\"'; $s.WindowStyle=7; $s.Save(); Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File','\"%~dp0asc-mail-watch.ps1\"'"
echo.
echo  Done. ASC mails are now converted and sent to you while this PC and Outlook are running.
echo  To stop: run uninstall-mail.bat
echo.
pause
