# Mail helper for the PLAN VIEWER "mail" tab (PC only).
# Reads Outlook on this PC (read-only) and hands the viewer page a list of recent mails that carry .asc / .edi plans, and the attachment itself when asked.
# Nothing leaves this PC: it only answers on 127.0.0.1 and only to requests that carry the random token written to %TEMP%\asc-viewer\mailsrv.js.
# Started (hidden) by open-asc.ps1; stops by itself when no viewer page has asked for anything for 15 minutes.
# Keep this file ASCII only (Windows PowerShell 5.1). Category names and sender rules live in mail-rules.json (UTF-8, this PC / team only).
#
# -Agent : phone helper mode (set up by phone-agent-setup.ps1). No listener at all - nothing can connect to this PC.
#   This PC asks the team server first ("any job for my PC?"), does the job with Outlook on this PC and uploads the answer; the phone of the same person shows it.
#   Only this person's jobs come here (the server ties this PC's key to the login it was registered with), and only read jobs are accepted.
#   Outlook is used through its COM object model only, on a narrow scope: received mail of the last days (at most 14) in the inbox tree
#   and in the top-level folders that mail-rules.json names (mail filed there by Outlook rules). Sent / deleted / other stores are never opened.
param([int]$Days = 7, [switch]$Agent)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tmp = Join-Path $env:TEMP 'asc-viewer'
if (-not (Test-Path $tmp)) { New-Item -ItemType Directory -Path $tmp | Out-Null }
$mutex = New-Object Threading.Mutex($false, $(if ($Agent) { 'Local\asc-viewer-phone-agent' } else { 'Local\asc-viewer-mail-server' }))
if (-not $mutex.WaitOne(0)) { exit }     # already running
$log = Join-Path $tmp $(if ($Agent) { 'agent.log' } else { 'mailsrv.log' })
function Log($m) { try { Add-Content -LiteralPath $log -Value ((Get-Date).ToString('MM-dd HH:mm:ss') + '  ' + $m) -Encoding UTF8 } catch { } }

$listener = $null; $port = 0; $token = ''
if (-not $Agent) {
    # ---- listener on a free loopback port + token file for the page
    foreach ($p in 47815..47835) { try { $l = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $p); $l.Start(); $listener = $l; $port = $p; break } catch { } }
    if (-not $listener) { Log 'no free port'; exit }
    # token: persistent (kept in mailsrv-token.txt next to this file). Never committed; stays on this PC.
    $tokFile = Join-Path $dir 'mailsrv-token.txt'
    if (Test-Path $tokFile) { try { $token = (Get-Content -LiteralPath $tokFile -Raw).Trim() } catch { } }
    if ($token -notmatch '^[0-9a-fA-F]{32,}$') { $token = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N'); try { [IO.File]::WriteAllText($tokFile, $token, (New-Object Text.UTF8Encoding($false))) } catch { } }
    [IO.File]::WriteAllText((Join-Path $tmp 'mailsrv.js'), "window.__MAILSRV__={port:$port,token:'$token'};", (New-Object Text.UTF8Encoding($false)))
    Log "listening on $port"
}

