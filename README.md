# PLAN VIEWER MADE BY JUNJAE

CASP ASC(`$609` / `$604`) 스토이지 플랜 파일을 CASP · cCASP 없이 바로 보는 뷰어예요.
General Plan이 메인이고, 베이를 더블클릭하면 Bay Plan 창이 떠요.

## 폰 · 웹에서 보기

깃허브 페이지 주소를 열고 **ASC 파일 열기**로 파일을 고르면 돼요.
파일은 그 기기 안에서만 읽고 어디에도 올리지 않아요.

## PC에서 Outlook 첨부를 더블클릭으로 열기 (Windows)

1. 이 저장소를 내려받아(Code → Download ZIP) 옮기지 않을 폴더에 풀어요.
2. `install.bat`을 더블클릭해요. (내 계정에만 `.asc` 연결을 등록해요. 관리자 권한 불필요)
3. Outlook이나 탐색기에서 `.asc` 파일을 더블클릭하면 기본 브라우저에 플랜이 떠요.

지울 때는 `uninstall.bat`.

## 폰에서 메일함까지 앱처럼 쓰기

폰에는 아무것도 깔지 않아요. **서버 PC 한 대**만 Tailscale Funnel 로 고정 주소(`https://<서버 PC>.ts.net`)를 열고, 폰과 다른 PC 는 그 주소로 들어와요. 팀원 PC 에는 Tailscale 을 깔지 않아요.

```
폰 ──(로그인)──> 서버 PC ──대기열──> 내 회사 PC 도우미가 먼저 물어 와서 가져감
                    <── 결과 ───────  내 PC 의 아웃룩으로 처리해 올림
```

- 메일은 각자 자기 회사 PC 의 아웃룩에서 나와요. 서버는 로그인한 사람의 요청을 그 사람 대기열에 넣어 두고, 그 사람 PC 의 도우미(`mail-server.ps1 -Agent`)가 "내 일 있나?" 하고 물어 와서 가져가요. 밖에서 팀원 PC 로 들어가는 연결은 없어요.
- 내 일은 내 PC 도우미만 가져가요 (도우미를 등록할 때 내 아이디 · 비밀번호로 확인하고 그 PC 만의 열쇠를 받아요).
- 도우미는 읽기만 해요 (메일 쓰기 · 보내기 없음). 아웃룩은 COM 으로만, 받은 메일의 최근 14일까지만 봐요: 받은 편지함과 그 아래 폴더, 그리고 `mail-rules.json` 에 이름이 있는 맨 위 폴더(규칙으로 분류해 둔 곳). 보낸 편지함 · 삭제된 항목 · 다른 저장소는 열지 않아요. (삭제된 항목도 보려면 `mail-rules.json` 에 `"phoneAlso": ["deleted"]`)

### 공유 링크 (로그인 · 도우미 없이 보기)

`python phone-server.py --link` 가 `https://<서버 PC>.ts.net/t/<열쇠>/` 모양의 링크를 보여 줘요. 이 링크를 연 사람은 로그인 없이, 따로 깔 것도 없이 **링크 주인의 메일함**(그 사람 PC 의 플랜 메일, 읽기만)을 봐요. 홈 화면에 추가하면 그 링크로 바로 열려요.

- 링크가 곧 열쇠예요. 팀 안에서만 돌리세요. 열쇠 없는 주소(`https://<서버 PC>.ts.net/`)는 그대로 로그인을 물어요.
- `--new-link` 로 새로 만들면 앞의 링크는 그 자리에서 못 쓰게 돼요. 없애기는 `--del-link`.
- 각자 자기 메일함을 보게 하려면 아래처럼 사람을 추가하고 각자 PC 에 도우미를 둬요.
### 서버 PC (한 대, 한 번)

1. Tailscale 과 Python 을 깔고 Tailscale 에 로그인해요.
2. `powershell -ExecutionPolicy Bypass -File phone-setup.ps1`. Funnel 허용 링크가 나오면 한 번 열어 허용하고 다시 실행해요.
3. 사람 추가: `python phone-server.py --add-user 아이디 [이름]` (비밀번호를 만들어 보여 줘요). 목록은 `--users`, 지우기는 `--del-user`, 비밀번호 바꾸기는 `--set-password`.

서버가 죽으면 2분 안에 다시 켜지고, 공개 주소만 안 열리면 Tailscale 을 다시 붙여요 (예약 작업 `PLAN VIEWER phone server`, 기록은 `%LOCALAPPDATA%\asc-viewer\phone-watch.log`). 끄기는 `phone-setup.ps1 -Off`.

### 각자 회사 PC (한 번)

1. 팀 배포 zip 을 풀고 `phone-agent-setup.bat` 을 더블클릭해요.
2. 받은 아이디 · 비밀번호를 넣어요. `Connected` 가 보이면 끝이에요. (비밀번호는 PC 에 남지 않아요.)
3. PC 는 켜 두고 윈도우에 로그인된 채로, 아웃룩을 열어 두세요. 끄기는 `phone-agent-setup.ps1 -Off`.

### 폰 (기기마다 한 번)

서버 주소를 열고 로그인 → 안드로이드 크롬은 **앱 설치**, 아이폰 사파리는 **공유 → 홈 화면에 추가**. 한 번 로그인하면 쓰는 동안은 다시 묻지 않아요.
## 파일

| 파일 | 설명 |
|---|---|
| `viewer.src.html` | 뷰어 본체 (본문만 있는 한 장짜리) |
| `index.html` | 웹용. `python tools/build_site.py`로 `viewer.src.html`에서 만들어요 (직접 고치지 않기) |
| `ships.js` | 선박 구조(SKR · HAS 운용 컨테이너선). `tools/build_ships.py`로 만들어요 |
| `open-asc.ps1` | ASC 파일을 임시 HTML로 만들어 브라우저로 여는 실행 파일 |
| `asc-mail-watch.ps1` | (선택) `.asc` 메일이 오면 폰에서 보기 좋은 그림 전용 파일을 만들어 본인에게 보내 줘요 |
| `phone-server.py` | (선택 · 서버 PC) 폰용 서버. 로그인 뒤에 뷰어를 내어 주고, 메일함 요청을 그 사람 대기열에 맡겨요 (127.0.0.1 에서만 들어요) |
| `phone-watch.py` | (선택 · 서버 PC) 2분마다 서버와 공개 주소를 살펴보고 되살려요 |
| `phone-setup.ps1` | (선택 · 서버 PC) 위 둘을 켜고 끄는 설치 스크립트 |
| `phone-agent-setup.bat` · `.ps1` | (선택 · 각자 PC) 내 PC 의 도우미를 서버에 등록하고 켜 둬요 |
