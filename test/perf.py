"""Is it smooth on an average phone?  Sim cost per step and draw + HUD cost per frame at 844x390 @3x, on this machine
as it is and again with Chrome's CPU throttled 4x (DevTools' own "mid-tier mobile" setting), in two scenes.
  HW_URL=http://127.0.0.1:8377/index.html HW_PORT=9415 python3 test/perf.py <scratch dir>

TYPICAL: a solo match as it starts: 12 worms in the arena, whatever happens to be on the player's screen.
BUSY:    the worst pile-up the game can produce. All 12 worms on one screen in the food court (four of them long, about
         960 body segments), every bot holding the trigger of a special gun (ray gun, rocket launcher, flamethrower
         stream, popcorn minigun, freeze ray), rampage / supersize / shield / hot sauce running, a fart cloud and a puke
         puddle, every kind of pickup, veggies, mushrooms, extra food, 260+ particles, floating numbers, the mushroom
         trip effect on half the frames, a banner, the bump warning, the touch controls.

THE BUDGET.  One 60 fps frame is 16.7 ms and the game does one sim step and one draw in it. The page's own work must
leave room for what this test cannot see: the browser scaling the canvas up to the screen and compositing it, garbage
collection, touch handling, sound, and a phone that has warmed up. So at 4x throttle:
  typical scene: sim + draw + HUD <= 10 ms on average (60% of a 60 fps frame): normal play runs at a steady 60;
  busy scene:    sim + draw + HUD <= 25 ms on average (75% of a 30 fps frame): the worst pile-up never drops under 30.
Headless Chrome paints the canvas on the CPU, so the throttle slows painting as well, which a phone does on its GPU:
the proxy is on the harsh side, and that is the reason the headroom is not larger still.
Each figure is the best of three batches, and when other programs on the test machine make the throttle bite harder
than 4x (a fixed loop is timed both ways to see), the throttled figures are scaled back to exactly 4x."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html"); FAIL = []
BUDGET_TYPICAL, BUDGET_BUSY, BUDGET_SIM, THROTTLE = 10.0, 25.0, 3.0, 4
def ok(c, msg, extra=""):
    print(("ok   " if c else "FAIL ") + msg, extra if (extra != "" and not c) or os.environ.get("HW_VERBOSE") else "")
    if not c: FAIL.append(msg)
J = lambda t, js, timeout=120: json.loads(t.eval("JSON.stringify(%s)" % js, timeout=timeout))

BENCH = r"""
window.PF = (() => {
  const A = HW.App, R = HW.Render, CFG = HW.CFG, PI = Math.PI, CX = 1200, CY = 1085;   // between the food court's top counter and its middle table
  // where each worm lies: dx, dy, heading, mass. The first is the player.
  const LAY = [[0, 10, 0, 150], [-40, -66, 0, 430], [70, 70, PI, 390], [-210, 44, 0.25, 300], [250, -40, PI - 0.2, 260], [-270, -20, -0.5, 120], [280, 30, 2.6, 90], [10, -100, 0, 70], [-90, 112, 0, 60], [120, -30, PI / 2, 60], [-290, -112, 0, 60], [296, 116, PI, 50]];
  let on = false, n = 0;
  const stat = a => { a = a.slice().sort((x, y) => x - y); return { mean: a.reduce((s, v) => s + v, 0) / a.length, p50: a[a.length >> 1], p95: a[(a.length * 0.95) | 0], max: a[a.length - 1] }; };
  function lay(w, q) {
    w.mass = q[3]; w.x = CX + q[0]; w.y = CY + q[1]; w.ang = q[2]; w.aim = q[2]; const k = HW.segCount(w.mass); w.pts.length = 0;
    for (let i = 0; i < k; i++) w.pts.push({ x: w.x - Math.cos(q[2]) * i * 6, y: w.y - Math.sin(q[2]) * i * 6 }); HW.follow(w);
  }
  // everybody back to their mark, guns loaded, power-ups running
  function herd() {
    const S = A.sim.S, me = A.locals[0].me, all = [me].concat(S.worms.filter(w => w !== me));
    all.forEach((w, i) => { lay(w, LAY[i % LAY.length]); w.shield = 0; w.stuck = 0; w.ammo = 99; w.sg = 1 + (i % 5); w.sgT = 99; w.rage = i % 4 === 1 ? 9 : 0; w.big = i % 4 === 2 ? 9 : 0; w.guard = i % 4 === 3 ? 9 : 0; w.sauce = i % 3 === 0 ? 9 : 0; w.chill = i === 5 ? 3 : 0; w.slow = i === 6 ? 3 : 0; w.trip = i === 7 ? 9 : 0; HW.follow(w); });
    me.sg = 3; me.rage = 9; me.guard = 9; me.sauce = 9; me.big = 0; me.abil = 0;
    for (const w of all) if (w !== me) w.abil = 99;   // no more clouds than the two below
    if (S.zones.length !== 2) { S.zones.length = 0; S.zones.push({ id: S.nextId++, k: 0, x: CX - 150, y: CY + 150, r: CFG.FART_R, t: 99, owner: me.id }, { id: S.nextId++, k: 1, x: CX + 170, y: CY + 140, r: CFG.PUKE_R, t: 99, owner: me.id }); }
    for (const z of S.zones) z.t = 99; S.match.t = 200;
    // the props: back where they were (worms keep eating them), nothing extra turning up, and no more food on this
    // screen than a pile-up really leaves (the worms here are refilled for ever, so they would spill food for ever)
    const s = A.sim; S.respawns.length = 0; let nf = 0;
    for (const it of Array.from(S.items.values())) { if (it.k !== 'f') s.remItem(it); else if (Math.abs(it.x - CX) < 340 && Math.abs(it.y - CY) < 170 && ++nf > 70) s.remItem(it); }
    for (let i = 0; i < 4; i++) s.addItem('p', i, CX - 240 + i * 150, CY - 120, 0);
    for (let i = 0; i < 5; i++) s.addItem('g', i, CX - 270 + i * 130, CY + 128, 0);
    s.addItem('x', 0, CX + 200, CY - 100, HW.GOLD.v);
    for (let i = 0; i < 6; i++) s.addItem('v', i % HW.vegSpr.length, CX - 300 + i * 115, CY + 40 + (i % 2) * 50, 0);
    for (let i = 0; i < 4; i++) s.addItem('m', i % HW.shroomSpr.length, CX - 250 + i * 160, CY - 60 + (i % 2) * 30, 0);
    while (nf++ < 40) s.addFood(CX - 310 + (nf * 97) % 620, CY - 140 + (nf * 53) % 280, [3, 5, 8][nf % 3]);
    S.adds.length = 0; S.rems.length = 0;
  }
  function build() {
    const s = A.sim, S = s.S, me = A.locals[0].me, P = A.locals[0].player; P.comp.lives = 99;
    // nobody dies (herd() puts every worm, every prop and the two clouds back on their marks); every bot keeps its trigger down and aims at the player
    s.kill = function () { }; on = true; herd();
    const think = HW.botThink; HW.botThink = function (sim, w, dt) { think(sim, w, dt); if (on) { const a = Math.atan2(me.y - w.y, me.x - w.x) + 0.2; w.inp.ax = Math.cos(a); w.inp.ay = Math.sin(a); w.inp.fire = true; } };
    const step = s.step; s.step = function (dt) { if (on) { if (n++ % 45 === 0) herd(); P.inp.ax = 1; P.inp.ay = 0.2; P.inp.fire = true; P.inp.mx = 1; P.inp.boost = true; } return step.call(this, dt); };
    A.locals[0].view.cam.x = me.x; A.locals[0].view.cam.y = me.y;
    return { worms: S.worms.length };
  }
  // what is on the player's screen right now
  function census() {
    alive(); const S = A.sim.S, v = A.locals[0].view, x0 = v.cam.x - R.W / 2, y0 = v.cam.y - R.H / 2, inV = (x, y) => x >= x0 && x <= x0 + R.W && y >= y0 && y <= y0 + R.H;
    const kinds = {}; for (const b of S.bullets) if (inV(b.x, b.y)) kinds[b.ch] = (kinds[b.ch] || 0) + 1;
    const it = {}; for (const i of S.items.values()) if (inV(i.x, i.y)) it[i.k] = (it[i.k] || 0) + 1;
    return { canvas: R.W + 'x' + R.H, worms: S.worms.filter(w => inV(w.x, w.y)).length, long: S.worms.filter(w => inV(w.x, w.y) && w.pts.length > 100).length, segs: S.worms.reduce((a, w) => a + w.pts.length, 0),
      bullets: S.bullets.length, onScreen: Object.values(kinds).reduce((a, b) => a + b, 0), kinds, flames: kinds[7] || 0, items: it, zones: S.zones.length, obstacles: HW.MAP.obs.filter(o => o.x1 > x0 && o.x0 < x0 + R.W && o.y1 > y0 && o.y0 < y0 + R.H).length, parts: HW.fx.parts.length };
  }
  // a fixed piece of work, to see how hard the CPU throttle really bites on this machine right now
  function calib() { let best = 1e9; for (let k = 0; k < 7; k++) { const t0 = performance.now(); let x = 0; for (let i = 0; i < 2e6; i++) x += Math.sqrt(i ^ k); best = Math.min(best, performance.now() - t0); } return best; }
  // where a busy frame goes: draw the same frame with one thing taken away at a time
  function parts(frames) {
    const S = A.sim.S, l = A.locals[0], v = l.view, me = alive(), fx = HW.fx;
    const tm = f => { const t0 = performance.now(); for (let i = 0; i < frames; i++) { f(100 + i / 60); R.ctx.getImageData(i % R.W, 0, 1, 1); } return (performance.now() - t0) / frames; };
    const view = () => tm(t => R.drawView(v, S, t)), o = {}; v.trip = 0; v.slow = 0; v.meId = me.id;
    while (fx.parts.length < 260) fx.burst(CX - 250 + Math.random() * 500, CY - 120 + Math.random() * 240, ['#fff'], 20, 0, 9, 2);
    while (fx.texts.length < 6) fx.text(CX - 100 + Math.random() * 200, CY, 'RAMPAGE!', '#ff5a4d');
    o.world = view(); v.trip = 5; o.trip = view() - o.world; v.trip = 0;
    o.hud = tm(t => R.drawHUD(v, { G: S, me, player: l.player, t, touch: true, roomCode: '', slotLabel: '', abilKey: '' }));
    o.touch = tm(t => R.drawTouch(HW.Input.tpads ? HW.Input.tpads[0] : HW.Input.touch, me, t, HW.CHARS[l.ch]));
    const P = fx.parts.splice(0); o.particles = o.world - view(); const T = fx.texts.splice(0); let base = view(); o.texts = (o.world - o.particles) - base;
    const B = S.bullets.splice(0); let q = view(); o.bullets = base - q; base = q;
    const Z = S.zones.splice(0); q = view(); o.zones = base - q; base = q;
    const I = new Map(S.items); S.items.clear(); q = view(); o.items = base - q; base = q;
    const W = S.worms.splice(0); q = view(); o.worms = base - q; o.floor = q;
    for (const w of W) S.worms.push(w); for (const [k, it] of I) S.items.set(k, it); for (const z of Z) S.zones.push(z); for (const b of B) S.bullets.push(b); for (const p of P) fx.parts.push(p); for (const x of T) fx.texts.push(x);
    for (const k in o) o[k] = Math.round(o[k] * 100) / 100; return o;
  }
  // the player's worm, alive (in the typical scene the bots may well have killed it)
  function alive() { const s = A.sim, l = A.locals[0], P = l.player; P.comp.lives = 99; for (let i = 0; i < 600 && !(P.worm && P.worm.alive); i++) { P.wantSpawn = true; s.step(1 / 60); s.S.events = []; s.S.adds.length = 0; s.S.rems.length = 0; } l.me = P.worm; return P.worm; }
  function sim(steps) { alive(); const s = A.sim, S = s.S, a = []; let bul = 0; for (let i = 0; i < steps; i++) { const t0 = performance.now(); s.step(1 / 60); a.push(performance.now() - t0); S.events = []; S.adds.length = 0; S.rems.length = 0; bul += S.bullets.length; } const r = stat(a); r.bullets = bul / steps; return r; }
  // one frame as main.js draws it: world, screen effects, HUD, touch controls. Every frame is flushed to pixels
  // (getImageData) so the cost of actually painting it is in the number, not put off until later.
  function draw(frames) {
    const s = A.sim, S = s.S, l = A.locals[0], v = l.view, a = [], cols = ['#fff', '#ffd23f', '#f08a1c', '#e03c32'];
    for (let i = 0; i < frames; i++) {
      const me = alive();
      if (i % 2 === 0) { s.step(1 / 60); S.events = []; S.adds.length = 0; S.rems.length = 0; }      // keep the scene moving (not timed)
      if (on) { while (HW.fx.parts.length < 260) HW.fx.burst(CX - 250 + Math.random() * 500, CY - 120 + Math.random() * 240, cols, 20, 120, 0.6, 2);
        if (HW.fx.texts.length < 6) HW.fx.text(CX - 100 + Math.random() * 200, CY, '-12', '#ff5a4d'); }
      const t = 100 + i / 60, t0 = performance.now();
      HW.fx.update(1 / 60); v.cam.x = me.x; v.cam.y = me.y; v.meId = me.id; if (on) { v.trip = i % 120 < 60 ? 5 : 0; v.slow = i % 90 < 30 ? 1 : 0; v.banner = { s: 'FEEDING FRENZY! LAST MINUTE', c: '#ff5a4d', t: 2 }; v.warn = i % 50 < 12 ? 0.2 : 0; }
      R.drawView(v, S, t); R.drawHUD(v, { G: S, me, player: l.player, t, touch: true, roomCode: '', slotLabel: '', abilKey: '' }); R.drawTouch(HW.Input.tpads ? HW.Input.tpads[0] : HW.Input.touch, me, t, HW.CHARS[l.ch]);
      R.ctx.getImageData(i % R.W, 0, 1, 1); a.push(performance.now() - t0);
    }
    v.trip = 0; v.slow = 0; return stat(a);
  }
  // the real loop: time spent inside every animation frame callback (input, sim steps, events, sound, draw, HUD)
  function live(ms) {
    return new Promise(res => { const a = [], gaps = []; let last = 0; const raf = window.requestAnimationFrame; window.requestAnimationFrame = cb => raf(ts => { const t0 = performance.now(); cb(ts); a.push(performance.now() - t0); if (last) gaps.push(ts - last); last = ts; });
      setTimeout(() => { window.requestAnimationFrame = raf; const r = a.length > 5 ? stat(a) : { mean: 0, p50: 0, p95: 0, max: 0 }; r.frames = a.length; r.fps = a.length / (ms / 1000); r.gap = gaps.length > 5 ? stat(gaps) : null; res(JSON.stringify(r)); }, ms); });
  }
  return { build, herd, census, sim, draw, live, calib, parts };
})();
"""
b = Browser(profile=SP + "/prof")
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 1.0)
    t.eval("localStorage.setItem('hw_diff','2')"); t.goto(URL, 1.0)
    t.eval("HW.App.startLocal([0])"); t.pump(1.0)
    t.eval("HW.Input.touch.used=true;HW.Input.lastKind='touch'"); t.eval(BENCH + ";0")
    res = {}
    def measure(scene):
        for rate in (1, THROTTLE):
            t.call("Emulation.setCPUThrottlingRate", {"rate": rate}); t.pump(0.3)
            cal = J(t, "PF.calib()"); sims, draws = [], []
            for rep in range(3):
                sims.append(J(t, "PF.sim(300)", 300)); draws.append(J(t, "PF.draw(150)", 300))
            s = min(sims, key=lambda q: q["mean"]); d = min(draws, key=lambda q: q["mean"])
            lv = json.loads(t.eval("PF.live(2500)", timeout=60))
            res[(scene, rate)] = {"sim": s, "draw": d, "live": lv, "cal": cal, "sims": sims, "draws": draws}
        t.call("Emulation.setCPUThrottlingRate", {"rate": 1})
        a, th = res[(scene, 1)], res[(scene, THROTTLE)]
        k = th["cal"] / a["cal"]; th["k"] = k; th["scale"] = min(1.0, THROTTLE / k)   # throttle biting harder than asked: other programs, not the game
        for rate, q in ((1, a), (THROTTLE, th)):
            s, d, lv = q["sim"], q["draw"], q["live"]
            print("%-8s %s: sim %.3f ms/step (p95 %.2f, max %.1f)   draw+HUD %.3f ms/frame (p95 %.2f, max %.1f)   sim+draw %.2f ms   [batches: sim %s, draw %s]" % (
                scene, "no throttle " if rate == 1 else "%dx throttle" % rate, s["mean"], s["p95"], s["max"], d["mean"], d["p95"], d["max"], s["mean"] + d["mean"],
                "/".join("%.2f" % x["mean"] for x in q["sims"]), "/".join("%.2f" % x["mean"] for x in q["draws"])))
            print("           real game loop: %.2f ms of work per frame (p95 %.2f), %.0f fps%s" % (lv["mean"], lv["p95"], lv["fps"], (", frame gaps p50 %.1f / p95 %.1f ms" % (lv["gap"]["p50"], lv["gap"]["p95"])) if lv.get("gap") else ""))
        print("           the %dx throttle measured %.1fx on a fixed loop; scaled to exactly %dx: sim %.2f + draw %.2f = %.2f ms a frame" % (
            THROTTLE, k, THROTTLE, th["sim"]["mean"] * th["scale"], th["draw"]["mean"] * th["scale"], (th["sim"]["mean"] + th["draw"]["mean"]) * th["scale"]))
        return a, th

    # ---- typical ----
    c = J(t, "PF.census()")
    print("typical scene: canvas %s, %d worms on screen, %d bullets, items on screen %s" % (c["canvas"], c["worms"], c["bullets"], c["items"]))
    J(t, "PF.sim(120)"); J(t, "PF.draw(60)")
    a, th = measure("typical")
    typ = (th["sim"]["mean"] + th["draw"]["mean"]) * th["scale"]
    ok(a["sim"]["mean"] + a["draw"]["mean"] <= BUDGET_TYPICAL / 2, "typical scene, no throttle: sim + draw + HUD = %.2f ms a frame" % (a["sim"]["mean"] + a["draw"]["mean"]), a)
    ok(typ <= BUDGET_TYPICAL, "typical scene, %dx throttle (mid-range phone): sim + draw + HUD = %.2f ms a frame, budget %.0f ms (60 fps with headroom)" % (THROTTLE, typ, BUDGET_TYPICAL), th)

    # ---- busy ----
    J(t, "PF.build()"); t.pump(0.5); J(t, "PF.sim(240)"); J(t, "PF.draw(60)")   # warm up: bullets in the air, sprites cached, JIT hot
    c = J(t, "PF.census()"); t.shot(SP + "/perf_scene.png")
    print("busy scene: %d worms on screen (%d long, %d body segments in all), %d bullets in the air (%d on screen, %d of them flames; kinds %s), items on screen %s, %d zones, %d obstacles, %d particles" % (
        c["worms"], c["long"], c["segs"], c["bullets"], c["onScreen"], c["flames"], sorted(c["kinds"].keys()), c["items"], c["zones"], c["obstacles"], c["parts"]))
    ok(c["worms"] >= 9 and c["long"] >= 3 and c["bullets"] >= 20 and c["flames"] >= 8 and len(c["kinds"]) >= 2 and c["zones"] == 2 and c["obstacles"] >= 2 and all(c["items"].get(k, 0) >= n for k, n in (("p", 1), ("g", 1), ("v", 2), ("m", 1), ("f", 30))),
       "the busy scene is busy: the worms with long ones on screen, special-gun fire with a flamethrower stream, zones, obstacles, every pickup", c)
    a, th = measure("busy")
    busy = (th["sim"]["mean"] + th["draw"]["mean"]) * th["scale"]; simT = th["sim"]["mean"] * th["scale"]
    bd = J(t, "PF.parts(40)")
    print("where a busy frame goes (ms, no throttle): world %.2f = floor+obstacles+graffiti %.2f, worms %.2f, items %.2f, particles %.2f, floating text %.2f, bullets %.2f, zones %.2f;  mushroom trip effect +%.2f;  HUD %.2f;  touch controls %.2f" % (
        bd["world"], bd["floor"], bd["worms"], bd["items"], bd["particles"], bd["texts"], bd["bullets"], bd["zones"], bd["trip"], bd["hud"], bd["touch"]))
    ok(a["sim"]["mean"] + a["draw"]["mean"] <= BUDGET_TYPICAL, "busy scene, no throttle: sim + draw + HUD = %.2f ms a frame (60 fps on a laptop even in the worst pile-up)" % (a["sim"]["mean"] + a["draw"]["mean"]), a)
    ok(simT <= BUDGET_SIM, "busy scene, %dx throttle: the simulation alone is %.2f ms a step, budget %.0f ms (four catch-up steps still fit in one frame)" % (THROTTLE, simT, BUDGET_SIM), th["sim"])
    ok(busy <= BUDGET_BUSY, "render.js: busy scene, %dx throttle (mid-range phone): sim + draw + HUD fits the budget of %.0f ms a frame (never under 30 fps)" % (THROTTLE, BUDGET_BUSY), "%.2f ms a frame; where it goes: %s" % (busy, bd))
    c2 = J(t, "PF.census()")
    ok(c2["worms"] >= 8 and c2["bullets"] >= 15 and c2["items"].get("f", 0) <= 130 and c2["items"].get("v", 0) <= 6 and c2["items"].get("g", 0) <= 5, "the busy scene stayed as it was to the end (%d worms on screen, %d bullets, %d pieces of food)" % (c2["worms"], c2["bullets"], c2["items"].get("f", 0)), c2)
    ok(not t.errors, "no page errors", t.errors)
finally:
    b.close()
print("\n%d failed: %s" % (len(FAIL), FAIL) if FAIL else "\nsmooth: inside the frame budgets")
sys.exit(1 if FAIL else 0)
