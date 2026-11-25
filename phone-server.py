# -*- coding: utf-8 -*-
# PLAN VIEWER 폰 서버 (서버 PC 한 대에서만 돈다)
#
# 폰 · 다른 PC 는 이 서버의 공개 주소(Tailscale Funnel, https://<서버 PC>.ts.net) 하나로 들어온다. Tailscale 은 서버 PC 에만 있다.
#   - 로그인: 사람마다 아이디 · 비밀번호(phone-server.json 의 users). 기기마다 한 번 넣으면 쿠키로 오래 기억한다.
#   - 메일함: 서버는 아웃룩을 직접 읽지 않는다. 로그인한 사람의 요청을 그 사람 대기열에 넣어 두면,
#     그 사람 회사 PC 의 도우미(mail-server.ps1 -Agent)가 "내 일 있나?" 하고 먼저 물어 와서 가져가고, 자기 PC 의 아웃룩으로 처리해 결과를 올린다.
#     → 팀원 PC 로 밖에서 들어가는 연결은 하나도 없다. 내 일은 내 PC 도우미만 가져간다 (도우미 열쇠 ↔ 사람).
#   - 메일 쓰기 · 보내기는 이 길로는 하지 않는다 (읽기만).
# 127.0.0.1 에서만 듣는다. 켜고 끄기: phone-setup.ps1 (끄기는 -Off). 죽으면 phone-watch.py 가 2분 안에 다시 켠다.
#
# 사람 관리 (서버 PC 에서):
#   python phone-server.py --add-user 아이디 [이름]     비밀번호를 무작위로 만들어 보여 줌
#   python phone-server.py --set-password 아이디 [비밀번호]
#   python phone-server.py --del-user 아이디
#   python phone-server.py --users                    등록된 사람 · 도우미 PC · 마지막으로 물어 온 때
# 공유 링크 (가진 사람은 로그인 없이 그 사람의 메일함을 봄 — 링크가 곧 열쇠):
#   python phone-server.py --link [아이디]              지금 링크 보기 (없으면 만듦)
#   python phone-server.py --new-link [아이디]          새로 만듦 (앞의 링크는 바로 못 쓰게 됨)
#   python phone-server.py --del-link [아이디]          없앰
import collections
import ctypes
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(ROOT, "phone-server.json")
STATE = os.path.join(os.environ.get("LOCALAPPDATA") or ROOT, "asc-viewer")
LOG_FILE = os.path.join(STATE, "phone-server.log")
SESS_FILE = os.path.join(STATE, "phone-sessions.json")
AGENT_FILE = os.path.join(STATE, "phone-agents.json")
COOKIE = "pvs"
# 공유 링크: https://<주소>/t/<열쇠>/  — 링크를 가진 사람은 로그인 없이 그 주인의 메일함(플랜 메일)을 본다. 열쇠가 틀리면 아무것도 안 열림.
LINK_TOKEN = re.compile(r"[A-Za-z0-9_-]{20,64}")
LINK_PATH = re.compile(r"^/t/([A-Za-z0-9_-]{1,80})(/.*)?$")
MAX_BODY = 1024 * 1024               # 폰 · 로그인 요청
MAX_RESULT = 24 * 1024 * 1024        # 도우미가 올리는 결과 (첨부 파일)

os.makedirs(STATE, exist_ok=True)
_log_lock = threading.Lock()


def log(msg):
    try:
        with _log_lock:
            if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 1024 * 1024:
                os.replace(LOG_FILE, LOG_FILE + ".1")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(time.strftime("%m-%d %H:%M:%S") + "  " + str(msg) + "\n")
    except OSError:
        pass


# ---------- 설정 (phone-server.json) ----------
def new_password():
    a = "abcdefghjkmnpqrstuvwxyz"     # 헷갈리는 글자(i l o) 뺀 소문자 8자. 5번 틀리면 15분 잠기므로 대입으로는 못 뚫음
    return "".join(secrets.choice(a) for _ in range(8))


def read_config():
    with open(CFG_FILE, encoding="utf-8-sig") as f:
        return json.load(f)


def write_config(c):
    tmp = CFG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, CFG_FILE)


