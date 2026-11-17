@echo off
rem Stops the ASC mail watcher and removes it from logon.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item ([Environment]::GetFolderPath('Startup')+'\ASC mail watch.lnk') -Force -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -like '*asc-mail-watch.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo.
echo  Done. The ASC mail watcher is stopped.
echo.
pause
