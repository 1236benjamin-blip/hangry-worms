"""Online multiplayer tests for Hangry Worms.

Part A (no network): net.js is driven through fake connections inside one page, on a virtual clock, so every
case is exact and repeatable: item / worm sync under heavy churn, worst-case message sizes, malformed input,
room full, joins in the same tick, slow clients, time-outs, ability / respawn flags, interpolation smoothness,
bandwidth; the state added with power-ups, special guns, frenzy, awards and taunts; prediction of the client's own
worm on links with 60 to 300 ms round trip.
Part B (real PeerJS cloud, needs internet): a host tab and three client tabs, a fifth player being turned away,
input round trip, leaving, signalling loss, error messages for bad codes, stale sessions.
Part C (no internet): the real game in two tabs, host and client, joined through a stand-in for PeerJS that carries the
messages between the tabs with a fixed delay. Checks what only the real loop can show: the join, the client's own worm
answering a key press at once while the host's answer is still on its way, taunt key, power-up / special gun / frenzy /
awards on the client's screen.

  python3 -m http.server 8377        (in the project folder)
  HW_PORT=9413 python3 test/online.py /tmp/out [url] [a|b|c]
"""
import sys, time, os, json, math
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("http") else os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html")
ONLY = sys.argv[-1] if sys.argv[-1] in ("a", "b", "c") else ""
FAILS = []
def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ((" - " + str(detail)) if detail != "" else ""))
    if not ok: FAILS.append(name)

