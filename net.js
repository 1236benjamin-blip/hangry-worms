// Hangry Worms - online rooms over PeerJS (free peer-to-peer, host is authoritative)
//
// Wire format (JSON, one PeerJS data channel per client, reliable + ordered):
//   client -> host  {t:'hello',ch,v}   {t:'i',m:[mx,my,ax,ay],f:flags,a:abilSeq}   {t:'k',c:clientMs} keep-alive/ping   {t:'bye'}
//   host -> client  {t:'init',pid}  {t:'it',z?,a?,r?} item chunks (z = forget all items first)  {t:'pt',id,p} body points
//                   {t:'s',T,w,b?,z?,a?,r?,e?,p?,first?} snapshot   {t:'k',c} pong   {t:'full'}  {t:'x',r:reason}  {t:'bye'}
//   Snapshot rows: w = worms: 17 numbers (everything), 7 numbers (movement only) or a bare id (alive, nothing new);
//   b = bullets near that client: 7 numbers the first time, then a bare id; z / p (zones, players) only when they change;
//   a / r = items added / removed since that client's last snapshot; e = events near that client.
// PeerJS refuses JSON messages of 16300 bytes or more and raises an error on the connection, so every message is kept far below that.
'use strict';
(function (HW) {
  const CFG = HW.CFG, CHARS = HW.CHARS, { angDiff, clamp } = HW.util;
  const PREFIX = 'hangryworms-v1-', VER = 3, ALPHA = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
  const LIBS = ['https://unpkg.com/peerjs@1.5.4/dist/peerjs.min.js', 'https://cdn.jsdelivr.net/npm/peerjs@1.5.4/dist/peerjs.min.js'];
  const SRI = 'sha384-nlUQ8ZqCbvStErob+biJNzSgltf6urV3VGqhfIfzhmg9RXmpeRm76ELw0pYnKlTR'; // same file on both CDNs
  const LIMIT = 15000;        // hard cap for one message (bytes; everything we send is ASCII)
  const VIEW = 500, FAR = 640; // a client only gets bullets / effects this near its worm; worms beyond FAR update at half rate
  const CONGESTED = 64000;    // bytes waiting in a client's channel before the host stops adding to it
  const Net = HW.Net = { role: null, peer: null, conns: [], lobby: [], conn: null, code: '', acc: 0, evbuf: [], SNAP: 1 / 20, gen: 0, online: false, tick: 0, wst: new Map(), zsig: '', psig: '', stats: null };
  Net.now = () => performance.now() / 1000; // seconds; tests replace this
  Net.LAG = 0.5; // how far behind the newest snapshot worms are drawn, in snapshot intervals (plus an allowance for jitter)
  const toast = s => { try { if (HW.App && HW.App.toast) HW.App.toast(s); } catch (e) { } };
  const num = v => typeof v === 'number' && v === v && v !== Infinity && v !== -Infinity ? v : 0;
  const unit = v => { v = num(v); return v < -1 ? -1 : v > 1 ? 1 : v; };
  const r1 = v => Math.round(v * 10) / 10;
  function resetStats() { Net.stats = { out: 0, outN: 0, snapB: 0, snapN: 0, snapMax: 0, msgMax: 0, over: 0, skip: 0, resync: 0, inN: 0, rtt: 0 }; }
  resetStats();

  let libCbs = null;
  function loadLib(cb) {
    if (window.Peer) return cb(true);
    if (libCbs) { libCbs.push(cb); return; }
    libCbs = [cb]; let i = 0;
    const done = ok => { const l = libCbs; libCbs = null; for (const f of l) f(ok); };
    (function next() {
      if (window.Peer) return done(true);
      if (i >= LIBS.length) return done(false);
      const s = document.createElement('script'); let over = false;
      const fin = ok => { if (over) return; over = true; clearTimeout(to); if (ok && window.Peer) done(true); else { try { s.remove(); } catch (e) { } next(); } };
      const to = setTimeout(() => fin(false), 9000);
      s.src = LIBS[i++]; s.crossOrigin = 'anonymous'; s.integrity = SRI; s.onload = () => fin(true); s.onerror = () => fin(false); document.head.appendChild(s);
    })();
  }
  const newCode = () => { let c = ''; for (let i = 0; i < 4; i++) c += ALPHA[(Math.random() * ALPHA.length) | 0]; return c; };

  // Leaves the room. Every callback of the old session is ignored from here on (Net.gen), so a slow
  // answer from a room you already left can never touch the next game.
  Net.close = function () {
    const peer = Net.peer, fast = Net.leaving; Net.gen++;
    try {
      if (Net.role === 'host') for (const c of Net.conns) { c.dead = true; if (c.conn.open) c.conn.send({ t: 'bye' }); }
      else if (Net.conn && Net.conn.open) Net.conn.send({ t: 'bye' });
    } catch (e) { }
    clearInterval(Net.timer); clearTimeout(Net.reT); Net.timer = 0; Net.reT = 0; Net.reN = 0; Net.reTold = false;
    Net.peer = null; Net.conns = []; Net.lobby = []; Net.conn = null; Net.role = null; Net.code = ''; Net.evbuf = []; Net.online = false;
    Net.fail = null; Net.getSim = null; Net.wst = new Map(); Net.zsig = Net.psig = ''; Net.inKey = ''; Net.inT = 0; Net.hkT = 0;
    // give the goodbye a moment to leave before tearing the connection down
    if (peer) { const kill = () => { try { peer.destroy(); } catch (e) { } }; if (fast) kill(); else setTimeout(kill, 200); }
  };

  // ---------- host ----------
  // cb(err, code); getSim() returns the live sim (or null when no game is running)
  Net.host = function (getSim, cb) {
    Net.close(); resetStats(); const gen = Net.gen;
    loadLib(ok => {
      if (gen !== Net.gen) return;
      if (!ok) return cb('COULD NOT LOAD ONLINE LIBRARY');
      let tries = 0, done = false;
      (function attempt() {
        const code = newCode(); let peer;
        try { peer = new window.Peer(PREFIX + code); } catch (e) { done = true; return cb('BROWSER CANNOT PLAY ONLINE'); }
        const scrap = () => { try { peer.destroy(); } catch (e) { } };
        const to = setTimeout(() => { if (done) return; done = true; scrap(); if (gen === Net.gen) cb('ONLINE SERVER DID NOT ANSWER'); }, 12000);
        peer.on('open', () => {
          if (gen !== Net.gen) return scrap();
          Net.online = true; Net.reN = 0;
          if (done) { if (Net.reTold) { Net.reTold = false; toast('ROOM CODE WORKS AGAIN'); } return; } // back on the signalling server
          done = true; clearTimeout(to); Net.peer = peer; Net.role = 'host'; Net.code = code; Net.getSim = getSim; cb(null, code);
        });
        peer.on('error', err => {
          // once the room is up, signalling trouble must not hurt the players already connected
          if (done) return; clearTimeout(to); scrap();
          if (gen !== Net.gen) { done = true; return; }
          if (err && err.type === 'unavailable-id' && ++tries < 5) return attempt();
          done = true; cb(err && err.type === 'browser-incompatible' ? 'BROWSER CANNOT PLAY ONLINE' : 'ONLINE UNAVAILABLE');
        });
        peer.on('disconnected', () => { if (Net.peer === peer) { Net.online = false; reconnectSoon(peer); } });
        peer.on('connection', conn => { if (Net.peer === peer) accept(conn); else { try { conn.close(); } catch (e) { } } });
      })();
    });
  };
  // The signalling server is only needed for new players to find the room. If it drops, keep trying
  // (1s, 2s, 4s ... 30s) with the same room code; players already in are not affected.
  function reconnectSoon(peer) {
    if (Net.reT) return;
    const wait = Math.min(30, 1 << Math.min(5, Net.reN || 0)) * (750 + Math.random() * 500); Net.reN = (Net.reN || 0) + 1;
    Net.reT = setTimeout(() => {
      Net.reT = 0; if (Net.peer !== peer || peer.destroyed) return;
      if (Net.reN > 3 && !Net.reTold) { Net.reTold = true; toast('ROOM CODE OFFLINE - RETRYING'); }
      Net.reAt = Net.now();
      try { if (peer.disconnected) peer.reconnect(); } catch (e) { }
    }, wait);
  }
  function accept(conn) {
    if (conn.serialization !== 'json' || Net.lobby.length >= 8) { try { conn.close(); } catch (e) { } return null; }
    const now = Net.now();
    const c = { conn, gen: Net.gen, player: null, pending: false, dead: false, full: true, idle: false, seq: 0, born: now, last: now, lastIn: now, lastK: 0, qa: [], qr: [], bk: new Set(), ix: CFG.W / 2, iy: CFG.H / 2, wid: 0 };
    Net.lobby.push(c);
    conn.on('data', m => { try { hostMsg(c, m); } catch (e) { } });
    conn.on('close', () => drop(c));
    conn.on('error', e => { const t = e && e.type; if (t !== 'not-open-yet' && t !== 'message-too-big') drop(c); });
    return c;
  }
  // forget a client; `why` is shown on their screen
  function drop(c, why) {
    if (c.dead) return; c.dead = true;
    let i = Net.conns.indexOf(c); if (i >= 0) Net.conns.splice(i, 1);
    i = Net.lobby.indexOf(c); if (i >= 0) Net.lobby.splice(i, 1);
    if (c.player && c.gen === Net.gen) {
      const sim = Net.getSim && Net.getSim();
      if (sim && sim.S.players.indexOf(c.player) >= 0) { sim.removePlayer(c.player); toast('A FRIEND LEFT'); }
    }
    c.player = null;
    const conn = c.conn, shut = () => { try { conn.close(); } catch (e) { } };
    if (why && conn.open) { try { conn.send(why === 'ROOM IS FULL' ? { t: 'full' } : { t: 'x', r: why }); } catch (e) { } setTimeout(shut, 500); } else shut();
  }
  // Everything a client sends is checked here: wrong types are ignored and numbers are clamped,
  // so a broken or hostile client cannot put bad values into the simulation.
  function hostMsg(c, m) {
    if (c.dead || c.gen !== Net.gen || !m || typeof m !== 'object') return;
    const sim = Net.getSim && Net.getSim(); if (!sim) return;
    const now = Net.now(); c.last = now; Net.stats.inN++;
    if (m.t === 'i') {
      const p = c.player; if (!p || !Array.isArray(m.m)) return;
      const I = p.inp, f = m.f | 0, alive = !!(p.worm && p.worm.alive);
      I.mx = unit(m.m[0]); I.my = unit(m.m[1]); I.ax = unit(m.m[2]); I.ay = unit(m.m[3]);
      I.fire = !!(f & 1); I.boost = !!(f & 2); I.auto = !!(f & 4); c.lastIn = now; c.idle = false;
      // the ability counter only ever goes up; a press while dead is used up, not saved for the next life
      if (Number.isSafeInteger(m.a) && m.a > c.seq) { c.seq = m.a; if (alive) { I.abil = true; p.worm.inp.abil = true; } }
      if ((f & 8) && !alive) p.wantSpawn = true;
    } else if (m.t === 'hello') {
      if (c.player) return;
      if (m.v !== VER) return drop(c, 'OLD VERSION - RELOAD THE GAME');
      if (sim.S.players.length >= CFG.MAX_PLAYERS) return drop(c, 'ROOM IS FULL');
      const i = Net.lobby.indexOf(c); if (i >= 0) Net.lobby.splice(i, 1);
      c.player = sim.addPlayer(clamp(m.ch | 0, 0, CHARS.length - 1), c.conn);
      c.player.inp = { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false };
      c.pending = true; Net.conns.push(c); toast('A FRIEND JOINED!');
    } else if (m.t === 'k') {
      if (now - c.lastK > 0.3 && c.conn.open) { c.lastK = now; c.conn.send({ t: 'k', c: num(m.c) }); }
    } else if (m.t === 'bye') drop(c);
  }
  // once a second: drop clients that have been silent for 30 s (a crashed tab, a sleeping phone), stop the worms of
  // clients whose input stopped (hidden tab), keep the signalling connection alive
  function housekeep(now) {
    const slept = Net.hkT && now - Net.hkT > 5; Net.hkT = now; // the host itself was asleep: nobody else is late
    for (const c of Net.conns.concat(Net.lobby)) {
      if (slept) { c.last = c.lastIn = c.born = now; continue; }
      if (!c.player) { if (now - c.born > 10) drop(c); continue; }
      if (now - c.last > 30) { drop(c, 'TIMED OUT'); continue; }
      if (now - c.lastIn > 1.5 && !c.idle) { c.idle = true; const I = c.player.inp; I.mx = I.my = I.ax = I.ay = 0; I.fire = I.boost = I.abil = false; }
    }
    const peer = Net.peer;
    if (peer && !peer.destroyed) {
      Net.online = !!peer.open;
      if (!peer.open) { if (peer.disconnected) reconnectSoon(peer); else if (now - (Net.reAt || 0) > 20) { Net.reAt = now; try { peer.disconnect(); } catch (e) { } } }
    }
  }

  const itemRow = it => [it.id, it.k, it.type, Math.round(it.x), Math.round(it.y), it.v];
  const tenths = v => Math.ceil(Math.max(0, v) * 10);
  const flags = w => (w.boosting ? 1 : 0) | (w.isBot ? 2 : 0);
  const fullRow = w => [w.id, w.ch, w.variant, r1(w.x), r1(w.y), Math.round(w.ang * 100), Math.round(w.aim * 100), Math.round(w.mass * 10), flags(w), w.ammo, tenths(w.abil), tenths(w.stuck), tenths(w.slow), tenths(w.trip), w.kills, w.pid, tenths(w.shield)];
  const TIMERS = ['abil', 'stuck', 'slow', 'trip', 'shield'];
  // has anything changed that a client cannot work out for itself (timers just count down)?
  function stale(o, w, t) {
    if (o.ammo !== w.ammo || o.kills !== w.kills || o.variant !== w.variant) return true;
    for (const k of TIMERS) if (Math.abs(Math.max(0, o[k] - (t - o.t)) - Math.max(0, w[k])) > 0.12) return true;
    return false;
  }
  function send(c, m) {
    let s = JSON.stringify(m);
    if (s.length > LIMIT && m.t === 's') {
      // cannot happen with the caps in build(); if it ever does, shed the least important parts instead of losing the client
      Net.stats.over++; delete m.e; if (m.b && m.b.length > 40) m.b.length = 40;
      if (m.a || m.r) { send(c, { t: 'it', a: m.a || [], r: m.r || [] }); delete m.a; delete m.r; }
      s = JSON.stringify(m);
    }
    if (s.length > LIMIT) { Net.stats.over++; c.pending = true; return false; } // dropped: resend the whole arena next tick
    c.conn.send(m);
    const st = Net.stats; st.out += s.length; st.outN++; if (s.length > st.msgMax) st.msgMax = s.length;
    if (m.t === 's' && !m.first) { st.snapB += s.length; st.snapN++; if (s.length > st.snapMax) st.snapMax = s.length; }
    return true;
  }
  // one client's snapshot
  function build(c, S, ctx, all) {
    const m = { t: 's', T: ctx.T, w: [] }, full = all || c.full, N = ctx.N, ix = c.ix, iy = c.iy;
    for (const L of ctx.live) {
      const w = L.w;
      if (full || L.full) { m.w.push(L.F || (L.F = fullRow(w))); continue; }
      if (Math.abs(w.x - ix) <= FAR && Math.abs(w.y - iy) <= FAR) m.w.push(L.n || (L.n = [w.id, r1(w.x), r1(w.y), Math.round(w.ang * 100), Math.round(w.aim * 100), Math.round(w.mass * 10), flags(w)]));
      else if ((N + w.id) & 1) m.w.push(w.id);
      else m.w.push(L.f || (L.f = [w.id, Math.round(w.x), Math.round(w.y), Math.round(w.ang * 100), Math.round(w.aim * 100), Math.round(w.mass * 10), flags(w)]));
    }
    const bk = new Set(); let b = null;
    for (const q of S.bullets) {
      if (Math.abs(q.x - ix) > VIEW || Math.abs(q.y - iy) > VIEW) continue;
      if (bk.size >= 90) break;
      // bullets fly straight, so after the first sighting an id is enough (with a position refresh now and then)
      (b || (b = [])).push(!full && c.bk.has(q.id) && (N + q.id) % 8 ? q.id : [q.id, q.ch, r1(q.x), r1(q.y), Math.round(q.vx), Math.round(q.vy), q.c]); bk.add(q.id);
    }
    c.bk = bk; if (b) m.b = b;
    if (full || ctx.zNew) m.z = S.zones.map(z => [z.id, z.k, Math.round(z.x), Math.round(z.y), z.r, r1(z.t), z.owner]);
    if (full || ctx.pNew) m.c = [Math.ceil(S.match.t), S.match.over ? 1 : 0, S.match.n, S.match.reason || '', r1(Math.max(0, (S.autoNext || 0) - S.match.overT)), S.comps.map(c => [c.cid, c.pid, c.ch, c.variant, c.kills, c.score, c.lives, c.out ? 1 : 0])];
    if (full || ctx.pNew) m.p = S.players.map(p => [p.pid, p.worm && p.worm.alive ? p.worm.id : 0, r1(p.deadT), p.lastKiller || '', p.lastCause || '', p.lastScore || 0, Math.round(p.best || 0), p.everSpawned ? 1 : 0]);
    if (!all) {
      // effects: deaths always (kill feed); eating / empty-gun clicks only for the worm they belong to; the rest only if nearby
      const e = [], wid = c.wid;
      for (const ev of Net.evbuf) if (ev[0] === 'die' && e.length < 24) e.push(ev);
      for (const ev of Net.evbuf) {
        const k = ev[0]; if (k === 'die') continue; if (e.length >= 40) break;
        if (k === 'eat' || k === 'dry' ? ev[3] === wid : ev[3] === wid || (k === 'shot' && ev[4] === wid) || (Math.abs(ev[1] - ix) < VIEW + 40 && Math.abs(ev[2] - iy) < VIEW + 40)) e.push(ev);
      }
      if (e.length) m.e = e;
    }
    return m;
  }
  // a newcomer (or a client that fell too far behind): who you are, the whole arena in small pieces, then a snapshot
  function sendWorld(c, S, ctx) {
    c.pending = false; c.qa = []; c.qr = []; c.bk = new Set();
    send(c, { t: 'init', pid: c.player.pid, v: VER, d: S.diff | 0 });
    let chunk = [], z = 1;
    for (const it of S.items.values()) { chunk.push(itemRow(it)); if (chunk.length >= 150) { send(c, z ? { t: 'it', z: 1, a: chunk } : { t: 'it', a: chunk }); z = 0; chunk = []; } }
    if (chunk.length || z) send(c, z ? { t: 'it', z: 1, a: chunk } : { t: 'it', a: chunk });
    for (const w of S.worms) { if (!w.alive) continue; const a = []; for (let i = 0; i < w.pts.length; i += 3) a.push(Math.round(w.pts[i].x), Math.round(w.pts[i].y)); send(c, { t: 'pt', id: w.id, p: a }); }
    const m = build(c, S, ctx, true); m.first = 1; send(c, m); c.full = false;
  }
  function sendTo(c, S, ctx) {
    const p = c.player, me = p.worm && p.worm.alive ? p.worm : null;
    if (me) { c.ix = me.x; c.iy = me.y; c.wid = me.id; } else p.inp.abil = false;
    // item changes queue up per client, so a client that has to skip snapshots still gets every one of them, in order
    if (!c.pending) {
      for (const r of ctx.adds) c.qa.push(r); for (const id of ctx.rems) c.qr.push(id);
      // too far behind to catch up change by change: send the whole arena again once the link has room
      if (c.qa.length + c.qr.length > 6000) { c.pending = true; c.qa = []; c.qr = []; Net.stats.resync++; }
    }
    if (!c.conn.open) return;
    const dc = c.conn.dataChannel;
    // this client's link is not keeping up: send nothing rather than pile up stale snapshots in memory
    if (dc && dc.bufferedAmount > CONGESTED) { Net.stats.skip++; c.full = true; return; }
    if (c.pending) return sendWorld(c, S, ctx);
    const m = build(c, S, ctx, false);
    if (c.qa.length > 80 || c.qr.length > 200) {
      // a lot at once (a huge worm burst): separate small messages, every add before any remove
      for (let i = 0; i < c.qa.length; i += 150) send(c, { t: 'it', a: c.qa.slice(i, i + 150) });
      for (let i = 0; i < c.qr.length; i += 1000) send(c, { t: 'it', r: c.qr.slice(i, i + 1000) });
    } else { if (c.qa.length) m.a = c.qa; if (c.qr.length) m.r = c.qr; }
    c.qa = []; c.qr = [];
    send(c, m); c.full = false;
  }
  // called every frame on the host; sends snapshots at 20Hz. Returns true when it has taken S.adds / S.rems (the caller clears them).
  Net.hostTick = function (sim, dt, events) {
    const S = sim.S;
    if (Net.conns.length && Net.evbuf.length < 600) for (const e of events) if (e[0] !== 'spawn') Net.evbuf.push(e);
    Net.acc += dt; if (Net.acc < Net.SNAP) return false; Net.acc = Math.min(Net.acc - Net.SNAP, Net.SNAP);
    const now = Net.now(), N = ++Net.tick;
    if (now - (Net.hkT || 0) >= 1) housekeep(now);
    if (Net.conns.length) {
      const ctx = { N, T: Math.round(S.t * 1000), adds: S.adds.map(itemRow), rems: S.rems, live: [], zNew: false, pNew: false }, wst = new Map();
      for (const w of S.worms) {
        if (!w.alive) continue;
        const o = Net.wst.get(w.id), full = !o || (N + w.id) % 40 === 0 || stale(o, w, S.t);
        wst.set(w.id, full ? { t: S.t, ammo: w.ammo, kills: w.kills, variant: w.variant, abil: w.abil, stuck: w.stuck, slow: w.slow, trip: w.trip, shield: w.shield } : o);
        ctx.live.push({ w, full, F: null, n: null, f: null });
      }
      Net.wst = wst;
      const zsig = S.zones.map(z => z.id).join(), psig = S.players.map(p => [p.pid, p.worm && p.worm.alive ? p.worm.id : 0, p.lastKiller, p.lastCause, p.lastScore, p.everSpawned ? 1 : 0, p.comp ? p.comp.lives : 0].join()).join('|') + '#' + S.match.n + (S.match.over ? 'o' : '');
      ctx.zNew = zsig !== Net.zsig || N % 20 === 0; ctx.pNew = psig !== Net.psig || N % 20 === 0; Net.zsig = zsig; Net.psig = psig;
      for (const c of Net.conns.slice()) { if (c.dead) continue; try { sendTo(c, S, ctx); } catch (e) { } }
    } else Net.wst = new Map();
    Net.evbuf.length = 0; return true;
  };
  // test hook: a host with no PeerJS behind it; returns accept(conn) for fake connections
  Net._loop = function (getSim) { Net.close(); resetStats(); Net.role = 'host'; Net.code = 'TEST'; Net.getSim = getSim; return accept; };

  // ---------- client ----------
  // h = { onInit(msg), onPart(msg), onSnap(msg), onClose(reason) }
  Net.join = function (code, ch, h) {
    Net.close(); resetStats(); const gen = Net.gen;
    code = String(code || '').toUpperCase().replace(/[^A-Z]/g, '');
    Net.role = 'client'; Net.code = code;
    let got = false, dead = false, to = 0, started = false;
    const live = () => gen === Net.gen && !dead;
    const fail = msg => { if (!live()) return; dead = true; clearTimeout(to); h.onClose(msg); };
    const arm = (ms, msg) => { clearTimeout(to); to = setTimeout(() => { if (!got) fail(msg); }, ms); };
    Net.fail = fail;
    if (code.length !== 4) { setTimeout(() => fail('ROOM CODES ARE 4 LETTERS'), 0); return; }
    arm(20000, 'COULD NOT LOAD ONLINE LIBRARY');
    loadLib(ok => {
      if (!live()) return;
      if (!ok) return fail('COULD NOT LOAD ONLINE LIBRARY');
      let peer; try { peer = new window.Peer(); } catch (e) { return fail('BROWSER CANNOT PLAY ONLINE'); }
      Net.peer = peer; arm(12000, 'ONLINE SERVER DID NOT ANSWER');
      peer.on('error', err => {
        if (got) return; // in the room only the data channel matters; losing the signalling server is harmless
        const t = err && err.type;
        fail(t === 'peer-unavailable' ? 'ROOM ' + code + ' NOT FOUND' : t === 'browser-incompatible' ? 'BROWSER CANNOT PLAY ONLINE'
          : t === 'network' || t === 'server-error' || t === 'socket-error' || t === 'socket-closed' ? 'ONLINE SERVER UNREACHABLE' : 'COULD NOT CONNECT');
      });
      peer.on('open', () => {
        if (!live() || started) return; started = true;
        arm(15000, 'COULD NOT REACH ROOM ' + code);
        const conn = peer.connect(PREFIX + code, { reliable: true, serialization: 'json' }); Net.conn = conn;
        conn.on('open', () => { if (live()) try { conn.send({ t: 'hello', ch: ch | 0, v: VER }); } catch (e) { } });
        conn.on('data', m => { if (live() && m && typeof m === 'object') try { onMsg(m); } catch (e) { } });
        conn.on('close', () => fail(got ? 'HOST LEFT THE GAME' : 'COULD NOT REACH ROOM ' + code));
        conn.on('error', e => { const t = e && e.type; if (t !== 'not-open-yet' && t !== 'message-too-big') fail(got ? 'CONNECTION LOST' : 'COULD NOT REACH ROOM ' + code); });
      });
      const onMsg = m => {
        Net.stats.inN++;
        switch (m.t) {
          case 's': if (got) { norm(m); Net.lastSnap = Net.now(); h.onSnap(m); } break;
          case 'it': case 'pt': if (got) h.onPart(m); break;
          case 'init': got = true; clearTimeout(to); Net.lastSnap = Net.now(); h.onInit(m); break;
          case 'k': if (typeof m.c === 'number') Net.stats.rtt = Math.max(0, Math.round(Net.now() * 1000 - m.c)); break;
          case 'full': fail('ROOM IS FULL'); break;
          case 'x': fail(String(m.r || 'DISCONNECTED').toUpperCase().replace(/[^A-Z0-9 .,!?:-]/g, '').slice(0, 40)); break;
          case 'bye': fail('HOST LEFT THE GAME'); break;
        }
      };
      // once a second, even in a hidden tab: tell the host we are still here, and notice a host that went silent.
      // (A host that vanished is normally reported by the browser within ~30 s as a closed connection; 45 s is the backstop.)
      let prev = Net.now(), warned = 0;
      Net.timer = setInterval(() => {
        if (!live()) return; const now = Net.now(), conn = Net.conn;
        if (now - prev > 3) Net.lastSnap = Math.max(Net.lastSnap || 0, now - 30); // this device was asleep: give the host a moment
        prev = now; if (!got || !conn || !conn.open) return;
        try { conn.send({ t: 'k', c: Math.round(now * 1000) }); } catch (e) { }
        const quiet = now - Net.lastSnap;
        if (quiet > 45) fail('LOST CONNECTION TO HOST'); else if (quiet > 4 && now - warned > 5) { warned = now; toast('WAITING FOR HOST...'); }
      }, 1000);
    });
  };
  Net.sendInput = function (o, abilSeq, wantSpawn) {
    const conn = Net.conn; if (!conn || !conn.open) return;
    const q = v => Math.round(unit(+v) * 100) / 100;
    const m = [q(o.mx), q(o.my), q(o.ax), q(o.ay)], f = (o.fire ? 1 : 0) | (o.boost ? 2 : 0) | (o.auto ? 4 : 0) | (wantSpawn ? 8 : 0);
    const key = m.join() + '|' + f + '|' + abilSeq, now = Net.now(), since = now - (Net.inT || 0);
    // the host keeps the last input, so an unchanged one is only repeated 5 times a second; stick movement goes out at up to 40Hz,
    // buttons at once
    if (key === Net.inKey ? since < 0.2 : since < 0.024 && f === Net.inF && abilSeq === Net.inA) return;
    const dc = conn.dataChannel; if (dc && dc.bufferedAmount > 16000) return;
    Net.inKey = key; Net.inF = f; Net.inA = abilSeq; Net.inT = now;
    try { conn.send({ t: 'i', m, f, a: abilSeq }); } catch (e) { }
  };

  // ---------- mirror state on the client ----------
  Net.newMirror = function () { return { t: 0, worms: [], items: new Map(), bullets: [], zones: [], players: [], comps: [], match: { t: CFG.MATCH_T, over: false, n: 0, reason: '', next: 0 }, wmap: new Map(), bmap: new Map(), pre: null, snapN: 0, gap: 0.055, late: 0.005, delay: 0.07 }; };
  const arr = v => Array.isArray(v) ? v : [];
  function norm(m) { m.w = arr(m.w); m.b = arr(m.b); m.a = arr(m.a); m.r = arr(m.r); m.e = arr(m.e); if (!Array.isArray(m.z)) delete m.z; if (!Array.isArray(m.p)) delete m.p; return m; }
  const KINDS = { f: () => HW.foodSpr, a: () => null, v: () => HW.vegSpr, m: () => HW.shroomSpr };
  function addItem(G, r) {
    if (!Array.isArray(r) || !KINDS[r[1]] || (G.items.size >= 20000 && !G.items.has(r[0]))) return;
    const spr = KINDS[r[1]](), n = spr && spr.length ? spr.length : 1;
    G.items.set(r[0], { id: r[0], k: r[1], type: clamp(r[2] | 0, 0, n - 1), x: clamp(num(r[3]), 0, CFG.W), y: clamp(num(r[4]), 0, CFG.H), v: num(r[5]) });
  }
  // Host time (T, seconds of simulation) -> this device's clock. Packets can only arrive late, never early, so the
  // best estimate of the offset is the largest (T - arrival time) seen in the last second or two.
  function clock(G, T, now) {
    const est = T - now;
    if (G.offT !== undefined && est < G.offT - 0.75) G.lateN = (G.lateN || 0) + 1; else G.lateN = 0;
    if (G.offT === undefined || est > G.offT + 0.3 || G.lateN >= 2) { G.op = G.oc = G.offT = est; G.ob = now; G.lateN = 0; if (G.off === undefined) G.off = est; }
    else {
      if (now - G.ob > 1) { G.op = G.oc; G.oc = est; G.ob = now; } else if (est > G.oc) G.oc = est;
      G.offT = Math.max(G.op, G.oc);
      G.late += (clamp(G.offT - est, 0, 0.3) - G.late) * 0.1;
    }
    const g = T - (G.lastT || 0); if (G.lastT && g > 0 && g < 0.5) G.gap += (g - G.gap) * 0.1;
    G.lastT = T;
  }
  const tm = (cur, v) => Math.abs((cur || 0) - v) > 0.15 ? v : cur || 0; // keep our own countdown unless it has drifted
  function applyWorm(G, r, T) {
    const full = r.length >= 17, o = full ? 3 : 1; let w = G.wmap.get(r[0]);
    if (!w && !full) return; // never seen in full; its full row is on the way
    const x = clamp(num(r[o]), 0, CFG.W), y = clamp(num(r[o + 1]), 0, CFG.H), ang = num(r[o + 2]) / 100, aim = num(r[o + 3]) / 100, mass = clamp(num(r[o + 4]) / 10, 1, 1e6), fl = r[o + 5] | 0;
    if (!w) {
      w = { id: r[0], ch: clamp(r[1] | 0, 0, CHARS.length - 1), variant: 0, x, y, ang, aim, mass, pts: [], q: [], alive: true, inp: {}, abil: 0, stuck: 0, slow: 0, trip: 0, shield: 0, ammo: 0, kills: 0, pid: -1 };
      const pre = G.pre && G.pre[w.id];
      if (pre && pre.length >= 4) {
        // rebuild the body from the every-3rd-point data sent at join time
        for (let i = 0; i + 3 < pre.length; i += 2) for (let k = 0; k < 3; k++) w.pts.push({ x: num(pre[i]) + (num(pre[i + 2]) - num(pre[i])) * k / 3, y: num(pre[i + 1]) + (num(pre[i + 3]) - num(pre[i + 1])) * k / 3 });
        w.pts.push({ x: num(pre[pre.length - 2]), y: num(pre[pre.length - 1]) });
      } else { const n = HW.segCount(mass); for (let i = 0; i < n; i++) w.pts.push({ x: x - Math.cos(ang) * i * 2, y: y - Math.sin(ang) * i * 2 }); } // fresh spawn: laid out like the host does
      G.wmap.set(w.id, w); G.worms.push(w); HW.follow(w);
    }
    if (full) {
      w.variant = clamp(r[2] | 0, 0, 3); w.ammo = num(r[9]); w.kills = num(r[14]); w.pid = r[15] | 0; w.isBot = !!(fl & 2);
      w.abil = tm(w.abil, num(r[10]) / 10); w.stuck = tm(w.stuck, num(r[11]) / 10); w.slow = tm(w.slow, num(r[12]) / 10); w.trip = tm(w.trip, num(r[13]) / 10); w.shield = tm(w.shield, num(r[16]) / 10);
    }
    w.mass = mass; w.boosting = !!(fl & 1); w.seen = G.snapN;
    const q = w.q, l = q[q.length - 1], s = { t: T, x, y, a: ang, m: aim };
    if (l && T <= l.t) q[q.length - 1] = s; else { q.push(s); if (q.length > 6) q.shift(); }
  }
  Net.applySnap = function (G, m) {
    norm(m); const now = Net.now(), T = num(m.T) / 1000, N = ++G.snapN;
    clock(G, T, now);
    for (const r of m.w) { if (typeof r === 'number') { const w = G.wmap.get(r); if (w) w.seen = N; } else if (Array.isArray(r)) applyWorm(G, r, T); }
    for (let i = G.worms.length - 1; i >= 0; i--) if (G.worms[i].seen !== N) { G.wmap.delete(G.worms[i].id); G.worms[i].alive = false; G.worms.splice(i, 1); }
    if (m.first) G.pre = null;
    // bullets keep flying on our own clock; a snapshot only nudges them (its positions are `late` seconds old)
    const late = clamp((G.now || now) + G.off - T, -0.1, 0.25);
    for (const r of m.b) {
      if (typeof r === 'number') { const b = G.bmap.get(r); if (b) b.seen = N; continue; }
      if (!Array.isArray(r)) continue;
      const vx = num(r[4]), vy = num(r[5]), x = num(r[2]) + vx * late, y = num(r[3]) + vy * late; let b = G.bmap.get(r[0]);
      if (!b) { b = { id: r[0], ch: clamp(r[1] | 0, 0, CHARS.length - 1), x, y, vx, vy, c: clamp(r[6] | 0, 0, 4) }; G.bmap.set(b.id, b); G.bullets.push(b); }
      else { const dx = x - b.x, dy = y - b.y; if (dx * dx + dy * dy > 900) { b.x = x; b.y = y; } else { b.x += dx * 0.25; b.y += dy * 0.25; } b.vx = vx; b.vy = vy; }
      b.seen = N;
    }
    for (let i = G.bullets.length - 1; i >= 0; i--) if (G.bullets[i].seen !== N) { G.bmap.delete(G.bullets[i].id); G.bullets.splice(i, 1); }
    if (m.z) {
      const old = new Map(); for (const z of G.zones) old.set(z.id, z);
      G.zones = m.z.filter(Array.isArray).map(r => { const o = old.get(r[0]), t = num(r[5]); return { id: r[0], k: r[1] ? 1 : 0, x: num(r[2]), y: num(r[3]), r: clamp(num(r[4]), 0, 400), t: o && Math.abs(o.t - t) < 0.25 ? o.t : t, owner: r[6] }; });
    }
    for (const r of m.a) addItem(G, r);
    for (const id of m.r) G.items.delete(id);
    if (Array.isArray(m.c) && Array.isArray(m.c[5])) {
      G.match = { t: num(m.c[0]), over: !!m.c[1], n: m.c[2] | 0, reason: String(m.c[3] || ''), next: num(m.c[4]) };
      G.comps = m.c[5].filter(Array.isArray).slice(0, 16).map(r => ({ cid: r[0] | 0, pid: r[1] | 0, ch: clamp(r[2] | 0, 0, CHARS.length - 1), variant: clamp(r[3] | 0, 0, 3), kills: num(r[4]), score: num(r[5]), lives: num(r[6]), out: !!r[7] }));
    }
    if (m.p) G.players = m.p.filter(Array.isArray).map(r => ({ pid: r[0] | 0, wormId: r[1], deadT: num(r[2]), lastKiller: String(r[3] || ''), lastCause: String(r[4] || ''), lastScore: num(r[5]), best: num(r[6]), everSpawned: !!r[7] }));
  };
  // pieces of the arena that arrive before a newcomer's first snapshot (or a resync), and big bursts of item changes
  Net.applyPart = function (G, m) {
    if (m.t === 'it') { if (m.z) G.items.clear(); for (const r of arr(m.a)) addItem(G, r); for (const id of arr(m.r)) G.items.delete(id); }
    else if (m.t === 'pt' && Array.isArray(m.p) && m.p.length <= 600) (G.pre = G.pre || {})[m.id] = m.p;
  };
  // Worms are drawn a little in the past (G.delay: half a snapshot interval plus an allowance for jitter) and slide
  // between the two snapshots around that moment, using the host's own timestamps. That keeps their speed even
  // although snapshots are 3 or 4 sim steps apart and arrive unevenly. Past the newest snapshot a worm carries on
  // in a straight line for up to 0.1s (a few ms of that is normal and invisible), then waits.
  Net.clientUpdate = function (G, dt) {
    G.t += dt; const now = Net.now(), rdt = clamp(now - (G.now || now), 0, 0.25); G.now = now;
    if (G.off !== undefined) {
      let d = G.offT - G.off; G.off += Math.abs(d) > 0.3 ? d : clamp(d, -rdt * 0.1, rdt * 0.1);
      d = clamp(G.gap * Net.LAG + G.late * 2 + 0.005, 0.03, 0.25) - G.delay; G.delay += clamp(d, -rdt * 0.05, rdt * 0.05);
    }
    const rt = now + (G.off || 0) - G.delay;
    for (const w of G.worms) {
      const q = w.q; while (q.length > 2 && q[1].t <= rt) q.shift();
      const a = q[0], b = q[1];
      if (!a) { /* no position yet */ }
      else if (!b || b.t <= a.t) { w.x = a.x; w.y = a.y; w.ang = a.a; if (!w.localAim) w.aim = a.m; }
      else {
        const span = b.t - a.t, k = clamp((rt - a.t) / span, 0, 1 + 0.1 / span), ka = Math.min(1, k);
        w.x = clamp(a.x + (b.x - a.x) * k, 0, CFG.W); w.y = clamp(a.y + (b.y - a.y) * k, 0, CFG.H);
        w.ang = a.a + angDiff(b.a, a.a) * ka; if (!w.localAim) w.aim = a.m + angDiff(b.m, a.m) * ka;
      }
      if (w.abil > 0) w.abil -= dt; if (w.stuck > 0) w.stuck -= dt; if (w.slow > 0) w.slow -= dt; if (w.trip > 0) w.trip -= dt; if (w.shield > 0) w.shield -= dt;
      HW.follow(w);
    }
    for (const b of G.bullets) {
      const bg = CHARS[b.ch].gun; if (bg.blast) { const v = Math.sqrt(b.vx * b.vx + b.vy * b.vy); if (v > 1) { const nv = Math.min(bg.vmax, v + bg.accel * rdt); b.vx *= nv / v; b.vy *= nv / v; } } // rockets speed up, as in sim.js
      b.x += b.vx * rdt; b.y += b.vy * rdt;
    }
    for (const z of G.zones) z.t -= dt;
    for (const p of G.players) if (!p.wormId) p.deadT += dt;
    if (G.match) { if (!G.match.over) G.match.t = Math.max(0, G.match.t - dt); else G.match.next = Math.max(0, G.match.next - dt); }
    // food slides toward mouths (visual only, the host decides what is eaten)
    for (const it of G.items.values()) {
      if (it.k !== 'f') continue;
      for (const w of G.worms) {
        const dx = w.x - it.x, dy = w.y - it.y; if (dx > 60 || dx < -60 || dy > 60 || dy < -60) continue;
        const d = Math.sqrt(dx * dx + dy * dy); if (d < w.r + CHARS[w.ch].eat && d > 1) { const k = Math.min(1, 260 * dt / d); it.x += dx * k; it.y += dy * k; }
      }
    }
  };

  // closing the tab: tell the others right away instead of leaving them to a timeout
  window.addEventListener('pagehide', () => {
    if (!Net.role && !Net.peer) return;
    Net.leaving = true; try { if (Net.role === 'client' && Net.fail) Net.fail('DISCONNECTED'); Net.close(); } catch (e) { } Net.leaving = false;
  });
  // back on the network: do not wait for the next retry
  window.addEventListener('online', () => { const p = Net.peer; if (Net.role === 'host' && p && p.disconnected) { clearTimeout(Net.reT); Net.reT = 0; Net.reN = 0; reconnectSoon(p); } });
})(window.HW);
