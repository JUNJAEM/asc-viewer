# Server setup for the PLAN VIEWER phone app: run on the ONE server PC only (Tailscale Funnel + PWA).
# Phones and the other PCs only use the public address; they do not install Tailscale.
# (Each person's office PC runs phone-agent-setup instead - see that file.)
#
# What it does:
#   1. makes phone-server.json (users: id + random password) if it is not there yet
#   2. registers a scheduled task that runs phone-watch.py every 2 minutes without a window:
#      it starts phone-server.py when it is not running and re-attaches Tailscale when the public address stops answering
#   3. turns on Tailscale Funnel for the server port and prints the fixed public address (https://<this pc>.ts.net)
#   4. sets up the mail helper of this PC's own user (the first user in phone-server.json), talking to the server locally
#
# People:  python phone-server.py --add-user <id> [name]   |   --users   |   --set-password <id>   |   --del-user <id>
#
# Run:        powershell -ExecutionPolicy Bypass -File phone-setup.ps1
# Turn off:   powershell -ExecutionPolicy Bypass -File phone-setup.ps1 -Off      (public address closed, task removed, server stopped)
#
# Needs Tailscale installed and signed in on this PC, and Python (the same one tools\*.py use).
# The server only listens on 127.0.0.1; the internet reaches it through Tailscale Funnel only, and every page needs the login.
# Keep this file ASCII only (Windows PowerShell 5.1).
param([switch]$Off)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$task = 'PLAN VIEWER phone server'

function Find-Tailscale {
    $c = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    foreach ($p in @("$env:ProgramFiles\Tailscale\tailscale.exe", "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe")) { if (Test-Path $p) { return $p } }
    return $null
}
function Run-Ts($ts, $tsArgs, $sec) {
    # tailscale can wait for an approval in the browser: never hang here, give back what it printed so far
    $job = Start-Job { param($ts, $a) & $ts @a 2>&1 | ForEach-Object { "$_" } } -ArgumentList $ts, $tsArgs
    $done = Wait-Job $job -Timeout $sec
    $out = ((Receive-Job $job 2>&1 | ForEach-Object { "$_" }) -join "`n")
    if (-not $done) { Stop-Job $job }
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    return @{ done = [bool]$done; out = $out }
}
function Local-Ok($port) {
    try { return ((Invoke-WebRequest "http://127.0.0.1:$port/healthz" -UseBasicParsing -TimeoutSec 4 -Proxy $null).Content -eq 'ok') } catch { return $false }
}

$ts = Find-Tailscale
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host 'Python is not installed (python.exe not found). Install it from https://www.python.org/downloads/ and run this again.' -ForegroundColor Yellow; exit 1 }
$pyw = Join-Path (Split-Path -Parent $py.Source) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = $py.Source }
$info = (& $py.Source (Join-Path $dir 'phone-server.py') --init | Out-String | ConvertFrom-Json)
$port = [int]$info.port

if ($Off) {
    try { Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction Stop; Write-Host 'Scheduled task removed.' } catch { Write-Host 'Scheduled task was not there.' }
    $own = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($id in $own) { $pr = Get-Process -Id $id -ErrorAction SilentlyContinue; if ($pr -and $pr.ProcessName -match '^python') { Stop-Process -Id $id -Force; Write-Host "Server stopped (pid $id)." } }
    if ($ts) { $r = Run-Ts $ts @('funnel', '--https=443', 'off') 30; Write-Host ('Funnel off: ' + $r.out.Trim()) }
    & (Join-Path $dir 'phone-agent-setup.ps1') -Off
    Write-Host 'Phone app access is off. The viewer on this PC is unaffected.'
    exit 0
}

if (-not $ts) {
    Write-Host 'Tailscale is not installed.' -ForegroundColor Yellow
    Write-Host '  1) Install it from https://tailscale.com/download/windows' -ForegroundColor Yellow
    Write-Host '  2) Click the Tailscale icon in the tray and sign in' -ForegroundColor Yellow
    Write-Host '  3) Run this script again' -ForegroundColor Yellow
    exit 1
}
$dns = ''
try { $dns = ([string](& $ts status --json | Out-String | ConvertFrom-Json).Self.DNSName).TrimEnd('.') } catch { }
if (-not $dns) { Write-Host 'Tailscale is not signed in. Click the Tailscale icon in the tray, sign in, then run this again.' -ForegroundColor Yellow; exit 1 }

