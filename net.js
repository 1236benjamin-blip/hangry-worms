// Hangry Worms - online rooms over PeerJS (free peer-to-peer, host is authoritative)
//
// Wire format (JSON, one PeerJS data channel per client, reliable + ordered):
//   client -> host  {t:'hello',ch,v}   {t:'i',m:[mx,my,ax,ay],f:flags,a:abilSeq}   {t:'k',c:clientMs} keep-alive/ping   {t:'bye'}
//                   flags: 1 fire, 2 boost, 4 auto-aim, 8 wants to respawn, 16 taunt (flips once per taunt, see Net.sendInput)
//   host -> client  {t:'init',pid}  {t:'it',z?,a?,r?} item chunks (z = forget all items first)  {t:'pt',id,p} body points
//                   {t:'s',T,w,b?,z?,c?,a?,r?,e?,p?,first?} snapshot   {t:'k',c} pong   {t:'full'}  {t:'x',r:reason}  {t:'bye'}
//   Snapshot rows: w = worms: 24 numbers (everything), 7 numbers (movement only) or a bare id (alive, nothing new);
//   b = bullets near that client: 8 numbers the first time, then a bare id; z / c / p (zones, match + scores, players) only
//   when they change; a / r = items added / removed since that client's last snapshot; e = events for that client.
// PeerJS refuses JSON messages of 16300 bytes or more and raises an error on the connection, so every message is kept far below that.
'use strict';
(function (HW) {
  const CFG = HW.CFG, CHARS = HW.CHARS, GUNS = HW.GUNS, MAP = HW.MAP, { angDiff, clamp } = HW.util;
  const PREFIX = 'hangryworms-v1-', VER = 4, ALPHA = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
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
  function resetStats() { Net.stats = { out: 0, outN: 0, snapB: 0, snapN: 0, snapMax: 0, msgMax: 0, over: 0, skip: 0, resync: 0, inN: 0, rtt: 0, pred: 0, psnap: 0, perr: 0 }; }
  resetStats();
  // round trip in ms, from the host's answer to our once-a-second keep-alive (c = our clock when we sent it)
  Net.onPong = function (c) { if (typeof c === 'number') Net.stats.rtt = Math.max(0, Math.round(Net.now() * 1000 - c)); };

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
    Net.fail = null; Net.getSim = null; Net.wst = new Map(); Net.zsig = Net.psig = ''; Net.inKey = ''; Net.inT = 0; Net.hkT = 0; Net.tnt = 0; Net.tnWas = false;
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
    const c = { conn, gen: Net.gen, player: null, pending: false, dead: false, full: true, idle: false, seq: 0, tnt: 0, born: now, last: now, lastIn: now, lastK: 0, qa: [], qr: [], bk: new Set(), ix: CFG.W / 2, iy: CFG.H / 2, wid: 0 };
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
      // the taunt bit flips once per taunt, so a repeated or late message can neither repeat one nor lose one
      if ((f & 16) !== c.tnt) { c.tnt = f & 16; if (alive) I.taunt = true; }
      if ((f & 8) && !alive) p.wantSpawn = true;
    } else if (m.t === 'hello') {
      if (c.player) return;
      if (m.v !== VER) return drop(c, 'OLD VERSION - RELOAD THE GAME');
      if (sim.S.players.length >= CFG.MAX_PLAYERS) return drop(c, 'ROOM IS FULL');
      const i = Net.lobby.indexOf(c); if (i >= 0) Net.lobby.splice(i, 1);
      c.player = sim.addPlayer(clamp(m.ch | 0, 0, CHARS.length - 1), c.conn);
      c.player.inp = { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false, taunt: false };
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
      if (now - c.lastIn > 1.5 && !c.idle) { c.idle = true; const I = c.player.inp; I.mx = I.my = I.ax = I.ay = 0; I.fire = I.boost = I.abil = I.taunt = false; }
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
  const FULL = 24;   // length of a full worm row
  const fullRow = w => [w.id, w.ch, w.variant, r1(w.x), r1(w.y), Math.round(w.ang * 100), Math.round(w.aim * 100), Math.round(w.mass * 10), flags(w), w.ammo, tenths(w.abil), tenths(w.stuck), tenths(w.slow), tenths(w.trip), w.kills, w.pid, tenths(w.shield),
    tenths(w.rage), tenths(w.big), tenths(w.guard), tenths(w.sauce), tenths(w.chill), w.sg | 0, tenths(w.sgT)];
  // countdowns (seconds): the host sends them when they jump, in between every device counts down by itself
  const TIMERS = ['abil', 'stuck', 'slow', 'trip', 'shield', 'rage', 'big', 'guard', 'sauce', 'chill', 'sgT'];
  // what the host remembers of the last full row it sent for a worm
  function sent(w, t) { const o = { t, ammo: w.ammo, kills: w.kills, variant: w.variant, sg: w.sg | 0 }; for (const k of TIMERS) o[k] = w[k] || 0; return o; }
  // has anything changed that a client cannot work out for itself (timers just count down)?
  function stale(o, w, t) {
    if (o.ammo !== w.ammo || o.kills !== w.kills || o.variant !== w.variant || o.sg !== (w.sg | 0)) return true;
    for (const k of TIMERS) if (Math.abs(Math.max(0, o[k] - (t - o.t)) - Math.max(0, w[k] || 0)) > 0.12) return true;
    return false;
  }
  // Who an event is for. 0: every client (the kill feed, match-wide news; these sit at 0,0 or anywhere).
  // 1: only the worm it belongs to (e[3]; for a shot e[4], because e[3] is the gun). 3: whoever is near; e[3] is
  // not a worm (a gun kind, a radius, an item kind), so it must never be compared with a worm id.
  // Everything else (2): the worm it belongs to, and whoever is near enough to see or hear it.
  const EVC = { die: 0, frenzy: 0, over: 0, go: 0, eat: 1, dry: 1, poweroff: 1, gunoff: 1, puff: 3, boom: 3, clang: 3, drop: 3 };
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
      (b || (b = [])).push(!full && c.bk.has(q.id) && (N + q.id) % 8 ? q.id : [q.id, q.ch, r1(q.x), r1(q.y), Math.round(q.vx), Math.round(q.vy), q.c, Math.round((q.age || 0) * 100)]); bk.add(q.id);
    }
    c.bk = bk; if (b) m.b = b;
    if (full || ctx.zNew) m.z = S.zones.map(z => [z.id, z.k, Math.round(z.x), Math.round(z.y), z.r, r1(z.t), z.owner]);
    if (full || ctx.pNew) m.c = [Math.ceil(S.match.t), S.match.over ? 1 : 0, S.match.n, S.match.reason || '', r1(Math.max(0, (S.autoNext || 0) - S.match.overT)), S.comps.map(c => [c.cid, c.pid, c.ch, c.variant, c.kills, c.score, c.lives, c.out ? 1 : 0]),
      S.match.frenzy ? 1 : 0, S.match.over ? S.match.awards || [] : []];
    if (full || ctx.pNew) m.p = S.players.map(p => [p.pid, p.worm && p.worm.alive ? p.worm.id : 0, r1(p.deadT), p.lastKiller || '', p.lastCause || '', p.lastScore || 0, Math.round(p.best || 0), p.everSpawned ? 1 : 0]);
    if (!all) {
      // Effects, 40 at most so a busy fight cannot bloat the message. In order of importance: match-wide news and
      // deaths (kill feed); what happened to this client's own worm (its banners, hits, pickups); then its own
      // eating / shooting noises and whatever else is near enough to see or hear.
      const e = [], wid = c.wid, B = Net.evbuf; let dies = 0;
      const own = ev => wid !== 0 && EVC[ev[0]] !== 3 && (ev[0] === 'shot' ? ev[4] : ev[3]) === wid, chatter = k => k === 'eat' || k === 'shot';
      for (const ev of B) if (EVC[ev[0]] === 0 && (ev[0] !== 'die' || dies++ < 24)) e.push(ev);
      for (const ev of B) { if (e.length >= 40) break; if (EVC[ev[0]] !== 0 && !chatter(ev[0]) && own(ev)) e.push(ev); }
      for (const ev of B) {
        const k = ev[0], g = EVC[k]; if (e.length >= 40) break; if (g === 0) continue;
        if (own(ev) ? chatter(k) : g !== 1 && Math.abs(ev[1] - ix) < VIEW + 40 && Math.abs(ev[2] - iy) < VIEW + 40) e.push(ev);
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
    if (me) { c.ix = me.x; c.iy = me.y; c.wid = me.id; }
    else {
      p.inp.abil = p.inp.taunt = false;   // a press while dead is not saved for the next life
      // out of lives: this client is watching the biggest worm (see playFrame in main.js), so that is where it needs detail
      if (p.comp && p.comp.out && p.deadT > 1.5) { let top = null; for (const L of ctx.live) if (!top || L.w.mass > top.mass) top = L.w; if (top) { c.ix = top.x; c.iy = top.y; } }
    }
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
        wst.set(w.id, full ? sent(w, S.t) : o);
        ctx.live.push({ w, full, F: null, n: null, f: null });
      }
      Net.wst = wst;
      const zsig = S.zones.map(z => z.id).join(), psig = S.players.map(p => [p.pid, p.worm && p.worm.alive ? p.worm.id : 0, p.lastKiller, p.lastCause, p.lastScore, p.everSpawned ? 1 : 0, p.comp ? p.comp.lives : 0].join()).join('|') + '#' + S.match.n + (S.match.over ? 'o' : '') + (S.match.frenzy ? 'f' : '');
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
          case 'init': got = true; clearTimeout(to); Net.lastSnap = Net.now(); h.onInit(m);
            try { Net.conn.send({ t: 'k', c: Math.round(Net.now() * 1000) }); } catch (e) { }   // measure the round trip now: prediction wants it before the first second is over
            break;
          case 'k': Net.onPong(m.c); break;
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
  const q2 = v => Math.round(unit(+v) * 100) / 100;   // sticks travel as hundredths
  Net.sendInput = function (o, abilSeq, wantSpawn) {
    const conn = Net.conn; if (!conn || !conn.open) return;
    // A taunt is one press. It travels as a bit that flips (Net.tnt), carried by every input message from then on:
    // a throttled or repeated message cannot lose it or play it twice (the ability uses a counter for the same reason).
    const tn = !!o.taunt; if (tn && !Net.tnWas) Net.tnt ^= 16; Net.tnWas = tn;
    const q = q2, m = [q(o.mx), q(o.my), q(o.ax), q(o.ay)], f = (o.fire ? 1 : 0) | (o.boost ? 2 : 0) | (o.auto ? 4 : 0) | (wantSpawn ? 8 : 0) | (Net.tnt || 0);
    const key = m.join() + '|' + f + '|' + abilSeq, now = Net.now(), since = now - (Net.inT || 0);
    // the host keeps the last input, so an unchanged one is only repeated 5 times a second; stick movement goes out at up to 40Hz,
    // buttons at once
    if (key === Net.inKey ? since < 0.2 : since < 0.024 && f === Net.inF && abilSeq === Net.inA) return;
    const dc = conn.dataChannel; if (dc && dc.bufferedAmount > 16000) return;
    Net.inKey = key; Net.inF = f; Net.inA = abilSeq; Net.inT = now;
    try { conn.send({ t: 'i', m, f, a: abilSeq }); } catch (e) { }
  };

  // ---------- mirror state on the client ----------
  Net.newMirror = function () { return { t: 0, worms: [], items: new Map(), bullets: [], zones: [], players: [], comps: [], match: { t: CFG.MATCH_T, over: false, n: 0, reason: '', next: 0, frenzy: false, awards: [] }, wmap: new Map(), bmap: new Map(), pre: null, snapN: 0, gap: 0.055, late: 0.005, delay: 0.07 }; };
  const arr = v => Array.isArray(v) ? v : [];
  function norm(m) { m.w = arr(m.w); m.b = arr(m.b); m.a = arr(m.a); m.r = arr(m.r); m.e = arr(m.e); if (!Array.isArray(m.z)) delete m.z; if (!Array.isArray(m.p)) delete m.p; return m; }
  // item kinds and how many types each has: food, ammo crate, veggie, mushroom, power-up, special gun, golden burger
  const KINDS = { f: () => HW.foodSpr.length, a: () => 1, v: () => HW.vegSpr.length, m: () => HW.shroomSpr.length, p: () => HW.POWERS.length, g: () => HW.SGUNS.length, x: () => 1 };
  function addItem(G, r) {
    if (!Array.isArray(r) || typeof r[1] !== 'string' || !KINDS.hasOwnProperty(r[1]) || (G.items.size >= 20000 && !G.items.has(r[0]))) return;
    const n = KINDS[r[1]]() || 1;
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
    const full = r.length >= FULL, o = full ? 3 : 1; let w = G.wmap.get(r[0]);
    if (!w && !full) return; // never seen in full; its full row is on the way
    const x = clamp(num(r[o]), 0, CFG.W), y = clamp(num(r[o + 1]), 0, CFG.H), ang = num(r[o + 2]) / 100, aim = num(r[o + 3]) / 100, mass = clamp(num(r[o + 4]) / 10, 1, 1e6), fl = r[o + 5] | 0;
    if (!w) {
      w = { id: r[0], ch: clamp(r[1] | 0, 0, CHARS.length - 1), variant: 0, x, y, ang, aim, mass, pts: [], q: [], alive: true, inp: {}, abil: 0, stuck: 0, slow: 0, trip: 0, shield: 0, rage: 0, big: 0, guard: 0, sauce: 0, chill: 0, sg: 0, sgT: 0, ammo: 0, kills: 0, pid: -1 };
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
      w.rage = tm(w.rage, num(r[17]) / 10); w.big = tm(w.big, num(r[18]) / 10); w.guard = tm(w.guard, num(r[19]) / 10); w.sauce = tm(w.sauce, num(r[20]) / 10); w.chill = tm(w.chill, num(r[21]) / 10);
      w.sg = clamp(r[22] | 0, 0, HW.SGUNS.length); w.sgT = w.sg ? tm(w.sgT, num(r[23]) / 10) : 0;   // sg: special gun + 1 (HW.gunSprOf reads it)
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
      const age = clamp(num(r[7]) / 100 + late, 0, 60);
      // ch is the gun kind (HW.GUNS: five character guns, then the special guns); age drives the flamethrower's puffs
      if (!b) { b = { id: r[0], ch: clamp(r[1] | 0, 0, GUNS.length - 1), x, y, vx, vy, c: clamp(r[6] | 0, 0, 4), age, stop: false }; G.bmap.set(b.id, b); G.bullets.push(b); }
      else { const dx = x - b.x, dy = y - b.y; if (dx * dx + dy * dy > 900) { b.x = x; b.y = y; } else { b.x += dx * 0.25; b.y += dy * 0.25; } b.vx = vx; b.vy = vy; if (Math.abs(age - b.age) > 0.1) b.age = age; b.stop = false; }
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
      // awards: [competitor id, title, a number or a short text like '85%'], shown on the results screen
      const aw = arr(m.c[7]).filter(Array.isArray).slice(0, 8).map(a => [a[0] | 0, String(a[1] || '').slice(0, 60), typeof a[2] === 'number' ? num(a[2]) : String(a[2] === undefined ? '' : a[2]).slice(0, 12)]);
      G.match = { t: num(m.c[0]), over: !!m.c[1], n: m.c[2] | 0, reason: String(m.c[3] || ''), next: num(m.c[4]), frenzy: !!m.c[6], awards: aw };
      G.comps = m.c[5].filter(Array.isArray).slice(0, 16).map(r => ({ cid: r[0] | 0, pid: r[1] | 0, ch: clamp(r[2] | 0, 0, CHARS.length - 1), variant: clamp(r[3] | 0, 0, 3), kills: num(r[4]), score: num(r[5]), lives: num(r[6]), out: !!r[7] }));
    }
    if (m.p) G.players = m.p.filter(Array.isArray).map(r => ({ pid: r[0] | 0, wormId: r[1], deadT: num(r[2]), lastKiller: String(r[3] || ''), lastCause: String(r[4] || ''), lastScore: num(r[5]), best: num(r[6]), everSpawned: !!r[7] }));
  };
  // pieces of the arena that arrive before a newcomer's first snapshot (or a resync), and big bursts of item changes
  Net.applyPart = function (G, m) {
    if (m.t === 'it') { if (m.z) G.items.clear(); for (const r of arr(m.a)) addItem(G, r); for (const id of arr(m.r)) G.items.delete(id); }
    else if (m.t === 'pt' && Array.isArray(m.p) && m.p.length <= 600) (G.pre = G.pre || {})[m.id] = m.p;
  };
  // ---------- prediction of this client's own worm ----------
  // Every other worm is drawn a little in the past, between two snapshots. Drawn like that, our own worm would answer
  // the stick a whole round trip (plus that delay) late. So its head is moved here, at once, with the host's own
  // movement code (HW.turnHead / headSpeed / moveHead in sim.js) from the input of this frame (G.myId and G.myInp,
  // set by main.js). The body, the camera and the HUD follow from the head as usual.
  //
  // Keeping it honest: the input of every frame is remembered for a moment. A snapshot shows where the host really
  // had the head; the inputs the host had not seen by then are the ones of the last `full` seconds (the round trip),
  // so the head is put back on the host's position and those inputs are played again on top of it. Walls, counters
  // and other worms are met in that replay exactly as the host will meet them, so the two cannot drift apart or end
  // up on different sides of a table. Whatever the replay changes is not shown as a jump: the difference goes into
  // a small offset that slides away over a few frames, never faster than a fraction of the worm's speed. The head
  // only jumps when the difference is too big to slide (the host moved us, a long stall).
  //
  // What the client cannot know in time (stuck, slowed, frozen, a rampage starting; boost running out of mass) turns
  // up as such a difference one round trip later and is slid off. Effects ENDING are known in advance: the mirror's
  // countdowns show the host a moment ago and the predicted head lives a moment ahead, so the replay reads them that
  // much early. Mushrooms weave on host time, which clock() gives us. Bumping into another worm (the host holds the
  // head at its surface) is repeated against the worms as this client sees them: predHold().
  //
  // PRED_LEAD_MAX caps how far ahead of the last picture from the host the drawn head may run. The trade-off:
  // prediction shows where our head WILL be once the host has our input, while every other worm is still drawn where
  // it WAS. The host judges contact with everybody at the same moment, so at 110 px/s each 100 ms of lead makes a
  // dash across another worm's nose look about 11 px (most of a head) safer than it is. 0.15 s predicts ordinary
  // peer-to-peer links (round trip up to ~140 ms) in full, which keeps that gap near one and a half head widths.
  // On slower links the head still TURNS on the very frame (the heading is predicted in full), but it is drawn where
  // the prediction was a moment ago, so that it stays 0.15 s ahead of the host's picture and no more: the rest of
  // the delay is felt as plain delay in where the head goes, on the true path, instead of as a wider gap.
  const PRED_LEAD_MAX = 0.15;
  const PRED_REPLAY = 0.35;    // s of round trip beyond the cap that are still replayed (so: links up to 0.5 s)
  const PRED_PIPE = 0.012;     // s: an input waits for the host's next 60 Hz step on top of the trip there
  const PRED_COAST = 0.5;      // s without a newer picture from the host (frozen host, dead link) before the head stops and waits
  const PRED_TAU = 0.15;       // s: time constant of sliding a correction away
  const PRED_FIX = 0.5;        // ... but never faster than this fraction of the worm's normal speed
  const PRED_SNAP = 70;        // px: a correction bigger than this is not slid, the head jumps
  const PRED_GHOST = 4;        // px: see predHold
  const PRED_RTT_DOWN = 0.15;  // s per s: how fast the round-trip estimate may fall (on a link over the cap the drawn head moves up by as much)
  const TQ = 0.05;             // s: countdowns travel rounded up to tenths, so on average they read this much high
  Net.PREDICT = true;          // tests switch it off to compare
  Net.PRED = { LEAD_MAX: PRED_LEAD_MAX, REPLAY: PRED_REPLAY, PIPE: PRED_PIPE, COAST: PRED_COAST, TAU: PRED_TAU, FIX: PRED_FIX, SNAP: PRED_SNAP, RTT_DOWN: PRED_RTT_DOWN, hold: true };   // for tests (hold: false leaves out the test against visible worms, to show what it is for)
  const PW = { id: 0, ch: 0, x: 0, y: 0, ang: 0, r: 0, trip: 0, slow: 0, stuck: 0, rage: 0, chill: 0, sauce: 0, shield: 0, boosting: false }, PT = { x: 0, y: 0, nx: 0, ny: 0 };
  // nearest point of worm b's body to (x, y) if it is closer than lim; the squared distance is left in nearQ
  let nearQ = 0;
  function nearPt(b, x, y, lim) {
    const m = lim + 2; if (b.bx0 === undefined || x < b.bx0 - m || x > b.bx1 + m || y < b.by0 - m || y > b.by1 + m) return null;
    const p = b.pts; let hit = null, hq = lim * lim;
    for (let i = 0; i < p.length; i++) { const dx = p[i].x - x, dy = p[i].y - y, q = dx * dx + dy * dy; if (q < hq) { hq = q; hit = p[i]; } }
    nearQ = hq; return hit;
  }
  // The bump ("head vs body" in sim.js): a head that touches another worm is held at that worm's surface. Same
  // contact distance and same hold as the host, against the worms as this client sees them. Their picture is a
  // moment old, so the host has the last word: P.ghost lists worms whose picture lies across the position the host
  // itself reported for us (by more than PRED_GHOST px), typically a tail that has already moved on. Those cannot
  // be holding us and are passed through.
  function predHold(G, P, x0, y0) {   // x0, y0: where this step started
    let q = null, deep = 1e9, cd = 0;
    if (PW.shield <= 0 && Net.PRED.hold) for (const b of G.worms) {
      if (b.id === PW.id || b.shield > 0 || (PW.rage > 0 && !(b.rage > 0)) || P.ghost.indexOf(b.id) >= 0) continue;   // shields and a rampage go straight through
      const c = PW.r * 0.7 + b.r * 0.78, h = nearPt(b, PW.x, PW.y, c); if (!h) continue;
      const d = Math.sqrt(nearQ) - c; if (d < deep) { deep = d; q = h; cd = c; }
    }
    if (!q) { if (P.stall) { PW.x = x0; PW.y = y0; } return; }   // held by something we cannot see (below): turn, but do not advance
    const dx = q.x - PW.x, dy = q.y - PW.y, d = Math.sqrt(dx * dx + dy * dy) || 0.01, r = PW.r;
    PW.x = clamp(q.x - dx / d * (cd + 0.5), r, CFG.W - r); PW.y = clamp(q.y - dy / d * (cd + 0.5), r, CFG.H - r);
    if (MAP.push(PW.x, PW.y, r, PT)) { PW.x = clamp(PT.x, r, CFG.W - r); PW.y = clamp(PT.y, r, CFG.H - r); }
  }
  // Move our own head for h seconds of input I ({mx, my, b}: the stick as the host receives it, boost), in steps no
  // longer than the host's so walls and counters are met the same way. ahead: how far (s) this moment lies ahead of
  // what the mirror knows
  function predStep(G, P, w, I, h, ahead) {
    if (h > 0.025) { const n = Math.ceil(h * 60 - 0.01); for (let i = 0; i < n; i++) predStep(G, P, w, I, h / n, ahead); return; }
    const o = ahead + TQ;
    PW.id = w.id; PW.ch = w.ch; PW.r = w.r; PW.x = P.x; PW.y = P.y; PW.ang = P.ang;
    PW.trip = w.trip - o; PW.slow = w.slow - o; PW.stuck = w.stuck - o; PW.rage = w.rage - o; PW.chill = w.chill - o; PW.sauce = w.sauce - o; PW.shield = w.shield - o;
    // same rule as sim.js. Boosting burns mass and the host is further along than the mass we know
    PW.boosting = !!(I.b && (PW.sauce > 0 || w.mass - (P.boost ? CFG.BOOST_COST * Math.max(0, ahead) : 0) > CFG.MIN_MASS + 4) && PW.stuck <= 0);
    HW.turnHead(PW, I, h, G.now + G.off + ahead, false); HW.moveHead(PW, HW.headSpeed(PW), h); predHold(G, P, P.x, P.y);
    P.x = PW.x; P.y = PW.y; P.ang = PW.ang; P.boost = PW.boosting;
  }
  // where the predicted head was at time t (the history keeps its path)
  function predAt(H, t) {
    let j = H.length - 1; while (j > 0 && H[j].t > t) j--;
    const a = H[j], b = H[j + 1]; if (!b || t <= a.t) { PT.x = a.x; PT.y = a.y; return; }
    const k = (t - a.t) / (b.t - a.t); PT.x = a.x + (b.x - a.x) * k; PT.y = a.y + (b.y - a.y) * k;
  }
  // Is the host holding our head against something this client cannot see (a worm that is somewhere else in our
  // picture, a rule this code does not know)? Then every replay would run the head forward again from where the
  // host keeps it, for as long as it lasts. The test: play the inputs the host used between its last two pictures
  // from the first of them. If that says the head should have travelled and it hardly did, it is being held (stall);
  // predStep then stops advancing until the host's head moves as expected again.
  const PM = { x: 0, y: 0, ang: 0, boost: false, stall: false, ghost: null };
  function predStall(G, P, w, s, H, tl, full, now) {
    const o = P.pa, t0 = tl - (s.t - o.t); if (!(s.t > o.t) || s.t - o.t > 0.3) return false;
    PM.x = o.x; PM.y = o.y; PM.ang = o.a; PM.boost = P.boost; PM.ghost = P.ghost;
    for (let i = 0; i < H.length; i++) { const c = H[i], h = Math.min(c.t, tl) - Math.max(c.t - c.h, t0); if (h > 0) predStep(G, PM, w, c, h, c.t - now + full); }
    const m = Math.sqrt((PM.x - o.x) * (PM.x - o.x) + (PM.y - o.y) * (PM.y - o.y)), a = Math.sqrt((s.x - o.x) * (s.x - o.x) + (s.y - o.y) * (s.y - o.y));
    return m > 1.5 && (a < m * 0.4 || (P.stall && a < m * 0.7));
  }
  // returns true when it has placed w's head (x, y, ang); false: draw it from snapshots like any other worm
  function predict(G, w, rdt, now, gap) {
    const I = G.myInp, q = w.q, s = q[q.length - 1]; if (!s || G.off === undefined) return false;
    // round trip: follow the once-a-second measurement slowly, a faster one at 150 ms per second and a slower one at
    // 50 (one ping that sat in a stalled link is not a slower link). It must not swing: the drawn head hangs on it.
    const st = Net.stats, r = st.rtt / 1000; if (!(G.rtt > 0)) G.rtt = r; else G.rtt += clamp(r - G.rtt, -rdt * PRED_RTT_DOWN, rdt * 0.05);
    // full: how far ahead of the host's picture our newest input is; lead: how far ahead the head is drawn
    const full = Math.min(G.rtt + PRED_PIPE, PRED_LEAD_MAX + PRED_REPLAY), lead = Math.min(PRED_LEAD_MAX, full), age = now + G.off - s.t;
    const wait = age > PRED_COAST || !!(G.match && G.match.over);   // the host has gone quiet, or the arena is frozen: stay put rather than run on alone
    const e = { t: now, h: wait ? 0 : rdt, mx: q2(I.mx), my: q2(I.my), b: !!I.boost, x: 0, y: 0 };
    let P = G.pr, fresh = false;
    if (!P || P.id !== w.id || gap > 0.25) {
      // a new life, or this tab was asleep: start from the newest position the host sent, as if the stick had been
      // where it is now ever since (a short made-up history for the replay below)
      if (P && P.id === w.id) st.psnap++;
      P = G.pr = { id: w.id, x: s.x, y: s.y, ang: s.a, vx: 0, vy: 0, va: 0, look: now, aim: w.aim, boost: false, at: NaN, pa: null, stall: false, ghost: [], hist: [] }; fresh = true;
      const D = wait ? 0 : clamp(age + full, 0, PRED_LEAD_MAX + PRED_REPLAY + PRED_COAST), n = Math.ceil(D * 60), h = n ? D / n : 0;
      for (let i = 1; i < n; i++) P.hist.push({ t: now - D + i * h, h, mx: e.mx, my: e.my, b: e.b, x: s.x, y: s.y });
      e.h = h;
    }
    const H = P.hist; H.push(e);
    if (s.t !== P.at) {
      // news from the host: back to its position, then the inputs it had not seen yet, again
      const tl = s.t - G.off - full, n = H.length, a0 = P.ang; let a1 = s.a;
      predAt(H, P.look); const bx = PT.x, by = PT.y;   // where the drawn head was taken from last frame...
      P.stall = !!P.pa && predStall(G, P, w, s, H, tl, full, now); P.pa = s;
      P.at = s.t; P.x = s.x; P.y = s.y; P.ang = s.a; P.ghost.length = 0;
      for (const b of G.worms) if (b !== w && nearPt(b, s.x, s.y, Math.max(0, w.r * 0.7 + b.r * 0.78 - PRED_GHOST))) P.ghost.push(b.id);
      for (let i = 0; i < n; i++) {
        const c = H[i]; if (c.t <= tl) continue;
        if (i === n - 1) a1 = P.ang;
        const h = Math.min(c.h, c.t - tl); if (h > 0) predStep(G, P, w, c, h, c.t - now + full);
        c.x = P.x; c.y = P.y;
      }
      if (!fresh) {
        // ... and where that moment is now: the difference becomes the offset that slides away
        predAt(H, P.look); P.vx += bx - PT.x; P.vy += by - PT.y; P.va += angDiff(a0, a1);
        st.perr = Math.sqrt((bx - PT.x) * (bx - PT.x) + (by - PT.y) * (by - PT.y));
        if (P.vx * P.vx + P.vy * P.vy > PRED_SNAP * PRED_SNAP) { P.vx = P.vy = P.va = 0; st.psnap++; }
      }
    } else { if (e.h > 0) predStep(G, P, w, e, e.h, full); e.x = P.x; e.y = P.y; }
    while (H.length > 2 && H[1].t < now - (PRED_LEAD_MAX + PRED_REPLAY + PRED_COAST + 0.4)) H.shift();
    // slide the offset away
    const k = 1 - Math.exp(-rdt / PRED_TAU), v = Math.sqrt(P.vx * P.vx + P.vy * P.vy), lim = CHARS[w.ch].speed * PRED_FIX * rdt, f = v > 0 ? Math.min(v * k, lim) / v : 0;
    P.vx -= P.vx * f; P.vy -= P.vy * f; P.va -= clamp(P.va * k, -3 * rdt, 3 * rdt);
    P.look = now - (full - lead); predAt(H, P.look);
    w.x = PT.x + P.vx; w.y = PT.y + P.vy; w.ang = P.ang + P.va; w.boosting = P.boost; st.pred++;
    return true;
  }

  // Worms are drawn a little in the past (G.delay: half a snapshot interval plus an allowance for jitter) and slide
  // between the two snapshots around that moment, using the host's own timestamps. That keeps their speed even
  // although snapshots are 3 or 4 sim steps apart and arrive unevenly. Past the newest snapshot a worm carries on
  // in a straight line for up to 0.1s (a few ms of that is normal and invisible), then waits.
  // The one exception is this client's own worm, whose head is predicted (above).
  Net.clientUpdate = function (G, dt) {
    G.t += dt; const now = Net.now(), gap = now - (G.now || now), rdt = clamp(gap, 0, 0.25); G.now = now;
    if (G.off !== undefined) {
      let d = G.offT - G.off; G.off += Math.abs(d) > 0.3 ? d : clamp(d, -rdt * 0.1, rdt * 0.1);
      d = clamp(G.gap * Net.LAG + G.late * 2 + 0.005, 0.03, 0.25) - G.delay; G.delay += clamp(d, -rdt * 0.05, rdt * 0.05);
    }
    const rt = now + (G.off || 0) - G.delay;
    const mine = Net.PREDICT && G.myId && G.myInp ? G.wmap.get(G.myId) : null; if (!mine) G.pr = null;   // dead (or not a player): nothing to predict
    for (const w of G.worms) {
      const q = w.q; while (q.length > 2 && q[1].t <= rt) q.shift();
      const a = q[0], b = q[1], pred = w === mine && predict(G, w, rdt, now, gap);
      if (!a) { /* no position yet */ }
      else if (!b || b.t <= a.t) { if (!pred) { w.x = a.x; w.y = a.y; w.ang = a.a; } if (!w.localAim) w.aim = a.m; }
      else {
        const span = b.t - a.t, k = clamp((rt - a.t) / span, 0, 1 + 0.1 / span), ka = Math.min(1, k);
        if (!pred) { w.x = clamp(a.x + (b.x - a.x) * k, 0, CFG.W); w.y = clamp(a.y + (b.y - a.y) * k, 0, CFG.H); w.ang = a.a + angDiff(b.a, a.a) * ka; }
        if (!w.localAim) w.aim = a.m + angDiff(b.m, a.m) * ka;
      }
      if (pred) {
        // the gun: with the aim stick at rest it swings to the heading, as in sim.js. Only auto-aim is the host's secret.
        const P = G.pr, I = G.myInp;
        if (w.localAim || (I.auto && I.fire)) P.aim = w.aim; else { P.aim += clamp(angDiff(w.ang, P.aim), -14 * rdt, 14 * rdt); w.aim = P.aim; }
      }
      if (w.abil > 0) w.abil -= dt; if (w.stuck > 0) w.stuck -= dt; if (w.slow > 0) w.slow -= dt; if (w.trip > 0) w.trip -= dt; if (w.shield > 0) w.shield -= dt;
      if (w.rage > 0) w.rage -= dt; if (w.big > 0) w.big -= dt; if (w.guard > 0) w.guard -= dt; if (w.sauce > 0) w.sauce -= dt; if (w.chill > 0) w.chill -= dt; if (w.sgT > 0) w.sgT -= dt;
      HW.follow(w);
    }
    for (const b of G.bullets) {
      b.age += rdt; if (b.stop) continue;
      const g = GUNS[b.ch]; if (g.accel) { const v = Math.sqrt(b.vx * b.vx + b.vy * b.vy); if (v > 1) { const nv = Math.min(g.vmax, v + g.accel * rdt); b.vx *= nv / v; b.vy *= nv / v; } } // rockets speed up, as in sim.js
      const ox = b.x, oy = b.y; b.x += b.vx * rdt; b.y += b.vy * rdt;
      // counters and tables stop shots. The host says so a moment later; until then the shot waits at the surface instead of flying through
      if (MAP.hit(b.x, b.y, g.br * 0.5)) { b.x = ox; b.y = oy; b.stop = true; }
    }
    for (const z of G.zones) z.t -= dt;
    for (const p of G.players) if (!p.wormId) p.deadT += dt;
    if (G.match) { if (!G.match.over) G.match.t = Math.max(0, G.match.t - dt); else G.match.next = Math.max(0, G.match.next - dt); }
    // food slides toward mouths (visual only, the host decides what is eaten)
    for (const it of G.items.values()) {
      if (it.k !== 'f') continue;
      for (const w of G.worms) {
        const dx = w.x - it.x, dy = w.y - it.y; if (dx > 60 || dx < -60 || dy > 60 || dy < -60) continue;
        const d = Math.sqrt(dx * dx + dy * dy); if (d < w.r + CHARS[w.ch].eat * (w.big > 0 ? HW.POWERS[1].eat : 1) && d > 1) { const k = Math.min(1, 260 * dt / d); it.x += dx * k; it.y += dy * k; }
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