# ---------- page-side harness for part A ----------
HARNESS = r"""
window.TH = (() => {
  const Net = HW.Net, CFG = HW.CFG; let vt = 1000;
  const fin = v => typeof v === 'number' && isFinite(v);
  const INP = () => ({ mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false });
  // the emptiest places in the arena (nothing but floor within .d px): tests that need a clear run use them
  const SPOTS = (() => {
    const l = []; for (let y = 200; y <= CFG.H - 200; y += 40) for (let x = 200; x <= CFG.W - 200; x += 40) {
      let d = Math.min(x, y, CFG.W - x, CFG.H - y); for (const o of HW.MAP.obs) d = Math.min(d, Math.hypot(Math.max(o.x0 - x, 0, x - o.x1), Math.max(o.y0 - y, 0, y - o.y1)));
      l.push({ x, y, d });
    }
    return l.sort((a, b) => b.d - a.d);
  })();
  const OPEN = SPOTS[0], OPEN2 = SPOTS.find(q => Math.hypot(q.x - OPEN.x, q.y - OPEN.y) > 1100);
  // lay a worm out straight, head at (x, y), pointing along ang
  function place(w, x, y, ang, mass) {
    if (mass) w.mass = mass; w.x = x; w.y = y; w.ang = ang; w.aim = ang;
    const n = HW.segCount(w.mass); w.pts.length = 0; for (let i = 0; i < n; i++) w.pts.push({ x: x - Math.cos(ang) * i * 6, y: y - Math.sin(ang) * i * 6 });
    HW.follow(w); return w;
  }
  function mkConn(ser) {
    return { open: true, serialization: ser || 'json', dataChannel: { bufferedAmount: 0 }, h: {}, out: [], max: 0, bytes: 0, n: 0,
      on(ev, f) { this.h[ev] = f; }, send(m) { const s = JSON.stringify(m); if (s.length > this.max) this.max = s.length; this.bytes += s.length; this.n++; this.out.push(s); },
      close() { if (this.open) { this.open = false; if (this.h.close) this.h.close(); } }, recv(m) { this.h.data(m); } };
  }
  function join(X, ch, hello) {
    const conn = mkConn(), c = X.accept(conn); if (c) conn.recv(hello || { t: 'hello', ch, v: 4 });
    const k = { conn, c, G: Net.newMirror(), G2: null, pid: -1, first: 0, ev: 0, evs: null, other: [], zs: 0, seq: 0 }; X.cl.push(k); return k;
  }
  function setup(n) {
    Net.now = () => vt;
    const sim = new HW.Sim(); sim.S.events = []; sim.S.adds.length = 0; sim.S.rems.length = 0;
    const X = { sim, cl: [], accept: Net._loop(() => sim), old: { n: 0, bytes: 0, max: 0 } };
    X.host = sim.addPlayer(0); X.host.inp = INP();
    for (let i = 0; i < n; i++) join(X, i + 1);
    return X;
  }
  function deliver(k) {
    for (const s of k.conn.out) {
      const m = JSON.parse(s);
      if (m.t === 'init') k.pid = m.pid;
      else if (m.t === 'it' || m.t === 'pt') { if (m.z) k.zs++; Net.applyPart(k.G, m); }
      else if (m.t === 's') { Net.applySnap(k.G, m); if (m.first) k.first++; k.ev += m.e.length; if (k.evs) for (const e of m.e) k.evs.push(e); }
      else k.other.push(m);
      if (k.G2) { const m2 = JSON.parse(s); if (m2.t === 'it' || m2.t === 'pt') Net.applyPart(k.G2, m2); else if (m2.t === 's') Net.applySnap(k.G2, m2); }
    }
    k.conn.out.length = 0;
  }
  // the snapshot format before the rewrite, measured on the same states for comparison
  function oldSize(S, evs) {
    const r1 = v => Math.round(v * 10) / 10, c10 = v => Math.ceil(Math.max(0, v) * 10);
    return JSON.stringify({ t: 's', w: S.worms.filter(w => w.alive).map(w => [w.id, w.ch, w.variant, Math.round(w.x), Math.round(w.y), Math.round(w.ang * 100), Math.round(w.aim * 100), Math.round(w.mass * 10), (w.boosting ? 1 : 0) | (w.isBot ? 2 : 0), w.ammo, c10(w.abil), c10(w.stuck), c10(w.slow), c10(w.trip), w.kills, w.pid, c10(w.shield)]),
      b: S.bullets.map(b => [b.id, b.ch, Math.round(b.x), Math.round(b.y), Math.round(b.vx), Math.round(b.vy), b.c]),
      z: S.zones.map(z => [z.id, z.k, Math.round(z.x), Math.round(z.y), z.r, r1(z.t), z.owner]),
      a: S.adds.map(it => [it.id, it.k, it.type, Math.round(it.x), Math.round(it.y), it.v]), r: S.rems.slice(), e: evs,
      p: S.players.map(p => [p.pid, p.worm && p.worm.alive ? p.worm.id : 0, r1(p.deadT), p.lastKiller || '', p.lastCause || '', p.lastScore || 0, Math.round(p.best || 0), p.everSpawned ? 1 : 0]) }).length;
  }
  // like main.js advance(): step the sim, then feed the network. Returns true when a snapshot went out.
  function tick(X, steps, dt) {
    steps = steps === undefined ? 3 : steps; dt = dt === undefined ? steps / 60 + 1e-6 : dt; vt += dt;
    for (let i = 0; i < steps; i++) X.sim.step(1 / 60);
    const S = X.sim.S, evs = S.events; S.events = []; X.evAcc = (X.evAcc || []).concat(evs);
    const willSend = Net.acc + dt >= Net.SNAP;
    if (willSend && Net.conns.length) { const n = oldSize(S, X.evAcc); X.old.n++; X.old.bytes += n; if (n > X.old.max) X.old.max = n; }
    const sent = Net.hostTick(X.sim, dt, evs);
    if (sent) { S.adds.length = 0; S.rems.length = 0; X.evAcc = []; for (const k of X.cl) deliver(k); }
    for (const k of X.cl) { Net.clientUpdate(k.G, dt); if (k.G2) Net.clientUpdate(k.G2, dt); }
    return sent;
  }
  function diff(X, k) {
    const S = X.sim.S, G = k.G; let miss = 0, extra = 0, wrong = 0, wbad = 0, why = '';
    for (const [id, it] of S.items) { const o = G.items.get(id); if (!o) miss++; else if (o.k !== it.k || o.type !== it.type || o.v !== it.v) wrong++; }
    for (const id of G.items.keys()) if (!S.items.has(id)) extra++;
    const hw = S.worms.filter(w => w.alive), cw = G.worms.map(w => w.id).sort((a, b) => a - b);
    for (const w of hw) {
      const m = G.wmap.get(w.id); if (!m) { wbad++; why = why || 'missing'; continue; }
      const s = m.q[m.q.length - 1];
      const fresh = Math.abs(s.t - Math.round(S.t * 1000) / 1000) < 1e-6; // far worms are only refreshed every other snapshot
      if (m.ch !== w.ch || m.variant !== w.variant || m.ammo !== w.ammo || m.kills !== w.kills || m.pid !== w.pid || m.sg !== w.sg || Math.abs(m.mass - w.mass) > (fresh ? 0.06 : 1e9) || (fresh && Math.hypot(s.x - w.x, s.y - w.y) > 0.75)) { wbad++; why = why || JSON.stringify(['core', fresh, m.ch, w.ch, m.variant, w.variant, m.ammo, w.ammo, m.kills, w.kills, m.pid, w.pid, m.sg, w.sg, m.mass, w.mass, s.x, w.x, s.y, w.y]); }
      else if (Math.hypot(s.x - w.x, s.y - w.y) > 24 || TIMERS.some(t => Math.abs(Math.max(0, m[t]) - Math.max(0, w[t])) > 0.35)) { wbad++; why = why || JSON.stringify(['timer', fresh, s.x, w.x, s.y, w.y].concat(TIMERS.map(t => [t, +m[t].toFixed(2), +w[t].toFixed(2)]))); }
    }
    const hb = new Map(S.bullets.map(b => [b.id, b])); let bbad = 0; for (const b of G.bullets) { const h = hb.get(b.id); if (!h || h.ch !== b.ch) bbad++; }   // no bullet the host does not have, and the same kind of bullet
    const hp = S.players.map(p => p.pid + ':' + (p.worm && p.worm.alive ? p.worm.id : 0)).join(), cp = G.players.map(p => p.pid + ':' + p.wormId).join();
    return { miss, extra, wrong, wbad, why, bbad, worms: hw.map(w => w.id).sort((a, b) => a - b).join() === cw.join(), dup: new Set(cw).size !== cw.length,
      zones: S.zones.map(z => z.id).join() === G.zones.map(z => z.id).join(), players: hp === cp };
  }
  const TIMERS = ['abil', 'stuck', 'slow', 'trip', 'shield', 'rage', 'big', 'guard', 'sauce', 'chill', 'sgT'];
  let firstBad = null;
  const clean = d => { const ok = !d.miss && !d.extra && !d.wrong && !d.wbad && !d.bbad && d.worms && !d.dup && d.zones && d.players; if (!ok && !firstBad) firstBad = d; return ok; };
  const sane = X => X.sim.S.worms.every(w => fin(w.x) && fin(w.y) && fin(w.ang) && fin(w.aim) && fin(w.mass) && w.x >= 0 && w.x <= CFG.W && w.y >= 0 && w.y <= CFG.H)
    && X.sim.S.players.every(p => !p.inp || (['mx', 'my', 'ax', 'ay'].every(a => fin(p.inp[a]) && Math.abs(p.inp[a]) <= 1) && ['fire', 'boost', 'abil', 'auto', 'taunt'].every(a => typeof p.inp[a] === 'boolean' || (a === 'taunt' && p.inp[a] === undefined))));
  const maxMsg = X => Math.max(0, ...X.cl.map(k => k.conn.max));
  const input = (k, mx, my, ax, ay, f, a) => k.conn.recv({ t: 'i', m: [mx, my, ax, ay], f, a: a === undefined ? k.seq : a });
  const wormOf = (X, k) => { const p = X.sim.S.players.find(p => p.pid === k.pid); return p && p.worm && p.worm.alive ? p.worm : null; };
  const playerOf = (X, k) => X.sim.S.players.find(p => p.pid === k.pid);
  const rnd = (a, b) => a + Math.random() * (b - a);

  const T = { open: () => ({ OPEN, OPEN2 }) };
  // 30 s of busy play with 3 clients: everything every client holds must match the host after every snapshot
  T.churn = function () {
    const X = setup(3), S = X.sim.S; let bad = 0, snaps = 0, firstBad = null, kills = 0;
    for (let i = 0; i < 620; i++) {
      if (i % 7 === 0) for (const k of X.cl) { const a = rnd(0, 6.28); input(k, Math.cos(a), Math.sin(a), Math.cos(a * 3), Math.sin(a * 3), 1 | (i % 40 < 8 ? 2 : 0) | 8); }
      if (i % 45 === 20) { const l = S.worms.filter(w => w.alive); const w = l[(Math.random() * l.length) | 0]; w.mass = rnd(100, 900); X.sim.kill(w, null, 'shot'); kills++; }
      if (i % 60 === 30) for (const w of S.worms) { w.ammo = 99; if (w.abil > 1) w.abil = 0.5; }
      X.host.inp.fire = true; X.host.inp.mx = Math.cos(i / 30); X.host.inp.my = Math.sin(i / 30); if (!X.host.worm || !X.host.worm.alive) X.host.wantSpawn = true;
      if (!tick(X, i % 3 === 2 ? 4 : 3)) continue; snaps++;
      for (const k of X.cl) { const d = diff(X, k); if (!clean(d)) { bad++; if (!firstBad) firstBad = { i, d }; } }
    }
    const st = Net.stats;
    return { snaps, kills, bad, firstBad, sane: sane(X), maxMsg: maxMsg(X), over: st.over, first: X.cl.map(k => k.first), pids: X.cl.map(k => k.pid), events: X.cl.map(k => k.ev),
      perSnap: Math.round(st.snapB / st.snapN), kbps: +(st.out / 3 / (snaps / 20) / 1000).toFixed(2), oldPerSnap: Math.round(X.old.bytes / X.old.n), oldMax: X.old.max, oldKbps: +(X.old.bytes / (snaps / 20) / 1000).toFixed(2) };
  };
  // quiet play: clients move and shoot now and then, bots do their thing
  T.typical = function () {
    const X = setup(3); let snaps = 0, bad = 0;
    for (let i = 0; i < 1200; i++) {
      if (i % 5 === 0) X.cl.forEach((k, j) => { const a = i / 90 + j * 2; input(k, Math.cos(a), Math.sin(a), Math.cos(a * 2), Math.sin(a * 2), (i % 120 < 30 ? 1 : 0) | 8); });
      X.host.inp.mx = Math.cos(i / 70); X.host.inp.my = Math.sin(i / 70); X.host.inp.fire = i % 200 < 40; if (!X.host.worm || !X.host.worm.alive) X.host.wantSpawn = true;
      if (tick(X, i % 3 === 2 ? 4 : 3)) { snaps++; for (const k of X.cl) if (!clean(diff(X, k))) bad++; }
    }
    const st = Net.stats;
    return { snaps, bad, perSnap: Math.round(st.snapB / st.snapN), snapMax: st.snapMax, kbps: +(st.out / 3 / (snaps / 20) / 1000).toFixed(2), oldPerSnap: Math.round(X.old.bytes / X.old.n), oldMax: X.old.max, oldKbps: +(X.old.bytes / (snaps / 20) / 1000).toFixed(2),
      bullets: X.sim.S.bullets.length, items: X.sim.S.items.size };
  };
  // the worst we can build: 7-digit ids, 12 long worms, 200 bullets on top of the clients, hundreds of effects,
  // then every worm bursting in the same tick
  T.worst = function () {
    const X = setup(3), S = X.sim.S; let bad = 0; const out = {};
    for (let i = 0; i < 30; i++) tick(X);
    S.nextId = 5000000;
    for (let i = 0; i < 100; i++) X.sim.addFood(); // items with long ids
    const stuff = () => {
      // every countdown running with its longest reading, a special gun in every hand
      for (const w of S.worms) { w.mass = 3000; w.ammo = 150; w.kills = 99; w.shield = 99; w.abil = 59; w.stuck = 9; w.slow = 3; w.trip = 7; w.rage = 8.9; w.big = 11.9; w.guard = 9.9; w.sauce = 7.9; w.chill = 3.4; w.sg = 5; w.sgT = 13.9; }
      for (const k of X.cl) { const w = wormOf(X, k); if (!w) continue; for (let j = 0; j < 70; j++) S.bullets.push({ id: S.nextId++, ch: 5 + j % 5, owner: w.id, x: w.x + rnd(-300, 300), y: w.y + rnd(-300, 300), vx: -289.6, vy: -289.6, life: 5, age: 59.99, hit: null, pierce: 0, c: 4 }); }
      if (S.zones.length < 12) for (let j = 0; j < 12; j++) S.zones.push({ id: S.nextId++, k: j & 1, x: 1000 + j, y: CFG.H, r: 76, t: 9.9, owner: 5000000 }); // out of the spawn area
      for (const k of X.cl) {
        const w = wormOf(X, k) || { x: CFG.W / 2, y: CFG.H / 2, id: 0 };
        for (let j = 0; j < 150; j++) X.sim.ev(j % 3 ? 'hit' : 'die', w.x, w.y, 5000000 + j, 5000001, 'rampage', 4, 4, 3, 3, 3, 30000);
        for (let j = 0; j < 60; j++) X.sim.ev('streak', w.x, w.y, w.id, 7, 60, 3, 4);      // the longest of the new events, addressed to this client
      }
    };
    // (compared right after a snapshot, before the host's numbers are forced again: with meals worth up to 8 a worm's mass moves within a tick)
    stuff(); for (let i = 0; i < 4; i++) { tick(X); if (i === 3) for (const k of X.cl) if (!clean(diff(X, k))) bad++; stuff(); }
    out.busyMax = maxMsg(X); out.busyOld = X.old.max;
    // 6 huge worms burst at once. A dead worm now leaves a few big meals (40 at most), so the thousands of crumbs this
    // case is about are spilled next to each one: thousands of item adds in one tick (sent as chunks)
    let n = 0; for (const w of S.worms.slice()) if (w.alive && n++ < 6) { w.shield = 0; w.mass = 3000; X.sim.spill(w.x, w.y, 2500, 220); X.sim.kill(w, null, 'shot'); }
    out.adds6 = S.adds.length; tick(X); for (const k of X.cl) if (!clean(diff(X, k))) bad++;
    out.resyncBefore = Net.stats.resync;
    // all of them: more than the per-client queue holds -> full resync
    for (const w of S.worms.slice()) if (w.alive) { w.shield = 0; w.mass = 6000; X.sim.spill(w.x, w.y, 6000, 300); X.sim.kill(w, null, 'shot'); }
    out.addsAll = S.adds.length; out.oldAll = oldSize(S, []); tick(X); tick(X);
    for (const k of X.cl) if (!clean(diff(X, k))) bad++;
    for (let i = 0; i < 60; i++) { if (tick(X)) for (const k of X.cl) if (!clean(diff(X, k))) bad++; }
    out.bad = bad; out.maxMsg = maxMsg(X); out.over = Net.stats.over; out.resync = Net.stats.resync; out.items = S.items.size; out.zs = X.cl.map(k => k.zs); out.oldMax = X.old.max;
    return out;
  };
  // junk from a client must never reach the simulation
  T.fuzz = function () {
    const X = setup(1), k = X.cl[0], S = X.sim.S; let threw = 0; for (let i = 0; i < 5; i++) tick(X);
    const before = S.players.length, junk = [null, undefined, 5, 'str', true, [], [1, 2], {}, { t: 'i' }, { t: 'i', m: 'x' }, { t: 'i', m: {} }, { t: 'i', m: { length: 4 } }, { t: 'i', m: [] },
      { t: 'i', m: [Infinity, -Infinity, NaN, 1e308], f: 'zz', a: 1e308 }, { t: 'i', m: ['a', {}, [], null], f: {}, a: 'x' }, { t: 'i', m: [5, -5, 2, -2], f: -1, a: -5 }, { t: 'i', m: [0.5, 0.5, 0, 0], f: 1e99, a: 2.5 },
      { t: 'i', m: [0, 0, 0, 0], f: 8, a: null }, { t: 'hello', ch: 3, v: 4 }, { t: 'hello' }, { t: 'i', m: [0, 0, 0, 0], f: 16, a: 0 }, { t: 'i', m: [0, 0, 0, 0], f: 'x', a: 0 }, { t: 'k' }, { t: 'k', c: 'x' }, { t: 'k', c: 1e999 }, { t: 'zzz', m: [1] }, { t: 's', w: [[1, 2, 3]] }, { t: 'init', pid: 0 }, { t: 'it', z: 1, a: [] },
      { t: 'i', m: [1, 0, 0, 0], f: 3, a: 1, extra: 'x'.repeat(5000) }, { __proto__: null, t: 'i' }, { t: { toString() { return 'i'; } } }];
    for (const m of junk) { try { k.conn.recv(m); } catch (e) { threw++; } tick(X); if (!sane(X)) return { failedOn: JSON.stringify(m) }; }
    const p = playerOf(X, k), out = { threw, players: S.players.length === before, sane: sane(X), stillIn: !!p, seq: k.c.seq, sync: clean(diff(X, k)) };
    // character index is clamped
    const a = join(X, 99), b = join(X, -7); tick(X); out.ch = [playerOf(X, a).ch, playerOf(X, b).ch];
    return out;
  };
  T.gate = function () {
    const X = setup(3), S = X.sim.S, out = {}; tick(X);
    const k5 = join(X, 1); tick(X); out.fullMsg = k5.conn.out.concat(k5.other.map(m => JSON.stringify(m))).join(); out.playersAfterFifth = S.players.length;
    X.cl[1].conn.close(); out.afterLeave = S.players.length; const freed = X.cl[1].pid;
    const k6 = join(X, 4); tick(X); out.rejoin = { players: S.players.length, pid: k6.pid, freed, first: k6.first, sync: clean(diff(X, k6)) };
    X.cl[0].conn.recv({ t: 'bye' }); out.afterBye = S.players.length; out.byeClosed = !X.cl[0].conn.open;
    const old = join(X, 1, { t: 'hello', ch: 1 }); out.oldVersion = old.conn.out.join(); out.afterOld = S.players.length;
    const bin = mkConn('binary'); out.binary = X.accept(bin) === null && !bin.open;
    const quiet = []; for (let i = 0; i < 10; i++) { const c = mkConn(); X.accept(c); quiet.push(c); }
    out.lobbyCap = quiet.filter(c => c.open).length;
    for (let i = 0; i < 230; i++) tick(X); out.quietDropped = quiet.filter(c => c.open).length; out.playersEnd = S.players.length;
    return out;
  };
  // two players arriving between the same two snapshots, during a food burst
  T.sameTick = function () {
    const X = setup(0), S = X.sim.S; for (let i = 0; i < 10; i++) tick(X);
    const w = S.worms.find(w => w.alive && w.isBot); w.mass = 900; X.sim.kill(w, null, 'shot');
    const a = join(X, 1), b = join(X, 2), out = {}; tick(X);
    out.pids = [a.pid, b.pid]; out.first = [a.first, b.first]; out.sync0 = clean(diff(X, a)) && clean(diff(X, b));
    let bad = 0; for (let i = 0; i < 100; i++) { if (i === 3) { const q = S.worms.find(w => w.alive && w.isBot); q.mass = 700; X.sim.kill(q, null, 'shot'); } if (tick(X)) { if (!clean(diff(X, a))) bad++; if (!clean(diff(X, b))) bad++; } }
    out.bad = bad; out.worms = [a.G.worms.length, b.G.worms.length, S.worms.filter(w => w.alive).length]; out.bodies = a.G.worms.every(w => w.pts.length === HW.segCount(w.mass));
    return out;
  };
  // a client whose link stalls: nothing piles up, and it is exact again afterwards (first by catching up, then by a full resync)
  T.slow = function () {
    const X = setup(2), S = X.sim.S, k = X.cl[0], out = {}; for (let i = 0; i < 10; i++) tick(X);
    k.conn.dataChannel.bufferedAmount = 1e6; const n0 = k.conn.n;
    for (let i = 0; i < 60; i++) { if (i % 20 === 5) { const w = S.worms.find(w => w.alive && w.isBot); w.mass = 600; X.sim.kill(w, null, 'shot'); } tick(X); }
    out.sentWhileStalled = k.conn.n - n0; out.skips = Net.stats.skip; out.queued = k.c.qa.length + k.c.qr.length; out.otherOk = clean(diff(X, X.cl[1]));
    k.conn.dataChannel.bufferedAmount = 0; tick(X); out.caughtUp = clean(diff(X, k)); out.resync0 = Net.stats.resync;
    k.conn.dataChannel.bufferedAmount = 1e6;
    for (let r = 0; r < 3; r++) { for (const w of S.worms.slice()) if (w.alive && w.isBot) { w.shield = 0; w.mass = 3000; X.sim.spill(w.x, w.y, 1200, 200); X.sim.kill(w, null, 'shot'); } tick(X); for (let i = 0; i < 30; i++) tick(X); }
    out.queuedCapped = k.c.qa.length + k.c.qr.length; out.resync1 = Net.stats.resync;
    k.conn.dataChannel.bufferedAmount = 0; const z0 = k.zs, f0 = k.first; tick(X);
    out.resynced = k.zs === z0 + 1 && k.first === f0 + 1; out.exact = clean(diff(X, k)); out.maxMsg = maxMsg(X);
    let bad = 0; for (let i = 0; i < 40; i++) if (tick(X) && !clean(diff(X, k))) bad++; out.bad = bad;
    return out;
  };
  // ability counter, respawn flag, a client that goes quiet, a client that disappears, a host that was asleep
  T.flags = function () {
    const X = setup(2), S = X.sim.S, k = X.cl[0], out = {}; for (let i = 0; i < 5; i++) tick(X);
    const zonesOf = w => S.zones.filter(z => z.owner === w.id).length;
    let w = wormOf(X, k); w.abil = 0; w.shield = 99; input(k, 1, 0, 0, 0, 0, 1); tick(X); out.abilUsed = zonesOf(w) === 1;
    w.abil = 0; input(k, 1, 0, 0, 0, 0, 1); tick(X); out.repeatIgnored = zonesOf(w) === 1;
    input(k, 1, 0, 0, 0, 8, 1); tick(X); out.spawnFlagAliveIgnored = playerOf(X, k).wantSpawn === false;
    w.shield = 0; X.sim.kill(w, null, 'shot'); tick(X); out.deadOnClient = k.G.players.find(p => p.pid === k.pid).wormId === 0;
    input(k, 1, 0, 0, 0, 0, 2); tick(X); out.inpAbilWhileDead = playerOf(X, k).inp.abil;       // pressed while dead
    for (let i = 0; i < 10; i++) tick(X); out.noEarlySpawn = !wormOf(X, k);
    input(k, 1, 0, 0, 0, 8, 2); tick(X); tick(X); out.spawnTooEarly = !wormOf(X, k); for (let i = 0; i < 20; i++) { input(k, 1, 0, 0, 0, 8, 2); tick(X); }
    w = wormOf(X, k); out.respawned = !!w; if (w) { w.abil = 0; tick(X); tick(X); out.deadPressNotSaved = zonesOf(w) === 0; input(k, 1, 0, 0, 0, 0, 3); tick(X); out.nextPressWorks = zonesOf(w) === 1; }
    out.mirrorSeesWorm = !!k.G.wmap.get(k.G.players.find(p => p.pid === k.pid).wormId);
    // goes quiet while holding fire: neutral after 1.5 s, still in the room (keep-alives), gone after 30 s of nothing
    input(k, 0, 1, 1, 0, 3, 3); tick(X); const I = playerOf(X, k).inp; out.held = I.fire && I.boost;
    for (let i = 0; i < 50; i++) { if (i % 10 === 0) k.conn.recv({ t: 'k', c: 1 }); tick(X); } out.neutralised = !I.fire && !I.boost && I.mx === 0 && I.my === 0;
    out.pong = k.other.some(m => m.t === 'k'); out.stillIn = !!playerOf(X, k);
    for (let i = 0; i < 300; i++) { if (i % 10 === 0) k.conn.recv({ t: 'k', c: 1 }); X.cl[1].conn.recv({ t: 'k', c: 1 }); tick(X); } out.keptAliveByPings = !!playerOf(X, k);
    for (let i = 0; i < 640; i++) { X.cl[1].conn.recv({ t: 'k', c: 1 }); tick(X); } out.timedOut = !playerOf(X, k); out.kickMsg = k.other.filter(m => m.t === 'x').map(m => m.r).join(); out.otherStays = !!playerOf(X, X.cl[1]);
    // the host itself freezes for a minute (phone locked): nobody is thrown out for it
    vt += 60; tick(X); tick(X); for (let i = 0; i < 25; i++) { X.cl[1].conn.recv({ t: 'k', c: 1 }); tick(X); } out.hostSleepKeepsClients = !!playerOf(X, X.cl[1]);
    out.sync = clean(diff(X, X.cl[1]));
    return out;
  };
  // a sim replaced under a live connection (host quit and started again) must not be touched by the old room's clients
  T.stale = function () {
    const X = setup(1), k = X.cl[0]; for (let i = 0; i < 5; i++) tick(X);
    const sim2 = new HW.Sim(); sim2.S.events = []; const n = sim2.S.items.size, ev0 = sim2.S.events.length;
    X.accept = Net._loop(() => sim2);            // Net.close() + a new room
    k.conn.recv({ t: 'i', m: [1, 0, 0, 0], f: 1, a: 5 }); k.conn.close();
    return { items: sim2.S.items.size === n, events: sim2.S.events.length === ev0, players: sim2.S.players.length, gotBye: k.conn.out.some(s => s.indexOf('"bye"') >= 0), conns: Net.conns.length };
  };
  // Interpolation: a worm circling at constant speed, snapshots delayed by a jittery link. Reports how even the
  // displayed speed is (cv = stddev / mean of per-frame movement) and how far the picture is from the truth.
  T.smooth = function (jit, spikeEvery, hostHz, seed) {
    let s = seed || 7; const rand = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const X = setup(1), k = X.cl[0], S = X.sim.S; for (let i = 0; i < 4; i++) tick(X);
    const W = wormOf(X, k); const queue = []; let lastDue = 0, frames = [], truth = [], n = 0, sent = 0; place(W, OPEN.x + 60, OPEN.y, Math.PI / 2, 60);
    const old = { x: W.x, y: W.y, sx: W.x, sy: W.y, tx: W.x, ty: W.y, lt: 0 }, oframes = []; // the previous interpolation, fed the same snapshots
    const step = 1 / (hostHz || 60), FR = 1 / 60; let hostAcc = 0, cx = OPEN.x, cy = OPEN.y;
    k.conn.out.length = 0;
    for (let f = 0; f < 60 * 14; f++) {
      vt += FR;
      // host: fixed 60 Hz sim, frames at hostHz
      hostAcc += FR;
      while (hostAcc >= step - 1e-9) {
        hostAcc -= step; const steps = Math.round(step * 60);
        W.shield = 99; W.slow = 0; W.stuck = 0; W.trip = 0; W.mass = 60;
        const a = Math.atan2(W.y - cy, W.x - cx) + 1.75; input(k, Math.cos(a), Math.sin(a), 0, 0, 0);
        for (let i = 0; i < steps; i++) X.sim.step(1 / 60);
        truth.push({ t: vt, x: W.x, y: W.y });
        const evs = S.events; S.events = [];
        if (Net.hostTick(X.sim, step, evs)) { S.adds.length = 0; S.rems.length = 0; sent++; const spike = spikeEvery && sent % spikeEvery === 0 ? 0.15 : 0; for (const m of k.conn.out) { const due = Math.max(lastDue, vt + 0.03 + rand() * jit + spike); lastDue = due; queue.push({ due, m }); } k.conn.out.length = 0; }
      }
      // client frame
      while (queue.length && queue[0].due <= vt) {
        const m = JSON.parse(queue.shift().m); if (m.t === 'it' || m.t === 'pt') Net.applyPart(k.G, m); if (m.t !== 's') continue;
        Net.applySnap(k.G, m);
        const r = m.w.find(r => Array.isArray(r) && r[0] === W.id); if (r) { const o = r.length >= 17 ? 3 : 1; old.sx = old.x; old.sy = old.y; old.tx = Math.round(r[o]); old.ty = Math.round(r[o + 1]); old.lt = 0; }
      }
      Net.clientUpdate(k.G, FR);
      old.lt += FR; const ok = Math.min(1.6, old.lt / 0.05); old.x = old.sx + (old.tx - old.sx) * ok; old.y = old.sy + (old.ty - old.sy) * ok;
      const me = k.G.wmap.get(W.id); if (me && f > 240) { frames.push({ t: vt, x: me.x, y: me.y }); oframes.push({ t: vt, x: old.x, y: old.y }); }
    }
    const stats = frames => {
      const sp = []; let back = 0, maxStep = 0;
      for (let i = 1; i < frames.length; i++) { const dx = frames[i].x - frames[i - 1].x, dy = frames[i].y - frames[i - 1].y, d = Math.hypot(dx, dy); sp.push(d); if (d > maxStep) maxStep = d;
        if (i > 1) { const px = frames[i - 1].x - frames[i - 2].x, py = frames[i - 1].y - frames[i - 2].y; if (dx * px + dy * py < -0.01) back++; } }
      const mean = sp.reduce((a, b) => a + b, 0) / sp.length, sd = Math.sqrt(sp.reduce((a, b) => a + (b - mean) * (b - mean), 0) / sp.length);
      // lag: how old is the picture? find the truth sample nearest to each displayed position
      let lag = 0, ln = 0, err = 0; for (let i = 0; i < frames.length; i += 7) { const fr = frames[i]; let best = 1e9, bt = 0; for (const q of truth) { if (q.t > fr.t || q.t < fr.t - 0.6) continue; const d = Math.hypot(q.x - fr.x, q.y - fr.y); if (d < best) { best = d; bt = q.t; } } lag += fr.t - bt; err += best; ln++; }
      return { cv: +(sd / mean).toFixed(3), maxStep: +maxStep.toFixed(2), back, lagMs: Math.round(lag / ln * 1000), offPath: +(err / ln).toFixed(2), stops: sp.filter(d => d < mean * 0.25).length, mean: +mean.toFixed(3) };
    };
    const r = stats(frames); r.frames = frames.length; r.delayMs = Math.round(k.G.delay * 1000); r.old = stats(oframes); return r;
  };
  // bullets: a client's copy must fly straight (no back-and-forth) and end where the host's does
  T.bullets = function (jit) {
    let s = 11; const rand = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const X = setup(1), k = X.cl[0], S = X.sim.S; for (let i = 0; i < 4; i++) tick(X);
    const W = wormOf(X, k), queue = []; let lastDue = 0, back = 0, n = 0, maxCross = 0; const prev = new Map(), lags = []; place(W, OPEN.x, OPEN.y - 92, 0, 60);   // on the circle it is about to steer, round the middle of the open area
    k.conn.out.length = 0;
    for (let f = 0; f < 60 * 10; f++) {
      vt += 1 / 60; W.shield = 99; W.ammo = 99; W.mass = 60; W.slow = 0; W.stuck = 0; input(k, Math.cos(f / 50), Math.sin(f / 50), Math.cos(f / 50), Math.sin(f / 50), 1);
      X.sim.step(1 / 60); const evs = S.events; S.events = [];
      if (Net.hostTick(X.sim, 1 / 60, evs)) { S.adds.length = 0; S.rems.length = 0; for (const m of k.conn.out) { const due = Math.max(lastDue, vt + 0.03 + rand() * jit); lastDue = due; queue.push({ due, m }); } k.conn.out.length = 0; }
      while (queue.length && queue[0].due <= vt) { const m = JSON.parse(queue.shift().m); if (m.t === 's') Net.applySnap(k.G, m); else if (m.t === 'it' || m.t === 'pt') Net.applyPart(k.G, m); }
      Net.clientUpdate(k.G, 1 / 60);
      if (f > 240) for (const b of k.G.bullets) { const p = prev.get(b.id); if (p) { n++; if ((b.x - p.x) * b.vx + (b.y - p.y) * b.vy < 0) back++; } prev.set(b.id, { x: b.x, y: b.y });
        const h = S.bullets.find(q => q.id === b.id); if (h && !b.stop) { const v = Math.hypot(h.vx, h.vy), al = ((h.x - b.x) * h.vx + (h.y - b.y) * h.vy) / v, cr = Math.abs((h.x - b.x) * h.vy - (h.y - b.y) * h.vx) / v; lags.push(al / v * 1000); if (cr > maxCross) maxCross = cr; } }
    }
    const mean = lags.reduce((a, b) => a + b, 0) / lags.length, sd = Math.sqrt(lags.reduce((a, b) => a + (b - mean) * (b - mean), 0) / lags.length);
    return { samples: n, back, lagMs: +mean.toFixed(1), lagSd: +sd.toFixed(1), lagMin: +Math.min(...lags).toFixed(1), lagMax: +Math.max(...lags).toFixed(1), maxCross: +maxCross.toFixed(2) };
  };
  // ---------- the state added with power-ups, special guns, frenzy, awards and taunts ----------
  // Three clients: `a` owns the worm things happen to, `n` sits next to it, `f` is at the far end of the arena.
  T.fresh = function () {
    const X = setup(3), S = X.sim.S, [a, n, f] = X.cl, out = {}; for (const k of X.cl) k.evs = [];
    for (let i = 0; i < 6; i++) tick(X);
    S.respawns.length = 0; for (const it of Array.from(S.items.values())) if (it.k !== 'f') X.sim.remItem(it);   // only what the test puts there
    const wa = wormOf(X, a), wn = wormOf(X, n), wf = wormOf(X, f); let bad = 0;
    place(wa, OPEN.x, OPEN.y, 0); place(wn, OPEN.x + 110, OPEN.y + 60, 0); place(wf, OPEN2.x, OPEN2.y, 0);
    // glued to the spot (stuck) and safe from the bots (shield), so the three stay where they were put
    const keep = () => { S.respawns.length = 0; for (const w of [wa, wn, wf]) if (w.alive) { w.shield = 99; w.stuck = 99; } };
    const run = c => { for (let i = 0; i < c; i++) { keep(); if (tick(X)) for (const k of X.cl) if (!clean(diff(X, k))) bad++; } };
    const mark = () => { for (const k of X.cl) k.evs.length = 0; }, M = (k, w) => k.G.wmap.get(w.id);
    const got = (k, kind, id, v) => k.evs.filter(e => e[0] === kind && (id === undefined || e[3] === id) && (v === undefined || e[4] === v)).length;
    const who = (kind, id, v) => [a, n, f].map(k => got(k, kind, id, v));   // [1, 1, 0] = owner and neighbour got it once, the far client did not
    const r2 = v => +(+v).toFixed(2);
    run(4);
    // --- power-ups: the countdown reaches every mirror, the pick-up event reaches the owner and whoever is near ---
    out.power = [];
    ['rage', 'big', 'guard', 'sauce'].forEach((key, ty) => {
      mark(); X.sim.addItem('p', ty, wa.x + 2, wa.y, 0); run(3);
      const e = a.evs.find(e => e[0] === 'power') || [];
      out.power.push({ key, host: r2(wa[key]), a: r2(M(a, wa)[key]), far: r2(M(f, wa)[key]), who: who('power', wa.id, ty), pid: e[5] === a.pid });
    });
    out.bigR = [wa.r, M(a, wa).r, M(f, wa).r, HW.wormR(wa.ch, wa.mass, false)];
    run(40);   // two seconds later the mirrors' own countdowns still agree with the host
    out.powerLater = ['rage', 'big', 'guard', 'sauce'].map(key => [r2(wa[key]), r2(M(a, wa)[key]), r2(M(f, wa)[key])]);
    mark(); wa.rage = 0.03; wa.big = 0.03; run(3);
    out.powerOff = { who0: who('poweroff', wa.id, 0), who1: who('poweroff', wa.id, 1), a: [r2(Math.max(0, M(a, wa).rage)), r2(Math.max(0, M(a, wa).big))], r: [wa.r, M(a, wa).r] };
    // --- special guns: sg / sgT, the sprite render.js draws, and bullets of that gun's kind with a running age ---
    out.guns = [];
    for (let ty = 0; ty < HW.SGUNS.length; ty++) {
      // bots come for a gun pickup now and would stand in the line of fire: park them (shots pass a shielded worm) and disarm them
      for (const o of S.worms) if (o !== wa) { o.shield = 99; if (o.isBot) { o.stuck = 99; o.sg = 0; o.inp.fire = false; } }   // (the host's own worm drifts about too)
      mark(); X.sim.addItem('g', ty, wa.x + 2, wa.y, 0); run(2);
      const ma = M(a, wa), g = { ty, sg: [wa.sg, ma.sg, M(f, wa).sg], sgT: [r2(wa.sgT), r2(ma.sgT), r2(M(f, wa).sgT)], spr: HW.gunSprOf(ma) === HW.sgunSpr[ty], who: who('gun', wa.id, ty), kinds: [], n: 0, ageErr: 0, vErr: 0, ages: [], far: 0, nearN: 0, v0: 0, v1: 0 };
      input(a, 0, 0, 0, -1, 1);   // aim up, fire
      for (let i = 0; i < 8; i++) {
        run(1);
        for (const b of a.G.bullets) {
          const h = S.bullets.find(q => q.id === b.id); if (!h || h.owner !== wa.id) continue;
          g.n++; if (g.kinds.indexOf(b.ch) < 0) g.kinds.push(b.ch); g.ages.push(r2(b.age)); if (!b.stop) { g.v1 = Math.round(Math.hypot(b.vx, b.vy)); if (!g.v0) g.v0 = g.v1; }
          if (!b.stop) { g.ageErr = Math.max(g.ageErr, Math.abs(b.age - h.age)); g.vErr = Math.max(g.vErr, Math.abs(Math.hypot(b.vx, b.vy) - Math.hypot(h.vx, h.vy))); }
        }
        g.far += f.G.bullets.filter(b => b.ch >= 5).length; g.nearN += n.G.bullets.filter(b => b.ch === 5 + ty).length;
      }
      g.ageErr = r2(g.ageErr); g.vErr = r2(g.vErr); g.ageMax = Math.max(0, ...g.ages); delete g.ages;
      g.shot = who('shot', 5 + ty);
      input(a, 0, 0, 0, 0, 0); run(34); out.guns.push(g);
    }
    mark(); wa.sgT = 0.03; run(3); out.gunOff = { who: who('gunoff', wa.id), sg: [wa.sg, M(a, wa).sg, M(f, wa).sg], spr: HW.gunSprOf(M(a, wa)) === HW.gunSpr[wa.ch] };
    // --- golden burger and the three new item kinds ---
    const m0 = M(a, wa).mass; mark(); X.sim.addItem('x', 0, wa.x + 2, wa.y, HW.GOLD.v); run(3);
    out.gold = { who: who('gold', wa.id, HW.GOLD.v), pid: (a.evs.find(e => e[0] === 'gold') || [])[5] === a.pid, grew: r2(M(a, wa).mass - m0) };
    const its = [X.sim.dropItem('p'), X.sim.dropItem('g'), X.sim.dropItem('x'), X.sim.addItem('p', 3, wf.x + 200, wf.y, 0), X.sim.addItem('g', 4, wf.x + 200, wf.y + 60, 0)]; run(2);
    out.items = X.cl.map(k => its.map(it => { const o = k.G.items.get(it.id); return o ? o.k + o.type + ':' + o.v : '-'; }).join(' '));
    out.itemsHost = its.map(it => it.k + it.type + ':' + it.v).join(' ');
    for (const it of its) X.sim.remItem(it); run(2); out.itemsGone = X.cl.every(k => its.every(it => !k.G.items.has(it.id)));
    { const G = Net.newMirror(); Net.applyPart(G, { t: 'it', a: [[1, 'p', 99, 5, 5, 0], [2, 'g', -3, 5, 5, 0], [3, 'x', 7, 5, 5, 30], [4, 'q', 0, 5, 5, 0], [5, 'constructor', 0, 5, 5, 0], [6, 'toString', 0, 5, 5, 0]] }); out.junkItems = Array.from(G.items.values()).map(i => i.k + i.type).join(' '); }
    // --- who gets which event. Made by hand so every kind is covered whatever the bots are doing ---
    mark(); const E = X.sim.ev.bind(X.sim);
    E('ping', wa.x, wa.y, wa.id); E('chill', wa.x, wa.y, wa.id); E('streak', wa.x, wa.y, wa.id, 3, 20, a.pid, wa.ch); E('bounty', wa.x, wa.y, wa.id, 40); E('hit', wa.x, wa.y, wa.id, 3); E('bump', wa.x, wa.y, wa.id, 50);
    E('poweroff', wa.x, wa.y, wa.id, 2); E('gunoff', wa.x, wa.y, wa.id); E('dry', wa.x, wa.y, wa.id); E('eat', wa.x, wa.y, wa.id, 3);
    E('clang', wa.x + 30, wa.y, 'T'); E('drop', wa.x + 40, wa.y, 'x', 0);
    // e[3] of these is a gun kind / radius, not a worm: made equal to the far client's worm id, they must still not go to it
    E('boom', wa.x, wa.y, wf.id); E('shot', wa.x, wa.y, wf.id, wa.id); E('puff', wa.x, wa.y, wf.id);
    E('drop', wf.x + 30, wf.y, 'g', 2);   // next to the far client only
    run(1);
    out.route = {}; for (const kd of ['ping', 'chill', 'streak', 'bounty', 'hit', 'bump', 'poweroff', 'gunoff', 'dry', 'eat']) out.route[kd] = who(kd, wa.id);
    for (const kd of ['boom', 'shot', 'puff']) out.route[kd] = who(kd, wf.id); out.route.clang = who('clang', 'T'); out.route.dropNearA = who('drop', 'x'); out.route.dropNearF = who('drop', 'g');
    // the cap: a lot going on near `a`, and the things that matter to it come last in the host's buffer
    mark(); for (let i = 0; i < 100; i++) E('puff', wa.x, wa.y, 2); for (let i = 0; i < 30; i++) E('die', 5, 5, 9000000 + i, 0, 'shot', 1, -1, -1, -1, 0, 50);
    E('power', wa.x, wa.y, wa.id, 1, a.pid); E('gold', wa.x, wa.y, wa.id, 30, a.pid); E('frenzy', 0, 0); run(1);
    out.cap = { n: a.evs.length, die: a.evs.filter(e => e[0] === 'die' && e[3] >= 9000000).length, power: got(a, 'power'), gold: got(a, 'gold'), frenzy: got(a, 'frenzy'), puff: got(a, 'puff', 2), farDie: f.evs.filter(e => e[0] === 'die' && e[3] >= 9000000).length, farFrenzy: got(f, 'frenzy'), farN: f.evs.length };
    // --- frenzy: the flag and its one event reach everybody, wherever they are ---
    mark(); S.match.t = HW.FRENZY.t + 0.2; run(8);
    out.frenzy = { host: S.match.frenzy, mirrors: X.cl.map(k => k.G.match.frenzy), events: who('frenzy') };
    // --- taunt: one press = one taunt, however often the message is repeated ---
    wa.tauntT = 0; const t0 = wa.comp.st.taunt; mark(); input(a, 0, 0, 0, 0, 16); run(2);
    const te = a.evs.find(e => e[0] === 'taunt') || [];
    out.taunt = { first: wa.comp.st.taunt - t0, who: who('taunt', wa.id), text: typeof HW.TAUNTS[te[4]] === 'string' };
    for (let i = 0; i < 70; i++) { if (i % 4 === 0) input(a, 0, 0, 0, 0, 16); run(1); } out.taunt.repeats = wa.comp.st.taunt - t0;   // 3.5 s of repeats, far past the 2.5 s cooldown
    input(a, 0, 0, 0, 0, 0); run(2); out.taunt.second = wa.comp.st.taunt - t0;
    // the same through Net.sendInput: a press held for several frames, a press while the channel is choked
    const sent = [], ch = { open: true, dataChannel: { bufferedAmount: 0 }, send: m => sent.push(JSON.parse(JSON.stringify(m))) }; Net.conn = ch; Net.tnt = 0; Net.tnWas = false; Net.inKey = ''; Net.inT = 0;
    const o = { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, auto: false, taunt: false }, fr = () => { vt += 1 / 60; Net.sendInput(o, 0, false); };
    for (let i = 0; i < 30; i++) fr(); const n0 = sent.length;
    o.taunt = true; fr(); const atOnce = sent.length === n0 + 1 && (sent[n0].f & 16) === 16; fr(); fr(); o.taunt = false; for (let i = 0; i < 30; i++) fr();
    const held = sent.slice(n0).every(m => (m.f & 16) === 16);
    ch.dataChannel.bufferedAmount = 50000; const n1 = sent.length; o.taunt = true; fr(); o.taunt = false; for (let i = 0; i < 20; i++) fr(); const choked = sent.length === n1;
    ch.dataChannel.bufferedAmount = 0; for (let i = 0; i < 20; i++) fr(); const after = sent.length > n1 && sent.slice(n1).every(m => (m.f & 16) === 0);
    Net.conn = null;
    // played back to the host (which has seen the bit at 0 last): exactly two taunts, with the cooldown out of the way
    const t1 = wa.comp.st.taunt; let flips = 0, prev = 0; for (const m of sent) { if ((m.f & 16) !== prev) { prev = m.f & 16; flips++; } wa.tauntT = 0; a.conn.recv(m); keep(); X.sim.step(1 / 60); }
    out.sendInput = { atOnce, held, choked, after, flips, taunts: wa.comp.st.taunt - t1, msgs: sent.length };
    run(2);
    // pressed while dead: not saved for the next life
    const wd = wormOf(X, n); wd.shield = 0; X.sim.kill(wd, null, 'shot'); tick(X); input(n, 0, 0, 0, 0, 16); tick(X); out.tauntDead = playerOf(X, n).inp.taunt;
    // out of lives: that client watches the biggest worm, so the host sends it what happens there (bullets, effects)
    { const pn = playerOf(X, n); pn.comp.lives = 0; pn.comp.out = true; pn.deadT = 2; pn.wantSpawn = false; tick(X); tick(X);
      let top = null; for (const w of S.worms) if (w.alive && (!top || w.mass > top.mass)) top = w;
      out.spectate = Math.round(Math.hypot(n.c.ix - top.x, n.c.iy - top.y)); pn.comp.lives = 3; pn.comp.out = false; }
    // --- awards: on the results screen of every client, cleared for the next match ---
    wa.comp.st.veg = 5; wa.comp.st.shots = 20; wa.comp.st.hits = 17; wf.comp.st.taunt = 9; wf.comp.st.boost = 31.4;
    const max0 = maxMsg(X); X.sim.endMatch('time'); tick(X); tick(X);
    out.awards = { host: S.match.awards, same: X.cl.map(k => k.G.match.over && JSON.stringify(k.G.match.awards) === JSON.stringify(S.match.awards)), cids: S.match.awards.every(w => a.G.comps.some(c => c.cid === w[0])), row: JSON.stringify(S.match.awards).length };
    X.sim.restart(); for (let i = 0; i < 30; i++) tick(X);
    out.next = X.cl.map(k => !k.G.match.over && k.G.match.awards.length === 0 && !k.G.match.frenzy && k.G.match.n === S.match.n);
    out.bad = bad; out.maxMsg = maxMsg(X); out.over = Net.stats.over; out.sane = sane(X);
    return out;
  };

  // ---------- prediction of the client's own worm ----------
  // One client on a link with latency. Up and down are delayed separately (half the round trip each, plus jitter, kept
  // in order like the real channel), pings travel through the same link and inputs go through the real Net.sendInput.
  // A second mirror (G2) is fed the same snapshots but never told which worm is ours: it is the picture without
  // prediction, and the proof that nothing except our own head is touched.
  const PC = Net.PRED;
  const SCEN = {
    // chase a point that wanders round the open area: constant, smooth steering
    weave: { input(t, I, me) { if (!me) return; const tx = OPEN.x + 150 * Math.cos(0.5 * t), ty = OPEN.y + 150 * Math.sin(0.9 * t), dx = tx - me.x, dy = ty - me.y; if (dx * dx + dy * dy > 900) { const d = Math.hypot(dx, dy); I.mx = dx / d; I.my = dy / d; } } },
    // a 90 degree flick of the stick every 1.5 s
    turns: { flick: 1.5, input(t, I) { const a = Math.floor(t / 1.5 + 1e-6) * Math.PI / 2; I.mx = Math.cos(a); I.my = Math.sin(a); } },
    // steer, then let go of the stick
    stop: { stopAt: 6, input(t, I, me) { if (t < 6) SCEN.weave.input(t, I, me); else { I.mx = 0; I.my = 0; } } },
    circle: { input(t, I) { I.mx = Math.cos(t * 1.2); I.my = Math.sin(t * 1.2); } }
  };
  const circ = (extra) => Object.assign({ input: SCEN.circle.input, fxAt: 5 }, extra);
  // things the client only hears about afterwards (applied on the host at 5 s)
  SCEN.slow = circ({ host(t, W) { if (t >= 5 && !this.done) { this.done = 1; W.slow = CFG.SLOW_T; } } });
  SCEN.stuck = circ({ fxEnd: 7.5, host(t, W) { if (t >= 5 && !this.done) { this.done = 1; W.stuck = 2.5; } } });
  SCEN.chill = circ({ fxEnd: 8.5, host(t, W) { if (t >= 5 && !this.done) { this.done = 1; W.chill = 3.5; } } });
  SCEN.rampage = circ({ fxEnd: 9, mult: 1.4, host(t, W) { if (t >= 5 && !this.done) { this.done = 1; W.rage = 4; } } });
  SCEN.trip = circ({ fxEnd: 10, host(t, W) { if (t >= 5 && !this.done) { this.done = 1; W.trip = 5; } } });
  SCEN.boost = { fxAt: 5, fxEnd: 7, mult: CFG.BOOST_MULT, input(t, I) { SCEN.circle.input(t, I); I.boost = t >= 5 && t < 7; } };
  // boost that the host cuts short because the mass runs out (the client's idea of its mass is old)
  SCEN.boostDry = { fxAt: 5, fxEnd: 8, mult: CFG.BOOST_MULT, keepMass: true, host(t, W) { if (t < 5) W.mass = 60; else if (!this.done) { this.done = 1; W.mass = 15; } }, input(t, I) { SCEN.circle.input(t, I); I.boost = t >= 5 && t < 8; } };
  SCEN.sauce = { fxAt: 5, fxEnd: 8, mult: CFG.BOOST_MULT * HW.POWERS[3].boost, host(t, W) { if (t >= 5 && !this.done) { this.done = 1; W.sauce = 3; } }, input(t, I) { SCEN.circle.input(t, I); I.boost = t >= 4.5 && t < 8.5; } };
  // into the arena wall at an angle, along it, away again
  SCEN.wall = { start: () => { const q = SPOTS.filter(q => q.x === 200).sort((a, b) => b.d - a.d)[0]; return { x: 120, y: q.y, ang: Math.PI }; }, input(t, I) { if (t < 6) { I.mx = -1; I.my = 0.6; } else { I.mx = 1; I.my = 0.3; } } };
  // into a counter at an angle, along it and off its end; then square into a round table
  SCEN.counter = { start: () => ({ x: 380, y: 610, ang: Math.PI / 2 }), input(t, I) { I.mx = 0.35; I.my = 1; } };
  SCEN.table = { start: () => ({ x: 700, y: 688, ang: Math.PI / 4 }), input(t, I) { I.mx = 1; I.my = 1; } };
  // dying and coming back; being moved by the host; a tab that was hidden; a host that froze; snapshots that never came
  SCEN.respawn = { input: SCEN.weave.input, host(t, W, X) { if (t >= 4 && !this.done) { this.done = 1; W.shield = 0; X.sim.kill(W, null, 'shot'); } } };
  SCEN.teleport = { input: SCEN.circle.input, fxAt: 5, host(t, W) { if (t >= 5 && !this.done) { this.done = 1; place(W, OPEN2.x, OPEN2.y, 1, 60); } } };
  SCEN.hidden = { input: SCEN.circle.input, fxAt: 5, fxEnd: 7, hidden: [5, 2] };
  SCEN.freeze = { input: SCEN.circle.input, fxAt: 5, fxEnd: 6.5, hostFreeze: [5, 1.5] };
  SCEN.drop = { input: SCEN.weave.input, drop: [[4, 0.35], [6, 0.35], [8, 0.35]] };
  SCEN.spikes = { input: SCEN.weave.input, spike: 25 };
  // Square into the side of a worm that is not moving, kept there for a second and a half, then steered away.
  // The other worm is the host's own (so the test can drive it): it runs along a line first, so that its body lies
  // on every device the way it does on the host, and is then frozen. Bots are disarmed and cannot touch anybody.
  SCEN.bump = {
    noShield: true, bumpAt: 4.6, leaveAt: 6.5,
    setup(X) { const B = X.host.worm; place(B, OPEN.x - 200, OPEN.y, 0, 60); return { x: OPEN.x, y: OPEN.y - 160, ang: Math.PI / 2 }; },
    host(t, W, X) {
      const B = X.host.worm; this.B = B;
      for (const w of X.sim.S.worms) { w.ammo = 0; w.sg = 0; if (w.abil < 30) w.abil = 60; if (w !== W && w !== B) w.shield = 99; }
      B.mass = 60; if (t < 3) { B.shield = 99; X.host.inp.mx = 1; X.host.inp.my = 0; } else { B.shield = 0; B.stuck = 99; X.host.inp.mx = 0; }
      W.shield = 0; if (!this.go) { this.go = 1; W.stuck = 3.5; } W.crash = Math.min(W.crash, 0.15);   // the count that would kill it is held down: this is about where the head is drawn
    },
    input(t, I) { if (t < 6.5) { I.mx = 0; I.my = 1; } else { I.mx = 1; I.my = -0.5; } }
  };
  T.pred = function (name, rttMs, jitMs, seed, ch) {
    const sc = Object.assign({}, SCEN[name]); let s = seed || 5; const rand = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const FR = 1 / 60, up = (rttMs || 0) / 2000, down = up, jit = (jitMs || 0) / 1000; ch = ch === undefined ? 1 : ch; const C = HW.CHARS[ch];
    const X = setup(0), S = X.sim.S, k = join(X, ch); k.G2 = Net.newMirror();
    for (let i = 0; i < 4; i++) tick(X);
    S.respawns.length = 0; for (const it of Array.from(S.items.values())) if (it.k !== 'f' && it.k !== 'a') X.sim.remItem(it);   // no veggies, mushrooms or pickups the scenario did not ask for
    let W = wormOf(X, k); const st0 = sc.setup ? sc.setup(X) : sc.start ? sc.start() : { x: OPEN.x + 60, y: OPEN.y, ang: 0 }; place(W, st0.x, st0.y, st0.ang, 60);
    for (let i = 0; i < 6; i++) { W.shield = 99; W.stuck = sc.setup ? 1 : 0; tick(X); } W.stuck = 0;   // the mirrors have seen the move before the clock starts
    const G = k.G, G2 = k.G2, upQ = [], dnQ = []; let lastUp = 0, lastDn = 0, snapsOut = 0, upSum = 0, upN = 0, fNow = 0;
    Net.conn = { open: true, dataChannel: { bufferedAmount: 0 }, send(m) { const due = Math.max(lastUp, vt + up + rand() * jit); lastUp = due; upQ.push({ due, f: fNow, m: JSON.stringify(m) }); } };
    Net.tnt = 0; Net.tnWas = false; Net.inKey = ''; Net.inT = 0; Net.stats.rtt = 0; Net.stats.pred = 0; Net.stats.psnap = 0;
    const N = Math.round((sc.secs || 12) * 60), P = [], Q = [], TR = [], I = { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false };
    let pingT = 0, others = 0, othersN = 0, predDead = 0, deadF = 0, itemsBad = 0, bumps = 0; const pen = [], pen2 = [], penH = [];
    // how far a head is inside a body, past the distance at which the host calls it contact (0 or less: not inside)
    const inside = (a, b) => { if (!a || !b) return -99; let d = 1e9; for (const q of b.pts) d = Math.min(d, Math.hypot(q.x - a.x, q.y - a.y)); return a.r * 0.7 + b.r * 0.78 - d; };
    const within = (t, w) => w && (Array.isArray(w[0]) ? w.some(q => t >= q[0] && t < q[0] + q[1]) : t >= w[0] && t < w[0] + w[1]);
    k.conn.out.length = 0;
    for (let f = 0; f < N; f++) {
      vt += FR; const t = f * FR; fNow = f;
      // --- host ---
      if (!within(t, sc.hostFreeze)) {
        while (upQ.length && upQ[0].due <= vt) { const u = upQ.shift(); if (t < 3.5) { upSum += f - u.f; upN++; } k.conn.recv(JSON.parse(u.m)); }
        W = wormOf(X, k);
        if (W) { if (!sc.noShield) W.shield = 99; if (!sc.keepMass) W.mass = 60; if (sc.host) sc.host(t, W, X); }
        k.conn.dataChannel.bufferedAmount = within(t, sc.drop) ? 1e6 : 0;   // a choked channel: the host sends that client nothing (real lost snapshots)
        X.sim.step(FR); const evs = S.events; S.events = [];
        if (Net.hostTick(X.sim, FR, evs)) { S.adds.length = 0; S.rems.length = 0; }
        for (const m of k.conn.out) {
          const spike = sc.spike && m.indexOf('"t":"s"') > 0 && ++snapsOut % sc.spike === 0 ? 0.15 : 0, due = Math.max(lastDn, vt + down + rand() * jit + spike); lastDn = due; dnQ.push({ due, m });
        }
        k.conn.out.length = 0;
      }
      W = wormOf(X, k); TR.push(W ? { id: W.id, x: W.x, y: W.y, a: W.ang } : null);
      // --- client ---
      while (dnQ.length && dnQ[0].due <= vt) {
        const sm = dnQ.shift().m;
        for (const g of [G, G2]) { const m = JSON.parse(sm); if (m.t === 'it' || m.t === 'pt') Net.applyPart(g, m); else if (m.t === 's') { Net.applySnap(g, m); if (g === G) for (const e of m.e) if (e[0] === 'bump' && e[3] === G.myId) bumps++; } else if (m.t === 'k' && g === G) Net.onPong(m.c); }
      }
      if (within(t, sc.hidden)) { P.push(null); Q.push(null); continue; }   // a hidden tab: messages still arrive, frames do not happen
      if (t >= pingT) { pingT = t + 1; Net.conn.send({ t: 'k', c: Math.round(vt * 1000) }); }
      // as playFrame in main.js does it
      const p = G.players.find(q => q.pid === k.pid) || { deadT: 0 }, me = p.wormId ? G.wmap.get(p.wormId) || null : null;
      sc.input(t, I, me, f);
      G.myId = me ? me.id : 0; G.myInp = I;
      Net.sendInput(I, 0, !me && p.deadT > 1.2);
      const pr0 = Net.stats.pred, sn0 = Net.stats.psnap, lead0 = G.pr ? 1 : 0;
      Net.clientUpdate(G, FR); Net.clientUpdate(G2, FR);
      if (!me) { deadF++; if (Net.stats.pred !== pr0 || G.pr) predDead++; }
      const m2 = me && G2.wmap.get(me.id);
      P.push(me ? { id: me.id, x: me.x, y: me.y, a: me.ang, snap: Net.stats.psnap !== sn0, fresh: !lead0, pred: Net.stats.pred !== pr0, e: Net.stats.perr } : null);
      Q.push(m2 ? { id: m2.id, x: m2.x, y: m2.y, a: m2.ang } : null);
      if (sc.B && me) { pen[f] = inside(me, G.wmap.get(sc.B.id)); pen2[f] = inside(m2, G2.wmap.get(sc.B.id)); penH[f] = inside(W, sc.B); }
      // everything else must be exactly what the mirror without prediction shows
      for (const w of G.worms) { if (w === me) continue; othersN++; const v = G2.wmap.get(w.id); if (!v || v.x !== w.x || v.y !== w.y || v.ang !== w.ang || v.aim !== w.aim || v.pts.length !== w.pts.length) others++; }
      if (G.bullets.length !== G2.bullets.length || G.bullets.some((b, i) => b.x !== G2.bullets[i].x || b.y !== G2.bullets[i].y)) others++;
      if (G.items.size !== G2.items.size || G.zones.length !== G2.zones.length) itemsBad++;
    }
    Net.conn = null;
    // --- measure ---
    // where the host's head is when the input of frame f lands: that is what prediction is after. With the lead
    // capped the head is deliberately held back by `held` seconds along its path, so that is measured too.
    // (an input waits for the host's next frame, and jitter adds to that: the average trip of this run is used)
    const upF = upN ? upSum / upN : 1, held = Math.max(0, upF * FR * 2 + PC.PIPE - PC.LEAD_MAX), heldF = held / FR;
    const at = x => { const i = Math.floor(x), a = TR[i], b = TR[i + 1], u = x - i; return a && b && a.id === b.id ? { id: a.id, x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, a: a.a } : a || null; };
    const vmax = C.speed * (sc.mult || 1), stat = a => { if (!a.length) return { mean: 0, p95: 0, max: 0 }; const q = a.slice().sort((x, y) => x - y); return { mean: +(a.reduce((x, y) => x + y, 0) / a.length).toFixed(2), p95: +q[Math.floor(q.length * 0.95)].toFixed(2), max: +q[q.length - 1].toFixed(2) }; };
    const win = (t0, t1) => {
      const ideal = [], cap = [], cross = [], base = [], steps = [], stepsBase = []; let snaps = 0;
      for (let f = Math.round(t0 * 60); f < Math.min(N, Math.round(t1 * 60)); f++) {
        const p = P[f], g = at(f + upF), gc = at(f + upF - heldF), q = Q[f]; if (!p) continue; if (p.snap) snaps++;
        if (g && g.id === p.id) { ideal.push(Math.hypot(p.x - g.x, p.y - g.y)); cross.push(Math.abs((p.x - g.x) * -Math.sin(g.a) + (p.y - g.y) * Math.cos(g.a))); if (q) base.push(Math.hypot(q.x - g.x, q.y - g.y)); }
        if (gc && gc.id === p.id) cap.push(Math.hypot(p.x - gc.x, p.y - gc.y));
        const o = P[f - 1]; if (o && o.id === p.id && !p.snap && !p.fresh) steps.push(Math.hypot(p.x - o.x, p.y - o.y));
        const qo = Q[f - 1]; if (q && qo) stepsBase.push(Math.hypot(q.x - qo.x, q.y - qo.y));
      }
      const mean = steps.reduce((x, y) => x + y, 0) / (steps.length || 1), sd = Math.sqrt(steps.reduce((x, y) => x + (y - mean) * (y - mean), 0) / (steps.length || 1));
      return { ideal: stat(ideal), held: stat(cap), cross: stat(cross), noPred: stat(base), snaps, maxStep: +(Math.max(0, ...steps) / (vmax * FR)).toFixed(2), cv: +(sd / (mean || 1)).toFixed(3), n: ideal.length };
    };
    const r = { name, link: rttMs, jit: jitMs, upMs: Math.round(upF * FR * 1000), heldMs: Math.round(held * 1000), lead: Math.round(Math.min(PC.LEAD_MAX, G.rtt + PC.PIPE) * 1000), rtt: Math.round(upF * FR * 2000), rttSeen: Net.stats.rtt, speed: C.speed, mult: sc.mult || 1, all: win(3, 12), snaps: Net.stats.psnap, others, othersN, itemsBad, predFrames: Net.stats.pred, deadF, predDead, snapAt: P.map((p, f) => p && p.snap ? f : -1).filter(f => f >= 0), stepLimit: +(1 + PC.FIX / (sc.mult || 1) + PC.RTT_DOWN).toFixed(2) };   // per frame: its own speed, the slide, and the round-trip estimate coming down
    if (sc.flick) {
      // how many frames after a flick of the stick does the head start to turn? (0 = the same frame)
      const lag = A => { const l = []; for (let t = 4.5; t < 11; t += sc.flick) { const F = Math.round(t * 60); let j = 0; while (j < 60 && A[F + j] && A[F - 1] && Math.abs(HW.util.angDiff(A[F + j].a, A[F - 1].a)) < 0.02) j++; l.push(j); } return l; };
      const lp = lag(P), lq = lag(Q); r.turnLag = { pred: Math.max(...lp), predMean: +(lp.reduce((a, b) => a + b, 0) / lp.length).toFixed(2), noPredMean: +(lq.reduce((a, b) => a + b, 0) / lq.length).toFixed(1), n: lp.length };
      const F = Math.round(4.5 * 60); r.firstFrame = +Math.abs(HW.util.angDiff(P[F].a, P[F - 1].a)).toFixed(4); r.fullRate = +(C.turn * FR).toFixed(4);
    }
    if (sc.stopAt) { r.moving = win(3, sc.stopAt); r.settled = win(sc.stopAt + 1, sc.stopAt + 2); }
    if (sc.fxAt) {
      // before / during / after the disturbance, and how long after its end the head is back to its usual accuracy
      // (the half second before it is left out: "where the host's head will be" already looks past the event there)
      const end = sc.fxEnd || sc.fxAt; r.before = win(3, sc.fxAt - 0.5); r.during = win(sc.fxAt, end + 1.5); r.after = win(end + 1.5, 12);
      let last = -1; for (let f = Math.round(sc.fxAt * 60); f < N - 30; f++) { const p = P[f], g = at(f + upF - heldF); if (p && g && g.id === p.id && Math.hypot(p.x - g.x, p.y - g.y) > r.before.held.p95 + 4) last = f; }
      r.recoverMs = last < 0 ? 0 : Math.round((last + 1 - Math.round(end * 60)) / 60 * 1000);
    }
    if (name === 'respawn') {
      const F = P.findIndex((p, f) => f > 300 && p), g = at(F + upF); r.newLife = { frame: F, firstErr: +(g ? Math.hypot(P[F].x - g.x, P[F].y - g.y) : -1).toFixed(2), noPredFirst: +(g && Q[F] ? Math.hypot(Q[F].x - g.x, Q[F].y - g.y) : -1).toFixed(2), newId: P[F].id !== P[200].id, after: win(F / 60 + 0.5, 12) };
    }
    if (name === 'bump') {
      const mx = (a, t0, t1) => +Math.max(-99, ...a.slice(Math.round(t0 * 60), Math.round(t1 * 60)).filter(v => v !== undefined)).toFixed(2);
      // touching = the frames in which the drawn head is within 2 px of the contact distance
      const touchF = pen.map((v, f) => v > -2 ? f : -1).filter(f => f >= 0), hostF = penH.map((v, f) => v > -2 ? f : -1).filter(f => f >= 0);
      r.bump = { events: bumps, inside: mx(pen, 3.5, 12), insideNoPred: mx(pen2, 3.5, 12), insideHost: mx(penH, 3.5, 12), touchMs: [Math.round(touchF[0] / 60 * 1000), Math.round(touchF[touchF.length - 1] / 60 * 1000)], hostTouchMs: [Math.round(hostF[0] / 60 * 1000), Math.round(hostF[hostF.length - 1] / 60 * 1000)],
        held: win(5.2, 6.4), leaving: win(6.5, 8), after: win(8, 12), alive: !!wormOf(X, k) && TR[N - 1] && TR[N - 1].id === TR[0].id };
    }
    if (name === 'freeze') {
      // while the host is frozen the head may coast, then it must stop and wait
      const a = P[Math.round(5 * 60) - 1], b = P[Math.round(6.4 * 60)], c = P[Math.round(5.8 * 60)]; r.coast = { moved: +Math.hypot(b.x - a.x, b.y - a.y).toFixed(1), stillAtEnd: +Math.hypot(b.x - c.x, b.y - c.y).toFixed(2), limit: +(C.speed * (PC.COAST + upF * FR * 2 + 0.1)).toFixed(1) };
    }
    return r;
  };
  // solo play and hosting must never touch the client code: the real game loop is run with a counter on it
  T.solo = async function () {
    const App = HW.App, real = Net.clientUpdate; let calls = 0; Net.now = () => performance.now() / 1000;
    Net.clientUpdate = function () { calls++; return real.apply(this, arguments); };
    const wait = ms => new Promise(r => setTimeout(r, ms)), out = {};
    Net.stats.pred = 0; App.startLocal([1]); await wait(700);
    out.solo = { calls, pred: Net.stats.pred, pr: 'pr' in App.G, myId: 'myId' in App.G, frames: App.sim.S.t > 0.3, role: Net.role };
    Net._loop(() => App.sim); await wait(700);   // the same game as an online host (no PeerJS needed for that)
    out.host = { calls, pred: Net.stats.pred, pr: 'pr' in App.G, myId: 'myId' in App.G, role: Net.role, ticks: Net.tick > 0 };
    Net.clientUpdate = real; App.quit(); Net.now = () => vt;
    return out;
  };
  T.firstBad = function (v) { if (v === null) firstBad = null; return firstBad; };
  return T;
})();
"""

