# -*- coding: utf-8 -*-
"""CASP 선박 DEFINE(.def) 파일에서 베이별 슬롯 배치(로우·티어·리퍼 플러그)를 읽음.

바탕화면\\plancheck\\scripts\\import_define.py 를 그대로 가져온 것 (plancheck 쪽은 건드리지 않음).
parse_define(path) -> {"format", "bays", "slots": {"베이": [[로우, 티어, 1 일반 / 3 리퍼], ...]}, "name"}

지원 형식 (파일 구조를 직접 분석해서 맞춘 것, ASC 실제 적재 위치로 검증함)
  - "CASP SHIP DEFINE FILE 6.10" : 슬롯 표 20x20(short), 베이 목록 0x90 간격, 글자 표 120바이트
  - "CONVERTED FROM CASP 6.50"   : 슬롯 표 26x26(short), 베이 목록 0xBD 간격, 글자 표 234바이트
  - 6.60 (TYTR 등) 은 아직 못 읽음
슬롯 값: 1 = 일반, 3 = 리퍼 플러그(추정)
"""
import os, re, struct

DEF_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "CASP69", "Define")

# 칸 값은 비트 합: 1 = 칸 있음, 2 = 리퍼 플러그, 4 = 40' 전용(20' 못 실음).  5·7 을 빼먹으면 40' 전용 칸이 통째로 빠짐 (SWSH)
SLOT = (1, 3, 5, 7)

FORMATS = {
    "6.10": dict(W=20, rec_stride=0x90, label=rb"\x00(\d\d)    ", text_len=120, fields=((0, 29), (29, 79), (79, 120))),
    # 6.50 원본은 베이 번호 앞이 공백, 변환본은 \x00
    "6.50": dict(W=26, rec_stride=0xBD, label=rb"[\x00 ](01) {4}", text_len=234, fields=((0, 72), (72, 153), (153, 234))),
}


def pairs(s):
    """'060402010305' 또는 '06 04 02 01 03 05' -> [6,4,2,1,3,5] (첫 번째 숫자 묶음만)"""
    m = re.search(r"\d\d(?: ?\d\d)*", s)
    return [int(x) for x in re.findall(r"\d\d", m.group())] if m else []


def bay_list(d, f, with_entries=False):
    m = re.search(f["label"], d)
    o, bays, ents = m.start() + 1, [], []
    while re.match(rb"\d\d ", d[o:o + 3]):
        bays.append(int(d[o:o + 2]))
        ents.append(d[o:o + f["rec_stride"]])
        o += f["rec_stride"]
    return (bays, ents) if with_entries else bays


def find_grids(d, n, W):
    """슬롯 표 시작 위치 찾기: 모든 베이 블록이 한 기록 안에 들어가고, 가운데 정렬이 맞는 위치"""
    rec = W * W * 2
    best = None
    for S in range(0x100, 0x100 + rec, 2):
        allv = struct.unpack_from("<%dh" % (n * W * W), d, S)
        nz = sum(1 for k, v in enumerate(allv) if v in SLOT and S + 2 * k >= 0x180)   # 헤더 값 제외
        if not nz:
            continue
        grids = []
        ok = True
        for i in range(n):
            g = allv[i * W * W:(i + 1) * W * W]
            lines = [t for t in range(W) if any(v in SLOT for v in g[t * W:(t + 1) * W])]
            for t in lines:   # 줄마다 슬롯이 가운데 근처에 모여 있어야 함 (어긋나면 표가 옆으로 밀린 것)
                cs = [c for c in range(W) if g[t * W + c] in SLOT]
                if abs((cs[0] + cs[-1]) / 2 - (W - 1) / 2) > 1.5:
                    ok = False
            if not ok:
                break
            grids.append(g)
        if not ok:
            continue
        # 가운데 정렬 점수: 각 줄의 슬롯 중심이 W/2 근처
        score = 0
        for g in grids:
            for t in range(W):
                cs = [c for c in range(W) if g[t * W + c] in SLOT]
                if cs:
                    score -= abs((cs[0] + cs[-1]) / 2 - (W - 1) / 2)
        edge = sum(1 for g in grids if any(v in SLOT for v in g[:W]) or any(v in SLOT for v in g[-W:]))
        key = (-edge, nz, score)
        if best is None or key > best[0]:
            best = (key, S, grids)
    if not best:
        raise ValueError("slot grid not found")
    return best[1], best[2]


def is_rows(v):
    """로우 목록 모양: 짝수 내림차순 (00) 홀수 오름차순.  예) 06 04 02 01 03 05"""
    ev = [x for x in v if x % 2 == 0 and x > 0]
    od = [x for x in v if x % 2 == 1]
    return len(v) >= 1 and v == ev + ([0] if 0 in v else []) + od and ev == sorted(ev, reverse=True) and od == sorted(od) and (len(od) > 0 or 0 in v)


