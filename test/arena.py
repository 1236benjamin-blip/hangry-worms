"""The arena: map geometry, obstacles against worms and shots, items, food and hazards, bot difficulty, the BOTS menu, spawns.
Rules are checked on private HW.Sim instances inside the page (no rendering, exact and fast); the menu part taps the real page.
  HW_URL=http://127.0.0.1:8377/index.html HW_PORT=9415 python3 test/arena.py <scratch dir> [section ...]
Sections: map worms shots items food diff menu spawns (default: all). HW_VERBOSE=1 prints the measurements behind every check."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html"); FAIL = []
ONLY = [a for a in sys.argv[2:] if not a.startswith("-")]
def want(name): return not ONLY or name in ONLY
def ok(c, msg, extra=""):
    print(("ok   " if c else "FAIL ") + msg, extra if (extra != "" and not c) or os.environ.get("HW_VERBOSE") else "")
    if not c: FAIL.append(msg)

HARNESS = r"""
window.AT = (() => {
  const CFG = HW.CFG, MAP = HW.MAP, OB = MAP.obs, PI = Math.PI;
  const INP = () => ({ mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false });
  // seeded random numbers for the probes, so a failure can be reproduced
  function rng(seed) { let a = seed | 0; return () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  // ---------- geometry worked out again from the obstacle list (x, y, w, h or x, y, r) ----------
  // Nothing below uses map.js's grid, its bounding boxes or its code: this is what the map is checked against.
  // distance from a point to the surface of one obstacle: 0 on the edge, negative (the depth) inside
  function sd(o, x, y) {
    if (o.r) return Math.hypot(x - o.x, y - o.y) - o.r;
    const dx = Math.max(o.x - x, 0, x - (o.x + o.w)), dy = Math.max(o.y - y, 0, y - (o.y + o.h));
    if (dx > 0 || dy > 0) return Math.hypot(dx, dy);
    return -Math.min(x - o.x, o.x + o.w - x, y - o.y, o.y + o.h - y);
  }
  // distance to the nearest obstacle surface (negative: inside one)
  function clear(x, y) { let m = 1e9; for (const o of OB) { const d = sd(o, x, y); if (d < m) m = d; } return m; }
  function nearest(x, y) { let m = 1e9, b = null; for (const o of OB) { const d = sd(o, x, y); if (d < m) { m = d; b = o; } } return b; }
  // gap between two obstacles
  function gap(a, b) {
    if (a.r && b.r) return Math.hypot(a.x - b.x, a.y - b.y) - a.r - b.r;
    if (a.r) return sd(b, a.x, a.y) - a.r; if (b.r) return sd(a, b.x, b.y) - b.r;
    return Math.hypot(Math.max(b.x - (a.x + a.w), a.x - (b.x + b.w), 0), Math.max(b.y - (a.y + a.h), a.y - (b.y + b.h), 0));
  }
  // point to segment distance
  function segDist(px, py, ax, ay, bx, by) { const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy, t = l2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0; return Math.hypot(ax + dx * t - px, ay + dy * t - py); }
  // do two segments cross? (orientation test)
  function segSeg(ax, ay, bx, by, cx, cy, dx, dy) {
    const o = (px, py, qx, qy, rx, ry) => (qx - px) * (ry - py) - (qy - py) * (rx - px);
    const d1 = o(cx, cy, dx, dy, ax, ay), d2 = o(cx, cy, dx, dy, bx, by), d3 = o(ax, ay, bx, by, cx, cy), d4 = o(ax, ay, bx, by, dx, dy);
    return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
  }
  // How deep does the segment a-b go into obstacle o grown by pad?  > 0: it crosses, < 0: it misses by that much.
  function segDepth(o, ax, ay, bx, by, pad) {
    if (o.r) return o.r + pad - segDist(o.x, o.y, ax, ay, bx, by);
    const x0 = o.x - pad, y0 = o.y - pad, x1 = o.x + o.w + pad, y1 = o.y + o.h + pad;
    const inside = (x, y) => Math.min(x - x0, x1 - x, y - y0, y1 - y);
    let d = Math.max(inside(ax, ay), inside(bx, by));
    const E = [[x0, y0, x1, y0], [x1, y0, x1, y1], [x1, y1, x0, y1], [x0, y1, x0, y0]];
    let cross = false; for (const e of E) if (segSeg(ax, ay, bx, by, e[0], e[1], e[2], e[3])) cross = true;
    // a segment that crosses the outline goes at least as deep as the nearest corner is far from it
    if (cross) { let m = 1e9; for (const e of E) m = Math.min(m, segDist(e[0], e[1], ax, ay, bx, by)); d = Math.max(d, Math.max(m, 1e-3)); }
    else if (d <= 0) { let m = 1e9; for (const e of E) m = Math.min(m, segDist(e[0], e[1], ax, ay, bx, by), segDist(ax, ay, e[0], e[1], e[2], e[3]), segDist(bx, by, e[0], e[1], e[2], e[3])); d = -m; }
    return d;
  }

  // the emptiest spot in the arena: nothing within `far` of it, so worms can be lined up with no obstacle in the way
  let spot = null, far = 0;
  for (let y = 300; y < CFG.H - 300; y += 40) for (let x = 300; x < CFG.W - 300; x += 40) { const d = clear(x, y); if (d > far) { far = d; spot = { x, y }; } }

  // ---------- private sims ----------
  // humans with the given characters plus `bots` bot seats (opt.botCh: their characters), spawned, the map swept clean
  function mk(chs, opt) {
    opt = opt || {}; const nb = (opt.botCh || []).length, keep = CFG.WORMS; CFG.WORMS = chs.length + nb;
    const s = new HW.Sim({ diff: opt.diff === undefined ? 1 : opt.diff }); CFG.WORMS = keep; s.keepWorms = chs.length + nb;
    const fb = s.fillBots; s.fillBots = function () { const k = CFG.WORMS; CFG.WORMS = this.keepWorms; fb.call(this); CFG.WORMS = k; };
    const ps = chs.map(ch => { const p = s.addPlayer(ch); p.inp = INP(); p.comp.lives = 99; return p; });
    for (let i = 0; i < 5; i++) s.step(1 / 60);
    // give the bot seats the characters asked for
    const seats = s.S.comps.filter(c => c.pid < 0);
    (opt.botCh || []).forEach((ch, i) => { const c = seats[i]; if (c.ch !== ch) { c.ch = ch; if (c.worm) s.kill(c.worm, null, 'left'); c.worm = null; } });
    s.fillBots(); for (let i = 0; i < 2; i++) s.step(1 / 60);
    if (!opt.keepItems) {
      // an empty floor that stays empty: no food turns up on its own (a frozen worm would eat it and spoil an exact mass check)
      sweep(s); const af = s.addFood; s.addFood = function (x, y, v) { return x === undefined ? null : af.call(this, x, y, v); };
    }
    flush(s); return { s, ps, w: ps.map(p => p.worm), bots: seats.map(c => c.worm) };
  }
  function sweep(s) { for (const it of Array.from(s.S.items.values())) s.remItem(it); s.S.respawns.length = 0; }
  function flush(s) { const e = s.S.events; s.S.events = []; s.S.adds.length = 0; s.S.rems.length = 0; return e; }
  // lay a worm out straight, head at (x, y) pointing along ang, no shields of any kind
  function place(w, x, y, ang, mass) {
    if (mass) w.mass = mass; w.x = x; w.y = y; w.ang = ang; w.aim = ang; w.shield = 0; w.mercy = 0; w.cd = 0;
    const n = HW.segCount(w.mass); w.pts.length = 0; for (let i = 0; i < n; i++) w.pts.push({ x: x - Math.cos(ang) * i * 6, y: y - Math.sin(ang) * i * 6 });
    HW.follow(w); return w;
  }
  function run(s, secs, each) { const ev = []; for (let i = 0; i < Math.round(secs * 60); i++) { if (each) each(i); s.step(1 / 60); for (const e of flush(s)) ev.push(e); } return ev; }
  const evs = (ev, k) => ev.filter(e => e[0] === k);
  const fin = w => isFinite(w.x) && isFinite(w.y) && isFinite(w.ang) && isFinite(w.aim) && isFinite(w.mass) && isFinite(w.r) && w.pts.every(p => isFinite(p.x) && isFinite(p.y));
  // hold a worm where it is: call the returned function before every step (a bot keeps thinking and shooting, it just goes nowhere)
  function pin(w) { const x = w.x, y = w.y, a = w.ang, pts = w.pts.map(p => ({ x: p.x, y: p.y })); return () => { w.x = x; w.y = y; w.ang = a; w.pts.length = pts.length; for (let i = 0; i < pts.length; i++) { w.pts[i] = w.pts[i] || {}; w.pts[i].x = pts[i].x; w.pts[i].y = pts[i].y; } HW.follow(w); }; }
  const ob = (k, f) => OB.find(o => o.k === k && (!f || f(o)));
  // the long counter in the kitchen: the cover most of the shooting checks use
  const C = ob('counter', o => o.w > o.h && o.zone === 0);
  return { mk, place, run, evs, flush, sweep, spot, far, INP, rng, sd, clear, nearest, gap, segDepth, segDist, fin, pin, ob, PI, C };
})();
"""
J = lambda t, js, timeout=120: json.loads(t.eval("JSON.stringify(%s)" % js, timeout=timeout))

# ====================================================================================================
def sec_map(t):
    """Map sanity: layout, and HW.MAP.hit / push / los / spot against brute-force geometry."""
    r = J(t, """(()=>{const M=HW.MAP,O=M.obs,R=[0,1,2,3,4].map(c=>HW.wormR(c,9999,true)),maxR=Math.max(...R);
      let minGap=1e9,minWall=1e9,pair=null,badBox=[],kinds={};
      for(let i=0;i<O.length;i++){const a=O[i];kinds[a.k]=(kinds[a.k]||0)+1;
        const x0=a.r?a.x-a.r:a.x,y0=a.r?a.y-a.r:a.y,x1=a.r?a.x+a.r:a.x+a.w,y1=a.r?a.y+a.r:a.y+a.h;
        if(a.x0!==x0||a.y0!==y0||a.x1!==x1||a.y1!==y1||a.i!==i||!(a.r>0||(a.w>0&&a.h>0)))badBox.push(i);
        minWall=Math.min(minWall,x0,y0,M.W-x1,M.H-y1);
        for(let j=i+1;j<O.length;j++){const g=AT.gap(a,O[j]);if(g<minGap){minGap=g;pair=[a.k,O[j].k,i,j]}}}
      // the layout is the same piece turned four times: every obstacle has a twin a quarter turn round the middle
      let sym=0;for(const a of O){const cx=a.r?a.x:a.x+a.w/2,cy=a.r?a.y:a.y+a.h/2,tx=M.W-cy,ty=cx;
        if(O.some(b=>b.k===a.k&&Math.abs((b.r?b.x:b.x+b.w/2)-tx)<0.01&&Math.abs((b.r?b.y:b.y+b.h/2)-ty)<0.01&&(a.r?b.r===a.r:b.w===a.h&&b.h===a.w)))sym++;}
      return {n:O.length,kinds,minGap,pair,minWall,maxR,R,badBox,sym,PAD:M.PAD,W:M.W,H:M.H,cfg:[HW.CFG.W,HW.CFG.H],far:AT.far,zones:M.zones.length,
        zoneIn:M.zones.every(z=>z.x>=0&&z.y>=0&&z.x+z.w<=M.W&&z.y+z.h<=M.H&&z.w>0&&z.h>0)}})()""")
    need = 2 * r["maxR"] + 16
    ok(r["W"] == 2400 and r["H"] == 2400 and r["cfg"] == [2400, 2400], "map: the arena is 2400 x 2400 and the sim agrees", r)
    ok(r["n"] >= 30 and all(r["kinds"].get(k, 0) >= 4 for k in ("counter", "vend", "crate", "table", "can")), "map: all five kinds of obstacle are there (%d in all)" % r["n"], r["kinds"])
    ok(not r["badBox"] and r["sym"] == r["n"], "map: bounding boxes match the shapes; the layout is four-fold symmetric", (r["badBox"], r["sym"]))
    ok(r["minGap"] > 0, "map: no two obstacles overlap", r["pair"])
    ok(r["maxR"] <= 21 and r["PAD"] >= r["maxR"] + 9, "map: the biggest worm (radius %d) and a bot's look-ahead fit the grid lookup (PAD %d)" % (r["maxR"], r["PAD"]), r)
    ok(r["minGap"] >= need, "map: every gap between obstacles lets the biggest worm through with room to spare (%.0f px, need %d)" % (r["minGap"], need), r["pair"])
    ok(r["minWall"] >= need, "map: every gap between an obstacle and a wall does too (%.0f px)" % r["minWall"], r)
    ok(r["zones"] == 5 and r["zoneIn"] and r["far"] > 200, "map: five floor zones inside the arena; there is open ground to test on", r)

    # ---- hit: the grid lookup against a scan of every obstacle ----
    r = J(t, """(()=>{const M=HW.MAP,O=M.obs,rnd=AT.rng(1234),N=60000,bad=[];let hits=0,skip=0,wrongOb=0;
      for(let n=0;n<N;n++){let x,y;const m=n%4;
        if(m===0){x=-80+rnd()*(M.W+160);y=-80+rnd()*(M.H+160)}                                  // anywhere, a little beyond the walls too
        else{const o=O[(rnd()*O.length)|0],p=M.PAD+12;x=o.x0-p+rnd()*(o.x1-o.x0+2*p);y=o.y0-p+rnd()*(o.y1-o.y0+2*p)}   // round an obstacle
        const rr=n%7===0?0:n%7===1?M.PAD:n%7===2?20:rnd()*M.PAD;
        let want=false,amb=false;for(const o of O){const d=AT.sd(o,x,y);if(Math.abs(d-rr)<1e-7)amb=true;if(o.r?d<rr:(d<rr||d<=0))want=true}
        if(amb){skip++;continue}
        const got=M.hit(x,y,rr);if(want)hits++;
        if(!!got!==want){if(bad.length<5)bad.push([x,y,rr,want,got&&got.i])}
        else if(got){const d=AT.sd(got,x,y);if(!(got.r?d<rr:(d<rr||d<=0)))wrongOb++}}
      return {N,hits,skip,bad,wrongOb}})()""")
    ok(not r["bad"] and r["wrongOb"] == 0, "MAP.hit: the grid lookup equals a scan of all obstacles on %d probes, radius 0..PAD (%d of them hits)" % (r["N"], r["hits"]), r)
    ok(r["hits"] > r["N"] * 0.15 and r["hits"] < r["N"] * 0.85 and r["skip"] < 50, "MAP.hit: the probes are a fair mix of hits and misses", r)

    # ---- push: out of everything, by the shortest way, with a unit normal ----
    r = J(t, """(()=>{const M=HW.MAP,O=M.obs,rnd=AT.rng(99),N=40000,out={x:0,y:0,nx:0,ny:0},bad=[];let moved=0,still=0,worst=0,far=0,badN=0,hitAfter=0,wrongStill=0;
      for(let n=0;n<N;n++){const o=O[(rnd()*O.length)|0],rr=n%5===0?3:n%5===1?12:n%5===2?20:n%5===3?M.PAD:rnd()*M.PAD,p=rr+6;
        const x=o.x0-p+rnd()*(o.x1-o.x0+2*p),y=o.y0-p+rnd()*(o.y1-o.y0+2*p),c0=AT.clear(x,y);
        const mv=M.push(x,y,rr,out),c1=AT.clear(out.x,out.y);
        if(!(isFinite(out.x)&&isFinite(out.y))){if(bad.length<5)bad.push(['nan',x,y,rr]);continue}
        if(Math.abs(c0-rr)<1e-7)continue;
        if(mv!==(c0<rr)){if(bad.length<5)bad.push(['moved?',x,y,rr,mv,c0])}
        if(mv){moved++;const pen=rr-c1;if(pen>worst)worst=pen;if(pen>1e-6&&bad.length<5)bad.push(['still inside',x,y,rr,c1]);
          if(Math.abs(Math.hypot(out.nx,out.ny)-1)>1e-6)badN++;
          const d=Math.hypot(out.x-x,out.y-y);if(d>far)far=d;if(d>rr-c0+1e-6&&bad.length<5)bad.push(['not the shortest way out',x,y,rr,d,rr-c0]);
          if(rr>0.05&&M.hit(out.x,out.y,rr-0.01))hitAfter++;}
        else{still++;if(out.x!==x||out.y!==y||out.nx!==0||out.ny!==0)wrongStill++}}
      return {N,moved,still,worst,far,badN,hitAfter,wrongStill,bad}})()""")
    ok(not r["bad"] and r["worst"] < 1e-6, "MAP.push: a pushed point is never inside anything (%d pushes, worst overlap %.1e px)" % (r["moved"], r["worst"]), r)
    ok(r["badN"] == 0 and r["hitAfter"] == 0 and r["wrongStill"] == 0 and r["moved"] > 5000 and r["still"] > 5000, "MAP.push: unit normal, moves only what overlaps, and MAP.hit agrees afterwards", r)

    # ---- los: symmetric, and false exactly when the segment crosses an obstacle ----
    r = J(t, """(()=>{const M=HW.MAP,O=M.obs,rnd=AT.rng(777),N=40000,bad=[];let blocked=0,open=0,asym=0,skip=0;
      for(let n=0;n<N;n++){let ax,ay,bx,by;const m=n%6,pad=n%3===0?0:n%3===1?2:rnd()*4;
        if(m===0){ax=rnd()*M.W;ay=rnd()*M.H;bx=rnd()*M.W;by=rnd()*M.H}                      // right across the arena
        else{const o=O[(rnd()*O.length)|0],p=70;ax=o.x0-p+rnd()*(o.x1-o.x0+2*p);ay=o.y0-p+rnd()*(o.y1-o.y0+2*p);
          const L=m===1?rnd()*30:rnd()*260,a=rnd()*6.283;bx=ax+Math.cos(a)*L;by=ay+Math.sin(a)*L;
          if(m===2)bx=ax;else if(m===3)by=ay;else if(m===4){bx=ax;by=ay}}                    // straight up, straight across, a single point
        let deep=-1e9;for(const o of O){const d=AT.segDepth(o,ax,ay,bx,by,pad);if(d>deep)deep=d}
        const got=M.los(ax,ay,bx,by,pad),back=M.los(bx,by,ax,ay,pad);if(got!==back)asym++;
        if(Math.abs(deep)<1e-6){skip++;continue}
        const want=deep<0;if(want)open++;else blocked++;
        if(got!==want&&bad.length<6)bad.push([ax,ay,bx,by,pad,deep,got])}
      return {N,blocked,open,asym,skip,bad}})()""")
    ok(r["asym"] == 0, "MAP.los: the same both ways round on %d segments" % r["N"], r)
    ok(not r["bad"], "MAP.los: blocked exactly when the segment crosses an obstacle (%d blocked, %d clear)" % (r["blocked"], r["open"]), r["bad"])
    ok(r["blocked"] > 5000 and r["open"] > 5000 and r["skip"] < 100, "MAP.los: the probes are a fair mix of blocked and clear", r)

    # ---- spot: random free places as the sim asks for them ----
    r = J(t, """(()=>{const M=HW.MAP,bad=[];let n=0,inSalad=0;
      for(const [edge,rr,box] of [[80,26,null],[120,26,null],[120,26,M.zones[2]],[30,14,null],[200,40,null]])for(let i=0;i<4000;i++){
        const p=M.spot(edge,rr,box);n++;const c=AT.clear(p.x,p.y);
        if(!(c>=rr-1e-6)||p.x<edge-1e-9||p.y<edge-1e-9||p.x>M.W-edge+1e-9||p.y>M.H-edge+1e-9){if(bad.length<5)bad.push([edge,rr,p.x,p.y,c])}
        if(box&&p.x>=box.x&&p.x<=box.x+box.w&&p.y>=box.y&&p.y<=box.y+box.h)inSalad++}
      // unlucky twelve times in a row (every try lands in an obstacle): the fallback must still hand back a free place
      const keep=Math.random,fb=[];
      for(const o of M.obs){const cx=o.r?o.x:o.x+o.w/2,cy=o.r?o.y:o.y+o.h/2;let k=0;const edge=120,rr=40;
        Math.random=()=>(k++%2===0?cx-edge:cy-edge)/(M.W-2*edge);const p=M.spot(edge,rr,null);Math.random=keep;
        const c=AT.clear(p.x,p.y);if(!(c>=rr-1e-6)||!isFinite(p.x)||!isFinite(p.y))fb.push([o.i,p.x,p.y,c])}
      Math.random=keep;return {n,bad,inSalad,fb}})()""")
    ok(not r["bad"], "MAP.spot: %d random spots, every one clear of obstacles by its radius and of the walls by its edge" % r["n"], r["bad"])
    ok(r["inSalad"] >= 3990, "MAP.spot: a spot asked for inside a zone is inside it", r["inSalad"])
    ok(not r["fb"], "MAP.spot: even when every try lands in an obstacle the fallback is a free place", r["fb"])

# ====================================================================================================
def sec_worms(t):
    """Obstacles block worms: drive at every kind from many angles, normal, supersized and rampaging."""
    t.eval(r"""AT.drive = function (o, a, opt) {
      const CFG = HW.CFG, { s, w } = AT.mk([opt.ch]), me = w[0], cx = o.r ? o.x : o.x + o.w / 2, cy = o.r ? o.y : o.y + o.h / 2, ext = o.r ? o.r : Math.hypot(o.w, o.h) / 2;
      const tx = cx + (opt.ox || 0), ty = cy + (opt.oy || 0), D = (o.r ? o.r : Math.min(ext, Math.abs(Math.cos(a)) * o.w / 2 + Math.abs(Math.sin(a)) * o.h / 2)) + 95;
      AT.place(me, tx + Math.cos(a) * D, ty + Math.sin(a) * D, a + Math.PI, opt.mass || 60);
      if (opt.big) me.big = 99; if (opt.rage) me.rage = 99; if (opt.sauce) me.sauce = 99; HW.follow(me);
      me.inp.mx = -Math.cos(a); me.inp.my = -Math.sin(a); me.inp.boost = !!opt.boost;
      const free = HW.CHARS[opt.ch].speed * (opt.rage ? HW.POWERS[0].speed : 1), R = { head: -1e9, body: -1e9, nan: false, dead: false, touch: -1, path: 0, minWin: 1e9, free, r: me.r, die: 0, end: 0 };
      const steps = Math.round((opt.secs || 4) * 60), d = []; let px = me.x, py = me.y;
      for (let i = 0; i < steps; i++) {
        s.step(1 / 60); R.die += AT.evs(AT.flush(s), 'die').length;
        if (!me.alive) { R.dead = true; break; } if (!AT.fin(me)) { R.nan = true; break; }
        const c = AT.clear(me.x, me.y); if (me.r - c > R.head) R.head = me.r - c;
        for (let k = 1; k < me.pts.length; k++) { const q = 3 - AT.clear(me.pts[k].x, me.pts[k].y); if (q > R.body) R.body = q; }
        if (R.touch < 0 && AT.sd(o, me.x, me.y) < me.r + 1.5) R.touch = i;
        d.push(Math.hypot(me.x - px, me.y - py)); px = me.x; py = me.y;
        if (me.x < 45 || me.y < 45 || me.x > CFG.W - 45 || me.y > CFG.H - 45) break;   // past the obstacle and at the arena wall: that is another check
      }
      // from the moment it touches: distance covered, and the slowest second
      if (R.touch >= 0) { let acc = 0; for (let i = R.touch; i < d.length; i++) { R.path += d[i]; acc += d[i]; if (i - R.touch >= 60) { acc -= d[i - 60]; if (acc < R.minWin) R.minWin = acc; } } R.secs = (d.length - R.touch) / 60; }
      R.end = AT.sd(o, me.x, me.y); return R;
    };0""")
    r = J(t, """(()=>{const O=HW.MAP.obs,pick=[AT.ob('counter',o=>o.w>o.h&&o.zone===0),AT.ob('counter',o=>o.h>o.w&&o.zone===0),AT.ob('counter',o=>o.zone===4),AT.ob('vend'),AT.ob('crate'),AT.ob('table',o=>o.zone===0),AT.ob('table',o=>o.zone===4&&o.r>40),AT.ob('can')];
      const ANG=[0,0.785,1.571,2.356,3.1416,3.927,4.712,5.498,0.3,2.0,4.1,5.9],MODES=[{},{big:1,mass:460},{rage:1,boost:1,sauce:1,mass:90},{big:1,rage:1,boost:1,mass:300}];
      const out=[];let n=0;
      for(const o of pick)for(let ai=0;ai<ANG.length;ai++)for(let mi=0;mi<MODES.length;mi++){const m=MODES[mi],ch=(n++)%5;
        // aim at the middle, and for the long counters also at a point near one end
        const offs=o.r||Math.max(o.w,o.h)<100?[[0,0]]:[[0,0],[o.w>o.h?o.w*0.4:0,o.h>o.w?o.h*0.4:0]];
        for(const f of offs){const R=AT.drive(o,ANG[ai],Object.assign({ch,ox:f[0],oy:f[1]},m));R.k=o.k;R.i=o.i;R.a=ANG[ai];R.mode=mi;R.ch=ch;out.push(R)}}
      return out})()""", 300)
    n = len(r); touched = [q for q in r if q["touch"] >= 0]
    ok(n >= 380 and len(touched) >= n * 0.9, "worms: %d drives at 8 obstacles (all five kinds) from 12 angles, 4 ways; %d ran into their obstacle" % (n, len(touched)), [(q["k"], q["a"], q["mode"]) for q in r if q["touch"] < 0][:8])
    ok(all(not q["nan"] for q in r), "worms: nothing becomes NaN", [(q["k"], q["a"], q["mode"]) for q in r if q["nan"]][:5])
    ok(all(not q["dead"] and q["die"] == 0 for q in r), "worms: no worm ever dies from an obstacle", [(q["k"], q["a"], q["mode"]) for q in r if q["dead"]][:5])
    worst = max(q["head"] for q in r)
    ok(worst < 0.01, "worms: the head never ends up inside an obstacle (worst overlap %.4f px)" % worst, [(q["k"], q["a"], q["mode"], q["head"]) for q in r if q["head"] >= 0.01][:5])
    worstB = max(q["body"] for q in r)
    ok(worstB < 0.01, "worms: body points stay out too (worst overlap %.4f px)" % worstB, [(q["k"], q["a"], q["mode"], q["body"]) for q in r if q["body"] >= 0.01][:5])
    slow = [q for q in touched if q["secs"] >= 1.5 and q["path"] / q["secs"] < 0.4 * q["free"]]
    stuck = [q for q in touched if q["minWin"] < 1e8 and q["minWin"] < 12]
    ratio = sorted(q["path"] / q["secs"] / q["free"] for q in touched if q["secs"] >= 1.5)
    ok(not slow, "worms: after hitting an obstacle a worm slides on at a good pace (slowest %.0f%% of its speed, median %.0f%%)" % (100 * ratio[0], 100 * ratio[len(ratio) // 2]), [(q["k"], q["a"], q["mode"], q["ch"], round(q["path"] / q["secs"]), q["free"]) for q in slow][:6])
    ok(not stuck, "worms: it never freezes: at least 12 px in every second (slowest second %.0f px)" % min(q["minWin"] for q in touched if q["minWin"] < 1e8), [(q["k"], q["a"], q["mode"], q["ch"], round(q["minWin"])) for q in stuck][:6])
    big = [q for q in r if q["mode"] in (1, 3)]
    ok(all(q["r"] >= 17 for q in big if q["mode"] == 1) and max(q["r"] for q in big) == 20, "worms: the supersized ones really are big (radius up to %d)" % max(q["r"] for q in big), sorted(set(q["r"] for q in big)))

    # ---- put inside an obstacle by force, and growing while leaning on one ----
    r = J(t, """(()=>{const out={in:[],grow:[]};
      for(const o of [AT.ob('counter'),AT.ob('vend'),AT.ob('crate'),AT.ob('table'),AT.ob('can')]){
        const {s,w}=AT.mk([1]),me=w[0],cx=o.r?o.x:o.x+o.w/2,cy=o.r?o.y:o.y+o.h/2;
        AT.place(me,cx+1,cy+2,0.7,80);me.x=cx+1;me.y=cy+2;for(const p of me.pts){p.x=cx+1;p.y=cy+2}
        AT.run(s,0.05);const c=AT.clear(me.x,me.y);let b=1e9;for(let k=1;k<me.pts.length;k++)b=Math.min(b,AT.clear(me.pts[k].x,me.pts[k].y));
        out.in.push([o.k,c-me.r,b-3,me.alive,AT.fin(me)]);
        // leaning on it, then supersized: the bigger head must be moved out, not left overlapping
        const y0=(o.r?o.y-o.r:o.y)-me.r;AT.place(me,cx,y0-0.2,Math.PI/2,460);me.inp.mx=0;me.inp.my=1;AT.run(s,0.3);const r0=me.r;me.big=99;AT.run(s,0.1);
        out.grow.push([o.k,r0,me.r,AT.clear(me.x,me.y)-me.r,me.alive,AT.fin(me)])}
      return out})()""")
    ok(all(q[1] > -0.01 and q[2] > -0.01 and q[3] and q[4] for q in r["in"]), "worms: a worm that somehow is inside an obstacle is put outside at once, alive", r["in"])
    ok(all(q[2] > q[1] and q[3] > -0.01 and q[4] and q[5] for q in r["grow"]), "worms: supersizing while leaning on an obstacle does not leave the head inside it", r["grow"])

    # ---- the arena walls and corners ----
    r = J(t, """(()=>{const W=HW.CFG.W,H=HW.CFG.H,out=[];
      for(const [x,y,a,big] of [[W/2+200,60,-1.571,0],[W-60,H/2+200,0,1],[W/2-200,H-60,1.571,0],[60,H/2-200,3.1416,1],[70,70,-2.356,0],[W-70,70,-0.785,1],[W-70,H-70,0.785,0],[70,H-70,2.356,1],[W/2,90,-1.2,1]]){
        const {s,w}=AT.mk([out.length%5]),me=w[0];AT.place(me,x,y,a,big?460:60);if(big)me.big=99;me.inp.mx=Math.cos(a);me.inp.my=Math.sin(a);
        let bad=0,px=me.x,py=me.y,path=0;AT.run(s,4,()=>{if(me.x<me.r-1e-6||me.y<me.r-1e-6||me.x>W-me.r+1e-6||me.y>H-me.r+1e-6)bad++;path+=Math.hypot(me.x-px,me.y-py);px=me.x;py=me.y});
        out.push([bad,me.alive,AT.fin(me),Math.round(path),me.r])}
      return out})()""")
    ok(all(q[0] == 0 and q[1] and q[2] for q in r), "worms: walls and corners hold every worm inside the arena, alive", r)
    ok(all(q[3] > 60 for q in r[:4] + r[8:]), "worms: a worm steered into a wall slides along it", [q[3] for q in r])
    # nobody steering (thumb off the stick): the worm drifts into a wall, slides along it and reaches a corner
    r = J(t, """(()=>{const W=HW.CFG.W,H=HW.CFG.H,out=[];
      for(let c=0;c<4;c++)for(const da of [-0.6,-0.3,-0.1,0,0.1,0.3,0.6])for(const off of [0,25,60]){
        const cx=c===0||c===3?0:W,cy=c<2?0:H,a=Math.atan2(cy-H/2,cx-W/2)+da,{s,w}=AT.mk([out.length%5]),me=w[0];
        AT.place(me,cx-Math.cos(a)*140-Math.sin(a)*off+(cx?-10:10),cy-Math.sin(a)*140+Math.cos(a)*off+(cy?-10:10),a,60);
        let px=me.x,py=me.y;const d=[];AT.run(s,6,()=>{d.push(Math.hypot(me.x-px,me.y-py));px=me.x;py=me.y});
        let last=0;for(let i=d.length-120;i<d.length;i++)last+=d[i];
        out.push([c,da,off,Math.round(last),Math.round(me.x),Math.round(me.y),me.alive&&AT.fin(me)])}
      return out})()""")
    froz = [q for q in r if q[3] < 20]
    ok(all(q[6] for q in r), "worms: drifting into an arena corner with nobody steering never kills or breaks a worm (%d drifts)" % len(r), [q for q in r if not q[6]][:4])
    ok(not froz, "sim.js: a worm that drifts into an arena corner with nobody steering turns out of it instead of sitting there for good (%d of %d stayed wedged)" % (len(froz), len(r)), froz[:6])

# ====================================================================================================
def sec_shots(t):
    """Obstacles block shots: every character gun, rockets, a muzzle poked into cover, auto-aim, bots."""
    t.eval(r"""// shooter above the counter firing straight down at a worm lying across the line of fire behind it (cover = true),
    // or exactly the same line-up on open ground (cover = false)
    AT.shoot = function (ch, cover, sg) {
      const o = AT.C, { s, w } = AT.mk([ch, 1]), a = w[0], v = w[1], ax = cover ? o.x + o.w / 2 : AT.spot.x, ay = cover ? o.y - 70 : AT.spot.y - 70 - o.h / 2;
      AT.place(a, ax, ay, Math.PI / 2, 60); AT.place(v, ax + 40, ay + 70 + o.h + 30, 0, 60); a.stuck = v.stuck = 99; a.ammo = HW.CHARS[ch].gun.max; if (sg) { a.sg = sg; a.sgT = 99; }
      a.inp.ay = 1; a.inp.fire = true; const m = v.mass, ev = AT.run(s, 2.6), cl = AT.evs(ev, 'clang');
      return { loss: m - v.mass, clang: cl.length, near: cl.filter(e => e[2] <= o.y + 1).length, boom: AT.evs(ev, 'boom').length, hit: AT.evs(ev, 'hit').length, shots: AT.evs(ev, 'shot').length, kind: (AT.evs(ev, 'shot')[0] || [])[3], alive: v.alive, far: AT.far };
    };0""")
    names = J(t, "HW.CHARS.map(c=>c.gun.name)")
    for ch in range(5):
        c = J(t, "AT.shoot(%d,true)" % ch); o = J(t, "AT.shoot(%d,false)" % ch)
        ok(c["shots"] > 0 and c["kind"] == ch and c["loss"] == 0 and c["hit"] == 0 and c["clang"] > 0 and c["near"] == c["clang"], "shots: %s - a worm directly behind a counter takes no damage, the shots clang off the near side" % names[ch], c)
        ok(o["shots"] > 0 and o["loss"] > 2 and o["hit"] > 0, "shots: %s - the same shot with a clear line does damage" % names[ch], o)
    # every obstacle kind stops a bullet (the skewer: straight and piercing)
    r = J(t, """(()=>{const out=[];for(const o of [AT.ob('vend'),AT.ob('crate'),AT.ob('table'),AT.ob('can'),AT.ob('counter',q=>q.h>q.w)]){
      const {s,w}=AT.mk([3,1]),a=w[0],v=w[1],cx=o.r?o.x:o.x+o.w/2,cy=o.r?o.y:o.y+o.h/2,hw=o.r||o.w/2;
      AT.place(a,cx-hw-60,cy,0,60);AT.place(v,cx+hw+30,cy-40,-Math.PI/2,60);a.stuck=v.stuck=99;a.inp.ax=1;a.inp.fire=true;const m=v.mass,ev=AT.run(s,2);
      out.push([o.k,m-v.mass,AT.evs(ev,'clang').length,AT.evs(ev,'shot').length])}return out})()""")
    ok(all(q[1] == 0 and q[2] > 0 and q[2] >= q[3] - 1 for q in r), "shots: vending machines, crates, tables, cans and upright counters stop bullets as well", r)

    # ---- rocket blast: hidden behind the counter = safe, beside the blast = hurt ----
    r = J(t, """(()=>{const o=AT.C,{s,w}=AT.mk([4,1,1]),j=w[0],hid=w[1],side=w[2],cx=o.x+o.w/2;
      AT.place(j,cx,o.y-150,Math.PI/2,60);AT.place(hid,cx+40,o.y+o.h+30,0,60);AT.place(side,cx+45,o.y-28,Math.PI,60);j.stuck=hid.stuck=side.stuck=99;j.ammo=1;j.inp.ay=1;j.inp.fire=true;
      const mh=hid.mass,mj=j.mass,ev=AT.run(s,2.5),b=AT.evs(ev,'boom')[0]||[],dmg=id=>AT.evs(ev,'hit').filter(e=>e[3]===id).reduce((a,e)=>a+e[4],0);
      // would the hidden worm have been in the blast if the counter were not there?
      const R=HW.CHARS[4].gun.blast;let dh=1e9;for(const p of hid.pts)dh=Math.min(dh,Math.hypot(p.x-b[1],p.y-b[2]));
      return {booms:AT.evs(ev,'boom').length,by:b[2],top:o.y,hid:mh-hid.mass,hidHit:dmg(hid.id),side:dmg(side.id),self:mj-j.mass,inBlast:dh-hid.r<R,dh,clang:AT.evs(ev,'clang').length}})()""")
    ok(r["booms"] == 1 and r["clang"] == 1 and r["by"] <= r["top"] and r["inBlast"], "rocket: explodes on the near side of the counter, with a worm inside the blast radius behind it", r)
    ok(r["hid"] == 0 and r["hidHit"] == 0, "rocket: the worm hidden behind the counter is not hurt", r)
    ok(r["side"] > 5 and r["self"] == 0, "rocket: the worm beside the blast on the near side is", r)

    # ---- a muzzle poked into (or past) an obstacle cannot shoot through it ----
    r = J(t, """(()=>{const o=AT.C,out=[];
      for(let g=0;g<HW.GUNS.length;g++)for(const big of [0,1]){
        const ch=g<5?g:2,{s,w}=AT.mk([ch,1]),a=w[0],v=w[1],cx=o.x+o.w/2;
        AT.place(a,cx,o.y-50,Math.PI/2,big?460:60);if(big){a.big=99;HW.follow(a)}AT.place(a,cx,o.y-a.r-0.4,Math.PI/2);
        AT.place(v,cx+40,o.y+o.h+11,0,60);a.stuck=v.stuck=99;a.ammo=20;if(g>=5){a.sg=g-4;a.sgT=99}a.inp.ay=1;a.inp.fire=true;
        const mz=a.r+6+HW.gunSprOf(a).len,my=a.y+mz,m=v.mass,ev=AT.run(s,1.6);
        let through=0;for(const b of s.S.bullets)if(b.y>o.y+o.h)through++;
        out.push({g,big,r:a.r,poke:my-o.y,loss:m-v.mass,shots:AT.evs(ev,'shot').length,stop:AT.evs(ev,'clang').length,through})}
      return out})()""")
    ok(all(q["poke"] > 5 for q in r), "muzzle: with the head against the counter every gun's muzzle is inside it (%d set-ups)" % len(r), [(q["g"], q["poke"]) for q in r if q["poke"] <= 0])
    ok(all(q["shots"] > 0 and q["loss"] == 0 and q["stop"] > 0 and q["through"] == 0 for q in r), "muzzle: no gun can shoot through the counter from there, big worm or not", [q for q in r if q["loss"] or not q["stop"] or q["through"]][:4])
    r = J(t, """(()=>{const o=AT.ob('crate'),out=[];
      for(const g of [0,3,5,8]){const ch=g<5?g:3,{s,w}=AT.mk([ch,1]),a=w[0],v=w[1],aim=-Math.PI/6;
        AT.place(a,o.x-8.5,o.y+6,aim,60);a.stuck=99;a.ammo=20;if(g>=5){a.sg=g-4;a.sgT=99}
        const G=HW.gunOf(a),mz=a.r+6+HW.gunSprOf(a).len,mx=a.x+Math.cos(aim)*mz,my=a.y+Math.sin(aim)*mz;
        // the target lies across the line of fire, 75 px out, round the corner
        const tx=a.x+Math.cos(aim)*75,ty=a.y+Math.sin(aim)*75;AT.place(v,tx+Math.cos(aim+1.571)*40,ty+Math.sin(aim+1.571)*40,aim+1.571,60);v.stuck=99;
        a.inp.ax=Math.cos(aim);a.inp.ay=Math.sin(aim);a.inp.fire=true;const m=v.mass,ev=AT.run(s,1.5);
        out.push({g,muzzleFree:!HW.MAP.hit(mx,my,G.br*0.5),lineClear:AT.segDepth(o,a.x,a.y,mx,my,0)<0,loss:m-v.mass,stop:AT.evs(ev,'clang').length,shots:AT.evs(ev,'shot').length})}
      return out})()""")
    ok(all(q["muzzleFree"] and not q["lineClear"] for q in r), "muzzle: (set-up) round a crate's corner the muzzle is in the open but the gun barrel crosses the crate", r)
    ok(all(q["shots"] > 0 and q["loss"] == 0 and q["stop"] > 0 for q in r), "muzzle: a gun poked past a corner cannot shoot what is behind the corner", r)

    # ---- keyboard / trigger auto-aim ----
    r = J(t, """(()=>{const o=AT.C,cx=o.x+o.w/2,out={};
      {const {s,w}=AT.mk([3,1]),a=w[0],v=w[1];AT.place(a,cx,o.y-60,Math.PI/2,60);AT.place(v,cx+40,o.y+o.h+30,0,60);a.stuck=v.stuck=99;
        out.covered=s.autoAim(a);a.inp.auto=true;a.inp.fire=true;const m=v.mass;AT.run(s,1.5);out.coveredAim=a.aim;out.coveredLoss=m-v.mass}
      {const {s,w}=AT.mk([3,1,1]),a=w[0],v=w[1],u=w[2];AT.place(a,cx,o.y-60,Math.PI/2,60);AT.place(v,cx+40,o.y+o.h+30,0,60);AT.place(u,cx+150,o.y-30,0,60);a.stuck=v.stuck=u.stuck=99;
        const g=s.autoAim(a);out.other=g;let best=9;for(const p of u.pts)best=Math.min(best,Math.abs(HW.util.angDiff(Math.atan2(p.y-a.y,p.x-a.x),g)));out.otherErr=g===null?9:best;
        a.inp.auto=true;a.inp.fire=true;const mv=v.mass,mu=u.mass;AT.run(s,1.5);out.otherLoss=mu-u.mass;out.hidLoss=mv-v.mass}
      {const {s,w}=AT.mk([3,1]),a=w[0],v=w[1],sp=AT.spot;AT.place(a,sp.x,sp.y-90,Math.PI/2,60);AT.place(v,sp.x+40,sp.y+36,0,60);a.stuck=v.stuck=99;
        const g=s.autoAim(a);out.open=g;a.inp.auto=true;a.inp.fire=true;const m=v.mass;AT.run(s,1.5);out.openLoss=m-v.mass}
      return out})()""")
    ok(r["covered"] is None and abs(r["coveredAim"] - 1.5708) < 0.01 and r["coveredLoss"] == 0, "auto-aim: a worm behind cover is ignored (the gun keeps pointing where the worm is heading)", r)
    ok(r["other"] is not None and r["otherErr"] < 0.01 and r["otherLoss"] > 0 and r["hidLoss"] == 0, "auto-aim: it picks the worm in the open instead of the nearer one behind cover", r)
    ok(r["open"] is not None and r["openLoss"] > 0, "auto-aim: the same worm with a clear line is aimed at and hit", r)

    # ---- bots do not waste shots on what is behind a counter ----
    r = J(t, """(()=>{const o=AT.C,cx=o.x+o.w/2,go=(cover)=>{const {s,w,bots}=AT.mk([1],{botCh:[3],diff:2}),h=w[0],b=bots[0],sp=AT.spot;
        const bx=cover?cx:sp.x,by=cover?o.y-45:sp.y-45-o.h/2;AT.place(b,bx,by,Math.PI/2,60);AT.place(h,bx+40,by+45+o.h+30,0,60);h.stuck=99;b.ammo=40;b.abil=99;s.S.match.t=200;
        const hold=AT.pin(b),m=h.mass;let shots=0;const ev=AT.run(s,8,()=>{hold();h.mercy=0;h.shield=0;b.shield=0;s.S.match.t=200});
        return {shots:AT.evs(ev,'shot').filter(e=>e[4]===b.id).length,loss:m-h.mass}};
      return {cover:go(true),open:go(false)}})()""")
    ok(r["cover"]["shots"] == 0 and r["cover"]["loss"] == 0, "bots: a hard bot 80 px from a human behind a counter holds its fire for 8 s", r)
    ok(r["open"]["shots"] > 0 and r["open"]["loss"] > 0, "bots: the same bot with a clear line shoots (and hits)", r)

# ====================================================================================================
def sec_items(t):
    """Items after minutes of bot play: nothing inside an obstacle, counts add up, food settles, the litter cap holds."""
    r = J(t, """(()=>{const C=HW.CFG,P=HW.PCFG,out=[],MIN=5;
      for(const diff of [0,2]){const s=new HW.Sim({diff}),S=s.S,p=s.addPlayer(1);p.inp=AT.INP();p.comp.lives=1e9;
        const R={diff,inside:[],nIn:0,oob:0,nan:0,drift:[],stock:[],fsum:0,fn:0,fmax:0,deaths:0,kmax:{a:0,v:0,m:0,p:0,g:0,x:0},head:-1e9,causes:{},eat:0,seen:{}};
        for(let i=0;i<3600*MIN;i++){S.match.t=200;
          // the human is a passenger: it swims in slow circles and comes back when it dies
          if(!p.worm||!p.worm.alive){if(p.deadT>3)p.wantSpawn=true}else{const a=S.t*0.5;p.inp.mx=Math.cos(a);p.inp.my=Math.sin(a)}
          s.step(1/60);
          for(const e of S.events){R.seen[e[0]]=1;if(e[0]==='die'){R.deaths++;R.causes[e[5]]=(R.causes[e[5]]||0)+1}else if(e[0]==='eat')R.eat++}S.events=[];S.adds.length=0;S.rems.length=0;
          if(S.counts.f>R.fmax)R.fmax=S.counts.f;
          if(i%10===0){
            for(const it of S.items.values()){if(!(isFinite(it.x)&&isFinite(it.y)&&isFinite(it.v))){R.nan++;continue}
              if(it.x<0||it.y<0||it.x>C.W||it.y>C.H)R.oob++;
              const c=AT.clear(it.x,it.y);if(c<=0){R.nIn++;if(R.inside.length<6)R.inside.push([it.k,it.v,Math.round(it.x),Math.round(it.y),+c.toFixed(1),AT.nearest(it.x,it.y).k,(i/60)|0])}}
            for(const w of S.worms){const q=w.r-AT.clear(w.x,w.y);if(q>R.head)R.head=q}}
          if(i%60===0){const cn={f:0,a:0,v:0,m:0,p:0,g:0,x:0};for(const it of S.items.values())cn[it.k]=(cn[it.k]||0)+1;
            for(const k in cn)if(cn[k]!==S.counts[k]&&R.drift.length<5)R.drift.push([k,cn[k],S.counts[k],i]);
            if(Object.keys(cn).sort().join('')!=='afgmpvx'||Object.keys(S.counts).sort().join('')!=='afgmpvx')R.drift.push(['kinds',Object.keys(cn).join(''),Object.keys(S.counts).join('')]);
            for(const k in R.kmax)if(S.counts[k]>R.kmax[k])R.kmax[k]=S.counts[k];
            // what lies around plus what is on its way is always the full stock
            const pend=k=>S.respawns.filter(q=>q.k===k).length;
            for(const [k,want] of [['a',C.AMMO],['v',C.VEG],['m',C.SHROOM],['p',P.POWERS],['g',P.GUNS],['x',1]])if(S.counts[k]+pend(k)!==want&&R.stock.length<5)R.stock.push([k,S.counts[k],pend(k),want,i]);
            if(i>=3600){R.fsum+=S.counts.f;R.fn++}}}
        R.fmean=R.fsum/R.fn;R.counts=S.counts;R.size=S.items.size;out.push(R)}
      return {runs:out,FOOD:C.FOOD,MIN,stock:{a:C.AMMO,v:C.VEG,m:C.SHROOM,p:P.POWERS,g:P.GUNS,x:1}}})()""", 400)
    F = r["FOOD"]
    for q in r["runs"]:
        nm = "items (%s bots, %d min)" % (["easy", "intermediate", "hard"][q["diff"]], r["MIN"])
        ok(q["deaths"] >= 10 and q["eat"] > 500 and all(k in q["seen"] for k in ("shot", "hit", "clang", "drop")), "%s: a lively match (%d deaths, %d bites)" % (nm, q["deaths"], q["eat"]), q["seen"])
        ok(q["nIn"] == 0 and q["oob"] == 0 and q["nan"] == 0, "%s: no item of any kind is ever inside an obstacle or outside the arena" % nm, (q["nIn"], q["oob"], q["nan"], q["inside"]))
        ok(not q["drift"] and sum(q["counts"].values()) == q["size"], "%s: the per-kind item counts match S.counts (f a v m p g x)" % nm, q["drift"])
        ok(not q["stock"] and all(q["kmax"][k] <= r["stock"][k] for k in r["stock"]), "%s: crates, veggies, mushrooms and pickups: lying around + on their way = the full stock, always" % nm, (q["stock"], q["kmax"]))
        ok(F * 0.9 <= q["fmean"] <= F * 1.5 and q["fmax"] <= 520 + 100, "%s: food settles near CFG.FOOD (%d): mean %.0f, most ever %d, under the litter cap" % (nm, F, q["fmean"], q["fmax"]), q)
        ok(q["head"] < 0.01, "%s: no worm's head is ever inside an obstacle (bots and deaths included)" % nm, q["head"])
        ok(all(c in ("shot", "crash", "bonk", "fart", "puke", "rampage", "left") for c in q["causes"]) and q["causes"].get("left", 0) <= 1, "%s: every death has a real cause (shot, crash, bonk, fart, puke, rampage), none is an obstacle" % nm, q["causes"])
    # the litter cap itself, and what it throws away first
    r = J(t, """(()=>{const {s}=AT.mk([1]),S=s.S,sp=AT.spot,rnd=AT.rng(5);const far=()=>[200+rnd()*400,1700+rnd()*500];
      for(let i=0;i<300;i++){const q=far();s.addFood(q[0],q[1],8)}for(let i=0;i<400;i++){const q=far();s.addFood(q[0],q[1],1)}
      const before=S.counts.f;AT.run(s,1);let big=0,crumb=0,bad=0;for(const it of S.items.values())if(it.k==='f'){if(it.v>=HW.CFG.BIG)big++;else crumb++;if(AT.clear(it.x,it.y)<=0)bad++}
      for(let i=0;i<600;i++){const q=far();s.addFood(q[0],q[1],5)}AT.run(s,1.5);let big2=0;for(const it of S.items.values())if(it.k==='f'&&it.v>=HW.CFG.BIG)big2++;
      return {before,after:S.counts.f,big,crumb,bad,after2:S.counts.f,big2}})()""")
    ok(r["before"] >= 700 and r["after"] <= 521 and r["big"] >= 300 and r["bad"] == 0, "items: 700 pieces of litter are cut back to the cap (520) within a second, crumbs first", r)
    ok(r["after2"] <= 521, "items: with nothing but proper food lying around the cap still holds", r)
    # food and a worm on opposite sides of a counter
    r = J(t, """(()=>{const o=AT.C,{s,w}=AT.mk([0]),me=w[0],cx=o.x+o.w/2;
      AT.place(me,cx,o.y-60,Math.PI/2,460);me.big=99;HW.follow(me);AT.place(me,cx,o.y-me.r-0.4,Math.PI/2);me.stuck=99;
      const er=me.r+HW.CHARS[0].eat*HW.POWERS[1].eat,it=s.addFood(cx+6,o.y+o.h+13,5),d0=Math.hypot(it.x-me.x,it.y-me.y),y0=it.y;
      let min=1e9;const m=me.mass;AT.run(s,1.5,()=>{if(s.S.items.has(it.id)){const c=AT.clear(it.x,it.y);if(c<min)min=c}});
      return {er,d0,inReach:d0<er,min,moved:it.y-y0,eaten:!s.S.items.has(it.id),gain:me.mass-m}})()""")
    ok(r["inReach"], "items: (set-up) food lies behind a counter within the eating reach of a supersized Ben on the other side", r)
    ok(r["min"] > 0 and not r["eaten"], "sim.js: food is not sucked through a counter by a worm on the other side", r)

# ====================================================================================================
def sec_food(t):
    """Food values and eating, veggies, mushrooms, the spawn shield."""
    r = J(t, """(()=>{const C=HW.CFG,out={C:{BIG:C.BIG,FOOD:C.FOOD,MIN:C.MIN_MASS,SLOW_T:C.SLOW_T,SLOW_MULT:C.SLOW_MULT,TRIP_T:C.TRIP_T,VEG_LOSS:C.VEG_LOSS,SHIELD:C.SHIELD},FOODV:HW.FOODV};
      {const s=new HW.Sim({diff:1}),vals={};let bad=0,n=0,cls=0;
        for(const it of s.S.items.values())if(it.k==='f'){n++;vals[it.v]=(vals[it.v]||0)+1;if(it.v<C.BIG)bad++;if(HW.FOODV[HW.FOOD[it.type].v]!==it.v)cls++}
        let later=0;for(let i=0;i<300;i++){const it=s.addFood();if([3,5,8].indexOf(it.v)<0||it.v<C.BIG||AT.clear(it.x,it.y)<14-1e-6)later++}
        // food made with a value gets a picture of the right class: snack, meal or feast
        let art=0;for(const v of [1,3,5,8,30])for(let i=0;i<40;i++){const it=s.addFood(500,1500,v),k=HW.FOOD[it.type].v;if(k!==(v>=7?3:v>=4?2:1))art++}
        out.fresh={n,vals,bad,cls,later,art}}
      {const {s,w}=AT.mk([1]),me=w[0],sp=AT.spot;AT.place(me,sp.x,sp.y,0,50);me.stuck=99;out.eat=[];
        for(const v of [3,5,8,1,30]){const m=me.mass;s.addFood(me.x+4,me.y,v);const e=AT.evs(AT.run(s,0.05),'eat');out.eat.push([v,me.mass-m,e.length,e[0]&&e[0][4],s.S.counts.f])}
        // out of reach it is left alone; within eating range it is pulled in
        const far=s.addFood(me.x+me.r+HW.CHARS[1].eat+12,me.y,5),nearIt=s.addFood(me.x,me.y+me.r+HW.CHARS[1].eat-3,5),m=me.mass;AT.run(s,0.6);
        out.reach={farLeft:s.S.items.has(far.id),nearEaten:!s.S.items.has(nearIt.id),gain:me.mass-m}}
      {const res=[];for(const m0 of [300,200,60,20,C.MIN_MASS+3,C.MIN_MASS+1,C.MIN_MASS]){const {s,w}=AT.mk([1]),me=w[0],sp=AT.spot;AT.place(me,sp.x,sp.y,0,m0);me.stuck=99;me.mass=m0;me.abil=0;
          s.addItem('v',0,me.x+3,me.y,0);const e=AT.evs(AT.run(s,0.05),'veg')[0]||[];
          res.push({m0,loss:m0-me.mass,want:Math.max(0,Math.min(m0-C.MIN_MASS-2,3+m0*C.VEG_LOSS)),slow:me.slow,alive:me.alive,ev:e[4],n:e.length?1:0,resp:s.S.respawns.filter(q=>q.k==='v').length,left:s.S.counts.v})}
        out.veg=res;
        // a whole salad bar, one veggie after another
        const {s,w}=AT.mk([2]),me=w[0],sp=AT.spot;AT.place(me,sp.x,sp.y,0,100);me.stuck=99;let min=1e9,die=0;
        for(let i=0;i<40;i++){s.addItem('v',i%HW.vegSpr.length,me.x+3,me.y,0);die+=AT.evs(AT.run(s,0.04),'die').length;if(me.mass<min)min=me.mass}
        out.salad={min,die,alive:me.alive,mass:me.mass,st:me.comp.st.veg}}
      {const {s,w}=AT.mk([1]),me=w[0],sp=AT.spot;AT.place(me,sp.x-220,sp.y,0,80);me.inp.mx=1;AT.run(s,0.5);let x=me.x;AT.run(s,1);const base=me.x-x;
        s.addItem('v',0,me.x+10,me.y,0);AT.run(s,0.2);const got=me.slow>0;x=me.x;AT.run(s,1);const slowed=me.x-x;let n=72;while(me.slow>0&&n<2000){s.step(1/60);n++}AT.flush(s);
        x=me.x;AT.run(s,1);out.slow={base,slowed,got,secs:n/60,after:me.x-x}}
      {const {s,w}=AT.mk([3]),me=w[0],sp=AT.spot;AT.place(me,sp.x-150,sp.y,0,60);me.stuck=99;me.abil=0;
        s.addItem('m',0,me.x+3,me.y,0);const e=AT.evs(AT.run(s,0.05),'shroom');const t0=me.trip,resp=s.S.respawns.filter(q=>q.k==='m').length;let n=3;while(me.trip>0&&n<2000){s.step(1/60);n++}AT.flush(s);
        out.shroom={t0,ev:e.length,secs:n/60,resp,alive:me.alive,st:me.comp.st.shr};
        // tripping: the worm weaves and the gun sways; sober: dead straight
        const go=(trip)=>{const {s,w}=AT.mk([3]),me=w[0];AT.place(me,sp.x-200,sp.y,0,60);me.inp.mx=1;me.inp.ax=1;me.inp.fire=true;me.ammo=40;if(trip)me.trip=20;
          let wob=0,lo=9,hi=-9;const seen=new Set();AT.run(s,3,()=>{if(Math.abs(me.ang)>wob)wob=Math.abs(me.ang);for(const b of s.S.bullets)if(!seen.has(b.id)){seen.add(b.id);const a=Math.atan2(b.vy,b.vx);if(a<lo)lo=a;if(a>hi)hi=a}});
          return {wob,sway:hi-lo,shots:seen.size}};
        out.trip=go(true);out.sober=go(false)}
      {const {s,w}=AT.mk([1]),me=w[0],sp=AT.spot;AT.place(me,sp.x,sp.y,0,80);me.stuck=99;me.shield=3;me.abil=40;const m=me.mass;
        s.addItem('v',0,me.x+3,me.y,0);s.addItem('m',0,me.x-3,me.y,0);const ev=AT.run(s,0.05);
        out.shield={loss:m-me.mass,slow:me.slow,trip:me.trip,abil:me.abil,veg:AT.evs(ev,'veg').length,shr:AT.evs(ev,'shroom').length,gone:s.S.counts.v===0&&s.S.counts.m===0,resp:s.S.respawns.map(q=>q.k).sort().join(''),st:[me.comp.st.veg,me.comp.st.shr],shieldLeft:me.shield}}
      {const s=new HW.Sim({diff:1}),p=s.addPlayer(2);p.inp=AT.INP();s.step(1/60);const me=p.worm,s0=me.shield,cd0=me.cd;let n=1;while(me.shield>0&&n<2000){s.step(1/60);n++;p.worm.x=AT.spot.x;p.worm.y=AT.spot.y}
        out.spawn={s0,cd0,secs:n/60}}
      return out})()""")
    C = r["C"]; f = r["fresh"]
    ok(r["FOODV"] == [0, 3, 5, 8] and C["BIG"] == 3 and f["n"] == C["FOOD"], "food: a fresh arena has CFG.FOOD (%d) pieces; a snack, a meal and a feast are worth 3, 5 and 8" % C["FOOD"], r["FOODV"])
    ok(sorted(f["vals"].keys()) == ["3", "5", "8"] and f["bad"] == 0 and f["cls"] == 0, "food: all of it is worth 3, 5 or 8 and so at least CFG.BIG (drawn double size)", f)
    ok(f["later"] == 0 and f["art"] <= 50, "food: food that turns up later is the same and never in an obstacle; dropped food gets a picture that suits its value", f)
    ok(all(q[1] == q[0] and q[2] == 1 and q[3] == q[0] and q[4] == 0 for q in r["eat"]) and len(r["eat"]) == 5, "food: eating adds exactly its value to the worm's mass", r["eat"])
    ok(r["reach"]["farLeft"] and r["reach"]["nearEaten"] and r["reach"]["gain"] == 5, "food: pulled in from eating range, left alone beyond it", r["reach"])
    ok(all(abs(q["loss"] - q["want"]) < 1e-9 and q["n"] == 1 and q["ev"] == round(q["loss"]) for q in r["veg"]), "veggies: you shrink by 3 + 10% of your mass (less when nearly at the minimum)", r["veg"])
    ok(all(q["alive"] and q["m0"] - q["loss"] >= min(q["m0"], C["MIN"] + 2) - 1e-9 for q in r["veg"]) and r["veg"][-1]["loss"] == 0 and r["veg"][0]["loss"] == 33, "veggies: never kill and never take a worm below the minimum", r["veg"])
    ok(all(abs(q["slow"] - C["SLOW_T"]) < 0.06 and q["resp"] == 1 and q["left"] == 0 for q in r["veg"]), "veggies: slow you for CFG.SLOW_T (%.1f s); another one is on its way" % C["SLOW_T"], r["veg"])
    sl = r["salad"]
    ok(sl["alive"] and sl["die"] == 0 and sl["min"] >= C["MIN"] + 2 - 1e-9 and sl["st"] == 40, "veggies: 40 in a row leave a worm tiny (mass %.1f) but alive" % sl["mass"], sl)
    s = r["slow"]
    ok(s["got"] and abs(s["slowed"] / s["base"] - C["SLOW_MULT"]) < 0.03 and abs(s["secs"] - C["SLOW_T"]) < 0.1 and abs(s["after"] / s["base"] - 1) < 0.03, "veggies: half speed for %.1f s, then back to normal" % C["SLOW_T"], s)
    m = r["shroom"]
    ok(m["ev"] == 1 and abs(m["t0"] - C["TRIP_T"]) < 0.06 and abs(m["secs"] - C["TRIP_T"]) < 0.1 and m["resp"] == 1 and m["alive"] and m["st"] == 1 and C["TRIP_T"] == 10, "mushrooms: you trip for CFG.TRIP_T (%d s); another one is on its way" % C["TRIP_T"], m)
    ok(r["trip"]["wob"] > 0.2 and r["trip"]["sway"] > 0.3 and r["sober"]["wob"] < 0.01 and r["sober"]["sway"] < 0.06 and r["sober"]["shots"] > 3, "mushrooms: steering weaves and the gun sways (sober: dead straight)", (r["trip"], r["sober"]))
    sh = r["shield"]
    ok(sh["loss"] == 0 and sh["slow"] == 0 and sh["trip"] == 0 and sh["veg"] == 0 and sh["shr"] == 0 and sh["st"] == [0, 0] and abs(sh["abil"] - 39.95) < 0.01, "spawn shield: veggies and mushrooms do nothing to a shielded worm", sh)
    ok(sh["gone"] and sh["resp"] == "mv" and sh["shieldLeft"] > 2.9, "spawn shield: the shielded worm still clears them off the floor (and keeps its shield)", sh)
    sp = r["spawn"]
    ok(C["SHIELD"] == 4 and abs(sp["s0"] - 4) < 0.03 and abs(sp["secs"] - 4) < 0.05 and 0.9 < sp["cd0"] <= 1, "spawn shield: lasts CFG.SHIELD = 4 s; the gun is locked for the first second", sp)

# ====================================================================================================
def sec_diff(t):
    """Bot difficulty: S.diff, skill ranges, spawn mercy, warm-up, and hits landed on a passive human."""
    D = J(t, "HW.DIFFS")
    ok(len(D) == 3 and [d["name"] for d in D] == ["EASY", "INTERMEDIATE", "HARD"], "difficulty: three levels, EASY / INTERMEDIATE / HARD", [d["name"] for d in D])
    ok(all(0 <= d["skill"][0] < d["skill"][1] <= 1 for d in D) and D[0]["skill"][1] <= D[2]["skill"][0] and D[0]["engage"] < D[1]["engage"] < D[2]["engage"] and D[0]["mercy"] >= D[1]["mercy"] >= D[2]["mercy"] and D[0]["warm"] > D[1]["warm"] > D[2]["warm"] == 0,
       "difficulty: each level is tougher than the one before (skill, range, mercy, warm-up)", D)
    r = J(t, """(()=>{const out=[];for(const d of [0,1,2,undefined,7,-3,1.9,'2']){const s=d===undefined?new HW.Sim():new HW.Sim({diff:d}),S=s.S,first=S.worms.map(w=>w.bot.skill);
        // bots that respawn later are drawn from the same range
        const p=s.addPlayer(1);p.inp=AT.INP();p.comp.lives=1e9;for(let i=0;i<600;i++){S.match.t=200;s.step(1/60);if(i%120===0)for(const w of S.worms)if(w.isBot&&Math.random()<0.4)s.kill(w,null,'shot');S.events=[];S.adds.length=0;S.rems.length=0}
        const all=first.concat(S.worms.filter(w=>w.isBot).map(w=>w.bot.skill));
        out.push({d:d===undefined?'none':d,diff:S.diff,n:all.length,lo:Math.min(...all),hi:Math.max(...all),bots:S.worms.filter(w=>w.isBot).length,botMercy:Math.max(...S.worms.filter(w=>w.isBot).map(w=>w.mercy))})}
      return out})()""")
    for q, want in zip(r, [0, 1, 2, 1, 2, 0, 1, 2]):
        rg = D[want]["skill"]
        ok(q["diff"] == want and q["n"] >= 23 and rg[0] <= q["lo"] and q["hi"] <= rg[1] and q["botMercy"] == 0, "difficulty: new HW.Sim({diff: %s}) -> S.diff %d (%s), every bot's skill in %s" % (q["d"], want, D[want]["name"], rg), q)
    r = J(t, """(()=>{const out=[];for(let d=0;d<3;d++){const s=new HW.Sim({diff:d}),p=s.addPlayer(1);p.inp=AT.INP();s.step(1/60);const w=p.worm,m0=w.mercy+1/60,sh=w.shield+1/60;
        // shooting (or using the ability) gives the mercy up, like the spawn shield
        w.cd=0;p.inp.fire=true;p.inp.ax=1;s.step(1/60);const afterFire=[w.mercy,w.shield];p.inp.fire=false;
        s.kill(w,null,'shot');p.wantSpawn=true;for(let i=0;i<70&&!(p.worm&&p.worm.alive);i++)s.step(1/60);const w2=p.worm;s.step(1/60);w2.abil=0;w2.mercy=5;p.inp.abil=true;s.step(1/60);
        out.push({d,m0,sh,afterFire,afterAbil:[w2.mercy,w2.shield]})}return out})()""")
    ok(all(abs(q["m0"] - (q["sh"] + D[q["d"]]["mercy"])) < 1e-6 and abs(q["sh"] - 4) < 1e-6 for q in r), "difficulty: a human spawns with mercy = spawn shield + %s s (easy / intermediate / hard)" % [d["mercy"] for d in D], r)
    ok(all(q["afterFire"] == [0, 0] and q["afterAbil"] == [0, 0] for q in r), "difficulty: opening fire or using the ability ends the mercy (and the shield)", r)

    # ---- one bot held next to one frozen human on open ground: does it attack? ----
    t.eval(r"""AT.duel = function (diff, botCh, mode) {
      const CFG = HW.CFG, D = HW.DIFFS[diff], { s, w, bots } = AT.mk([1], { botCh: [botCh], diff }), h = w[0], b = bots[0], sp = AT.spot, S = s.S, g = HW.CHARS[botCh].gun;
      AT.place(b, sp.x + 60, sp.y, 0, 60); AT.place(h, sp.x - 36, sp.y + 30, -Math.PI / 2, 200); b.abil = 0;
      const hold = AT.pin(b), holdH = AT.pin(h), hid = h.id; let phase = 0; const R = { A: { shots: 0, abil: 0, hits: 0, secs: 0 }, B: { shots: 0, abil: 0, hits: 0, secs: 0 }, tShot: -1, tAbil: -1, dist: Math.hypot(h.x - b.x, h.y - b.y), engage: D.engage };
      if (mode === 'warm') S.match.t = CFG.MATCH_T - 0.5; else S.match.t = 200;
      const lenA = mode === 'warm' ? Math.max(0, D.warm - 1) : mode === 'mercy' ? 6 : 0; if (mode === 'mercy') h.mercy = 6.1;
      const step = (P) => { hold(); b.ammo = g.max; b.shield = 0; if (h.alive && h.id === hid) { if (h.stuck <= 0) holdH(); h.mass = 200; h.shield = 0; if (mode !== 'mercy') h.mercy = 0; } if (mode !== 'warm') S.match.t = 200;
        s.step(1 / 60); P.secs += 1 / 60;
        for (const e of AT.flush(s)) { if (e[0] === 'shot' && e[4] === b.id) { P.shots++; if (P === R.B && R.tShot < 0) R.tShot = P.secs; } else if ((e[0] === 'fart' || e[0] === 'puke') && e[3] === b.id) { P.abil++; if (P === R.B && R.tAbil < 0) R.tAbil = P.secs; } else if (e[0] === 'hit' && e[3] === hid) P.hits++; } };
      for (let i = 0; i < Math.round(lenA * 60); i++) step(R.A);
      R.mercyLeft = h.mercy; R.warmLeft = D.warm - (CFG.MATCH_T - S.match.t); R.alive = h.alive && h.id === hid;
      if (mode === 'mercy') h.mercy = 0;
      for (let i = 0; i < 60 * 120 && (R.tShot < 0 || R.tAbil < 0); i++) step(R.B);
      return R;
    };0""")
    for d in range(3):
        nm = D[d]["name"]
        for ch, ab in ((0, "fart"), (2, "puke")):
            q = J(t, "AT.duel(%d,%d,'mercy')" % (d, ch))
            ok(q["dist"] < q["engage"] and q["A"]["secs"] > 5.9 and q["A"]["shots"] == 0 and q["A"]["abil"] == 0 and q["A"]["hits"] == 0 and q["alive"], "mercy (%s): a bot %d px from a human whose mercy timer is running does not fire or %s for 6 s" % (nm, q["dist"], ab), q)
            ok(q["tShot"] >= 0 and q["tAbil"] >= 0, "mercy (%s): once it has run out the bot shoots (after %.1f s) and uses its %s (after %.1f s)" % (nm, q["tShot"], ab, q["tAbil"]), q)
        if D[d]["warm"] > 0:
            q = J(t, "AT.duel(%d,0,'warm')" % d); q2 = J(t, "AT.duel(%d,2,'warm')" % d)
            ok(all(x["A"]["secs"] > D[d]["warm"] - 1.1 and x["A"]["shots"] == 0 and x["A"]["abil"] == 0 and x["A"]["hits"] == 0 and x["warmLeft"] > 0 for x in (q, q2)), "warm-up (%s): for the first %d s of a match bots leave humans alone (no shot, no fart, no puke)" % (nm, D[d]["warm"]), (q, q2))
            ok(all(x["tShot"] >= 0 and x["tAbil"] >= 0 for x in (q, q2)), "warm-up (%s): after it they attack (first shot %.1f s later)" % (nm, q["tShot"]), (q, q2))
        else:
            q = J(t, "AT.duel(%d,0,'warm')" % d)
            ok(q["A"]["secs"] == 0 and 0 <= q["tShot"] < 20, "warm-up (%s): none - a bot opens fire in the first seconds of a match (%.1f s)" % (nm, q["tShot"]), q)

    # ---- fast-forwarded play: hits landed on passive humans per minute ----
    r = J(t, """(()=>{const out=[];
      for(let d=0;d<3;d++){let hits=0,dmg=0,alive=0,deaths=0,shotDeaths=0;const REPS=3,MIN=5;
        for(let rep=0;rep<REPS;rep++){const s=new HW.Sim({diff:d}),S=s.S,ps=[1,2,0].map(ch=>{const p=s.addPlayer(ch);p.inp=AT.INP();p.comp.lives=1e9;return p}),od=s.damage;
          s.damage=function(w,dm,owner,x,y){if(w.pid>=0&&w.alive&&w.shield<=0&&!(w.guard>0)&&owner&&owner.isBot){hits++;dmg+=dm}return od.call(this,w,dm,owner,x,y)};
          for(let i=0;i<3600*MIN;i++){S.match.t=200;
            // passive: no shooting, no boosting, no dodging - just swimming in slow circles (and respawning 3 s after a death)
            for(const p of ps){if(!p.worm||!p.worm.alive){if(p.deadT>3)p.wantSpawn=true}else{alive++;const a=S.t*0.5+p.pid*2;p.inp.mx=Math.cos(a);p.inp.my=Math.sin(a)}}
            s.step(1/60);for(const e of S.events)if(e[0]==='die'&&e[8]>=0){deaths++;if(e[5]==='shot')shotDeaths++}S.events=[];S.adds.length=0;S.rems.length=0}}
        const m=alive/3600;out.push({d,mins:m,hpm:hits/m,dmgpm:dmg/m,deaths,shotDeaths})}
      return out})()""", 400)
    e, i, h = r
    print("     hits per minute on a passive human: EASY %.2f, INTERMEDIATE %.2f, HARD %.2f   (damage per minute %.0f / %.0f / %.0f, shot dead %d / %d / %d times in %.0f human-minutes each)" % (
        e["hpm"], i["hpm"], h["hpm"], e["dmgpm"], i["dmgpm"], h["dmgpm"], e["shotDeaths"], i["shotDeaths"], h["shotDeaths"], e["mins"]))
    ok(h["hpm"] > 2 and e["hpm"] < 0.6 * h["hpm"], "difficulty: bots land clearly fewer hits per minute on a passive human on EASY (%.2f) than on HARD (%.2f)" % (e["hpm"], h["hpm"]), r)
    ok(e["hpm"] < i["hpm"] and e["dmgpm"] < 0.6 * h["dmgpm"], "difficulty: EASY is also gentler than INTERMEDIATE (%.2f), and does well under 60%% of HARD's damage" % i["hpm"], r)

# ====================================================================================================
def sec_spawns(t):
    """Humans spawn clear of obstacles, walls, worms and clouds."""
    r = J(t, """(()=>{const C=HW.CFG,s=new HW.Sim({diff:2}),S=s.S,ps=[0,2].map(ch=>{const p=s.addPlayer(ch);p.inp=AT.INP();p.comp.lives=1e9;return p});
      const wormD=(x,y,skip)=>{let d=1e9;for(const w of S.worms){if(!w.alive||w===skip)continue;for(const q of w.pts){const e=Math.hypot(q.x-x,q.y-y);if(e<d)d=e}}return d};
      const zoneD=(x,y)=>{let d=1e9;for(const z of S.zones){const e=Math.hypot(z.x-x,z.y-y)-z.r;if(e<d)d=e}return d};
      const R={pos:{n:0,clear:1e9,wall:1e9,worm:[],zone:1e9},real:{n:0,clear:1e9,body:1e9,wall:1e9,worm:[],zone:1e9,shield:[9,0],mercy:[9,0],ahead:1e9,bad:0},bots:{n:0,clear:1e9,wall:1e9}};
      for(let i=0;i<3600*5;i++){S.match.t=200;
        for(const p of ps){if(!p.worm||!p.worm.alive)p.wantSpawn=true;else if(i%150===p.pid*75)s.kill(p.worm,null,'shot')}   // die every 2.5 s, come straight back
        s.step(1/60);
        for(const e of S.events)if(e[0]==='spawn'){const w=S.worms.find(o=>o.id===e[3]);if(!w)continue;const c=AT.clear(w.x,w.y),wl=Math.min(w.x,w.y,C.W-w.x,C.H-w.y);
          if(w.pid<0){R.bots.n++;if(c<R.bots.clear)R.bots.clear=c;if(wl<R.bots.wall)R.bots.wall=wl;continue}
          const q=R.real;q.n++;if(c<q.clear)q.clear=c;if(wl<q.wall)q.wall=wl;q.worm.push(wormD(w.x,w.y,w));const z=zoneD(w.x,w.y);if(z<q.zone)q.zone=z;
          for(const pt of w.pts){const b=AT.clear(pt.x,pt.y);if(b<q.body)q.body=b}
          q.shield=[Math.min(q.shield[0],w.shield),Math.max(q.shield[1],w.shield)];q.mercy=[Math.min(q.mercy[0],w.mercy),Math.max(q.mercy[1],w.mercy)];
          // nothing solid right in front of the nose
          let a=0;while(a<200&&AT.clear(w.x+Math.cos(w.ang)*a,w.y+Math.sin(w.ang)*a)>w.r)a+=4;if(a<q.ahead)q.ahead=a;
          if(!AT.fin(w)||w.mass<HW.CHARS[w.ch].startMass||w.ammo!==HW.CHARS[w.ch].gun.start||w.abil<HW.CFG.ABIL_START-0.1)q.bad++}
        S.events=[];S.adds.length=0;S.rems.length=0;
        if(i%5===0){const p=s.spawnPos(true),q=R.pos;q.n++;const c=AT.clear(p.x,p.y),wl=Math.min(p.x,p.y,C.W-p.x,C.H-p.y);if(c<q.clear)q.clear=c;if(wl<q.wall)q.wall=wl;q.worm.push(wormD(p.x,p.y,null));const z=zoneD(p.x,p.y);if(z<q.zone)q.zone=z}}
      const st=a=>{a.sort((x,y)=>x-y);return {min:a[0],p05:a[(a.length*0.05)|0],med:a[a.length>>1]}};
      R.pos.worm=st(R.pos.worm);R.real.worm=st(R.real.worm);R.zonesSeen=S.zones.length;return R})()""", 300)
    p, q, b = r["pos"], r["real"], r["bots"]
    ok(p["n"] >= 3000 and q["n"] >= 200, "spawns: %d spawn spots asked for and %d real human spawns in a busy hard match" % (p["n"], q["n"]), (p["n"], q["n"]))
    ok(p["clear"] >= 40 - 1e-6 and q["clear"] >= 40 - 3, "spawns: a human is never inside or hard against an obstacle (nearest: %.0f px from the head's middle)" % min(p["clear"], q["clear"]), (p["clear"], q["clear"]))
    ok(q["body"] >= 3 - 1e-6 and q["bad"] == 0, "spawns: the whole body starts outside every obstacle; starting mass, ammo and ability countdown", q)
    ok(p["wall"] >= 200 - 1e-6 and q["wall"] >= 200 - 1e-6, "spawns: at least 200 px from the arena walls (%.0f)" % min(p["wall"], q["wall"]), (p["wall"], q["wall"]))
    ok(p["worm"]["min"] >= 150 and q["worm"]["min"] >= 150 and p["worm"]["p05"] >= 300 and q["worm"]["p05"] >= 300, "spawns: a clear area around a new human: nearest worm at least %.0f px away, 95%% of the time over %.0f px (median %.0f)" % (min(p["worm"]["min"], q["worm"]["min"]), min(p["worm"]["p05"], q["worm"]["p05"]), q["worm"]["med"]), (p["worm"], q["worm"]))
    ok(p["zone"] > 20 and q["zone"] > 20, "spawns: never in or at the edge of a fart cloud or a puke puddle (nearest edge %.0f px)" % min(p["zone"], q["zone"]), (p["zone"], q["zone"]))
    ok(abs(q["shield"][0] - 4) < 0.02 and abs(q["shield"][1] - 4) < 0.02 and abs(q["mercy"][0] - 4) < 0.02 and q["ahead"] >= 24, "spawns: 4 s of shield, and room to move off (nearest obstacle straight ahead: %d px)" % q["ahead"], q)
    ok(b["n"] > 20 and b["clear"] >= 40 - 1e-6 and b["wall"] >= 200 - 1e-6, "spawns: bots start clear of obstacles and walls too", b)

# ====================================================================================================
def sec_menu(t):
    """The BOTS button, the pause screen and the per-difficulty best scores, with real taps on the real page."""
    LS = lambda k: t.eval("localStorage.getItem('%s')" % k)
    # every label on the menus is a little canvas of pixel text: remember what was written on each
    WRAP = "(()=>{if(HW.text.__w)return;const o=HW.text;HW.text=function(c,str){try{if(c&&c.canvas)c.canvas.dataset.s=String(str)}catch(e){}return o.apply(this,arguments)};HW.text.__w=1})()"
    def load(): t.goto(URL, 1.2); t.eval(HARNESS + ";0"); t.eval(WRAP); t.eval("HW.App.show(HW.App.screen)"); t.pump(0.2)
    labels = lambda: J(t, "[...document.querySelectorAll('#ui canvas')].map(c=>c.dataset.s||'')")
    def tap(label, exact=True):
        js = "[...document.querySelectorAll('#ui button')].find(b=>[...b.querySelectorAll('canvas')].some(c=>(c.dataset.s||'')%s))" % ("==='%s'" % label if exact else ".indexOf('%s')===0" % label)
        r = J(t, "(()=>{const b=%s;if(!b)return null;const r=b.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2,r.width,r.height,innerWidth,innerHeight]})()" % js)
        if not r: ok(False, "menu: button '%s' is on the screen" % label, labels()); return None
        t.touch("touchStart", [(0, r[0], r[1])]); t.touch("touchEnd", []); t.pump(0.4); return r
    bots = lambda: next((s for s in labels() if s.startswith("BOTS: ")), None)
    def finish(mass):   # grow to `mass`, let the clock run out, return the final score
        t.eval("(()=>{const m=HW.App.locals[0].me;m.mass=%d;m.shield=30})()" % mass); t.pump(0.3)
        t.eval("HW.App.sim.S.match.t=0.2"); t.pump(1.0)
        return J(t, "HW.App.locals[0].player.comp.score")

    t.eval("localStorage.clear()"); load()
    ok(LS("hw_diff") is None and t.eval("HW.App.diff") == 0 and t.eval("HW.App.screen") == "title", "menu: a clean profile starts on EASY (nothing stored yet)", (LS("hw_diff"), t.eval("HW.App.diff")))
    ok(not any(s.startswith("YOUR BEST") for s in labels()), "menu: no best scores on the title of a clean profile", labels())
    tap("PLAY"); ok(t.eval("HW.App.screen") == "select" and bots() == "BOTS: EASY", "menu: PLAY -> the select screen has a BOTS button, showing EASY", labels())
    r = tap("BOTS: EASY"); ok(bots() == "BOTS: INTERMEDIATE" and LS("hw_diff") == "1" and t.eval("HW.App.diff") == 1, "menu: tap -> INTERMEDIATE, stored in localStorage hw_diff", (bots(), LS("hw_diff")))
    ok(r and r[3] >= 30 and r[2] >= 60 and r[1] + r[3] / 2 <= r[5], "menu: the BOTS button is a proper touch target and on the screen (%dx%d css px)" % ((r[2], r[3]) if r else (0, 0)), r)
    tap("BOTS: INTERMEDIATE"); ok(bots() == "BOTS: HARD" and LS("hw_diff") == "2", "menu: tap -> HARD", (bots(), LS("hw_diff")))
    tap("BOTS: HARD"); ok(bots() == "BOTS: EASY" and LS("hw_diff") == "0", "menu: tap -> back round to EASY", (bots(), LS("hw_diff")))
    tap("BOTS: EASY"); tap("BOTS: INTERMEDIATE"); load()
    ok(t.eval("HW.App.diff") == 2 and LS("hw_diff") == "2", "menu: the choice survives a reload")
    tap("PLAY"); ok(bots() == "BOTS: HARD", "menu: ...and the button shows it", bots())
    tap("BACK"); tap("JOIN ONLINE GAME")
    ok(t.eval("HW.App.screen") == "select" and t.eval("HW.App.sel.mode") == "join" and bots() is None and t.eval("document.querySelectorAll('#ui button[data-diff]').length") == 0, "menu: no BOTS button when joining a room (the host's setting applies)", labels())
    tap("BACK"); tap("HOST ONLINE GAME"); ok(bots() == "BOTS: HARD", "menu: the host picks the difficulty", bots())
    tap("BACK"); tap("2 PLAYERS, 1 SCREEN"); ok(bots() == "BOTS: HARD", "menu: so do two players on one screen", bots())
    tap("BACK"); tap("PLAY"); tap("PLAY!"); t.pump(1.0)
    g = J(t, "(()=>{const A=HW.App,S=A.sim.S,sk=S.worms.filter(w=>w.isBot).map(w=>w.bot.skill);return {mode:A.mode,screen:A.screen,diff:S.diff,play:A.playDiff,lo:Math.min(...sk),hi:Math.max(...sk),mercy:A.locals[0].me?A.locals[0].me.mercy:-1}})()")
    ok(g["mode"] == "play" and g["diff"] == 2 and g["play"] == 2 and g["lo"] >= 0.8, "menu: PLAY! starts a match against HARD bots", g)
    # pause with a real tap on the pause button
    pz = J(t, "(()=>{const L=HW.Input.touch.layout.pause,k=HW.Render.scale;return [(L.x+L.w/2)*k,(L.y+L.h/2)*k]})()")
    t.touch("touchStart", [(0, pz[0], pz[1])]); t.touch("touchEnd", []); t.pump(0.5)
    ok(t.eval("HW.App.screen") == "pause" and "BOTS: HARD" in labels() and "PAUSED" in labels(), "menu: the pause screen shows the difficulty being played", labels())
    t.shot(SP + "/a_pause.png"); tap("RESUME"); ok(t.eval("HW.App.screen") == "" and not t.eval("HW.App.paused"), "menu: RESUME goes back to the game")

    # ---- best scores per difficulty ----
    sc = finish(400)
    ok(t.eval("HW.App.screen") == "results" and sc >= 400 and LS("hw_best3_2") == str(sc) and LS("hw_best3_0") is None and LS("hw_best3_1") is None, "best: a HARD match is stored under hw_best3_2 only (%d)" % sc, (sc, LS("hw_best3_2"), LS("hw_best3_0"), LS("hw_best3_1")))
    ok("NEW BEST SCORE!" in labels(), "best: the results screen says NEW BEST SCORE!", labels())
    tap("MENU"); lb = [s for s in labels() if s.startswith("YOUR BEST")]
    ok(t.eval("HW.App.screen") == "title" and len(lb) == 1 and ("HARD %d" % sc) in lb[0] and "EASY" not in lb[0] and "INTERMEDIATE" not in lb[0], "best: the title shows it against HARD and nothing for the levels not played", lb)
    tap("PLAY"); tap("BOTS: HARD"); tap("PLAY!"); t.pump(1.0)
    ok(t.eval("HW.App.sim.S.diff") == 0 and t.eval("HW.App.bestBefore") == 0 and t.eval("HW.App.locals[0].player.best") < 100, "best: a match on EASY starts from EASY's own best (0), not HARD's", (t.eval("HW.App.bestBefore"), t.eval("HW.App.locals[0].player.best")))
    sc0 = finish(150)
    ok(150 <= sc0 < sc and LS("hw_best3_0") == str(sc0) and LS("hw_best3_2") == str(sc) and "NEW BEST SCORE!" in labels(), "best: a lower score on EASY is a new EASY best (%d); HARD's stays" % sc0, (sc0, LS("hw_best3_0"), LS("hw_best3_2")))
    tap("PLAY AGAIN"); t.pump(1.0); sc1 = finish(90)
    ok(sc1 < sc0 and LS("hw_best3_0") == str(sc0) and "NEW BEST SCORE!" not in labels(), "best: a worse match does not overwrite it", (sc1, LS("hw_best3_0"), labels()))
    t.shot(SP + "/a_results.png"); tap("MENU"); lb = [s for s in labels() if s.startswith("YOUR BEST")]
    ok(len(lb) == 1 and ("EASY %d" % sc0) in lb[0] and ("HARD %d" % sc) in lb[0] and lb[0].index("EASY") < lb[0].index("HARD"), "best: the title lists the bests per difficulty", lb)
    t.shot(SP + "/a_title_bests.png")
    fit = J(t, "(()=>{const c=[...document.querySelectorAll('#ui canvas')].find(c=>(c.dataset.s||'').indexOf('YOUR BEST')===0).getBoundingClientRect();return [c.left,c.right,c.bottom,innerWidth,innerHeight]})()")
    ok(fit[0] >= 0 and fit[1] <= fit[3] and fit[2] <= fit[4], "best: that line fits on the phone screen", fit)
    # ---- the old shared key goes, odd stored values are harmless ----
    t.eval("localStorage.setItem('hw_best','999');localStorage.setItem('hw_diff','7')"); load()
    ok(LS("hw_best") is None and LS("hw_best3_0") == str(sc0) and LS("hw_best3_2") == str(sc), "best: the old hw_best key is removed on load, the new ones are kept", (LS("hw_best"), LS("hw_best3_0")))
    ok(t.eval("HW.App.diff") == 2, "menu: a stored difficulty that is out of range is clamped", t.eval("HW.App.diff"))
    t.eval("localStorage.setItem('hw_diff','banana')"); load(); ok(t.eval("HW.App.diff") == 0, "menu: a stored difficulty that is nonsense falls back to EASY", t.eval("HW.App.diff"))
    t.eval("localStorage.clear()"); load()

# ====================================================================================================
SECTIONS = [("map", sec_map), ("worms", sec_worms), ("shots", sec_shots), ("items", sec_items), ("food", sec_food), ("diff", sec_diff), ("spawns", sec_spawns), ("menu", sec_menu)]

if __name__ == "__main__":
    b = Browser(profile=SP + "/prof")
    try:
        t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 1.2); t.eval(HARNESS + ";0")
        for name, fn in SECTIONS:
            if not want(name): continue
            print("--- " + name)
            try: fn(t)
            except Exception as e: ok(False, "section '%s' ran to the end" % name, repr(e)[:700])
        ok(not t.errors, "no page errors", t.errors)
    finally:
        b.close()
    print("\n%d failed: %s" % (len(FAIL), FAIL) if FAIL else "\nall arena checks passed")
    sys.exit(1 if FAIL else 0)