def newtab(b, w=1280, h=720, dpr=1, mobile=False, touch=False):
    t = b.tab(); t.device(w, h, dpr, mobile, touch)
    t.call("Network.enable"); t.call("Network.setCacheDisabled", {"cacheDisabled": True})  # always test the files on disk
    return t

def part_a(b):
    print("== Part A: net.js through fake connections (no network) ==")
    t = newtab(b); t.goto(URL, 1.5); t.eval(HARNESS)
    def run(js):
        r = json.loads(t.eval("(()=>{TH.firstBad(null);const r=TH.%s;r.firstBad=r.firstBad||TH.firstBad();return JSON.stringify(r)})()" % js, 120))
        if r.get("firstBad") is None: r.pop("firstBad", None)
        return r
    r = run("churn()"); print(" churn  :", r)
    check("churn: every client matches the host after every snapshot (items, worms, bullets, zones, players)", r["bad"] == 0, r.get("firstBad"))
    check("churn: host state sane, no oversize message", r["sane"] and r["over"] == 0 and r["maxMsg"] < 15000, r["maxMsg"])
    check("churn: each client got exactly one handshake and its own pid", r["first"] == [1, 1, 1] and sorted(r["pids"]) == [1, 2, 3], (r["first"], r["pids"]))
    check("churn: clients received events", all(e > 0 for e in r["events"]), r["events"])
    r = run("typical()"); print(" typical:", r); typ = r
    check("typical: in sync", r["bad"] == 0)
    check("typical: bandwidth per client below the old format", r["kbps"] < r["oldKbps"], "%s vs %s KB/s" % (r["kbps"], r["oldKbps"]))
    r = run("worst()"); print(" worst  :", r); worst = r
    check("worst: no message near the 16300-byte PeerJS limit", r["maxMsg"] < 15000 and r["over"] == 0, r["maxMsg"])
    check("worst: old format would have overflowed here (the case this guards)", r["oldAll"] > 16300, r["oldAll"])
    check("worst: in sync after bursts of %d and %d item adds" % (r["adds6"], r["addsAll"]), r["bad"] == 0)
    check("worst: oversize burst handled by a full resync", r["resync"] > r["resyncBefore"] and min(r["zs"]) >= 2, (r["resync"], r["zs"]))
    r = run("fuzz()"); print(" fuzz   :", r)
    check("fuzz: malformed messages ignored, nothing thrown, sim sane", r.get("threw") == 0 and r.get("sane") and r.get("players") and r.get("stillIn") and r.get("sync"), r)
    check("fuzz: ability counter not poisoned by junk values", r.get("seq") == 1, r.get("seq"))
    check("fuzz: character index clamped", r.get("ch") == [4, 0], r.get("ch"))
    r = run("gate()"); print(" gate   :", r)
    check("room full: 5th player gets 'full' and is not added", '"full"' in r["fullMsg"] and r["playersAfterFifth"] == 4, r["fullMsg"][:60])
    check("leave frees the seat; next player gets it and a full handshake", r["afterLeave"] == 3 and r["rejoin"]["players"] == 4 and r["rejoin"]["pid"] == r["rejoin"]["freed"] and r["rejoin"]["first"] == 1 and r["rejoin"]["sync"], r["rejoin"])
    check("'bye' removes the player at once", r["afterBye"] == 3 and r["byeClosed"])
    check("wrong version refused with a reason", "RELOAD" in r["oldVersion"] and r["afterOld"] == 3, r["oldVersion"])
    check("non-JSON connection closed; lobby capped; silent connections dropped", r["binary"] and r["lobbyCap"] == 8 and r["quietDropped"] == 0 and r["playersEnd"] == 3, (r["lobbyCap"], r["quietDropped"]))
    r = run("sameTick()"); print(" same   :", r)
    check("two joins in one tick: distinct pids, one handshake each, both exact", sorted(r["pids"]) == [1, 2] and r["first"] == [1, 1] and r["sync0"] and r["bad"] == 0, r)
    check("two joins: no missing / duplicate worms, bodies rebuilt", r["worms"][0] == r["worms"][2] and r["worms"][1] == r["worms"][2] and r["bodies"], r["worms"])
    r = run("slow()"); print(" slow   :", r)
    check("stalled client: nothing sent into a full channel, other client unaffected", r["sentWhileStalled"] == 0 and r["skips"] >= 60 and r["otherOk"], r["sentWhileStalled"])
    check("stalled client: exact again after catching up from its queue", r["caughtUp"] and r["resync0"] == 0)
    check("stalled client: queue is capped, then a full resync makes it exact", r["queuedCapped"] <= 6000 and r["resync1"] >= 1 and r["resynced"] and r["exact"] and r["bad"] == 0 and r["maxMsg"] < 15000, r)
    r = run("flags()"); print(" flags  :", r)
    check("ability: used once per press, repeats ignored", r["abilUsed"] and r["repeatIgnored"])
    check("ability pressed while dead is not saved for the next life", r["inpAbilWhileDead"] is False and r.get("deadPressNotSaved") and r.get("nextPressWorks"), r)
    check("respawn flag: ignored while alive, honoured only after the 1 s minimum", r["spawnFlagAliveIgnored"] and r["noEarlySpawn"] and r["spawnTooEarly"] and r["respawned"] and r["deadOnClient"] and r["mirrorSeesWorm"])
    check("quiet client: inputs neutralised, kept by keep-alives, pong sent", r["held"] and r["neutralised"] and r["pong"] and r["stillIn"] and r["keptAliveByPings"])
    check("silent client dropped after 30 s, others stay", r["timedOut"] and "TIMED OUT" in r["kickMsg"] and r["otherStays"], r["kickMsg"])
    check("host asleep for a minute does not time out its clients", r["hostSleepKeepsClients"] and r["sync"])
    r = run("stale()"); print(" stale  :", r)
    check("old room's connections cannot touch a new game", r["items"] and r["events"] and r["players"] == 0 and r["gotBye"] and r["conns"] == 0, r)
    sm = {}
    for name, args in (("clean 60Hz host", "0.004,0,60"), ("jitter 25ms", "0.025,0,60"), ("jitter 25ms + 150ms spikes", "0.025,25,60"), ("30Hz host (hidden tab / slow phone)", "0.01,0,30")):
        r = run("smooth(%s)" % args); sm[name] = r; print(" smooth [%s]:" % name, r)
    check("interpolation: even speed on a clean link (cv < 0.06), no backward steps", sm["clean 60Hz host"]["cv"] < 0.06 and sm["clean 60Hz host"]["back"] == 0, sm["clean 60Hz host"]["cv"])
    check("interpolation: still even with 25 ms jitter (cv < 0.12), no backward steps, no stops", sm["jitter 25ms"]["cv"] < 0.12 and sm["jitter 25ms"]["back"] == 0 and sm["jitter 25ms"]["stops"] == 0, sm["jitter 25ms"])
    check("interpolation: picture stays within 1.5 px of the true path and < 160 ms old", all(v["offPath"] < 1.5 for v in sm.values()) and sm["jitter 25ms"]["lagMs"] < 160, [(v["offPath"], v["lagMs"]) for v in sm.values()])
    check("interpolation: 30 Hz host has no backward steps", sm["30Hz host (hidden tab / slow phone)"]["back"] == 0)
    check("interpolation: more even than the previous method on the same snapshots, in every case", all(v["cv"] < v["old"]["cv"] for v in sm.values()), [(v["cv"], v["old"]["cv"]) for v in sm.values()])
    r = run("bullets(0.025)"); print(" bullets:", r)
    check("bullets: never move backwards, stay on the host's line, steady lag", r["samples"] > 500 and r["back"] == 0 and r["maxCross"] < 2.5 and r["lagSd"] < 4 and 15 < r["lagMs"] < 70, r)
    # ---------- power-ups, special guns, golden burger, frenzy, awards, taunts, the new events ----------
    r = run("fresh()"); print(" fresh  :", r)
    near = lambda a, b: abs(a - b) < 0.25
    check("new state: every mirror matches the host after every snapshot, no oversize message", r["bad"] == 0 and r["sane"] and r["over"] == 0 and r["maxMsg"] < 15000, (r["bad"], r.get("firstBad"), r["maxMsg"]))
    check("power-ups: all four countdowns reach near and far mirrors; pick-up event goes to owner and neighbour, not across the arena", all(p["host"] > 5 and near(p["host"], p["a"]) and near(p["host"], p["far"]) and p["who"] == [1, 1, 0] and p["pid"] for p in r["power"]), r["power"])
    check("power-ups: mirrors count down by themselves (still within 0.25 s two seconds later)", all(near(h, a) and near(h, f) for h, a, f in r["powerLater"]), r["powerLater"])
    check("supersize: mirror worms get the bigger radius", r["bigR"][0] == r["bigR"][1] == r["bigR"][2] and r["bigR"][0] > r["bigR"][3], r["bigR"])
    check("power-up running out: only the owner is told; its mirror is back to normal", r["powerOff"]["who0"] == [1, 0, 0] and r["powerOff"]["who1"] == [1, 0, 0] and r["powerOff"]["a"] == [0, 0] and r["powerOff"]["r"][0] == r["powerOff"]["r"][1], r["powerOff"])
    gs = r["guns"]
    check("special guns: sg / sgT on every mirror, the special gun's sprite is the one drawn", len(gs) == 5 and all(g["sg"] == [g["ty"] + 1] * 3 and near(g["sgT"][0], g["sgT"][1]) and near(g["sgT"][0], g["sgT"][2]) and g["spr"] and g["who"] == [1, 1, 0] for g in gs), [(g["sg"], g["sgT"]) for g in gs])
    check("bullets: kind = the gun's kind (5..9) on owner and neighbour, none sent across the arena", all(g["kinds"] == [5 + g["ty"]] and g["n"] > 0 and g["nearN"] > 0 and g["far"] == 0 and g["shot"][0] > 0 and g["shot"][1] > 0 and g["shot"][2] == 0 for g in gs), [(g["kinds"], g["n"], g["nearN"], g["far"], g["shot"]) for g in gs])
    check("bullets: client age runs with the host's (flame puffs grow)", all(g["ageErr"] < 0.1 and g["ageMax"] >= 0.3 for g in gs), [(g["ageErr"], g["ageMax"]) for g in gs])
    check("rockets from the launcher speed up on the client with the launcher's own numbers", gs[1]["v1"] > gs[1]["v0"] + 60 and gs[1]["vErr"] < 40 and gs[0]["v0"] == gs[0]["v1"] == 720, (gs[1]["v0"], gs[1]["v1"], gs[1]["vErr"]))
    check("special gun running out: sg back to 0 everywhere, own gun drawn again, only the owner is told", r["gunOff"]["who"] == [1, 0, 0] and r["gunOff"]["sg"] == [0, 0, 0] and r["gunOff"]["spr"], r["gunOff"])
    check("golden burger: event with its value and the eater's pid, mass arrives", r["gold"]["who"] == [1, 1, 0] and r["gold"]["pid"] and r["gold"]["grew"] >= 29, r["gold"])
    check("item kinds p / g / x: on every mirror with type and value, removed again", all(i == r["itemsHost"] for i in r["items"]) and "x0:30" in r["itemsHost"] and r["itemsGone"], (r["itemsHost"], r["items"]))
    check("item rows from a broken host: types clamped, unknown kinds dropped", r["junkItems"] == "p3 g0 x0", r["junkItems"])
    ro = r["route"]
    check("events for a worm reach its client and the neighbours, not the far side: " + ", ".join(k for k in ("ping", "chill", "streak", "bounty", "hit", "bump")), all(ro[k] == [1, 1, 0] for k in ("ping", "chill", "streak", "bounty", "hit", "bump")), ro)
    check("events only the owner needs stay with the owner: poweroff, gunoff, dry, eat", all(ro[k] == [1, 0, 0] for k in ("poweroff", "gunoff", "dry", "eat")), ro)
    check("events by position (clang, drop with its string, boom, shot, puff) go by distance only, even when their 4th field equals a worm id", all(ro[k] == [1, 1, 0] for k in ("clang", "dropNearA", "boom", "shot", "puff")) and ro["dropNearF"] == [0, 0, 1], ro)
    c = r["cap"]
    check("event cap: 40 per snapshot; deaths (24), frenzy and the client's own pick-ups survive a flood of 100 puffs", c["n"] == 40 and c["die"] == 24 and c["power"] == 1 and c["gold"] == 1 and c["frenzy"] == 1 and c["farDie"] == 24 and c["farFrenzy"] == 1, c)
    check("frenzy: flag on every mirror, the event reaches every client once", r["frenzy"]["host"] and r["frenzy"]["mirrors"] == [True] * 3 and r["frenzy"]["events"] == [1, 1, 1], r["frenzy"])
    check("taunt: one press = one taunt on the host, shown to owner and neighbour; repeats of the message do nothing; the next press works", r["taunt"]["first"] == 1 and r["taunt"]["who"] == [1, 1, 0] and r["taunt"]["text"] and r["taunt"]["repeats"] == 1 and r["taunt"]["second"] == 2, r["taunt"])
    si = r["sendInput"]
    check("taunt through Net.sendInput: sent at once, a held button is one taunt, a choked channel does not lose it", si["atOnce"] and si["held"] and si["choked"] and si["after"] and si["flips"] == 2 and si["taunts"] == 2, si)
    check("taunt pressed while dead is not saved for the next life", r["tauntDead"] is False)
    check("a client that is out of lives is sent what happens round the worm it is watching (the biggest)", r["spectate"] < 12, r["spectate"])
    check("awards: the same list on every client's results screen, for competitors the client knows", len(r["awards"]["host"]) >= 3 and r["awards"]["same"] == [True] * 3 and r["awards"]["cids"], r["awards"])
    check("next match: awards and frenzy cleared on every mirror", r["next"] == [True] * 3, r["next"])
    fresh = r
    # ---------- prediction of the client's own worm ----------
    # link delay + jitter per run; with the 60 fps stepping of this harness they give round trips of about 67, 150 and 300 ms
    LINKS = ((40, 10), (112, 20), (250, 30)); PR = {}
    def pred(name):
        PR[name] = [run("pred('%s',%d,%d)" % (name, l, j)) for l, j in LINKS]; return PR[name]
    fmt = lambda v: "%.1f/%.1f/%.1f" % (v["mean"], v["p95"], v["max"])
    print(" prediction: px between the drawn head and where the host's head is when that frame's input lands (mean/p95/max);")
    print("   'held' = against the point 0.15 s ahead of the host's picture, which is what a link slower than the cap is drawn at")
    for name in ("weave", "turns", "stop", "drop", "spikes", "wall", "counter", "table"):
        rs = pred(name)
        for q in rs: print("   %-8s rtt %3d ms (held back %3d ms): ideal %s  held %s  across the path p95 %.2f  without prediction %s  biggest step x%.2f  evenness cv %.3f  snaps %d" % (name, q["rtt"], q["heldMs"], fmt(q["all"]["ideal"]), fmt(q["all"]["held"]), q["all"]["cross"]["p95"], fmt(q["all"]["noPred"]), q["all"]["maxStep"], q["all"]["cv"], q["snaps"]))
        check("prediction [%s]: head within 6 px (p95) / 9 px (max) of where the host will have it, on all three links" % name, all(q["all"]["held"]["p95"] <= 6 and q["all"]["held"]["max"] <= 9 and q["all"]["n"] > 400 for q in rs), [fmt(q["all"]["held"]) for q in rs])
        check("prediction [%s]: never further from the uncapped target than the capped lead explains (+6 px)" % name, all(q["all"]["ideal"]["max"] <= q["heldMs"] / 1000 * q["speed"] + 6 for q in rs), [(q["all"]["ideal"]["max"], q["heldMs"]) for q in rs])
        check("prediction [%s]: within 3 px across the path (p95), no snap, no frame faster than speed + slide + estimate allowance" % name, all(q["all"]["cross"]["p95"] <= 3 and q["snaps"] == 0 and q["all"]["maxStep"] <= q["stepLimit"] + 0.02 for q in rs), [(q["all"]["cross"]["p95"], q["snaps"], q["all"]["maxStep"]) for q in rs])
        check("prediction [%s]: at least 3 times closer than drawing the worm from snapshots" % name, all(q["all"]["noPred"]["mean"] >= 3 * q["all"]["held"]["mean"] for q in rs), [(q["all"]["noPred"]["mean"], q["all"]["held"]["mean"]) for q in rs])
        check("prediction [%s]: every other worm, bullet, item and zone exactly as without prediction" % name, all(q["others"] == 0 and q["othersN"] > 5000 and q["itemsBad"] == 0 for q in rs), [(q["others"], q["itemsBad"]) for q in rs])
    rs = PR["turns"]; print("   turn lag (frames from a flick of the stick to the head turning): predicted", [q["turnLag"]["pred"] for q in rs], "without prediction", [q["turnLag"]["noPredMean"] for q in rs])
    check("prediction: the head starts turning in the very frame of the input, at the full turning rate, on all three links", all(q["turnLag"]["pred"] == 0 and q["turnLag"]["n"] >= 4 and q["firstFrame"] >= q["fullRate"] * 0.95 for q in rs), [(q["turnLag"], q["firstFrame"]) for q in rs])
    check("prediction: without it the same flick takes 4+ frames to show (the test can tell the difference)", all(q["turnLag"]["noPredMean"] >= 4 for q in rs), [q["turnLag"]["noPredMean"] for q in rs])
    rs = PR["stop"]; print("   stick released: error a second later (mean/p95/max)", [fmt(q["settled"]["held"]) for q in rs], "of which across the path", [fmt(q["settled"]["cross"]) for q in rs])
    # (what is left lies along the path: the head is a few ms early or late, by as much as the round-trip estimate is off)
    check("prediction: with the stick at rest the error settles to under 1 px across the path and 4 px along it", all(q["settled"]["held"]["max"] <= 4 and q["settled"]["cross"]["max"] <= 1 and q["settled"]["n"] > 50 for q in rs), [(fmt(q["settled"]["held"]), fmt(q["settled"]["cross"])) for q in rs])
    print("   things the client only learns afterwards: biggest error while it lasts / p95 before / p95 after / ms to settle / snaps")
    for name in ("stuck", "slow", "chill", "rampage", "boost", "boostDry", "sauce", "trip"):
        rs = pred(name)
        for q in rs: print("   %-8s rtt %3d ms: %5.1f / %4.1f / %4.1f / %4d ms / %d   biggest step x%.2f" % (name, q["rtt"], q["during"]["held"]["max"], q["before"]["held"]["p95"], q["after"]["held"]["p95"], max(0, q["recoverMs"]), q["snaps"], q["all"]["maxStep"]))
        check("prediction [%s]: error bounded by what one round trip of not knowing can cost (speed x (rtt + 0.1 s)), no snap" % name, all(q["during"]["held"]["max"] <= q["speed"] * q["mult"] * (q["rtt"] / 1000 + 0.1) and q["snaps"] == 0 for q in rs), [(q["during"]["held"]["max"], round(q["speed"] * q["mult"] * (q["rtt"] / 1000 + 0.1), 1)) for q in rs])
        check("prediction [%s]: back to normal within a second, slid there (no frame faster than speed + slide + estimate allowance)" % name, all(q["recoverMs"] <= 1000 and q["after"]["held"]["p95"] <= q["before"]["held"]["p95"] + 2 and q["all"]["maxStep"] <= q["stepLimit"] + 0.02 and q["others"] == 0 for q in rs), [(q["recoverMs"], q["after"]["held"]["p95"], q["all"]["maxStep"]) for q in rs])
    rs = pred("respawn")
    for q in rs: print("   respawn  rtt %3d ms: %d frames dead, predicted while dead %d; first frame of the new life %.1f px off (%.1f without prediction); afterwards %s" % (q["rtt"], q["deadF"], q["predDead"], q["newLife"]["firstErr"], q["newLife"]["noPredFirst"], fmt(q["newLife"]["after"]["held"])))
    check("prediction: none while dead", all(q["predDead"] == 0 and q["deadF"] > 30 for q in rs), [(q["predDead"], q["deadF"]) for q in rs])
    check("prediction: a new life starts in the right place at once (no slide from the old one), then tracks as usual", all(q["newLife"]["newId"] and q["newLife"]["firstErr"] <= q["heldMs"] / 1000 * q["speed"] + 10 and q["newLife"]["after"]["held"]["max"] <= 9 and q["snaps"] == 0 and q["others"] == 0 for q in rs), [q["newLife"]["firstErr"] for q in rs])
    rs = pred("teleport")
    for q in rs: print("   teleport rtt %3d ms: snaps %d, settled %d ms after the host moved the worm 1200 px; afterwards p95 %.1f" % (q["rtt"], q["snaps"], q["recoverMs"], q["after"]["held"]["p95"]))
    check("prediction: a worm moved by the host is followed with exactly one jump, right again within a round trip + 0.1 s", all(q["snaps"] == 1 and q["recoverMs"] <= q["rtt"] + 100 and q["after"]["held"]["p95"] <= q["before"]["held"]["p95"] + 2 for q in rs), [(q["snaps"], q["recoverMs"]) for q in rs])
    rs = pred("hidden")
    for q in rs: print("   hidden tab (2 s) rtt %3d ms: snaps %d, biggest error after coming back %.1f, settled after %d ms" % (q["rtt"], q["snaps"], q["during"]["held"]["max"], max(0, q["recoverMs"])))
    check("prediction: a tab that was hidden starts again from the host's position (one jump), right within half a second", all(q["snaps"] == 1 and q["recoverMs"] <= 500 and q["during"]["held"]["max"] <= 20 and q["after"]["held"]["p95"] <= q["before"]["held"]["p95"] + 2 for q in rs), [(q["snaps"], q["recoverMs"], q["during"]["held"]["max"]) for q in rs])
    rs = pred("freeze")
    for q in rs: print("   host frozen 1.5 s, rtt %3d ms: head ran on %.1f px (limit %.1f) and stood still after that (%.2f px); settled %d ms after the host came back, snaps %d" % (q["rtt"], q["coast"]["moved"], q["coast"]["limit"], q["coast"]["stillAtEnd"], max(0, q["recoverMs"]), q["snaps"]))
    check("prediction: with the host silent the head stops within the coast limit and waits", all(q["coast"]["moved"] <= q["coast"]["limit"] and q["coast"]["stillAtEnd"] < 0.5 for q in rs), [q["coast"] for q in rs])
    check("prediction: right again within 1.5 s of the host coming back, at most one jump", all(q["recoverMs"] <= 1500 and q["snaps"] <= 1 and q["after"]["held"]["p95"] <= q["before"]["held"]["p95"] + 2 for q in rs), [(q["recoverMs"], q["snaps"]) for q in rs])
    # the bump: square into the side of a frozen worm, held there, then away
    rs = pred("bump")
    for q in rs: print("   bump     rtt %3d ms: drawn head at most %.2f px inside the body (host %.2f, without prediction %.2f); %d bump events; touching %s ms (host %s); leaving: error max %.1f, biggest step x%.2f, snaps %d" % (q["rtt"], q["bump"]["inside"], q["bump"]["insideHost"], q["bump"]["insideNoPred"], q["bump"]["events"], q["bump"]["touchMs"], q["bump"]["hostTouchMs"], q["bump"]["leaving"]["held"]["max"], q["bump"]["leaving"]["maxStep"], q["snaps"]))
    check("bump: the drawn head is never more than 3 px inside the other worm, on all three links", all(q["bump"]["inside"] <= 3 and q["bump"]["alive"] and q["bump"]["events"] >= 10 for q in rs), [q["bump"]["inside"] for q in rs])
    check("bump: held at the surface where the host holds it (within 5 px), from before the host's own contact", all(q["bump"]["held"]["held"]["max"] <= 5 and q["bump"]["touchMs"][0] <= q["bump"]["hostTouchMs"][0] + 20 for q in rs), [(q["bump"]["held"]["held"]["max"], q["bump"]["touchMs"], q["bump"]["hostTouchMs"]) for q in rs])
    check("bump: no jump when contact ends (no snap, no frame faster than speed + slide + estimate allowance, within 6 px of the host)", all(q["snaps"] == 0 and q["bump"]["leaving"]["maxStep"] <= q["stepLimit"] + 0.02 and q["bump"]["leaving"]["held"]["max"] <= 6 and q["bump"]["after"]["held"]["max"] <= 9 for q in rs), [(q["snaps"], q["bump"]["leaving"]["maxStep"], q["bump"]["leaving"]["held"]["max"]) for q in rs])
    t.eval("HW.Net.PRED.hold=false"); q = run("pred('bump',112,20)"); t.eval("HW.Net.PRED.hold=true")
    print("   bump without the test against visible worms (only the host's word): %.2f px inside" % q["bump"]["inside"])
    check("bump: without that test the head does sink in (so the check above means something)", q["bump"]["inside"] > 6, q["bump"]["inside"])
    # solo play and hosting: the real game loop, with a counter on the client code
    t.call("Page.bringToFront"); r = json.loads(t.eval("TH.solo().then(r=>JSON.stringify(r))", 30)); print(" solo   :", r)
    check("solo play never runs the client / prediction code", r["solo"]["frames"] and r["solo"]["calls"] == 0 and r["solo"]["pred"] == 0 and not r["solo"]["pr"] and not r["solo"]["myId"] and r["solo"]["role"] is None, r["solo"])
    check("hosting never runs it either", r["host"]["ticks"] and r["host"]["role"] == "host" and r["host"]["calls"] == 0 and r["host"]["pred"] == 0 and not r["host"]["pr"] and not r["host"]["myId"], r["host"])
    check("no page errors in part A", not t.errors, t.errors[:3])
    return typ, worst, fresh

