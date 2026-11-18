# -*- coding: utf-8 -*-
"""ships.js 만들기: cCASP 에서 받은 선박 구조(tools/ccasp/*_structure.json) -> 뷰어용 ships.js

    python tools/build_ships.py

- 원본은 cCASP 구조(JSON). SKR·HAS 가 운용하는 컨테이너선 전부(2026-11-17 기준 69척).
  바탕화면 DEFINE(.def) 해석(tools/casp_define.py)은 틀리는 배가 있어 이제 쓰지 않음.
- tools/ccasp/_lanes.json = {서비스: [선박 코드]} (전산 포트 스케줄에서 운항사가 SKR/HAS 인 것)
- 구조가 실제 플랜과 맞는지는  python tools/check_ccasp.py  로 대조.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CC = os.path.join(HERE, "ccasp")
OUT = os.path.join(os.path.dirname(HERE), "ships.js")
SLOT = (1, 3, 5, 7)     # 칸 값은 비트 합: 1 칸, 2 리퍼 플러그, 4 40' 전용
REEFER = (3, 7)


def ccasp(path):
    s = json.load(open(path, encoding="utf-8"))
    s = s["response"]["data"] if isinstance(s, dict) and "response" in s else s
    s = s[0] if isinstance(s, list) else s
    out = {}
    for b in s["bays"]:
        tiers = [int(t) if t else None for t in b["tierNo"]]   # 빈 칸도 자리를 지켜야 줄이 안 밀림
        slots = []
        for ti, line in enumerate(b["cells"]):
            if ti >= len(tiers) or tiers[ti] is None: continue
            t = tiers[ti]; rows = b["holdRowNo"] if t < 80 else b["deckRowNo"]
            for ri, c in enumerate(line):
                v = c.get("value") if isinstance(c, dict) else c
                if v in SLOT and ri < len(rows) and rows[ri] not in (None, ""):
                    slots.append([int(rows[ri]), t, v])
        out[str(int(b["name"]))] = slots
    # 3D 보기용 배치: [전장 m, 폭 m, 깊이 m, 거주구 바로 앞(선수 쪽) 베이 번호, 연돌 바로 앞 베이 번호(따로 없으면 -1)]
    # cCASP 의 hatchArrangement = 선수부터 해치 순서, deckhouseIndex = 거주구 앞에 있는 해치 개수
    el = [h for h in (s.get("hatchArrangement") or []) if h.get("s")]
    def before(ix):
        if ix is None or ix < 0: return -1
        if ix == 0 or not el: return 0
        f = el[min(ix, len(el)) - 1]["f"]
        return int(s["bays"][f - 1]["name"]) if 0 < f <= len(s["bays"]) else -1
    g = [round(float(s.get("loa") or 0), 1), round(float(s.get("width") or 0), 1), round(float(s.get("depth") or 0), 1),
         before(s.get("deckhouseIndex")), before(s.get("funnelIndex"))]
    return {"slots": out, "name": (s.get("vesselName") or "").strip(), "g": g}


def pack(r):
    b, rf = {}, {}
    for bay, slots in r["slots"].items():
        for row, tier, v in slots:
            b.setdefault(bay, {}).setdefault(str(tier), []).append(row)
            if v in REEFER: rf.setdefault(bay, {}).setdefault(str(tier), []).append(row)
    j = lambda d: {bay: {t: "".join("%02d" % x for x in sorted(set(rs))) for t, rs in ts.items()} for bay, ts in d.items()}
    return {"n": r["name"], "b": j(b), "r": j(rf), "g": r.get("g")}


def main():
    lanes = json.load(open(os.path.join(CC, "_lanes.json"), encoding="utf-8"))
    svc_of = {}
    for svc in sorted(lanes):
        for v in lanes[svc]: svc_of.setdefault(v, []).append(svc)
    ships, fail = {}, []
    hp = os.path.join(HERE, "homo14.json")   # 전산 Vessel Code 의 HOMO14 (14t 균일 적재 TEU = BSA 기준)
    homo = json.load(open(hp, encoding="utf-8")) if os.path.exists(hp) else {}
    for p in sorted(glob.glob(os.path.join(CC, "*_structure.json"))):
        code = os.path.basename(p).split("_")[0].upper()
        try:
            s = pack(ccasp(p))
            if not s["b"]: raise ValueError("no slots")
            s["s"] = u"·".join(svc_of.get(code, []))
            if homo.get(code): s["h"] = homo[code]
            ships[code] = s
        except Exception as e:
            fail.append("%s (%s)" % (code, e))
    ports = {}
    pp = os.path.join(HERE, "ports_3to5.json")   # 3글자 -> 5글자 포트 (tools/build_ports.py), 긴급양하 메일 표에 씀
    if os.path.exists(pp): ports = json.load(open(pp, encoding="utf-8"))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.ASC_SHIPS=" + json.dumps(ships, ensure_ascii=False, separators=(",", ":")) + ";\n")
        f.write("window.ASC_PORTS=" + json.dumps(ports, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + ";\n")
    print("ships", len(ships), "| size KB", os.path.getsize(OUT) // 1024, "| fail", fail)
    print("no service:", sorted(c for c in ships if not ships[c]["s"]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
