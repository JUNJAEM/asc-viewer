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

## 파일

| 파일 | 설명 |
|---|---|
| `viewer.src.html` | 뷰어 본체 (본문만 있는 한 장짜리) |
| `index.html` | 웹용. `python tools/build_site.py`로 `viewer.src.html`에서 만들어요 (직접 고치지 않기) |
| `ships.js` | 선박 구조(SKR · HAS 운용 컨테이너선). `tools/build_ships.py`로 만들어요 |
| `open-asc.ps1` | ASC 파일을 임시 HTML로 만들어 브라우저로 여는 실행 파일 |
| `asc-mail-watch.ps1` | (선택) `.asc` 메일이 오면 폰에서 보기 좋은 그림 전용 파일을 만들어 본인에게 보내 줘요 |