def split_record(rec):
    """글자 표 한 베이 -> (해치 안 로우, 티어, 갑판 로우). 내용 모양으로 구분"""
    groups = [[int(x) for x in g.split()] for g in re.findall(r"\d\d(?: \d\d)*", rec)] if " " in rec.strip() else              [[int(g[k:k + 2]) for k in range(0, len(g), 2)] for g in re.findall(r"(?:\d\d)+", rec)]
    hr, tl, dr = [], [], []
    for g in groups:
        if g == sorted(g) and all(x % 2 == 0 for x in g) and (len(g) > 1 or g[0] >= 2) and not (len(g) > 1 and is_rows(g) and not tl):
            tl += g
        elif is_rows(g):
            if tl:
                dr = dr or g
            else:
                hr = hr or g
        else:
            return None
    return hr, tl, dr


def find_text(d, n, f, grid_tiers, max_short=0):
    L, fields = f["text_len"], f["fields"]
    best = None
    for m in re.finditer(rb" \d\d(?: ?\d\d){2,} ", d):
        t0 = m.start() + 1
        for base in range(t0 - L, t0 + 1):
            res, score, short = [], 0, 0
            for i in range(n):
                raw = d[base + L * i: base + L * (i + 1)].decode("latin-1")
                if L == 234:
                    # 6.50: 기록 경계에서 숫자가 잘리면 안 됨
                    if raw[:1].isdigit() or raw[-1:].isdigit():
                        break
                    fs = split_record(raw)
                    if not fs:
                        break
                else:
                    (a0, a1), (b0, b1), (c0, c1) = fields
                    fs = (pairs(raw[a0:a1]), pairs(raw[b0:b1]), pairs(raw[c0:c1]))
                if not fs[1]:
                    break
                if len(fs[1]) < grid_tiers[i]:
                    # 40' 베이(짝수)는 티어 목록이 덜 적힌 파일이 있음(PCTJ) -> 두 개까지만 봐줌. 그 베이는 parse_define 에서 버림
                    short += 1
                    if short > max_short:
                        break
                res.append(fs)
                score += sum(len(x) for x in fs)
            if len(res) == n and (best is None or score - 1000 * short > best[0]):
                score -= 1000 * short
                best = (score, res)
        if best:
            return best[1]
    raise ValueError("bay text table not found")


def find_text_global(d, n, f, grid_tiers):
    """글자 표가 여러 군데(기본값 표 + 진짜 표) 있는 파일용: 모든 후보 위치를 다 보고, 티어 수가 칸 표 줄 수와 가장 많이 맞는 곳을 고름 (SWSH)"""
    L = f["text_len"]
    if L != 234:
        raise ValueError("bay text table not found")
    cands = set()
    for m in re.finditer(rb" \d\d(?: ?\d\d){2,} ", d):
        t0 = m.start() + 1
        cands.update(range(max(0, t0 - L), t0 + 1))
    best = None
    for base in sorted(cands):
        res, exact, score = [], 0, 0
        for i in range(n):
            raw = d[base + L * i: base + L * (i + 1)].decode("latin-1")
            if len(raw) < L or raw[:1].isdigit() or raw[-1:].isdigit():
                break
            fs = split_record(raw)
            if not fs or not fs[1]:
                break
            exact += len(fs[1]) == grid_tiers[i]
            res.append(fs)
            score += sum(len(x) for x in fs)
        if len(res) == n and (best is None or (exact, score) > best[0]):
            best = ((exact, score), res)
    if not best or best[0][0] < n * 0.6:
        raise ValueError("bay text table not found")
    return best[1]