# ---- scheduled task: every 2 minutes (and at logon when this account is allowed to set that), no window
$act = New-ScheduledTaskAction -Execute $pyw -Argument ('"' + (Join-Path $dir 'phone-watch.py') + '"') -WorkingDirectory $dir
$rep = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2)
$set = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$who = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$desc = 'Keeps the PLAN VIEWER phone server running and its public address reachable (phone-watch.py).'
try {
    $logon = New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
    Register-ScheduledTask -TaskName $task -Action $act -Trigger @($rep, $logon) -Settings $set -Principal $who -Description $desc -Force | Out-Null
} catch {
    Register-ScheduledTask -TaskName $task -Action $act -Trigger $rep -Settings $set -Principal $who -Description $desc -Force | Out-Null
}
Start-ScheduledTask -TaskName $task
for ($i = 0; $i -lt 30 -and -not (Local-Ok $port); $i++) { Start-Sleep -Milliseconds 500 }
if (-not (Local-Ok $port)) { Write-Host "The server did not start on 127.0.0.1:$port. See $env:LOCALAPPDATA\asc-viewer\phone-server.log" -ForegroundColor Yellow; exit 1 }

# ---- public address
$r = Run-Ts $ts @('funnel', '--bg', "$port") 25
$st = (Run-Ts $ts @('funnel', 'status') 20).out
if ($st -notmatch 'Funnel on') {
    $link = [regex]::Match($r.out, 'https://login\.tailscale\.com/\S+').Value
    Write-Host ''
    Write-Host 'Funnel is not turned on yet.' -ForegroundColor Yellow
    if ($link) { Write-Host 'Open this link, allow Funnel for your tailnet, then run this script again:' -ForegroundColor Yellow; Write-Host "  $link" -ForegroundColor Green }
    else { Write-Host 'tailscale said:' -ForegroundColor Yellow; Write-Host $r.out }
    exit 2
}

# ---- the team zip carries this address so the others do not have to type it (tools\dist-build\build_dist.py)
[IO.File]::WriteAllText((Join-Path $dir 'phone-agent-server.txt'), "https://$dns", (New-Object Text.UTF8Encoding($false)))

# ---- this PC's own user: the mail helper talks to the server on this PC directly
$owner = @((Get-Content -LiteralPath $info.config -Raw -Encoding UTF8 | ConvertFrom-Json).users)[0]
if ($owner) {
    & (Join-Path $dir 'phone-agent-setup.ps1') -Server "http://127.0.0.1:$port" -Id ([string]$owner.id) -Password ([string]$owner.password)
    if ($LASTEXITCODE) { Write-Host 'The mail helper of this PC did not start (see above). The address still works; mail will not show until it does.' -ForegroundColor Yellow }
}

Write-Host ''
Write-Host '====================  PLAN VIEWER PHONE APP  ====================' -ForegroundColor Cyan
Write-Host 'Address (fixed):'
Write-Host "  https://$dns" -ForegroundColor Green
Write-Host ''
Write-Host "Ids and passwords are in:  $($info.config)"
if ($info.created) { Write-Host '  (just created with a random password - open the file to read or change it)' }
Write-Host 'Add a person:  python phone-server.py --add-user <id> [name]'
Write-Host ''
Write-Host 'Share link (whoever has it sees the plan mails of this PC with no login - give it to the team only):'
Write-Host ('  ' + (& $py.Source (Join-Path $dir 'phone-server.py') --link | Out-String).Trim()) -ForegroundColor Green
Write-Host '  new link (the old one stops working):  python phone-server.py --new-link'
Write-Host ''
Write-Host 'A new public address can take about 10 minutes to open the first time.'
Write-Host 'Keep this PC on and signed in to Windows, Outlook and Tailscale.'
Write-Host '=================================================================' -ForegroundColor Cyan
