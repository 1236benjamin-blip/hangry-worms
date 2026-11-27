// Hangry Worms - game simulation (host-authoritative; also used for local play)
'use strict';
(function (HW) {
  const CFG = HW.CFG = {
    W: 1900, H: 1900, SEG: 6, WORMS: 12, FOOD: 520, AMMO: 12, VEG: 22, SHROOM: 8,
    MIN_MASS: 6, SHIELD: 3, BOOST_MULT: 1.65, BOOST_COST: 6,
    MATCH_T: 300, LIVES: 3, KILL_PTS: 20, ABIL_CD: 60, ABIL_START: 20, ZONE_T: 10, STUCK_T: 10,
    FART_R: 76, PUKE_R: 68, SLOW_T: 3, SLOW_MULT: 0.5, TRIP_T: 7, MAX_PLAYERS: 4
  };

  // gun: interval s, speed px/s, dmg mass, br bullet radius, range px
  const CHARS = HW.CHARS = [
    {
      id: 'ben', name: 'BEN', big: true, startMass: 46, speed: 116, turn: 2.6, baseR: 8, eat: 24, ability: 'fart',
      colors: [['#f08a1c', '#ffd23f'], ['#e03c32', '#ffb0a8'], ['#d9d9e0', '#8d8fa0'], ['#b06a3a', '#e8b574']],
      blurb: 'BIG. SLOW. EATS FROM FAR AWAY.', stats: { size: 5, speed: 1, power: 4, rate: 2 },
      gun: { name: 'BURGER CANNON', desc: 'SLOW SHOTS. BIG FAST BULLETS.', interval: 0.85, speed: 520, dmg: 11, br: 5, range: 430, max: 16, pickup: 8, start: 8, pellets: 1, spread: 0.02, kind: 0 }
    },
    {
      id: 'chandler', name: 'CHANDLER', big: true, startMass: 40, speed: 130, turn: 2.9, baseR: 8, eat: 12, ability: 'fart',
      colors: [['#2b6fd6', '#7fc4ff'], ['#16a085', '#7dffd8'], ['#c0392b', '#ff9a8a'], ['#6c5ce7', '#c3b8ff']],
      blurb: 'BIG, BUT QUICKER THAN BEN.', stats: { size: 4, speed: 2, power: 4, rate: 2 },
      gun: { name: 'SODA SCATTERGUN', desc: '5 PELLET BLAST. DEADLY UP CLOSE, SHORT RANGE.', interval: 0.8, speed: 430, dmg: 4, br: 2, range: 190, max: 14, pickup: 7, start: 7, pellets: 5, spread: 0.5, kind: 1 }
    },
    {
      id: 'nate', name: 'NATE', big: false, startMass: 32, speed: 164, turn: 4.6, baseR: 6, eat: 10, ability: 'puke',
      colors: [['#7ed321', '#3d8b1f'], ['#f5d547', '#b8860b'], ['#ff8fd0', '#c2409a'], ['#59d9d9', '#1f7f8b']],
      blurb: 'SMALL, FAST AND TWITCHY.', stats: { size: 2, speed: 5, power: 2, rate: 5 },
      gun: { name: 'GUMBALL SMG', desc: 'SPRAYS FAST. BULLETS ARE SLOW AND WEAK.', interval: 0.1, speed: 290, dmg: 2.8, br: 2, range: 300, max: 150, pickup: 60, start: 70, pellets: 1, spread: 0.13, kind: 2 }
    },
    {
      id: 'wesley', name: 'WESLEY', big: false, startMass: 32, speed: 158, turn: 4.3, baseR: 6, eat: 10, ability: 'puke',
      colors: [['#9b5de5', '#ff7eb6'], ['#3ec1d3', '#f6f7d7'], ['#ff9a3c', '#ffe26a'], ['#5d6d7e', '#aeb6bf']],
      blurb: 'SMALL, FAST, SHARP SHOOTER.', stats: { size: 2, speed: 4, power: 3, rate: 3 },
      gun: { name: 'KEBAB SKEWER', desc: 'ACCURATE. PIERCES THROUGH WORMS.', interval: 0.42, speed: 450, dmg: 8, br: 3, range: 380, max: 40, pickup: 16, start: 20, pellets: 1, spread: 0.01, pierce: 3, kind: 3 }
    },
    {
      id: 'jeff', name: 'JEFF', big: true, startMass: 46, speed: 124, turn: 2.6, baseR: 8, eat: 12, ability: null, weakPuke: true,
      colors: [['#6b7a3a', '#3e4a22'], ['#8d6e63', '#4e342e'], ['#546e7a', '#263238'], ['#a67c00', '#5c4400']],
      blurb: 'NO ABILITY. FART AND PUKE BOTH KILL HIM.', stats: { size: 4, speed: 1, power: 5, rate: 1 },
      gun: { name: 'MEATBALL ROCKET', desc: 'HUGE BLAST RADIUS. FEW ROCKETS.', interval: 1.5, speed: 260, dmg: 24, br: 4, range: 400, max: 8, pickup: 3, start: 4, pellets: 1, spread: 0.01, blast: 80, accel: 380, vmax: 460, kind: 4 }
    }
  ];

  const rnd = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const angDiff = (a, b) => { let d = (a - b) % (Math.PI * 2); if (d > Math.PI) d -= Math.PI * 2; if (d < -Math.PI) d += Math.PI * 2; return d; };
  HW.util = { rnd, clamp, angDiff };

  HW.segCount = mass => clamp(Math.round(9 + mass * 0.42), 9, 240);
  HW.wormR = (ch, mass) => CHARS[ch].baseR + Math.min(5, Math.floor(mass / 90));

  // shared by host + client: make body points follow the head
  HW.follow = function (w) {
    const n = HW.segCount(w.mass), p = w.pts;
    while (p.length < n) { const l = p[p.length - 1]; p.push({ x: l.x, y: l.y }); }
    if (p.length > n) p.length = n;
    p[0].x = w.x; p[0].y = w.y;
    const SEG = CFG.SEG;
    let x0 = w.x, y0 = w.y, x1 = w.x, y1 = w.y;
    for (let i = 1; i < p.length; i++) {
      const a = p[i - 1], b = p[i]; const dx = b.x - a.x, dy = b.y - a.y; const d = Math.sqrt(dx * dx + dy * dy);
      if (d > SEG) { const k = SEG / d; b.x = a.x + dx * k; b.y = a.y + dy * k; }
      if (b.x < x0) x0 = b.x; else if (b.x > x1) x1 = b.x;
      if (b.y < y0) y0 = b.y; else if (b.y > y1) y1 = b.y;
    }
    w.bx0 = x0; w.by0 = y0; w.bx1 = x1; w.by1 = y1;
    w.r = HW.wormR(w.ch, w.mass);
  };

  function newState() {
    return { t: 0, worms: [], items: new Map(), bullets: [], zones: [], players: [], nextId: 1, events: [], adds: [], rems: [], respawns: [], botTimer: 0,
      comps: [], nextCid: 1, match: { t: CFG.MATCH_T, over: false, overT: 0, n: 1, reason: '' }, autoNext: 0 };
  }

  function Sim() {
    const S = this.S = newState();
    for (let i = 0; i < CFG.FOOD; i++) this.addFood();
    for (let i = 0; i < CFG.AMMO; i++) this.addItem('a', 0, rnd(80, CFG.W - 80), rnd(80, CFG.H - 80), 0);
    for (let i = 0; i < CFG.VEG; i++) this.addItem('v', (Math.random() * 5) | 0, rnd(120, CFG.W - 120), rnd(120, CFG.H - 120), 0);
    for (let i = 0; i < CFG.SHROOM; i++) this.addItem('m', (Math.random() * 2) | 0, rnd(120, CFG.W - 120), rnd(120, CFG.H - 120), 0);
    S.counts = { f: CFG.FOOD, a: CFG.AMMO, v: CFG.VEG, m: CFG.SHROOM };
    this.fillBots();
  }
  const P = Sim.prototype;

  P.ev = function (k, x, y) { const e = [k, Math.round(x), Math.round(y)]; for (let i = 3; i < arguments.length; i++) e.push(arguments[i]); this.S.events.push(e); };

  P.addItem = function (k, type, x, y, v) {
    const S = this.S; const it = { id: S.nextId++, k, type, x: clamp(x, 14, CFG.W - 14), y: clamp(y, 14, CFG.H - 14), v };
    S.items.set(it.id, it); S.adds.push(it); if (S.counts) S.counts[k]++; return it;
  };
  P.remItem = function (it) { const S = this.S; if (S.items.delete(it.id)) { S.rems.push(it.id); S.counts[it.k]--; } };
  P.addFood = function (x, y, v) {
    let type;
    if (v === undefined) { type = (Math.random() * HW.FOOD.length) | 0; v = HW.FOOD[type].v; }
    else {
      // choose a sprite that suits the value
      const want = v >= 3 ? 3 : v >= 2 ? 2 : 1; let tries = 0;
      do { type = (Math.random() * HW.FOOD.length) | 0; } while (HW.FOOD[type].v !== want && ++tries < 12);
    }
    return this.addItem('f', type, x === undefined ? rnd(30, CFG.W - 30) : x, y === undefined ? rnd(30, CFG.H - 30) : y, v);
  };
  // scatter `total` mass as food items around a point
  P.spill = function (x, y, total, spread) {
    while (total >= 1) {
      const v = total >= 9 ? 3 : total >= 4 ? 2 : 1; total -= v;
      const a = Math.random() * 6.283, d = Math.sqrt(Math.random()) * spread;
      this.addFood(x + Math.cos(a) * d, y + Math.sin(a) * d, v);
    }
  };

  P.spawnPos = function () {
    const S = this.S; let best = null, bestD = -Infinity; // -Infinity: a try next to a zone scores below zero and must still be usable
    for (let t = 0; t < 14; t++) {
      const x = rnd(200, CFG.W - 200), y = rnd(200, CFG.H - 200); let d = 1e9;
      for (const w of S.worms) { if (!w.alive) continue; for (let i = 0; i < w.pts.length; i += 6) { const q = (w.pts[i].x - x) ** 2 + (w.pts[i].y - y) ** 2; if (q < d) d = q; } }
      for (const z of S.zones) { const q = (z.x - x) ** 2 + (z.y - y) ** 2 - 200 * 200; if (q < d) d = q; }
      if (d > bestD) { bestD = d; best = { x, y }; }
      if (d > 300 * 300) break;
    }
    return best;
  };

  // Colour for a bot: the least used one that no human has claimed. Humans claim theirs in addPlayer
  // and keep it for as long as they are in the game (alive or waiting to respawn).
  P.pickVariant = function (ch, skip) {
    const S = this.S, used = [0, 0, 0, 0];
    for (const p of S.players) if (p.ch === ch && p.variant >= 0) used[p.variant] += 100;
    for (const w of S.worms) if (w.alive && w !== skip && w.isBot && w.ch === ch) used[w.variant & 3]++;
    let best = 0, bs = 1e9;
    for (let v = 0; v < 4; v++) { const q = used[v] + Math.random() * 0.5; if (q < bs) { bs = q; best = v; } }
    return best;
  };
  // Colour for a human: the lowest one no other human with the same worm holds (so P1 gets 0, P2 gets 1)
  P.claimVariant = function (p) {
    const taken = [0, 0, 0, 0]; for (const q of this.S.players) if (q !== p && q.ch === p.ch && q.variant >= 0) taken[q.variant] = 1;
    let v = 0; while (v < 3 && taken[v]) v++; return v;
  };

  P.spawnWorm = function (ch, pid) {
    const S = this.S, C = CHARS[ch], pos = this.spawnPos();
    const ang = Math.atan2(CFG.H / 2 - pos.y, CFG.W / 2 - pos.x) + rnd(-0.8, 0.8);
    let variant;
    if (pid < 0) variant = this.pickVariant(ch, null);
    else { const pl = S.players.find(q => q.pid === pid); if (pl && !(pl.variant >= 0)) pl.variant = this.claimVariant(pl); variant = pl ? pl.variant : 0; }
    const w = {
      id: S.nextId++, ch, variant, pid, isBot: pid < 0, x: pos.x, y: pos.y, ang, aim: ang,
      mass: C.startMass, pts: [], r: C.baseR, alive: true, shield: CFG.SHIELD, ammo: C.gun.start, cd: 1, // cd 1: no shot (and so no lost shield) in the first second, even with fire held
      abil: C.ability ? CFG.ABIL_START : 0, stuck: 0, pukeImm: 0, slow: 0, trip: 0, boosting: false, boostAcc: 0, kills: 0,
      inp: { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false }, bot: null
    };
    const n = HW.segCount(w.mass);
    for (let i = 0; i < n; i++) w.pts.push({ x: pos.x - Math.cos(ang) * i * 2, y: pos.y - Math.sin(ang) * i * 2 });
    HW.follow(w);
    if (w.isBot) w.bot = { think: Math.random() * 0.2, steer: ang, wander: ang, fireT: 0, skill: rnd(0.5, 1), aimErr: 0, burst: 0, panic: 0, abT: 0, abArm: false, mx: 0, my: 0 };
    if (!w.isBot) for (const o of S.worms) if (o.alive && o.isBot && o.ch === ch && o.variant === w.variant) o.variant = this.pickVariant(ch, o); // the human keeps their colour
    S.worms.push(w); this.ev('spawn', w.x, w.y, w.id);
    return w;
  };

  // ----- match: competitors, lives, score -----
  // Every seat in the arena is a competitor: one per human, the rest are bot seats that keep the
  // same worm for the whole match (bots respawn freely, humans have CFG.LIVES lives).
  P.newComp = function (pid, ch) {
    const S = this.S, c = { cid: S.nextCid++, pid, ch, variant: 0, kills: 0, peak: 0, score: 0, lives: CFG.LIVES, out: false, worm: null };
    S.comps.push(c); return c;
  };
  P.attach = function (c, w) { c.worm = w; w.comp = c; c.variant = w.variant; return w; };
  P.fillBots = function () {
    const S = this.S, want = Math.max(0, CFG.WORMS - S.players.length);
    let seats = S.comps.filter(c => c.pid < 0);
    while (seats.length < want) {
      // keep the roster varied: pick the least common character
      const cnt = [0, 0, 0, 0, 0]; for (const c of S.comps) cnt[c.ch]++;
      let ch = 0, b = 1e9; for (let i = 0; i < 5; i++) { const s = cnt[i] + Math.random() * 1.5; if (s < b) { b = s; ch = i; } }
      seats.push(this.newComp(-1, ch));
    }
    if (seats.length > want) {
      // a human took a seat: the lowest scoring bots leave
      seats.sort((a, b) => a.score - b.score);
      while (seats.length > want) { const c = seats.shift(); if (c.worm && c.worm.alive) this.kill(c.worm, null, 'left'); S.comps.splice(S.comps.indexOf(c), 1); }
    }
    if (S.match.over) return;
    for (const c of seats) if (!c.worm || !c.worm.alive) this.attach(c, this.spawnWorm(c.ch, -1));
  };
  P.board = function () { return this.S.comps.slice().sort((a, b) => b.score - a.score || b.kills - a.kills); };
  P.endMatch = function (reason) {
    const S = this.S, M = S.match; if (M.over) return;
    M.over = true; M.overT = 0; M.reason = reason; M.t = Math.max(0, M.t);
    this.ev('over', 0, 0, reason);
  };
  // next match: same arena and seats, everything else fresh
  P.restart = function () {
    const S = this.S;
    for (const w of S.worms) w.alive = false;
    S.worms.length = 0; S.bullets.length = 0; S.zones.length = 0;
    for (const c of S.comps) { c.kills = 0; c.peak = 0; c.score = 0; c.lives = CFG.LIVES; c.out = false; c.worm = null; }
    for (const p of S.players) { p.worm = null; p.deadT = 0; p.wantSpawn = true; p.everSpawned = false; p.lastKiller = ''; p.lastCause = ''; p.lastScore = 0; if (p.inp) p.inp.abil = false; }
    S.match = { t: CFG.MATCH_T, over: false, overT: 0, n: S.match.n + 1, reason: '' };
    S.botTimer = 0; this.ev('go', 0, 0);
  };

  // ----- players -----
  P.addPlayer = function (ch, conn) {
    const S = this.S; let pid = 0; while (S.players.some(p => p.pid === pid)) pid++;
    const p = { pid, ch, conn: conn || null, worm: null, deadT: 0, wantSpawn: true, inp: null, best: 0, lastKiller: '', lastCause: '', variant: -1 };
    S.players.push(p); p.variant = this.claimVariant(p);
    p.comp = this.newComp(pid, ch); p.comp.variant = p.variant;
    // the first human starts the match clock from the top
    if (S.players.length === 1 && !S.match.over) { S.match.t = CFG.MATCH_T; for (const c of S.comps) { c.kills = 0; c.peak = c.worm && c.worm.alive ? c.worm.mass : 0; c.score = Math.round(c.peak); } }
    this.fillBots(); // make room: a bot seat is given up for the human
    return p;
  };
  P.removePlayer = function (p) {
    const S = this.S; const i = S.players.indexOf(p); if (i >= 0) S.players.splice(i, 1);
    if (p.worm && p.worm.alive) this.kill(p.worm, null, 'left');
    const ci = S.comps.indexOf(p.comp); if (ci >= 0) S.comps.splice(ci, 1);
  };

  // ----- combat -----
  P.kill = function (w, killer, cause) {
    if (!w.alive) return; const S = this.S; w.alive = false;
    const total = w.mass * 0.8 + 4, n = Math.min(w.pts.length, 46), per = total / n;
    let acc = 0;
    for (let i = 0; i < n; i++) {
      acc += per; const v = Math.floor(acc); if (v < 1) continue; acc -= v;
      const p = w.pts[Math.floor(i * w.pts.length / n)];
      let rem = v; while (rem > 0) { const vv = rem >= 3 ? 3 : rem; rem -= vv; this.addFood(p.x + rnd(-9, 9), p.y + rnd(-9, 9), vv); }
    }
    if (killer && killer !== w && killer.alive) { killer.kills++; if (killer.comp && cause !== 'left') { killer.comp.kills++; killer.comp.score = Math.round(killer.comp.peak) + CFG.KILL_PTS * killer.comp.kills; } }
    if (w.pid >= 0 && w.comp && cause !== 'left') { w.comp.lives = Math.max(0, w.comp.lives - 1); if (w.comp.lives <= 0) w.comp.out = true; }
    const k = killer && killer !== w ? killer : null;
    this.ev('die', w.x, w.y, w.id, k ? k.id : 0, cause, w.ch, k ? k.ch : -1, w.pid, k ? k.pid : -1, w.variant, Math.round(w.mass));
    if (w.pid >= 0) { const p = S.players.find(q => q.pid === w.pid); if (p) { p.deadT = 0; p.wantSpawn = false; p.lastKiller = k ? CHARS[k.ch].name : ''; p.lastCause = cause; p.lastScore = p.comp ? p.comp.score : Math.round(w.mass); } }
  };
  P.damage = function (w, dmg, owner, x, y) {
    if (!w.alive || w.shield > 0) return;
    const loss = Math.min(w.mass, dmg + w.mass * 0.02);
    w.mass -= loss;
    this.spill(x, y, loss * 0.75, 26);
    this.ev('hit', x, y, w.id, Math.round(loss));
    if (w.bot) w.bot.panic = 1.2;
    if (w.mass < CFG.MIN_MASS) this.kill(w, owner, 'shot');
  };
  P.nearestSeg = function (w, x, y, maxD) { // squared distance to nearest segment (bbox prefilter)
    if (x < w.bx0 - maxD || x > w.bx1 + maxD || y < w.by0 - maxD || y > w.by1 + maxD) return 1e12;
    let best = 1e12; const p = w.pts;
    for (let i = 0; i < p.length; i++) { const dx = p[i].x - x, dy = p[i].y - y, q = dx * dx + dy * dy; if (q < best) best = q; }
    return best;
  };
  P.explode = function (b) {
    const S = this.S, g = CHARS[b.ch].gun, R = g.blast;
    for (const w of S.worms) {
      if (!w.alive || w.id === b.owner || w.shield > 0) continue;
      const q = this.nearestSeg(w, b.x, b.y, R + w.r); const d = Math.sqrt(q) - w.r;
      if (d < R) { const f = 1 - clamp(d / R, 0, 1) * 0.65; const p = this.hitPoint(w, b.x, b.y); this.damage(w, g.dmg * f, S.worms.find(o => o.id === b.owner), p.x, p.y); }
    }
    this.ev('boom', b.x, b.y, R);
  };
  P.hitPoint = function (w, x, y) { let best = w.pts[0], bq = 1e12; for (const p of w.pts) { const q = (p.x - x) ** 2 + (p.y - y) ** 2; if (q < bq) { bq = q; best = p; } } return best; };

  P.fire = function (w) {
    const S = this.S, g = CHARS[w.ch].gun;
    // w.cd sits in (-dt, 0] when a shot is due: carry the remainder so the average cadence is exactly g.interval
    w.cd = g.interval + (w.cd > -0.05 ? w.cd : 0); w.ammo--; w.shield = 0;
    const mz = w.r + 6 + HW.gunSpr[w.ch].len, ca = Math.cos(w.aim), sa = Math.sin(w.aim);
    const mx = w.x + ca * mz, my = w.y + sa * mz;
    // Bullets leave from the muzzle, which is well in front of the head. If something is already
    // between the head and the muzzle (a body brushing past), start there so the shot cannot skip it.
    let bx = mx, by = my;
    scan: for (let d = w.r; d < mz; d += 4) {
      const x = w.x + ca * d, y = w.y + sa * d;
      for (const o of S.worms) {
        if (o === w || !o.alive || o.shield > 0) continue;
        const lim = g.br + o.r; if (this.nearestSeg(o, x, y, lim) <= lim * lim) { bx = x - ca * 2; by = y - sa * 2; break scan; }
      }
    }
    // rockets speed up as they fly, so their lifetime is worked out from the range they should cover
    let life = g.range / g.speed;
    if (g.accel) { const t1 = (g.vmax - g.speed) / g.accel, d1 = g.speed * t1 + 0.5 * g.accel * t1 * t1; life = g.range >= d1 ? t1 + (g.range - d1) / g.vmax : (Math.sqrt(g.speed * g.speed + 2 * g.accel * g.range) - g.speed) / g.accel; }
    for (let i = 0; i < g.pellets; i++) {
      const a = w.aim + (g.pellets > 1 ? (i / (g.pellets - 1) - 0.5) * g.spread + rnd(-0.04, 0.04) : rnd(-g.spread, g.spread));
      const sp = g.speed * (g.pellets > 1 ? rnd(0.85, 1.1) : 1);
      S.bullets.push({ id: S.nextId++, ch: w.ch, owner: w.id, x: bx, y: by, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life, hit: null, pierce: g.pierce || 0, c: (Math.random() * 5) | 0 });
    }
    this.ev('shot', mx, my, w.ch, w.id);
  };
  P.useAbility = function (w) {
    const S = this.S, C = CHARS[w.ch]; if (!C.ability || w.abil > 0 || w.stuck > 0) return;
    w.abil = CFG.ABIL_CD; w.shield = 0;
    if (C.ability === 'fart') {
      // comes out the back: a little behind the head so it guards you (see NOTES)
      const i = Math.min(w.pts.length - 1, 16), p = w.pts[i];
      S.zones.push({ id: S.nextId++, k: 0, x: p.x, y: p.y, r: CFG.FART_R, t: CFG.ZONE_T, owner: w.id });
      this.ev('fart', p.x, p.y, w.id);
    } else {
      const d = w.r + CFG.PUKE_R + 14, x = clamp(w.x + Math.cos(w.aim) * d, 0, CFG.W), y = clamp(w.y + Math.sin(w.aim) * d, 0, CFG.H);
      S.zones.push({ id: S.nextId++, k: 1, x, y, r: CFG.PUKE_R, t: CFG.ZONE_T, owner: w.id });
      this.ev('puke', x, y, w.id, Math.round(w.aim * 100));
    }
  };

  // nearest enemy for keyboard / trigger auto-aim
  P.autoAim = function (w) {
    const g = CHARS[w.ch].gun, R = Math.min(g.range, 300); let best = null, bs = 1e9;
    for (const o of this.S.worms) {
      if (o === w || !o.alive || o.shield > 0) continue;
      if (w.x < o.bx0 - R || w.x > o.bx1 + R || w.y < o.by0 - R || w.y > o.by1 + R) continue;
      for (let i = 0; i < o.pts.length; i += 3) {
        const dx = o.pts[i].x - w.x, dy = o.pts[i].y - w.y, d = Math.sqrt(dx * dx + dy * dy); if (d > R) continue;
        const da = Math.abs(angDiff(Math.atan2(dy, dx), w.ang)); if (da > 0.95) continue;
        const s = d * (1 + da * 1.5) * (i === 0 ? 0.8 : 1); if (s < bs) { bs = s; best = Math.atan2(dy, dx); }
      }
    }
    return best;
  };

  // ----- main step -----
  P.step = function (dt) {
    const S = this.S, M = S.match; S.t += dt;
    // match clock: only runs while a human is playing; the arena freezes on the final whistle
    if (M.over) { M.overT += dt; for (const p of S.players) p.deadT += dt; if (S.autoNext && M.overT >= S.autoNext) this.restart(); return; }
    if (S.players.length) {
      M.t -= dt;
      if (M.t <= 0) { this.endMatch('time'); return; }
      if (S.players.every(p => p.comp.out && p.deadT > 1.6)) { this.endMatch('lives'); return; }
    }
    // players: respawn handling
    for (const p of S.players) {
      if (!p.worm || !p.worm.alive) {
        p.deadT += dt;
        if (p.comp.out) p.wantSpawn = false;
        else if (p.wantSpawn && (p.deadT > 1 || !p.worm)) { p.worm = this.attach(p.comp, this.spawnWorm(p.ch, p.pid)); p.wantSpawn = false; p.everSpawned = true; }
      } else { if (p.inp) p.worm.inp = p.inp; }
      if (p.comp.score > p.best) p.best = p.comp.score;
    }
    for (const c of S.comps) { const w = c.worm; if (w && w.alive && w.mass > c.peak) { c.peak = w.mass; c.score = Math.round(c.peak) + CFG.KILL_PTS * c.kills; } }
    // bot respawns
    S.botTimer -= dt; if (S.botTimer <= 0) { S.botTimer = 0.8; this.fillBots(); }

    for (const w of S.worms) {
      if (!w.alive) continue;
      if (w.bot) HW.botThink(this, w, dt);
      const C = CHARS[w.ch], I = w.inp;
      // steering
      const mm = I.mx * I.mx + I.my * I.my;
      if (mm > 0.04) {
        let ta = Math.atan2(I.my, I.mx); if (w.trip > 0 && w.bot) ta += Math.sin(S.t * 3 + w.id) * 0.9;
        const d = angDiff(ta, w.ang), mt = C.turn * dt * (w.slow > 0 ? 0.8 : 1);
        w.ang += clamp(d, -mt, mt);
      }
      // aim
      if (I.ax * I.ax + I.ay * I.ay > 0.09) w.aim = Math.atan2(I.ay, I.ax);
      else { let a = null; if (I.auto && I.fire) a = this.autoAim(w); if (a === null) a = w.ang; w.aim += clamp(angDiff(a, w.aim), -14 * dt, 14 * dt); }
      // timers
      if (w.shield > 0) w.shield -= dt; if (w.cd > 0) w.cd -= dt; if (w.abil > 0) w.abil -= dt;
      if (w.slow > 0) w.slow -= dt; if (w.trip > 0) w.trip -= dt; if (w.pukeImm > 0) w.pukeImm -= dt;
      // move
      let sp = C.speed;
      w.boosting = !!(I.boost && w.mass > CFG.MIN_MASS + 4 && w.stuck <= 0);
      if (w.boosting) {
        sp *= CFG.BOOST_MULT; const c = CFG.BOOST_COST * dt; w.mass -= c; w.boostAcc += c * 0.6;
        if (w.boostAcc >= 1) { w.boostAcc -= 1; const tl = w.pts[w.pts.length - 1]; this.addFood(tl.x + rnd(-4, 4), tl.y + rnd(-4, 4), 1); }
      }
      if (w.slow > 0) sp *= CFG.SLOW_MULT;
      if (w.stuck > 0) { w.stuck -= dt; sp = 0; }
      const nx = w.x + Math.cos(w.ang) * sp * dt, ny = w.y + Math.sin(w.ang) * sp * dt;
      w.x = clamp(nx, w.r, CFG.W - w.r); w.y = clamp(ny, w.r, CFG.H - w.r);
      // walls don't kill: the worm slides and its nose is nudged along the wall
      if (w.x !== nx) { const tg = Math.sin(w.ang) >= 0 ? Math.PI / 2 : -Math.PI / 2; w.ang += clamp(angDiff(tg, w.ang), -5 * dt, 5 * dt); }
      if (w.y !== ny) { const tg = Math.cos(w.ang) >= 0 ? 0 : Math.PI; w.ang += clamp(angDiff(tg, w.ang), -5 * dt, 5 * dt); }
      HW.follow(w);
      // fire / ability
      if (I.fire && w.cd <= 0) { if (w.ammo > 0) this.fire(w); else if (!w.dryT || S.t - w.dryT > 0.5) { w.dryT = S.t; this.ev('dry', w.x, w.y, w.id); } }
      if (I.abil) { I.abil = false; this.useAbility(w); }
    }

    // items
    const eatList = [];
    for (const it of S.items.values()) {
      for (const w of S.worms) {
        if (!w.alive) continue;
        const dx = w.x - it.x, dy = w.y - it.y; if (dx > 70 || dx < -70 || dy > 70 || dy < -70) continue;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (it.k === 'f') {
          const er = w.r + CHARS[w.ch].eat;
          if (d < w.r + 3) { eatList.push(it, w); break; }
          if (d < er) { const k = Math.min(1, 300 * dt / d); it.x += dx * k; it.y += dy * k; }
        } else if (d < w.r + (it.k === 'a' ? 9 : 7)) { eatList.push(it, w); break; }
      }
    }
    for (let i = 0; i < eatList.length; i += 2) {
      const it = eatList[i], w = eatList[i + 1]; if (!S.items.has(it.id)) continue;
      this.remItem(it);
      if (it.k === 'f') { w.mass += it.v; this.ev('eat', it.x, it.y, w.id, it.v); }
      else if (it.k === 'a') { const g = CHARS[w.ch].gun; w.ammo = Math.min(g.max, w.ammo + g.pickup); this.ev('ammo', it.x, it.y, w.id); S.respawns.push({ k: 'a', t: 7 }); }
      else if (it.k === 'v') { if (w.shield <= 0) { w.slow = CFG.SLOW_T; this.ev('veg', it.x, it.y, w.id); } S.respawns.push({ k: 'v', t: 5 }); }
      else if (it.k === 'm') { if (w.shield <= 0) { w.trip = CFG.TRIP_T; this.ev('shroom', it.x, it.y, w.id); } S.respawns.push({ k: 'm', t: 8 }); }
    }
    for (let i = S.respawns.length - 1; i >= 0; i--) {
      const r = S.respawns[i]; r.t -= dt; if (r.t > 0) continue; S.respawns.splice(i, 1);
      this.addItem(r.k, r.k === 'v' ? (Math.random() * 5) | 0 : r.k === 'm' ? (Math.random() * 2) | 0 : 0, rnd(100, CFG.W - 100), rnd(100, CFG.H - 100), 0);
    }
    if (S.counts.f < CFG.FOOD && Math.random() < dt * 14) this.addFood();
    if (S.counts.f > 1100) {
      // too much litter: clear the oldest crumbs first, then anything, so the cap always holds
      let n = 0; for (const it of S.items.values()) { if (it.k === 'f' && it.v === 1) { this.remItem(it); if (++n > 20) break; } }
      if (n === 0) for (const it of S.items.values()) { if (it.k === 'f') { this.remItem(it); if (++n > 20) break; } }
    }

    // head vs body. Every touch is collected first and judged afterwards, so the outcome never
    // depends on the order worms happen to be stored in.
    const touch = this.touch || (this.touch = []); touch.length = 0;
    for (const a of S.worms) {
      if (!a.alive || a.shield > 0) continue;
      for (const b of S.worms) {
        if (b === a || !b.alive || b.shield > 0) continue;
        const m = a.r + b.r;
        if (a.x < b.bx0 - m || a.x > b.bx1 + m || a.y < b.by0 - m || a.y > b.by1 + m) continue;
        // the part of b that a's head is closest to decides what was hit: b's head (0) or its body
        const p = b.pts; let hit = -1, hq = (a.r * 0.78 + b.r * 0.82) ** 2;
        for (let i = 0; i < p.length; i++) { const dx = p[i].x - a.x, dy = p[i].y - a.y, q = dx * dx + dy * dy; if (q < hq) { hq = q; hit = i; } }
        if (hit >= 0) touch.push(a, b, hit);
      }
    }
    if (touch.length) {
      const dead = [];
      const mark = (w, by, cause) => { for (let i = 0; i < dead.length; i += 3) if (dead[i] === w) return; dead.push(w, by, cause); };
      // 1) a head that ran into a body dies, whatever else is going on
      for (let i = 0; i < touch.length; i += 3) if (touch[i + 2] > 0) mark(touch[i], touch[i + 1], 'crash');
      // 2) head against head: the lighter worm dies, equal worms both die. A worm that has just
      //    crashed into a body has already lost: it cannot also win (or lose) a head-on this step.
      const n = dead.length;
      for (let i = 0; i < touch.length; i += 3) {
        if (touch[i + 2] !== 0) continue; const a = touch[i], b = touch[i + 1];
        let out = false; for (let k = 0; k < n; k += 3) if (dead[k] === a || dead[k] === b) { out = true; break; }
        if (out) continue;
        if (a.mass <= b.mass) mark(a, b, 'bonk');
        if (b.mass <= a.mass) mark(b, a, 'bonk');
      }
      for (let i = 0; i < dead.length; i += 3) this.kill(dead[i], dead[i + 1], dead[i + 2]);
    }

    // zones
    for (let i = S.zones.length - 1; i >= 0; i--) {
      const z = S.zones[i]; z.t -= dt; if (z.t <= 0) { S.zones.splice(i, 1); continue; }
      const owner = S.worms.find(o => o.id === z.owner);
      for (const w of S.worms) {
        if (!w.alive || w.id === z.owner || w.shield > 0) continue;
        const dx = w.x - z.x, dy = w.y - z.y; if (dx * dx + dy * dy > (z.r - 4) * (z.r - 4)) continue;
        if (z.k === 0) this.kill(w, owner, 'fart');
        else if (CHARS[w.ch].weakPuke) this.kill(w, owner, 'puke');
        else if (w.stuck <= 0 && w.pukeImm <= 0) { w.stuck = CFG.STUCK_T; w.pukeImm = CFG.STUCK_T + 2.5; this.ev('stuck', w.x, w.y, w.id); }
      }
    }

    // bullets
    for (let i = S.bullets.length - 1; i >= 0; i--) {
      const b = S.bullets[i], g = CHARS[b.ch].gun; let dead = false;
      if (g.accel) { const v = Math.sqrt(b.vx * b.vx + b.vy * b.vy), nv = Math.min(g.vmax, v + g.accel * dt); if (v > 0) { b.vx *= nv / v; b.vy *= nv / v; } }
      const steps = 2;
      for (let s = 0; s < steps && !dead; s++) {
        b.x += b.vx * dt / steps; b.y += b.vy * dt / steps;
        if (b.x < 0 || b.y < 0 || b.x > CFG.W || b.y > CFG.H) { dead = true; break; }
        for (const w of S.worms) {
          if (!w.alive || w.id === b.owner || w.shield > 0) continue;
          if (b.hit && b.hit.indexOf(w.id) >= 0) continue;
          const lim = g.br + w.r; if (this.nearestSeg(w, b.x, b.y, lim) > lim * lim) continue;
          if (g.blast) { dead = true; break; }
          this.damage(w, g.dmg, S.worms.find(o => o.id === b.owner), b.x, b.y);
          if (b.pierce > 0) { b.pierce--; (b.hit = b.hit || []).push(w.id); } else { dead = true; break; }
        }
      }
      b.life -= dt; if (b.life <= 0) dead = true;
      if (dead) { if (g.blast) this.explode(b); else this.ev('puff', b.x, b.y, b.ch); S.bullets.splice(i, 1); }
    }

    // prune dead worms
    for (let i = S.worms.length - 1; i >= 0; i--) if (!S.worms[i].alive) S.worms.splice(i, 1);
  };

  HW.Sim = Sim;
})(window.HW);
