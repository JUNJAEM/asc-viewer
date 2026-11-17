# -*- coding: utf-8 -*-
# cCASP 에서 받은 선박 구조(tools/ccasp/*_structure.json)를 읽어 보고, 이 PC 의 ASC 플랜과 대조한다.
#   python tools/check_ccasp.py
import collections, glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CC = os.path.join(HERE, "ccasp")
SLOT = (1, 3, 5, 7)   # 비트 합: 1 칸, 2 리퍼 플러그, 4 40' 전용


def read(path):
    s = json.load(open(path, encoding="utf-8"))
    s = s["response"]["data"] if isinstance(s, dict) and "response" in s else s
    s = s[0] if isinstance(s, list) else s
    out, vals = {}, collections.Counter()
    for b in s["bays"]:
        tiers = [int(t) if t else None for t in b["tierNo"]]
        st = set()
        for ti, line in enumerate(b["cells"]):
            if ti >= len(tiers) or tiers[ti] is None: continue
            t = tiers[ti]; rows = b["holdRowNo"] if t < 80 else b["deckRowNo"]
            for ri, c in enumerate(line):
                v = c.get("value") if isinstance(c, dict) else c
                vals[v] += 1
                if v in SLOT and ri < len(rows) and rows[ri] not in (None, ""):
                    st.add((int(rows[ri]), t))
        out[int(b["name"])] = st
    return out, s.get("vesselName", ""), vals


def slots(sh, bay):
    if sh.get(bay): return sh[bay]
    a, b = sh.get(bay - 1), sh.get(bay + 1)
    if a and b: return a & b
    return a or b or set()


def main():
    ships, info = {}, {}
    for p in sorted(glob.glob(os.path.join(CC, "*_structure.json"))):
        code = os.path.basename(p).split("_")[0].upper()
        try:
            sh, name, vals = read(p)
            ships[code] = sh
            info[code] = dict(name=name, bays=len([b for b in sh if sh[b]]), slots=sum(len(v) for b, v in sh.items() if b % 2), vals=dict(vals))
        except Exception as e:
            info[code] = dict(err=str(e)[:80])
    bad = [c for c, i in info.items() if "err" in i or not i.get("slots")]
    print("read ok", len(info) - len(bad), "/", len(info), "| failed:", bad)
    odd = collections.Counter(v for i in info.values() for v in i.get("vals", {}))
    print("cell values seen:", dict(odd))
    # ASC 대조
    roots = [os.path.expanduser(r"~\Desktop"), r"D:\USER", os.path.expanduser(r"~\Downloads"), os.path.expanduser(r"~\Documents")]
    res = collections.defaultdict(lambda: [0, 0, 0])   # files, boxes, outside
    for r in roots:
        for dp, dn, fn in os.walk(r):
            dn[:] = [d for d in dn if d not in ("node_modules", ".git", "AppData")]
            for f in fn:
                if not f.lower().endswith(".asc"): continue
                up = re.sub(r"\.asc$", "", f.upper())
                toks = re.split(r"[^A-Z0-9]+", up)
                code = next((t for t in toks if t in ships), None) or (up[:4] if up[:4] in ships else None) or (up[:3] if up[:3] in ships else None)
                if not code: continue
                n = out = 0
                try:
                    for ln in open(os.path.join(dp, f), encoding="latin-1"):
                        if ln.startswith("***") and "IMDG" in ln: break          # 뒤는 위험물 목록 (컨테이너 줄 아님)
                        if len(ln) < 60 or not ln[:6].isdigit() or ln[6] != " " or not ln[27:33].strip(): continue
                        bay, row, tier = int(ln[0:2]), int(ln[2:4]), int(ln[4:6])
                        if bay == 0: continue
                        n += 1
                        if (row, tier) not in slots(ships[code], bay): out += 1
                except Exception:
                    continue
                if n:
                    x = res[code]; x[0] += 1; x[1] += n; x[2] += out
    print("\ncode  files  boxes  outside  %")
    for c in sorted(info):
        if c in res:
            f, n, o = res[c]
            print("%-5s %5d %6d %7d  %.1f" % (c, f, n, o, 100.0 * o / n))
    print("\nno ASC on this PC:", " ".join(c for c in sorted(info) if c not in res and c not in bad))
    json.dump({"info": info, "check": {c: res[c] for c in res}}, open(os.path.join(CC, "_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
