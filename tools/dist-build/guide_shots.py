# 설명서용 화면 캡처: 뷰어 페이지에 설명 딱지를 얹어 헤드리스 크롬으로 찍는다
import io, base64, os, subprocess, sys, json
SP = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(os.path.dirname(SP))
CH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
tpl = io.open(os.path.join(V, "viewer.src.html"), encoding="utf-8").read()
ships = io.open(os.path.join(V, "ships.js"), encoding="utf-8").read()
name = "ASC609_KJS2_2612E_KRPUS_HRON.asc"
asc = open(os.path.join(SP, name), "rb").read()
t = tpl.replace('<script src="ships.js"></script>', '<script>' + ships + '</script>')
t = t.replace('/*__ASC_DATA__*/', "window.__ASC__={name:'%s',b64:'%s'};" % (name, base64.b64encode(asc).decode()))
head = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0}[hidden]{display:none!important}</style></head><body>'

CO = r'''
function CO(list){
  function draw(){
    [].forEach.call(document.querySelectorAll(".coX"),function(e){e.remove()});
    var ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");svg.setAttribute("class","coX");
    svg.setAttribute("style","position:fixed;inset:0;width:100vw;height:100vh;z-index:90;pointer-events:none");document.body.appendChild(svg);
    list.forEach(function(c){
      var lb=document.createElement("div");lb.className="coX";lb.innerHTML=c[1];
      var base="position:fixed;z-index:92;background:#fff7c2;color:#000;border:2px solid #e00000;border-radius:5px;padding:4px 8px;font:700 13px/1.35 'Malgun Gothic',sans-serif;white-space:nowrap;box-shadow:2px 2px 0 rgba(0,0,0,.25);";
      if(c[0]==="@bottom"){lb.setAttribute("style",base+"left:"+c[2]+"px;bottom:"+c[3]+"px");document.body.appendChild(lb);return}
      var el=typeof c[0]==="string"?document.querySelector(c[0]):c[0]; if(!el)return;
      var r=el.getBoundingClientRect(),p=c[4]==null?3:c[4];
      var B={l:r.left-p,t:r.top-p,r:r.right+p,b:r.bottom+p};
      var bx=document.createElement("div");bx.className="coX";
      bx.setAttribute("style","position:fixed;z-index:91;border:2.5px solid #e00000;border-radius:4px;pointer-events:none;left:"+B.l+"px;top:"+B.t+"px;width:"+(B.r-B.l-5)+"px;height:"+(B.b-B.t-5)+"px");
      document.body.appendChild(bx);
      lb.setAttribute("style",base+"left:"+(r.left+c[2])+"px;top:"+(r.top+c[3])+"px");
      document.body.appendChild(lb);
      var L=lb.getBoundingClientRect(),cx=L.left+L.width/2,cy=L.top+L.height/2;
      var tx=Math.max(B.l,Math.min(B.r,cx)),ty=Math.max(B.t,Math.min(B.b,cy));
      var ln=document.createElementNS(ns,"line");ln.setAttribute("x1",cx);ln.setAttribute("y1",cy);ln.setAttribute("x2",tx);ln.setAttribute("y2",ty);
      ln.setAttribute("stroke","#e00000");ln.setAttribute("stroke-width","2.5");svg.appendChild(ln);
    });
  }
  draw();window.addEventListener("resize",draw);
}
'''

def shot(key, js, w, h):
    i = t.rindex("})();")
    page = head + t[:i] + CO + "setTimeout(function(){" + js + "},300);" + t[i:] + "</body></html>"
    f = os.path.join(SP, "g_%s.html" % key); io.open(f, "w", encoding="utf-8").write(page)
    png = os.path.join(SP, "g_%s.png" % key)
    if os.path.exists(png): os.remove(png)
    subprocess.run([CH, "--headless=new", "--disable-gpu", "--force-device-scale-factor=1.5", "--virtual-time-budget=4000",
                    "--window-size=%d,%d" % (w, h), "--screenshot=" + png, "file:///" + f.replace("\\", "/")], capture_output=True)
    print(key, os.path.getsize(png))

S = json.load(io.open(os.path.join(SP, "guide_shots.json"), encoding="utf-8"))
for k in (sys.argv[1:] or S.keys()):
    shot(k, S[k]["js"], S[k]["w"], S[k]["h"])
