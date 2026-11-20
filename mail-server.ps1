# Mail helper for the PLAN VIEWER "mail" tab (PC only).
# Reads Outlook on this PC (read-only) and hands the viewer page a list of recent mails that carry .asc / .edi plans, and the attachment itself when asked.
# Nothing leaves this PC: it only answers on 127.0.0.1 and only to requests that carry the random token written to %TEMP%\asc-viewer\mailsrv.js.
# Started (hidden) by open-asc.ps1; stops by itself when no viewer page has asked for anything for 15 minutes.
# Keep this file ASCII only (Windows PowerShell 5.1). Category names and sender rules live in mail-rules.json (UTF-8, this PC / team only).
param([int]$Days = 7)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tmp = Join-Path $env:TEMP 'asc-viewer'
if (-not (Test-Path $tmp)) { New-Item -ItemType Directory -Path $tmp | Out-Null }
$mutex = New-Object Threading.Mutex($false, 'Local\asc-viewer-mail-server')
if (-not $mutex.WaitOne(0)) { exit }     # already running
$log = Join-Path $tmp 'mailsrv.log'
function Log($m) { try { Add-Content -LiteralPath $log -Value ((Get-Date).ToString('MM-dd HH:mm:ss') + '  ' + $m) -Encoding UTF8 } catch { } }