def part_b(b):
    print("== Part B: real PeerJS cloud ==")
    hook = "HW.App.toast=(o=>s=>{(window.__toasts=window.__toasts||[]).push(s);o(s)})(HW.App.toast)"
    toasts = lambda t: t.eval("JSON.stringify(window.__toasts||[])")
    def both(tabs, secs, step=0.2):
        end = time.time() + secs
        while time.time() < end:
            for t in tabs: t.pump(step / len(tabs))
    def wait(tabs, js_tab, js, secs=25):
        end = time.time() + secs
        while time.time() < end:
            both(tabs, 0.3)
            if js_tab.eval(js): return True
        return False
    h = newtab(b); h.goto(URL, 1.5); h.eval(hook)
    h.eval("HW.App.startHost(0)")
    wait([h], h, "!!HW.Net.code", 25)
    code = h.eval("HW.Net.code"); print(" room code:", code, "role:", h.eval("HW.Net.role"))
    check("host opens a room", bool(code) and h.eval("HW.Net.role") == "host" and h.eval("HW.Net.online") is True)
    if not code: print(h.log[-10:]); return
    # --- three clients; the first two join at the same moment ---
    cl = []
    for i in range(3):
        c = newtab(b, 844, 390, 3, True, True); c.goto(URL + "?join=" + code, 1.2); c.eval(hook); cl.append(c)
    check("invite link prefills the code", cl[0].eval("HW.App.sel.code") == code and cl[0].eval("HW.App.screen") == "select")
    tabs = [h] + cl
    cl[0].eval("HW.App.startJoin(2,'%s')" % code); cl[1].eval("HW.App.startJoin(1,'%s')" % code)
    ok = wait(tabs, h, "HW.App.sim.S.players.length===3") and wait(tabs, cl[0], "HW.App.mode==='play'") and wait(tabs, cl[1], "HW.App.mode==='play'")
    check("two clients joining together both get in", ok, [c.eval("HW.App.mode") for c in cl[:2]])
    cl[2].eval("HW.App.startJoin(4,'%s')" % code)
    ok = wait(tabs, cl[2], "HW.App.mode==='play'") and wait(tabs, h, "HW.App.sim.S.players.length===4")
    check("third client joins: 4 players in the room", ok, h.eval("HW.App.sim.S.players.length"))
    both(tabs, 2.5)
    pids = [c.eval("HW.App.myPid") for c in cl]
    check("each client has its own player id", sorted(pids) == [1, 2, 3], pids)
    view = "(()=>{const G=HW.App.G,S=HW.App.sim&&HW.App.sim.S;return JSON.stringify({worms:G.worms.length,ids:G.worms.map(w=>w.id).sort((a,b)=>a-b).join(),dup:new Set(G.worms.map(w=>w.id)).size!==G.worms.length,items:G.items.size,players:G.players.length,bodies:G.worms.every(w=>w.pts.length===HW.segCount(w.mass))})})()"
    hv = json.loads(h.eval(view)); cvs = [json.loads(c.eval(view)) for c in cl]
    print(" host  :", {k: v for k, v in hv.items() if k != "ids"}); [print(" client:", {k: v for k, v in v.items() if k != "ids"}) for v in cvs]
    check("all clients see the host's worms (%d), none duplicated" % hv["worms"], all(abs(v["worms"] - hv["worms"]) <= 1 and v["worms"] >= 10 and not v["dup"] for v in cvs), [v["worms"] for v in cvs])
    check("worm bodies are rebuilt on the client that is drawing (front tab)", cvs[2]["bodies"])
    check("all clients see 4 players", all(v["players"] == 4 for v in cvs))
    check("item counts within a few of the host's (live game, so not exact)", all(abs(v["items"] - hv["items"]) <= 12 for v in cvs), ([v["items"] for v in cvs], hv["items"]))
    # exact item check: compare ids against the host at the same instant, allowing only what is in flight
    ids = lambda t: set(json.loads(t.eval("JSON.stringify([...HW.App.G.items.keys()])")))
    hi = ids(h); ci = ids(cl[2]); d = len(hi ^ ci)
    check("item ids match the host (difference only what is in flight)", d <= 30, d)
    # --- 5th player ---
    x = newtab(b); x.goto(URL, 1.2); x.eval(hook); x.eval("HW.App.startJoin(0,'%s')" % code)
    wait(tabs + [x], x, "HW.App.mode==='menu'&&(window.__toasts||[]).length>0", 25)
    check("5th player is told the room is full", "ROOM IS FULL" in toasts(x) and h.eval("HW.App.sim.S.players.length") == 4, toasts(x))
    check("5th player is back on the title screen, offline", x.eval("HW.App.screen") == "title" and x.eval("HW.Net.role") is None)
    # --- error messages (same tab) ---
    x.eval("window.__toasts=[];HW.App.startJoin(0,'AB')"); wait([x], x, "(window.__toasts||[]).length>0", 5)
    check("short code rejected at once", "4 LETTERS" in toasts(x), toasts(x))
    bad = "QQZX" if code != "QQZX" else "QQZY"
    x.eval("window.__toasts=[];HW.App.startJoin(0,'%s')" % bad); t0 = time.time(); wait([x], x, "(window.__toasts||[]).length>0", 30)
    check("unknown room: clear message", ("ROOM %s NOT FOUND" % bad) in toasts(x) or "COULD NOT REACH ROOM" in toasts(x), toasts(x) + " after %.1fs" % (time.time() - t0))
    # --- input round trip from the foreground client (rAF only runs in the front tab) ---
    c = cl[2]; c.call("Page.bringToFront"); both(tabs, 1.0)
    me = lambda: json.loads(c.eval("(()=>{const m=HW.App.locals[0].me;return JSON.stringify(m?{id:m.id,ch:m.ch,x:m.x,y:m.y,ang:m.ang,ammo:m.ammo}:null)})()"))
    hostworm = lambda wid: json.loads(h.eval("(()=>{const w=HW.App.sim.S.worms.find(w=>w.id===%d);return JSON.stringify(w?{x:w.x,y:w.y,ang:w.ang,ammo:w.ammo,abil:w.abil,pid:w.pid}:null)})()" % wid))
    keep = "(()=>{const p=HW.App.sim.S.players.find(p=>p.pid===%d);if(p&&p.worm&&p.worm.alive){p.worm.shield=30;return p.worm.id}return 0})()" % pids[2]
    wait(tabs, h, keep, 10); wid = h.eval(keep); ammo0 = hostworm(wid)["ammo"]
    h.eval("window.__keep=setInterval(()=>{const w=HW.App.sim&&HW.App.sim.S.worms.find(w=>w.id===%d);if(w)w.shield=30},20)" % wid)  # bots must not eat it mid-test
    both(tabs, 0.8); m0 = me()
    check("client sees its own worm (the one the host gave it)", m0 is not None and m0["id"] == wid and m0["ch"] == 4, (m0, wid))
    c.touch("touchStart", [(1, 150, 200)]); c.touch("touchMove", [(1, 150, 250)]); both(tabs, 1.6)
    c.touch("touchStart", [(1, 150, 250), (2, 650, 250)]); c.touch("touchMove", [(1, 150, 250), (2, 700, 250)]); both(tabs, 1.6)
    hw = hostworm(wid); m1 = me(); print(" after input: host", hw, "client", m1)
    check("client steering reaches the host (heading down)", hw is not None and math.sin(hw["ang"]) > 0.97, hw and hw["ang"])
    check("client firing reaches the host (ammo used)", hw is not None and hw["ammo"] < ammo0, (ammo0, hw and hw["ammo"]))
    check("client's picture of itself follows the host", m1 is not None and abs(m1["x"] - hw["x"]) < 60 and abs(m1["y"] - hw["y"]) < 60 and m1["ammo"] <= hw["ammo"] + 1, (m1, hw))
    c.touch("touchEnd", []); both(tabs, 0.5)
    st = json.loads(c.eval("JSON.stringify({rtt:HW.Net.stats.rtt,delay:Math.round(HW.App.G.delay*1000),gap:Math.round(HW.App.G.gap*1000),late:Math.round(HW.App.G.late*1000)})")); print(" client link:", st)
    check("client measures ping and snapshot rhythm", st["gap"] > 30 and st["gap"] < 120 and st["delay"] >= 40 and st["delay"] <= 250, st)
    c.shot(SP + "/o_client.png")
    # --- bandwidth on the real link ---
    s0 = json.loads(h.eval("JSON.stringify(HW.Net.stats)")); t0 = time.time(); both(tabs, 5.0); s1 = json.loads(h.eval("JSON.stringify(HW.Net.stats)")); dt = time.time() - t0
    per = (s1["out"] - s0["out"]) / 3 / dt / 1000; snap = (s1["snapB"] - s0["snapB"]) / max(1, s1["snapN"] - s0["snapN"])
    print(" real link: %.2f KB/s per client, %.0f bytes/snapshot, %.1f snapshots/s per client, biggest message %d, oversize %d, skipped %d" % (per, snap, (s1["snapN"] - s0["snapN"]) / 3 / dt, s1["msgMax"], s1["over"], s1["skip"]))
    check("host keeps sending ~20 snapshots/s to each client (hidden host tab uses the worker timer)", (s1["snapN"] - s0["snapN"]) / 3 / dt > 12, (s1["snapN"] - s0["snapN"]) / 3 / dt)
    check("no oversize or skipped snapshots on the real link", s1["over"] == 0 and s1["msgMax"] < 15000, s1)
    rate = (s1["inN"] - s0["inN"]) / dt
    check("idle clients send little (unchanged input 5/s + keep-alive)", rate < 14, "%.1f messages/s from 3 clients" % rate)
    # --- signalling server lost after the room is up ---
    c.eval("HW.Net.peer.disconnect()"); h.eval("HW.Net.peer.disconnect()"); both(tabs, 0.4)
    n0 = c.eval("HW.App.G.snapN"); both(tabs, 3.0); n1 = c.eval("HW.App.G.snapN")
    check("losing signalling does not drop a connected client", c.eval("HW.App.mode") == "play" and n1 > n0 + 20 and h.eval("HW.App.sim.S.players.length") == 4, (n0, n1))
    ok = wait(tabs, h, "HW.Net.online===true&&HW.Net.peer.open", 15)
    check("host reconnects to signalling with the same code", ok and h.eval("HW.Net.code") == code)
    # --- client leaves: seat is freed at once and a new player can join through the reconnected signalling ---
    cl[0].eval("HW.App.quit()"); ok = wait(tabs, h, "HW.App.sim.S.players.length===3", 6)
    check("client quitting frees its seat quickly", ok, h.eval("HW.App.sim.S.players.length"))
    check("host is told a friend left", "A FRIEND LEFT" in toasts(h))
    # stale session: start joining, cancel straight away, start a solo game -> the old join must not disturb it
    x.eval("window.__toasts=[];HW.App.startJoin(0,'%s');HW.App.quit();HW.App.startLocal([1])" % code); both(tabs + [x], 6)
    check("cancelled join does not leak into the next game", x.eval("HW.App.mode") == "play" and x.eval("HW.Net.role") is None and x.eval("!!HW.App.sim") and h.eval("HW.App.sim.S.players.length") == 3, (x.eval("HW.App.mode"), toasts(x)))
    x.eval("HW.App.quit()")
    x.eval("window.__toasts=[];HW.App.startJoin(3,'%s')" % code); ok = wait(tabs + [x], x, "HW.App.mode==='play'", 25)
    check("new player can join after the signalling reconnect (into the freed seat)", ok and h.eval("HW.App.sim.S.players.length") == 4 and x.eval("HW.App.myPid") == pids[0], (toasts(x), x.eval("HW.App.myPid")))
    # quit and join again from the same tab: fresh state
    cl[0].eval("window.__toasts=[];HW.App.startJoin(1,'%s')" % code); wait(tabs + [x], cl[0], "(window.__toasts||[]).length>0", 25)
    check("room is full again for the returning player", "ROOM IS FULL" in toasts(cl[0]), toasts(cl[0]))
    # --- a client tab closing without saying goodbye (navigation away) ---
    cl[1].call("Page.navigate", {"url": "about:blank"}); ok = wait([h, cl[2], x], h, "HW.App.sim.S.players.length===3", 8)
    check("client tab closing frees its seat quickly", ok, h.eval("HW.App.sim.S.players.length"))
    # --- death and respawn on the foreground client ---
    h.eval("clearInterval(window.__keep);(()=>{const s=HW.App.sim,w=s.S.worms.find(w=>w.id===%d);if(w){w.shield=0;s.kill(w,null,'shot')}})()" % wid); both([h, c, x], 1.0)
    check("client sees its death", me() is None and c.eval("HW.App.locals[0].player.wormId") == 0); c.shot(SP + "/o_dead.png")
    ok = wait([h, c, x], c, "!!HW.App.locals[0].me", 8)
    check("client respawns", ok)
    # --- host leaves ---
    h.eval("HW.App.quit()"); ok = wait([h, c, x], c, "HW.App.mode==='menu'", 8) and wait([h, c, x], x, "HW.App.mode==='menu'", 8)
    check("host quitting sends every client back to the menu with a reason", ok and "HOST LEFT THE GAME" in toasts(c) and "HOST LEFT THE GAME" in toasts(x), (toasts(c), toasts(x)))
    check("clients are fully offline afterwards", c.eval("HW.Net.role") is None and c.eval("HW.Net.conn") is None and c.eval("HW.App.screen") == "title")
    h.shot(SP + "/o_host.png")
    # --- a second room on another device: old clients move over with clean state; then that host's tab just goes away ---
    x.eval("window.__toasts=[];HW.App.startHost(1)"); wait([x], x, "!!HW.Net.code", 25); code2 = x.eval("HW.Net.code")
    c.eval("window.__toasts=[];HW.App.startJoin(2,'%s')" % code2); ok = wait([x, c], c, "HW.App.mode==='play'", 25); both([x, c], 1.5)
    st = json.loads(c.eval("JSON.stringify({pid:HW.App.myPid,players:HW.App.G.players.length,code:HW.Net.code,worms:HW.App.G.worms.length,me:!!HW.App.locals[0].me,seq:HW.App.locals[0].abilSeq})")); print(" second room:", code2, st)
    check("client moves to another room with fresh state", ok and code2 != code and st["pid"] == 1 and st["players"] == 2 and st["code"] == code2 and st["worms"] >= 10 and st["me"] and x.eval("HW.App.sim.S.players.length") == 2, st)
    x.call("Page.navigate", {"url": "about:blank"}); ok = wait([c], c, "HW.App.mode==='menu'", 12)
    check("host tab closing sends the client back to the menu quickly", ok and "HOST LEFT THE GAME" in toasts(c), toasts(c))
    # --- the PeerJS library itself: first CDN blocked -> second one is used; both blocked -> a clear message, game goes on offline ---
    y = newtab(b); y.call("Network.setBlockedURLs", {"urls": ["*unpkg.com*"]}); y.goto(URL, 1.2); y.eval(hook)
    y.eval("HW.App.startJoin(0,'%s')" % bad); wait([y], y, "(window.__toasts||[]).length>0", 40)
    check("first CDN blocked: library loads from the second (integrity-checked) and signalling works", y.eval("!!window.Peer") and "NOT FOUND" in toasts(y), toasts(y))
    z = newtab(b); z.call("Network.setBlockedURLs", {"urls": ["*unpkg.com*", "*jsdelivr.net*"]}); z.goto(URL, 1.2); z.eval(hook)
    z.eval("HW.App.startHost(0)"); wait([z], z, "(window.__toasts||[]).some(s=>s.indexOf('LIBRARY')>=0)", 25)
    check("both CDNs blocked: host is told and keeps playing offline", "COULD NOT LOAD ONLINE LIBRARY" in toasts(z) and z.eval("HW.App.mode") == "play" and z.eval("HW.Net.role") is None, toasts(z))
    for name, t in (("host", h), ("client0", cl[0]), ("client2", cl[2])):
        check("no page errors: " + name, not t.errors, t.errors[:3])

