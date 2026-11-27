"""Input tests in headless Chrome: phone touch, desktop keyboard + mouse, gamepads, split screen.
Usage: python3 test/play.py /tmp/out   (static server on :8377, see NOTES.md). Exits 1 if a check fails."""
import sys, time, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = "http://127.0.0.1:8377/index.html"
b = Browser(profile=SP + "/prof")
ME = "HW.App.locals[0].me"
FAILS = []
def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (("  " + str(detail)) if detail != "" else ""))
    if not ok: FAILS.append(name)
def near(a, b, tol=0.15):  # angles, wrap-safe
    import math
    d = (a - b + math.pi) % (2 * math.pi) - math.pi
    return abs(d) <= tol
def st(t): return json.loads(t.eval("(()=>{const m=%s;return JSON.stringify(m?{x:m.x|0,y:m.y|0,ang:+m.ang.toFixed(2),aim:+m.aim.toFixed(2),ammo:m.ammo,mass:+m.mass.toFixed(1),abil:+m.abil.toFixed(1),boost:m.boosting,shield:+m.shield.toFixed(1)}:null)})()" % ME))
def J(t, js): return json.loads(t.eval("JSON.stringify(%s)" % js))
def rd(t, i=0): return J(t, "HW.Input.read(HW.App.locals[%d].dev,HW.App.locals[%d].view)" % (i, i))  # one input frame, read directly
def T(t): return J(t, "(()=>{const T=HW.Input.touch;return {move:T.move,aim:T.aim,boost:T.boost,abil:T.abil,held:T.abilHeld,pause:T.pause,tap:T.tap}})()")
def fresh(t):  # the profile's HTTP cache can serve a script edited seconds ago from its old copy
    t.call("Network.enable"); t.call("Network.setCacheDisabled", {"cacheDisabled": True}); return t
# count shots at the source (ammo also changes when the worm happens to eat a crate)
def spy(t): t.eval("(()=>{const s=HW.App.sim,f=s.fire;window.__shots=[];s.fire=function(w){__shots.push(+w.aim.toFixed(2));return f.call(this,w)}})()")
def nshots(t): return t.eval("__shots.length")
# Edge-triggered outputs (ability / tap / pause) are consumed by whichever read comes first, the game's own
# frame or a direct read from here, so they are counted inside Input.read instead of sampled.
def spyread(t): t.eval("(()=>{const I=HW.Input,r=I.read;window.__e=[0,1].map(()=>({abil:0,tap:0,pause:0}));I.read=function(d,v){const o=r(d,v),i=HW.App.locals.findIndex(l=>l.dev===d);if(i>=0)for(const k in __e[i])if(o[k])__e[i][k]++;return o}})()")
def edges(t): return J(t, "__e")
# put the local worms mid-arena so walls cannot bend a steering check
def ctr(t): t.eval("HW.App.locals.forEach((l,i)=>{const w=l.me;if(!w)return;w.x=800+i*300;w.y=950;for(const p of w.pts){p.x=w.x;p.y=w.y}})")
PAD = "({connected:true,index:%d,id:'%s',mapping:'%s',axes:%s,buttons:Array.from({length:%d},()=>({pressed:false,value:0}))})"