def parse_define(path, deep=False):
    d = open(path, "rb").read()
    head = d[:64].decode("latin-1")
    ver = re.search(r"(\d)\.(\d\d)", head)
    fmt = "6.50" if "CONVERTED" in head or (ver and int(ver.group(1) + ver.group(2)) >= 650) else "6.10"
    f = FORMATS[fmt]
    W = f["W"]
    bays, ents = bay_list(d, f, True)
    if fmt == "6.10":   # 헤더의 베이 수 (목록 뒤에 지난 값이 남아 있을 수 있음)
        bays = bays[:struct.unpack_from("<h", d, 0x94)[0]]
    n = len(bays)
    S, grids = find_grids(d, n, W)
    gl = [[t for t in range(W) if any(v in SLOT for v in g[t * W:(t + 1) * W])] for g in grids]
    if deep:
        text = find_text_global(d, n, f, [len(x) for x in gl])
    else:
        try:
            text = find_text(d, n, f, [len(x) for x in gl])
        except ValueError:
            text = find_text(d, n, f, [len(x) for x in gl], max_short=max(2, n // 6))
    # 배 중심선 찾기: 슬롯 줄의 가운데가 정수 칸이면 로우 00이 있는 줄, x.5 면 02|01 사이
    from collections import Counter
    whole, half = Counter(), Counter()
    for g, ls in zip(grids, gl):
        for t in ls:
            cs = [c for c in range(W) if g[t * W + c] in SLOT]
            m2 = cs[0] + cs[-1]
            (whole if m2 % 2 == 0 else half)[m2 // 2] += 1
    hc = half.most_common(1)[0][0] if half else W // 2 - 1       # 02 칸 (01 은 hc+1)
    zc = whole.most_common(1)[0][0] if whole else hc             # 00 칸

    def c2r(c, with00):
        if with00:
            return 0 if c == zc else 2 * (zc - c) if c < zc else 2 * (c - zc) - 1
        return 2 * (hc + 1 - c) if c <= hc else 2 * (c - hc - 1) + 1

    # 6.50: 베이 기록 19번째 바이트 = 해치 안 맨 위 줄 (+ 배마다 고정값 k). k 는 모든 베이가 말이 되는 값으로 고름
    k_best = None
    k_bad = 0
    if fmt == "6.50":
        best = None
        for k in range(-W, W):
            bad = 0
            for i in range(n):
                hb = ents[i][19] + k
                H = [t for t in text[i][1] if t < 50]
                D = [t for t in text[i][1] if t > 50]
                hl = [t for t in gl[i] if t <= hb]
                dl = [t for t in gl[i] if t > hb]
                bad += max(0, len(hl) - len(H)) + max(0, len(dl) - len(D))
                if hl and hl[-1] != hb and H:
                    bad += 1          # 해치 안 맨 위 줄에는 보통 슬롯이 있음
                if H and not hl:
                    bad += len(H)     # 해치 안 티어가 있는데 해치 안 줄이 하나도 없으면 경계가 틀린 것
            if best is None or bad < best[0]:
                best = (bad, k)
        k_best = best[1]
        k_bad = best[0]
        if os.environ.get("DEF_DEBUG"):
            print("k", best)
    out = {}
    for i, b in enumerate(bays):
        hr, tl, dr = text[i]
        tl = sorted(tl)
        if not gl[i]:
            continue
        if len(tl) < len(gl[i]):
            continue   # 티어 목록이 덜 적힌 베이는 믿을 수 없어 뺌 (뷰어가 앞뒤 20' 베이로 대신 그림)
        # 슬롯 표의 맨 위 줄 = 그 베이의 맨 위 티어. 아래로 한 줄씩 = 한 티어씩.
        # 줄 사이가 비어 있으면(예: 08 과 84 사이 82 자리) 배 전체 티어 순서를 따름, 아니면 그 베이 티어 목록을 따름
        tmap = {}
        if k_best is not None and (k_bad > 0 or deep) and len(tl) == len(gl[i]):
            # 경계 값(k)이 깔끔하게 안 나온 파일: 줄 수와 티어 수가 같으면 아래 줄부터 차례로 붙임 (PCTJ)
            for line, tier in zip(gl[i], tl):
                tmap[line] = tier
        elif k_best is not None:
            # 해치 안: 맨 위 줄부터 아래로 해치 안 티어(큰 것부터) / 갑판: 슬롯 있는 첫 줄부터 위로 갑판 티어(작은 것부터)
            hb = ents[i][19] + k_best
            H = sorted([t for t in tl if t < 50], reverse=True)
            D = sorted(t for t in tl if t > 50)
            for idx, t in enumerate(range(hb, hb - len(H), -1)):
                tmap[t] = H[idx]
            dl = [t for t in gl[i] if t > hb]
            if dl:
                for idx, t in enumerate(range(dl[0], dl[0] + len(D))):
                    tmap[t] = D[idx]
        else:
            # 6.10: 슬롯 표의 맨 위 줄 = 그 베이의 맨 위 티어, 한 줄씩 내려가며 티어 목록을 붙임
            top = gl[i][-1]
            for t in gl[i]:
                k = len(tl) - 1 - (top - t)
                if k >= 0:
                    tmap[t] = tl[k]
        slots = []
        for t in gl[i]:
            if t not in tmap:
                continue
            tier = tmap[t]
            w00 = (0 in hr) if tier < 50 else (0 in dr)
            for c in range(W):
                v = grids[i][t * W + c]
                if v in SLOT:
                    slots.append([c2r(c, w00), tier, 3 if v & 2 else 1])
        out[str(b)] = slots
    # 자체 점검: 읽은 슬롯의 로우/티어가 그 베이 글자 표의 로우/티어 목록 안에 있어야 함
    total = wrong = 0
    for i, b in enumerate(bays):
        hr, tl, dr = text[i]
        for r, t, _ in out.get(str(b), []):
            total += 1
            rows = hr if t < 50 and hr else dr
            if t not in tl or r not in rows:
                wrong += 1
    if not total or wrong / total > 0.02:
        raise ValueError(f"자체 점검 실패 (안 맞는 슬롯 {wrong}/{total})")
    name = re.sub(r"\s+", " ", d[0x30:0x60].decode("latin-1")).strip()
    return {"format": fmt, "bays": bays, "slots": out, "name": name}
