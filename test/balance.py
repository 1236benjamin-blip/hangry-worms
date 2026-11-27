"""Balance measurements: staged checks of what the bots do with the toys, fast-forwarded bots-only play, and matches
with a scripted ROOKIE in the human seat.

  HW_URL=http://127.0.0.1:8453/index.html HW_PORT=9453 python3 test/balance.py <scratch dir> [minutes=20] [runs=3] [diffs=1] [rookie=0]

  minutes, runs  bots-only: `runs` fresh arenas of `minutes` each, per difficulty (0 minutes: skip this part)
  diffs          difficulties to measure: 0 easy, 1 intermediate, 2 hard, a list like 0,2 or `all`
  rookie         rookie matches per worm per difficulty (0: skip). A match is 5 minutes or three lives.

Always first: the behaviour checks (a rampaging bot spares a player whose mercy timer is running, special guns are
fired without ammo and each from its own distance, pickups are fetched, ...). They take a few seconds.
Bots-only prints, per difficulty: deaths / kills / K/D / lifetime / causes per worm, arena deaths per minute, mass over
time, item counts, every gun's hit rate and how often its shots end on an obstacle, how long bots sit wedged, what each
power-up, special gun and golden burger is worth, and the sim cost. The rookie part prints how a new player fares:
first minute survival, time to first death, deaths, placing, and what a kill is worth next to a final score.

K/D per worm is noisy: bot seats are dealt at random (two or three of each worm), so one 20 minute arena says little
and even 3 x 20 minutes moves a worm's K/D by 0.2 or more from one call to the next. Compare numbers from 60 x 20.

Environment: HW_SET='js' is run in the page before measuring (try a number without editing a file, e.g.
HW_SET='HW.CHARS[3].gun.dmg=8'); HW_INJECT=a.js,b.js swaps whole files in; HW_JSON=path dumps the raw results."""
import sys, os, json, statistics
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
A = sys.argv
SP = A[1]; MIN = float(A[2]) if len(A) > 2 else 20; RUNS = int(A[3]) if len(A) > 3 else 3
DIFFS = [0, 1, 2] if len(A) > 4 and A[4] == "all" else [int(x) for x in (A[4] if len(A) > 4 else "1").split(",")]
ROOK = int(A[5]) if len(A) > 5 else 0
URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html")

