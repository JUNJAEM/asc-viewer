// 메일 받는 사람·참조 고정값 (긴급양하 / COD). 깃허브에도 올려 둠 (2026-11-17 결정) — 깃허브 페이지에서 열어도 수신처가 자동으로 들어가게.
// 고칠 때는 주소만 바꾸면 됨. "이름 <주소>" 또는 "주소" 형식.
window.ASC_MAIL={
  urgent:{
    to:["bptplan@bptc.co.kr","planner@bptc.co.kr","BPT 감만 플래너 <plan@bptc.co.kr>"],
    cc:["부산운항팀 운항담당 <bvot@sinokor.co.kr>"]
  },
  cod:{
    to:["moly558@naver.com","wje@woojinent.com","syoper1@sytally.com","syoper2@sytally.com","Syoper3 <syoper3@sytally.com>","cgt3355@daum.net"],
    cc:["부산운항팀 운항담당 <bvot@sinokor.co.kr>","장금상선 부산고객지원팀 <buscst@sinokor.co.kr>","흥아라인 부산고객지원팀 <buscst@heungaline.com>","장금상선 울산사무소 <ulsan@sinokor.co.kr>","장금상선 광양사무소 <kwangyang@sinokor.co.kr>","장금상선 평택사무소 <pyongtaek@sinokor.co.kr>","장금상선 인천사무소 <inchon@sinokor.co.kr>","장금상선 본사고객지원팀수입 <csti@sinokor.co.kr>"]
  }
};

// 폰·웹의 메일함: 회사 Microsoft 365 에 등록한 앱 ID (비밀 값이 아님 — 로그인 창을 띄울 때 쓰는 이름표).
// 비어 있으면 폰·웹의 메일함은 "설정이 필요해요" 안내만 보여 줌. 등록: Entra > 앱 등록 > 단일 페이지 앱, 리디렉션 URI = 깃허브 페이지 주소, 위임 권한 Mail.Read
window.ASC_GRAPH={clientId:"",tenant:"organizations"};
