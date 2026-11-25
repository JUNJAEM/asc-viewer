# -*- coding: utf-8 -*-
# PLAN VIEWER 폰 서버 지킴이 (이 PC 전용). 작업 스케줄러가 2분마다 창 없이(pythonw) 한 번씩 돌린다.
#   1) 폰 서버(phone-server.py)가 죽어 있으면 다시 켠다.
#   2) 이 PC 안에서는 열리는데 공개 주소(https://<이 PC>.ts.net)가 안 열리면  tailscale down → 3초 → tailscale up  으로 다시 붙인다.
#      (인터넷 자체가 끊긴 때, 방금 다시 붙인 때(10분 안)는 건드리지 않는다. Funnel 을 일부러 꺼 둔 때도 다시 켜지 않는다.)
# 한 일은 %LOCALAPPDATA%\asc-viewer\phone-watch.log 에 남는다.
#   python phone-watch.py --check   : 지금 상태만 보여 줌 (아무것도 고치지 않음)
import json
import os
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(ROOT, "phone-server.json")
STATE = os.path.join(os.environ.get("LOCALAPPDATA") or ROOT, "asc-viewer")
LOG_FILE = os.path.join(STATE, "phone-watch.log")
ST_FILE = os.path.join(STATE, "phone-watch.json")
NO_WINDOW = 0x08000000
CHECK = "--check" in sys.argv
os.makedirs(STATE, exist_ok=True)


def log(msg):
    if CHECK:
        print(msg)
        return
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 512 * 1024:
            os.replace(LOG_FILE, LOG_FILE + ".1")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%m-%d %H:%M:%S") + "  " + str(msg) + "\n")
    except OSError:
        pass