HARNESS = r"""
window.BAL = (() => {
  const CFG = HW.CFG, CHARS = HW.CHARS, GUNS = HW.GUNS, MAP = HW.MAP, POWERS = HW.POWERS, SGUNS = HW.SGUNS, W = CFG.W, H = CFG.H, DT = 1 / 60;
  const names = CHARS.map(c => c.name), rnd = HW.util.rnd, angDiff = HW.util.angDiff;
  const zero = n => Array.from({ length: n }, () => 0), ITEMK = ['f', 'a', 'v', 'm', 'p', 'g', 'x'];

  // ---- probes: wrap a sim so that every death, shot, hit and pickup is attributed. Bots only: the human seat is counted apart. ----
  function probe(s) {
    const S = s.S, T = {
      st: names.map(() => ({ deaths: 0, kills: 0, life: 0, early: 0, peak: 0, veg: 0, shroom: 0, gotStuck: 0, diedStuck: 0, killsBy: {}, massAtDeath: 0, cause: {}, abil: 0, massT: 0, dryT: 0, liveT: 0, slowT: 0, stuckT: 0, boostT: 0, chillT: 0 })),
      gun: GUNS.map(() => ({ shots: 0, pellets: 0, hits: 0, dmg: 0, kills: 0, clang: 0, waste: 0 })),   // clang: shots that ended on an obstacle. waste: ...without having hit a worm first
      // act: seconds the effect was running. kills / deaths: by / of the holder while it ran. ram: kills by ramming
      pw: POWERS.map(() => ({ picks: 0, human: 0, by: zero(5), kills: 0, ram: 0, deaths: 0, act: 0 })),
      sg: SGUNS.map(() => ({ picks: 0, human: 0, by: zero(5), kills: 0, deaths: 0, act: 0 })),
      gold: { picks: 0, human: 0, by: zero(5), wasLead: 0, leadAfter: 0, checked: 0 },
      chill: { n: 0, killed: 0, byFreeze: 0 }, deaths: 0, liveT: 0,
      wedge: { win: 0, wedged: 0, pinned: 0, dither: 0, dwin: 0, spots: [] },
      mass: [], cnt: {}, cntN: 0, fMin: 1e9, fMax: 0, maxItems: 0, maxBul: 0, bad: [], ms: 0, steps: 0, die: []
    };
    for (const k of ITEMK) T.cnt[k] = 0;
    const born = new Map(), info = new Map(), goldCheck = [];
    let blastKind = -1, hitKind = -1;
    const shotAt = (x, y) => { for (const b of S.bullets) if (b.x === x && b.y === y) return b; return null; };
    const ox = s.explode; s.explode = function (b) { blastKind = b.ch; const r = ox.call(this, b); blastKind = -1; return r; };
    const od = s.damage; s.damage = function (w, dmg, owner, x, y) {
      const sh = blastKind >= 0 ? null : shotAt(x, y), k = blastKind >= 0 ? blastKind : sh ? sh.ch : -1; hitKind = k; if (sh) sh.struck = true;
      if (k >= 0 && w.alive && w.shield <= 0 && !(w.guard > 0)) { const g = T.gun[k]; g.hits++; g.dmg += Math.min(w.mass, dmg * (w.big > 0 ? POWERS[1].armor : 1) + w.mass * 0.02); }
      const r = od.call(this, w, dmg, owner, x, y); hitKind = -1; return r;
    };
    const ok = s.kill; s.kill = function (w, k, cause) {
      if (w.alive && cause !== 'left') {
        if (w.isBot) {
          if (w.stuck > 0) T.st[w.ch].diedStuck++;
          if (w.rage > 0) T.pw[0].deaths++; if (w.big > 0) T.pw[1].deaths++; if (w.guard > 0) T.pw[2].deaths++; if (w.sauce > 0) T.pw[3].deaths++;
          if (w.sg) T.sg[w.sg - 1].deaths++;
        }
        if (w.chill > 0) { T.chill.killed++; if (hitKind >= 5 && GUNS[hitKind].chill) T.chill.byFreeze++; }
        if (k && k !== w && k.alive && k.isBot) {
          if (k.rage > 0) { T.pw[0].kills++; if (cause === 'rampage') T.pw[0].ram++; }
          if (k.big > 0) T.pw[1].kills++; if (k.guard > 0) T.pw[2].kills++; if (k.sauce > 0) T.pw[3].kills++;
          if (cause === 'shot' && hitKind >= 0) { T.gun[hitKind].kills++; if (hitKind >= 5) T.sg[hitKind - 5].kills++; }
        }
      }
      return ok.call(this, w, k, cause);
    };
    const oe = s.ev; s.ev = function (k, x, y) { if (k === 'clang') { const b = shotAt(x, y); if (b) { T.gun[b.ch].clang++; if (!b.struck) T.gun[b.ch].waste++; } } return oe.apply(this, arguments); };

    // call after every step with the step number
    T.tick = function (i) {
      for (const e of S.events) {
        const k = e[0];
        if (k === 'spawn') { const w = S.worms.find(o => o.id === e[3]); if (w) { born.set(w.id, S.t); info.set(w.id, { ch: w.ch, bot: w.isBot, wx: w.x, wy: w.y, wst: true, dx: w.x, dy: w.y, px: w.x, py: w.y, path: 0 }); } }
        else if (k === 'die') {
          const q = info.get(e[3]), l = S.t - (born.get(e[3]) || 0); born.delete(e[3]); info.delete(e[3]);
          if (e[5] === 'left') continue;
          T.die.push({ t: S.t, ch: e[6], kch: e[7], cause: e[5], pid: e[8], kpid: e[9], life: l, mass: e[11] });
          if (e[8] < 0) { const c = T.st[e[6]]; T.deaths++; c.deaths++; c.life += l; if (l < 8) c.early++; c.massAtDeath += e[11]; c.cause[e[5]] = (c.cause[e[5]] || 0) + 1; }
          if (e[7] >= 0 && e[9] < 0) { const kc = T.st[e[7]]; kc.kills++; kc.killsBy[e[5]] = (kc.killsBy[e[5]] || 0) + 1; }
        }
        else if (k === 'shot') { const g = T.gun[e[3]]; g.shots++; g.pellets += GUNS[e[3]].pellets; }
        else if (k === 'veg' || k === 'shroom' || k === 'stuck' || k === 'fart' || k === 'puke') { const q = info.get(e[3]); if (q && q.bot) T.st[q.ch][k === 'stuck' ? 'gotStuck' : k === 'fart' || k === 'puke' ? 'abil' : k]++; }
        else if (k === 'power' || k === 'gun' || k === 'gold') {
          const q = info.get(e[3]), o = k === 'power' ? T.pw[e[4]] : k === 'gun' ? T.sg[e[4]] : T.gold; o.picks++;
          if (q) { if (q.bot) o.by[q.ch]++; else o.human++; }
          if (k === 'gold') { if (S.leader === e[3]) T.gold.wasLead++; goldCheck.push(S.t + 20, e[3]); }
        }
        else if (k === 'chill') T.chill.n++;
      }
      S.events = []; S.adds.length = 0; S.rems.length = 0;
      if (S.items.size > T.maxItems) T.maxItems = S.items.size; if (S.bullets.length > T.maxBul) T.maxBul = S.bullets.length;
      while (goldCheck.length && goldCheck[0] <= S.t) { T.gold.checked++; if (S.leader === goldCheck[1]) T.gold.leadAfter++; goldCheck.splice(0, 2); }
      if (i % 15 === 0) for (const w of S.worms) { const q = info.get(w.id); if (q) { q.path += Math.hypot(w.x - q.px, w.y - q.py); q.px = w.x; q.py = w.y; } }
      if (i % 20 === 0) for (const w of S.worms) {
        if (T.bad.length < 6 && !(isFinite(w.x) && isFinite(w.y) && isFinite(w.ang) && isFinite(w.aim) && isFinite(w.mass) && w.x >= 0 && w.y >= 0 && w.x <= W && w.y <= H && w.mass > 0 && w.pts.length >= 9)) T.bad.push('worm ' + names[w.ch] + ' ' + [w.x, w.y, w.ang, w.mass, w.pts.length].join(','));
        if (T.bad.length < 6 && MAP.hit(w.x, w.y, Math.max(0, w.r - 2))) T.bad.push('in obstacle ' + names[w.ch] + ' ' + Math.round(w.x) + ',' + Math.round(w.y));
        if (!w.isBot) continue;
        const c = T.st[w.ch]; c.liveT++; T.liveT++; c.massT += w.mass; if (w.ammo <= 0) c.dryT++; if (w.slow > 0) c.slowT++; if (w.stuck > 0) c.stuckT++; if (w.boosting) c.boostT++; if (w.chill > 0) c.chillT++; if (w.mass > c.peak) c.peak = Math.round(w.mass);
        if (w.rage > 0) T.pw[0].act++; if (w.big > 0) T.pw[1].act++; if (w.guard > 0) T.pw[2].act++; if (w.sauce > 0) T.pw[3].act++; if (w.sg) T.sg[w.sg - 1].act++;
      }
      // wedged: a bot that has moved less than 20 px in 2 s without being glued down by puke. That also catches a worm
      // grazing in a tight circle on open floor, so the ones actually leaning on an obstacle, a wall or a worm are counted apart (pinned)
      if (i % 120 === 0) for (const w of S.worms) {
        const q = info.get(w.id); if (!q || !q.bot) continue; const free = w.stuck <= 0;
        if (S.t - born.get(w.id) > 2.5) {
          T.wedge.win++;
          if (free && q.wst && Math.hypot(w.x - q.wx, w.y - q.wy) < 20) {
            T.wedge.wedged++; const m = w.r + 6, o = MAP.hit(w.x, w.y, Math.min(44, m));
            if (o || w.crash > 0 || w.x < m || w.y < m || w.x > W - m || w.y > H - m) { T.wedge.pinned++; if (T.wedge.spots.length < 12) T.wedge.spots.push(names[w.ch] + '@' + Math.round(w.x) + ',' + Math.round(w.y) + ':' + (o ? o.k : w.crash > 0 ? 'worm' : 'wall')); }
          }
        }
        q.wx = w.x; q.wy = w.y; q.wst = free;
      }
      // dithering: 4 s spent next to an obstacle going back and forth (ends up under a quarter of the distance covered away)
      if (i % 240 === 0) for (const w of S.worms) {
        const q = info.get(w.id); if (!q || !q.bot) continue;
        if (S.t - born.get(w.id) > 4.5) { T.wedge.dwin++; if (w.stuck <= 0 && q.path > 120 && Math.hypot(w.x - q.dx, w.y - q.dy) < q.path * 0.25 && MAP.hit(w.x, w.y, Math.min(44, w.r + 30))) T.wedge.dither++; }
        q.dx = w.x; q.dy = w.y; q.path = 0;
      }
      if (i % 600 === 0) {
        for (const b of S.bullets) if (T.bad.length < 6 && !(isFinite(b.x) && isFinite(b.y) && isFinite(b.vx))) T.bad.push('bullet ' + b.x + ',' + b.y);
        const cn = {}; for (const k of ITEMK) cn[k] = 0;
        for (const it of S.items.values()) { cn[it.k]++; if (T.bad.length < 6 && !(isFinite(it.x) && isFinite(it.y))) T.bad.push('item ' + it.k); }
        for (const k of ITEMK) { if (T.bad.length < 6 && cn[k] !== S.counts[k]) T.bad.push('count ' + k + ' ' + cn[k] + ' vs ' + S.counts[k]); T.cnt[k] += cn[k]; }
        T.cntN++; if (cn.f < T.fMin) T.fMin = cn.f; if (cn.f > T.fMax) T.fMax = cn.f;
        let m = 0, top = 0, n = 0; for (const w of S.worms) { if (!w.alive) continue; m += w.mass; n++; if (w.mass > top) top = w.mass; }
        T.mass.push([Math.round(S.t), n ? m / n : 0, top]);
      }
    };
    T.out = function () {
      const r1 = v => +v.toFixed(1), pc = (a, b) => Math.round(1000 * a / Math.max(1, b)) / 10, cnt = {}; for (const k of ITEMK) cnt[k] = r1(T.cnt[k] / Math.max(1, T.cntN));
      return {
        ms: T.ms / Math.max(1, T.steps), secs: S.t, maxItems: T.maxItems, maxBul: T.maxBul, bad: T.bad, counts: S.counts, cnt, fMin: T.fMin, fMax: T.fMax, deaths: T.deaths, liveS: T.liveT / 3,
        top: S.worms.map(w => names[w.ch] + ':' + Math.round(w.mass)).join(' '), mass: T.mass, wedge: T.wedge, gun: T.gun, pw: T.pw, sg: T.sg, gold: T.gold, chill: T.chill,
        st: T.st.map((c, i) => ({ n: names[i], deaths: c.deaths, kills: c.kills, liveS: c.liveT / 3, lifeSum: c.life, early: c.early, massT: c.massT, liveT: c.liveT, massAtDeath: c.massAtDeath, peak: c.peak,
          dry: c.dryT, slow: c.slowT, stuck: c.stuckT, boost: c.boostT, chill: c.chillT, abil: c.abil, veg: c.veg, shroom: c.shroom, gotStuck: c.gotStuck, diedStuck: c.diedStuck, killsBy: c.killsBy, cause: c.cause }))
      };
    };
    return T;
  }

  // ---- bots only ----
  function bots(minutes, diff) {
    const s = new HW.Sim({ diff }), T = probe(s), steps = Math.round(minutes * 3600);
    for (let i = 0; i < steps; i++) { const t0 = performance.now(); s.step(DT); T.ms += performance.now() - t0; T.tick(i); }
    T.steps = steps; return JSON.stringify(T.out());
  }
  // sim cost with nothing attached: the number a phone has to pay
  function cost(minutes, diff) {
    const s = new HW.Sim({ diff }), S = s.S, n = Math.round(minutes * 3600); for (let i = 0; i < 600; i++) { s.step(DT); S.events = []; S.adds.length = 0; S.rems.length = 0; }
    const t0 = performance.now(); for (let i = 0; i < n; i++) { s.step(DT); S.events = []; S.adds.length = 0; S.rems.length = 0; }
    return (performance.now() - t0) / n;
  }

  // ---- the rookie: a deliberately naive player in the human seat ----
  // Sees about a screen around itself. Decides a few times a second and acts a moment later, heads for the nearest
  // tasty thing, only notices what is right in front of its nose (and sometimes not even that), now and then holds
  // its course for a second or two without looking, shoots at whatever is close with a wobbly aim, never uses cover.
  // RK: how short-sighted and absent-minded it is. look: how far ahead of its nose it checks (px). miss: how often it
  // fails to notice what is there. hold: chance per decision of a spell of not looking (holdT seconds). aim: aiming
  // error (radians). jolt: seconds it takes to react to bumping into a worm.
  const RK = { look: [26, 52, 80], miss: 0.12, hold: 0.04, holdT: [1, 2], see: 230, aim: 0.42, range: 175, jolt: [0.22, 0.4] };
  const INP = () => ({ mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false });
  function rookieThink(s, p, R) {
    const S = s.S, w = p.worm, I = p.inp;
    if (!w || !w.alive) { I.fire = I.boost = false; I.mx = I.my = I.ax = I.ay = 0; R.next = null; R.think = 0.5; R.goal = 0; if (p.deadT > 3 && !p.comp.out) p.wantSpawn = true; return; }
    if (R.next && S.t >= R.next.at) { const n = R.next; R.next = null; I.mx = n.mx; I.my = n.my; I.ax = n.ax; I.ay = n.ay; I.fire = n.fire; I.boost = n.boost; if (n.abil) I.abil = true; }
    // a bump is felt (the game makes a point of it): after a moment's fright it wrenches the wheel away, even out of a daydream
    if (w.crash > 0) {
      if (!R.bump) R.bump = S.t + rnd(RK.jolt[0], RK.jolt[1]) + (R.hold > 0 ? 0.15 : 0);
      if (S.t >= R.bump) {
        let c = null, cq = 1e12; for (const o of S.worms) { if (o === w || !o.alive || s.nearestSeg(o, w.x, w.y, 30) > 900) continue; const q = s.hitPoint(o, w.x, w.y), d = (q.x - w.x) ** 2 + (q.y - w.y) ** 2; if (d < cq) { cq = d; c = q; } }
        if (c) { const ta = Math.atan2(c.y - w.y, c.x - w.x), a = ta + (angDiff(w.ang, ta) >= 0 ? 1 : -1) * 2.2; I.mx = Math.cos(a); I.my = Math.sin(a); R.swerve = a; R.swerveT = S.t + 0.6; R.hold = 0; R.next = null; R.goal = 0; R.think = 0.3; }
      }
      return;
    }
    R.bump = 0;
    R.think -= DT; if (R.think > 0) return;
    R.think = rnd(0.28, 0.5);
    if (R.hold > 0) { R.hold -= R.think; return; }                 // not looking
    if (Math.random() < RK.hold) { R.hold = rnd(RK.holdT[0], RK.holdT[1]); return; }    // ...starting now
    const C = CHARS[w.ch], g = HW.gunOf(w);
    // where to: stick with a target until it is gone or boring
    let it = R.goal ? S.items.get(R.goal) : null; if (it && (S.t > R.goalT || Math.hypot(it.x - w.x, it.y - w.y) > 320)) it = null;
    if (!it) {
      let bs = 0; const low = w.ammo < g.max * 0.3;
      for (const q of S.items.values()) {
        const dx = q.x - w.x, dy = q.y - w.y; if (dx > RK.see || dx < -RK.see || dy > RK.see || dy < -RK.see) continue;
        if (q.k === 'v' || q.k === 'm' || (q.k === 'a' && !low)) continue;
        const d = Math.hypot(dx, dy), v = q.k === 'f' ? q.v : q.k === 'a' ? 12 : 25, sc = v / (d + 30) * (1 - Math.abs(angDiff(Math.atan2(dy, dx), w.ang)) * 0.15);
        if (sc > bs) { bs = sc; it = q; }
      }
      if (it) { R.goal = it.id; R.goalT = S.t + 3; }
    }
    let ga;
    if (it) ga = Math.atan2(it.y - w.y, it.x - w.x);
    else { R.wander += rnd(-0.5, 0.5); if (w.x < 160 || w.y < 160 || w.x > W - 160 || w.y > H - 160) R.wander = Math.atan2(H / 2 - w.y, W / 2 - w.x) + rnd(-0.6, 0.6); ga = R.wander; }
    // danger: only what is just ahead of the nose, and it is missed one time in seven
    const hitAt = (x, y) => {
      for (const z of S.zones) if (z.owner !== w.id && (z.x - x) ** 2 + (z.y - y) ** 2 < z.r * z.r) return true;
      for (const o of S.worms) { if (o === w || !o.alive) continue; const m = o.r + w.r + 5; if (s.nearestSeg(o, x, y, m) < m * m) return true; }
      return false;
    };
    // how much of the way is free if it steers for heading a: follows the real turning circle, but only as far as RK.look
    const tr = C.speed / C.turn, s0 = Math.sin(w.ang), c0 = Math.cos(w.ang);
    const free = a => {
      const d = angDiff(a, w.ang), sg = d < 0 ? -1 : 1, arc = Math.abs(d) * tr; let n = 0;
      for (const l of RK.look) {
        let x, y; if (l < arc) { const h = w.ang + sg * l / tr; x = w.x + sg * tr * (Math.sin(h) - s0); y = w.y - sg * tr * (Math.cos(h) - c0); }
        else { x = w.x + sg * tr * (Math.sin(a) - s0) + Math.cos(a) * (l - arc); y = w.y - sg * tr * (Math.cos(a) - c0) + Math.sin(a) * (l - arc); }
        if (hitAt(x, y)) break; n++;
      }
      return n;
    };
    const full = RK.look.length;
    if (S.t < R.swerveT && free(R.swerve) === full) ga = R.swerve;   // still getting out of the way of the last thing
    else if (Math.random() > RK.miss && free(ga) < full) {
      // something in the way: take the nearest heading that looks free
      let pick = w.ang, best = -1; for (const o of [0, 0.7, -0.7, 1.4, -1.4, 2.1, -2.1, 2.8, -2.8]) { const f = free(w.ang + o); if (f > best) { best = f; pick = w.ang + o; if (f === full) break; } }
      ga = pick; R.swerve = ga; R.swerveT = S.t + 0.55; R.goal = 0;
    }
    const n = { at: S.t + rnd(0.12, 0.25), mx: Math.cos(ga), my: Math.sin(ga), ax: 0, ay: 0, fire: false, boost: w.mass > 50 && Math.random() < 0.05, abil: false };
    // shoot at whatever is close: no leading the target, and a fresh guess at the aim every time
    const RG = RK.range; let tq = RG * RG, tx = 0, ty = 0, hd = 1e9;
    for (const o of S.worms) {
      if (o === w || !o.alive || o.shield > 0) continue; const hq = Math.hypot(o.x - w.x, o.y - w.y); if (hq < hd) hd = hq;
      if (w.x < o.bx0 - RG || w.x > o.bx1 + RG || w.y < o.by0 - RG || w.y > o.by1 + RG) continue;
      for (let i = 0; i < o.pts.length; i += 3) { const dx = o.pts[i].x - w.x, dy = o.pts[i].y - w.y, q = dx * dx + dy * dy; if (q < tq) { tq = q; tx = dx; ty = dy; } }
    }
    if (tq < RG * RG && (w.ammo > 0 || w.sg) && Math.random() < 0.75) { const a = Math.atan2(ty, tx) + (Math.random() + Math.random() - 1) * RK.aim; n.ax = Math.cos(a); n.ay = Math.sin(a); n.fire = true; }
    if (C.ability && w.abil <= 0 && hd < 130 && Math.random() < 0.3) n.abil = true;
    R.next = n;
  }
  // one match with a rookie playing worm ch. Returns what happened to the rookie and how the match ended.
  function rookie(ch, diff) {
    const s = new HW.Sim({ diff }), S = s.S, T = probe(s), p = s.addPlayer(ch); p.inp = INP();
    const R = { think: 0.5, hold: 0, wander: Math.random() * 6.28, goal: 0, goalT: 0, next: null, swerve: 0, swerveT: 0, bump: 0 };
    let i = 0, aliveT = 0, prot = 0; const max = (CFG.MATCH_T + 5) * 60, D = HW.DIFFS[diff];
    const k0 = s.kill; s.kill = function (w, k, cause) { if (w.alive && w === p.worm && k && k.isBot && cause !== 'crash' && cause !== 'bonk' && (w.mercy > 0 || w.shield > 0 || CFG.MATCH_T - S.match.t < D.warm)) prot++; return k0.call(this, w, k, cause); };   // killed by a bot while off limits
    for (; i < max && !S.match.over; i++) { rookieThink(s, p, R); const t0 = performance.now(); s.step(DT); T.ms += performance.now() - t0; if (p.worm && p.worm.alive) aliveT += DT; T.tick(i); }
    T.steps = i;
    const el = CFG.MATCH_T - S.match.t, mine = T.die.filter(d => d.pid === p.pid), board = s.board(), botc = S.comps.filter(c => c.pid < 0), sc = botc.map(c => c.score).sort((a, b) => a - b);
    let lead = 0; for (const w of S.worms) if (w.alive && w.mass > lead) lead = w.mass;
    let pts = 0, kills = 0; for (const c of S.comps) { pts += c.pts; kills += c.kills; }
    return JSON.stringify({
      ch, diff, prot, reason: S.match.reason, len: el, first: mine.length ? mine[0].t : null, deaths: mine.length, lives: mine.map(d => d.life), causes: mine.map(d => d.cause), killers: mine.map(d => d.kch),
      place: board.indexOf(p.comp) + 1, score: p.comp.score, kills: p.comp.kills, peak: p.comp.peak, aliveT, picks: p.comp.st.pick, veg: p.comp.st.veg, shr: p.comp.st.shr, shots: p.comp.st.shots, hits: p.comp.st.hits,
      botScore: sc[sc.length >> 1], botBest: sc[sc.length - 1], botKills: botc.reduce((a, c) => a + c.kills, 0) / botc.length, lead, pts, killsAll: kills, botDeaths: T.deaths, botLiveS: T.liveT / 3,
      ms: T.ms / Math.max(1, i), bad: T.bad, pw: T.pw.map(q => [q.picks, q.human]), sg: T.sg.map(q => [q.picks, q.human]), gold: [T.gold.picks, T.gold.human]
    });
  }

  // ---- behaviour checks: small staged scenes, many trials each, that pin down what the bots are meant to do with the toys ----
  let SPOT = null;   // the emptiest place in the arena, so scenes are not disturbed by an obstacle
  function spot() {
    if (SPOT) return SPOT; let far = 0;
    for (let y = 300; y < H - 300; y += 40) for (let x = 300; x < W - 300; x += 40) { let d = 1e9; for (const o of MAP.obs) d = Math.min(d, Math.hypot(Math.max(o.x0 - x, 0, x - o.x1), Math.max(o.y0 - y, 0, y - o.y1))); if (d > far) { far = d; SPOT = { x, y }; } }
    return SPOT;
  }
  // an arena with nothing in it but `humans` player worms and `nb` bots
  function scene(humans, nb, diff) {
    const keep = CFG.WORMS; CFG.WORMS = humans.length + nb; const s = new HW.Sim({ diff }), n = CFG.WORMS; CFG.WORMS = keep;
    const fb = s.fillBots; s.fillBots = function () { const k = CFG.WORMS; CFG.WORMS = n; fb.call(this); CFG.WORMS = k; };
    const ps = humans.map(ch => { const p = s.addPlayer(ch); p.inp = INP(); return p; });
    for (let i = 0; i < 3; i++) s.step(DT);
    for (const it of Array.from(s.S.items.values())) s.remItem(it); s.S.respawns.length = 0; s.S.match.t = CFG.MATCH_T - 120;   // well past the warm-up
    s.addFood = function () { };   // and no food turning up to distract anybody
    return { s, S: s.S, h: ps.map(p => p.worm), b: s.S.worms.filter(w => w.isBot) };
  }
  function place(w, x, y, ang, mass) {
    if (mass) w.mass = mass; w.x = x; w.y = y; w.ang = ang; w.aim = ang; w.shield = 0; w.mercy = 0; w.cd = 0; w.bot && (w.bot.think = 0);
    const n = HW.segCount(w.mass); w.pts.length = 0; for (let i = 0; i < n; i++) w.pts.push({ x: x - Math.cos(ang) * i * 6, y: y - Math.sin(ang) * i * 6 });
    HW.follow(w); return w;
  }
  function run(sc, secs, each) { const ev = []; for (let i = 0; i < Math.round(secs * 60); i++) { sc.s.step(DT); for (const e of sc.S.events) ev.push(e); sc.S.events = []; sc.S.adds.length = 0; sc.S.rems.length = 0; if (each) each(); } return ev; }
  function checks() {
    const sp = spot(), out = [], N = 30, add = (name, ok, detail) => out.push([name, !!ok, detail]);
    // 1) rampage: a bot runs a player over, but not one whose mercy timer is running and not in the warm-up, even when
    //    it is already heading straight for them (head: true). On EASY it does not go after players at all.
    const ram = (diff, head, prep) => { let killed = 0; for (let i = 0; i < N; i++) { const sc = scene([1], 1, diff), h = sc.h[0], b = sc.b[0]; place(h, sp.x, sp.y, 0, 120);
        if (head) place(b, sp.x - 150 + i * 5, sp.y + 150, -Math.PI / 2, 60); else place(b, sp.x - 330 + i * 4, sp.y + 130, 0, 60);
        h.stuck = 99; b.rage = 6; prep(sc, h); const ev = run(sc, 5, () => { if (h.alive && h.keep) h.mercy = 5; }); if (ev.some(e => e[0] === 'die' && e[3] === h.id)) killed++; } return killed; };
    const r0 = ram(1, false, () => { }), r4 = ram(2, false, () => { }), r1 = ram(1, true, (sc, h) => { h.keep = true; h.mercy = 5; }), r2 = ram(1, true, sc => { sc.S.match.t = CFG.MATCH_T - 1; }), r5 = ram(0, true, (sc, h) => { h.keep = true; h.mercy = 5; }), r3 = ram(0, false, () => { });
    add('rampaging bot goes for a player and runs them over (INTERMEDIATE, HARD)', r0 > N * 0.6 && r4 > N * 0.6, [r0, r4]);
    add('...but not one whose mercy timer is running (INTERMEDIATE, EASY)', r1 === 0 && r5 === 0, [r1, r5]);
    add('...not during the warm-up', r2 === 0, r2);
    add('...and on EASY it does not go after players', r3 <= 1, r3);
    // 2) special guns: fired without ammo, each from its own distance; nothing wasted on a shot shield
    const gun = (sg, dist, prep) => { let shots = 0, near = 1e9, far = 0, n = 8; for (let i = 0; i < n; i++) { const sc = scene([1], 1, 1), h = sc.h[0], b = sc.b[0]; place(h, sp.x, sp.y, Math.PI / 2, 150); place(b, sp.x - dist, sp.y - 200 + i * 20, Math.PI / 2, 60); h.stuck = 99; b.ammo = 0; b.sg = sg; b.sgT = 30; b.bot.skill = 0.8; if (prep) prep(h, b);
        for (let k = 0; k < 300; k++) { sc.s.step(DT); for (const e of sc.S.events) if (e[0] === 'shot' && e[4] === b.id) { shots++; const d = Math.sqrt(sc.s.nearestSeg(h, b.x, b.y, 900)); if (d < near) near = d; if (d > far) far = d; } sc.S.events = []; sc.S.adds.length = 0; sc.S.rems.length = 0; } } return { shots: shots / n, near: Math.round(near), far: Math.round(far) }; };   // near / far: head to target when a shot went off
    const g1 = gun(1, 200), g2 = gun(2, 200), g3 = gun(3, 200), g4 = gun(4, 140), g5 = gun(5, 200), gs = gun(4, 140, h => { h.guard = 30; });
    add('a bot with a special gun fires it with an empty magazine', g1.shots > 2 && g4.shots > 20 && g5.shots > 2, [g1, g4, g5]);
    add('ray gun and freeze ray are used from range', g1.far > 170 && g5.far > 170, [g1.far, g5.far]);
    add('flamethrower only up close (it closes in first)', g3.shots > 20 && g3.far < 135, g3);
    add('rocket launcher: never point blank', g2.shots >= 1 && g2.near >= 70, g2);
    add('minigun: long bursts', g4.shots > 25, g4.shots);
    add('no shooting at a worm behind a shot shield', gs.shots === 0, gs);
    // 3) a rampaging worm bearing down from the side: the bot turns tail (stick within 60 degrees of straight away from it)
    //    and is still alive three seconds later. (Nothing saves a worm from a rampage that comes straight down the line
    //    of its own body, so that is not the test.)
    let away = 0, alive = 0; for (let i = 0; i < N; i++) { const sc = scene([1], 1, 1), h = sc.h[0], b = sc.b[0]; place(h, sp.x + 60 + i, sp.y - 210, Math.PI / 2, 60); place(b, sp.x, sp.y, 0, 80); h.rage = 9; h.inp.my = 1; b.bot.skill = 0.7;
      run(sc, 0.6, () => { }); const dx = b.x - h.x, dy = b.y - h.y; if ((dx * b.inp.mx + dy * b.inp.my) / Math.hypot(dx, dy) > 0.5) away++; run(sc, 2.4, () => { }); if (b.alive) alive++; }
    add('bots run from a rampaging worm', away > N * 0.8 && alive > N * 0.8, 'turned away ' + away + '/' + N + ', alive after 3 s ' + alive + '/' + N);
    // 4) pickups: taken on INTERMEDIATE and HARD; on EASY left for the player standing next to them
    const grab = (diff, k) => { let got = 0; for (let i = 0; i < N; i++) { const sc = scene([1], 1, diff), h = sc.h[0], b = sc.b[0]; place(h, sp.x + 60, sp.y + 60, 0, 60); h.stuck = 99; h.mercy = 99; place(b, sp.x - 220, sp.y - 30 + i * 2, 0, 60); sc.s.addItem(k, k === 'x' ? 0 : i % 4, sp.x, sp.y, k === 'x' ? HW.GOLD.v : 0);
        const ev = run(sc, 5, () => { h.mercy = 99; }); if (ev.some(e => (e[0] === 'power' || e[0] === 'gun' || e[0] === 'gold') && e[3] === b.id)) got++; } return got; };
    const p1 = grab(1, 'p'), q1 = grab(1, 'g'), x1 = grab(2, 'x'), p0 = grab(0, 'p');
    add('bots go and get power-ups, special guns and the golden burger', p1 > N * 0.8 && q1 > N * 0.8 && x1 > N * 0.8, [p1, q1, x1]);
    add('...but on EASY leave them for a player who is near', p0 < N * 0.2, p0);
    // 5) veggies are not food, countdown bonus or not
    let ate = 0; for (let i = 0; i < N; i++) { const sc = scene([], 1, 1), b = sc.b[0]; place(b, sp.x - 150, sp.y, 0, 60); b.abil = 50; b.bot.skill = 0.8; sc.s.addItem('v', 0, sp.x, sp.y + i - 15, 0); if (run(sc, 4, () => { }).some(e => e[0] === 'veg')) ate++; }
    add('bots do not eat veggies for the countdown bonus', ate <= 1, ate);
    return JSON.stringify(out);
  }
  return { bots, cost, rookie, probe, rookieThink, RK, checks, scene, place, run, spot };
})();
"""

