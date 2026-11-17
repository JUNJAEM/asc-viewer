# Watches the Outlook inbox (and its subfolders). When a mail with an .asc attachment arrives,
# makes a phone-friendly plan page (open-asc.ps1 -Static) and mails it to yourself.
# Keep this file ASCII only (Windows PowerShell 5.1).
#   asc-mail-watch.ps1          run forever, check every minute (started at logon by install-mail.bat)
#   asc-mail-watch.ps1 -Test    convert the newest .asc mail of the last 30 days once, then exit
param([switch]$Test, [int]$Every = 60)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$data = Join-Path $env:LOCALAPPDATA 'asc-viewer'
if (-not (Test-Path $data)) { New-Item -ItemType Directory -Path $data | Out-Null }
$stateFile = Join-Path $data 'mail-state.txt'    # line 1 = last check time, other lines = handled mail ids
$logFile = Join-Path $data 'mail-log.txt'
$work = Join-Path $env:TEMP 'asc-viewer-mail'

function Log($m) {
    $line = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + '  ' + $m
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    if ($Test) { Write-Output $line }
}

if (-not $Test) {
    $mutex = New-Object Threading.Mutex($false, 'Local\asc-viewer-mail-watch')
    if (-not $mutex.WaitOne(0)) { exit }     # already running
}

function AscAttachments($mail) {
    $list = @()
    foreach ($a in $mail.Attachments) { if ($a.FileName -match '\.asc$') { $list += $a } }
    return , $list
}

function Convert-Mail($ol, $mail, $me) {
    $atts = AscAttachments $mail
    if ($atts.Count -eq 0) { return $false }
    if (Test-Path $work) { Remove-Item -LiteralPath $work -Recurse -Force }
    New-Item -ItemType Directory -Path $work | Out-Null
    $out = $ol.CreateItem(0)
    $names = @()
    foreach ($a in $atts) {
        $safe = ($a.FileName -replace '[^\w\.\-]', '_')
        $src = Join-Path $work $safe
        $a.SaveAsFile($src)
        $html = Join-Path $work ($safe + '.html')
        & (Join-Path $dir 'open-asc.ps1') -Path $src -OutFile $html -NoOpen -Static
        [void]$out.Attachments.Add($html)
        $names += $a.FileName
    }
    $out.To = $me
    $out.Subject = '[ASC] ' + $mail.Subject
    $out.Body = "ASC plan for phone - tap the attachment.`r`n`r`nFrom: " + $mail.SenderName + "`r`nReceived: " + $mail.ReceivedTime.ToString('yyyy-MM-dd HH:mm') + "`r`nFile: " + ($names -join ', ')
    $out.Send()
    Log ('sent: ' + ($names -join ', '))
    return $true
}

function Folders($f) { $f; foreach ($s in $f.Folders) { Folders $s } }

function Scan($since, $done, $max) {
    # returns the number of mails converted
    if (-not (Get-Process OUTLOOK -ErrorAction SilentlyContinue)) { return 0 }   # never start Outlook ourselves
    $ol = New-Object -ComObject Outlook.Application
    $ns = $ol.Session
    $me = $ns.Accounts.Item(1).SmtpAddress
    $n = 0
    foreach ($f in (Folders $ns.GetDefaultFolder(6))) {
        $items = $f.Items
        $items.Sort('[ReceivedTime]', $true)
        foreach ($m in $items) {
            if ($m.Class -ne 43) { continue }                 # mail items only
            if ($m.ReceivedTime -lt $since) { break }
            if ($m.Subject -like '`[ASC`] *') { continue }    # our own converted mail
            $id = $m.EntryID
            if ($done.Contains($id)) { continue }
            if ((AscAttachments $m).Count -eq 0) { continue }
            try { if (Convert-Mail $ol $m $me) { $n++ } } catch { Log ('ERROR ' + $m.Subject + ' : ' + $_.Exception.Message) }
            [void]$done.Add($id)
            if ($max -and $n -ge $max) { return $n }
        }
    }
    return $n
}

if ($Test) {
    $n = Scan (Get-Date).AddDays(-30) (New-Object Collections.Generic.HashSet[string]) 1
    if ($n -eq 0) { Log 'test: no mail with an .asc attachment in the last 30 days (or Outlook is not running)' }
    exit
}

# state
$last = Get-Date
$done = New-Object Collections.Generic.HashSet[string]
if (Test-Path $stateFile) {
    $lines = @(Get-Content -LiteralPath $stateFile)
    if ($lines.Count -gt 0) { try { $last = [datetime]::ParseExact($lines[0], 'o', $null) } catch {} }
    foreach ($l in ($lines | Select-Object -Skip 1)) { if ($l) { [void]$done.Add($l) } }
}
Log 'watch started'
while ($true) {
    try {
        $now = Get-Date
        # mails that arrived while the PC was off are picked up too, but never older than 3 days
        $since = $last.AddMinutes(-10)
        $floor = $now.AddDays(-3)
        if ($since -lt $floor) { $since = $floor }
        [void](Scan $since $done 0)
        $last = $now
        $keep = @($done) | Select-Object -Last 500
        Set-Content -LiteralPath $stateFile -Value (@($last.ToString('o')) + $keep) -Encoding ASCII
    } catch { Log ('ERROR ' + $_.Exception.Message) }
    Start-Sleep -Seconds $Every
}