def init_config():
    """설정 파일이 없으면 만들고, 예전 모양(아이디 하나)이면 users 모양으로 옮긴다. 새로 만들었으면 True."""
    if not os.path.exists(CFG_FILE):
        write_config({"port": 47800, "sessionDays": 180,
                      "users": [{"id": (os.environ.get("USERNAME") or "planner").lower(), "name": "", "password": new_password()}]})
        return True
    try:
        c = read_config()
    except Exception:
        return False
    if "users" not in c:
        u = [{"id": str(c.get("id") or "").strip().lower(), "name": "", "password": str(c.get("password") or "")}] if c.get("id") else []
        write_config({"port": int(c.get("port") or 47800), "sessionDays": 180, "users": u})
    return False


class Config:
    def __init__(self):
        self.mt = None
        self.d = {"port": 47800, "sessionDays": 180, "users": {}, "links": {}}
        self.lock = threading.Lock()

    def _load(self):
        try:
            mt = os.path.getmtime(CFG_FILE)
        except OSError:
            return
        if mt == self.mt:
            return
        self.mt = mt                              # 파일을 고치면 다시 켜지 않아도 바로 반영 (포트만 예외)
        try:
            j = read_config()
            users = {}
            for u in j.get("users") or []:
                uid = str(u.get("id") or "").strip().lower()
                if uid:
                    users[uid] = {"id": uid, "name": str(u.get("name") or ""), "password": str(u.get("password") or "").strip()}
            links = {}
            for k in j.get("links") or []:
                tok, uid = str(k.get("token") or ""), str(k.get("user") or "").strip().lower()
                if LINK_TOKEN.fullmatch(tok) and uid in users:
                    links[tok] = uid
            self.d = {"port": int(j.get("port") or 47800), "sessionDays": int(j.get("sessionDays") or 180), "users": users, "links": links}
        except Exception as e:                    # 잘못 고친 파일: 직전 값을 그대로 씀
            log("config: " + str(e))

    def get(self, key):
        with self.lock:
            self._load()
            return self.d[key]

    def user(self, uid):
        return self.get("users").get(uid)

    def link_user(self, tok):
        """공유 링크의 열쇠가 맞으면 그 메일함의 주인."""
        found = None
        for t, uid in self.get("links").items():
            if hmac.compare_digest(t.encode("ascii"), tok.encode("ascii", "replace")):
                found = uid
        return found


CFG = Config()


def cred_tag(uid):
    u = CFG.user(uid)
    return hashlib.sha256(("pv|%s|%s" % (uid, u["password"])).encode("utf-8")).hexdigest()[:16] if u else ""


def check_login(uid, pw):
    """아이디 · 비밀번호가 맞으면 그 아이디."""
    uid, pw = str(uid or "").strip().lower(), str(pw or "").strip()
    u = CFG.user(uid)
    want = u["password"] if u else secrets.token_hex(8)       # 없는 아이디도 같은 시간만큼 비교
    ok = hmac.compare_digest(pw.encode("utf-8"), want.encode("utf-8"))
    return uid if (u and ok and len(want) >= 8) else None


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path, d):
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


# ---------- 로그인 세션 (비밀번호를 바꾸면 그 사람의 모든 기기가 다시 로그인) ----------
class Sessions:
    def __init__(self):
        self.lock = threading.Lock()
        self.d = _load_json(SESS_FILE)

    def _save(self):
        now = time.time()
        self.d = {k: v for k, v in self.d.items() if v.get("exp", 0) > now}
        _save_json(SESS_FILE, self.d)

    def life(self):
        return max(1, min(365, CFG.get("sessionDays"))) * 86400

    def new(self, uid):
        tok = secrets.token_urlsafe(32)
        with self.lock:
            self.d[_sha(tok)] = {"exp": time.time() + self.life(), "tag": cred_tag(uid), "user": uid}
            self._save()
        return tok

    def check(self, tok):
        """(로그인한 사람 또는 None, 쿠키를 새로 내려 줄지)"""
        if not tok:
            return None, False
        with self.lock:
            s = self.d.get(_sha(tok))
            now = time.time()
            if not s or s.get("exp", 0) <= now:
                return None, False
            uid = s.get("user") or next(iter(CFG.get("users")), "")     # 사람이 하나뿐이던 때 만든 세션
            if not uid or s.get("tag") != cred_tag(uid):
                return None, False
            if s["exp"] - now < self.life() - 86400:        # 하루에 한 번쯤 기한을 늘림 (쓰는 동안은 로그인이 안 풀리게)
                s["exp"], s["user"] = now + self.life(), uid
                self._save()
                return uid, True
            return uid, False

    def drop(self, tok):
        if not tok:
            return
        with self.lock:
            if self.d.pop(_sha(tok), None):
                self._save()


