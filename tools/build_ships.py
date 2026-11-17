# -*- coding: utf-8 -*-
"""DEFINE(.def) 폴더 -> ../ships.js (뷰어가 읽는 선박 구조).
쓰는 법: python build_ships.py [DEFINE 폴더]   (기본: 바탕화면\222Define)
.def 를 못 읽은 배는 스토우 도우미가 cCASP 에서 받아 둔 구조(JSON)가 있으면 그걸 씀.
ships.js 모양: ASC_SHIPS = {코드: {n: 선박명, b: {베이: {티어: "로우2자리씩", ...}}, r: {베이: {티어: "리퍼 로우"}}}}
"""
import os, sys, glob, json
sys.stdout.reconfigure(encoding="utf-8")
from casp_define import parse_define
HOME = os.path.expanduser("~")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HOME, "Desktop", "222Define")
CC = os.path.join(HOME, "Desktop", "stowage-helper", "data", "ccasp")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ships.js")

def ccasp(path):
    s = json.load(open(path, encoding="utf-8"))
    s = s["response"]["data"] if isinstance(s, dict) and "response" in s else s
    s = s[0] if isinstance(s, list) else s
    out, bays = {}, []
    for b in s["bays"]:
        tiers = [int(t) if t else None for t in b["tierNo"]]   # 빈 칸도 자리를 지켜야 줄이 안 밀림 (TYTR 은 맨 앞이 빈 칸)
        slots = []
        for ti, line in enumerate(b["cells"]):
            if ti >= len(tiers) or tiers[ti] is None: continue
            t = tiers[ti]; rows = b["holdRowNo"] if t < 80 else b["deckRowNo"]
            for ri, c in enumerate(line):
                v = c.get("value") if isinstance(c, dict) else c
                if v in (1, 3) and ri < len(rows) and rows[ri] not in (None, ""):
                    slots.append([int(rows[ri]), t, v])
        out[str(int(b["name"]))] = slots
    return {"slots": out, "name": s.get("vesselName", "")}

def pack(r):
    b, rf = {}, {}
    for bay, slots in r["slots"].items():
        if not slots: continue
        for row, tier, v in slots:
            b.setdefault(bay, {}).setdefault(str(tier), []).append(row)
            if v == 3: rf.setdefault(bay, {}).setdefault(str(tier), []).append(row)
    j = lambda d: {bay: {t: "".join("%02d" % x for x in sorted(set(rs))) for t, rs in ts.items()} for bay, ts in d.items()}
    name = r.get("name", "")
    return {"n": name, "b": j(b), "r": j(rf)}

ships, fail, src, deep = {}, [], {}, []
for p in sorted(glob.glob(os.path.join(SRC, "**", "*.[dD][eE][fF]"), recursive=True)):
    code = os.path.splitext(os.path.basename(p))[0].upper()
    try:
        try:
            r = parse_define(p)
        except Exception:
            r = parse_define(p, deep=True)   # 글자 표가 여러 군데 있는 파일 (SWSH 등)
            deep.append(code)
        nm = "".join(ch for ch in r["name"] if 32 <= ord(ch) < 127).strip()
        nm = nm[len(code):] if nm.upper().startswith(code) else nm
        keep = []
        for tok in nm.split():
            if any(ch.isdigit() for ch in tok): break   # 호출부호·IMO 번호부터는 버림
            keep.append(tok)
        r["name"] = " ".join(keep)
        ships[code] = pack(r); src[code] = "def"
    except Exception as e:
        fail.append(code)
for p in glob.glob(os.path.join(CC, "*_structure.json")):
    code = os.path.basename(p).split("_")[0].upper()
    if code not in ships:
        ships[code] = pack(ccasp(p)); src[code] = "ccasp"
        if code in fail: fail.remove(code)
# 이름 앞에 다른 선박 코드가 붙어 있으면 뗌 (예: HAXNHEUNG-A XIAMEN)
_codes = set(ships) | set(fail)
for c, v in ships.items():
    if len(v["n"]) > 7 and v["n"][:4] in _codes and v["n"][4:5].isalpha(): v["n"] = v["n"][4:]
# 동형선: 구조 파일이 없는 배는 같은 형의 배 구조를 빌려 씀 (팀 확인)
SISTERS = {"HKEP": "HSWH", "MJEP": "HSWH", "HAHP": "HAXM", "HAKT": "HAXM", "HTVY": "OSVY"}   # VTVY 도 OSVY 와 동형선이지만 자기 .def 가 검증돼 있어 그대로 둠
own = {c: ships[c] for c in SISTERS if c in ships}   # 비교용: 자기 .def 로 읽은 것
json.dump(own, open(os.path.join(os.path.dirname(OUT), "tools", "_own.json"), "w", encoding="utf-8"))
for code, base in SISTERS.items():
    if base in ships:   # 동형선으로 확인된 배는 자기 .def 가 읽혀도 동형선 구조를 씀
        ships[code] = dict(ships[base], n=base + " 동형선"); src[code] = "sister"
# 뷰어 목록에 띄울 배: 지금 대일선에 투입된 SKR·HAS 선박만 (2026-11-17 기준)
# 출처: 전산 포트 스케줄(SP_GETPORTSCHEDULE, KRPUS, 2026-10-01~12-15, SNKO+HALK) 에서 OP_LINER 가 SKR/HAS 인 대일선 서비스 선박.
# 투입 선박이 바뀌면 이 표를 고치고 다시 실행.  서비스: 선박
ACTIVE = {
    "ISX": ["PCBS"], "JSW1": ["PCNB"], "JSW2": ["OSVY", "VTVY"], "KHX1": ["HAHP", "HAXM"], "KJS1": ["AKTR"],
    "KJS2": ["HRON"], "MSX": ["HKEP"], "SETO3": ["PCTJ"], "SETO4": ["SKNT"], "SKX1": ["HSWH", "MJEP"],
    "SKX2": ["HTVY"], "BSS1": ["SWRG", "SWSH"], "THS2": ["HAHP", "HAXM"], "THS3": ["OSVY", "TYTR"], "THS4": ["ATSH"], "THS5": ["HAKT"],
}
svc_of = {}
for svc, vs in ACTIVE.items():
    for v in vs: svc_of.setdefault(v, []).append(svc)
print("대일선 선박 중 구조 없음:", sorted(v for v in svc_of if v not in ships))
ships = {c: dict(ships[c], s="·".join(svc_of[c])) for c in sorted(svc_of) if c in ships}
with open(OUT, "w", encoding="utf-8") as f:
    f.write("window.ASC_SHIPS=" + json.dumps(ships, ensure_ascii=False, separators=(",", ":")) + ";\n")
print("ships", len(ships), "| def", sum(v == "def" for v in src.values()), "| ccasp", sum(v == "ccasp" for v in src.values()), "| size KB", os.path.getsize(OUT) // 1024)
print("ccasp:", sorted(k for k, v in src.items() if v == "ccasp"))
print("deep 으로 읽은 배:", " ".join(sorted(deep)))
print("fail", len(fail), " ".join(sorted(fail)))
