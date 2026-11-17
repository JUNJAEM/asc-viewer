# -*- coding: utf-8 -*-
"""ASC 의 3글자 포트(PUS) -> 5글자 코드(KRPUS) 표 만들기 -> tools/ports_3to5.json

    python tools/build_ports.py

- 원본: 회사 전산 포트 마스터(sinokor-setting-api 스킬의 resources/domain/port.txt, 이 PC 에만 있음)
- 뒤 3글자가 같은 포트가 여럿이면(KAN = JPKAN / KRKAN) 이 PC 의 ASC 파일 DEST 칸(39~44)에 더 많이 나온 쪽,
  그래도 못 정하면 나라 순서(PRI)로 고름. 실제 메일에서는 그 플랜의 DEST 칸이 먼저 쓰임(뷰어).
- 결과는 build_ships.py 가 ships.js 에 window.ASC_PORTS 로 넣음.
"""
import collections, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PORT_TXT = os.path.expanduser(r"~\.claude\skills\sinokor-setting-api\resources\domain\port.txt")
OUT = os.path.join(HERE, "ports_3to5.json")
PRI = ["KR", "JP", "CN", "VN", "TH", "ID", "MY", "SG", "PH", "TW", "HK", "RU", "IN", "KH", "MM", "BD", "LK"]


def dest_counts():
    c = collections.Counter()
    for r in [os.path.expanduser(r"~\Desktop"), r"D:\USER"]:
        for dp, dn, fn in os.walk(r):
            dn[:] = [d for d in dn if d not in ("node_modules", ".git", "AppData")]
            for f in fn:
                if not f.lower().endswith(".asc"): continue
                try:
                    for ln in open(os.path.join(dp, f), encoding="latin-1"):
                        if ln.startswith("***") and "IMDG" in ln: break
                        if len(ln) > 44 and ln[:6].isdigit() and ln[6] == " ":
                            d = ln[39:44]
                            if d.isalpha(): c[d] += 1
                except Exception:
                    pass
    return c


def main():
    by = collections.defaultdict(list)
    for ln in io.open(PORT_TXT, encoding="utf-8"):
        if ln.startswith("#"): continue
        c = ln.split("|")[0].strip()
        if len(c) == 5 and c.isalpha() and not c.endswith("ZZZ"): by[c[2:]].append(c)
    dc = dest_counts()
    out = {}
    for k, v in sorted(by.items()):
        if len(v) == 1: out[k] = v[0]; continue
        v = sorted(v, key=lambda c: (-dc[c], PRI.index(c[:2]) if c[:2] in PRI else 99, c))
        out[k] = v[0]
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print("ports", len(out), "| KAN", out.get("KAN"), "SGN", out.get("SGN"), "HMD", out.get("HMD"), "PUS", out.get("PUS"), "PNC", out.get("PNC"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