# Geometry of the touch layout against what render.js draws (minimap top left, leaderboard top right of each
# view) and against the safe area. Returns a list of problems; sizes are checked in CSS px.
LAYOUT_JS = """(()=>{const R=HW.Render,L=HW.Input.touch.layout,s=R.scale,W=R.W,H=R.H,n=HW.App.locals.length,ins=HW.Input.safe||{l:0,r:0,t:0,b:0},bad=[];
const hw=Math.floor(W/2),small=(n>1?hw:W)<420,ms=small?50:60,rects=[];
for(let i=0;i<n;i++){const vx=n>1?i*(W-hw):0,vw=n>1?hw:W;rects.push(['leaderboard'+i,vx+vw-96,4,vx+vw-4,4+(small?3:5)*9+3],['minimap'+i,vx+4,4,vx+6+ms,6+ms]);if(n>1)rects.push(['label'+i,vx+ms+10,5,vx+ms+24,13]);}
const cr=(c,r,q)=>{const dx=Math.max(q[1]-c.x,0,c.x-q[3]),dy=Math.max(q[2]-c.y,0,c.y-q[4]);return dx*dx+dy*dy<r*r};
const d=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y),P=L.pause,pr=[0,P.x-P.pad,0,P.x+P.w+P.pad,P.y+P.h+P.pad];
for(const [k,c] of [['abil',L.abil],['boost',L.boost]]){
  if(c.r*2*s<44)bad.push(k+' drawn smaller than 44 css px: '+c.r*2*s);
  if(c.hit<c.r)bad.push(k+' hit zone smaller than the button');
  for(const q of rects)if(cr(c,c.hit,q))bad.push(k+' overlaps '+q[0]);
  if(cr(c,c.hit,pr))bad.push(k+' overlaps pause');
  if(c.x+c.r>W-ins.r/s||c.x-c.r<ins.l/s||c.y+c.r>H-ins.b/s||c.y-c.r<ins.t/s)bad.push(k+' outside the safe area');
  if(c.x-c.hit<W/2)bad.push(k+' reaches the move half');}
if(d(L.abil,L.boost)<L.abil.hit+L.boost.hit+8/s)bad.push('ability and boost hit zones closer than 8 css px');
if(L.abil.y>=L.boost.y)bad.push('ability not above boost');
if(d(L.abil,L.aimIdle)*s<120)bad.push('ability within 120 css px of the resting aim thumb: '+d(L.abil,L.aimIdle)*s);
if(d(L.boost,L.aimIdle)<L.boost.r+L.ring)bad.push('boost overlaps the idle aim ring');
if(d(L.boost,L.aimIdle)*s>190)bad.push('boost further than 190 css px from the aim thumb: '+d(L.boost,L.aimIdle)*s);
if((P.w+2*P.pad)*s<44||(P.y+P.h+P.pad)*s<44)bad.push('pause hit zone under 44 css px');
for(const q of rects)if(pr[1]<q[3]&&pr[3]>q[1]&&pr[2]<q[4]&&pr[4]>q[2])bad.push('pause overlaps '+q[0]);
if(P.x<ins.l/s||P.x+P.w>W/2)bad.push('pause outside the safe area / left half');
if(!(L.moveIdle.x<W/2&&L.aimIdle.x>W/2))bad.push('idle sticks on the wrong halves');
if(L.moveIdle.x-L.ring<ins.l/s||L.aimIdle.x+L.ring>W-ins.r/s||L.aimIdle.y+L.ring>H-ins.b/s)bad.push('idle stick outside the safe area');
if(L.stickR*s<40||L.stickR*s>60)bad.push('stick travel not 40-60 css px: '+L.stickR*s);
return bad})()"""

