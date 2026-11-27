"""Input tests in headless Chrome: phone touch (solo, and 2 players sharing one phone with a touch control set
in each half), touch layout geometry, desktop keyboard + mouse, gamepads, split screen.
Usage: python3 test/play.py /tmp/out   (static server on :8377 or HW_URL, see NOTES.md). Exits 1 if a check fails.
Screenshots to look at land in the output folder: p_1p / p_2p* (844x390), p_1p_small / p_2p_small* (667x375)."""
import sys, time, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html")
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
def T(t, i=0): return J(t, "(()=>{const T=HW.Input.tpads[%d];return {move:T.move,aim:T.aim,boost:T.boost,abil:T.abil,held:T.abilHeld,pause:T.pause,tap:T.tap}})()" % i)  # touch pad i (0 = solo / P1, 1 = P2)
def fresh(t):  # the profile's HTTP cache can serve a script edited seconds ago from its old copy
    t.call("Network.enable"); t.call("Network.setCacheDisabled", {"cacheDisabled": True}); return t
# count shots at the source (ammo also changes when the worm happens to eat a crate)
def spy(t): t.eval("(()=>{const s=HW.App.sim,f=s.fire;window.__shots=[];window.__shotw=[];s.fire=function(w){__shots.push(+w.aim.toFixed(2));__shotw.push(w.id);return f.call(this,w)}})()")
def nshots(t): return t.eval("__shots.length")
# Edge-triggered outputs (ability / tap / pause) are consumed by whichever read comes first, the game's own
# frame or a direct read from here, so they are counted inside Input.read instead of sampled.
def spyread(t): t.eval("(()=>{const I=HW.Input,r=I.read;window.__e=[0,1].map(()=>({abil:0,tap:0,pause:0}));I.read=function(d,v){const o=r(d,v),i=HW.App.locals.findIndex(l=>l.dev===d);if(i>=0)for(const k in __e[i])if(o[k])__e[i][k]++;return o}})()")
def edges(t): return J(t, "__e")
# Put the local worms on open floor so nothing can bend a steering or aiming check. The arena is full of
# obstacles: its emptiest spots are discs about 230 px across the radius, so the spot is searched with
# HW.MAP.hit (rings of probes out to 224 px, also clear of the outer wall) instead of being hardcoded, and no
# check lets a worm travel further than that. The two players are at least 1000 px apart (out of gun range).
# Veggies and mushrooms are removed: a mushroom sways steering and aim for 10 s.
CTR = """(()=>{const M=HW.MAP,sim=HW.App.sim,ok=(x,y)=>{if(Math.min(x,y,M.W-x,M.H-y)<260)return false;
for(let r=0;r<=180;r+=45)for(let i=0;i<16;i++)if(M.hit(x+Math.cos(i*Math.PI/8)*r,y+Math.sin(i*Math.PI/8)*r,44))return false;return true};
if(!window.__spots){const o=[];for(let y=300;y<=M.H-300&&o.length<2;y+=25)for(let x=300;x<=M.W-300&&o.length<2;x+=25)if(ok(x,y)&&o.every(q=>Math.hypot(q.x-x,q.y-y)>=1000))o.push({x,y});window.__spots=o}
for(const it of Array.from(sim.S.items.values()))if(it.k==='v'||it.k==='m')sim.remItem(it);
HW.App.locals.forEach((l,i)=>{const w=l.me,q=__spots[i];if(!w||!q)return;w.x=q.x;w.y=q.y;w.slow=0;w.trip=0;for(const p of w.pts){p.x=w.x;p.y=w.y}});return __spots.length})()"""
def ctr(t):
    n = t.eval(CTR)
    if n != 2: check("(setup) two clear spots found in the arena", False, n)
PAD = "({connected:true,index:%d,id:'%s',mapping:'%s',axes:%s,buttons:Array.from({length:%d},()=>({pressed:false,value:0}))})"