SESS = Sessions()


# ---------- 비밀번호 대입 막기 ----------
class Guard:
    WINDOW, PER_IP, TOTAL = 900, 5, 40      # 15분 안에 같은 곳에서 5번, 전체 40번 틀리면 15분 잠금

    def __init__(self):
        self.lock = threading.Lock()
        self.fails = []                      # (time, ip)

    def blocked(self, ip):
        with self.lock:
            cut = time.time() - self.WINDOW
            self.fails = [x for x in self.fails if x[0] > cut]
            return len(self.fails) >= self.TOTAL or sum(1 for x in self.fails if x[1] == ip) >= self.PER_IP

    def fail(self, ip):
        with self.lock:
            self.fails.append((time.time(), ip))

    def ok(self, ip):
        with self.lock:
            self.fails = [x for x in self.fails if x[1] != ip]


GUARD = Guard()


# ---------- 도우미 등록부: 사람 ↔ 그 사람 PC (한 사람에 PC 하나. 다시 등록하면 앞의 PC 는 끊김) ----------
class Agents:
    def __init__(self):
        self.lock = threading.Lock()
        self.d = _load_json(AGENT_FILE)       # user -> {hash, pc, since, seen}
        self.saved = 0

    def register(self, uid, pc):
        key = secrets.token_urlsafe(32)
        with self.lock:
            self.d[uid] = {"hash": _sha(key), "pc": str(pc or "")[:60], "since": int(time.time()), "seen": 0}
            _save_json(AGENT_FILE, self.d)
        return key

    def user_of(self, key):
        if not key:
            return None
        h = _sha(key)
        with self.lock:
            for uid, a in self.d.items():
                if hmac.compare_digest(a.get("hash", ""), h):
                    return uid if CFG.user(uid) else None
        return None

    def touch(self, uid):
        with self.lock:
            a = self.d.get(uid)
            if a:
                a["seen"] = int(time.time())
                if time.time() - self.saved > 20:
                    self.saved = time.time()
                    _save_json(AGENT_FILE, self.d)

    def info(self, uid):
        with self.lock:
            return dict(self.d.get(uid) or {})


AGENTS = Agents()


# ---------- 대기열: 폰의 요청을 그 사람 PC 도우미가 가져갈 때까지 맡아 둠 ----------
class Offline(Exception):
    pass


class Hub:
    def __init__(self):
        self.cv = threading.Condition()
        self.queue = collections.defaultdict(collections.deque)     # user -> 아직 안 가져간 일
        self.jobs = {}                                              # id -> 일
        self.busy = collections.Counter()                           # user -> 도우미가 처리 중인 일 수

    def online(self, uid):
        return self.busy[uid] > 0 or time.time() - (AGENTS.info(uid).get("seen") or 0) < 75

    def submit(self, uid, name, q, timeout=300):
        """(상태 코드, 형식, 내용). 같은 사람이 같은 것을 또 물으면(다시 시도) 먼저 맡긴 일의 결과를 같이 받음."""
        key = (uid, name, tuple(sorted(q.items())))
        with self.cv:
            if not self.online(uid):
                raise Offline()
            job = next((j for j in self.jobs.values() if j["key"] == key and j["res"] is None), None)
            if not job:
                job = {"id": secrets.token_urlsafe(12), "key": key, "user": uid, "name": name, "q": q, "res": None, "taken": False, "t": time.time()}
                self.jobs[job["id"]] = job
                self.queue[uid].append(job)
                self.cv.notify_all()
            end = time.time() + timeout
            while job["res"] is None:
                left = end - time.time()
                if left <= 0 or (not job["taken"] and time.time() - job["t"] > 40 and not self.online(uid)):
                    self._drop(job)
                    if left <= 0:
                        raise TimeoutError()
                    raise Offline()
                self.cv.wait(min(left, 5))
            return job["res"]

    def _drop(self, job):
        if self.jobs.pop(job["id"], None):
            if job["taken"]:
                self.busy[job["user"]] -= 1
            else:
                try:
                    self.queue[job["user"]].remove(job)
                except ValueError:
                    pass

    def poll(self, uid, wait=25):
        """도우미가 물어 옴: 일이 생기면 바로, 없으면 wait 초 뒤 None."""
        end = time.time() + wait
        with self.cv:
            while True:
                AGENTS.touch(uid)
                if self.queue[uid]:
                    job = self.queue[uid].popleft()
                    job["taken"] = True
                    self.busy[uid] += 1
                    return job
                left = end - time.time()
                if left <= 0:
                    return None
                self.cv.wait(min(left, 5))

    def result(self, uid, jid, res):
        with self.cv:
            job = self.jobs.get(jid)
            if not job or job["user"] != uid or not job["taken"]:      # 남의 일 · 없는 일에는 답할 수 없음
                return False
            del self.jobs[jid]
            self.busy[uid] -= 1
            job["res"] = res
            AGENTS.touch(uid)
            self.cv.notify_all()
            return True


