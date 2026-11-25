# Phone helper setup for PLAN VIEWER - run once on each person's office PC (no Tailscale, nothing to install).
#
# After this, the phone app (the team server address, your own login) shows the plan mails of THIS PC's Outlook.
# How it works: a small helper (mail-server.ps1 -Agent) keeps asking the team server "any job for my PC?" over normal outgoing HTTPS.
# Nothing connects into this PC. Only your own login's requests come here, and the helper only reads (never sends mail).
#
# What this script does:
#   1. asks for the server address, your id and your password, and registers this PC with the server (the password is not kept on this PC)
#   2. saves the key the server gave back, encrypted for your Windows account  (%LOCALAPPDATA%\asc-viewer\phone-agent.json)
#   3. registers a scheduled task that keeps the helper running without a window while you are signed in to Windows
#
# Run:        double-click phone-agent-setup.bat     (or: powershell -ExecutionPolicy Bypass -File phone-agent-setup.ps1)
# Turn off:   powershell -ExecutionPolicy Bypass -File phone-agent-setup.ps1 -Off
# Keep this file ASCII only (Windows PowerShell 5.1).
param([string]$Server, [string]$Id, [string]$Password, [switch]$Off)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$task = 'PLAN VIEWER mail agent'
$state = Join-Path $env:LOCALAPPDATA 'asc-viewer'
$cfgFile = Join-Path $state 'phone-agent.json'

function Stop-Agent {
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'mail-server\.ps1"?\s+-Agent' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
function Post-Server($url, [byte[]]$body, $key) {
    # returns @{ code; text }; never throws for an HTTP error status
    $req = [Net.HttpWebRequest]::Create($url)
    $req.Method = 'POST'; $req.Timeout = 30000; $req.UserAgent = 'pv-agent-setup'; $req.ContentType = 'application/json'
    if ($key) { $req.Headers['Authorization'] = 'Bearer ' + $key }
    if ($url -match '^http://(127\.0\.0\.1|localhost)[:/]') { $req.Proxy = $null }
    $req.ContentLength = $body.Length
    if ($body.Length) { $s = $req.GetRequestStream(); $s.Write($body, 0, $body.Length); $s.Close() }
    $resp = $null
    try { $resp = $req.GetResponse() }
    catch { $e = $_.Exception; while ($e -and -not ($e -is [Net.WebException])) { $e = $e.InnerException }; if ($e -and $e.Response) { $resp = $e.Response } else { throw } }
    try { $rd = New-Object IO.StreamReader($resp.GetResponseStream(), [Text.Encoding]::UTF8); return @{ code = [int]$resp.StatusCode; text = $rd.ReadToEnd() } } finally { $resp.Close() }
}

if ($Off) {
    try { Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction Stop; Write-Host 'Scheduled task removed.' } catch { Write-Host 'Scheduled task was not there.' }
    Stop-Agent
    Remove-Item -LiteralPath $cfgFile -Force -ErrorAction SilentlyContinue
    Write-Host 'Phone helper is off on this PC. The viewer on this PC is unaffected.'
    exit 0
}

if (-not (Test-Path (Join-Path $dir 'mail-server.ps1'))) { Write-Host 'mail-server.ps1 is not in this folder. Unzip the whole asc-viewer folder and run this again.' -ForegroundColor Yellow; exit 1 }
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

# ---- 1. who and where
$def = ''
$sf = Join-Path $dir 'phone-agent-server.txt'       # the team server address, put into the team zip by the person who runs the server
if (Test-Path $sf) { try { $def = (Get-Content -LiteralPath $sf -Raw).Trim() } catch { } }
if (-not $Server) { $Server = $def }
if (-not $Server) { $Server = (Read-Host 'Server address (https://....ts.net)').Trim() }
if ($Server -notmatch '^https?://') { $Server = 'https://' + $Server }
$Server = $Server.TrimEnd('/')
if (-not $Id) { $Id = (Read-Host 'Your id').Trim() }
if (-not $Password) {
    $sec = Read-Host 'Your password' -AsSecureString
    $Password = [Runtime.InteropServices.Marshal]::PtrToStringUni([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}

$body = [Text.Encoding]::UTF8.GetBytes((@{ id = $Id; password = $Password; pc = $env:COMPUTERNAME } | ConvertTo-Json -Compress))
try { $r = Post-Server ($Server + '/agent/register') $body $null }
catch { Write-Host ('Could not reach the server ' + $Server + ' : ' + $_.Exception.Message) -ForegroundColor Yellow; Write-Host 'Check the address and that the server PC is on, then run this again.' -ForegroundColor Yellow; exit 1 }
if ($r.code -eq 401) { Write-Host 'Wrong id or password.' -ForegroundColor Yellow; exit 1 }
if ($r.code -eq 429) { Write-Host 'Too many wrong tries. Wait 15 minutes and run this again.' -ForegroundColor Yellow; exit 1 }
if ($r.code -ne 200) { Write-Host ('The server answered ' + $r.code + ': ' + $r.text) -ForegroundColor Yellow; exit 1 }
$reg = $r.text | ConvertFrom-Json

# ---- 2. keep the key (encrypted for this Windows account), not the password
if (-not (Test-Path $state)) { New-Item -ItemType Directory -Path $state | Out-Null }
$enc = ConvertTo-SecureString ([string]$reg.key) -AsPlainText -Force | ConvertFrom-SecureString
[IO.File]::WriteAllText($cfgFile, (@{ server = $Server; user = [string]$reg.user; pc = $env:COMPUTERNAME; key = $enc } | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))

# ---- 3. keep the helper running: started at logon and looked at every 5 minutes (a second copy exits by itself), no window
Stop-Agent
$arg = '--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $dir 'mail-server.ps1') + '" -Agent'
$act = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument $arg -WorkingDirectory $dir
$rep = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$set = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$who = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited
$desc = 'PLAN VIEWER phone helper: asks the team server for this person''s mail jobs and answers them with Outlook on this PC (mail-server.ps1 -Agent).'
try {
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $me
    Register-ScheduledTask -TaskName $task -Action $act -Trigger @($rep, $logon) -Settings $set -Principal $who -Description $desc -Force | Out-Null
} catch {
    Register-ScheduledTask -TaskName $task -Action $act -Trigger $rep -Settings $set -Principal $who -Description $desc -Force | Out-Null
}
Start-ScheduledTask -TaskName $task

# ---- check: has the helper asked the server yet?
$ok = $false
for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
    Start-Sleep -Milliseconds 700
    try { $w = Post-Server ($Server + '/agent/whoami') ([byte[]]@()) ([string]$reg.key); if ($w.code -eq 200) { $j = $w.text | ConvertFrom-Json; if ($null -ne $j.seenAgo -and [int]$j.seenAgo -lt 40) { $ok = $true } } } catch { }
}
Write-Host ''
if ($ok) {
    Write-Host ('Connected: ' + $reg.user + ' on ' + $env:COMPUTERNAME + '  ->  ' + $Server) -ForegroundColor Green
    if ($Server -notmatch '^http://(127\.0\.0\.1|localhost)[:/]') {
        Write-Host 'Open that address on your phone, sign in with the same id and password, and add it to the home screen.'
        Write-Host 'Keep this PC on and signed in to Windows, with Outlook open.'
    }
} else {
    Write-Host 'Registered, but the helper has not reached the server yet.' -ForegroundColor Yellow
    Write-Host ('Look at ' + (Join-Path $env:TEMP 'asc-viewer\agent.log') + ' and run this again.') -ForegroundColor Yellow
    exit 1
}
