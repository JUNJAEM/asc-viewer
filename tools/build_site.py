# -*- coding: utf-8 -*-
# 깃허브 페이지용 index.html 만들기: viewer.src.html(본문만 있는 뷰어)에 문서 뼈대를 씌운다.
# 뷰어를 고친 뒤에는  python tools/build_site.py  를 한 번 돌리고 커밋한다.
import io, os, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
body = io.open(os.path.join(ROOT, "viewer.src.html"), encoding="utf-8").read()
# 화면 오른쪽 위에 올린 날짜·시각을 찍는다 (폰이 옛 판을 붙잡고 있는지 알아보는 용도)
body = body.replace("<!--VER-->", time.strftime("%m-%d %H:%M") + u" 판")
head = (u'<!doctype html>\n<html lang="ko"><head><meta charset="utf-8">'
        u'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        u'<meta name="robots" content="noindex,nofollow">'
        u'<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="ASC 뷰어">'
        u'<link rel="apple-touch-icon" href="icon-180.png"><link rel="icon" type="image/png" href="icon-180.png">'
        u'<style>body{margin:0}[hidden]{display:none!important}</style></head><body>\n')
io.open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8", newline="\n").write(head + body + u"\n</body></html>\n")
print("index.html", os.path.getsize(os.path.join(ROOT, "index.html")))