# A stand-in for the PeerJS library: same calls and events as far as net.js uses them, messages carried between tabs
# of this browser by a BroadcastChannel (as JSON text, like the real 'json' serialisation), each held back LAT ms.
FAKE_PEER = r"""
window.Peer = (() => {
  const LAT = window.__lat || 0, bc = new BroadcastChannel('hw-fake-peer'), peers = new Map();
  bc.onmessage = ev => { const m = ev.data, p = peers.get(m.to); if (p) p._in(m); };
  const emitter = o => { o.h = {}; o.on = (e, f) => { (o.h[e] = o.h[e] || []).push(f); return o; }; o.fire = (e, a) => { for (const f of o.h[e] || []) f(a); }; return o; };
  function mkConn(peer, remote, cid) {
    const c = emitter({ serialization: 'json', open: false, peer: remote, dataChannel: { bufferedAmount: 0 },
      send(d) { if (c.open) bc.postMessage({ to: remote, from: peer.id, cid, k: 'd', d: JSON.stringify(d), at: Date.now() }); },
      close() { if (!c.open) return; c.open = false; bc.postMessage({ to: remote, from: peer.id, cid, k: 'x' }); peer.conns.delete(cid); c.fire('close'); } });
    peer.conns.set(cid, c); return c;
  }
  return class {
    constructor(id) { emitter(this); this.id = id || 'anon-' + Math.random().toString(36).slice(2); this.open = false; this.disconnected = false; this.destroyed = false; this.conns = new Map(); peers.set(this.id, this);
      setTimeout(() => { if (!this.destroyed) { this.open = true; this.fire('open', this.id); } }, 20); }
    connect(to) { const cid = this.id + '>' + Math.random().toString(36).slice(2), c = mkConn(this, to, cid); bc.postMessage({ to, from: this.id, cid, k: 'c' }); c.to = setTimeout(() => { if (!c.open) this.fire('error', { type: 'peer-unavailable' }); }, 3000); return c; }
    _in(m) {
      if (this.destroyed) return;
      if (m.k === 'c') { const c = mkConn(this, m.from, m.cid); c.open = true; bc.postMessage({ to: m.from, from: this.id, cid: m.cid, k: 'a' }); this.fire('connection', c); setTimeout(() => c.fire('open'), 0); return; }
      const c = this.conns.get(m.cid); if (!c) return;
      if (m.k === 'a') { clearTimeout(c.to); c.open = true; c.fire('open'); }
      else if (m.k === 'd') setTimeout(() => { if (c.open) c.fire('data', JSON.parse(m.d)); }, Math.max(0, LAT - (Date.now() - m.at)));
      else if (m.k === 'x') { c.open = false; this.conns.delete(m.cid); c.fire('close'); }
    }
    disconnect() { } reconnect() { }
    destroy() { this.destroyed = true; for (const c of Array.from(this.conns.values())) c.close(); peers.delete(this.id); }
  };
})();
"""

