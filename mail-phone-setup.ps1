# Phone mail setup for PLAN VIEWER.
#
# Lets your phone open the "mail" tab using THIS PC's Outlook, with nothing going through any outside server.
# It exposes the local helper (127.0.0.1) to your own private Tailscale network only, over HTTPS, and prints a one-time
# connection code / link to open on the phone. The helper still binds to 127.0.0.1 - only Tailscale (your own devices) can reach it,
# and every request still needs the secret token. No port is opened to the LAN or the public internet.
#
# Run (on this PC, after opening the viewer at least once so the helper is running):
#     powershell -ExecutionPolicy Bypass -File mail-phone-setup.ps1
# Turn it off again:
#     powershell -ExecutionPolicy Bypass -File mail-phone-setup.ps1 -Off
#
# Needs Tailscale installed and signed in (same tailnet on PC and phone), with HTTPS/MagicDNS enabled for the tailnet.
# Keep this file ASCII only (Windows PowerShell 5.1).
param([switch]$Off, [string]$PageUrl = 'https://junjaem.github.io/asc-viewer/')
$ErrorActionPreference = 'Stop'

function Find-Tailscale {
    $c = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    foreach ($p in @("$env:ProgramFiles\Tailscale\tailscale.exe", "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe")) { if (Test-Path $p) { return $p } }
    return $null
}
$ts = Find-Tailscale
if (-not $ts) { Write-Host 'Tailscale is not installed. Install it from https://tailscale.com/download and sign in with the company account, then run this again.' -ForegroundColor Yellow; exit 1 }

if ($Off) {
    try { & $ts serve reset } catch { }
    Write-Host 'Phone mail access turned off (tailscale serve reset). The phone will stop seeing mail; the PC viewer is unaffected.'
    exit 0
}

# tailnet host name (DNSName like myhost.tailXXXX.ts.net.)
$dns = ''
try { $st = (& $ts status --json | ConvertFrom-Json); $dns = [string]$st.Self.DNSName } catch { }
$dns = $dns.TrimEnd('.')
if (-not $dns) { Write-Host 'Could not read the Tailscale name. Make sure Tailscale is signed in (run: tailscale status).' -ForegroundColor Yellow; exit 1 }

# the helper writes its port + token here when the viewer is open
$js = Join-Path $env:TEMP 'asc-viewer\mailsrv.js'
if (-not (Test-Path $js)) {
    # start the helper if it is not running yet
    $srv = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'mail-server.ps1'
    if (Test-Path $srv) { Start-Process -WindowStyle Hidden powershell -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $srv) | Out-Null }
    for ($i = 0; $i -lt 20 -and -not (Test-Path $js); $i++) { Start-Sleep -Milliseconds 400 }
}
if (-not (Test-Path $js)) { Write-Host 'The mail helper is not running. Open a plan in the viewer once (so the mail helper starts), then run this again.' -ForegroundColor Yellow; exit 1 }
$txt = Get-Content -LiteralPath $js -Raw
$port = [regex]::Match($txt, 'port:(\d+)').Groups[1].Value
$token = [regex]::Match($txt, "token:'([0-9a-fA-F]+)'").Groups[1].Value
if (-not $port -or -not $token) { Write-Host 'Could not read the helper port/token. Open a plan in the viewer once and run this again.' -ForegroundColor Yellow; exit 1 }

# expose 127.0.0.1:port on the tailnet over HTTPS (private to your own devices). Try the newer CLI form, then the older one.
$served = $false
foreach ($args in @(@('serve', '--bg', '--https=443', "http://127.0.0.1:$port"), @('serve', '--bg', "$port"))) {
    try { & $ts @args 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { $served = $true; break } } catch { }
}
if (-not $served) { Write-Host 'tailscale serve did not succeed. Your Tailscale version/admin settings may differ. Run this once by hand and tell me the result:' -ForegroundColor Yellow; Write-Host "    `"$ts`" serve --bg http://127.0.0.1:$port" -ForegroundColor Yellow }

$base = "https://$dns"
$jsonBytes = [Text.Encoding]::UTF8.GetBytes((@{ b = $base; t = $token } | ConvertTo-Json -Compress))
$b64 = [Convert]::ToBase64String($jsonBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
$code = 'ascmail.' + $b64
$link = $PageUrl.TrimEnd('/') + '/#mail=' + $code

Write-Host ''
Write-Host '====================  PHONE MAIL SETUP  ====================' -ForegroundColor Cyan
Write-Host 'On your phone, open this link once (it saves the connection):'
Write-Host ''
Write-Host "  $link" -ForegroundColor Green
Write-Host ''
Write-Host 'Or open the viewer on the phone, go to Settings, and paste this code:'
Write-Host ''
Write-Host "  $code" -ForegroundColor Green
Write-Host ''
Write-Host 'Mail comes straight from this PC over your private Tailscale network - no outside server.'
Write-Host 'Keep the code to yourself: anyone with it (and on your tailnet) can read this PC''s mail list.'
Write-Host 'Leave this PC on and signed in to Outlook and Tailscale while you use it from the phone.'
Write-Host '============================================================' -ForegroundColor Cyan
