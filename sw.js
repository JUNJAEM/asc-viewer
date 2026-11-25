// PLAN VIEWER MADE BY JUNJAE 앱(설치판)용 서비스 워커
// - 항상 새 판을 먼저 받아 오고(폰이 옛 판을 붙잡지 않게), 인터넷이 안 될 때만 저장해 둔 판을 씀
// - 다른 앱(아웃룩 등)에서 '공유'로 넘어온 .asc 파일을 받아 뷰어에 넘김
var C = "asc-viewer-v1", SH = "asc-shared";
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", function (e) {
  var r = e.request, u = new URL(r.url);
  if (u.origin !== location.origin) return;
  // 폰 서버판(회사 PC 가 내어 주는 주소): 메일함 · 로그인 요청은 건드리지 않음 — 메일 목록이 폰에 저장되지 않게, 로그인 화면이 옛 것으로 보이지 않게
  if (/^(api\/|login$|logout$|healthz$)/.test(u.pathname.slice(new URL(self.registration.scope).pathname.length))) return;
  if (r.method === "POST" && /\/share$/.test(u.pathname)) {
    e.respondWith(r.formData().then(function (fd) {
      var fs = fd.getAll("file").filter(function (x) { return x && x.arrayBuffer; }), f = fs[0];
      if (!f) return Response.redirect("./", 303);
      return caches.open(SH).then(function (c) {
        return c.put(new URL("shared-file", self.registration.scope).href,
          new Response(f, { headers: { "X-Name": encodeURIComponent(f.name || "plan.asc"), "Content-Type": "application/octet-stream" } }));
      }).then(function () { return Response.redirect("./?shared=1", 303); });
    }).catch(function () { return Response.redirect("./", 303); }));
    return;
  }
  if (r.method !== "GET") return;
  e.respondWith(fetch(r.url, { cache: "no-cache" }).then(function (res) {
    if (res.ok) { var cp = res.clone(); caches.open(C).then(function (c) { c.put(u.origin + u.pathname, cp); }); }
    return res;
  }).catch(function () {
    return caches.match(u.origin + u.pathname).then(function (m) { return m || caches.match(new URL("./", self.registration.scope).href); });
  }));
});