try:
    # ================= touch on a phone =================
    t = fresh(b.tab()); t.device(844, 390, 3, True, True); t.goto(URL, 1.5)
    t.eval("HW.CFG.WORMS=1")  # no bots: input checks must not be interrupted by deaths
    print("dims", t.eval("HW.Render.W+'x'+HW.Render.H"))
    t.shot(SP + "/p_title.png")
    sc = lambda: t.eval("HW.Render.canvas.getBoundingClientRect().width/HW.Render.W")
    def L(): return J(t, "HW.Input.touch.layout")
    def tap_btn(js):
        r = json.loads(t.eval("(()=>{const b=%s;const r=b.getBoundingClientRect();return JSON.stringify([r.left+r.width/2,r.top+r.height/2])})()" % js))
        t.touch("touchStart", [(0, r[0], r[1])]); t.touch("touchEnd", []); t.pump(0.4)
    def up(): t.touch("touchEnd", []); t.pump(0.1)
    # tap PLAY with a real touch -> select -> PLAY!
    tap_btn("document.querySelectorAll('#ui button')[0]"); check("touch: PLAY tap opens select", t.eval("HW.App.screen") == "select")
    t.shot(SP + "/p_select.png")
    tap_btn("document.querySelector('#ui button.go')"); check("touch: PLAY! tap starts the game", t.eval("HW.App.mode") == "play" and t.eval("HW.App.screen") == "")
    t.pump(1.0); s0 = st(t); print("spawn", s0)
    # taps on menu buttons make the browser invent mouse events; they must not turn mouse aim on
    m = J(t, "HW.Input.mouse"); r0 = rd(t)
    check("touch: menu taps leave mouse aim off", not m["active"] and r0["ax"] == 0 and r0["ay"] == 0, m)

    # ---- move stick: drag left thumb up-left
    ctr(t); t.touch("touchStart", [(1, 150, 250)]); t.touch("touchMove", [(1, 110, 210)]); t.pump(1.2); s1 = st(t)
    check("touch: move stick steers up-left", near(s1["ang"], -2.36), s1["ang"])
    # ---- aim stick: right thumb drag right -> fires right, and the very first shot already goes there
    spy(t); t.eval("%s.shield=0;%s.cd=0" % (ME, ME))
    t.touch("touchStart", [(1, 110, 210), (2, 650, 280)]); t.touch("touchMove", [(1, 110, 210), (2, 700, 280)]); t.pump(1.5); s2 = st(t)
    shots = J(t, "__shots"); print("after aim right", s2, "shots", shots)
    check("touch: aim stick aims right and fires", near(s2["aim"], 0) and len(shots) > 0, s2)
    check("touch: first shot of a drag goes where the thumb points (not along the heading)", len(shots) > 0 and near(shots[0], 0), shots)
    t.shot(SP + "/p_touch.png")
    # ---- thumb back through the middle: keeps the last aim instead of snapping to auto-aim
    a = T(t)["aim"]; t.touch("touchMove", [(1, 110, 210), (2, a["ox"] * sc(), a["oy"] * sc())]); t.pump(0.1); r = rd(t)
    check("touch: aim held at centre keeps the last direction", r["fire"] and not r["auto"] and near(r["ax"], 1, 0.05) and abs(r["ay"]) < 0.05, r)
    up()
    check("touch: sticks released on touchend", not T(t)["move"]["on"] and not T(t)["aim"]["on"])

    # ---- still thumb on the aim side: short grace, then auto-aim fire; quick tap = exactly one shot
    t.eval("(()=>{const I=HW.Input,r=I.read;window.__read=r;window.__log=[];I.read=function(d,v){const o=r(d,v);if(d.touch&&I.touch.aim.on)__log.push([performance.now()-I.touch.aim.t0,o.fire,o.auto]);return o}})()")
    t.touch("touchStart", [(2, 650, 280)]); t.pump(0.5); up(); log = J(t, "__log"); t.eval("HW.Input.read=__read")
    early = [e for e in log if e[0] < 90]; late = [e for e in log if e[0] > 170]
    check("touch: no shot in the first moments of a still aim touch", len(early) > 0 and all(not e[1] for e in early), early[:3])
    check("touch: a held still thumb auto-fires after the grace", len(late) > 0 and all(e[1] and e[2] for e in late), late[:3])
    t.eval("%s.ammo=8" % ME); t.pump(1.3); t.eval("%s.cd=0" % ME); n0 = nshots(t)
    t.touch("touchStart", [(2, 650, 280)]); t.touch("touchEnd", []); t.pump(0.4)
    check("touch: quick tap on the aim side fires one shot", nshots(t) == n0 + 1, (n0, nshots(t)))

    # ---- a hand gripping the right edge of the glass is not an aim thumb: it must never shoot
    t.pump(1.0); n0 = nshots(t); t.touch("touchStart", [(1, 840, 330)]); t.pump(0.5); r = rd(t); up()
    check("touch: a still contact on the screen edge does not fire", not r["fire"] and nshots(t) == n0, r)
    # ---- exact screen midline belongs to the aim side, one px left of it to the move side
    t.touch("touchStart", [(1, 422, 200)]); x = T(t); up(); check("touch: midline touch -> aim stick", x["aim"]["on"] and not x["move"]["on"])
    t.touch("touchStart", [(1, 421, 200)]); x = T(t); up(); check("touch: just left of midline -> move stick", x["move"]["on"] and not x["aim"]["on"])

    # ---- second finger on the same half
    t.touch("touchStart", [(1, 150, 250)]); t.touch("touchMove", [(1, 110, 210)])                 # working thumb
    t.touch("touchStart", [(1, 110, 210), (3, 250, 300)]); x = T(t)["move"]
    check("touch: second finger does not steal a working stick", x["id"] == 1 and abs(x["dx"]) > 0.3, x)
    t.touch("touchEnd", [(1, 110, 210)]); x = T(t)["move"]                                         # thumb lifts, finger 3 stays
    check("touch: remaining finger takes the stick over", x["on"] and x["id"] == 3 and x["dx"] == 0, x)
    t.touch("touchMove", [(3, 310, 300)]); check("touch: taken-over stick works", T(t)["move"]["dx"] > 0.9); up()
    t.touch("touchStart", [(1, 6, 330)])                                                           # palm resting on the edge
    t.touch("touchStart", [(1, 6, 330), (3, 160, 260)]); t.touch("touchMove", [(1, 6, 330), (3, 200, 260)]); x = T(t)["move"]
    check("touch: thumb takes the stick from a resting palm", x["id"] == 3 and x["dx"] > 0.8, x)
    t.touch("touchStart", [(1, 6, 330), (3, 200, 260), (4, 300, 100)]); check("touch: third finger ignored", T(t)["move"]["id"] == 3); up()

    # ---- a touchend that never arrives must not leave a stuck stick
    t.touch("touchStart", [(1, 150, 250)]); t.touch("touchMove", [(1, 110, 210)])
    t.eval("window.addEventListener('touchend',e=>e.stopPropagation(),{capture:true,once:true})"); t.touch("touchEnd", [])
    check("(setup) touchend was swallowed", T(t)["move"]["on"])
    t.touch("touchStart", [(2, 650, 280)]); x = T(t)
    check("touch: lost touchend heals on the next touch", not x["move"]["on"] and x["aim"]["on"], x["move"])
    t.touch("touchCancel", []); t.pump(0.1); check("touch: touchcancel releases sticks", not T(t)["aim"]["on"])

    # ---- boost button: hold, slide off (still boosting, not aiming), release
    Lq = L(); k = sc(); t.eval("%s.mass=80" % ME)
    bx, by = Lq['boost']['x'] * k, Lq['boost']['y'] * k
    t.touch("touchStart", [(3, bx, by)]); t.pump(0.5); check("touch: boost button boosts", st(t)['boost'])
    t.touch("touchMove", [(3, bx - 120, by + 40)]); t.pump(0.2); x = T(t)
    check("touch: sliding off boost keeps boosting and does not aim", st(t)['boost'] and not x["aim"]["on"])
    up(); t.pump(0.1); check("touch: boost released", not st(t)['boost'] and not T(t)["boost"])
    # ---- ability: fires on release, on the button; sliding off turns it into an aim gesture; cancel = nothing
    ax, ay = Lq['abil']['x'] * k, Lq['abil']['y'] * k
    t.eval("%s.abil=0" % ME); t.touch("touchStart", [(4, ax, ay)]); t.pump(0.2)
    check("touch: ability not fired while the finger is still down", t.eval("HW.App.G.zones.length") == 0 and T(t)["held"])
    up(); t.pump(0.2); z = J(t, "HW.App.G.zones.map(z=>[z.k,z.r,+z.t.toFixed(1)])")
    check("touch: ability fires on release", len(z) == 1 and st(t)['abil'] > 50, z)
    t.pump(0.5); t.shot(SP + "/p_fart.png")
    t.eval("%s.abil=0;%s.ammo=8" % (ME, ME)); t.touch("touchStart", [(4, ax, ay)]); t.touch("touchMove", [(4, ax - 70, ay + 50)]); t.pump(0.2); x = T(t)
    check("touch: sliding off the ability button aims instead", x["aim"]["on"] and not x["held"] and near(st(t)["aim"], 2.52, 0.2), st(t)["aim"])
    up(); t.pump(0.2); check("touch: ...and does not use the ability", t.eval("HW.App.G.zones.length") == 1 and st(t)['abil'] <= 0)
    t.touch("touchStart", [(4, ax, ay)]); t.touch("touchCancel", []); t.pump(0.2)
    check("touch: cancelled ability press does nothing", t.eval("HW.App.G.zones.length") == 1)
    t.eval("%s.abil=30" % ME)

    # ---- pause button, and a thumb that stays down through pause / resume
    t.touch("touchStart", [(1, 150, 250)]); t.touch("touchMove", [(1, 110, 210)])
    px_, py_ = (Lq['pause']['x'] + Lq['pause']['w'] / 2) * k, (Lq['pause']['y'] + Lq['pause']['h'] / 2) * k
    t.touch("touchStart", [(1, 110, 210), (5, px_, py_)]); t.pump(0.4)
    check("touch: pause button pauses", t.eval("HW.App.paused") is True and t.eval("HW.App.screen") == "pause"); t.shot(SP + "/p_pause.png")
    t.touch("touchEnd", [(5, px_, py_)]); x = T(t); check("touch: sticks cleared by pause", not x["move"]["on"] and not x["tap"] and not x["pause"])
    t.eval("HW.App.setPause(false)"); t.pump(0.2)
    t.touch("touchMove", [(1, 150, 210)]); t.touch("touchMove", [(1, 200, 210)]); x = T(t)["move"]
    check("touch: thumb held through pause works again after resume", x["on"] and x["dx"] > 0.9, x); up()
    t.eval("HW.App.setPause(true)"); t.pump(0.2); tap_btn("document.querySelector('#ui button.go')"); x = T(t)
    check("touch: RESUME tap resumes without ghost input", t.eval("HW.App.paused") is False and not x["tap"] and not x["aim"]["on"] and not J(t, "HW.Input.mouse")["active"])

    # ---- canvas re-scaled under a held thumb (rotation / fullscreen): the stick must stay under the thumb or let go
    t.touch("touchStart", [(1, 150, 250)]); t.touch("touchMove", [(1, 150, 200)])
    t.device(800, 360, 3, True, True); t.pump(0.5); x = T(t)["move"]; k2 = sc()
    check("touch: stick survives a canvas re-scale", (not x["on"]) or (abs(x["ox"] * k2 - 150) < 3 and abs(x["oy"] * k2 - (200 + 46)) < 6), (x, k2))
    up(); t.device(844, 390, 3, True, True); t.pump(0.5)

    # ---- hazards: put veggie + mushroom on head
    t.eval("(()=>{const m=%s,s=HW.App.sim;m.shield=0;s.addItem('v',0,m.x,m.y,0);})()" % ME); t.pump(0.4); t.shot(SP + "/p_veg.png"); check("veggie slows", t.eval("%s.slow" % ME) > 0)
    t.eval("(()=>{const m=%s,s=HW.App.sim;s.addItem('m',0,m.x,m.y,0);})()" % ME); t.pump(1.2); t.shot(SP + "/p_trip.png"); check("mushroom trips", t.eval("%s.trip" % ME) > 0)

    # ---- a worm with no ability has no ability button: that spot is plain aim area
    t.eval("HW.App.quit();HW.App.startLocal([4])"); t.pump(0.5); Lq = L(); k = sc()
    t.touch("touchStart", [(4, Lq['abil']['x'] * k, Lq['abil']['y'] * k)]); x = T(t); up()
    check("touch: no ability button for a worm without an ability", x["aim"]["on"] and not x["held"])
    # ---- 2 players on a phone: P1 touch, P2 controller
    t.eval("window.__pad=" + PAD % (0, "fake", "standard", "[0,0,0,0]", 17) + ";navigator.getGamepads=()=>[window.__pad];HW.App.quit();HW.App.startLocal([0,2]);")
    t.pump(0.6); t.touch("touchStart", [(1, 150, 250)]); t.touch("touchMove", [(1, 110, 210)]); t.pump(0.3)
    t.eval("__pad.axes[0]=1"); t.pump(0.5)
    check("2P phone: P2's controller does not hide P1's touch controls", t.eval("HW.Input.lastKind") == "touch" and t.eval("HW.App.locals[1].dev.kind") == "pad")
    r1, r2 = rd(t, 0), rd(t, 1)
    check("2P phone: touch drives P1 only, pad drives P2 only", r1["mx"] < -0.5 and r1["my"] < -0.5 and r2["mx"] == 1 and r2["my"] == 0, (r1, r2))
    t.shot(SP + "/p_2p.png"); up(); t.eval("__pad.axes[0]=0;HW.App.quit()"); t.pump(0.2)

    # ---- layout geometry on real phone sizes, with and without notch / home-indicator insets, 1P and 2P
    for (w, h, d) in [(667, 375, 2), (667, 320, 2), (736, 414, 3), (812, 375, 3), (844, 390, 3), (896, 414, 2), (915, 412, 2.625), (932, 430, 3)]:
        t.device(w, h, d, True, True); t.pump(0.3)
        for n in ("[0]", "[0,2]"):
            t.eval("HW.App.startLocal(%s)" % n); t.pump(0.25)
            for safe in ("null", "{l:47,r:47,t:0,b:21}", "{l:59,r:59,t:0,b:21}", "{l:0,r:48,t:0,b:0}"):
                t.eval("HW.Input.safe=%s;HW.Input.layout()" % safe); bad = J(t, LAYOUT_JS)
                if bad: check("layout %dx%d %s safe=%s" % (w, h, "2P" if "," in n else "1P", safe), False, bad)
            t.eval("HW.Input.safe=null;HW.App.quit()")
    check("layout: all phone sizes checked", True)
    # real env(safe-area-inset-*) values reach the layout (Chrome can emulate them)
    try:
        t.device(844, 390, 3, True, True); t.pump(0.3); x0 = L()["boost"]["x"]
        t.call("Emulation.setSafeAreaInsetsOverride", {"insets": {"left": 59, "right": 59, "bottom": 21, "top": 0}}); t.eval("HW.Input.layout()"); x1 = L()["boost"]["x"]
        t.call("Emulation.setSafeAreaInsetsOverride", {"insets": {}})
        gap = (t.eval("HW.Render.W") - x1 - L()["boost"]["r"]) * sc()
        check("layout: env(safe-area-inset-right) pushes boost clear of the notch", x1 < x0 and 59 <= gap <= 72, (x0, x1, gap))
    except Exception as e: print("skip  safe-area emulation not available:", str(e)[:80])
    check("touch: no page errors", not t.errors, t.errors)

    # ================= keyboard + mouse on desktop =================
    k = fresh(b.tab()); k.device(1280, 720, 1, False, False); k.goto(URL, 1.2); k.eval("HW.CFG.WORMS=1"); print("desktop dims", k.eval("HW.Render.W+'x'+HW.Render.H"))
    k.mouse("mouseMoved", 700, 500)                      # cursor parked where a menu button was clicked
    spyread(k); k.eval("HW.App.startLocal([2])"); k.pump(0.5); a0 = st(k); spy(k)
    ctr(k); k.key("down", "KeyS", "s", 83); k.pump(1.0); a1 = st(k); k.key("up", "KeyS", "s", 83); check("kb: S steers down", near(a1['ang'], 1.57), (a0['ang'], a1['ang']))
    k.mouse("mouseMoved", 704, 503); k.key("down", "Space", " ", 32); k.pump(0.1); r = rd(k); k.key("up", "Space", " ", 32)
    check("kb: Space with a parked cursor gets aim assist (mouse aim off)", r["fire"] and r["auto"] and r["ax"] == 0 and r["ay"] == 0, r)
    k.pump(0.3); n0 = nshots(k)
    k.mouse("mouseMoved", 1000, 360); k.mouse("mousePressed", 1000, 360, "left", 1); k.pump(0.6); a2 = st(k); k.mouse("mouseReleased", 1000, 360, "left", 0)
    check("mouse: aims right and fires", near(a2['aim'], 0, 0.3) and nshots(k) > n0, (a2['aim'], n0, nshots(k)))
    k.pump(0.5); k.eval("%s.cd=0" % ME); n0 = nshots(k)
    k.mouse("mousePressed", 1000, 360, "left", 1); k.mouse("mouseReleased", 1000, 360, "left", 0); k.pump(0.3)
    check("mouse: click shorter than a frame (trackpad tap) still fires", nshots(k) == n0 + 1, (n0, nshots(k)))
    k.mouse("mousePressed", 1000, 360, "left", 1); k.mouse("mouseMoved", 1010, 360, "left", 1); r1 = rd(k); k.mouse("mouseMoved", 1020, 360); r2 = rd(k)
    check("mouse: a mouseup that was never delivered does not leave the gun firing", r1["fire"] and not r2["fire"], (r1["fire"], r2["fire"]))
    k.eval("%s.mass=80" % ME); k.mouse("mousePressed", 1000, 360, "right", 2); r1 = rd(k); k.mouse("mouseReleased", 1000, 360, "right", 0); r2 = rd(k)
    check("mouse: right button boosts while held", r1["boost"] and not r2["boost"])
    k.eval("%s.abil=0" % ME); k.key("down", "KeyE", "e", 69); k.key("up", "KeyE", "e", 69); k.pump(0.3)
    check("kb: E tap shorter than a frame uses the ability once", k.eval("HW.App.G.zones.length") == 1)
    k.eval("%s.mass=80" % ME); k.key("down", "ShiftLeft", "Shift", 16); k.pump(0.3); bo = st(k)['boost']; k.key("up", "ShiftLeft", "Shift", 16); check("kb: Shift boosts", bo)
    k.key("down", "Escape", "Escape", 27); k.pump(0.3); p1 = k.eval("HW.App.paused")
    k.call("Input.dispatchKeyEvent", {"type": "keyDown", "code": "Escape", "key": "Escape", "windowsVirtualKeyCode": 27, "autoRepeat": True}); k.pump(0.3); p2 = k.eval("HW.App.paused")
    k.key("up", "Escape", "Escape", 27); check("kb: Esc pauses, and holding it does not un-pause", p1 is True and p2 is True, (p1, p2))
    k.key("down", "KeyE", "e", 69); k.key("up", "KeyE", "e", 69); k.eval("HW.App.setPause(false)"); k.pump(0.3)
    check("kb: keys pressed in the pause menu do nothing after resume", k.eval("HW.App.G.zones.length") == 1)
    k.key("down", "KeyD", "d", 68); k.eval("window.dispatchEvent(new Event('blur'))"); r = rd(k); k.key("up", "KeyD", "d", 68)
    check("kb: window blur (alt-tab) releases held keys", r["mx"] == 0, r)
    k.key("down", "KeyD", "d", 68); k.call("Input.dispatchKeyEvent", {"type": "keyDown", "code": "MetaLeft", "key": "Meta", "windowsVirtualKeyCode": 91}); r = rd(k)
    k.call("Input.dispatchKeyEvent", {"type": "keyUp", "code": "MetaLeft", "key": "Meta", "windowsVirtualKeyCode": 91}); k.key("up", "KeyD", "d", 68)
    check("kb: Cmd releases held keys (macOS sends no keyup under Cmd)", r["mx"] == 0, r)
    k.pump(0.5); k.shot(SP + "/k_play.png")

    # ================= gamepad quirks (single player, any pad) =================
    def setpads(js): k.eval("window.__pads=%s;navigator.getGamepads=()=>window.__pads" % js)
    setpads("[" + PAD % (0, "raw", "", "[0,0,-1,0,0,-1]", 12) + "]"); k.pump(0.2); r = rd(k)
    check("pad: trigger axis idling at -1 on an unmapped pad does not aim / fire", not r["fire"] and r["ax"] == 0, r)
    setpads("[" + PAD % (0, "std", "standard", "[0,0,0,0]", 17) + "]"); rd(k)
    k.eval("__pads[0].axes=[1,0.2,0,0]"); r = rd(k); check("pad: round dead zone keeps small off-axis tilt", r["mx"] == 1 and r["my"] == 0.2, r)
    k.eval("__pads[0].axes=[0.2,0.1,0.25,-0.25]"); r = rd(k); check("pad: stick drift inside the dead zones is ignored", r["mx"] == 0 and r["my"] == 0 and not r["fire"], r)
    k.eval("__pads[0].axes=[0,0,0,0.9]"); r = rd(k); check("pad: right stick aims and fires", r["fire"] and not r["auto"] and r["ay"] == 0.9, r)
    k.eval("__pads[0].axes=[0,0,0,0]"); k.pump(0.1)
    k.mouse("mouseMoved", 900, 300); k.mouse("mouseMoved", 1000, 360); ma = J(k, "HW.Input.mouse")["active"]   # cursor left aiming somewhere
    k.eval("__pads[0].buttons[7]={pressed:false,value:0.8}"); r = rd(k)
    check("pad: analog trigger fires with aim assist, even with a cursor lying on the screen", ma and r["fire"] and r["auto"] and r["ax"] == 0 and r["ay"] == 0, (ma, r))
    e0 = edges(k)[0]["abil"]; k.eval("__pads[0].buttons[7]={pressed:false,value:0};__pads[0].buttons[2]={pressed:true,value:1}"); k.pump(0.4)
    check("pad: ability is edge triggered (once per press, however long it is held)", edges(k)[0]["abil"] == e0 + 1, (e0, edges(k)[0]["abil"])); k.eval("__pads[0].buttons[2]={pressed:false,value:0}")
    k.eval("__pads[0].buttons[9]={pressed:true,value:1}"); k.pump(0.5); p1 = k.eval("HW.App.paused"); k.eval("__pads[0].buttons[9]={pressed:false,value:0}"); k.pump(0.2)
    k.eval("__pads[0].buttons[9]={pressed:true,value:1}"); k.pump(0.5); p2 = k.eval("HW.App.paused"); k.eval("__pads[0].buttons[9]={pressed:false,value:0}"); k.pump(0.2)
    check("pad: Start pauses once, Start again resumes once (held button does not flicker)", p1 is True and p2 is False, (p1, p2))
    setpads("[null," + PAD % (1, "two-axis", "", "[0,-1]", 6) + "]"); rd(k); k.eval("__pads[1].axes=[0,0]"); rd(k); k.eval("__pads[1].axes=[0,-1]"); r = rd(k)
    check("pad: missing right-stick axes and a null slot are fine", r["my"] == -1 and not r["fire"], r)
    setpads("[" + PAD % (0, "hat", "", "[0,0,0,0,0,0,0,0,0,1.2857]", 12) + "]"); rd(k); k.eval("__pads[0].axes[9]=-1"); r1 = rd(k); k.eval("__pads[0].axes[9]=-0.42857"); r2 = rd(k); k.eval("__pads[0].axes[9]=1.2857"); r3 = rd(k)
    check("pad: hat-switch d-pad on an unmapped pad", (r1["mx"], r1["my"]) == (0, -1) and (r2["mx"], r2["my"]) == (1, 0) and (r3["mx"], r3["my"]) == (0, 0), (r1, r2, r3))
    setpads("[" + PAD % (0, "std", "standard", "[0,0,0,0]", 17) + "]"); k.pump(0.2); k.eval("__pads[0].axes[0]=1"); k.pump(0.3)
    k.eval("__pads=[null];(()=>{const e=new Event('gamepaddisconnected');e.gamepad={index:0};window.dispatchEvent(e)})()"); k.pump(0.3)
    check("pad: a controller in use that disconnects pauses the game", k.eval("HW.App.paused") is True); k.eval("HW.App.setPause(false)")

    # ================= 2 players: P1 keyboard, P2 gamepad =================
    setpads("[" + PAD % (0, "fake", "standard", "[0,0,0,0]", 17) + "]"); k.eval("window.__pad=__pads[0];HW.App.quit();HW.App.startLocal([0,4]);")
    k.pump(0.8); devs = J(k, "HW.App.locals.map(l=>[l.dev.kb,l.dev.pad,l.view.x,l.view.w,l.dev.hasPad])"); print("2P devs:", devs)
    check("2P: one pad goes to P2", devs[0][4] is False and devs[1][4] is True)
    P2 = "HW.App.locals[1].me"
    ctr(k); k.eval("__pad.axes[0]=-1;__pad.axes[1]=0"); k.pump(1.5); check("2P: pad left stick steers P2", near(k.eval("%s.ang" % P2), 3.14), k.eval("%s.ang" % P2))
    spy(k); k.eval("__pad.axes[0]=0;__pad.axes[2]=0;__pad.axes[3]=1;%s.shield=0;%s.ammo=4" % (P2, P2)); k.pump(1.8)
    check("2P: pad right stick aims and fires for P2", near(k.eval("%s.aim" % P2), 1.57) and nshots(k) > 0 and all(near(a, 1.57) for a in J(k, "__shots")), J(k, "__shots"))
    k.eval("__pad.axes[2]=0;__pad.axes[3]=0;%s.mass=90;__pad.buttons[0]={pressed:true,value:1}" % P2); k.pump(0.3); check("2P: pad A boosts P2", k.eval("%s.boosting" % P2)); k.eval("__pad.buttons[0]={pressed:false,value:0}")
    ctr(k); k.key("down", "ArrowUp", "ArrowUp", 38); k.key("down", "KeyD", "d", 68); k.pump(0.1); r1, r2 = rd(k, 0), rd(k, 1); k.pump(1.6)
    check("2P: arrows drive P2 only, WASD drives P1 only", (r1["mx"], r1["my"]) == (1, 0) and (r2["mx"], r2["my"]) == (0, -1), (r1, r2))
    check("2P: worms follow their own keys", near(k.eval("%s.ang" % P2), -1.57) and near(k.eval("HW.App.locals[0].me.ang"), 0), (k.eval("%s.ang" % P2), k.eval("HW.App.locals[0].me.ang")))
    k.key("up", "ArrowUp", "ArrowUp", 38); k.key("up", "KeyD", "d", 68)
    k.key("down", "Enter", "Enter", 13); k.key("down", "Space", " ", 32); r1, r2 = rd(k, 0), rd(k, 1); k.key("up", "Enter", "Enter", 13); k.key("up", "Space", " ", 32)
    check("2P: Space fires for P1, Enter for P2", r1["fire"] and r2["fire"])
    e0 = edges(k); k.key("down", "Period", ".", 190); k.pump(0.3); k.key("up", "Period", ".", 190); e1 = edges(k)
    check("2P: Period is P2's ability only, once", e1[1]["abil"] == e0[1]["abil"] + 1 and e1[0]["abil"] == e0[0]["abil"], (e0, e1))
    k.shot(SP + "/k_2p.png")
    # a second pad arrives: P1 takes the new one, P2 keeps theirs
    k.eval("__pads.push(" + PAD % (1, "fake1", "standard", "[0,0,0,0]", 17) + ")"); k.pump(0.3)
    seats = J(k, "HW.App.locals.map(l=>l.dev.prev.pad)"); check("2P: second pad goes to P1, P2 keeps the first", seats == [1, 0], seats)
    # P2's pad dies: P1 keeps their own pad, P2 falls back to the arrow keys (the pad must not jump to P2's worm)
    k.eval("__pads[1].axes[1]=-1;__pads[0]=null"); k.pump(0.2); r1, r2 = rd(k, 0), rd(k, 1)
    check("2P: when P2's pad disconnects P1 keeps their pad", r1["my"] == -1 and r2["my"] == 0 and k.eval("HW.App.locals[1].dev.hasPad") is False, (r1, r2))
    k.eval("__pads[1].axes[1]=0;__pads[0]=" + PAD % (0, "fake", "standard", "[0,1,0,0]", 17)); k.pump(0.2); r1, r2 = rd(k, 0), rd(k, 1)
    check("2P: P2's pad comes back to P2", r1["my"] == 0 and r2["my"] == 1, (r1, r2))
    # P1's pad dies: P2 keeps theirs
    k.eval("__pads[0].axes[1]=-1;__pads[1]=null"); k.pump(0.2); r1, r2 = rd(k, 0), rd(k, 1)
    check("2P: when P1's pad disconnects P2 keeps their pad", r1["my"] == 0 and r2["my"] == -1, (r1, r2))

    # ================= gamepad menu navigation =================
    setpads("[" + PAD % (0, "fake", "standard", "[0,0,0,0]", 17) + "]"); k.eval("window.__pad=__pads[0];HW.App.quit();HW.App.sel.picks[0]=0"); k.pump(0.3)
    k.eval("__pad.buttons[0]={pressed:true,value:1}"); k.pump(0.2); k.eval("__pad.buttons[0]={pressed:false,value:0}"); k.pump(0.3); check("menu: pad A on title opens select", k.eval("HW.App.screen") == "select")
    k.eval("__pad.buttons[15]={pressed:true,value:1}"); k.pump(0.15); k.eval("__pad.buttons[15]={pressed:false,value:0}"); k.pump(0.15)
    k.eval("__pad.buttons[0]={pressed:true,value:1}"); k.pump(0.2); k.eval("__pad.buttons[0]={pressed:false,value:0}"); k.pump(0.3)
    check("menu: d-pad right + A picks the next worm", k.eval("HW.App.sel.picks[0]") == 1 and k.eval("HW.App.screen") == "select", k.eval("HW.App.sel.picks[0]"))
    k.eval("__pad.buttons[1]={pressed:true,value:1}"); k.pump(0.2); k.eval("__pad.buttons[1]={pressed:false,value:0}"); k.pump(0.2); check("menu: pad B goes back", k.eval("HW.App.screen") == "title")
    check("desktop: no page errors", not k.errors, k.errors)
finally:
    b.close()
print("\n%d check(s) failed" % len(FAILS) if FAILS else "\nall checks passed")
for f in FAILS: print("  FAIL", f)
sys.exit(1 if FAILS else 0)
