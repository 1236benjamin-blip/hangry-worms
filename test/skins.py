"""Worm skins in headless Chrome: every skin draws at every size without errors, the 20 identity colours stay
easy to tell apart, the sprite cache stays bounded, a body is still one drawImage per segment, and a frame of
12 long worms costs about what it did before the skins (the old flat-disc drawWorm is kept below as the yardstick).
Usage: python3 test/skins.py /tmp/out   (static server on :8377, see NOTES.md). Exits 1 if a check fails."""
import sys, os, json, itertools
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html")
FAILS = []
def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (("  " + str(detail)) if detail != "" else ""))
    if not ok: FAILS.append(name)

# ---- colour distance: CIE76 (plain distance in L*a*b*). Around 2 is the smallest step an eye can see; the 20 identity
# colours are 2 to 3 px dots on the minimap, so they have to be an order of magnitude further apart than that.
def lab(h):
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = f(r), f(g), f(b)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047; y = 0.2126 * r + 0.7152 * g + 0.0722 * b; z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    g2 = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    x, y, z = g2(x), g2(y), g2(z)
    return (116 * y - 16, 500 * (x - y), 200 * (y - z))
def dE(a, b): return sum((p - q) ** 2 for p, q in zip(lab(a), lab(b))) ** 0.5
MIN_ANY, MIN_SAME_WORM, MIN_DEFAULTS, MIN_FLOOR = 24, 32, 34, 28

