"""Power-ups, special guns, golden burger, kill streaks, bounty, frenzy, taunts, awards, veggie countdown.
Rules are checked on a private HW.Sim inside the page (no rendering, exact and fast); the last part plays the real game.
  HW_URL=http://127.0.0.1:8377/index.html HW_PORT=9415 python3 test/power.py <scratch dir>"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html"); FAIL = []
def ok(c, msg, extra=""):
    print(("ok   " if c else "FAIL ") + msg, extra if (extra != "" and not c) or os.environ.get("HW_VERBOSE") else "")
    if not c: FAIL.append(msg)

HARNESS = r"""
window.PT = (() => {
  const CFG = HW.CFG, MAP = HW.MAP, INP = () => ({ mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false });
  // the emptiest spot in the arena: nothing within `far` of it, so worms can be lined up without an obstacle in the way
  let spot = null, far = 0;
  for (let y = 300; y < CFG.H - 300; y += 40) for (let x = 300; x < CFG.W - 300; x += 40) {
    let d = 1e9; for (const o of MAP.obs) { const dx = Math.max(o.x0 - x, 0, x - o.x1), dy = Math.max(o.y0 - y, 0, y - o.y1); d = Math.min(d, Math.hypot(dx, dy)); }
    if (d > far) { far = d; spot = { x, y }; }
  }
  // n humans (no bots) with the given characters, spawned, the map swept clean of items and pending drops
  function mk(chs, keepItems) {
    const keep = CFG.WORMS; CFG.WORMS = chs.length; const s = new HW.Sim({ diff: 1 }); CFG.WORMS = keep; s.keepWorms = chs.length;
    const ps = chs.map(ch => { const p = s.addPlayer(ch); p.inp = INP(); return p; });
    const fb = s.fillBots; s.fillBots = function () { const k = CFG.WORMS; CFG.WORMS = this.keepWorms; fb.call(this); CFG.WORMS = k; };
    for (let i = 0; i < 5; i++) s.step(1 / 60);
    if (!keepItems) { for (const it of Array.from(s.S.items.values())) s.remItem(it); s.S.respawns.length = 0; }
    flush(s); return { s, ps, w: ps.map(p => p.worm) };
  }
  function flush(s) { const e = s.S.events; s.S.events = []; s.S.adds.length = 0; s.S.rems.length = 0; return e; }
  // lay a worm out straight, head at (x, y) pointing along ang, no shields of any kind
  function place(w, x, y, ang, mass) {
    if (mass) w.mass = mass; w.x = x; w.y = y; w.ang = ang; w.aim = ang; w.shield = 0; w.mercy = 0; w.cd = 0;
    const n = HW.segCount(w.mass); w.pts.length = 0; for (let i = 0; i < n; i++) w.pts.push({ x: x - Math.cos(ang) * i * 6, y: y - Math.sin(ang) * i * 6 });
    HW.follow(w); return w;
  }
  function run(s, secs) { const ev = []; for (let i = 0; i < Math.round(secs * 60); i++) { s.step(1 / 60); for (const e of flush(s)) ev.push(e); } return ev; }
  const evs = (ev, k) => ev.filter(e => e[0] === k);
  return { mk, place, run, evs, flush, spot, far, INP };
})();
"""
J = lambda t, js: json.loads(t.eval("JSON.stringify(%s)" % js))
b = Browser(profile=SP + "/prof")
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 1.2); t.eval(HARNESS + ";0")
    far = J(t, "PT.far"); ok(far > 200, "harness: found an open area", far)
    ok(J(t, "HW.GUNS.length") == 10 and J(t, "HW.GUNS.map(g=>g.kind)") == list(range(10)), "guns: 5 character guns + 5 special, kind = index")
    ok(J(t, "HW.POWERS.length") == 4 and J(t, "HW.powerSpr.length") == 4 and J(t, "HW.sgunSpr.length") == 5, "every power-up and special gun has a sprite")

    # ---------- rampage ----------
    r = J(t, """(()=>{const {s,w}=PT.mk([1]),a=w[0],sp=PT.spot;PT.place(a,sp.x-200,sp.y,0);s.addItem('p',0,a.x+6,a.y,0);
      const ev=PT.run(s,0.1),x0=a.x,r0=a.rage;PT.run(s,1);a.inp.mx=1;const x1=a.x;PT.run(s,1);
      return {rage:r0,pw:PT.evs(ev,'power').length,type:(PT.evs(ev,'power')[0]||[])[4],speed:a.x-x1,base:HW.CHARS[1].speed,resp:s.S.respawns.filter(q=>q.k==='p').length}})()""")
    ok(abs(r["rage"] - 9) < 0.2 and r["pw"] == 1 and r["type"] == 0 and r["resp"] == 1, "pizza: rampage starts, event sent, a new power-up is scheduled", r)
    ok(abs(r["speed"] - r["base"] * 1.4) < 3, "rampage: 40% faster", r)
    CRASH = """(()=>{const {s,w}=PT.mk([1,1]),a=w[0],v=w[1],sp=PT.spot;PT.place(v,sp.x+150,sp.y-60,Math.PI/2,80);PT.place(a,sp.x-80,sp.y-170,Math.PI/2,40);a.inp.mx=0;a.inp.my=0;
      PT.place(a,sp.x+80,sp.y-150,0,40);a.inp.mx=1;%s;const ev=PT.run(s,1.2),d=PT.evs(ev,'die');
      return {dies:d.map(e=>[e[3]===a.id?'a':'v',e[5]]),aAlive:a.alive,vAlive:v.alive,kills:a.comp.kills,pts:a.comp.pts}})()"""
    r = J(t, CRASH % "a.rage=5")
    ok(r["dies"] == [["v", "rampage"]] and r["aAlive"] and r["kills"] == 1, "rampage: running into a body kills THEM, with kill credit", r)
    r = J(t, CRASH % "0")
    ok(r["dies"] == [["a", "crash"]] and r["vAlive"], "no rampage: the same crash kills you", r)
    r = J(t, CRASH % "a.rage=5;v.rage=5")
    ok(r["dies"] == [["a", "crash"]], "two rampages: the usual rule holds", r)
    r = J(t, CRASH % "a.rage=5;v.shield=3")
    ok(r["dies"] == [], "rampage does not kill a worm under its spawn shield", r)
    HEADON = """(()=>{const {s,w}=PT.mk([1,1]),a=w[0],v=w[1],sp=PT.spot;PT.place(a,sp.x-60,sp.y,0,%d);PT.place(v,sp.x+60,sp.y,Math.PI,%d);a.inp.mx=1;v.inp.mx=-1;%s;
      const d=PT.evs(PT.run(s,1.5),'die');return d.map(e=>[e[3]===a.id?'a':'v',e[5]])})()"""
    ok(J(t, HEADON % (40, 90, "0")) == [["a", "bonk"]], "head-on: the lighter worm dies")
    ok(J(t, HEADON % (40, 90, "a.rage=5")) == [["v", "rampage"]], "head-on: rampage beats a heavier worm")
    ok(J(t, HEADON % (40, 90, "a.big=5")) == [["v", "bonk"]], "head-on: supersize beats a heavier worm")
    ok(J(t, HEADON % (40, 90, "a.big=5;v.rage=5")) == [["a", "rampage"]], "head-on: rampage beats supersize")
    r = J(t, """(()=>{const {s,w}=PT.mk([1]),a=w[0];PT.place(a,PT.spot.x,PT.spot.y,0);a.rage=0.5;const ev=PT.run(s,1);return {rage:a.rage,off:PT.evs(ev,'poweroff').map(e=>e[4])}})()""")
    ok(r["rage"] <= 0 and r["off"] == [0], "rampage runs out and says so", r)

    # ---------- bumping: a crash is not instant ----------
    BUMP = """(()=>{const {s,w}=PT.mk([%d,1]),a=w[0],v=w[1],sp=PT.spot,T=HW.CFG.CRASH_T;PT.place(v,sp.x+150,sp.y-60,Math.PI/2,80);v.stuck=99;PT.place(a,sp.x+%d,sp.y-%d,%s,40);a.inp.mx=Math.cos(a.ang);a.inp.my=Math.sin(a.ang);
      let first=-1,died=-1,bumps=0,side=1,minx=1e9,turned=false;const bx=sp.x+150;
      for(let i=0;i<60*%s;i++){s.step(1/60);for(const e of PT.flush(s)){if(e[0]==='bump'&&e[3]===a.id){bumps++;if(first<0)first=i/60}if(e[0]==='die'&&e[3]===a.id&&died<0)died=i/60}
        if(a.alive&&a.x>bx+2)side=-1;
        if(first>=0&&!turned&&i/60-first>=%s){turned=true;a.inp.mx=-1;a.inp.my=0}}
      return {T,first,died,wait:died<0?-1:died-first,bumps,alive:a.alive,through:side<0,crash:a.crash}})()"""
    r = J(t, BUMP % (1, 40, 150, "0", "2.5", "99"))
    ok(r["first"] >= 0 and r["died"] > 0 and abs(r["wait"] - r["T"]) < 0.06 and r["bumps"] >= 2 and not r["through"], "crash: square on, you bump first and die only after the grace time", r)
    r = J(t, BUMP % (1, 40, 150, "0", "2.5", "0.04"))
    ok(r["first"] >= 0 and r["alive"] and not r["through"] and r["crash"] == 0, "crash: turn away in time and you live (big, slow worm)", r)
    r = J(t, BUMP % (2, 40, 150, "0", "2.5", "0.15"))
    ok(r["alive"] and not r["through"], "crash: turn away in time and you live (small, quick worm)", r)
    r = J(t, BUMP % (1, 132, 280, "Math.PI/2-0.12", "1.3", "99"))
    ok(r["first"] >= 0 and r["alive"] and not r["through"], "crash: sliding along a body for a moment is only a scrape", r)
    r = J(t, """(()=>{const {s,w}=PT.mk([1,1]),a=w[0],v=w[1],sp=PT.spot;PT.place(v,sp.x+150,sp.y-60,Math.PI/2,80);v.stuck=99;PT.place(a,sp.x+60,sp.y-150,0,40);a.inp.mx=1;a.rage=5;
      let t0=-1,t1=-1;for(let i=0;i<120;i++){s.step(1/60);for(const e of PT.flush(s)){if(e[0]==='die'&&t1<0)t1=i}const d=Math.abs(a.x-v.x);if(t0<0&&d<a.r+v.r)t0=i}return {t0,t1,valive:v.alive}})()""")
    ok(not r["valive"] and r["t1"] - r["t0"] <= 2, "rampage: no waiting, the worm you hit dies on contact", r)

    # ---------- supersize ----------
    r = J(t, """(()=>{const {s,w}=PT.mk([1,3]),a=w[0],sh=w[1],sp=PT.spot;PT.place(a,sp.x,sp.y,0,60);const r0=a.r,m0=a.mass;s.addItem('p',1,a.x+4,a.y,0);PT.run(s,0.1);
      const big={r:a.r,mass:a.mass,t:a.big};
      const hit=(arm)=>{a.big=arm?5:0;a.mass=100;const m=a.mass;s.damage(a,10,sh,a.x,a.y);return m-a.mass};const lossBig=hit(true),lossNorm=hit(false);
      a.big=0.3;a.mass=60;const ev=PT.run(s,0.6);return {r0,m0,big,lossBig,lossNorm,rAfter:a.r,off:PT.evs(ev,'poweroff').map(e=>e[4])}})()""")
    ok(r["big"]["r"] == round(r["r0"] * 1.5) and abs(r["big"]["mass"] - r["m0"] - 20) < 0.01 and abs(r["big"]["t"] - 12) < 0.2, "fries: half again as big, +20 mass, 12 s", r)
    ok(abs(r["lossBig"] - (5 + 2)) < 0.01 and abs(r["lossNorm"] - (10 + 2)) < 0.01, "supersize: shot damage is halved", r)
    ok(r["rAfter"] == r["r0"] and r["off"] == [1], "supersize wears off: back to normal size", r)

    # ---------- shot shield ----------
    SHOOT = """(()=>{const {s,w}=PT.mk([%d,1,1]),a=w[0],v=w[1],v2=w[2],sp=PT.spot;PT.place(a,sp.x-%d,sp.y,0,60);PT.place(v,sp.x,sp.y-80,-Math.PI/2,90);PT.place(v2,sp.x+40,sp.y-80,-Math.PI/2,90);
      a.stuck=v.stuck=v2.stuck=99;%s;a.ammo=50;a.inp.ax=1;a.inp.fire=true;const m0=v.mass,m2=v2.mass,am=a.ammo,ev=PT.run(s,%s);
      return {loss:m0-v.mass,loss2:m2-v2.mass,ping:PT.evs(ev,'ping').length,hit:PT.evs(ev,'hit').length,shots:PT.evs(ev,'shot').length,kinds:[...new Set(PT.evs(ev,'shot').map(e=>e[3]))],used:am-a.ammo,vAlive:v.alive,chill:v.chill,sg:a.sg,off:PT.evs(ev,'gunoff').length,boom:PT.evs(ev,'boom').length,clang:PT.evs(ev,'clang').length,bul:s.S.bullets.length}})()"""
    # the victims lie across the line of fire: v at x=spot, v2 40 px behind it
    r = J(t, SHOOT % (3, 150, "0", "1.5"))
    ok(r["loss"] > 5 and r["loss2"] > 5 and r["ping"] == 0, "skewer (no shield): pierces both worms", r)
    r = J(t, SHOOT % (3, 150, "v.guard=9", "1.5"))
    ok(r["loss"] == 0 and r["loss2"] == 0 and r["ping"] >= 2 and r["vAlive"], "shot shield: stops shots dead, even piercing ones", r)
    r = J(t, SHOOT % (4, 150, "v.guard=9;v2.guard=9", "2.5"))
    ok(r["loss"] == 0 and r["loss2"] == 0 and r["boom"] >= 1, "shot shield: rocket blasts do nothing", r)
    r = J(t, CRASH % "a.guard=9")
    ok(r["dies"] == [["a", "crash"]], "shot shield does not save you from a crash", r)
    r = J(t, """(()=>{const {s,w}=PT.mk([1,1]),a=w[0],v=w[1],sp=PT.spot;PT.place(a,sp.x-100,sp.y-150,Math.PI,60);PT.place(v,sp.x+60,sp.y,0,60);v.guard=9;s.S.zones.push({id:s.S.nextId++,k:0,x:v.x,y:v.y,r:HW.CFG.FART_R,t:5,owner:a.id});
      return PT.evs(PT.run(s,0.2),'die').map(e=>e[5])})()""")
    ok(r == ["fart"], "shot shield does not stop a fart", r)

    # ---------- hot sauce ----------
    r = J(t, """(()=>{const go=(hot,mass)=>{const {s,w}=PT.mk([1]),a=w[0],sp=PT.spot;PT.place(a,sp.x-220,sp.y,0,mass);a.sauce=hot?8:0;a.inp.mx=1;a.inp.boost=true;const x=a.x,m=a.mass;PT.run(s,1);return [a.x-x,m-a.mass,a.boosting]};
      return {hot:go(true,40),cold:go(false,40),tiny:go(true,HW.CFG.MIN_MASS+1),tinyCold:go(false,HW.CFG.MIN_MASS+1),base:HW.CHARS[1].speed*HW.CFG.BOOST_MULT}})()""")
    ok(r["hot"][1] == 0 and r["cold"][1] > 4, "hot sauce: boosting costs no mass", r)
    ok(abs(r["hot"][0] - r["base"] * 1.15) < 4 and abs(r["cold"][0] - r["base"]) < 4, "hot sauce: boost is 15% quicker", r)
    ok(r["tiny"][2] is True and r["tinyCold"][2] is False, "hot sauce: even the smallest worm can boost", r)

    # ---------- special guns ----------
    GUN = "a.sg=%d;a.sgT=%s"
    r = J(t, SHOOT % (2, 150, GUN % (1, 20), "1.5"))
    ok(r["kinds"] == [5] and r["used"] == 0 and r["loss"] > 8 and r["loss2"] > 8, "ray gun: uses no ammo, goes through both worms", r)
    r = J(t, SHOOT % (2, 150, GUN % (2, 20), "2.5"))
    ok(r["kinds"] == [6] and r["boom"] >= 1 and r["loss"] > 15 and r["loss2"] > 10, "rocket launcher: big blast hurts both", r)
    near = J(t, SHOOT % (2, 110, GUN % (3, 20), "1.5")); farr = J(t, SHOOT % (2, 260, GUN % (3, 20), "1.5"))
    ok(near["kinds"] == [7] and near["loss"] > 10 and near["shots"] >= 20 and farr["loss"] == 0, "flamethrower: melts up close, cannot reach far", (near, farr))
    r = J(t, SHOOT % (2, 150, GUN % (4, 20), "1.5"))
    ok(r["kinds"] == [8] and r["shots"] >= 18 and r["loss"] > 8 and r["used"] == 0, "popcorn minigun: a stream of shots", r)
    r = J(t, SHOOT % (2, 150, GUN % (5, 20), "1.0"))
    ok(r["kinds"] == [9] and 0 < r["chill"] <= 3.5 and r["loss"] > 0, "freeze ray: chills what it hits (the timer refreshes, it does not stack)", r)
    r = J(t, SHOOT % (2, 150, GUN % (5, 20) + ";v.guard=9", "1.0"))
    ok(r["chill"] == 0 and r["loss"] == 0, "freeze ray: the shot shield keeps the cold out", r)
    r = J(t, """(()=>{const {s,w}=PT.mk([1]),a=w[0],sp=PT.spot;PT.place(a,sp.x-200,sp.y,0);a.inp.mx=1;PT.run(s,0.5);const x=a.x;PT.run(s,1);const base=a.x-x;a.chill=3;const x2=a.x;PT.run(s,1);return [base,a.x-x2]})()""")
    ok(abs(r[1] / r[0] - 0.4) < 0.03, "chilled: crawling at 40% speed", r)
    r = J(t, SHOOT % (2, 150, GUN % (1, 0.6), "1.5"))
    ok(r["sg"] == 0 and r["off"] == 1 and sorted(r["kinds"]) == [2, 5] and r["used"] > 0, "special gun times out: your own gun (and ammo) are back", r)
    r = J(t, """(()=>{const {s,w}=PT.mk([0]),a=w[0],sp=PT.spot;PT.place(a,sp.x,sp.y,0);const am=a.ammo;s.addItem('g',4,a.x+5,a.y,0);const ev=PT.run(s,0.1);
      return {sg:a.sg,t:a.sgT,ev:PT.evs(ev,'gun').map(e=>e[4]),resp:s.S.respawns.filter(q=>q.k==='g').length,ammo:a.ammo===am}})()""")
    ok(r["sg"] == 5 and abs(r["t"] - 14) < 0.2 and r["ev"] == [4] and r["resp"] == 1 and r["ammo"], "gun pickup: equips for its time, a new one is scheduled", r)
    # special shots are stopped by obstacles like any other
    r = J(t, """(()=>{const o=HW.MAP.obs.find(q=>q.k==='counter'&&q.w>q.h),out=[];for(let g=1;g<=5;g++){const {s,w}=PT.mk([2,1]),a=w[0],v=w[1];
      PT.place(a,o.x+o.w/2,o.y-70,Math.PI/2,60);PT.place(v,o.x+o.w/2+60,o.y+o.h+30,0,90);a.stuck=v.stuck=99;a.sg=g;a.sgT=20;a.inp.ay=1;a.inp.fire=true;const m=v.mass,ev=PT.run(s,2.2);out.push([m-v.mass,PT.evs(ev,'clang').length+PT.evs(ev,'boom').length])}return out})()""")
    ok(all(q[0] == 0 and q[1] > 0 for q in r), "special guns: a counter stops every one of them", r)

    # ---------- golden burger ----------
    r = J(t, """(()=>{const {s,w}=PT.mk([1]),a=w[0],sp=PT.spot;PT.place(a,sp.x,sp.y,0);const m=a.mass;s.dropItem('x');const it=[...s.S.items.values()].find(i=>i.k==='x');const v=it.v;it.x=a.x+5;it.y=a.y;
      const ev=PT.run(s,0.1);return {v,gain:a.mass-m,ev:PT.evs(ev,'gold').length,left:s.S.counts.x,resp:s.S.respawns.filter(q=>q.k==='x').length}})()""")
    ok(r["v"] == 30 and abs(r["gain"] - 30) < 0.01 and r["ev"] == 1 and r["left"] == 0 and r["resp"] == 1, "golden burger: +30 mass, then another one is on its way", r)

    # ---------- stock on the map ----------
    r = J(t, """(()=>{const s=new HW.Sim({diff:1}),S=s.S,c0=Object.assign({},S.counts);let bad=0,maxp=0,maxg=0,maxx=0,drops=0;
      for(let i=0;i<60*70;i++){s.step(1/60);for(const e of S.events)if(e[0]==='drop')drops++;S.events=[];S.adds.length=0;S.rems.length=0;maxp=Math.max(maxp,S.counts.p);maxg=Math.max(maxg,S.counts.g);maxx=Math.max(maxx,S.counts.x);}
      const cn={p:0,g:0,x:0};for(const it of S.items.values()){if(cn[it.k]!==undefined){cn[it.k]++;if(HW.MAP.hit(it.x,it.y,8))bad++;}}
      return {c0,maxp,maxg,maxx,drops,bad,cn,counts:S.counts}})()""")
    ok(r["c0"]["p"] == 0 and r["c0"]["g"] == 0 and r["c0"]["x"] == 0, "a fresh arena starts with no pickups lying around", r)
    ok(1 <= r["maxp"] <= 3 and 1 <= r["maxg"] <= 3 and r["maxx"] == 1 and r["drops"] >= 5, "within a minute pickups turn up: at most 3 power-ups, 3 guns, 1 golden burger", r)
    ok(r["bad"] == 0 and all(r["cn"][k] == r["counts"][k] for k in "pgx"), "pickups never land in an obstacle; counts agree", r)

    # ---------- veggies and mushrooms charge the ability ----------
    r = J(t, """(()=>{const {s,w}=PT.mk([1,4]),a=w[0],j=w[1],sp=PT.spot;PT.place(a,sp.x,sp.y,0,60);PT.place(j,sp.x,sp.y+120,0,60);a.abil=40;
      s.addItem('v',0,a.x+3,a.y,0);let ev=PT.run(s,0.05);const a1=a.abil,cut1=(PT.evs(ev,'veg')[0]||[])[5];s.addItem('m',0,a.x+3,a.y,0);ev=PT.run(s,0.05);const a2=a.abil,cut2=(PT.evs(ev,'shroom')[0]||[])[4];
      a.abil=4;s.addItem('v',0,a.x+3,a.y,0);PT.run(s,0.05);const a3=a.abil;s.addItem('v',0,j.x+3,j.y,0);s.addItem('m',0,j.x+3,j.y,0);PT.run(s,0.05);
      return {a1,cut1,a2,cut2,a3,slow:a.slow,trip:a.trip,jeff:j.abil,jalive:j.alive,st:a.comp.st}})()""")
    ok(abs(r["a1"] - 29.95) < 0.1 and r["cut1"] == 10 and abs(r["a2"] - 14.9) < 0.1 and r["cut2"] == 15, "veggie takes 10 s off the countdown, mushroom 15 s", r)
    ok(r["a3"] <= 0.001 and r["a3"] > -0.1 and r["slow"] > 0 and r["trip"] > 0, "the countdown stops at zero; the bad effects still apply", r)
    ok(r["jeff"] == 0 and r["jalive"] and r["st"]["veg"] == 2 and r["st"]["shr"] == 1, "Jeff (no ability) is unaffected; eaten greens are counted for the awards", r)

    # ---------- streaks and bounty ----------
    r = J(t, """(()=>{const {s,w,ps}=PT.mk([1,1,1,1]),a=w[0],sp=PT.spot;PT.place(a,sp.x,sp.y,0,50);const K=HW.CFG.KILL_PTS,out=[],evAll=[];
      for(let i=1;i<4;i++){PT.place(w[i],sp.x+100+i*40,sp.y+200,0,30)}
      s.S.leader=0;s.kill(w[1],a,'shot');out.push(a.comp.pts);s.kill(w[2],a,'shot');out.push(a.comp.pts);s.S.leader=w[3].id;s.kill(w[3],a,'shot');out.push(a.comp.pts);
      const ev=PT.flush(s);return {K,out,streak:PT.evs(ev,'streak').map(e=>[e[4],e[5]]),bounty:PT.evs(ev,'bounty').map(e=>e[4]),score:a.comp.score,peak:Math.round(a.comp.peak),wst:a.streak,best:a.comp.st.streak}})()""")
    K = r["K"]
    ok(r["out"] == [K, 2 * K + 10, 2 * K + 10 + 2 * K + 20], "kill points: plain, +10 for a double kill, double for the leader +20 for three in a row", r)
    ok(r["streak"] == [[2, 10], [3, 20]] and r["bounty"] == [2 * K] and r["score"] == r["peak"] + r["out"][2] and r["wst"] == 3 and r["best"] == 3, "streak and bounty events; score = biggest size + points", r)
    r = J(t, """(()=>{const {s,w,ps}=PT.mk([1,1]),a=w[0];a.streak=4;s.kill(a,null,'shot');PT.run(s,4.5);ps[0].wantSpawn=true;PT.run(s,1.5);const n=ps[0].worm;
      PT.place(n,PT.spot.x,PT.spot.y,0,200);PT.place(w[1],PT.spot.x,PT.spot.y+200,0,30);PT.run(s,0.1);return {streak:n.streak,alive:n.alive,leader:s.S.leader===n.id,small:(()=>{n.mass=40;w[1].mass=30;PT.run(s,0.05);return s.S.leader})()}})()""")
    ok(r["alive"] and r["streak"] == 0, "dying ends your streak", r)
    ok(r["leader"] and r["small"] == 0, "the bounty is on the biggest worm, and only once it is over 60", r)

    # ---------- frenzy ----------
    r = J(t, """(()=>{const {s}=PT.mk([1]),S=s.S;S.match.t=61;S.respawns.push({k:'p',t:10},{k:'a',t:10});const ev=PT.run(s,3);
      return {n:PT.evs(ev,'frenzy').length,on:S.match.frenzy,p:S.respawns.find(q=>q.k==='p').t,a:S.respawns.find(q=>q.k==='a').t}})()""")
    ok(r["n"] == 1 and r["on"] and abs(r["a"] - 7) < 0.05 and abs(r["p"] - 5) < 0.1, "last minute: frenzy announced once, pickups arrive twice as fast (crates do not)", r)
    r = J(t, """(()=>{const {s}=PT.mk([1]),S=s.S;S.match.t=30;PT.run(s,0.5);s.restart();PT.run(s,0.5);return {f:S.match.frenzy,aw:S.match.awards.length,pend:S.respawns.filter(q=>'pgx'.includes(q.k)).length}})()""")
    ok(r["f"] is False and r["aw"] == 0 and r["pend"] >= 1, "a new match starts calm, with pickups on their way", r)

    # ---------- taunts ----------
    r = J(t, """(()=>{const {s,w,ps}=PT.mk([1]),a=w[0];PT.place(a,PT.spot.x,PT.spot.y,0);ps[0].inp.taunt=true;let ev=PT.run(s,0.1);const n1=PT.evs(ev,'taunt');ps[0].inp.taunt=true;ev=PT.run(s,0.5);const n2=PT.evs(ev,'taunt').length;
      PT.run(s,2.5);ps[0].inp.taunt=true;const n3=PT.evs(PT.run(s,0.1),'taunt').length;return {n1:n1.length,idx:n1[0]&&n1[0][4],max:HW.TAUNTS.length,n2,n3,cnt:a.comp.st.taunt}})()""")
    ok(r["n1"] == 1 and 0 <= r["idx"] < r["max"] and r["n2"] == 0 and r["n3"] == 1 and r["cnt"] == 2, "taunt: one line, then a short cooldown", r)

    # ---------- awards ----------
    r = J(t, """(()=>{const {s,w}=PT.mk([1,2,3]),S=s.S;S.comps[0].st.veg=5;S.comps[1].st.shots=40;S.comps[1].st.hits=30;S.comps[2].st.pick=4;S.comps[2].st.taunt=6;S.comps[2].st.boost=20;S.comps[0].peak=150;
      s.endMatch('time');const A=S.match.awards;return {A,cids:S.comps.map(c=>c.cid)}})()""")
    A = r["A"]
    ok(1 <= len(A) <= 4 and all(a[0] in r["cids"] and isinstance(a[1], str) and len(a) == 3 for a in A), "awards: up to four, each for a real competitor", r)
    ok(any("VEGGIES" in a[1] and a[0] == r["cids"][0] and a[2] == 5 for a in A), "awards: the veggie eater gets the rabbit food award", A)

    # ---------- a long busy bot match with pickups everywhere ----------
    r = J(t, """(()=>{const P=HW.PCFG,keep=Object.assign({},P);P.POWERS=10;P.GUNS=10;P.POWER_WAIT=[1,2];P.GUN_WAIT=[1,2];
      const s=new HW.Sim({diff:2}),S=s.S,seen={},bad=[];let maxB=0;const t0=performance.now();
      for(let i=0;i<60*240;i++){s.step(1/60);for(const e of S.events){seen[e[0]]=(seen[e[0]]||0)+1}S.events=[];S.adds.length=0;S.rems.length=0;if(S.bullets.length>maxB)maxB=S.bullets.length;
        if(i%30===0)for(const w of S.worms){if(bad.length<5&&!(isFinite(w.x)&&isFinite(w.y)&&isFinite(w.mass)&&isFinite(w.ang)&&w.mass>0&&w.x>=0&&w.x<=HW.CFG.W&&w.y>=0&&w.y<=HW.CFG.H&&w.r>0&&w.r<=22&&!HW.MAP.hit(w.x,w.y,Math.max(0,w.r-2))))bad.push([w.x,w.y,w.mass,w.r])}}
      Object.assign(P,keep);return {seen,bad,maxB,ms:(performance.now()-t0)/(60*240)}})()""")
    ok(not r["bad"], "4 minutes of bots with pickups everywhere: no worm goes NaN, out of bounds or into an obstacle", r["bad"])
    ok(r["seen"].get("power", 0) > 5 and r["seen"].get("gun", 0) > 5, "bots do pick the things up", r["seen"])
    ok(r["maxB"] < 400 and r["ms"] < 0.25, "bullet count and sim cost stay sane with special guns in play", (r["maxB"], r["ms"]))

    # ---------- the real game: pickups on screen, HUD, sounds do not throw ----------
    t.eval("HW.App.startLocal([0])"); t.pump(1.2)
    t.eval("""(()=>{const s=HW.App.sim,m=HW.App.locals[0].me,sp=PT.spot;PT.place(m,sp.x,sp.y,0);for(let i=0;i<4;i++)s.addItem('p',i,sp.x+60+i*46,sp.y-70,0);for(let i=0;i<5;i++)s.addItem('g',i,sp.x-150+i*80,sp.y+90,0);s.dropItem('x')})()""")
    t.pump(0.5); t.shot(SP + "/pw_pickups.png")
    for i in range(5):
        t.eval("(()=>{const m=HW.App.locals[0].me;if(!m)return;m.shield=5;m.sg=%d;m.sgT=5;m.rage=%d;m.guard=%d;m.big=%d;m.sauce=%d;m.chill=%d;HW.App.locals[0].player.inp.taunt=true})()" % (i + 1, 5 * (i == 0), 5 * (i == 1), 5 * (i == 2), 5 * (i == 3), 3 * (i == 4)))
        t.touch("touchStart", [(2, 650, 250)]); t.touch("touchMove", [(2, 700, 240)]); t.pump(0.8); t.shot(SP + "/pw_gun%d.png" % i); t.touch("touchEnd", [])
    # the taunt button (a real tap), the T key
    t.eval("(()=>{window.__ta=0;const s=HW.App.sim,st=s.step;s.step=function(d){const r=st.call(this,d);for(const e of this.S.events)if(e[0]==='taunt'&&HW.App.locals[0].me&&e[3]===HW.App.locals[0].me.id)__ta++;return r};const m=HW.App.locals[0].me;if(m){m.shield=30;m.tauntT=0}})()")
    Lt = J(t, "HW.Input.touch.layout.taunt"); k = t.eval("HW.Render.canvas.getBoundingClientRect().width/HW.Render.W")
    ok(Lt["r"] * 2 * k >= 43.5, "touch: taunt button is at least 44 CSS px", Lt["r"] * 2 * k)
    t.touch("touchStart", [(5, Lt["x"] * k, Lt["y"] * k)]); t.pump(0.3); t.touch("touchEnd", []); t.pump(0.3); t.shot(SP + "/pw_taunt.png")
    ok(t.eval("__ta") == 1 and J(t, "!!(HW.App.locals[0].me&&HW.App.locals[0].me._say)"), "touch: tapping the taunt button taunts once and shows a speech bubble", t.eval("__ta"))
    ok(J(t, "(()=>{const T=HW.Input.touch;return T.move.on||T.aim.on})()") is False, "touch: the taunt tap did not start a stick")
    t.eval("HW.App.sim.S.match.t=60.4"); t.pump(1.0); t.shot(SP + "/pw_frenzy.png")
    ok(J(t, "HW.App.sim.S.match.frenzy") is True and J(t, "!!(HW.App.locals[0].view.banner&&HW.App.locals[0].view.banner.s.indexOf('FRENZY')>=0)"), "in game: the frenzy banner shows")
    t.eval("(()=>{const S=HW.App.sim.S;S.comps[0].st.veg=3;S.match.t=0.2})()"); t.pump(1.2); t.shot(SP + "/pw_results.png")
    ok(t.eval("HW.App.screen") == "results" and t.eval("document.querySelectorAll('#ui .panel').length") >= 4, "results screen shows the awards panel")
    ok(not t.errors, "no page errors", t.errors)
finally:
    b.close()
print("\n%d failed: %s" % (len(FAIL), FAIL) if FAIL else "\nall power-up checks passed")
sys.exit(1 if FAIL else 0)
