# Opens a CASP ASC file as a bay plan in the default browser.
# Usage: open-asc.ps1 "C:\path\plan.asc"   (no argument = viewer with the example plan)
# -Static: picture-only page (no scripts) for mail attachments - phone mail apps do not run scripts.
param([string]$Path, [string]$OutFile, [switch]$NoOpen, [switch]$Static)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Loading picture while the page is being built (optional: splash.jpg next to this script).
$splash = $null
$sp = Join-Path $dir 'local\splash.jpg'   # this PC only (not shared), used first when present
if (-not (Test-Path $sp)) { $sp = Join-Path $dir 'splash.jpg' }
if ((Test-Path $sp) -and -not $NoOpen -and -not $Static) {
    try {
        Add-Type -AssemblyName System.Windows.Forms, System.Drawing
        $simg = [Drawing.Image]::FromFile($sp)
        $splash = New-Object Windows.Forms.Form
        $splash.FormBorderStyle = 'None'; $splash.StartPosition = 'CenterScreen'; $splash.TopMost = $true; $splash.ShowInTaskbar = $false
        $sw = [int][Math]::Min(760, 440 * $simg.Width / $simg.Height); $splash.ClientSize = New-Object Drawing.Size($sw, [int]($sw * $simg.Height / $simg.Width))
        $splash.BackgroundImage = $simg; $splash.BackgroundImageLayout = 'Stretch'
        $splash.Show(); $splash.Refresh()
    } catch { $splash = $null }
}
$tpl = [IO.File]::ReadAllText((Join-Path $dir 'viewer.src.html'), [Text.Encoding]::UTF8)
$name = 'viewer'
# One viewer window for many plans: the page polls this small file, and a later double-click writes the new plan into it.
$tmpDir = Join-Path $env:TEMP 'asc-viewer'
if (-not (Test-Path $tmpDir)) { New-Item -ItemType Directory -Path $tmpDir | Out-Null }
$inbox = Join-Path $tmpDir 'inbox.js'
# Build stamp: lets a later double-click tell an already-open (older) viewer window that a newer version is installed.
$build = [string](Get-Item (Join-Path $dir 'viewer.src.html')).LastWriteTimeUtc.Ticks
$newNote = ('(function(){if((+window.__PV_BUILD__||0)<@B@&&!document.getElementById(''pvNew'')){var d=document.createElement(''div'');d.id=''pvNew'';d.style.cssText=''position:fixed;left:0;right:0;bottom:0;z-index:99;cursor:pointer;padding:9px 14px;background:#b00000;color:#fff;font:700 14px sans-serif;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.4)'';d.textContent=''\uC0C8 \uBC84\uC804\uC774 \uC124\uCE58\uB410\uC5B4\uC694. \uC774 \uCC3D\uC744 \uB2EB\uACE0 \uD50C\uB79C \uD30C\uC77C\uC744 \uB2E4\uC2DC \uC5F4\uBA74 \uC801\uC6A9\uB3FC\uC694. (\uBA54\uC77C\uD568 \u00B7 \uC0C8 \uAE30\uB2A5\uC774 \uADF8\uB54C \uBCF4\uC5EC\uC694)'';d.onclick=function(){d.remove()};document.body.appendChild(d)}})();').Replace('@B@', $build)
$inboxJs = "window.__PV_BUILD__='" + $build + "';window.__INBOX__='" + ([Uri]$inbox).AbsoluteUri + "';window.__MAILSRVJS__='" + ([Uri](Join-Path $tmpDir 'mailsrv.js')).AbsoluteUri + "';"
if ($Static) { $inboxJs = '' }
# Mail tab helper: reads Outlook on this PC for the viewer's mail list (hidden, one instance, stops by itself when unused).
if (-not $Static -and -not $OutFile -and -not $NoOpen) {
    try { $ms = Join-Path $dir 'mail-server.ps1'; if (Test-Path $ms) { Start-Process -FilePath 'conhost.exe' -ArgumentList @('--headless', 'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $ms + '"')) -WindowStyle Hidden } } catch { }
}
Add-Type @'
using System; using System.Text; using System.Runtime.InteropServices;
public class AscWin {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
  // A browser window whose title is "<file> (middle dot) PLAN VIEWER" (optionally followed by " - <browser>") or the empty viewer.
  public static IntPtr Find() {
    IntPtr found = IntPtr.Zero; string dot = "\u00B7 PLAN VIEWER\u200B", emp = "PLAN VIEWER MADE BY JUNJAE\u200B";
    EnumWindows((h, l) => { if (!IsWindowVisible(h)) return true; var s = new StringBuilder(400); GetWindowText(h, s, 400); string t = s.ToString();
      int i = t.IndexOf(dot); bool hit = (i >= 0 && (t.Length == i + dot.Length || t.Substring(i + dot.Length).StartsWith(" - "))) || t == emp || t.StartsWith(emp + " - ");
      if (hit) { found = h; return false; } return true; }, IntPtr.Zero);
    return found; }
  public static void Front(IntPtr h) { if (IsIconic(h)) ShowWindow(h, 9); SetForegroundWindow(h); }
}
'@
if ($Path -and (Test-Path -LiteralPath $Path)) {
    $full = (Resolve-Path -LiteralPath $Path).ProviderPath
    $name = [IO.Path]::GetFileName($full)
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($full))
    $jsName = ($name -replace '\\', '\\' -replace "'", "\'")
    $flag = ''; if ($Static) { $flag = 'window.__STATIC__=1;' }
    # Already-open viewer window? Then hand the file over to it (it shows up there as one more tab) instead of opening another window.
    if (-not $OutFile -and -not $NoOpen -and -not $Static) {
        try {
            $hw = [AscWin]::Find()
            if ($hw -ne [IntPtr]::Zero) {
                $ms = [int64]([DateTime]::UtcNow - [DateTime]'1970-01-01').TotalMilliseconds
                $js = $newNote + "window.__ASC_INBOX__&&window.__ASC_INBOX__({id:'" + [Guid]::NewGuid().ToString('N') + "',t:" + $ms + ",name:'" + $jsName + "',b64:'" + $b64 + "'});"
                [IO.File]::WriteAllText($inbox, $js, (New-Object Text.UTF8Encoding($false)))
                [AscWin]::Front($hw)
                if ($splash) { Start-Sleep -Milliseconds 700; $splash.Close() }
                return
            }
        } catch { }
    }
    $tpl = $tpl.Replace('/*__ASC_DATA__*/', $flag + $inboxJs + "window.__ASC__={name:'$jsName',b64:'$b64'};")
} else { $tpl = $tpl.Replace('/*__ASC_DATA__*/', $inboxJs) }
$shipsUrl = ([Uri](Join-Path $dir 'ships.js')).AbsoluteUri
$tpl = $tpl.Replace('src="ships.js"', 'src="' + $shipsUrl + '"')
$mailCfg = Join-Path $dir 'mail-config.js'   # fixed mail recipients (not on GitHub); optional
if (Test-Path $mailCfg) { $tpl = $tpl.Replace('src="mail-config.js"', 'src="' + ([Uri]$mailCfg).AbsoluteUri + '"') }
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
if (-not $NoOpen) {
    # Open as its own window (no tabs / address bar) when the default browser is Chromium-based, so the next file can find this window by its title.
    $exe = $null
    try {
        $prog = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice').ProgId
        $cmd = (Get-ItemProperty ("Registry::HKEY_CLASSES_ROOT\" + $prog + "\shell\open\command")).'(default)'
        if ($cmd -match '^"([^"]+)"' -or $cmd -match '^(\S+\.exe)') { $cand = $Matches[1]; if ((Test-Path $cand) -and ($cand -match '(chrome|msedge|whale|brave)\.exe$')) { $exe = $cand } }
    } catch { }
    if ($exe -and -not $Static) { Start-Process -FilePath $exe -ArgumentList ('--app="' + ([Uri]$OutFile).AbsoluteUri + '"') } else { Start-Process $OutFile }
}
# keep the loading picture up until the browser window has had time to appear
if ($splash) { $until = [DateTime]::Now.AddMilliseconds(1500); while ([DateTime]::Now -lt $until) { [Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 30 }; $splash.Close() }