CH = ["BEN", "CHANDLER", "NATE", "WESLEY", "JEFF"]
def add(a, b):
    """sum two result trees (numbers add, lists of numbers add elementwise, dicts merge)"""
    if isinstance(b, dict):
        a = a if isinstance(a, dict) else {}
        for k, v in b.items(): a[k] = add(a.get(k), v)
        return a
    if isinstance(b, list): return [add(a[i] if a and i < len(a) else None, v) for i, v in enumerate(b)]
    if isinstance(b, (int, float)) and not isinstance(b, bool): return (a or 0) + b
    return b
pc = lambda a, b: 100.0 * a / b if b else 0.0
def kv(d): return " ".join("%s %d" % q for q in sorted(d.items(), key=lambda q: -q[1]))
def who(by, human=0): return " ".join("%s %d" % (CH[i][:3], n) for i, n in enumerate(by) if n) + (" rookie %d" % human if human else "")

def bots_report(t, diff, name, out):
    runs = []; allbad = []
    for run in range(RUNS):
        d = json.loads(t.eval("BAL.bots(%s,%d)" % (MIN, diff), timeout=900)); runs.append(d); allbad += d["bad"]
        kd = " ".join("%s %.2f" % (c["n"][:3], c["kills"] / max(1, c["deaths"])) for c in d["st"])
        print("  run %d: %.3f ms/step, %.1f deaths/min, K/D %s | maxItems %d maxBullets %d %s" % (run + 1, d["ms"], d["deaths"] / MIN, kd, d["maxItems"], d["maxBul"], ("SANITY: %s" % d["bad"]) if d["bad"] else ""))
    mins = MIN * RUNS; tot = {}
    for d in runs: tot = add(tot, {k: d[k] for k in ("st", "gun", "pw", "sg", "gold", "chill", "deaths", "liveS", "cnt")});
    wedge = add(None, {});
    for d in runs: wedge = add(wedge, {k: v for k, v in d["wedge"].items() if k != "spots"})
    spots = sum((d["wedge"]["spots"] for d in runs), [])
    print("\n%-9s %6s %6s %5s %7s %6s %7s %7s %5s  died of  /  killed with" % ("worm", "deaths", "kills", "K/D", "life s", "early%", "avgMass", "atDeath", "dry%"))
    lifes = []
    for c in tot["st"]:
        life = c["liveS"] / max(1, c["deaths"]); lifes.append(life)
        print("%-9s %6d %6d %5.2f %7.1f %6.1f %7.1f %7.1f %5.1f  %s  /  %s" % (c["n"], c["deaths"], c["kills"], c["kills"] / max(1, c["deaths"]), life, pc(c["early"], c["deaths"]), c["massT"] / max(1, c["liveT"]), c["massAtDeath"] / max(1, c["deaths"]), pc(c["dry"], c["liveT"]), kv(c["cause"]), kv(c["killsBy"])))
    print("%-9s abil/min %s | veg/min %s | shroom/min %s | puke-stuck %% of time %s | boost %% %s" % ("", *[" ".join("%.2f" % (c[k] / max(1, c["liveS"]) * 60) for c in tot["st"]) for k in ("abil", "veg", "shroom")], " ".join("%.1f" % pc(c["stuck"], c["liveT"]) for c in tot["st"]), " ".join("%.1f" % pc(c["boost"], c["liveT"]) for c in tot["st"])))
    dpm = tot["deaths"] / mins; avglife = tot["liveS"] / max(1, tot["deaths"])
    print("PACE: %.1f deaths/min arena-wide, average bot lifetime %.1f s (longest-lived worm lives %.0f%% longer than the shortest)" % (dpm, avglife, 100 * (max(lifes) / max(1e-9, min(lifes)) - 1)))
    # mass over time: every run starts from a fresh arena, so minute 5 is what a match ends on
    marks = [m for m in (1, 2, 3, 5, 10, 15, 20, 30) if m <= MIN]
    row = []
    for m in marks:
        pts = [q for d in runs for q in d["mass"] if m * 60 - 30 <= q[0] <= m * 60 + 30]
        if pts: row.append("%dmin avg %.0f leader %.0f" % (m, statistics.mean(q[1] for q in pts), statistics.mean(q[2] for q in pts)))
    print("MASS: " + " | ".join(row))
    cnt = {k: v / RUNS for k, v in tot["cnt"].items()}
    print("ITEMS (average on the map): food %.0f (min %d, max %d; CFG.FOOD %d) crates %.1f veg %.1f shrooms %.1f power-ups %.2f guns %.2f gold %.2f" % (cnt["f"], min(d["fMin"] for d in runs), max(d["fMax"] for d in runs), t.eval("HW.CFG.FOOD"), cnt["a"], cnt["v"], cnt["m"], cnt["p"], cnt["g"], cnt["x"]))
    gn = t.eval("JSON.stringify(HW.GUNS.map(g=>g.name))"); gn = json.loads(gn)
    print("\n%-24s %7s %6s %7s %6s %7s %7s %7s" % ("gun", "shots", "hit%", "dmg/sh", "kills", "kills/m", "clang%", "waste%"))
    pel = clang = waste = 0
    for i, g in enumerate(tot["gun"]):
        pel += g["pellets"]; clang += g["clang"]; waste += g["waste"]
        print("%-24s %7d %6.1f %7.2f %6d %7.2f %7.1f %7.1f" % (gn[i], g["shots"], pc(g["hits"], g["pellets"]), g["dmg"] / max(1, g["shots"]), g["kills"], g["kills"] / mins, pc(g["clang"], g["pellets"]), pc(g["waste"], g["pellets"])))
    print("OBSTACLES: %.1f%% of all shots end on an obstacle (%.1f%% without having hit a worm first) | bots moved under 20 px in 2 s %.2f%% of the time (%d of %d windows): %.2f%% leaning on an obstacle, wall or worm, the rest grazing in a tight circle | dithering beside an obstacle %.2f%% %s" % (
        pc(clang, pel), pc(waste, pel), pc(wedge["wedged"], wedge["win"]), wedge["wedged"], wedge["win"], pc(wedge["pinned"], wedge["win"]), pc(wedge["dither"], wedge["dwin"]), spots[:6] if spots else ""))
    base = tot["deaths"] / max(1, tot["liveS"])   # deaths per second of bot life: the yardstick for "safer while it lasts"
    pn = json.loads(t.eval("JSON.stringify(HW.POWERS.map(g=>g.name))")); sn = json.loads(t.eval("JSON.stringify(HW.SGUNS.map(g=>g.name))"))
    print("\n%-24s %6s %7s %10s %7s %9s  %s" % ("pickup", "picks", "per min", "kills/pick", "K/D", "risk x", "picked up by"))
    allp = 0
    for nm, q in list(zip(pn, tot["pw"])) + list(zip(sn, tot["sg"])):
        allp += q["picks"]; risk = (q["deaths"] / max(1, q["act"] / 3)) / base if base else 0
        extra = " (rammed %d)" % q["ram"] if q.get("ram") else ""
        print("%-24s %6d %7.2f %10.2f %7.2f %9.2f  %s%s" % (nm, q["picks"], q["picks"] / mins, q["kills"] / max(1, q["picks"]), q["kills"] / max(1, q["deaths"]), risk, who(q["by"], q["human"]), extra))
    g = tot["gold"]; allp += g["picks"]
    print("%-24s %6d %7.2f %10s %7s %9s  %s | already the leader %.0f%%, leader 20 s later %.0f%%" % ("GOLDEN BURGER", g["picks"], g["picks"] / mins, "", "", "", who(g["by"], g["human"]), pc(g["wasLead"], g["picks"]), pc(g["leadAfter"], g["checked"])))
    c = tot["chill"]
    print("TOYS: a pickup every %.1f s arena-wide | risk x = holder's death rate while it runs / normal death rate | frozen worms: %d chills, %d died while chilled (%d of them to the freeze ray itself)" % (60 * mins / max(1, allp), c["n"], c["killed"], c["byFreeze"]))
    ms = statistics.median(d["ms"] for d in runs)
    print("SIM COST: %.3f ms/step with probes | sanity failures (NaN, out of arena, inside an obstacle, item count drift): %s" % (ms, allbad or "none"))
    out["bots"][name] = {"runs": runs, "kd": {c["n"]: c["kills"] / max(1, c["deaths"]) for c in tot["st"]}, "life": dict(zip(CH, lifes)), "dpm": dpm, "avglife": avglife}
    return allbad