# ---- categories. The Outlook folders are the categories (mail-rules.json names them); only mail that sits in no named folder (Deleted Items, ...) is told apart by its sender.
# Order of deciding: 1) folder rule (a rule with only "folder" = text in the folder path)  2) a sender whose mails are filed in a folder rule marked "learn" (taken from the scanned mails)
# 3) the other rules, first match wins: from (address endings, "" = unknown address), fromName (regex), subject (regex on subject + file names);
#    a rule marked "fleet" gives the category of the fleet folder ("fleet" folder rule) that has a sub-folder "CODE - NAME" of the vessel named in the mail   4) .jp / .cn / the rest
$rules = @(); $order = @(); $phoneAlso = @()
$rf = Join-Path $dir 'mail-rules.json'
if (Test-Path $rf) { try { $rj = Get-Content -LiteralPath $rf -Raw -Encoding UTF8 | ConvertFrom-Json; $rules = @($rj.rules); $order = @($rj.order); $phoneAlso = @($rj.phoneAlso | Where-Object { $_ }) } catch { Log ('rules: ' + $_.Exception.Message) } }
function IsFolderRule($r) { return [bool]($r.folder -and -not $r.from -and -not $r.fromName -and -not $r.subject -and ($null -eq $r.PSObject.Properties['from'])) }
$folderRules = @($rules | Where-Object { IsFolderRule $_ }); $otherRules = @($rules | Where-Object { -not (IsFolderRule $_) })
$fleet = @{}; $fleetNames = @{}; $learn = @{}
function FolderRule($folder) { foreach ($r in $folderRules) { if (([string]$folder).IndexOf([string]$r.folder, [StringComparison]::OrdinalIgnoreCase) -ge 0) { return $r } }; return $null }
function FleetOf($o) {
    $t = ($o.sub + ' ' + (($o.files | ForEach-Object { $_.n }) -join ' ')).ToUpper()
    foreach ($c in $fleet.Keys) { if ($t -cmatch ('(?<![A-Z])' + [regex]::Escape($c) + '(?![A-Z])')) { return $fleet[$c] } }
    foreach ($n in $fleetNames.Keys) { if ($t.Contains($n)) { return $fleetNames[$n] } }
    return ''
}
function CatOf($o) {
    $fr = FolderRule $o.folder; if ($fr) { return [string]$fr.cat }
    if ($o.ad -and $learn.ContainsKey($o.ad)) { return $learn[$o.ad] }
    foreach ($r in $otherRules) {
        $ok = $true
        if ($null -ne $r.PSObject.Properties['from']) { $hit = $false; foreach ($d in @($r.from)) { $d = [string]$d; if ($o.fd -eq $d -or ($d -and ($o.fd.EndsWith('.' + $d) -or ($d.StartsWith('.') -and $o.fd.EndsWith($d))))) { $hit = $true; break } }; if (-not $hit) { $ok = $false } }
        if ($ok -and $r.fromName -and ($o.from -notmatch $r.fromName)) { $ok = $false }
        if ($ok -and $r.subject -and (($o.sub + ' ' + (($o.files | ForEach-Object { $_.n }) -join ' ')) -notmatch $r.subject)) { $ok = $false }
        if ($ok -and $r.folder -and ($o.folder.IndexOf([string]$r.folder, [StringComparison]::OrdinalIgnoreCase) -lt 0)) { $ok = $false }
        if (-not $ok) { continue }
        if ($r.fleet) { $c = FleetOf $o; if ($c) { return $c }; if ($r.cat) { return [string]$r.cat }; continue }
        return [string]$r.cat
    }
    if ($o.fd.EndsWith('.jp')) { return 'JP' }
    if ($o.fd.EndsWith('.cn')) { return 'CN' }
    return 'ETC'
}
# after a scan: learn the senders of the "learn" folders, then name every mail again (folders, fleets and senders may have changed)
function Recat {
    $cnt = @{}
    foreach ($o in $script:cache.Values) { $fr = FolderRule $o.folder; if (-not $fr -or -not $fr.learn -or -not $o.ad) { continue }
        if (-not $cnt.ContainsKey($o.ad)) { $cnt[$o.ad] = @{} }; $c = [string]$fr.cat; $cnt[$o.ad][$c] = 1 + [int]$cnt[$o.ad][$c] }
    $script:learn = @{}
    foreach ($ad in $cnt.Keys) { $best = ''; $bn = 0; foreach ($c in $cnt[$ad].Keys) { if ($cnt[$ad][$c] -gt $bn) { $bn = $cnt[$ad][$c]; $best = $c } }; if ($best) { $script:learn[$ad] = $best } }
    foreach ($o in $script:cache.Values) { $o.cat = CatOf $o }
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
function CloseMailJson($q) { $a = QVoy $q; if (-not $a) { return '{"mails":[]}' }
    $roots = $null; if ($Agent) { $roots = @(ScanRoots ((Outlook).GetNamespace('MAPI')) | ForEach-Object { $_.f }) }     # phone helper: the same narrow folders as the mail list
    return (@{ mails = @(Out-CloseMail $a[0] ([string]$q['name']) $a[1] $roots) } | ConvertTo-Json -Depth 5 -Compress) }
function OutOpen($q) {
    $mode = if ($q.send -eq $true) { 'send' } elseif ($q.draft) { 'draft' } else { 'show' }
    $rcp = $null; if ($q.PSObject.Properties['to'] -or $q.PSObject.Properties['cc']) { $rcp = @{ to = @($q.to); cc = @($q.cc) } }     # only when the person changed the recipients
    return ((Out-Open ([string]$q.id) ([string]$q.voy) ([string]$q.subject) ([string]$q.rot) @($q.files) $mode @($q.ports) $null ([string]$q.html) $rcp) | ConvertTo-Json -Compress)
}

function Walk($f, $path, $since, $sentId) {
    $p = if ($path) { $path + '/' + $f.Name } else { $f.Name }
    try { $fr0 = FolderRule $p; if ($fr0 -and $fr0.fleet -and ([string]$f.Name) -match '^\s*([A-Za-z0-9]{3,5})\s*-\s*(.+?)\s*$') { $script:fleet[$Matches[1].ToUpper()] = [string]$fr0.cat; $script:fleetNames[$Matches[2].ToUpper()] = [string]$fr0.cat } } catch { }
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
# where a scan starts. PC viewer: the mailbox that holds the inbox (all its folders).
# Phone helper (-Agent): received mail only - the inbox tree, plus the top-level folders that a folder rule of mail-rules.json names
# (Outlook rules file received mail there). Sent, deleted, drafts, outbox, junk and every other store are left alone.
function ScanRoots($ns) {
    $inbox = $ns.GetDefaultFolder(6); $top = $inbox.Parent
    if (-not $Agent) { return @(@{ f = $top; p = '' }) }
    $skip = @{}; foreach ($k in 3, 4, 5, 16, 23) { try { $skip[[string]$ns.GetDefaultFolder($k).EntryID] = 1 } catch { } }
    $names = @{}; foreach ($r in $folderRules) { $s = ([string]$r.folder).Trim('/').Split('/')[0].Trim(); if ($s) { $names[$s.ToLower()] = 1 } }
    $list = @(@{ f = $inbox; p = [string]$top.Name })
    # opt-in in mail-rules.json:  "phoneAlso": ["deleted"]  = also the Deleted Items folder (for people who delete a plan mail once it is handled)
    if ($phoneAlso -contains 'deleted') { try { $list += @{ f = $ns.GetDefaultFolder(3); p = [string]$top.Name } } catch { } }
    foreach ($c in $top.Folders) {
        try {
            if ($c.EntryID -eq $inbox.EntryID -or $skip.ContainsKey([string]$c.EntryID) -or $c.DefaultItemType -ne 0) { continue }
            if ($names.ContainsKey(([string]$c.Name).Trim().ToLower())) { $list += @{ f = $c; p = [string]$top.Name } }
        } catch { }
    }
    return $list
}
function Scan($days) {
    $ns = (Outlook).GetNamespace('MAPI')
    $since = (Get-Date).AddDays(-$days)
    if ($script:lastScan -ne [DateTime]::MinValue -and $days -le $script:scanDays) { $since = $script:lastScan.AddMinutes(-10) }
    $t0 = Get-Date
    $sentId = ''; try { $sentId = $ns.GetDefaultFolder(5).EntryID } catch { }
    foreach ($r in @(ScanRoots $ns)) { Walk $r.f $r.p $since $sentId }
    try { Recat } catch { Log ('recat: ' + $_.Exception.Message) }
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
    return (@{ at = (Get-Date).ToString('HH:mm'); days = $days; order = @($order); items = @($out) } | ConvertTo-Json -Depth 5 -Compress)
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

# ---- one request -> one answer (the same for the local listener and for the phone helper)
$utf8 = New-Object Text.UTF8Encoding($false)
function Answer($code, $type, $bytes) { return @{ code = $code; type = $type; bytes = [byte[]]$bytes } }
function Route($verb, $path, $q, [byte[]]$body) {
    $J = 'application/json; charset=utf-8'
    # phone helper: read jobs only, whatever the server asks for
    if ($Agent -and ($verb -ne 'GET' -or @('/ping', '/list', '/file', '/mailhint', '/rotation', '/cbf', '/bk', '/cll', '/closemail') -notcontains $path)) { return (Answer '403 Forbidden' 'text/plain' @()) }
    if ($path -eq '/ping') { return (Answer '200 OK' 'text/plain' ($utf8.GetBytes('ok'))) }
    if ($path -eq '/list') { $d = 7; $max = 30; if ($Agent) { $max = 14 }; if ($q['days'] -match '^\d+$') { $d = [Math]::Min($max, [Math]::Max(1, [int]$q['days'])) }; return (Answer '200 OK' $J ($utf8.GetBytes((ListJson $d)))) }
    if ($path -eq '/rotation' -and $outOk) { return (Answer '200 OK' $J ($utf8.GetBytes((RotJson $q)))) }
    if ($path -eq '/cbf' -and $outOk) { return (Answer '200 OK' $J ($utf8.GetBytes((CbfJson $q)))) }
    if ($path -eq '/bk' -and $outOk) { return (Answer '200 OK' $J ($utf8.GetBytes((BkJson $q)))) }
    if ($path -eq '/cll' -and $outOk) { return (Answer '200 OK' $J ($utf8.GetBytes((CllJson $q)))) }
    if ($path -eq '/closemail' -and $outOk) { return (Answer '200 OK' $J ($utf8.GetBytes((CloseMailJson $q)))) }
    if ($path -eq '/mailhint') { return (Answer '200 OK' $J ($utf8.GetBytes((MailHint $q)))) }
    if ($path -eq '/file') { return (Answer '200 OK' 'application/octet-stream' (FileBytes $q['id'] $q['i'])) }
    if ($verb -eq 'POST' -and $outOk -and ($path -eq '/outprep' -or $path -eq '/outopen')) {
        $j = [Text.Encoding]::UTF8.GetString($body) | ConvertFrom-Json
        $res = if ($path -eq '/outprep') { OutPrep $j } else { OutOpen $j }
        return (Answer '200 OK' $J ($utf8.GetBytes($res)))
    }
    return (Answer '404 Not Found' 'text/plain' @())
}

if ($Agent) {
    # ---- phone helper: ask the team server for this person's jobs (outgoing HTTPS only), answer them, repeat
    $cfgFile = Join-Path $env:LOCALAPPDATA 'asc-viewer\phone-agent.json'      # written by phone-agent-setup.ps1: server address + this PC's key (encrypted for this Windows account)
    $script:acfg = $null; $script:acfgT = $null
    function AgentCfg {
        try { $t = (Get-Item -LiteralPath $cfgFile -ErrorAction Stop).LastWriteTimeUtc } catch { return $null }
        if ($script:acfg -and $t -eq $script:acfgT) { return $script:acfg }
        $j = Get-Content -LiteralPath $cfgFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $sec = ConvertTo-SecureString ([string]$j.key)
        $key = [Runtime.InteropServices.Marshal]::PtrToStringUni([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
        $script:acfg = @{ server = ([string]$j.server).TrimEnd('/'); key = $key }; $script:acfgT = $t
        return $script:acfg
    }
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }
    [Net.ServicePointManager]::Expect100Continue = $false
    function AgentCall($cfg, $path, [byte[]]$body, $ms) {
        $req = [Net.HttpWebRequest]::Create($cfg.server + $path)
        $req.Method = 'POST'; $req.Timeout = $ms; $req.ReadWriteTimeout = $ms; $req.UserAgent = 'pv-agent'; $req.ContentType = 'application/octet-stream'
        $req.Headers['Authorization'] = 'Bearer ' + $cfg.key
        if ($cfg.server -match '^http://(127\.0\.0\.1|localhost)[:/]') { $req.Proxy = $null }      # the server PC itself: straight to the local server
        $req.ContentLength = $body.Length
        if ($body.Length) { $s = $req.GetRequestStream(); $s.Write($body, 0, $body.Length); $s.Close() }
        $resp = $null
        try { $resp = $req.GetResponse() }
        catch { $e = $_.Exception; while ($e -and -not ($e -is [Net.WebException])) { $e = $e.InnerException }; if ($e -and $e.Response) { $resp = $e.Response } else { throw } }
        try { $m = New-Object IO.MemoryStream; $resp.GetResponseStream().CopyTo($m); return @{ code = [int]$resp.StatusCode; bytes = $m.ToArray() } } finally { $resp.Close() }
    }
    $fail = 0; Log 'agent started'
    while ($true) {
        try {
            $cfg = AgentCfg
            if (-not $cfg) { Start-Sleep -Seconds 30; continue }       # not set up yet
            $r = AgentCall $cfg '/agent/poll' ([byte[]]@()) 45000      # the server holds the question for about 25 s when there is nothing to do
            if ($r.code -eq 204) { $fail = 0; continue }
            if ($r.code -eq 401) { if ($fail -eq 0) { Log 'the server does not know this PC (run phone-agent-setup again)' }; $fail = 1; Start-Sleep -Seconds 60; continue }
            if ($r.code -ne 200) { throw ('poll: HTTP ' + $r.code) }
            $fail = 0
            $job = $utf8.GetString($r.bytes) | ConvertFrom-Json
            $q = @{}; if ($job.q) { foreach ($p in $job.q.PSObject.Properties) { $q[$p.Name] = [string]$p.Value } }
            try { $res = Route ([string]$job.verb) ('/' + [string]$job.name) $q ([byte[]]@()) }
            catch { Log ('job ' + $job.name + ': ' + $_.Exception.Message); $res = Answer '500 Error' 'text/plain; charset=utf-8' ($utf8.GetBytes($_.Exception.Message)) }
            $code = ([string]$res.code).Split(' ')[0]
            [void](AgentCall $cfg ('/agent/result?id=' + [Uri]::EscapeDataString([string]$job.id) + '&code=' + $code + '&type=' + [Uri]::EscapeDataString([string]$res.type)) ([byte[]]$res.bytes) 120000)
        } catch {
            $fail++; if ($fail -le 3 -or $fail % 30 -eq 0) { Log ('agent: ' + $_.Exception.Message) }
            Start-Sleep -Seconds ([Math]::Min(60, 2 * $fail))
        }
    }
}

# ---- tiny HTTP loop (PC viewer on this PC)
function Send($st, $code, $type, [byte[]]$body) {
    $h = "HTTP/1.1 $code`r`nContent-Type: $type`r`nContent-Length: " + $body.Length + "`r`nAccess-Control-Allow-Origin: *`r`nAccess-Control-Allow-Methods: GET, POST, OPTIONS`r`nAccess-Control-Allow-Headers: Content-Type`r`nAccess-Control-Allow-Private-Network: true`r`nCache-Control: no-store`r`nConnection: close`r`n`r`n"
    $hb = [Text.Encoding]::ASCII.GetBytes($h); $st.Write($hb, 0, $hb.Length); if ($body.Length) { $st.Write($body, 0, $body.Length) }
}
$lastReq = Get-Date
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
        $bb = New-Object byte[] ([Math]::Max(0, $all.Length - $hEnd)); if ($bb.Length) { [Array]::Copy($all, $hEnd, $bb, 0, $bb.Length) }
        $r = Route $verb $path $q $bb
        Send $st $r.code $r.type $r.bytes
    } catch { Log ('request: ' + $_.Exception.Message); try { Send $st '500 Error' 'text/plain' ($utf8.GetBytes($_.Exception.Message)) } catch { } }
    finally { $c.Close() }
}
$listener.Stop(); Remove-Item -LiteralPath (Join-Path $tmp 'mailsrv.js') -Force -ErrorAction SilentlyContinue; Log 'stopped (idle)'