def state(new=None):
    if new is None:
        try:
            with open(ST_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    if not CHECK:
        try:
            with open(ST_FILE, "w", encoding="utf-8") as f:
                json.dump(new, f)
        except OSError:
            pass


def port():
    try:
        with open(CFG_FILE, encoding="utf-8-sig") as f:
            return int(json.load(f).get("port") or 47800)
    except Exception:
        return 47800


_direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def local_ok(p):
    try:
        with _direct.open("http://127.0.0.1:%d/healthz" % p, timeout=5) as r:
            return r.read() == b"ok"
    except Exception:
        return False


def start_server():
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(w):
        exe = w
    args = [exe, os.path.join(ROOT, "phone-server.py")]
    kw = dict(cwd=ROOT, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # 이 지킴이(예약 작업)가 끝나도 서버는 계속 떠 있게: 새 묶음 + 작업 묶음에서 떼어 냄 (떼기가 안 되는 PC 면 그냥 켬)
    for flags in (0x00000008 | 0x00000200 | 0x01000000, 0x00000008 | 0x00000200):
        try:
            subprocess.Popen(args, creationflags=flags, **kw)
            return True
        except OSError:
            continue
    return False


def tailscale():
    t = shutil.which("tailscale")
    if t:
        return t
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        p = os.path.join(base or "", "Tailscale", "tailscale.exe")
        if os.path.exists(p):
            return p
    return None


def ts(exe, *args, timeout=40):
    try:
        r = subprocess.run([exe] + list(args), capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")
    except Exception as e:
        return -1, str(e)


def dns_a(host, server):
    """공개 DNS 에 직접 물어봄 (이 PC 의 Tailscale DNS 는 사설 주소를 돌려주므로 쓰지 않음)."""
    q = struct.pack(">HHHHHH", 0x5056, 0x0100, 1, 0, 0, 0)
    q += b"".join(bytes([len(x)]) + x.encode("ascii") for x in host.split(".")) + b"\x00" + struct.pack(">HH", 1, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(4)
    try:
        s.sendto(q, (server, 53))
        d = s.recvfrom(1500)[0]
    finally:
        s.close()
    n = struct.unpack(">H", d[6:8])[0]
    i = 12
    while d[i]:
        i += d[i] + 1
    i += 5
    out = []
    for _ in range(n):
        if d[i] & 0xC0 == 0xC0:
            i += 2
        else:
            while d[i]:
                i += d[i] + 1
            i += 1
        typ, _cls, _ttl, ln = struct.unpack(">HHIH", d[i:i + 10])
        i += 10
        if typ == 1 and ln == 4:
            out.append(".".join(str(b) for b in d[i:i + 4]))
        i += ln
    return out


def public_ips(host):
    for server in ("1.1.1.1", "8.8.8.8"):
        try:
            ips = dns_a(host, server)
            if ips:
                return ips
        except Exception:
            continue
    return []


def is_private(ip):
    a, b = (int(x) for x in ip.split(".")[:2])
    return a == 100 and 64 <= b <= 127       # Tailscale 사설 주소: Funnel 이 꺼져 있거나 아직 공개 DNS 에 안 퍼진 것


def public_ok(host):
    """'ok' | 'fail' | 'nodns'. 바깥 사람이 들어오는 길 그대로: 공개 DNS 가 알려 준 Funnel 입구로 접속."""
    ips = [x for x in public_ips(host) if not is_private(x)]
    if not ips:
        return "nodns"
    ctx = ssl.create_default_context()
    for ip in ips[:3]:
        try:
            with socket.create_connection((ip, 443), 8) as raw:
                with ctx.wrap_socket(raw, server_hostname=host) as s:
                    s.settimeout(10)
                    s.sendall(("GET /healthz HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % host).encode("ascii"))
                    buf = b""
                    while len(buf) < 4096:
                        c = s.recv(2048)
                        if not c:
                            break
                        buf += c
            if buf.startswith(b"HTTP/1.1 200") and buf.rstrip().endswith(b"ok"):
                return "ok"
        except Exception:
            continue
    return "fail"


def internet():
    for h in ("1.1.1.1", "8.8.8.8"):
        try:
            socket.create_connection((h, 443), 4).close()
            return True
        except OSError:
            continue
    return False


def main():
    p = port()
    st = state()
    # 1) 서버
    if not local_ok(p):
        if CHECK:
            log("server: DOWN (127.0.0.1:%d)" % p)
            return 1
        started = start_server()
        for _ in range(20):
            time.sleep(0.5)
            if local_ok(p):
                break
        log("server was down -> " + ("restarted" if local_ok(p) else ("start failed" if started else "could not start")))
        if not local_ok(p):
            return 1
    elif CHECK:
        log("server: ok (127.0.0.1:%d)" % p)
    # 2) 공개 주소
    exe = tailscale()
    if not exe:
        log("tailscale: not installed")
        return 1
    code, out = ts(exe, "status", "--json")
    try:
        host = json.loads(out)["Self"]["DNSName"].rstrip(".")
    except Exception:
        host = ""
    if not host:
        log("tailscale: not signed in / not running")
        return 1
    res = public_ok(host)
    if res != "ok" and not CHECK:
        time.sleep(5)
        res = public_ok(host)
    if CHECK:
        log("public: %s (https://%s)" % (res, host))
        log("funnel: " + ("on" if "Funnel on" in ts(exe, "funnel", "status")[1] else "OFF"))
        return 0 if res == "ok" else 1
    if res == "ok":
        if st.get("fails"):
            log("public address is back (https://%s)" % host)
        st["fails"] = 0
        state(st)
        return 0
    st["fails"] = int(st.get("fails") or 0) + 1
    state(st)
    if not internet():
        if st["fails"] == 1:
            log("no internet on this PC - waiting")
        return 1
    if "Funnel on" not in ts(exe, "funnel", "status")[1]:
        if st["fails"] == 1:
            log("funnel is off - not touching it (turn it on with phone-setup.ps1)")
        return 1
    if res == "nodns" and st["fails"] < 5:          # Funnel 을 막 켠 직후: 공개 DNS 에 퍼질 때까지 10분쯤 기다림
        log("public DNS has no funnel address yet (%d)" % st["fails"])
        return 1
    if time.time() - float(st.get("lastReset") or 0) < 600:
        return 1
    log("public address down (%s) but local ok -> tailscale down / up" % res)
    ts(exe, "down")
    time.sleep(3)
    code, out = ts(exe, "up", timeout=60)
    st["lastReset"] = time.time()
    state(st)
    time.sleep(8)
    log("after reset: public %s%s" % (public_ok(host), "" if code == 0 else "  (tailscale up: " + out.strip()[:200] + ")"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log("watch error: %r" % (e,))
        sys.exit(1)
