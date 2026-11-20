# -*- coding: utf-8 -*-
"""우리 선박이 실제로 기항하는 포트의 좌표 (부두 쪽 위치) — VESSEL VIEW 의 날씨 조회용.
2026-11-20 전산 포트 스케줄(2026-01 ~ 2027-02, 장금·흥아·한성)에 나온 기항지 108곳을 전부 넣음. 포트 이름은 전산 포트 표의 이름.
회사 코드가 공개 목록(UN/LOCODE)과 뜻이 다른 곳이 있어서(예: KIJ = 니가타, TOS = 도야마 신항, TKY = 도쿠야마, ISS = 이시카리만 신항) 코드가 아니라 이름으로 위치를 잡음.
사용: python tools/geo_called.py            -> ports_geo.json 에 덮어 넣고 몇 곳이 들어갔는지 알려 줌 (그다음 python tools/build_ships.py)
      python tools/geo_called.py --check    -> 공개 지명 검색(Open-Meteo)과 견줘서 30 km 넘게 다른 곳을 알려 줌
새 기항지가 생기면 아래 표에 한 줄 넣고 다시 돌리면 됨. build_geo.py 도 끝에 이 표를 덮어 넣음."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CALLED = {
    # 한국
    "KRPUS": [35.10, 129.07, "Busan"], "KRPNC": [35.08, 128.83, "Busan New Port"], "KRINC": [37.45, 126.60, "Incheon"], "KRKAN": [34.90, 127.70, "Gwangyang"],
    "KRUSN": [35.50, 129.38, "Ulsan"], "KRPTK": [36.97, 126.83, "Pyeongtaek"], "KRKPO": [36.03, 129.40, "Pohang"], "KROKK": [37.62, 129.06, "Okgye"], "KRTSN": [37.01, 126.42, "Daesan"],
    # 일본
    "JPTYO": [35.62, 139.78, "Tokyo"], "JPYOK": [35.45, 139.65, "Yokohama"], "JPNGO": [35.08, 136.88, "Nagoya"], "JPOSA": [34.65, 135.43, "Osaka"], "JPUKB": [34.68, 135.20, "Kobe"],
    "JPHKT": [33.61, 130.40, "Hakata"], "JPMOJ": [33.95, 130.96, "Moji"], "JPSMZ": [35.02, 138.50, "Shimizu"], "JPOIT": [33.26, 131.67, "Oita"], "JPHBK": [33.93, 130.79, "Hibiki"],
    "JPKIJ": [37.98, 139.22, "Niigata"], "JPIYM": [33.99, 133.55, "Iyomishima"], "JPMIZ": [34.50, 133.74, "Mizushima"], "JPTAK": [34.36, 134.05, "Takamatsu"], "JPKNZ": [36.62, 136.61, "Kanazawa"],
    "JPMYJ": [33.86, 132.70, "Matsuyama"], "JPIMI": [33.31, 129.83, "Imari"], "JPHIJ": [34.35, 132.46, "Hiroshima"], "JPIMB": [34.07, 133.01, "Imabari"], "JPTOS": [36.77, 137.11, "Toyama"],
    "JPFKY": [34.44, 133.42, "Fukuyama"], "JPTKY": [34.04, 131.80, "Tokuyama"], "JPSBS": [31.47, 131.11, "Shibushi"], "JPIWK": [34.17, 132.24, "Iwakuni"], "JPTHS": [34.72, 137.33, "Toyohashi"],
    "JPNAO": [37.18, 138.25, "Naoetsu"], "JPAXT": [39.75, 140.06, "Akita"], "JPHSM": [32.43, 131.66, "Hososhima"], "JPTMK": [42.63, 141.63, "Tomakomai"], "JPHMD": [34.89, 132.06, "Hamada"],
    "JPSHS": [33.95, 130.93, "Shimonoseki"], "JPNAH": [26.23, 127.67, "Naha"], "JPKCZ": [33.52, 133.57, "Kochi"], "JPTRG": [35.66, 136.07, "Tsuruga"], "JPMAI": [35.52, 135.36, "Maizuru"],
    "JPSMN": [35.54, 133.25, "Sakaiminato"], "JPKMJ": [32.76, 130.58, "Kumamoto"], "JPNGS": [32.74, 129.86, "Nagasaki"], "JPYAT": [32.50, 130.55, "Yatsushiro"], "JPHIC": [36.40, 140.62, "Hitachinaka"],
    "JPHHE": [40.54, 141.53, "Hachinohe"], "JPKSM": [35.92, 140.69, "Kashima"], "JPYKK": [34.95, 136.64, "Yokkaichi"], "JPISS": [43.21, 141.29, "Ishikari"], "JPSDJ": [38.27, 141.02, "Sendai"],
    "JPSEN": [31.84, 130.20, "Satsumasendai"], "JPTKS": [34.05, 134.59, "Tokushima"],
    # 러시아 (블라디보스토크의 부두들)
    "RUVVO": [43.10, 131.88, "Vladivostok"], "RUVFP": [43.10, 131.87, "Vladivostok"], "RUVST": [43.09, 131.90, "Vladivostok"], "RUVMP": [43.11, 131.88, "Vladivostok"],
    # 중국 · 홍콩 · 대만
    "CNSHA": [31.35, 121.60, "Shanghai"], "CNNGB": [29.94, 121.85, "Ningbo"], "CNTAO": [36.08, 120.32, "Qingdao"], "CNDLC": [38.93, 121.65, "Dalian"], "CNTSN": [38.98, 117.75, "Tianjin"],
    "CNWEI": [37.50, 122.13, "Weihai"], "CNXMN": [24.45, 118.07, "Xiamen"], "CNZJG": [31.97, 120.41, "Zhangjiagang"], "CNNTG": [32.00, 120.82, "Nantong"], "CNSHK": [22.47, 113.90, "Shekou"],
    "CNNSA": [22.63, 113.67, "Nansha"], "CNTAG": [31.60, 121.26, "Taicang"], "CNNKG": [32.17, 119.05, "Nanjing"], "CNYNT": [37.57, 121.38, "Yantai"], "CNHUA": [23.09, 113.45, "Huangpu"],
    "CNSWA": [23.33, 116.75, "Shantou"], "CNZOS": [30.00, 122.10, "Zhoushan"], "HKHKG": [22.32, 114.13, "Hong Kong"], "TWKHH": [22.60, 120.28, "Kaohsiung"], "TWKEL": [25.15, 121.75, "Keelung"],
    # 동남아
    "VNHPH": [20.85, 106.75, "Haiphong"], "VNSGN": [10.77, 106.72, "Ho Chi Minh City"], "THLCH": [13.08, 100.88, "Laem Chabang"], "THBKK": [13.70, 100.57, "Bangkok"],
    "MYPKL": [2.95, 101.31, "Port Klang"], "MYPKG": [3.00, 101.37, "Port Klang"], "MYPEN": [5.40, 100.37, "Penang"], "MYPGU": [1.44, 103.90, "Pasir Gudang"], "MYTPP": [1.36, 103.55, "Tanjung Pelepas"],
    "SGSIN": [1.27, 103.80, "Singapore"], "IDJKT": [-6.10, 106.88, "Jakarta"], "IDSUB": [-7.20, 112.73, "Surabaya"], "IDSRG": [-6.94, 110.42, "Semarang"], "PHMNN": [14.62, 120.95, "Manila"],
    # 서남아 · 중동 · 그 밖
    "INMUN": [22.74, 69.70, "Mundra"], "INNSA": [18.95, 72.95, "Nhava Sheva"], "INMAA": [13.10, 80.30, "Chennai"], "INVTZ": [17.69, 83.29, "Visakhapatnam"], "BDCGP": [22.31, 91.80, "Chittagong"],
    "PKKHI": [24.84, 66.98, "Karachi"], "PKBQM": [24.77, 67.33, "Port Qasim"], "AEJEA": [25.01, 55.06, "Jebel Ali"], "AEKLF": [25.35, 56.37, "Khor Fakkan"], "SAJED": [21.47, 39.15, "Jeddah"],
    "JOAQB": [29.48, 34.98, "Aqaba"], "EGSOK": [29.65, 32.35, "Ain Sokhna"], "TRKMX": [40.96, 28.68, "Istanbul"], "MXZLO": [19.06, -104.30, "Manzanillo"],
}
def coords(): return dict((k, [v[0], v[1]]) for k, v in CALLED.items())
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--check" in sys.argv:
        import math, time, urllib.parse, urllib.request
        def km(a, b, c, d):
            p = math.pi / 180; x = (d - b) * p * math.cos((a + c) / 2 * p); y = (c - a) * p; return 6371 * math.sqrt(x * x + y * y)
        far = []; none = []
        for code, v in sorted(CALLED.items()):
            try:
                u = "https://geocoding-api.open-meteo.com/v1/search?count=10&language=en&format=json&name=" + urllib.parse.quote(v[2])
                res = [x for x in (json.load(urllib.request.urlopen(u, timeout=15)).get("results") or []) if x.get("country_code") == code[:2]]
            except Exception as e:
                print(code, "lookup failed:", str(e)[:60]); res = []
            if not res: none.append(code + " " + v[2]); continue
            d = min(km(v[0], v[1], x["latitude"], x["longitude"]) for x in res)
            if d > 30: far.append("%s %s: %.0f km from the nearest place of that name" % (code, v[2], d))
            time.sleep(0.15)
        print("checked", len(CALLED), "| within 30 km of a place of that name:", len(CALLED) - len(far) - len(none))
        print("farther than 30 km:", far); print("name not found in the public gazetteer:", none)
    else:
        f = os.path.join(HERE, "ports_geo.json"); out = json.load(open(f, encoding="utf-8")); before = dict(out)
        out.update(coords()); json.dump(out, open(f, "w", encoding="utf-8"), separators=(",", ":"), sort_keys=True)
        new = [k for k in CALLED if k not in before]; moved = [k for k in CALLED if k in before and before[k][:2] != out[k]]
        print("ports with coordinates:", len(before), "->", len(out), "| newly added:", len(new), "| corrected:", len(moved), moved)