# ---- listener on a free loopback port + token file for the page
$listener = $null; $port = 0
foreach ($p in 47815..47835) { try { $l = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $p); $l.Start(); $listener = $l; $port = $p; break } catch { } }
if (-not $listener) { Log 'no free port'; exit }
# token: persistent (kept in mailsrv-token.txt next to this file) so a phone that saved the connection keeps working across restarts. Never committed; stays on this PC.
$tokFile = Join-Path $dir 'mailsrv-token.txt'
$token = ''
if (Test-Path $tokFile) { try { $token = (Get-Content -LiteralPath $tokFile -Raw).Trim() } catch { } }
if ($token -notmatch '^[0-9a-fA-F]{32,}$') { $token = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N'); try { [IO.File]::WriteAllText($tokFile, $token, (New-Object Text.UTF8Encoding($false))) } catch { } }
[IO.File]::WriteAllText((Join-Path $tmp 'mailsrv.js'), "window.__MAILSRV__={port:$port,token:'$token'};", (New-Object Text.UTF8Encoding($false)))
Log "listening on $port"

# ---- rules: first match wins. Each rule: cat (name shown), and any of from (domain endings), fromName (regex), subject (regex on subject + file names), folder (text in folder path)
$rules = @()
$rf = Join-Path $dir 'mail-rules.json'
if (Test-Path $rf) { try { $rules = @((Get-Content -LiteralPath $rf -Raw -Encoding UTF8 | ConvertFrom-Json).rules) } catch { Log ('rules: ' + $_.Exception.Message) } }
function CatOf($o) {
    foreach ($r in $rules) {
        $ok = $true
        if ($r.from) { $hit = $false; foreach ($d in $r.from) { if ($o.fd -eq $d -or $o.fd.EndsWith('.' + $d) -or ($d.StartsWith('.') -and $o.fd.EndsWith($d))) { $hit = $true; break } }; if (-not $hit) { $ok = $false } }
        if ($ok -and $r.fromName -and ($o.from -notmatch $r.fromName)) { $ok = $false }
        if ($ok -and $r.subject -and (($o.sub + ' ' + ($o.files | ForEach-Object { $_.n })) -notmatch $r.subject)) { $ok = $false }
        if ($ok -and $r.folder -and ($o.folder.IndexOf([string]$r.folder, [StringComparison]::OrdinalIgnoreCase) -lt 0)) { $ok = $false }
        if ($ok) { return [string]$r.cat }
    }
    if ($o.fd.EndsWith('.jp')) { return 'JP' }
    if ($o.fd.EndsWith('.cn')) { return 'CN' }
    return 'ETC'
}

# ---- Outlook scan (read-only), kept in memory and refreshed incrementally
$cache = @{}; $lastScan = [DateTime]::MinValue; $scanDays = 0
function Outlook { try { return [Runtime.InteropServices.Marshal]::GetActiveObject('Outlook.Application') } catch { return (New-Object -ComObject Outlook.Application) } }
# OUTBOUND mail writing (looks up the schedule, copies the style of an earlier mail, opens a new-mail window; never sends)
$outOk = $false; try { . (Join-Path $dir 'mail-out.ps1'); $outOk = $true } catch { Log ('mail-out: ' + $_.Exception.Message) }
function OutPrep($q) {
    $pp = @($q.ports | Where-Object { $_ } | ForEach-Object { [string]$_ } | Select-Object -Unique)
    $r = Out-Rotation ([string]$q.vsl) ([string]$q.voy) $pp
    $svc = if ($r.svc) { $r.svc } else { [string]$q.svc }
    # the plans' ports in the order she calls them; and Korean calls at the start of this voyage that no plan was given for
    $order = @(); $missing = @()
    if ($r.ok) {
        foreach ($c in $r.calls) { if (-not $c.skip -and -not $c.next -and ($pp -contains $c.p) -and ($order -notcontains $c.p)) { $order += $c.p } }
        foreach ($c in $r.calls) { if (-not $c.kr) { break }; if (-not $c.skip -and -not $c.next -and ($pp -notcontains $c.p) -and ($c.p -eq 'PUS' -or $c.p -eq 'PNC')) { $missing += $c.p } }
    }
    foreach ($x in $pp) { if ($order -notcontains $x) { $order += $x } }
    $cand = @(Out-Find ([string]$q.vsl) $r.name $svc $order $r.ports)
    $id = [string]$q.id; if (-not $id -and $cand.Count) { $id = $cand[0].id }
    $mail = $null; if ($id) { $mail = Out-Build $id ([string]$q.voy) ([string]$q.rot) $r.calls $order; $mail.imgs = Out-Imgs $id $mail.html }
    return (@{ rot = $r; cand = $cand; mail = $mail; svc = $svc; ports = $order; missing = $missing } | ConvertTo-Json -Depth 7 -Compress)
}
# rotation of one voyage from the company port schedule, for the Summary line of the viewer (read-only look-up)
function RotJson($q) {
    $v = ([string]$q['vsl']).ToUpper(); $y = ([string]$q['voy']).ToUpper()
    if ($v -notmatch '^[A-Z0-9]{3,5}$' -or $y -notmatch '^\d{3,4}[A-Z]$') { return '{"ok":false,"why":"noinput"}' }
    $pp = @(([string]$q['ports']).ToUpper() -split ',' | Where-Object { $_ -match '^[A-Z]{3}$' })
    return ((Out-Rotation $v $y $pp $true) | ConvertTo-Json -Depth 5 -Compress)
}
# CBF link of the LOAD LIST (read-only look-ups): booking forecast, box list, closing notices in the mailbox
function QVoy($q) { $v = ([string]$q['vsl']).ToUpper(); $y = ([string]$q['voy']).ToUpper(); $p = ([string]$q['port']).ToUpper(); if ($v -notmatch '^[A-Z0-9]{3,5}$' -or $y -notmatch '^\d{3,4}[A-Z]$' -or $p -notmatch '^[A-Z]{5}$') { return $null }; return @($v, $y, $p) }
function CbfJson($q) { $a = QVoy $q; if (-not $a) { return '{"ok":false,"why":"noinput"}' }; return ((Out-Cbf $a[0] $a[1] $a[2]) | ConvertTo-Json -Depth 6 -Compress) }
function CllJson($q) { $a = QVoy $q; if (-not $a) { return '{"ok":false,"why":"noinput"}' }; return ((Out-Cll $a[0] $a[1] $a[2] ([string]$q['pods'])) | ConvertTo-Json -Depth 5 -Compress) }
function BkJson($q) { $a = QVoy $q; if (-not $a) { return '{"ok":false,"why":"noinput"}' }; return ((Out-Bk $a[0] $a[1] $a[2] ([string]$q['etd'])) | ConvertTo-Json -Depth 5 -Compress) }
function CloseMailJson($q) { $a = QVoy $q; if (-not $a) { return '{"mails":[]}' }; return (@{ mails = @(Out-CloseMail $a[0] ([string]$q['name']) $a[1]) } | ConvertTo-Json -Depth 5 -Compress) }
function OutOpen($q) {
    $mode = if ($q.send -eq $true) { 'send' } elseif ($q.draft) { 'draft' } else { 'show' }
    $rcp = $null; if ($q.PSObject.Properties['to'] -or $q.PSObject.Properties['cc']) { $rcp = @{ to = @($q.to); cc = @($q.cc) } }     # only when the person changed the recipients
    return ((Out-Open ([string]$q.id) ([string]$q.voy) ([string]$q.subject) ([string]$q.rot) @($q.files) $mode @($q.ports) $null ([string]$q.html) $rcp) | ConvertTo-Json -Compress)
}

function Walk($f, $path, $since, $sentId) {
    $p = if ($path) { $path + '/' + $f.Name } else { $f.Name }
    try {
        if ($f.DefaultItemType -eq 0 -and $f.Items.Count -gt 0) {
            $field = if ($f.EntryID -eq $sentId) { 'SentOn' } else { 'ReceivedTime' }
            $items = $f.Items.Restrict("[$field] >= '" + $since.ToString('yyyy-MM-dd HH:mm') + "'")
            foreach ($m in $items) {
                try {
                    if ($m.Class -ne 43 -or $m.Attachments.Count -eq 0) { continue }
                    $id = $m.EntryID; if ($script:cache.ContainsKey($id)) { continue }
                    $files = @(); $k = 0
                    foreach ($a in $m.Attachments) { $k++; if ($a.FileName -match '\.(asc|edi)$') { $files += @{ i = $k; n = [string]$a.FileName; s = [int]$a.Size } } }
                    if (-not $files.Count) { continue }
                    $addr = ''; try { $addr = if ($m.SenderEmailType -eq 'EX') { $m.Sender.GetExchangeUser().PrimarySmtpAddress } else { $m.SenderEmailAddress } } catch { }
                    $when = if ($field -eq 'SentOn') { $m.SentOn } else { $m.ReceivedTime }
                    $o = @{ id = $id; sub = [string]$m.Subject; from = [string]$m.SenderName; fd = ([string]$addr).Split('@')[-1].ToLower(); ad = ([string]$addr).ToLower(); when = $when.ToString('yyyy-MM-dd HH:mm'); folder = $p; files = $files }
                    $o.cat = CatOf $o
                    $script:cache[$id] = $o
                } catch { }
            }
        }
    } catch { }
    foreach ($c in $f.Folders) { Walk $c $p $since $sentId }
}
function Scan($days) {
    $ns = (Outlook).GetNamespace('MAPI')
    $since = (Get-Date).AddDays(-$days)
    if ($script:lastScan -ne [DateTime]::MinValue -and $days -le $script:scanDays) { $since = $script:lastScan.AddMinutes(-10) }
    $t0 = Get-Date
    $sentId = ''; try { $sentId = $ns.GetDefaultFolder(5).EntryID } catch { }
    $root = $ns.GetDefaultFolder(6).Parent      # the mailbox that holds the inbox
    Walk $root '' $since $sentId
    $script:lastScan = $t0; if ($days -gt $script:scanDays) { $script:scanDays = $days }
    $cut = (Get-Date).AddDays(-[Math]::Max($days, $script:scanDays)).ToString('yyyy-MM-dd HH:mm')
    foreach ($k in @($script:cache.Keys)) { if ($script:cache[$k].when -lt $cut) { $script:cache.Remove($k) } }
    Log ("scan " + $days + "d: " + $script:cache.Count + " mails, " + [int]((Get-Date) - $t0).TotalSeconds + "s")
}
function ListJson($days) {
    if (((Get-Date) - $script:lastScan).TotalSeconds -gt 45 -or $days -gt $script:scanDays) { Scan $days }
    $cut = (Get-Date).AddDays(-$days).ToString('yyyy-MM-dd HH:mm'); $seen = @{}; $out = New-Object Collections.ArrayList
    foreach ($o in ($script:cache.Values | Sort-Object { $_.when } -Descending)) {
        if ($o.when -lt $cut) { continue }
        $key = $o.sub + '|' + $o.when + '|' + $o.fd + '|' + (($o.files | ForEach-Object { $_.n }) -join ',')
        if ($seen.ContainsKey($key)) { continue }; $seen[$key] = 1
        [void]$out.Add(@{ id = $o.id; sub = $o.sub; from = $o.from; fd = $o.fd; when = $o.when; cat = $o.cat; files = @($o.files) })
    }
    return (@{ at = (Get-Date).ToString('HH:mm'); days = $days; items = @($out) } | ConvertTo-Json -Depth 5 -Compress)
}
# ---- where a plan came from: the mail that carried a file of this name (or the given mail). The viewer uses it to guess the port when the file name does not say it.
# Gives the subject, the first part of the text and the names of other plans from the same sender. The answer goes to the viewer page on this PC only; nothing is logged.
function NameKey($n) { $k = ([string]$n).ToLower() -replace '\.(asc|edi)$', ''; $k = $k -replace '(\s*\(\d+\)|__\d+_)$', ''; return ($k -replace '[^a-z0-9]', '') }
function MailHint($q) {
    $d = [Math]::Max(7, $script:scanDays)
    if (((Get-Date) - $script:lastScan).TotalSeconds -gt 45 -or $d -gt $script:scanDays) { Scan $d }
    $o = $null
    if ($q['id']) { if ($script:cache.ContainsKey($q['id'])) { $o = $script:cache[$q['id']] } }
    elseif ($q['name']) { $k = NameKey $q['name']
        foreach ($c in ($script:cache.Values | Sort-Object { $_.when } -Descending)) { foreach ($f in $c.files) { if ((NameKey $f.n) -eq $k) { $o = $c; break } }; if ($o) { break } } }
    if (-not $o) { return '{"found":false}' }
    $body = ''; try { $body = [string](Outlook).GetNamespace('MAPI').GetItemFromID($o.id).Body; if ($body.Length -gt 3000) { $body = $body.Substring(0, 3000) } } catch { }
    $peers = @(); if ($o.ad) { foreach ($c in $script:cache.Values) { if ($c.ad -eq $o.ad) { foreach ($f in $c.files) { $peers += [string]$f.n } } } }
    return (@{ found = $true; sub = $o.sub; from = $o.from; body = $body; peers = @($peers | Select-Object -Unique -First 150) } | ConvertTo-Json -Depth 4 -Compress)
}
function FileBytes($id, $i) {
    $ns = (Outlook).GetNamespace('MAPI'); $m = $ns.GetItemFromID($id); $a = $m.Attachments.Item([int]$i)
    if ($a.FileName -notmatch '\.(asc|edi)$') { throw 'not a plan file' }
    $t = Join-Path $tmp ('att_' + [Guid]::NewGuid().ToString('N') + '.tmp'); $a.SaveAsFile($t)
    $b = [IO.File]::ReadAllBytes($t); Remove-Item -LiteralPath $t -Force; return $b
}

# ---- tiny HTTP loop
function Send($st, $code, $type, [byte[]]$body) {
    $h = "HTTP/1.1 $code`r`nContent-Type: $type`r`nContent-Length: " + $body.Length + "`r`nAccess-Control-Allow-Origin: *`r`nAccess-Control-Allow-Methods: GET, POST, OPTIONS`r`nAccess-Control-Allow-Headers: Content-Type`r`nAccess-Control-Allow-Private-Network: true`r`nCache-Control: no-store`r`nConnection: close`r`n`r`n"
    $hb = [Text.Encoding]::ASCII.GetBytes($h); $st.Write($hb, 0, $hb.Length); if ($body.Length) { $st.Write($body, 0, $body.Length) }
}
$utf8 = New-Object Text.UTF8Encoding($false); $lastReq = Get-Date
while ($true) {
    if (-not $listener.Pending()) { if (((Get-Date) - $lastReq).TotalMinutes -gt 15) { break }; Start-Sleep -Milliseconds 200; continue }
    $c = $listener.AcceptTcpClient()
    try {
        # read the whole request: the first line and headers, then (for POST) as many bytes as Content-Length says
        $c.ReceiveTimeout = 5000; $st = $c.GetStream(); $buf = New-Object byte[] 65536; $ms = New-Object IO.MemoryStream; $hEnd = -1; $need = 0
        while ($true) {
            $n = $st.Read($buf, 0, $buf.Length); if ($n -le 0) { break }; $ms.Write($buf, 0, $n)
            if ($hEnd -lt 0) { $txt = [Text.Encoding]::ASCII.GetString($ms.GetBuffer(), 0, [int][Math]::Min($ms.Length, 16384)); $i = $txt.IndexOf("`r`n`r`n")
                if ($i -ge 0) { $hEnd = $i + 4; if ($txt.Substring(0, $i) -match '(?im)^Content-Length:\s*(\d+)') { $need = [int]$Matches[1] } } }
            if ($hEnd -ge 0 -and ($ms.Length - $hEnd) -ge $need) { break }
            if ($ms.Length -gt 12MB) { break }
        }
        $all = $ms.ToArray(); if ($hEnd -lt 0) { $hEnd = $all.Length }
        $line = ([Text.Encoding]::ASCII.GetString($all, 0, [Math]::Min($hEnd, 4096)) -split "`r`n")[0]
        if ($line -match '^OPTIONS ') { Send $st '204 No Content' 'text/plain' ([byte[]]@()); continue }
        if ($line -notmatch '^(GET|POST) (/[a-z]*)\??(\S*) ') { Send $st '400 Bad Request' 'text/plain' ([byte[]]@()); continue }
        $verb = $Matches[1]; $path = $Matches[2]; $qs = $Matches[3]; $q = @{}
        foreach ($kv in ($qs -split '&')) { $x = $kv -split '=', 2; if ($x.Count -eq 2) { $q[$x[0]] = [Uri]::UnescapeDataString($x[1]) } }
        if ($q['t'] -ne $token) { Send $st '403 Forbidden' 'text/plain' ([byte[]]@()); continue }
        $lastReq = Get-Date
        if ($path -eq '/ping') { Send $st '200 OK' 'text/plain' ($utf8.GetBytes('ok')) }
        elseif ($path -eq '/list') { $d = 7; if ($q['days'] -match '^\d+$') { $d = [Math]::Min(30, [Math]::Max(1, [int]$q['days'])) }; Send $st '200 OK' 'application/json; charset=utf-8' ($utf8.GetBytes((ListJson $d))) }
        elseif ($path -eq '/rotation' -and $outOk) { Send $st '200 OK' 'application/json; charset=utf-8' ($utf8.GetBytes((RotJson $q))) }
        elseif ($path -eq '/cbf' -and $outOk) { Send $st '200 OK' 'application/json; charset=utf-8' ($utf8.GetBytes((CbfJson $q))) }
        elseif ($path -eq '/bk' -and $outOk) { Send $st '200 OK' 'application/json; charset=utf-8' ($utf8.GetBytes((BkJson $q))) }
        elseif ($path -eq '/cll' -and $outOk) { Send $st '200 OK' 'application/json; charset=utf-8' ($utf8.GetBytes((CllJson $q))) }
        elseif ($path -eq '/closemail' -and $outOk) { Send $st '200 OK' 'application/json; charset=utf-8' ($utf8.GetBytes((CloseMailJson $q))) }
        elseif ($path -eq '/mailhint') { Send $st '200 OK' 'application/json; charset=utf-8' ($utf8.GetBytes((MailHint $q))) }
        elseif ($path -eq '/file') { Send $st '200 OK' 'application/octet-stream' (FileBytes $q['id'] $q['i']) }
        elseif ($verb -eq 'POST' -and $outOk -and ($path -eq '/outprep' -or $path -eq '/outopen')) {
            $j = [Text.Encoding]::UTF8.GetString($all, $hEnd, $all.Length - $hEnd) | ConvertFrom-Json
            $res = if ($path -eq '/outprep') { OutPrep $j } else { OutOpen $j }
            Send $st '200 OK' 'application/json; charset=utf-8' ($utf8.GetBytes($res))
        }
        else { Send $st '404 Not Found' 'text/plain' ([byte[]]@()) }
    } catch { Log ('request: ' + $_.Exception.Message); try { Send $st '500 Error' 'text/plain' ($utf8.GetBytes($_.Exception.Message)) } catch { } }
    finally { $c.Close() }
}
$listener.Stop(); Remove-Item -LiteralPath (Join-Path $tmp 'mailsrv.js') -Force -ErrorAction SilentlyContinue; Log 'stopped (idle)'
