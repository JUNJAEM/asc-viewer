# 팀 배포용 묶음: 뷰어 파일 + 설명서.pdf → zip
import io, os, re, base64, shutil, subprocess, zipfile
SP = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(os.path.dirname(SP))
CH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DIST = os.path.join(V, "dist"); PK = os.path.join(DIST, "asc-viewer")
if os.path.exists(DIST): shutil.rmtree(DIST)
os.makedirs(PK)
for f in ["viewer.src.html", "ships.js", "open-asc.ps1", "install.bat", "uninstall.bat", "mail-config.js", "splash.jpg"]:
    if not os.path.exists(os.path.join(V, f)): continue   # mail-config.js 는 이 PC 에만 있음(깃허브 제외)
    shutil.copy2(os.path.join(V, f), os.path.join(PK, f))

ships = io.open(os.path.join(V, "ships.js"), encoding="utf-8").read()
codes = re.findall(r'"?([A-Z0-9]{3,4})"?:\{"?n"?:"([^"]*)"', ships)
shiplist = " · ".join(c for c, n in codes)
def img(k): return "data:image/png;base64," + base64.b64encode(open(os.path.join(SP, "g_%s.png" % k), "rb").read()).decode()

html = u'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>PLAN VIEWER MADE BY JUNJAE 사용 설명서</title>
<style>
@page{size:A4 landscape;margin:11mm 12mm}
*{box-sizing:border-box}
body{margin:0;font:12.5px/1.55 "Malgun Gothic",sans-serif;color:#111}
.pg{page-break-after:always;height:186mm;display:flex;flex-direction:column}
.pg:last-child{page-break-after:auto}
h1{font-size:25px;margin:0 0 2px;color:#000080} h2{font-size:18px;margin:0 0 6px;color:#000080;border-bottom:3px solid #000080;padding-bottom:4px}
h3{font-size:14px;margin:10px 0 4px}
.sub{color:#444;margin:0 0 10px;font-size:13px}
.cols{display:flex;gap:9mm;flex:1;min-height:0}
.cols>div{flex:1;min-width:0}
ol{margin:0;padding-left:20px} li{margin:0 0 7px}
.no{display:inline-block;background:#e00000;color:#fff;border-radius:50%;width:19px;height:19px;line-height:19px;text-align:center;font-weight:700;font-size:12px;margin-right:4px}
.shot{width:100%;border:1px solid #000;display:block}
.cap{font-size:11.5px;color:#333;margin-top:5px}
.mock{border:1px solid #777;background:#fff;font:12px "Malgun Gothic";margin:6px 0 4px;position:relative}
.mock .bar{background:#e8e8e8;border-bottom:1px solid #999;padding:3px 8px;font-size:11.5px}
.mock .row{padding:3px 10px;display:flex;gap:10px}.mock .row span{color:#777;margin-left:auto}
.mock .hl{outline:2.5px solid #e00000;outline-offset:-2px;background:#fff7c2;font-weight:700}
.tag{display:inline-block;background:#fff7c2;border:2px solid #e00000;border-radius:5px;padding:2px 8px;font-weight:700;margin:2px 0}
.cmd{background:#000;color:#eee;font:12px Consolas,monospace;padding:7px 10px;margin:6px 0 4px}
.box{border:1px solid #999;background:#f6f6f6;padding:7px 10px;margin-top:8px}
table{border-collapse:collapse;width:100%} td,th{border:1px solid #999;padding:5px 8px;vertical-align:top;text-align:left} th{background:#e6e6f2;width:36%}
.foot{margin-top:auto;font-size:10.5px;color:#666;padding-top:4px}
kbd{border:1px solid #777;border-radius:3px;padding:0 4px;background:#f2f2f2;font:11.5px Consolas,monospace}
</style></head><body>

<section class="pg">
<h1>PLAN VIEWER MADE BY JUNJAE 사용 설명서</h1>
<p class="sub">Outlook 첨부파일 <b>.asc</b>를 더블클릭하면 CASP · cCASP에 올리지 않고도 바로 스토이지 플랜이 뜨는 도구예요.</p>
<div class="cols">
<div>
<h2>1. 설치 (처음 한 번, 1분)</h2>
<ol>
<li><b>압축을 풀고 <span class="tag">asc-viewer</span> 폴더를 옮기지 않을 곳에 두세요.</b><br>예: <kbd>문서</kbd> 폴더 안. 나중에 폴더를 옮기면 2번을 다시 해야 해요.</li>
<li><b>폴더 안의 <span class="tag">install.bat</span>을 더블클릭하세요.</b>
<div class="mock"><div class="bar">📁 asc-viewer</div>
<div class="row hl">install.bat <span>← 이걸 더블클릭 (설치)</span></div>
<div class="row">uninstall.bat <span>지울 때</span></div>
<div class="row">open-asc.ps1 <span>건드리지 않음</span></div>
<div class="row">viewer.src.html <span>건드리지 않음</span></div>
<div class="row">ships.js <span>건드리지 않음 (선박 구조)</span></div>
<div class="row">mail-config.js <span>메일 받는 사람 고정값</span></div>
<div class="row">설명서.pdf <span>이 문서</span></div></div>
"Windows의 PC 보호" 파란 창이 뜨면 <b>추가 정보 → 실행</b>을 누르세요.</li>
<li><b>검은 창에 <span class="tag">Done.</span> 이 보이면 아무 키나 눌러 닫으세요.</b>
<div class="cmd">Done. .asc files now open in PLAN VIEWER MADE BY JUNJAE.<br>계속하려면 아무 키나 누르십시오 . . .</div></li>
</ol>
<div class="box">관리자 권한이 필요 없고, 내 계정에만 적용돼요. 프로그램을 따로 까는 게 아니라 ".asc 파일을 이 뷰어로 열어라"는 연결만 등록해요.</div>
</div>
<div>
<h2>2. 쓰는 법</h2>
<ol>
<li><b>Outlook 메일에서 .asc 첨부파일을 더블클릭하세요.</b><br>"첨부 파일 열기" 창이 뜨면 <b>열기</b>를 누르세요.</li>
<li><b>기본 브라우저(크롬 · 엣지 · 웨일)에 플랜이 떠요.</b><br>선박은 파일 이름에서 알아서 찾아요. (예: <kbd>…_HRON.asc</kbd>, <kbd>TYTR2635W….asc</kbd>)</li>
<li><b>탐색기에 저장해 둔 .asc 파일도 더블클릭하면 똑같이 열려요.</b></li>
</ol>
<h3>처음 열 때 "이 파일을 여는 방법"을 물으면</h3>
<p style="margin:0">목록에서 <span class="tag">Windows PowerShell</span>을 고르고 <b>항상</b>을 누르세요. 다른 프로그램(메모장 등)이 계속 열리면 .asc 파일을 오른쪽 클릭 → <b>연결 프로그램 → 다른 앱 선택</b>에서 같은 것을 고르면 돼요.</p>
<h3>알아 두세요</h3>
<ul style="margin:0;padding-left:18px">
<li>파일은 <b>내 PC 안에서만</b> 읽어요. 인터넷으로 올라가지 않아요.</li>
<li>보기 전용이에요. 플랜을 고치거나 저장하지는 못해요.</li>
<li>지우려면 <kbd>uninstall.bat</kbd>을 더블클릭한 뒤 폴더를 지우세요.</li>
</ul>
</div>
</div>
<div class="foot">PLAN VIEWER · 부산 운항 · 1 / 4</div>
</section>

<section class="pg">
<h2>3. 첫 화면 — Summary와 General Plan</h2>
<img class="shot" src="%(main)s" alt="">
<p class="cap">CASP처럼 <b>General Plan이 메인</b>이에요. 선수가 오른쪽이고, 해치마다 위가 앞 베이, 아래가 뒤 베이(40'는 <kbd>15(14)</kbd>처럼 표시)예요. 칸 위쪽 색 = 양하항(POD), 아래 띠 색 = 선적항(POL).</p>
<div class="foot">PLAN VIEWER · 부산 운항 · 2 / 4</div>
</section>

<section class="pg">
<h2>4. Bay Plan 창 — 베이를 더블클릭하면 떠요</h2>
<img class="shot" src="%(bay)s" alt="">
<p class="cap">칸 위쪽 색 = 양하항(POD), 아래 띠 = 선적항(POL, 북항 PUS / 신항 PNC). 빗금 = 40', × = 옆 베이 40'가 차지한 칸. 로우 번호 아래 작은 숫자는 그 줄의 무게 합계(톤)예요.</p>
<div class="foot">PLAN VIEWER · 부산 운항 · 3 / 4</div>
</section>

<section class="pg">
<h2>5. 자주 묻는 것</h2>
<div class="cols"><div>
<table>
<tr><th>선박 모양이 실제와 달라요</th><td>파일 이름에서 선박을 못 찾았거나 다른 선박으로 잡힌 경우예요. 화면의 <b>선박</b> 칸에서 직접 고르세요. 목록에 없는 선박은 실린 칸 기준으로만 그려져요.</td></tr>
<tr><th>더블클릭해도 메모장이 열려요</th><td>.asc 파일 오른쪽 클릭 → <b>연결 프로그램 → 다른 앱 선택 → Windows PowerShell → 항상</b>.</td></tr>
<tr><th>아무것도 안 떠요</th><td>asc-viewer 폴더를 옮기거나 이름을 바꿨는지 확인하고, <kbd>install.bat</kbd>을 다시 더블클릭하세요.</td></tr>
<tr><th>포트 색이 헷갈려요 / 바꾼 색을 되돌리고 싶어요</th><td>Summary의 <b>색정렬</b> 버튼을 누르세요. 양하항 개수에 맞춰 가장 잘 구분되는 색으로 다시 칠해요. 직접 바꾼 색은 내 PC 브라우저에만 저장돼요.</td></tr>
<tr><th>화면이 작아요 / 커요</th><td>General Plan 제목줄의 <b>− % +</b> 또는 <kbd>Alt</kbd> + 휠. 창 오른쪽 · 아래 가장자리를 끌면 창 크기도 바뀌어요(더블클릭 = 원래대로).</td></tr>
<tr><th>컨테이너를 찾고 싶어요</th><td><kbd>Alt</kbd> + <kbd>F</kbd>(또는 <b>컨테이너 찾기</b> 버튼)를 누르면 찾기 창이 떠요. 번호 일부만 넣어도 돼요. <kbd>Enter</kbd>를 누르면 그 베이가 열려요.</td></tr>
</table>
</div><div>
<h3 style="margin-top:0">선박 모양이 들어 있는 배 (SKR · HAS 운용 %(n)d척)</h3>
<p style="margin:0 0 8px;font-size:10px;line-height:1.45">%(ships)s</p>
<div class="box">선박 구조는 cCASP에서 받아 온 거예요. 플랜의 칸이 선박 구조와 3%% 넘게 안 맞으면 구조를 쓰지 않고 실린 칸 기준으로 그려요.</div>
<h3>칸 표시 한눈에</h3>
<table>
<tr><th>가운데 숫자</th><td>무게(톤)</td></tr>
<tr><th>H</th><td>하이큐빅</td></tr>
<tr><th>빨간 숫자 (예: 3, 9)</th><td>위험물 등급</td></tr>
<tr><th>E / T / TE</th><td>공컨 / 탱크 / 빈 탱크</td></tr>
<tr><th>R</th><td>냉동 (온도 설정된 것)</td></tr>
<tr><th>빗금 / ×</th><td>40' / 옆 베이 40'가 차지한 칸</td></tr>
</table>
<p style="margin:10px 0 0">고장이나 건의는 배포한 사람에게 알려 주세요.</p>
</div></div>
<div class="foot">PLAN VIEWER · 부산 운항 · 4 / 4</div>
</section>
</body></html>'''
for k, v in {"%(main)s": img("main"), "%(bay)s": img("bay"), "%(ships)s": shiplist, "%(n)d": str(len(codes)), "3%%": "3%"}.items():
    assert k in html, k
    html = html.replace(k, v)
gh = os.path.join(SP, "guide.html"); io.open(gh, "w", encoding="utf-8").write(html)
pdf = os.path.join(PK, u"설명서.pdf")
subprocess.run([CH, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf=" + pdf, "file:///" + gh.replace("\\", "/")], capture_output=True)
z = os.path.join(DIST, u"PLAN_VIEWER_배포.zip")
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(os.listdir(PK)): zf.write(os.path.join(PK, f), "asc-viewer/" + f)
print(len(codes), os.path.getsize(pdf), os.path.getsize(z)); print(zipfile.ZipFile(z).namelist())
