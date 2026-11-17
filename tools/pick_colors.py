# -*- coding: utf-8 -*-
"""양하항(POD) 개수별 '가장 잘 구분되는 색' 묶음 계산 -> 뷰어의 SETS 표

    python tools/pick_colors.py

- 후보: 뷰어의 PAL 12색. 색 차이는 CIEDE2000.
- 조건: 고른 색끼리 가장 가까운 쌍의 차이가 최대가 되게(최소 차이 최대화).
  선적항 띠 색(흰·검정·회색)과도 멀어야 해서 그 거리도 같은 기준에 넣음.
- 동점이면 색맹(적록) 시뮬레이션에서도 차이가 큰 쪽, 그다음 PAL 앞쪽(기본 색) 우선.

최종 (2026-11-17, 뷰어 PAL 순서에 반영): 진한 색 9개(흰·검정 띠와 25 이상 떨어진 것)를 먼저 쓰고,
적록 색약 차이에 1.6배 가중을 주어 계산하면 4개 이상은 앞 N색이 그대로 최적 묶음이 됨.
2·3개는 계산상 보라·연두 / 파랑·빨강·청록이지만, 현장에서 가장 익숙한 노랑·파랑(76) / 노랑·파랑·빨강으로 정함.
  노랑 파랑 빨강 청록 분홍 주황 초록 보라 연두 하늘 갈색 살구
"""
import itertools, math, json, sys

PAL = ["#ffeb00", "#2f7bff", "#ff4136", "#2ecc40", "#ff9f1a", "#5fd8ff", "#ff85e0", "#a66bff", "#c3f53c", "#b98555", "#19c2b0", "#ffd0b0"]
NM = ["노랑", "파랑", "빨강", "초록", "주황", "하늘", "분홍", "보라", "연두", "갈색", "청록", "살구"]
POL = ["#ffffff", "#000000", "#8c8c8c", "#d9d9d9"]


def rgb(h): return [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lab_from_lin(r, g, b):
    X = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047; Y = 0.2126 * r + 0.7152 * g + 0.0722 * b; Z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    t = lambda v: v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116
    fx, fy, fz = t(X), t(Y), t(Z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab(h): return lab_from_lin(*[lin(c) for c in rgb(h)])


def deutan(h):   # 적록 색약(2형) 시뮬레이션 (Viénot 1999)
    r, g, b = [lin(c) for c in rgb(h)]
    return lab_from_lin(0.29275 * r + 0.70725 * g, 0.29275 * r + 0.70725 * g, -0.02234 * r + 0.02234 * g + b)


def de(a, b):
    L1, a1, b1 = a; L2, a2, b2 = b
    C1 = math.hypot(a1, b1); C2 = math.hypot(a2, b2); Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7))); a1p = (1 + G) * a1; a2p = (1 + G) * a2
    C1p = math.hypot(a1p, b1); C2p = math.hypot(a2p, b2)
    h1 = math.degrees(math.atan2(b1, a1p)) % 360; h2 = math.degrees(math.atan2(b2, a2p)) % 360
    dL = L2 - L1; dC = C2p - C1p; dh = h2 - h1
    if C1p * C2p == 0: dh = 0
    elif dh > 180: dh -= 360
    elif dh < -180: dh += 360
    dH = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lb = (L1 + L2) / 2; Cbp = (C1p + C2p) / 2
    hb = (h1 + h2) / 2 if abs(h1 - h2) <= 180 else ((h1 + h2 + 360) / 2 if h1 + h2 < 360 else (h1 + h2 - 360) / 2)
    T = 1 - 0.17 * math.cos(math.radians(hb - 30)) + 0.24 * math.cos(math.radians(2 * hb)) + 0.32 * math.cos(math.radians(3 * hb + 6)) - 0.2 * math.cos(math.radians(4 * hb - 63))
    dth = 30 * math.exp(-((hb - 275) / 25) ** 2); RC = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    SL = 1 + 0.015 * (Lb - 50) ** 2 / math.sqrt(20 + (Lb - 50) ** 2); SC = 1 + 0.045 * Cbp; SH = 1 + 0.015 * Cbp * T; RT = -math.sin(math.radians(2 * dth)) * RC
    return math.sqrt((dL / SL) ** 2 + (dC / SC) ** 2 + (dH / SH) ** 2 + RT * (dC / SC) * (dH / SH))


def main():
    L = [lab(h) for h in PAL]; Ld = [deutan(h) for h in PAL]; P = [lab(h) for h in POL]
    D = [[de(L[i], L[j]) for j in range(12)] for i in range(12)]
    Dd = [[de(Ld[i], Ld[j]) for j in range(12)] for i in range(12)]
    toPol = [min(de(L[i], p) for p in P) for i in range(12)]
    sets = {}
    for n in range(1, 13):
        best = None
        for S in itertools.combinations(range(12), n):
            pairs = list(itertools.combinations(S, 2))
            m = min([D[i][j] for i, j in pairs] + [toPol[i] for i in S])
            md = min([Dd[i][j] for i, j in pairs] or [999])
            key = (round(m, 0), round(md, 0), -sum(S))
            if best is None or key > best[0]: best = (key, S)
        sets[n] = list(best[1])
        print(n, "최소 차이", best[0][0], "| 색약", best[0][1], "|", " ".join(NM[i] for i in best[1]))
    print(json.dumps(sets, separators=(",", ":")))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