# ---- helpers injected into the page
JS = r"""
// a worm object like the sim's, laid out along a wiggly path (6 px between points, like HW.follow leaves them)
window.mkWorm = function (ch, variant, mass, x, y, a0, wig, o) {
  const n = HW.segCount(mass), pts = []; let px = x, py = y;
  for (let i = 0; i < n; i++) { pts.push({ x: px, y: py }); const d = a0 + Math.PI + Math.sin(i * 0.21) * wig + i * (o && o.coil || 0); px += Math.cos(d) * 6; py += Math.sin(d) * 6; }
  return Object.assign({ id: ch * 4 + variant + 1, ch, variant, x, y, ang: a0, aim: a0 + 0.3, pts, r: HW.wormR(ch, mass), mass, alive: true, shield: 0, stuck: 0, slow: 0, boosting: false, pid: -1 }, o || {});
};
window.inked = function (c) { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; };
window.avgColor = function (c) { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let r = 0, g = 0, b = 0; for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; } const n = d.length / 4, h = v => ('0' + Math.round(v / n).toString(16)).slice(-2); return '#' + h(r) + h(g) + h(b); };

// ---- the worm drawing of the commit before the skins (7a55568), kept as the cost yardstick: flat shaded discs, two colours
(function () {
  const OLD = [[['#f08a1c', '#ffd23f'], ['#e03c32', '#ffb0a8'], ['#d9d9e0', '#8d8fa0'], ['#b06a3a', '#e8b574']], [['#2b6fd6', '#7fc4ff'], ['#16a085', '#7dffd8'], ['#c0392b', '#ff9a8a'], ['#6c5ce7', '#c3b8ff']],
    [['#7ed321', '#3d8b1f'], ['#f5d547', '#b8860b'], ['#ff8fd0', '#c2409a'], ['#59d9d9', '#1f7f8b']], [['#9b5de5', '#ff7eb6'], ['#3ec1d3', '#f6f7d7'], ['#ff9a3c', '#ffe26a'], ['#5d6d7e', '#aeb6bf']],
    [['#6b7a3a', '#3e4a22'], ['#8d6e63', '#4e342e'], ['#546e7a', '#263238'], ['#a67c00', '#5c4400']]];
  const CHARS = HW.CHARS, segCache = {}, shade = HW.shade;
  function seg(color, r) {
    const key = color + r; let c = segCache[key]; if (c) return c;
    const R = r + 1, d = R * 2 + 1; c = HW.mk(d, d); const x = c.getContext('2d');
    const out = shade(color, -0.62), hi = shade(color, 0.35), lo = shade(color, -0.25);
    for (let j = -R; j <= R; j++) for (let i = -R; i <= R; i++) {
      const q = i * i + j * j;
      if (q > R * R + R * 0.6) continue;
      let col = color;
      if (q > r * r - r * 0.4) col = out;
      else if ((i + r * 0.35) * (i + r * 0.35) + (j + r * 0.35) * (j + r * 0.35) < r * r * 0.16) col = hi;
      else if ((i - r * 0.3) * (i - r * 0.3) + (j - r * 0.3) * (j - r * 0.3) > r * r * 0.75) col = lo;
      x.fillStyle = col; x.fillRect(i + R, j + R, 1, 1);
    }
    return segCache[key] = c;
  }
  function pxLine(c, x0, y0, x1, y1, col, th) {
    const dx = x1 - x0, dy = y1 - y0, n = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy))));
    c.fillStyle = col; for (let i = 0; i <= n; i++) c.fillRect(Math.round(x0 + dx * i / n), Math.round(y0 + dy * i / n), th, th);
  }
  function ring(c, x, y, r, col, n, phase, sz) {
    c.fillStyle = col; for (let i = 0; i < n; i++) { const a = phase + i * 6.283 / n; c.fillRect(Math.round(x + Math.cos(a) * r), Math.round(y + Math.sin(a) * r), sz, sz); }
  }
  function segColor(ch, i, cols) {
    switch (ch) {
      case 0: return cols[(i >> 2) & 1];
      case 1: return cols[i % 6 < 2 ? 1 : 0];
      case 2: return cols[i % 5 === 2 ? 1 : 0];
      case 3: return cols[(i >> 1) & 1];
      default: return cols[(i * 7 + (i >> 2)) % 5 < 2 ? 1 : 0];
    }
  }
  window.drawWormOld = function (c, w, ox, oy, t, leader, isMe) {
    const C = CHARS[w.ch], cols = OLD[w.ch][w.variant % 4], p = w.pts, r = w.r, n = p.length;
    if (w.shield > 0 && ((t * 12) | 0) % 2) c.globalAlpha = 0.5;
    for (let i = n - 1; i >= 0; i--) {
      const ft = n - 1 - i; let rr = r; if (ft < 4) rr = Math.max(3, r - 4 + ft);
      const s = seg(i === 0 ? cols[0] : segColor(w.ch, i, cols), rr);
      c.drawImage(s, Math.round(p[i].x - ox) - rr - 1, Math.round(p[i].y - oy) - rr - 1);
    }
    const name = C.name, L = name.length, st = 3;
    if (n >= st + L) {
      const dxn = p[st + L - 1].x - p[st].x, dyn = p[st + L - 1].y - p[st].y;
      if (w._vert === undefined) w._vert = Math.abs(dyn) > Math.abs(dxn); else if (Math.abs(dyn) > Math.abs(dxn) * 1.4) w._vert = true; else if (Math.abs(dxn) > Math.abs(dyn) * 1.4) w._vert = false;
      const d = w._vert ? dyn : dxn, step = w._vert && n >= st + L * 2 ? 2 : 1;
      if (w._rev === undefined) w._rev = d < 0; else if (d > 8) w._rev = false; else if (d < -8) w._rev = true;
      for (let k = 0; k < L; k++) { const q = p[st + (w._rev ? L - 1 - k : k) * step]; HW.glyph(c, name[k], Math.round(q.x - ox), Math.round(q.y - oy), '#ffffff'); }
    }
    const hx = Math.round(w.x - ox), hy = Math.round(w.y - oy);
    const dx = Math.cos(w.ang), dy = Math.sin(w.ang), ax = Math.cos(w.aim), ay = Math.sin(w.aim);
    const gx = hx + ax * (r + 5), gy = hy + ay * (r + 5), arm = HW.shade(cols[0], -0.3);
    pxLine(c, hx - ay * (r - 1), hy + ax * (r - 1), gx, gy, arm, 2);
    pxLine(c, hx + ay * (r - 1), hy - ax * (r - 1), gx + ax * 4, gy + ay * 4, arm, 2);
    const g = HW.gunSpr[w.ch];
    c.save(); c.translate(Math.round(gx), Math.round(gy)); c.rotate(w.aim); if (ax < 0) c.scale(1, -1); c.drawImage(g.c, -g.px, -g.py); c.restore();
    c.fillStyle = HW.PAL.T; c.fillRect(Math.round(gx) - 1, Math.round(gy) - 1, 2, 2);
    const es = C.big ? 4 : 3;
    for (let s = -1; s <= 1; s += 2) {
      const ex = Math.round(hx + dx * r * 0.3 - dy * s * r * 0.5), ey = Math.round(hy + dy * r * 0.3 + dx * s * r * 0.5);
      if (w.ch === 1) { c.fillStyle = '#111'; c.fillRect(ex - 2, ey - 2, 5, 4); c.fillStyle = '#7fc4ff'; c.fillRect(ex - 1, ey - 1, 1, 1); }
      else {
        c.fillStyle = '#1a1423'; c.fillRect(ex - (es >> 1) - 1, ey - (es >> 1) - 1, es + 2, es + 2);
        c.fillStyle = w.stuck > 0 ? '#c8e86a' : '#fff'; c.fillRect(ex - (es >> 1), ey - (es >> 1), es, es);
        c.fillStyle = '#1a1423'; c.fillRect(ex - (es >> 1) + (ax > 0.3 ? es - 2 : ax < -0.3 ? 0 : (es - 2) >> 1), ey - (es >> 1) + (ay > 0.3 ? es - 2 : ay < -0.3 ? 0 : (es - 2) >> 1), 2, 2);
      }
    }
    if (w.ch === 1) pxLine(c, hx + dx * r * 0.3 - dy * r * 0.5, hy + dy * r * 0.3 + dx * r * 0.5, hx + dx * r * 0.3 + dy * r * 0.5, hy + dy * r * 0.3 - dx * r * 0.5, '#111', 1);
    if (w.ch === 0) c.drawImage(HW.hatSpr.ben, hx - 5, hy - r - 3);
    else if (w.ch === 4) c.drawImage(HW.hatSpr.jeff, hx - 5, hy - r - 3);
    else if (w.ch === 3) c.drawImage(((t * 8) | 0) % 2 ? HW.hatSpr.wes : HW.hatSpr.wes2, hx - 5, hy - r - 4);
    else if (w.ch === 2) {
      const bx = hx - dx * r * 0.35, by = hy - dy * r * 0.35;
      pxLine(c, bx - dy * r, by + dx * r, bx + dy * r, by - dx * r, '#e03c32', 2);
      const wv = Math.sin(t * 9 + w.id) * 2;
      pxLine(c, bx - dy * r, by + dx * r, bx - dy * r - dx * 6 + wv, by + dx * r - dy * 6, '#e03c32', 1);
      pxLine(c, bx - dy * r, by + dx * r, bx - dy * r - dx * 5 - wv, by + dx * r - dy * 5 + 2, '#9c2020', 1);
    }
    if (leader) c.drawImage(HW.crownSpr, hx - 4, hy - r - 11 + Math.round(Math.sin(t * 4)));
    c.globalAlpha = 1;
    if (w.shield > 0) ring(c, hx, hy, r + 6, '#aef', 12, t * 4, 2);
    if (w.slow > 0) ring(c, hx, hy, r + 4, '#5cc04a', 6, -t * 3, 2);
  };
})();

// ---- 12 worms at full length (240 segments each), all inside one phone-sized view, drawn old and new in turn
window.costRun = async function (frames, rounds) {
  const W = 585, H = 270, cv = HW.mk(W, H), c = cv.getContext('2d', { alpha: false }), ws = []; c.imageSmoothingEnabled = false;   // like the game's view canvas
  for (let i = 0; i < 12; i++) ws.push(mkWorm(i % 5, (i / 5 | 0) % 4, 560, 60 + (i % 6) * 90, 40 + (i / 6 | 0) * 120, i * 0.7, 0.9, { coil: 0.012 * (i % 3) }));
  const segs = ws.reduce((a, w) => a + w.pts.length, 0);
  const pass = (fn, n) => { const t0 = performance.now(); for (let f = 0; f < n; f++) { c.fillStyle = '#120e1c'; c.fillRect(0, 0, W, H); for (const w of ws) fn(c, w, 0, 0, 0.5 + f / 60, false, false); } c.getImageData(0, 0, 1, 1); return (performance.now() - t0) / n; };
  const neu = (c, w, ox, oy, t) => HW.Render.drawWormPreview(c, w, t);
  pass(drawWormOld, 30); pass(neu, 30);   // warm up: fill both caches, let the JIT settle
  await new Promise(r => setTimeout(r, 400)); pass(neu, 5);   // the discs become ImageBitmaps a moment after they are painted
  const a = [], b = [];
  for (let r = 0; r < rounds; r++) { a.push(pass(drawWormOld, frames)); b.push(pass(neu, frames)); }
  const med = v => v.slice().sort((x, y) => x - y)[v.length >> 1];
  return { segs, old: med(a), neu: med(b), ratio: med(b) / med(a) };
};
"""

