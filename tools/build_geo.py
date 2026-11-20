# -*- coding: utf-8 -*-
"""포트 좌표표 만들기 -> tools/ports_geo.json  {"KRPUS":[35.13,129.05],...}
3D VIEW 가 그 항의 실제 바람·파도를 물어볼 때 쓰는 위도·경도. 회사 포트 표(ports_3to5.json)에 있는 포트만 담음.
1) UN/LOCODE 공개 목록(code-list.csv)에 좌표가 있으면 그대로
2) 없으면 그 목록의 도시 이름으로 Open-Meteo 지오코딩(열쇠 없음)에 물어봄 — 같은 나라 것만
3) 그래도 없는 것 중 자주 쓰는 포트는 아래 FIX 에 직접
사용: python tools/build_geo.py <code-list.csv 경로> [전산 포트 표 port.txt]   (https://github.com/datasets/un-locode 의 data/code-list.csv)
이미 ports_geo.json 에 있는 포트는 다시 묻지 않음. 끝나면 python tools/build_ships.py 로 ships.js 를 다시 만들 것."""
import csv, json, os, re, sys, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ports_geo.json")
# 자주 가는 포트는 부두 쪽 좌표를 직접 (이름 검색은 같은 이름의 다른 도시를 집을 수 있음)
FIX = {"KRPNC": [35.08, 128.83], "KRPUS": [35.10, 129.07], "KRINC": [37.45, 126.60], "KRKAN": [34.90, 127.70], "KRUSN": [35.50, 129.38], "KRPTK": [36.97, 126.83],
       "JPTYO": [35.62, 139.78], "JPYOK": [35.45, 139.65], "JPNGO": [35.08, 136.88], "JPOSA": [34.65, 135.43], "JPUKB": [34.68, 135.20], "JPHKT": [33.61, 130.40],
       "JPMOJ": [33.95, 130.96], "JPSMZ": [35.02, 138.50], "JPOIT": [33.26, 131.67],
       "CNSHA": [31.35, 121.60], "CNNGB": [29.94, 121.85], "CNTAO": [36.08, 120.32], "CNDLC": [38.93, 121.65], "CNXMN": [24.45, 118.07], "CNTSN": [38.98, 117.75],
       "CNTXG": [38.98, 117.75], "CNLYG": [34.74, 119.44], "HKHKG": [22.32, 114.13], "VNHPH": [20.85, 106.75], "VNSGN": [10.77, 106.72], "THLCH": [13.08, 100.88], "THBKK": [13.70, 100.57]}
want = set(json.load(open(os.path.join(HERE, "ports_3to5.json"), encoding="utf-8")).values())
out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
names = {}
for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")):
    code = (r["Country"] or "") + (r["Location"] or "")
    if code not in want: continue
    names[code] = r["NameWoDiacritics"] or r["Name"]
    m = re.match(r"(\d{2})(\d{2})([NS]) (\d{3})(\d{2})([EW])", r["Coordinates"] or "")
    if m:
        la = (int(m.group(1)) + int(m.group(2)) / 60) * (1 if m.group(3) == "N" else -1)
        lo = (int(m.group(4)) + int(m.group(5)) / 60) * (1 if m.group(6) == "E" else -1)
        out[code] = [round(la, 2), round(lo, 2)]
if len(sys.argv) > 2 and not sys.argv[2].startswith('--'):   # 전산 포트 표(코드 | 이름 | ...)가 있으면 그 이름을 먼저 씀 — 공개 목록은 공항 이름으로 적힌 곳이 있음(상해·닝보 등)
    for ln in open(sys.argv[2], encoding="utf-8"):
        c = [x.strip() for x in ln.split("|")]
        if len(c) > 1 and c[0] in want and c[1]: names[c[0]] = c[1].title()
ASK = "--no-ask" not in sys.argv   # --no-ask: 이름 검색은 건너뜀 (Open-Meteo 는 하루 요청 한도가 있음 — 한도에 걸리면 다음 날 다시)
for code in sorted(want - set(out)) if ASK else []:
    nm = re.sub(r"\s*\(.*?\)|\s+Pt$|[/,].*$|\s+(Port|New Port|Apt)$", "", names.get(code, "")).strip()
    if not nm: continue
    try:
        u = "https://geocoding-api.open-meteo.com/v1/search?count=5&language=en&format=json&name=" + urllib.parse.quote(nm)
        res = json.load(urllib.request.urlopen(u, timeout=15)).get("results") or []
        hit = [x for x in res if x.get("country_code") == code[:2]]
        hit.sort(key=lambda x: -(x.get("population") or 0))   # 같은 이름이 여럿이면 큰 도시 쪽
        if hit: out[code] = [round(hit[0]["latitude"], 2), round(hit[0]["longitude"], 2), 1]   # 셋째 값 1 = 이름으로 찾은 위치(추정)
    except Exception as e:
        print("  ", code, nm, e)
        if "429" in str(e): print("하루 요청 한도에 걸림 — 내일 다시 돌리면 남은 포트를 채움"); break
    time.sleep(0.12)
out.update(FIX)
from geo_called import coords   # 실제 기항지 108곳은 이름으로 직접 잡은 좌표가 우선 (tools/geo_called.py)
out.update(coords())
json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"), sort_keys=True)
print(len(set(out) & want), "of", len(want), "ports have coordinates; missing:", " ".join(sorted(want - set(out))))