HUB = Hub()
GET_API = {"ping", "list", "rotation", "cbf", "bk", "cll", "closemail", "mailhint", "file"}     # 읽기만. 도우미 쪽에서도 이것만 받음

# ---------- 내어 주는 파일 (여기 적힌 것만. 토큰 · 규칙 · 스크립트는 절대 나가지 않음) ----------
PUBLIC = {       # 로그인 전에도 필요한 것: 앱 설치 정보 · 아이콘 · 서비스 워커
    "/manifest.webmanifest": "manifest.webmanifest", "/sw.js": "sw.js",
    "/icon-32.png": "icon-32.png", "/icon-180.png": "icon-180.png", "/icon-192.png": "icon-192.png",
    "/icon-512.png": "icon-512.png", "/icon-512-mask.png": "icon-512-mask.png", "/favicon.ico": "icon-32.png",
}
PRIVATE = {"/ships.js": "ships.js", "/mail-config.js": "mail-config.js"}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".webmanifest": "application/manifest+json; charset=utf-8", ".png": "image/png"}
JSON_T = "application/json; charset=utf-8"
_files = {}
_files_lock = threading.Lock()


def load_file(name, inject=b""):
    """(etag, 원본, gzip 또는 None). 파일이 바뀔 때만 다시 읽음."""
    p = os.path.join(ROOT, name)
    st = os.stat(p)
    key = (st.st_mtime_ns, st.st_size)
    with _files_lock:
        c = _files.get((name, inject))
        if c and c[0] == key:
            return c[1], c[2], c[3]
    with open(p, "rb") as f:
        data = f.read()
    if inject:
        data = data.replace(b"/*__ASC_DATA__*/", inject, 1)
    etag = '"%x-%x-%s"' % (st.st_mtime_ns, st.st_size, hashlib.sha1(inject).hexdigest()[:6])
    gz = None if name.endswith(".png") else gzip.compress(data, 6)
    with _files_lock:
        if len(_files) > 60:
            _files.clear()
        _files[(name, inject)] = (key, etag, data, gz)
    return etag, data, gz


LOGIN_HTML = u"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="PLAN VIEWER">
<link rel="apple-touch-icon" href="icon-180.png"><link rel="icon" type="image/png" href="icon-180.png">
<link rel="manifest" href="manifest.webmanifest"><meta name="theme-color" content="#000080">
<title>PLAN VIEWER MADE BY JUNJAE</title>
<style>
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:#bdbdbd;color:#000;font-family:Arial,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;font-size:15px;line-height:1.45;
  display:flex;align-items:center;justify-content:center;
  padding:16px max(16px,env(safe-area-inset-right,0px)) 16px max(16px,env(safe-area-inset-left,0px))}