def part_c(b, LAT=100):
    print("== Part C: the real game in two tabs, joined without the internet (%d ms each way) ==" % LAT)
    hook = "HW.App.toast=(o=>s=>{(window.__toasts=window.__toasts||[]).push(s);o(s)})(HW.App.toast)"
    J = lambda t, js: json.loads(t.eval("JSON.stringify(%s)" % js))
    def both(tabs, secs, step=0.1):
        end = time.time() + secs
        while time.time() < end:
            for t in tabs: t.pump(step / len(tabs))
    def wait(tabs, t, js, secs=15):
        end = time.time() + secs
        while time.time() < end:
            both(tabs, 0.2)
            if t.eval(js): return True
        return False
    h = newtab(b); h.goto(URL, 1.2); h.eval(hook); h.eval("window.__lat=%d;" % LAT + FAKE_PEER + ";0"); h.eval("HW.App.startHost(0)")
    wait([h], h, "!!HW.Net.code", 10); code = h.eval("HW.Net.code")
    check("host opens a room (stand-in transport)", bool(code) and h.eval("HW.Net.role") == "host", code)
    c = newtab(b); c.goto(URL, 1.2); c.eval(hook); c.eval("window.__lat=%d;" % LAT + FAKE_PEER + ";0"); c.eval("HW.App.startJoin(1,'%s')" % code); c.call("Page.bringToFront")
    tabs = [h, c]
    ok = wait(tabs, c, "HW.App.mode==='play'&&!!HW.App.locals[0].me", 20)
    check("client joins and gets its worm", ok and h.eval("HW.App.sim.S.players.length") == 2 and c.eval("HW.App.myPid") == 1, (c.eval("HW.App.mode"), c.eval("JSON.stringify(window.__toasts||[])")))
    if not ok: print(h.log[-5:], c.log[-5:]); return
    pid = c.eval("HW.App.myPid")
    # the client's worm is kept safe on the host for the whole test (bots must not end it)
    h.eval("window.__keep=setInterval(()=>{const S=HW.App.sim&&HW.App.sim.S,p=S&&S.players.find(p=>p.pid===%d);if(p&&p.worm&&p.worm.alive){p.worm.shield=30;p.worm.stuck=0;p.worm.slow=0;p.worm.trip=0}},20)" % pid)
    t0 = h.eval("HW.App.sim.S.t"); both(tabs, 1.0); t1 = h.eval("HW.App.sim.S.t")
    check("the host keeps simulating while its tab is in the background", t1 - t0 > 0.7, t1 - t0)
    # --- prediction is running in the real loop ---
    both(tabs, 1.5)
    p0 = c.eval("HW.Net.stats.pred"); both(tabs, 1.0); p1 = c.eval("HW.Net.stats.pred")
    st = J(c, "{rtt:HW.Net.stats.rtt,pr:!!HW.App.G.pr,same:!!HW.App.G.pr&&HW.App.G.pr.id===HW.App.locals[0].me.id,myId:HW.App.G.myId,lead:HW.App.G.rtt,hostPred:0}")
    print(" client: predicted frames in 1 s:", p1 - p0, st)
    check("the client predicts its own worm every frame (main.js hands over G.myId and G.myInp)", p1 - p0 > 25 and st["pr"] and st["same"] and st["myId"] > 0, (p1 - p0, st))
    check("the client measures the round trip (2 x %d ms)" % LAT, 2 * LAT - 15 <= st["rtt"] <= 2 * LAT + 90, st["rtt"])
    check("the host tab predicts nothing", h.eval("HW.Net.stats.pred") == 0 and not h.eval("'pr' in HW.App.G"))
    # --- a key press: the drawn head turns at once, the host's answer arrives a round trip later ---
    c.eval("""window.__s=[];window.__kd=0;addEventListener('keydown',e=>{if(e.code==='KeyW'&&!window.__kd)window.__kd=performance.now()},true);
      (function f(){const l=HW.App.locals[0],me=l&&l.me;if(me&&me.q.length)__s.push([performance.now(),me.ang,me.q[me.q.length-1].a,me.x,me.y]);if(__s.length>3000)__s.shift();requestAnimationFrame(f)})();0""")
    c.key("down", "KeyD", "d", 68); both(tabs, 1.6)
    hw = lambda: J(h, "(()=>{const p=HW.App.sim.S.players.find(p=>p.pid===%d),w=p&&p.worm;return w&&w.alive?{x:w.x,y:w.y,ang:w.ang,sg:w.sg,rage:w.rage,taunt:p.comp.st.taunt}:null})()" % pid)
    me = lambda: J(c, "(()=>{const m=HW.App.locals[0].me;return m?{x:m.x,y:m.y,ang:m.ang,sg:m.sg,rage:m.rage,say:m._say?m._say.s:''}:null})()")
    a = hw(); m = me(); print(" steering right: host", a, "client", m)
    check("steering reaches the host and the client's worm agrees with it", a is not None and m is not None and math.cos(a["ang"]) > 0.95 and math.cos(m["ang"]) > 0.95 and math.hypot(a["x"] - m["x"], a["y"] - m["y"]) < 70, (a, m))
    c.key("down", "KeyW", "w", 87); c.key("up", "KeyD", "d", 68); both(tabs, 1.2); c.key("up", "KeyW", "w", 87)
    r = J(c, """(()=>{const s=__s,kd=__kd,d=HW.util.angDiff;let i=s.findIndex(q=>q[0]>kd);if(i<1)return null;const a0=s[i-1][1],h0=s[i-1][2];
      const p=s.slice(i).find(q=>Math.abs(d(q[1],a0))>0.02),g=s.slice(i).find(q=>Math.abs(d(q[2],h0))>0.02);let step=0;for(let j=i;j<s.length;j++)step=Math.max(step,Math.hypot(s[j][3]-s[j-1][3],s[j][4]-s[j-1][4])/Math.max(0.004,(s[j][0]-s[j-1][0])/1000));
      return {frame:+(s[i][0]-s[i-1][0]).toFixed(1),drawn:p?Math.round(p[0]-kd):-1,host:g?Math.round(g[0]-kd):-1,speed:Math.round(step),frames:s.length-i}})()""")
    print(" key press to head turning: drawn head %s ms, host's answer %s ms (frame %s ms, round trip %d ms)" % (r and r["drawn"], r and r["host"], r and r["frame"], 2 * LAT))
    check("the drawn head turns within two frames of the key press", r is not None and 0 <= r["drawn"] <= 2 * r["frame"] + 25, r)
    check("the host's own answer only shows a round trip later (so that was prediction)", r is not None and r["host"] >= 2 * LAT - 30 and r["host"] > r["drawn"] + LAT, r)
    check("the drawn head never moves faster than the worm can (plus the slide)", r is not None and r["speed"] < HWSPEED * 1.75, r)
    # --- taunt key ---
    n0 = hw()["taunt"]; c.key("down", "KeyT", "t", 84); both(tabs, 0.15); c.key("up", "KeyT", "t", 84); both(tabs, 0.9)
    a = hw(); m = me()
    check("T on the client: one taunt on the host, speech bubble on the client's own worm", a["taunt"] == n0 + 1 and bool(m["say"]), (a, m))
    # --- power-up and special gun picked up on the host: HUD state and banner on the client ---
    give = lambda k, ty: h.eval("(()=>{const s=HW.App.sim,p=s.S.players.find(p=>p.pid===%d),w=p.worm;s.addItem('%s',%d,w.x+2,w.y,0);return 1})()" % (pid, k, ty))
    give("p", 0); both(tabs, 0.8); m = me(); ban = c.eval("(HW.App.locals[0].view.banner||{}).s||''")
    check("rampage picked up: countdown and banner on the client", m["rage"] > 5 and "RAMPAGE" in ban, (m, ban))
    give("g", 2); both(tabs, 0.8); m = me(); ban = c.eval("(HW.App.locals[0].view.banner||{}).s||''")
    check("special gun picked up: the client's worm holds it, banner names it", m["sg"] == 3 and "FLAMETHROWER" in ban, (m, ban))
    c.shot(SP + "/c_client.png")
    # --- frenzy, then the end of the match with its awards ---
    h.eval("HW.App.sim.S.match.t=HW.FRENZY.t+0.3"); both(tabs, 1.5)
    check("frenzy reaches the client (flag and banner)", c.eval("HW.App.G.match.frenzy") is True and "FRENZY" in c.eval("(HW.App.locals[0].view.banner||{}).s||''"), c.eval("(HW.App.locals[0].view.banner||{}).s||''"))
    h.eval("(()=>{const S=HW.App.sim.S;S.comps[0].st.veg=6;S.comps[1].st.taunt=7;HW.App.sim.endMatch('time')})()"); both(tabs, 1.5)
    aw = J(h, "HW.App.sim.S.match.awards"); cw = J(c, "HW.App.G.match.awards"); shown = c.eval("document.querySelectorAll('#ui .panel.c').length")
    check("match over: results screen on the client with the host's awards", c.eval("HW.App.screen") == "results" and len(aw) >= 2 and cw == aw and shown >= 2, (aw, cw, shown))
    check("no prediction while the arena is frozen: the client's worm stays put", (lambda a, b: math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < 1.0)(me(), (both(tabs, 0.5), me())[1]))
    c.shot(SP + "/c_results.png")
    h.eval("clearInterval(window.__keep);HW.App.quit()"); ok = wait(tabs, c, "HW.App.mode==='menu'", 8)
    check("host leaving sends the client back to the menu", ok and "HOST LEFT THE GAME" in c.eval("JSON.stringify(window.__toasts||[])"))
    for name, t in (("host", h), ("client", c)):
        check("no page errors: " + name, not t.errors, t.errors[:3])

HWSPEED = 110  # Chandler, px/s (the client's worm in part C)
b = Browser(profile=SP + "/prof")
try:
    if ONLY in ("", "a"):
        typ, worst, fresh = part_a(b)
        print(" bandwidth (3 clients, per client): typical %s bytes/snapshot, %s KB/s (old format %s bytes, %s KB/s); biggest message in the worst case %s bytes (old format %s), with power-ups and special guns in play %s bytes; limit 16300"
              % (typ["perSnap"], typ["kbps"], typ["oldPerSnap"], typ["oldKbps"], worst["maxMsg"], max(worst["oldMax"], worst["oldAll"]), fresh["maxMsg"]))
    if ONLY in ("", "c"): part_c(b)
    if ONLY in ("", "b"): part_b(b)
finally: b.close()
print("\n%d FAILED: %s" % (len(FAILS), FAILS) if FAILS else "\nALL PASSED")
sys.exit(1 if FAILS else 0)