b = Browser(profile=SP + "/prof")
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 1.5)
    t.eval(JS)
    check("page loads without errors", not t.errors, t.errors)

    # ---- contract with sim.js
    S = json.loads(t.eval("JSON.stringify(HW.SKINS.map(s=>s.colors))"))
    check("5 skins x 4 variants, two colours each", len(S) == 5 and all(len(v) == 4 and all(len(c) == 2 for c in v) for v in S))
    check("sim.js uses the skin colours", t.eval("HW.CHARS.every((c,i)=>c.colors===HW.SKINS[i].colors)"))

    # ---- every skin at several sizes, in every direction, in every state
    r = json.loads(t.eval("""(()=>{const cv=HW.mk(700,500),c=cv.getContext('2d'),out={n:0,empty:[],radii:{}};
      for(let ch=0;ch<5;ch++)for(let v=0;v<4;v++)for(const mass of [8,30,95,190,280,370,460,560])for(let k=0;k<4;k++){
        const st=[{},{shield:2},{stuck:3,slow:2},{boosting:true}][k],w=mkWorm(ch,v,mass,350,250,k*1.7+ch+v*0.4+mass,0.5+k*0.4,Object.assign({coil:k===3?0.05:0},st));
        c.clearRect(0,0,700,500);for(let f=0;f<3;f++)HW.Render.drawWormPreview(c,w,0.37+f*0.31+k);out.n++;out.radii[w.r]=1;if(inked(cv)<w.pts.length*20)out.empty.push([ch,v,mass,k]);}
      out.radii=Object.keys(out.radii).map(Number);return JSON.stringify(out)})()"""))
    check("all 20 skins draw at 8 sizes in 4 states (%d worms, radii %s)" % (r["n"], r["radii"]), not r["empty"] and sorted(r["radii"]) == list(range(6, 14)), r["empty"][:5])
    check("no errors while drawing them", not t.errors, t.errors[:3])

    # ---- the cache is bounded: that pass asked for far more discs than are ever kept, so the oldest sets were dropped
    st = json.loads(t.eval("JSON.stringify(HW.skinStats())"))
    everything = 20 * sum(16 * (q + 1) for q in range(6, 14))
    check("disc cache stays under its cap (%d of %d kept in %d sets; there are %d in all)" % (st["cells"], st["max"], st["sets"], everything), st["cells"] <= st["max"] < everything and st["skins"] == 20 and st["sets"] < 160)
    check("12 worms of the biggest size, coiled every way, fit in the cap together", 12 * 14 * 16 <= st["max"])
    check("tail discs and glints are bounded too (%d tails, %d glints)" % (st["tails"], st["glints"]), st["tails"] <= 20 * 40 and st["glints"] <= 21 * 8 * 2)
    r = json.loads(t.eval("""(()=>{const cv=HW.mk(700,500),c=cv.getContext('2d'),w=mkWorm(0,0,8,350,250,0.3,0.6);HW.Render.drawWormPreview(c,w,1);
      const a=inked(cv),s0=HW.skinStats();for(let i=0;i<50;i++)HW.Render.drawWormPreview(c,w,1+i/7);return JSON.stringify({a,s0,s1:HW.skinStats()})})()"""))
    check("a dropped set is repainted when its worm comes back, and drawing it again allocates nothing", r["a"] > 500 and r["s0"] == r["s1"], r)

    # ---- a painted disc is drawn from its canvas at first and from an ImageBitmap a moment later: same pixels either way
    r = json.loads(t.eval("""(async()=>{const cv=HW.mk(300,200),c=cv.getContext('2d'),w=mkWorm(3,2,190,220,60,0.4,0.9),S=()=>HW.skinSet(HW.skin(3,2),w.r).cells.filter(Boolean);
      const grab=()=>{c.clearRect(0,0,300,200);HW.Render.drawWormPreview(c,w,5);return c.getImageData(0,0,300,200).data};
      HW.skinSet(HW.skin(3,2),w.r).cells.forEach((q,i,a)=>{a[i]=null});   // paint this worm's discs afresh
      const a=grab(),canv=S().filter(q=>q instanceof HTMLCanvasElement).length;await new Promise(r=>setTimeout(r,500));
      const b=grab(),bm=S().filter(q=>q instanceof ImageBitmap).length;let diff=0;for(let i=0;i<a.length;i++)if(a[i]!==b[i])diff++;
      return JSON.stringify({cells:S().length,canv,bm,diff})})()""", 60))
    check("discs turn into ImageBitmaps without a pixel changing", r["canv"] == r["cells"] == r["bm"] > 20 and r["diff"] == 0, r)

    # ---- still one drawImage per body segment, plus a handful
    r = json.loads(t.eval("""(()=>{const cv=HW.mk(700,500),c=cv.getContext('2d'),d=c.drawImage;let n=0;c.drawImage=function(){n++;return d.apply(this,arguments)};const out=[];
      for(const o of [{},{boosting:true}])for(const mass of [8,95,560]){const w=mkWorm(1,0,mass,350,250,0.3,0.8,o);let m=0;for(let f=0;f<40;f++){n=0;HW.Render.drawWormPreview(c,w,f/9);m=Math.max(m,n)}out.push([w.pts.length,m,!!o.boosting])}
      return JSON.stringify(out)})()"""))
    # extras: name letters (8 for CHANDLER), gun, hat or crown, the sheen (2 in every 56 segments) or boost pulses (2 in 16)
    check("draw calls per worm [segments, drawImages, boosting]: %s" % r, all(m <= n + 12 + 2 * (n // (16 if boost else 56) + 1) for n, m, boost in r))

    # ---- identity colours: far apart from each other and from every floor
    ids = [(("BEN", "CHANDLER", "NATE", "WESLEY", "JEFF")[i] + str(j), S[i][j][0]) for i in range(5) for j in range(4)]
    floors = json.loads(t.eval("JSON.stringify([HW.floorTile].concat(HW.zoneTiles).map(avgColor))"))
    pairs = sorted((dE(a[1], c[1]), a[0], c[0]) for a, c in itertools.combinations(ids, 2))
    same = [p for p in pairs if p[1][:-1] == p[2][:-1]]; dflt = [p for p in pairs if p[1][-1] == "0" and p[2][-1] == "0"]
    fl = min((dE(c, f), n, f) for n, c in ids for f in floors)
    print("     closest identity colours: " + ", ".join("%s/%s %.0f" % (p[1], p[2], p[0]) for p in pairs[:4]))
    check("any two of the 20 identity colours differ by dE >= %d (closest %.1f)" % (MIN_ANY, pairs[0][0]), pairs[0][0] >= MIN_ANY, pairs[0])
    check("the 4 colours of one worm differ by dE >= %d (closest %.1f)" % (MIN_SAME_WORM, same[0][0]), same[0][0] >= MIN_SAME_WORM, same[0])
    check("the 5 default colours differ by dE >= %d (closest %.1f)" % (MIN_DEFAULTS, dflt[0][0]), dflt[0][0] >= MIN_DEFAULTS, dflt[0])
    check("every identity colour stands dE >= %d off every floor (closest %.1f)" % (MIN_FLOOR, fl[0]), fl[0] >= MIN_FLOOR, fl)

    # ---- the game itself with the skins on: select screen previews, then a few seconds of play
    t.eval("HW.App.sel.mode='solo';HW.App.show('select')"); t.pump(0.8); t.shot(SP + "/skins_select.png")
    check("select screen previews are drawn", t.eval("HW.App.previews.length===5&&HW.App.previews.every(p=>inked(p.c)>300)"))
    t.eval("HW.App.startLocal([3])"); t.pump(3); t.shot(SP + "/skins_play.png")
    check("playing: no errors", not t.errors, t.errors[:3])

    # ---- cost of a frame of 12 full-length worms, new against old, on a phone-ish CPU (4x throttle)
    # Old and new are timed in alternating rounds and the medians compared. The machine is shared, so a run that
    # comes out over the limit is measured again (up to 3 times) before it counts as a failure.
    t.call("Emulation.setCPUThrottlingRate", {"rate": 4})
    for attempt in range(3):
        c = json.loads(t.eval("costRun(40, 9).then(JSON.stringify)", 120))
        print("     12 worms, %d segments, CPU throttled 4x: old %.2f ms/frame, new %.2f ms/frame, ratio %.2f" % (c["segs"], c["old"], c["neu"], c["ratio"]))
        if c["ratio"] <= 1.3: break
    t.call("Emulation.setCPUThrottlingRate", {"rate": 1})
    check("12 long worms cost at most 1.3x the old flat discs (%.2fx)" % c["ratio"], c["ratio"] <= 1.3)
    st = json.loads(t.eval("JSON.stringify(HW.skinStats())"))
    check("cache still under its cap at the end (%d discs in %d sets)" % (st["cells"], st["sets"]), st["cells"] <= st["max"])
    check("no errors at the end", not t.errors, t.errors[:3])
finally:
    b.close()
print("FAILED: " + ", ".join(FAILS) if FAILS else "all skin checks passed")
sys.exit(1 if FAILS else 0)
