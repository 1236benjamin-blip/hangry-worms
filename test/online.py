"""Online multiplayer tests for Hangry Worms.

Part A (no network): net.js is driven through fake connections inside one page, on a virtual clock, so every
case is exact and repeatable: item / worm sync under heavy churn, worst-case message sizes, malformed input,
room full, joins in the same tick, slow clients, time-outs, ability / respawn flags, interpolation smoothness,
bandwidth.
Part B (real PeerJS cloud, needs internet): a host tab and three client tabs, a fifth player being turned away,
input round trip, leaving, signalling loss, error messages for bad codes, stale sessions.

  python3 -m http.server 8377        (in the project folder)
  HW_PORT=9413 python3 test/online.py /tmp/out [url] [a|b]
"""
import sys, time, os, json, math
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("http") else "http://127.0.0.1:8377/index.html"
ONLY = sys.argv[-1] if sys.argv[-1] in ("a", "b") else ""
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
  function mkConn(ser) {
    return { open: true, serialization: ser || 'json', dataChannel: { bufferedAmount: 0 }, h: {}, out: [], max: 0, bytes: 0, n: 0,
      on(ev, f) { this.h[ev] = f; }, send(m) { const s = JSON.stringify(m); if (s.length > this.max) this.max = s.length; this.bytes += s.length; this.n++; this.out.push(s); },
      close() { if (this.open) { this.open = false; if (this.h.close) this.h.close(); } }, recv(m) { this.h.data(m); } };
  }
  function join(X, ch, hello) {
    const conn = mkConn(), c = X.accept(conn); if (c) conn.recv(hello || { t: 'hello', ch, v: 2 });
    const k = { conn, c, G: Net.newMirror(), pid: -1, first: 0, ev: 0, other: [], zs: 0, seq: 0 }; X.cl.push(k); return k;
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
      else if (m.t === 's') { Net.applySnap(k.G, m); if (m.first) k.first++; k.ev += m.e.length; }
      else k.other.push(m);
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
    for (const k of X.cl) Net.clientUpdate(k.G, dt);
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
      if (m.ch !== w.ch || m.variant !== w.variant || m.ammo !== w.ammo || m.kills !== w.kills || m.pid !== w.pid || Math.abs(m.mass - w.mass) > (fresh ? 0.06 : 1e9) || (fresh && Math.hypot(s.x - w.x, s.y - w.y) > 0.75)) { wbad++; why = why || JSON.stringify(['core', fresh, m.ch, w.ch, m.variant, w.variant, m.ammo, w.ammo, m.kills, w.kills, m.pid, w.pid, m.mass, w.mass, s.x, w.x, s.y, w.y]); }
      else if (Math.hypot(s.x - w.x, s.y - w.y) > 24 || ['abil', 'stuck', 'slow', 'trip', 'shield'].some(t => Math.abs(Math.max(0, m[t]) - Math.max(0, w[t])) > 0.35)) { wbad++; why = why || JSON.stringify(['timer', fresh, s.x, w.x, s.y, w.y, m.abil, w.abil, m.stuck, w.stuck, m.slow, w.slow, m.trip, w.trip, m.shield, w.shield]); }
    }
    const hb = new Set(S.bullets.map(b => b.id)); let bbad = 0; for (const b of G.bullets) if (!hb.has(b.id)) bbad++;
    const hp = S.players.map(p => p.pid + ':' + (p.worm && p.worm.alive ? p.worm.id : 0)).join(), cp = G.players.map(p => p.pid + ':' + p.wormId).join();
    return { miss, extra, wrong, wbad, why, bbad, worms: hw.map(w => w.id).sort((a, b) => a - b).join() === cw.join(), dup: new Set(cw).size !== cw.length,
      zones: S.zones.map(z => z.id).join() === G.zones.map(z => z.id).join(), players: hp === cp };
  }
  let firstBad = null;
  const clean = d => { const ok = !d.miss && !d.extra && !d.wrong && !d.wbad && !d.bbad && d.worms && !d.dup && d.zones && d.players; if (!ok && !firstBad) firstBad = d; return ok; };
  const sane = X => X.sim.S.worms.every(w => fin(w.x) && fin(w.y) && fin(w.ang) && fin(w.aim) && fin(w.mass) && w.x >= 0 && w.x <= CFG.W && w.y >= 0 && w.y <= CFG.H)
    && X.sim.S.players.every(p => !p.inp || (['mx', 'my', 'ax', 'ay'].every(a => fin(p.inp[a]) && Math.abs(p.inp[a]) <= 1) && ['fire', 'boost', 'abil', 'auto'].every(a => typeof p.inp[a] === 'boolean')));
  const maxMsg = X => Math.max(0, ...X.cl.map(k => k.conn.max));
  const input = (k, mx, my, ax, ay, f, a) => k.conn.recv({ t: 'i', m: [mx, my, ax, ay], f, a: a === undefined ? k.seq : a });
  const wormOf = (X, k) => { const p = X.sim.S.players.find(p => p.pid === k.pid); return p && p.worm && p.worm.alive ? p.worm : null; };
  const playerOf = (X, k) => X.sim.S.players.find(p => p.pid === k.pid);
  const rnd = (a, b) => a + Math.random() * (b - a);

  const T = {};
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
      for (const w of S.worms) { w.mass = 3000; w.ammo = 150; w.kills = 99; w.shield = 99; w.abil = 59; w.stuck = 9; w.slow = 3; w.trip = 7; }
      for (const k of X.cl) { const w = wormOf(X, k); if (!w) continue; for (let j = 0; j < 70; j++) S.bullets.push({ id: S.nextId++, ch: 2, owner: w.id, x: w.x + rnd(-300, 300), y: w.y + rnd(-300, 300), vx: -289.6, vy: -289.6, life: 5, hit: null, pierce: 0, c: 4 }); }
      if (S.zones.length < 12) for (let j = 0; j < 12; j++) S.zones.push({ id: S.nextId++, k: j & 1, x: 1000 + j, y: 1900, r: 76, t: 9.9, owner: 5000000 }); // out of the spawn area
      for (const k of X.cl) { const w = wormOf(X, k) || { x: 950, y: 950, id: 0 }; for (let j = 0; j < 150; j++) X.sim.ev(j % 3 ? 'hit' : 'die', w.x, w.y, 5000000 + j, 5000001, 'crash', 4, 4, 3, 3, 3, 30000); }
    };
    stuff(); for (let i = 0; i < 4; i++) { tick(X); stuff(); }
    out.busyMax = maxMsg(X); out.busyOld = X.old.max;
    for (const k of X.cl) if (!clean(diff(X, k))) bad++;
    // 6 huge worms burst at once: thousands of item adds in one tick (sent as chunks)
    let n = 0; for (const w of S.worms.slice()) if (w.alive && n++ < 6) { w.shield = 0; w.mass = 3000; X.sim.kill(w, null, 'shot'); }
    out.adds6 = S.adds.length; tick(X); for (const k of X.cl) if (!clean(diff(X, k))) bad++;
    out.resyncBefore = Net.stats.resync;
    // all of them: more than the per-client queue holds -> full resync
    for (const w of S.worms.slice()) if (w.alive) { w.shield = 0; w.mass = 6000; X.sim.kill(w, null, 'shot'); }
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
      { t: 'i', m: [0, 0, 0, 0], f: 8, a: null }, { t: 'hello', ch: 3, v: 2 }, { t: 'hello' }, { t: 'k' }, { t: 'k', c: 'x' }, { t: 'k', c: 1e999 }, { t: 'zzz', m: [1] }, { t: 's', w: [[1, 2, 3]] }, { t: 'init', pid: 0 }, { t: 'it', z: 1, a: [] },
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
    for (let r = 0; r < 3; r++) { for (const w of S.worms.slice()) if (w.alive && w.isBot) { w.shield = 0; w.mass = 3000; X.sim.kill(w, null, 'shot'); } tick(X); for (let i = 0; i < 30; i++) tick(X); }
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
    const W = wormOf(X, k); const queue = []; let lastDue = 0, frames = [], truth = [], n = 0, sent = 0;
    const old = { x: W.x, y: W.y, sx: W.x, sy: W.y, tx: W.x, ty: W.y, lt: 0 }, oframes = []; // the previous interpolation, fed the same snapshots
    const step = 1 / (hostHz || 60), FR = 1 / 60; let hostAcc = 0, cx = 950, cy = 950;
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
    const W = wormOf(X, k), queue = []; let lastDue = 0, back = 0, n = 0, maxCross = 0; const prev = new Map(), lags = [];
    k.conn.out.length = 0;
    for (let f = 0; f < 60 * 8; f++) {
      vt += 1 / 60; W.shield = 99; W.ammo = 99; W.mass = 60; W.slow = 0; W.stuck = 0; input(k, Math.cos(f / 50), Math.sin(f / 50), Math.cos(f / 50), Math.sin(f / 50), 1);
      X.sim.step(1 / 60); const evs = S.events; S.events = [];
      if (Net.hostTick(X.sim, 1 / 60, evs)) { S.adds.length = 0; S.rems.length = 0; for (const m of k.conn.out) { const due = Math.max(lastDue, vt + 0.03 + rand() * jit); lastDue = due; queue.push({ due, m }); } k.conn.out.length = 0; }
      while (queue.length && queue[0].due <= vt) { const m = JSON.parse(queue.shift().m); if (m.t === 's') Net.applySnap(k.G, m); else if (m.t === 'it' || m.t === 'pt') Net.applyPart(k.G, m); }
      Net.clientUpdate(k.G, 1 / 60);
      if (f > 240) for (const b of k.G.bullets) { const p = prev.get(b.id); if (p) { n++; if ((b.x - p.x) * b.vx + (b.y - p.y) * b.vy < 0) back++; } prev.set(b.id, { x: b.x, y: b.y });
        const h = S.bullets.find(q => q.id === b.id); if (h) { const v = Math.hypot(h.vx, h.vy), al = ((h.x - b.x) * h.vx + (h.y - b.y) * h.vy) / v, cr = Math.abs((h.x - b.x) * h.vy - (h.y - b.y) * h.vx) / v; lags.push(al / v * 1000); if (cr > maxCross) maxCross = cr; } }
    }
    const mean = lags.reduce((a, b) => a + b, 0) / lags.length, sd = Math.sqrt(lags.reduce((a, b) => a + (b - mean) * (b - mean), 0) / lags.length);
    return { samples: n, back, lagMs: +mean.toFixed(1), lagSd: +sd.toFixed(1), lagMin: +Math.min(...lags).toFixed(1), lagMax: +Math.max(...lags).toFixed(1), maxCross: +maxCross.toFixed(2) };
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
    check("no page errors in part A", not t.errors, t.errors[:3])
    return typ, worst

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

b = Browser(profile=SP + "/prof")
try:
    if ONLY != "b":
        typ, worst = part_a(b)
        print(" bandwidth (3 clients, per client): typical %s bytes/snapshot, %s KB/s (old format %s bytes, %s KB/s); biggest message in the worst case %s bytes (old format %s)"
              % (typ["perSnap"], typ["kbps"], typ["oldPerSnap"], typ["oldKbps"], worst["maxMsg"], max(worst["oldMax"], worst["oldAll"])))
    if ONLY != "a": part_b(b)
finally: b.close()
print("\n%d FAILED: %s" % (len(FAILS), FAILS) if FAILS else "\nALL PASSED")
sys.exit(1 if FAILS else 0)