# Geometry of the touch layout against what render.js draws in each view (minimap, P-label, lives and kills,
# clock, kill feed, leaderboard, bottom read-outs) and against the safe area. Every pad is checked against its
# own view rectangle: the whole canvas in solo, one half each in split screen. Returns a list of problems;
# sizes are checked in CSS px.
LAYOUT_JS = """(()=>{const R=HW.Render,I=HW.Input,s=R.scale,W=R.W,H=R.H,n=Math.max(1,HW.App.locals.length),ins=I.safe||{l:0,r:0,t:0,b:0},bad=[];
const hw=Math.floor(W/2),c=v=>Math.round(v/s),sa={l:c(ins.l),r:c(ins.r),t:c(ins.t),b:c(ins.b)};
const cr=(c,r,q)=>{const dx=Math.max(q[1]-c.x,0,c.x-q[3]),dy=Math.max(q[2]-c.y,0,c.y-q[4]);return dx*dx+dy*dy<r*r};
const rr=(a,q)=>a[1]<q[3]&&a[3]>q[1]&&a[2]<q[4]&&a[4]>q[2],d=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
if(I.touch!==I.tpads[0])bad.push('In.touch is not pad 0');
if(!!I.tpads[1].layout!==(n>1))bad.push(n>1?'P2 has no touch layout':'pad 1 still has a layout in solo');
for(let i=0;i<n;i++){const L=I.tpads[i].layout,vx=n>1?i*(W-hw):0,vw=n>1?hw:W,x1=vx+vw,mid=vx+vw/2,B=m=>bad.push((n>1?'P'+(i+1)+' ':'')+m);
  if(!L){B('no layout');continue}
  if(L.x0!==vx||L.x1!==x1||L.mid!==mid)B('layout rectangle is not the view: '+[L.x0,L.x1,L.mid]);
  const oL=vx<=0,oR=x1>=W,iL=oL?ins.l/s:0,iR=oR?ins.r/s:0,small=vw<420,ms=small?50:60,mx=vx+5+(oL?sa.l:0),lx=x1-96-(oR?sa.r:0),by=H-12-sa.b,ck=small?12:23;
  // what render.js draws in this view (drawHUD)
  const top=[['leaderboard',lx,4,lx+92,4+(small?3:4)*9+3],['minimap',mx-1,4,mx+ms+1,6+ms],['lives and kills',mx,5+ms+4,mx+48,5+ms+21]];
  if(n>1)top.push(['P-label',mx+ms+5,5,mx+ms+17,12]);
  const clock=['clock',mid-ck,4,mid+ck,4+(small?7:14)],feed=["kill feed",mid-72,small?ms+26:21,mid+72,(small?ms+26:21)+25];
  const bottom=[['ability meter',mid-41,by-21,mid+41,by-5],['mass and ammo',mid-58,by,mid+56,by+7]];
  for(const [k,b] of [['abil',L.abil],['boost',L.boost]]){
    if(b.r*2*s<44)B(k+' drawn smaller than 44 css px: '+b.r*2*s);
    if(b.hit<b.r)B(k+' hit zone smaller than the button');
    for(const q of top.concat([clock],bottom))if(cr(b,b.hit,q))B(k+' overlaps '+q[0]);
    if(b.x+b.r>x1-iR||b.x-b.r<vx+iL||b.y+b.r>H-ins.b/s||b.y-b.r<ins.t/s)B(k+' outside the safe area');
    if(b.x+b.hit>x1||b.x-b.hit<vx)B(k+' hit zone leaves its view');
    if((oR&&b.x+b.hit>W-L.edge)||b.y+b.hit>H-L.edgeB)B(k+' hit zone reaches into the palm strip at the glass edge');
    if(b.x-b.hit<mid)B(k+' reaches the move half');}
  if(d(L.abil,L.boost)<L.abil.hit+L.boost.hit+8/s)B('ability and boost hit zones closer than 8 css px');
  if(L.abil.y>=L.boost.y)B('ability not above boost');
  if(d(L.abil,L.aimIdle)*s<120)B('ability within 120 css px of the resting aim thumb: '+d(L.abil,L.aimIdle)*s);
  if(d(L.boost,L.aimIdle)<L.boost.r+L.ring)B('boost overlaps the idle aim ring');
  if(d(L.boost,L.aimIdle)*s>190)B('boost further than 190 css px from the aim thumb: '+d(L.boost,L.aimIdle)*s);
  const P=L.pause;
  if(i>0){if(P)B('has a pause button (only P1 carries it)')}
  else if(!P)B('no pause button');
  else{const pr=['pause',P.x-P.pad,0,P.x+P.w+P.pad,P.y+P.h+P.padY],pd=['pause',P.x,P.y,P.x+P.w,P.y+P.h];
    if((P.w+2*P.pad)*s<44||(P.y+P.h+P.padY)*s<44)B('pause hit zone under 44 css px');
    if(P.w*s<30||P.h*s<12)B('pause drawn too small to see: '+P.w*s+'x'+P.h*s);
    for(const q of top)if(rr(pr,q))B('pause overlaps '+q[0]);
    for(const q of [clock,feed])if(rr(pd,q))B('pause drawn over the '+q[0]);
    for(const b of [L.abil,L.boost])if(cr(b,b.hit,pr))B('pause overlaps a button');
    if(P.x<vx+iL||pr[3]>x1||(n===1&&P.x+P.w>W/2))B('pause outside the safe area / its view');}
  // resting thumbs: each ring on its own half of the view, inside the safe area, clear of the bottom read-outs
  if(!(L.moveIdle.x+L.ring<=mid&&L.aimIdle.x-L.ring>=mid))B('idle sticks not on their own halves of the view');
  if(L.moveIdle.x-L.ring<vx+iL||L.aimIdle.x+L.ring>x1-iR||L.aimIdle.y+L.ring>H-ins.b/s||L.moveIdle.y!==L.aimIdle.y)B('idle stick outside the safe area');
  for(const [k,p,tw] of [['move',L.moveIdle,12],['aim',L.aimIdle,27]]){const box=[k,p.x-Math.max(L.ring,tw),p.y-L.ring,p.x+Math.max(L.ring,tw),p.y+L.ring+13];
    if(box[1]<vx||box[3]>x1)B('idle '+k+' stick or its label leaves the view');
    for(const q of bottom.concat(top))if(rr(box,q))B('idle '+k+' stick overlaps '+q[0]);
    for(const b of [L.abil,L.boost])if(d(p,b)<L.ring+b.r)B('idle '+k+' ring overlaps a button');}
  const lo=40,hi=n>1?46:60;
  if(L.stickR*s<lo||L.stickR*s>hi)B('stick travel not '+lo+'-'+hi+' css px: '+L.stickR*s);
  if(L.edge*s<12||L.edgeB<L.edge||L.edgeB<sa.b)B('palm strip too thin: '+[L.edge,L.edgeB]);
  // taunt button: a proper target, on the move half, under the minimap block, clear of the resting move thumb and the palm strip
  const Tn=L.taunt;
  if(!Tn)B('no taunt button');
  else{
    if(Tn.r*2*s<43.5)B('taunt drawn smaller than 44 css px: '+Tn.r*2*s);
    if(Tn.x-Tn.r<vx+iL||Tn.x+Tn.hit>mid)B('taunt outside the safe area / move half');
    for(const q of top)if(cr(Tn,Tn.r,q))B('taunt overlaps '+q[0]);
    if(d(Tn,L.moveIdle)<Tn.hit+L.ring+8/s)B('taunt within 8 css px of the idle move ring');
    if(L.pause&&cr(Tn,Tn.hit,[0,L.pause.x-L.pause.pad,0,L.pause.x+L.pause.w+L.pause.pad,L.pause.y+L.pause.h+L.pause.padY]))B('taunt hit zone overlaps pause');
  }
}
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
    t.pump(0.3); t.shot(SP + "/p_1p.png")   # solo, idle controls, 844x390

    # ================= 2 players on one phone: a full touch control set in each half =================
    def start2(chars): t.eval("HW.App.quit();HW.App.startLocal(%s)" % chars); t.pump(0.8); spy(t); spyread(t)
    def Lp(i): return J(t, "HW.Input.tpads[%d].layout" % i)
    def uses(): return J(t, "HW.App.locals.map(l=>l.useTouch)")   # whose touch overlay is drawn
    def w2(i): return J(t, "(()=>{const m=HW.App.locals[%d].me;return m?{id:m.id,ang:+m.ang.toFixed(2),aim:+m.aim.toFixed(2),boost:m.boosting,abil:+m.abil.toFixed(1)}:null})()" % i)
    P1, P2 = "HW.App.locals[0].me", "HW.App.locals[1].me"
    start2("[0,2]"); k = sc(); L1, L2 = Lp(0), Lp(1); VX = L2["x0"] * k   # VX: CSS x where P2's half starts
    print("2P dims", t.eval("HW.Render.W+'x'+HW.Render.H"), "P2 half from", VX)
    check("2P touch: both halves have their own layout and show their controls", L1["x1"] <= L2["x0"] and L2["pause"] is None and L1["pause"] is not None and uses() == [True, True], uses())
    t.shot(SP + "/p_2p.png")
    # ---- four fingers: both players steer and shoot at the same time
    ctr(t); t.eval("for(const l of HW.App.locals){l.me.shield=0;l.me.cd=0;l.me.ammo=30}")
    cur = {}
    def fingers(typ, **kw):   # finger ids are f1..f4; every call lists all fingers that are down, like the browser does
        for f, xy in kw.items(): cur[int(f[1:])] = xy
        t.touch(typ, [(i,) + cur[i] for i in sorted(cur)])
    def lift(*ids):
        t.touch("touchEnd", [(i,) + cur.pop(i) for i in ids]); t.pump(0.05)
    for f, xy in (("f1", (100, 250)), ("f2", (320, 290)), ("f3", (VX + 100, 250)), ("f4", (VX + 320, 290))): fingers("touchStart", **{f: xy})
    fingers("touchMove", f1=(60, 210), f2=(370, 290), f3=(VX + 140, 290), f4=(VX + 320, 240)); t.pump(1.4)
    a1, a2 = w2(0), w2(1); sh = list(zip(J(t, "__shotw"), J(t, "__shots"))); s1 = [a for (i, a) in sh if i == a1["id"]]; s2 = [a for (i, a) in sh if i == a2["id"]]
    print("2P four fingers", a1, a2, "shots", s1, s2)
    check("2P touch: P1 steers up-left with the left half's move stick", near(a1["ang"], -2.36), a1["ang"])
    check("2P touch: P2 steers down-right with the right half's move stick, at the same time", near(a2["ang"], 0.79), a2["ang"])
    check("2P touch: P1 aims right and fires", near(a1["aim"], 0) and len(s1) > 0 and all(near(a, 0) for a in s1), s1)
    check("2P touch: P2 aims up and fires, at the same time", near(a2["aim"], -1.57) and len(s2) > 0 and all(near(a, -1.57) for a in s2), s2)
    r1, r2 = rd(t, 0), rd(t, 1)
    check("2P touch: each player's input frame comes from their own half", r1["mx"] < -0.5 and r1["my"] < -0.5 and near(r1["ax"], 1, 0.05) and r1["fire"] and not r1["auto"]
          and r2["mx"] > 0.5 and r2["my"] > 0.5 and near(r2["ay"], -1, 0.05) and r2["fire"] and not r2["auto"], (r1, r2))
    t.shot(SP + "/p_2p_touch.png")
    # ---- a thumb that slides over the divider keeps its player
    b1, b2 = T(t, 0), T(t, 1); fingers("touchMove", f2=(VX + 150, 290)); x1, x2 = T(t, 0), T(t, 1); r1, r2 = rd(t, 0), rd(t, 1)
    check("2P touch: a P1 thumb that slides into P2's half is still P1's aim stick", x1["aim"]["on"] and x1["aim"]["id"] == 2 and x1["aim"]["dx"] > 0.9 and near(r1["ax"], 1, 0.05) and x1["aim"]["ox"] > L1["x1"], x1["aim"])
    check("2P touch: ...and P2's sticks never notice it", x2["move"] == b2["move"] and x2["aim"] == b2["aim"] and near(r2["ay"], -1, 0.05) and r2["mx"] > 0.5, (x2, r2))
    fingers("touchMove", f3=(200, 250)); x1, x2 = T(t, 0), T(t, 1); r1, r2 = rd(t, 0), rd(t, 1)
    check("2P touch: a P2 thumb that slides into P1's half is still P2's move stick", x2["move"]["id"] == 3 and x2["move"]["dx"] < -0.9 and r2["mx"] < -0.9 and x1["move"] == b1["move"] and r1["mx"] < -0.5, (x2["move"], r1))
    lift(1, 2); x1, x2 = T(t, 0), T(t, 1)
    check("2P touch: P1 lifting both thumbs leaves P2's sticks held", not x1["move"]["on"] and not x1["aim"]["on"] and x2["move"]["on"] and x2["aim"]["on"], (x1, x2))
    lift(3, 4); x2 = T(t, 1); check("2P touch: all sticks released", not x2["move"]["on"] and not x2["aim"]["on"])
    # ---- each half has its own midline; the divider is not a screen edge, the glass edge still is
    m2 = L2["mid"] * k
    t.touch("touchStart", [(1, m2, 200)]); x1, x2 = T(t, 0), T(t, 1); up(); check("2P touch: midline of P2's half -> P2's aim stick", x2["aim"]["on"] and not x2["move"]["on"] and not x1["aim"]["on"] and not x1["move"]["on"], x2)
    t.touch("touchStart", [(1, m2 - 1, 200)]); x2 = T(t, 1); up(); check("2P touch: just left of it -> P2's move stick", x2["move"]["on"] and not x2["aim"]["on"])
    t.touch("touchStart", [(1, VX - 1, 320)]); x1, x2 = T(t, 0), T(t, 1); up(); check("2P touch: last px left of the divider -> P1's aim stick", x1["aim"]["on"] and not x2["move"]["on"])
    t.touch("touchStart", [(1, VX, 320)]); x1, x2 = T(t, 0), T(t, 1); up(); check("2P touch: first px of P2's half -> P2's move stick", x2["move"]["on"] and not x1["aim"]["on"])
    t.pump(0.3); t.eval("for(const l of HW.App.locals){l.me.cd=0;l.me.ammo=30}"); n0 = nshots(t)
    t.touch("touchStart", [(1, VX - 5, 340)]); t.pump(0.4); r = rd(t, 0); up()
    check("2P touch: a still thumb right beside the divider auto-fires (the divider is not a palm edge)", r["fire"] and r["auto"] and nshots(t) > n0, r)
    t.pump(0.5); n0 = nshots(t); t.touch("touchStart", [(1, 840, 330)]); t.pump(0.4); r = rd(t, 1); x2 = T(t, 1); up()
    check("2P touch: a hand gripping P2's screen edge does not fire", x2["aim"]["on"] and x2["aim"]["edge"] and not r["fire"] and nshots(t) == n0, r)
    # ---- second finger on one half of P2's pad: hand-over works per pad
    t.touch("touchStart", [(1, VX + 100, 250)]); t.touch("touchMove", [(1, VX + 60, 210)])
    t.touch("touchStart", [(1, VX + 60, 210), (3, VX + 150, 300), (4, 100, 250)]); x1, x2 = T(t, 0), T(t, 1)
    check("2P touch: a second finger on P2's move half waits; a finger in P1's half is P1's", x2["move"]["id"] == 1 and x1["move"]["id"] == 4, (x1["move"], x2["move"]))
    t.touch("touchEnd", [(1, VX + 60, 210)]); x1, x2 = T(t, 0), T(t, 1)
    check("2P touch: P2's waiting finger takes P2's stick over (not P1's finger)", x2["move"]["on"] and x2["move"]["id"] == 3 and x1["move"]["id"] == 4, x2["move"]); up()
    # ---- P2's boost button
    t.eval("%s.mass=80;%s.mass=80" % (P1, P2)); bx, by = L2["boost"]["x"] * k, L2["boost"]["y"] * k
    t.touch("touchStart", [(3, bx, by)]); t.pump(0.4); a1, a2 = w2(0), w2(1)
    check("2P touch: P2's boost button boosts P2 only", a2["boost"] and not a1["boost"] and T(t, 1)["boost"] and not T(t, 0)["boost"], (a1, a2))
    t.touch("touchMove", [(3, bx - 90, by + 40)]); t.pump(0.2); check("2P touch: sliding off P2's boost keeps boosting and does not aim", w2(1)["boost"] and not T(t, 1)["aim"]["on"])
    up(); t.pump(0.1); check("2P touch: P2's boost released", not w2(1)["boost"] and not T(t, 1)["boost"])
    bx, by = L1["boost"]["x"] * k, L1["boost"]["y"] * k; t.touch("touchStart", [(3, bx, by)]); t.pump(0.4); a1, a2 = w2(0), w2(1); up()
    check("2P touch: P1's boost button (beside the divider) boosts P1 only", a1["boost"] and not a2["boost"], (a1, a2))
    # ---- P2's ability button: on release, P2 only; slide off = aim instead
    ax, ay = L2["abil"]["x"] * k, L2["abil"]["y"] * k; t.eval("%s.abil=0;%s.abil=0" % (P1, P2)); e0 = edges(t)
    t.touch("touchStart", [(4, ax, ay)]); t.pump(0.2)
    check("2P touch: P2's ability waits for the release", t.eval("HW.App.G.zones.length") == 0 and T(t, 1)["held"] and not T(t, 0)["held"])
    up(); t.pump(0.2); z = J(t, "HW.App.G.zones.map(z=>z.k)"); e1 = edges(t)
    check("2P touch: P2's ability button pukes for P2 only", z == [1] and e1[1]["abil"] == e0[1]["abil"] + 1 and e1[0]["abil"] == e0[0]["abil"] and w2(1)["abil"] > 50 and w2(0)["abil"] <= 0, (z, e0, e1))
    t.eval("%s.abil=0" % P2); t.touch("touchStart", [(4, ax, ay)]); t.touch("touchMove", [(4, ax - 70, ay + 50)]); t.pump(0.2); x2 = T(t, 1); x1 = T(t, 0)
    check("2P touch: sliding off P2's ability button aims for P2 instead", x2["aim"]["on"] and not x2["held"] and not x1["aim"]["on"] and near(w2(1)["aim"], 2.52, 0.2), w2(1)["aim"])
    up(); t.pump(0.2); check("2P touch: ...and does not use it", t.eval("HW.App.G.zones.length") == 1 and w2(1)["abil"] <= 0)
    ax, ay = L1["abil"]["x"] * k, L1["abil"]["y"] * k; t.touch("touchStart", [(4, ax, ay)]); up(); t.pump(0.2); z = J(t, "HW.App.G.zones.map(z=>z.k)")
    check("2P touch: P1's ability button farts for P1", sorted(z) == [0, 1] and w2(0)["abil"] > 50, z)
    t.pump(0.4); t.shot(SP + "/p_2p_abil.png")
    # ---- In.lastKind follows P1 only; P2 has dev.kind. Neither player's input changes the other's hints.
    LK = lambda: (t.eval("HW.Input.lastKind"), t.eval("HW.App.locals[1].dev.kind"))
    t.key("down", "KeyD", "d", 68); t.pump(0.2); t.key("up", "KeyD", "d", 68); t.pump(0.1)
    check("2P touch: P1 on the keyboard hides P1's touch overlay only", LK()[0] == "kb" and uses() == [False, True], (LK(), uses()))
    t.touch("touchStart", [(3, VX + 100, 250)]); t.touch("touchMove", [(3, VX + 140, 250)]); t.pump(0.3)
    check("2P touch: a touch in P2's half does not flip In.lastKind", LK() == ("kb", "touch") and uses() == [False, True] and rd(t, 1)["mx"] > 0.9, (LK(), uses())); up()
    t.touch("touchStart", [(1, 100, 250)]); t.pump(0.2); up(); check("2P touch: a touch in P1's half brings P1's overlay back", LK()[0] == "touch" and uses() == [True, True], (LK(), uses()))
    t.key("down", "ArrowUp", "ArrowUp", 38); t.pump(0.2); r2 = rd(t, 1); t.key("up", "ArrowUp", "ArrowUp", 38); t.pump(0.1)
    check("2P touch: P2 on the arrow keys hides P2's overlay and leaves In.lastKind alone", LK() == ("touch", "kb") and uses() == [True, False] and r2["my"] == -1, (LK(), uses()))
    t.touch("touchStart", [(3, VX + 100, 250)]); t.pump(0.2); up(); check("2P touch: P2 touching again brings P2's overlay back", LK() == ("touch", "touch") and uses() == [True, True], (LK(), uses()))
    # P1 aiming with a real mouse (touch-screen laptop) while P2 plays on the glass
    t.pump(1.2); t.mouse("mouseMoved", 100, 100); t.mouse("mouseMoved", 200, 200); m = J(t, "HW.Input.mouse")
    if m["active"]:
        t.touch("touchStart", [(3, VX + 100, 250)]); t.touch("touchMove", [(3, VX + 140, 250)]); t.mouse("mouseMoved", 260, 220); t.pump(0.2); m = J(t, "HW.Input.mouse")
        check("2P touch: P2's thumb leaves P1's mouse aim alone", m["active"] and abs(m["x"] * k - 260) < 2 and LK()[0] == "kb" and uses() == [False, True], (m, LK()))
        t.touch("touchStart", [(3, VX + 140, 250), (1, 100, 250)]); t.pump(0.2); m = J(t, "HW.Input.mouse"); up()
        check("2P touch: P1's own thumb switches P1 from mouse to touch", not m["active"] and LK()[0] == "touch" and uses() == [True, True], (m, LK()))
    else: print("skip  mouse events are not taken as real in this tab:", m)
    # ---- pause: one button, in P1's half; the same spot in P2's half is plain stick area
    p = L1["pause"]; px_, py_ = (p["x"] + p["w"] / 2) * k, (p["y"] + p["h"] / 2) * k
    t.touch("touchStart", [(3, VX + px_, py_)]); t.pump(0.3); x2 = T(t, 1)
    check("2P touch: no pause button in P2's half", t.eval("HW.App.paused") is False and x2["move"]["on"], x2["move"]); up()
    t.touch("touchStart", [(3, VX + 100, 250)]); t.touch("touchMove", [(3, VX + 60, 210)])
    t.touch("touchStart", [(3, VX + 60, 210), (5, px_, py_)]); t.pump(0.4)
    check("2P touch: P1's pause button pauses the game", t.eval("HW.App.paused") is True and t.eval("HW.App.screen") == "pause")
    t.touch("touchEnd", [(5, px_, py_)]); x1, x2 = T(t, 0), T(t, 1)
    check("2P touch: both players' sticks cleared by pause", not x2["move"]["on"] and not x1["tap"] and not x2["tap"] and not x1["pause"], (x1, x2))
    t.eval("HW.App.setPause(false)"); t.pump(0.2); t.touch("touchMove", [(3, VX + 100, 210)]); t.touch("touchMove", [(3, VX + 150, 210)]); x1, x2 = T(t, 0), T(t, 1)
    check("2P touch: P2's thumb held through the pause works again, for P2", x2["move"]["on"] and x2["move"]["dx"] > 0.9 and not x1["move"]["on"] and not x1["aim"]["on"], x2["move"]); up()
    # ---- tap to hurry the respawn: each player's own half
    t0 = t.eval("(()=>{const s=HW.App.sim;s.kill(HW.App.locals[1].player.worm,null,'shot');return s.S.t})()"); t.pump(1.4)
    t.touch("touchStart", [(1, 100, 250)]); t.touch("touchEnd", []); t.pump(0.3)
    check("2P touch: a tap in P1's half does not respawn P2", t.eval("!HW.App.locals[1].me") and t.eval("HW.App.sim.S.t") - t0 < 2.6, t.eval("HW.App.sim.S.t") - t0)
    t.shot(SP + "/p_2p_dead.png")
    t.touch("touchStart", [(3, VX + 100, 250)]); t.touch("touchEnd", []); t.pump(0.3); dt_ = t.eval("HW.App.sim.S.t") - t0
    check("2P touch: a tap in P2's half respawns P2 early", t.eval("!!HW.App.locals[1].me") and dt_ < 2.9, dt_)
    # ---- the ability button follows each half's own worm (Jeff has none)
    start2("[4,0]"); L1, L2 = Lp(0), Lp(1); k = sc()
    t.touch("touchStart", [(1, L1["abil"]["x"] * k, L1["abil"]["y"] * k)]); t.touch("touchStart", [(1, L1["abil"]["x"] * k, L1["abil"]["y"] * k), (3, L2["abil"]["x"] * k, L2["abil"]["y"] * k)]); x1, x2 = T(t, 0), T(t, 1); t.touch("touchCancel", []); t.pump(0.1)
    check("2P touch: no ability button for P1's Jeff, P2's Ben still has one", x1["aim"]["on"] and not x1["held"] and x2["held"] and not x2["aim"]["on"], (x1, x2))
    # ---- P2 picks up a controller: P2's overlay goes, P1 keeps touch
    t.eval("window.__pad=" + PAD % (0, "fake", "standard", "[0,0,0,0]", 17) + ";navigator.getGamepads=()=>[window.__pad];HW.App.quit();HW.App.startLocal([0,2]);")
    t.pump(0.6); VX = Lp(1)["x0"] * sc(); t.touch("touchStart", [(1, 150, 250)]); t.touch("touchMove", [(1, 110, 210)]); t.pump(0.3)
    t.eval("__pad.axes[0]=1"); t.pump(0.5)
    check("2P phone: P2's controller does not hide P1's touch controls", t.eval("HW.Input.lastKind") == "touch" and t.eval("HW.App.locals[1].dev.kind") == "pad")
    check("2P phone: P2 on a controller has no touch overlay, P1 keeps theirs", uses() == [True, False], uses())
    r1, r2 = rd(t, 0), rd(t, 1)
    check("2P phone: touch drives P1 only, pad drives P2 only", r1["mx"] < -0.5 and r1["my"] < -0.5 and r2["mx"] == 1 and r2["my"] == 0, (r1, r2))
    t.shot(SP + "/p_2p_pad.png"); up(); t.eval("__pad.axes[0]=0;navigator.getGamepads=()=>[]"); t.pump(0.3)
    t.touch("touchStart", [(3, VX + 100, 250)]); t.pump(0.3); up()
    check("2P phone: controller gone, P2 touches their half -> P2's overlay is back", uses() == [True, True] and t.eval("HW.Input.lastKind") == "touch", uses())
    check("2P touch: no page errors so far", not t.errors, t.errors); t.eval("HW.App.quit()"); t.pump(0.2)
    # ---- the same on a small phone (667x375 @2x): screenshots to look at, and one real four-finger frame
    t.device(667, 375, 2, True, True); t.pump(0.4); t.eval("HW.App.startLocal([0])"); t.pump(1.0); t.shot(SP + "/p_1p_small.png")
    start2("[0,2]"); k = sc(); VX = Lp(1)["x0"] * k; t.shot(SP + "/p_2p_small.png")
    t.touch("touchStart", [(1, 80, 250)]); t.touch("touchStart", [(1, 80, 250), (2, 250, 290)]); t.touch("touchStart", [(1, 80, 250), (2, 250, 290), (3, VX + 80, 250)]); t.touch("touchStart", [(1, 80, 250), (2, 250, 290), (3, VX + 80, 250), (4, VX + 250, 290)])
    t.touch("touchMove", [(1, 40, 250), (2, 250, 240), (3, VX + 130, 250), (4, VX + 250, 340)]); t.pump(0.3); r1, r2 = rd(t, 0), rd(t, 1)
    check("2P touch: four fingers on a 667 px wide phone", r1["mx"] < -0.9 and near(r1["ay"], -1, 0.05) and r1["fire"] and r2["mx"] > 0.9 and near(r2["ay"], 1, 0.05) and r2["fire"], (r1, r2))
    t.shot(SP + "/p_2p_small_touch.png"); up(); t.eval("HW.App.quit()"); t.device(844, 390, 3, True, True); t.pump(0.4)

    # ---- layout geometry on real phone sizes, with and without notch / home-indicator insets, 1P and 2P
    nlay = 0
    for (w, h, d) in [(667, 375, 2), (667, 320, 2), (736, 414, 3), (812, 375, 3), (844, 390, 3), (896, 414, 2), (915, 412, 2.625), (932, 430, 3)]:
        t.device(w, h, d, True, True); t.pump(0.3)
        for n in ("[0]", "[0,2]"):
            t.eval("HW.App.startLocal(%s)" % n); t.pump(0.25)
            for safe in ("null", "{l:47,r:47,t:0,b:21}", "{l:59,r:59,t:0,b:21}", "{l:0,r:48,t:0,b:0}", "{l:48,r:0,t:0,b:0}"):
                t.eval("HW.Input.safe=%s;HW.Input.layout()" % safe); bad = J(t, LAYOUT_JS); nlay += 1
                if bad: check("layout %dx%d %s safe=%s" % (w, h, "2P" if "," in n else "1P", safe), False, bad)
            t.eval("HW.Input.safe=null;HW.App.quit()")
    check("layout: all phone sizes checked", nlay == 80, nlay)
    t.eval("HW.App.startLocal([0])"); t.pump(0.2); check("layout: back in solo, pad 1 has no layout and pad 0 spans the screen", J(t, "HW.Input.tpads[1].layout") is None and L()["x1"] == t.eval("HW.Render.W")); t.eval("HW.App.quit()")
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
