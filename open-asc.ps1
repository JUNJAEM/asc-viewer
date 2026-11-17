# Opens a CASP ASC file as a bay plan in the default browser.
# Usage: open-asc.ps1 "C:\path\plan.asc"   (no argument = viewer with the example plan)
# -Static: picture-only page (no scripts) for mail attachments - phone mail apps do not run scripts.
param([string]$Path, [string]$OutFile, [switch]$NoOpen, [switch]$Static)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tpl = [IO.File]::ReadAllText((Join-Path $dir 'viewer.src.html'), [Text.Encoding]::UTF8)
$name = 'viewer'
if ($Path -and (Test-Path -LiteralPath $Path)) {
    $full = (Resolve-Path -LiteralPath $Path).ProviderPath
    $name = [IO.Path]::GetFileName($full)
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($full))
    $jsName = ($name -replace '\\', '\\' -replace "'", "\'")
    $flag = ''; if ($Static) { $flag = 'window.__STATIC__=1;' }
    $tpl = $tpl.Replace('/*__ASC_DATA__*/', $flag + "window.__ASC__={name:'$jsName',b64:'$b64'};")
}
$shipsUrl = ([Uri](Join-Path $dir 'ships.js')).AbsoluteUri
$tpl = $tpl.Replace('src="ships.js"', 'src="' + $shipsUrl + '"')
$fav = ''
$ico = Join-Path $dir 'local\icon.png'   # this PC only (not part of the shared viewer)
if ((Test-Path $ico) -and -not $Static) { $b64i = [Convert]::ToBase64String([IO.File]::ReadAllBytes($ico)); $fav = '<link rel="icon" type="image/png" href="data:image/png;base64,' + $b64i + '"><script>window.__ICON__="data:image/png;base64,' + $b64i + '"</script>' }
$head = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0}[hidden]{display:none!important}</style>' + $fav + '</head><body>'
$html = $head + $tpl + '</body></html>'
if (-not $OutFile) {
    $tmp = Join-Path $env:TEMP 'asc-viewer'
    if (-not (Test-Path $tmp)) { New-Item -ItemType Directory -Path $tmp | Out-Null }
    # keep the temp folder small: drop pages older than 7 days
    Get-ChildItem $tmp -Filter *.html | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item -Force -ErrorAction SilentlyContinue
    $safe = ($name -replace '[^\w\.\-]', '_')
    $OutFile = Join-Path $tmp ($safe + '.html')
}
[IO.File]::WriteAllText($OutFile, $html, (New-Object Text.UTF8Encoding($false)))
if ($Static) {
    # run the page once in a headless browser, keep the drawn result, drop the scripts
    $br = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $br) { throw 'Chrome or Edge not found' }
    $dom = $OutFile + '.dom'
    $prof = Join-Path $env:TEMP 'asc-viewer-headless'
    $bargs = @('--headless=new', '--disable-gpu', '--no-first-run', ('--user-data-dir="' + $prof + '"'), '--allow-file-access-from-files', '--virtual-time-budget=4000', '--dump-dom', ('"' + ([Uri]$OutFile).AbsoluteUri + '"'))
    Start-Process -FilePath $br -ArgumentList $bargs -RedirectStandardOutput $dom -RedirectStandardError ($dom + '.err') -WindowStyle Hidden -Wait
    Remove-Item -LiteralPath ($dom + '.err') -Force -ErrorAction SilentlyContinue
    $d = [IO.File]::ReadAllText($dom, [Text.Encoding]::UTF8)
    Remove-Item -LiteralPath $dom -Force
    $d = [regex]::Replace($d, '(?s)<script\b.*?</script>', '')
    if ($d -notmatch 'class="win sbp"') { throw 'static render failed' }
    [IO.File]::WriteAllText($OutFile, $d, (New-Object Text.UTF8Encoding($false)))
}
if (-not $NoOpen) { Start-Process $OutFile }