.win{width:100%;max-width:360px;background:#fff;border:1px solid #000;box-shadow:2px 2px 0 #808080}
.tb{background:#000080;color:#fff;font-weight:700;font-size:13px;padding:5px 10px}
.body{padding:16px 16px 18px;background:#d4d0c8}
p{margin:0 0 14px}
label{display:block;font-weight:700;font-size:13px;margin:0 0 4px}
input{display:block;width:100%;font:inherit;font-size:16px;padding:10px;margin:0 0 14px;border:1px solid #000;border-radius:0;background:#fff;color:#000}
input:focus-visible,button:focus-visible{outline:2px solid #0000c8;outline-offset:1px}
button{width:100%;font:inherit;font-weight:700;font-size:16px;padding:11px;background:#d4d0c8;color:#000;border:1px solid #000;border-radius:0;
  box-shadow:inset 1px 1px 0 #fff,inset -1px -1px 0 #808080;cursor:pointer}
button:active{box-shadow:inset 1px 1px 0 #808080,inset -1px -1px 0 #fff}
.err{background:#fff;border:1px solid #d00000;color:#b00000;padding:8px 10px;margin:0 0 14px;font-size:14px}
.note{margin:14px 0 0;font-size:12.5px;color:#3a3a3a}
</style></head><body>
<form class="win" method="post" action="login">
  <div class="tb">PLAN VIEWER MADE BY JUNJAE</div>
  <div class="body">
    <p>내 아이디로 로그인해 주세요.</p>
    <!--ERR-->
    <label for="id">아이디</label>
    <input id="id" name="id" type="text" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" required>
    <label for="pw">비밀번호</label>
    <input id="pw" name="password" type="password" autocomplete="current-password" required>
    <button type="submit">로그인</button>
    <p class="note">이 기기에서는 한 번만 로그인하면 돼요.</p>
  </div>
</form>
</body></html>
"""
LOGIN_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; manifest-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "pv"
    sys_version = ""
    timeout = 60

    def log_message(self, *a):
        pass

    # ---- 요청에서 읽는 것
    def ip(self):
        x = self.headers.get("X-Forwarded-For")           # Tailscale 이 붙여 주는 접속자 주소 (맨 끝 것이 Tailscale 이 본 주소)
        return x.split(",")[-1].strip() if x else self.client_address[0]

    def https(self):
        return (self.headers.get("X-Forwarded-Proto") or "").lower() == "https"

    def token(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE:
                return v
        return ""

    def user(self):
        uid, renew = SESS.check(self.token())
        if renew:
            self._cookie = self.cookie(self.token(), SESS.life())
        return uid

    def agent(self):
        a = self.headers.get("Authorization") or ""
        return AGENTS.user_of(a[7:].strip()) if a.startswith("Bearer ") else None

    def cookie(self, value, age):
        return "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Lax%s" % (COOKIE, value, age, "; Secure" if self.https() else "")

    def same_origin(self):
        """다른 사이트가 이 서버로 몰래 보내는 요청을 거름 (쿠키의 SameSite 와 이중으로)."""
        o = self.headers.get("Origin")
        if o and o != "null":
            return urllib.parse.urlsplit(o).netloc.lower() == (self.headers.get("Host") or "").lower()
        site = self.headers.get("Sec-Fetch-Site")      # 브라우저가 출처를 가려 보낸 때("null")는 이것으로 판단
        if site:
            return site in ("same-origin", "none")
        return not o

    # ---- 응답
    def out(self, code, body=b"", ctype="text/plain; charset=utf-8", cache="no-store", extra=()):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        if self.https():
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        if getattr(self, "_cookie", None):
            self.send_header("Set-Cookie", self._cookie)
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def redirect(self, to):
        self.out(303, b"", extra=[("Location", to)])

    def login_page(self, code=401, err=""):
        h = LOGIN_HTML.replace("<!--ERR-->", '<div class="err" role="alert">' + err + "</div>" if err else "")
        self.out(code, h, "text/html; charset=utf-8", extra=[("Content-Security-Policy", LOGIN_CSP)])

    def static(self, name, cache, inject=b""):
        try:
            etag, data, gz = load_file(name, inject)
        except OSError:
            return self.out(404, "not found")
        ctype = TYPES.get(os.path.splitext(name)[1], "application/octet-stream")
        if self.headers.get("If-None-Match") == etag:
            return self.out(304, b"", ctype, cache, [("ETag", etag)])
        extra = [("ETag", etag)]
        if gz is not None:
            extra.append(("Vary", "Accept-Encoding"))
            if "gzip" in (self.headers.get("Accept-Encoding") or ""):
                data = gz
                extra.append(("Content-Encoding", "gzip"))
        self.out(200, data, ctype, cache, extra)

    def api(self, uid, name, query, link=False):
        a = AGENTS.info(uid)
        if name == "me":
            return self.out(200, json.dumps({"user": uid, "name": CFG.user(uid)["name"], "pc": "" if link else a.get("pc") or "", "online": HUB.online(uid), "link": link}), JSON_T)
        if name not in GET_API:
            return self.out(404, "not found")
        q = {k: v for k, v in urllib.parse.parse_qsl(query, keep_blank_values=True) if k != "t"}
        try:
            code, ctype, data = HUB.submit(uid, name, q)
        except Offline:
            if link:
                return self.out(409, "메일함을 내어 주는 회사 PC 가 응답하지 않아요. 그 PC 가 켜져 있어야 해요.")
            if not a:
                return self.out(409, "내 회사 PC 가 아직 연결돼 있지 않아요. 회사 PC 에서 phone-agent-setup 을 한 번 실행해 주세요.")
            return self.out(409, "내 회사 PC(%s)가 응답하지 않아요. PC 가 켜져 있고 윈도우에 로그인돼 있는지 확인해 주세요." % a.get("pc"))
        except TimeoutError:
            return self.out(504, "회사 PC 가 답하는 데 너무 오래 걸려요. 아웃룩이 열려 있는지 확인하고 다시 시도해 주세요.")
        self.out(code, data, ctype)

    def link_get(self, tok, rest, query):
        """공유 링크로 들어온 요청: 로그인 없이, 링크 주인의 메일함만 (읽기)."""
        ip = self.ip()
        if GUARD.blocked(ip):
            return self.out(429, "잠시 뒤에 다시 해 주세요.")
        owner = CFG.link_user(tok)
        if not owner:                              # 틀린 · 없앤 링크: 대입을 막으려고 틀린 횟수에 넣음
            GUARD.fail(ip)
            log("link REJECTED  " + ip)
            gone = "이 링크는 더 이상 쓸 수 없어요. 새 링크를 받아 주세요."
            if rest and rest.startswith("/api/"):
                return self.out(410, gone)
            return self.out(404, '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                                 '<title>PLAN VIEWER</title><body style="font:16px sans-serif;margin:24px">' + gone, "text/html; charset=utf-8")
        if not rest:
            return self.redirect("/t/%s/" % tok)   # 끝에 / 가 있어야 화면 안의 주소들이 이 링크 아래로 풀림
        if rest in ("/", "/index.html"):
            log("link open      %s  %s" % (owner, ip))
            flag = "window.__PCSRV__=%s;" % json.dumps({"send": False, "user": owner, "link": True})
            return self.static("index.html", "private, no-cache", flag.encode("ascii"))
        if rest in PUBLIC:
            return self.static(PUBLIC[rest], "private, max-age=3600")
        if rest in PRIVATE:
            return self.static(PRIVATE[rest], "private, no-cache")
        if rest.startswith("/api/"):
            return self.api(owner, rest[5:], query, True)
        self.out(404, "not found")

    # ---- 길
    def do_GET(self):
        self._cookie = None
        u = urllib.parse.urlsplit(self.path)
        path = u.path
        if path == "/healthz":
            return self.out(200, "ok")
        if path == "/robots.txt":
            return self.out(200, "User-agent: *\nDisallow: /\n")
        m = LINK_PATH.match(path)
        if m:
            return self.link_get(m.group(1), m.group(2), u.query)
        if path in PUBLIC:
            return self.static(PUBLIC[path], "public, max-age=3600")
        if path == "/logout":
            SESS.drop(self.token())
            self._cookie = self.cookie("", 0)
            return self.redirect("/")
        uid = self.user()
        if path == "/login":
            return self.redirect("/")
        if path in ("/", "/index.html"):
            if not uid:
                return self.login_page()
            flag = "window.__PCSRV__=%s;" % json.dumps({"send": False, "user": uid})
            return self.static("index.html", "private, no-cache", flag.encode("ascii"))
        if path in PRIVATE or path.startswith("/api/"):
            if not uid:
                return self.out(401, "login")
            if path in PRIVATE:
                return self.static(PRIVATE[path], "private, no-cache")
            return self.api(uid, path[5:], u.query)
        self.out(404, "not found")

    do_HEAD = do_GET

    def do_POST(self):
        self._cookie = None
        u = urllib.parse.urlsplit(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > (MAX_RESULT if u.path == "/agent/result" else MAX_BODY):
            self.close_connection = True
            return self.out(413, "too large")
        body = self.rfile.read(n) if n else b""
        if not self.same_origin():
            return self.out(403, "forbidden")
        if u.path == "/login":
            return self.login(body)
        if u.path == "/agent/register":
            return self.agent_register(body)
        if u.path.startswith("/agent/"):
            uid = self.agent()
            if not uid:
                return self.out(401, "unknown agent")
            if u.path == "/agent/whoami":
                a = AGENTS.info(uid)
                return self.out(200, json.dumps({"user": uid, "pc": a.get("pc"), "seenAgo": int(time.time() - a["seen"]) if a.get("seen") else None}), JSON_T)
            if u.path == "/agent/poll":
                job = HUB.poll(uid)
                if not job:
                    return self.out(204)
                return self.out(200, json.dumps({"id": job["id"], "verb": "GET", "name": job["name"], "q": job["q"]}), JSON_T)
            if u.path == "/agent/result":
                q = dict(urllib.parse.parse_qsl(u.query))
                try:
                    code = int(q.get("code") or 500)
                except ValueError:
                    code = 500
                ok = HUB.result(uid, q.get("id") or "", (code if 200 <= code < 600 else 500, q.get("type") or "application/octet-stream", body))
                return self.out(200 if ok else 410, "ok" if ok else "gone")
            return self.out(404, "not found")
        if u.path.startswith("/api/") or LINK_PATH.match(u.path):
            if u.path.startswith("/api/") and not self.user():
                return self.out(401, "login")
            return self.out(403, "폰에서는 메일 쓰기 · 보내기를 하지 않아요. 회사 PC 의 뷰어에서 해 주세요.")
        self.out(404, "not found")

    def login(self, body):
        ip = self.ip()
        if GUARD.blocked(ip):
            log("login blocked  " + ip)
            return self.login_page(429, "여러 번 틀려서 잠시 잠겼어요. 15분 뒤에 다시 해 주세요.")
        f = urllib.parse.parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
        uid = check_login((f.get("id") or [""])[0], (f.get("password") or [""])[0])
        if not uid:
            GUARD.fail(ip)
            log("login FAILED   " + ip)
            time.sleep(1)
            return self.login_page(401, "아이디 또는 비밀번호가 맞지 않아요.")
        GUARD.ok(ip)
        log("login ok       %s  %s" % (uid, ip))
        self._cookie = self.cookie(SESS.new(uid), SESS.life())
        self.redirect("/")

    def agent_register(self, body):
        """회사 PC 의 도우미 등록: 그 사람의 아이디 · 비밀번호를 한 번 확인하고 그 PC 만 쓰는 열쇠를 내어 줌 (비밀번호는 PC 에 남지 않음)."""
        ip = self.ip()
        if GUARD.blocked(ip):
            return self.out(429, "locked")
        try:
            j = json.loads(body.decode("utf-8"))
            uid = check_login(j.get("id"), j.get("password"))
            pc = str(j.get("pc") or "")
        except Exception:
            return self.out(400, "bad request")
        if not uid:
            GUARD.fail(ip)
            log("agent register FAILED  " + ip)
            time.sleep(1)
            return self.out(401, "wrong id or password")
        GUARD.ok(ip)
        log("agent registered  %s  pc=%s  %s" % (uid, pc, ip))
        self.out(200, json.dumps({"user": uid, "key": AGENTS.register(uid, pc)}), JSON_T)


class Server(ThreadingHTTPServer):
    allow_reuse_address = False      # 같은 포트에 두 번 뜨지 않게 (윈도우에서는 True 면 겹쳐 뜸)
    allow_reuse_port = False
    daemon_threads = True
    request_queue_size = 64

    def handle_error(self, request, client_address):
        e = sys.exc_info()[1]
        if not isinstance(e, (ConnectionError, TimeoutError)):
            log("error: %r" % (e,))


# ---------- 사람 관리 (명령줄) ----------
def admin(argv):
    cmd, args = argv[0], argv[1:]
    c = read_config()
    users = c.setdefault("users", [])
    find = lambda uid: next((u for u in users if str(u.get("id")).lower() == uid), None)
    if cmd == "--users":
        ag = _load_json(AGENT_FILE)
        for u in users:
            a = ag.get(str(u["id"]).lower()) or {}
            seen = a.get("seen") or 0
            print("%-12s %-10s pc=%-18s %s" % (u["id"], u.get("name") or "", a.get("pc") or "(none)",
                  "never polled" if not seen else "last poll %ds ago" % (time.time() - seen)))
        return 0
    if cmd in ("--link", "--new-link", "--del-link"):      # 공유 링크: 가진 사람은 로그인 없이 그 사람(기본: 첫 번째 사람)의 메일함을 봄
        uid = (args[0].strip().lower() if args else str(users[0]["id"]).lower() if users else "")
        if not find(uid):
            print("no such user: " + uid)
            return 1
        links = c.setdefault("links", [])
        mine = [k for k in links if str(k.get("user")).lower() == uid]
        if cmd != "--link" or not mine:
            for k in mine:
                links.remove(k)                             # 새로 만들면 앞의 링크는 그 자리에서 못 쓰게 됨
            mine = []
            if cmd != "--del-link":
                mine = [{"user": uid, "token": secrets.token_urlsafe(18)}]
                links.extend(mine)
            write_config(c)
        if not mine:
            print("link removed: " + uid)
            return 0
        base = ""
        try:
            with open(os.path.join(ROOT, "phone-agent-server.txt"), encoding="utf-8-sig") as f:
                base = f.read().strip().rstrip("/")
        except OSError:
            pass
        print("%s/t/%s/" % (base or "https://<server address>", mine[0]["token"]))
        return 0
    if not args:
        print("user id is missing")
        return 1
    uid = args[0].strip().lower()
    u = find(uid)
    if cmd == "--add-user":
        if u:
            print("already there: " + uid)
            return 1
        u = {"id": uid, "name": args[1] if len(args) > 1 else "", "password": new_password()}
        users.append(u)
    elif cmd == "--set-password":
        if not u:
            print("no such user: " + uid)
            return 1
        u["password"] = args[1] if len(args) > 1 else new_password()
        if len(u["password"]) < 8:
            print("password must be 8 characters or longer")
            return 1
    elif cmd == "--del-user":
        if not u:
            print("no such user: " + uid)
            return 1
        users.remove(u)
        ag = _load_json(AGENT_FILE)
        if ag.pop(uid, None):
            _save_json(AGENT_FILE, ag)
        write_config(c)
        print("removed: " + uid + "  (restart not needed; that person's devices and PC are cut off)")
        return 0
    else:
        print("unknown command")
        return 1
    write_config(c)
    print("id: %s\npassword: %s" % (u["id"], u["password"]))
    return 0


def main():
    made = init_config()
    if "--init" in sys.argv:         # phone-setup.ps1 이 부름: 설정 파일만 만들고 포트를 알려 줌
        print(json.dumps({"created": made, "port": CFG.get("port"), "config": CFG_FILE, "owner": next(iter(CFG.get("users")), "")}))
        return 0
    if len(sys.argv) > 1:
        return admin(sys.argv[1:])
    if sys.stderr is None:           # pythonw 로 뜬 경우: 뜻밖의 오류도 기록 파일에 남게
        try:
            sys.stdout = sys.stderr = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
        except OSError:
            pass
    port = CFG.get("port")
    try:
        srv = Server(("127.0.0.1", port), Handler)
    except OSError:
        return 0                     # 이미 떠 있음
    # 이 서버가 떠 있는 동안 PC 가 절전으로 들어가지 않게 (화면 꺼짐은 그대로)
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass
    log("server started on 127.0.0.1:%d" % port)
    try:
        srv.serve_forever()
    finally:
        log("server stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