def med(v): return statistics.median(v) if v else 0.0
def rookie_report(t, diff, name, out):
    res = []; T = float(t.eval("HW.CFG.MATCH_T"))
    for ch in range(5):
        for k in range(0, ROOK, 4):
            n = min(4, ROOK - k)
            res += json.loads(t.eval("'['+Array.from({length:%d},()=>BAL.rookie(%d,%d)).join(',')+']'" % (n, ch, diff), timeout=900))
    print("\n%-9s %4s %7s %9s %7s %6s %7s %7s %6s %6s %6s %7s %7s  died of" % ("rookie", "n", "live60%", "1st death", "deaths", "out%", "<10s%", "life s", "place", "score", "kills", "botScr", "botKil"))
    def line(nm, rs):
        first = [r["first"] if r["first"] is not None else T for r in rs]; lives = [l for r in rs for l in r["lives"]]
        causes = {}
        for r in rs:
            for c in r["causes"]: causes[c] = causes.get(c, 0) + 1
        s60 = pc(sum(1 for f in first if f > 60), len(rs)); m = med(first)
        print("%-9s %4d %7.0f %9s %7.2f %6.0f %7.1f %7.1f %6.1f %6.0f %6.2f %7.0f %7.2f  %s" % (nm, len(rs), s60, ("%.0f" % m) if m < T else ">%d" % T, statistics.mean(r["deaths"] for r in rs), pc(sum(1 for r in rs if r["reason"] == "lives"), len(rs)),
              pc(sum(1 for l in lives if l < 10), len(lives)), sum(r["aliveT"] for r in rs) / max(1, sum(r["deaths"] for r in rs)), statistics.mean(r["place"] for r in rs), statistics.mean(r["score"] for r in rs), statistics.mean(r["kills"] for r in rs),
              statistics.mean(r["botScore"] for r in rs), statistics.mean(r["botKills"] for r in rs), kv(causes)))
        return {"live60": s60, "first": m, "deaths": statistics.mean(r["deaths"] for r in rs), "place": statistics.mean(r["place"] for r in rs), "score": statistics.mean(r["score"] for r in rs), "kills": statistics.mean(r["kills"] for r in rs)}
    o = {}
    for ch in range(5): o[CH[ch]] = line(CH[ch], [r for r in res if r["ch"] == ch])
    o["ALL"] = line("ALL", res)
    kil = {}
    for r in res:
        for k in r["killers"]: kil[CH[k] if k >= 0 else "nobody"] = kil.get(CH[k] if k >= 0 else "nobody", 0) + 1
    full = [r for r in res if r["reason"] == "time"]
    print("killed by a bot while off limits (mercy timer or warm-up; own crashes not counted): %d" % sum(r["prot"] for r in res))
    print("killed by: %s | rookie picks up %.1f toys a match, eats %.1f veggies and %.1f mushrooms, hits with %.0f%% of shots" % (kv(kil), statistics.mean(r["picks"] for r in res), statistics.mean(r["veg"] for r in res), statistics.mean(r["shr"] for r in res), pc(sum(r["hits"] for r in res), sum(r["shots"] for r in res))))
    dpm = 60 * sum(r["botDeaths"] + r["deaths"] for r in res) / max(1, sum(r["len"] for r in res))
    print("bots in these matches: %.1f deaths/min arena-wide (rookie included), bot lifetime %.1f s" % (dpm, sum(r["botLiveS"] for r in res) / max(1, sum(r["botDeaths"] for r in res))))
    if full:
        ppk = sum(r["pts"] for r in full) / max(1, sum(r["killsAll"] for r in full)); typ = statistics.mean(r["botScore"] for r in full); best = statistics.mean(max(r["botBest"], r["score"]) for r in full)
        print("ECONOMY (%d matches that ran the full %d s): leader mass at the whistle %.0f (median; range %.0f..%.0f) | winning score %.0f, median bot score %.0f | a kill is worth %.1f points on average = %.0f%% of a median score, %.0f%% of a winning one" % (
            len(full), T, med([r["lead"] for r in full]), min(r["lead"] for r in full), max(r["lead"] for r in full), best, typ, ppk, pc(ppk, typ), pc(ppk, best)))
    bad = sum((r["bad"] for r in res), [])
    print("sim cost %.3f ms/step with probes | sanity failures: %s" % (med([r["ms"] for r in res]), bad or "none"))
    out["rookie"][name] = {"by": o, "res": res}
    return bad

b = Browser(profile=SP + "/prof")
try:
    t = b.tab()
    t.goto(URL, 1.0)   # (Tab.init already turns the cache off, so an edited sim.js / bots.js is always the one measured)
    for f in filter(None, os.environ.get("HW_INJECT", "").split(",")): t.eval(open(f).read() + "\n;0"); print("injected", f)  # A/B: swap in another sim.js / bots.js
    if os.environ.get("HW_SET"): t.eval(os.environ["HW_SET"] + "\n;0"); print("set:", os.environ["HW_SET"])
    t.eval(HARNESS + ";0")
    names = json.loads(t.eval("JSON.stringify(HW.DIFFS.map(d=>d.name))")); out = {"bots": {}, "rookie": {}}; bad = []
    print("========== BOT BEHAVIOUR CHECKS ==========")
    for name, good, detail in json.loads(t.eval("BAL.checks()", timeout=300)):
        print(("ok   " if good else "FAIL ") + name, "" if good and not os.environ.get("HW_VERBOSE") else detail)
        if not good: bad.append("behaviour: " + name)
    for diff in DIFFS:
        if MIN > 0:
            print("\n========== BOTS ONLY, %s: %d x %g min ==========" % (names[diff], RUNS, MIN)); bad += bots_report(t, diff, names[diff], out)
        if ROOK > 0:
            print("\n========== ROOKIE vs %s bots: %d matches per worm ==========" % (names[diff], ROOK)); bad += rookie_report(t, diff, names[diff], out)
    cost = sorted(t.eval("BAL.cost(2,%d)" % DIFFS[0], timeout=300) for _ in range(3))
    print("\nSIM COST, nothing attached (%s, best / median of 3 x 2 min): %.3f / %.3f ms per step" % (names[DIFFS[0]], cost[0], cost[1]))
    print("SANITY FAILURES overall:", bad or "none")
    print("JS errors:", t.errors or "none")
    if os.environ.get("HW_JSON"): json.dump(out, open(os.environ["HW_JSON"], "w"))
finally: b.close()
