// Hangry Worms - game simulation (host-authoritative; also used for local play)
'use strict';
(function (HW) {
  const MAP = HW.MAP;
  const CFG = HW.CFG = {
    W: MAP.W, H: MAP.H, SEG: 6, WORMS: 12, FOOD: 210, AMMO: 14, VEG: 15, SHROOM: 7,
    MIN_MASS: 6, SHIELD: 4, BOOST_MULT: 1.55, BOOST_COST: 6,
    MATCH_T: 300, LIVES: 3, KILL_PTS: 20, ABIL_CD: 60, ABIL_START: 20, ZONE_T: 10, STUCK_T: 10,
    FART_R: 76, PUKE_R: 68, SLOW_T: 4.5, SLOW_MULT: 0.5, VEG_LOSS: 0.1, TRIP_T: 10, MAX_PLAYERS: 4,
    VEG_ABIL: 10, SHROOM_ABIL: 15,   // the upside of eating your greens: seconds knocked off the fart / puke countdown
    CRASH_T: 0.4,                    // seconds you must keep driving into another worm before it kills you (see "head vs body" in step)
    BIG: 3              // food worth this much or more is drawn double size
  };
  // what a snack / meal / feast is worth (FOOD[].v in sprites.js is the class: 1, 2 or 3)
  const FOODV = HW.FOODV = [0, 3, 5, 8];

  // Bot difficulty. skill: range each bot's skill is drawn from (0..1). think / err / rest / lapse multiply
  // thinking time, aim error, the pause between bursts and how often attention wanders. engage: furthest
  // a bot opens fire from. dodge / abil: how reliably it sidesteps shots and uses its ability.
  // mercy: seconds after a human's spawn shield that bots still leave them alone. warm: seconds at the
  // start of a match in which bots do not attack humans at all. lead: how well it leads a moving target.
  HW.DIFFS = [
    { name: 'EASY', skill: [0.15, 0.5], think: 1.5, engage: 120, err: 1.7, rest: 2.2, lapse: 2.2, dodge: 0.4, abil: 0.35, mercy: 5, warm: 30, lead: 0 },
    { name: 'INTERMEDIATE', skill: [0.45, 0.9], think: 1, engage: 165, err: 1, rest: 1, lapse: 1, dodge: 1, abil: 1, mercy: 2, warm: 12, lead: 0.3 },
    { name: 'HARD', skill: [0.8, 1], think: 0.8, engage: 215, err: 0.55, rest: 0.55, lapse: 0.3, dodge: 1.3, abil: 1, mercy: 0, warm: 0, lead: 1 }
  ];

  // gun: interval s, speed px/s, dmg mass, br bullet radius, range px
  const CHARS = HW.CHARS = [
    {
      id: 'ben', name: 'BEN', big: true, startMass: 48, speed: 104, turn: 2.7, baseR: 8, eat: 30, ability: 'fart',
      colors: [['#f08a1c', '#ffd23f'], ['#e03c32', '#ffb0a8'], ['#d9d9e0', '#8d8fa0'], ['#b06a3a', '#e8b574']],
      blurb: 'BIG. SLOW. EATS FROM FAR AWAY.', stats: { size: 5, speed: 1, power: 4, rate: 2 },
      gun: { name: 'BURGER CANNON', desc: 'SLOW SHOTS. BIG FAST BULLETS.', interval: 0.9, speed: 440, dmg: 14, br: 5, range: 430, max: 18, pickup: 9, start: 9, pellets: 1, spread: 0.02, kind: 0 }
    },
    {
      id: 'chandler', name: 'CHANDLER', big: true, startMass: 40, speed: 110, turn: 2.9, baseR: 8, eat: 15, ability: 'fart',
      colors: [['#2b6fd6', '#7fc4ff'], ['#16a085', '#7dffd8'], ['#c0392b', '#ff9a8a'], ['#6c5ce7', '#c3b8ff']],
      blurb: 'BIG, BUT QUICKER THAN BEN.', stats: { size: 4, speed: 2, power: 4, rate: 2 },
      gun: { name: 'SODA SCATTERGUN', desc: '5 PELLET BLAST. DEADLY UP CLOSE, SHORT RANGE.', interval: 0.95, speed: 370, dmg: 4, br: 2, range: 185, max: 14, pickup: 7, start: 7, pellets: 5, spread: 0.5, kind: 1 }
    },
    {
      id: 'nate', name: 'NATE', big: false, startMass: 32, speed: 130, turn: 4.4, baseR: 6, eat: 13, ability: 'puke',
      colors: [['#7ed321', '#3d8b1f'], ['#f5d547', '#b8860b'], ['#ff8fd0', '#c2409a'], ['#59d9d9', '#1f7f8b']],
      blurb: 'SMALL, FAST AND TWITCHY.', stats: { size: 2, speed: 5, power: 2, rate: 5 },
      gun: { name: 'GUMBALL SMG', desc: 'SPRAYS FAST. BULLETS ARE SLOW AND WEAK.', interval: 0.13, speed: 250, dmg: 2.6, br: 2, range: 290, max: 110, pickup: 45, start: 50, pellets: 1, spread: 0.13, kind: 2 }
    },
    {
      id: 'wesley', name: 'WESLEY', big: false, startMass: 34, speed: 128, turn: 4.3, baseR: 6, eat: 13, ability: 'puke',
      colors: [['#9b5de5', '#ff7eb6'], ['#3ec1d3', '#f6f7d7'], ['#ff9a3c', '#ffe26a'], ['#5d6d7e', '#aeb6bf']],
      blurb: 'SMALL, FAST, SHARP SHOOTER.', stats: { size: 2, speed: 4, power: 3, rate: 3 },
      gun: { name: 'KEBAB SKEWER', desc: 'ACCURATE. PIERCES THROUGH WORMS.', interval: 0.48, speed: 390, dmg: 10, br: 3, range: 390, max: 40, pickup: 16, start: 20, pellets: 1, spread: 0.01, pierce: 3, kind: 3 }
    },
    {
      id: 'jeff', name: 'JEFF', big: true, startMass: 46, speed: 104, turn: 2.6, baseR: 8, eat: 15, ability: null, weakPuke: true,
      colors: [['#6b7a3a', '#3e4a22'], ['#8d6e63', '#4e342e'], ['#546e7a', '#263238'], ['#a67c00', '#5c4400']],
      blurb: 'NO ABILITY. FART AND PUKE BOTH KILL HIM.', stats: { size: 4, speed: 1, power: 5, rate: 1 },
      gun: { name: 'MEATBALL ROCKET', desc: 'HUGE BLAST RADIUS. FEW ROCKETS.', interval: 1.7, speed: 220, dmg: 24, br: 4, range: 400, max: 8, pickup: 3, start: 4, pellets: 1, spread: 0.01, blast: 80, accel: 320, vmax: 390, kind: 4 }
    }
  ];

  // worm paint jobs live with the art (sprites.js): HW.SKINS[ch].colors replaces the colours above when present
  if (HW.SKINS) CHARS.forEach((c, i) => { if (HW.SKINS[i] && HW.SKINS[i].colors) c.colors = HW.SKINS[i].colors; });

  // every gun there is, by kind: the five character guns, then the special guns you pick up (power.js).
  // A bullet's ch field is its gun's kind.
  const SGUNS = HW.SGUNS || [], POWERS = HW.POWERS || [], PCFG = HW.PCFG || {};
  const GUNS = HW.GUNS = CHARS.map(c => c.gun).concat(SGUNS);
  HW.gunOf = w => w.sg ? SGUNS[w.sg - 1] : CHARS[w.ch].gun;                 // the gun a worm is holding right now
  HW.gunSprOf = w => w.sg ? HW.sgunSpr[w.sg - 1] : HW.gunSpr[w.ch];

  const rnd = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const angDiff = (a, b) => { let d = (a - b) % (Math.PI * 2); if (d > Math.PI) d -= Math.PI * 2; if (d < -Math.PI) d += Math.PI * 2; return d; };
  HW.util = { rnd, clamp, angDiff };

  HW.segCount = mass => clamp(Math.round(9 + mass * 0.42), 9, 240);
  HW.wormR = (ch, mass, big) => { const r = CHARS[ch].baseR + Math.min(5, Math.floor(mass / 90)); return big ? Math.round(r * POWERS[1].scale) : r; };

  const PT = { x: 0, y: 0, nx: 0, ny: 0 };   // scratch for MAP.push
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
      if (MAP.push(b.x, b.y, 3, PT)) { b.x = PT.x; b.y = PT.y; }   // bodies bend round obstacles instead of cutting through the corners
      if (b.x < x0) x0 = b.x; else if (b.x > x1) x1 = b.x;
      if (b.y < y0) y0 = b.y; else if (b.y > y1) y1 = b.y;
    }
    w.bx0 = x0; w.by0 = y0; w.bx1 = x1; w.by1 = y1;
    w.r = HW.wormR(w.ch, w.mass, w.big > 0);
  };

  // ---- head movement. Shared by the host's step and by an online client predicting its own worm (net.js),
  // so both must go through these three functions and nothing else. ----
  // turn towards the stick. t: sim time (the mushroom weave runs on it)
  HW.turnHead = function (w, I, dt, t, isBot) {
    if (I.mx * I.mx + I.my * I.my <= 0.04) return;
    let ta = Math.atan2(I.my, I.mx); if (w.trip > 0) ta += Math.sin(t * 3 + w.id) * (isBot ? 0.9 : 0.45);   // mushrooms: you weave
    const mt = CHARS[w.ch].turn * dt * (w.slow > 0 ? 0.8 : 1);
    w.ang += clamp(angDiff(ta, w.ang), -mt, mt);
  };
  // px/s right now (w.boosting must already be decided)
  HW.headSpeed = function (w) {
    if (w.stuck > 0) return 0;
    let sp = CHARS[w.ch].speed * (w.boosting ? CFG.BOOST_MULT : 1) * (w.slow > 0 ? CFG.SLOW_MULT : 1);
    if (w.rage > 0) sp *= POWERS[0].speed;                    // rampage
    if (w.chill > 0) sp *= PCFG.CHILL_MULT;                   // hit by the freeze ray
    if (w.boosting && w.sauce > 0) sp *= POWERS[3].boost;     // hot sauce
    return sp;
  };
  // advance the head. Walls and obstacles do not kill: the worm slides and its nose is nudged along the surface.
  HW.moveHead = function (w, sp, dt) {
    const nx = w.x + Math.cos(w.ang) * sp * dt, ny = w.y + Math.sin(w.ang) * sp * dt;
    w.x = clamp(nx, w.r, CFG.W - w.r); w.y = clamp(ny, w.r, CFG.H - w.r);
    if (w.x !== nx) { const tg = Math.sin(w.ang) >= 0 ? Math.PI / 2 : -Math.PI / 2; w.ang += clamp(angDiff(tg, w.ang), -5 * dt, 5 * dt); }
    if (w.y !== ny) { const tg = Math.cos(w.ang) >= 0 ? 0 : Math.PI; w.ang += clamp(angDiff(tg, w.ang), -5 * dt, 5 * dt); }
    if (MAP.push(w.x, w.y, w.r, PT)) {
      w.x = clamp(PT.x, w.r, CFG.W - w.r); w.y = clamp(PT.y, w.r, CFG.H - w.r);
      const side = Math.cos(w.ang) * -PT.ny + Math.sin(w.ang) * PT.nx >= 0 ? 1 : -1, tg = Math.atan2(PT.nx * side, -PT.ny * side);
      w.ang += clamp(angDiff(tg, w.ang), -5 * dt, 5 * dt);
    }
  };

  // per-competitor counters for the end-of-match awards
  const newStats = () => ({ veg: 0, shr: 0, shots: 0, hits: 0, pick: 0, boost: 0, taunt: 0, streak: 0 });
  function newState() {
    return { t: 0, worms: [], items: new Map(), bullets: [], zones: [], players: [], nextId: 1, events: [], adds: [], rems: [], respawns: [], botTimer: 0,
      comps: [], nextCid: 1, match: { t: CFG.MATCH_T, over: false, overT: 0, n: 1, reason: '', frenzy: false, awards: [] }, autoNext: 0, leader: 0 };
  }

  // opt.diff: bot difficulty, an index into HW.DIFFS (default 1)
  function Sim(opt) {
    const S = this.S = newState();
    S.diff = clamp((opt && opt.diff) | 0, 0, HW.DIFFS.length - 1); if (!opt || opt.diff === undefined) S.diff = 1;
    for (let i = 0; i < CFG.FOOD; i++) this.addFood();
    for (let i = 0; i < CFG.AMMO; i++) this.dropItem('a');
    for (let i = 0; i < CFG.VEG; i++) this.dropItem('v');
    for (let i = 0; i < CFG.SHROOM; i++) this.dropItem('m');
    S.counts = { f: CFG.FOOD, a: CFG.AMMO, v: CFG.VEG, m: CFG.SHROOM, p: 0, g: 0, x: 0 };
    this.stockPickups();
    this.fillBots();
  }
  const P = Sim.prototype;
  // a crate, veggie or mushroom somewhere free. Nearly half the veggies turn up in the salad bar.
  P.dropItem = function (k) {
    const p = MAP.spot(k === 'a' ? 80 : 120, 26, k === 'v' && Math.random() < 0.45 ? MAP.zones[2] : null);
    let type = 0;
    if (k === 'v') type = (Math.random() * HW.vegSpr.length) | 0; else if (k === 'm') type = (Math.random() * HW.shroomSpr.length) | 0;
    else if (k === 'g') type = (Math.random() * SGUNS.length) | 0;
    else if (k === 'p') { type = (Math.random() * POWERS.length) | 0; if (type === 0 && Math.random() < 0.35) type = 1 + ((Math.random() * (POWERS.length - 1)) | 0); }   // the pizza is the rare one
    const it = this.addItem(k, type, p.x, p.y, k === 'x' ? HW.GOLD.v : 0);
    if (k === 'p' || k === 'g' || k === 'x') this.ev('drop', it.x, it.y, k, type);
    return it;
  };
  // power-ups, special guns and the golden burger do not start on the map: they turn up over the first half minute
  P.stockPickups = function () {
    const S = this.S; if (!POWERS.length) return;
    S.respawns = S.respawns.filter(r => r.k !== 'p' && r.k !== 'g' && r.k !== 'x');
    for (let i = S.counts.p; i < PCFG.POWERS; i++) S.respawns.push({ k: 'p', t: rnd(8, 28) });
    for (let i = S.counts.g; i < PCFG.GUNS; i++) S.respawns.push({ k: 'g', t: rnd(6, 24) });
    if (!S.counts.x) S.respawns.push({ k: 'x', t: rnd(20, 40) });
  };

  P.ev = function (k, x, y) { const e = [k, Math.round(x), Math.round(y)]; for (let i = 3; i < arguments.length; i++) e.push(arguments[i]); this.S.events.push(e); };

  P.addItem = function (k, type, x, y, v) {
    const S = this.S; x = clamp(x, 14, CFG.W - 14); y = clamp(y, 14, CFG.H - 14);
    if (MAP.push(x, y, 12, PT)) { x = clamp(PT.x, 14, CFG.W - 14); y = clamp(PT.y, 14, CFG.H - 14); }   // nothing lands inside an obstacle
    const it = { id: S.nextId++, k, type, x, y, v };
    S.items.set(it.id, it); S.adds.push(it); if (S.counts) S.counts[k]++; return it;
  };
  P.remItem = function (it) { const S = this.S; if (S.items.delete(it.id)) { S.rems.push(it.id); S.counts[it.k]--; } };
  P.addFood = function (x, y, v) {
    let type;
    if (v === undefined) { type = (Math.random() * HW.FOOD.length) | 0; v = FOODV[HW.FOOD[type].v]; }
    else {
      // choose a sprite that suits the value
      const want = v >= 7 ? 3 : v >= 4 ? 2 : 1; let tries = 0;
      do { type = (Math.random() * HW.FOOD.length) | 0; } while (HW.FOOD[type].v !== want && ++tries < 12);
    }
    if (x === undefined) { const p = MAP.spot(30, 14); x = p.x; y = p.y; }
    return this.addItem('f', type, x, y, v);
  };
  // scatter `total` mass as food items around a point
  P.spill = function (x, y, total, spread) {
    while (total >= 1) {
      const v = total >= 10 ? 5 : total >= 3 ? 3 : 1; total -= v;
      const a = Math.random() * 6.283, d = Math.sqrt(Math.random()) * spread;
      this.addFood(x + Math.cos(a) * d, y + Math.sin(a) * d, v);
    }
  };

  P.spawnPos = function (human) {
    const S = this.S; let best = null, bestD = -Infinity; // -Infinity: a try next to a zone scores below zero and must still be usable
    const tries = human ? 40 : 14, room = human ? 460 : 300;   // a human is dropped somewhere quiet
    for (let t = 0; t < tries; t++) {
      const sp = MAP.spot(200, 40), x = sp.x, y = sp.y; let d = 1e9;
      for (const w of S.worms) { if (!w.alive) continue; for (let i = 0; i < w.pts.length; i += 6) { const q = (w.pts[i].x - x) ** 2 + (w.pts[i].y - y) ** 2; if (q < d) d = q; } }
      for (const z of S.zones) { const q = (z.x - x) ** 2 + (z.y - y) ** 2 - 200 * 200; if (q < d) d = q; }
      if (d > bestD) { bestD = d; best = { x, y }; }
      if (d > room * room) break;
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
    const S = this.S, C = CHARS[ch], pos = this.spawnPos(pid >= 0);
    const ang = Math.atan2(CFG.H / 2 - pos.y, CFG.W / 2 - pos.x) + rnd(-0.8, 0.8);
    let variant;
    if (pid < 0) variant = this.pickVariant(ch, null);
    else { const pl = S.players.find(q => q.pid === pid); if (pl && !(pl.variant >= 0)) pl.variant = this.claimVariant(pl); variant = pl ? pl.variant : 0; }
    const w = {
      id: S.nextId++, ch, variant, pid, isBot: pid < 0, x: pos.x, y: pos.y, ang, aim: ang,
      mass: C.startMass, pts: [], r: C.baseR, alive: true, shield: CFG.SHIELD, ammo: C.gun.start, cd: 1, // cd 1: no shot (and so no lost shield) in the first second, even with fire held
      abil: C.ability ? CFG.ABIL_START : 0, stuck: 0, pukeImm: 0, slow: 0, trip: 0, boosting: false, boostAcc: 0, kills: 0,
      rage: 0, big: 0, guard: 0, sauce: 0, chill: 0, sg: 0, sgT: 0, streak: 0, tauntT: 0,   // power-ups, special gun, kill streak
      crash: 0, bumpT: 0,   // how long this head has been pushing into another worm; time to the next bump effect
      mercy: pid >= 0 ? CFG.SHIELD + HW.DIFFS[S.diff].mercy : 0,   // bots leave a freshly spawned human alone for this long (see bots.js)
      inp: { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false }, bot: null
    };
    const n = HW.segCount(w.mass);
    for (let i = 0; i < n; i++) w.pts.push({ x: pos.x - Math.cos(ang) * i * 2, y: pos.y - Math.sin(ang) * i * 2 });
    HW.follow(w);
    if (w.isBot) { const D = HW.DIFFS[S.diff]; w.bot = { think: Math.random() * 0.2, steer: ang, wander: ang, fireT: 0, skill: rnd(D.skill[0], D.skill[1]), aimErr: 0, burst: 0, panic: 0, abT: 0, abArm: false, abNo: 0, mx: 0, my: 0, sx: pos.x, sy: pos.y, sT: 1.5, esc: 0, escA: 0 }; }
    if (!w.isBot) for (const o of S.worms) if (o.alive && o.isBot && o.ch === ch && o.variant === w.variant) o.variant = this.pickVariant(ch, o); // the human keeps their colour
    S.worms.push(w); this.ev('spawn', w.x, w.y, w.id);
    return w;
  };

  // ----- match: competitors, lives, score -----
  // Every seat in the arena is a competitor: one per human, the rest are bot seats that keep the
  // same worm for the whole match (bots respawn freely, humans have CFG.LIVES lives).
  P.newComp = function (pid, ch) {
    const S = this.S, c = { cid: S.nextCid++, pid, ch, variant: 0, kills: 0, pts: 0, peak: 0, score: 0, lives: CFG.LIVES, out: false, worm: null, st: newStats() };   // pts: points from kills (bounties and streaks included)
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
  // ----- end of match awards: one line each, the sillier the better. [cid, title, number] -----
  P.awards = function () {
    const S = this.S, out = [], best = (f, min) => { let b = null, bv = min; for (const c of S.comps) { const v = f(c.st, c); if (v > bv) { bv = v; b = c; } } return b ? [b, bv] : null; };
    const add = (r, title, fmt) => { if (r) out.push([r[0].cid, title, fmt ? fmt(r[1]) : Math.round(r[1]), r[0].pid >= 0 ? 1 : 0]); };
    add(best(s => s.veg, 1.5), 'RABBIT FOOD AWARD: MOST VEGGIES EATEN');
    add(best(s => s.shr, 1.5), 'SPACE CADET: MOST MUSHROOMS');
    add(best(s => s.shots >= 12 ? Math.min(1, s.hits / s.shots) : 0, 0.05), 'SHARPSHOOTER: BEST AIM', v => Math.round(v * 100) + '%');
    add(best(s => s.shots >= 12 ? s.shots - s.hits : 0, 8), 'BARN DOOR SAFE: MOST SHOTS MISSED');
    add(best(s => s.pick, 1.5), 'HOARDER: MOST PICKUPS');
    add(best(s => s.boost, 8), 'LEAD FOOT: MOST BOOSTING', v => Math.round(v) + 'S');
    add(best(s => s.taunt, 2.5), 'BIG MOUTH: MOST TAUNTS');
    add(best(s => s.streak, 1.5), 'HANGRIEST: BEST KILL STREAK');
    add(best((s, c) => c.peak, 80), 'ABSOLUTE UNIT: BIGGEST WORM');
    // awards won by a human are shown first; four at most
    return out.sort((a, b) => b[3] - a[3]).slice(0, 4).map(a => a.slice(0, 3));
  };
  P.endMatch = function (reason) {
    const S = this.S, M = S.match; if (M.over) return;
    M.over = true; M.overT = 0; M.reason = reason; M.t = Math.max(0, M.t); M.awards = this.awards();
    this.ev('over', 0, 0, reason);
  };
  // next match: same arena and seats, everything else fresh
  P.restart = function () {
    const S = this.S;
    for (const w of S.worms) w.alive = false;
    S.worms.length = 0; S.bullets.length = 0; S.zones.length = 0;
    for (const c of S.comps) { c.kills = 0; c.pts = 0; c.peak = 0; c.score = 0; c.lives = CFG.LIVES; c.out = false; c.worm = null; c.st = newStats(); }
    for (const p of S.players) { p.worm = null; p.deadT = 0; p.wantSpawn = true; p.everSpawned = false; p.lastKiller = ''; p.lastCause = ''; p.lastScore = 0; if (p.inp) p.inp.abil = false; }
    S.match = { t: CFG.MATCH_T, over: false, overT: 0, n: S.match.n + 1, reason: '', frenzy: false, awards: [] };
    S.botTimer = 0; this.stockPickups(); this.ev('go', 0, 0);
  };

  // ----- players -----
  P.addPlayer = function (ch, conn) {
    const S = this.S; let pid = 0; while (S.players.some(p => p.pid === pid)) pid++;
    const p = { pid, ch, conn: conn || null, worm: null, deadT: 0, wantSpawn: true, inp: null, best: 0, lastKiller: '', lastCause: '', variant: -1 };
    S.players.push(p); p.variant = this.claimVariant(p);
    p.comp = this.newComp(pid, ch); p.comp.variant = p.variant;
    // the first human starts the match clock from the top
    if (S.players.length === 1 && !S.match.over) { S.match.t = CFG.MATCH_T; for (const c of S.comps) { c.kills = 0; c.pts = 0; c.st = newStats(); c.peak = c.worm && c.worm.alive ? c.worm.mass : 0; c.score = Math.round(c.peak); } }
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
    // the body turns into a trail of meals: a few big pieces rather than a carpet of crumbs
    const total = w.mass * 0.8 + 4, n = Math.max(1, Math.min(w.pts.length, 40, Math.round(total / 5))), per = total / n;
    let acc = 0;
    for (let i = 0; i < n; i++) {
      acc += per; const v = Math.floor(acc); if (v < 1) continue; acc -= v;
      const p = w.pts[Math.floor(i * w.pts.length / n)];
      this.addFood(p.x + rnd(-7, 7), p.y + rnd(-7, 7), v);
    }
    if (killer && killer !== w && killer.alive) {
      killer.kills++;
      if (killer.comp && cause !== 'left') {
        const c = killer.comp; c.kills++;
        // the crowned leader has a bounty on its head; kills in a row without dying earn a bonus on top
        let pts = CFG.KILL_PTS; if (w.id === S.leader) { pts *= HW.BOUNTY || 1; this.ev('bounty', w.x, w.y, killer.id, pts); }
        killer.streak++; if (killer.streak > c.st.streak) c.st.streak = killer.streak;
        for (const q of HW.STREAKS || []) if (q[0] === killer.streak) { pts += q[2]; this.ev('streak', killer.x, killer.y, killer.id, killer.streak, q[2], killer.pid, killer.ch); }
        c.pts += pts; c.score = Math.round(c.peak) + c.pts;
        if (killer.bot && Math.random() < 0.3) killer.inp.taunt = true;   // bots gloat too
      }
    }
    if (w.pid >= 0 && w.comp && cause !== 'left') { w.comp.lives = Math.max(0, w.comp.lives - 1); if (w.comp.lives <= 0) w.comp.out = true; }
    const k = killer && killer !== w ? killer : null;
    this.ev('die', w.x, w.y, w.id, k ? k.id : 0, cause, w.ch, k ? k.ch : -1, w.pid, k ? k.pid : -1, w.variant, Math.round(w.mass));
    if (w.pid >= 0) { const p = S.players.find(q => q.pid === w.pid); if (p) { p.deadT = 0; p.wantSpawn = false; p.lastKiller = k ? CHARS[k.ch].name : ''; p.lastCause = cause; p.lastScore = p.comp ? p.comp.score : Math.round(w.mass); } }
  };
  P.damage = function (w, dmg, owner, x, y) {
    if (!w.alive || w.shield > 0) return;
    if (w.guard > 0) { this.ev('ping', x, y, w.id); return; }   // shot shield: nothing gets through
    if (w.big > 0) dmg *= POWERS[1].armor;                      // supersized worms shrug half of it off
    if (owner && owner.comp) owner.comp.st.hits++;
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
    const S = this.S, g = GUNS[b.ch], R = g.blast;
    for (const w of S.worms) {
      if (!w.alive || w.id === b.owner || w.shield > 0) continue;
      const q = this.nearestSeg(w, b.x, b.y, R + w.r); const d = Math.sqrt(q) - w.r;
      if (d < R) {
        const f = 1 - clamp(d / R, 0, 1) * 0.65, p = this.hitPoint(w, b.x, b.y);
        if (!MAP.los(b.x, b.y, p.x, p.y, 0) && !MAP.los(b.x, b.y, w.x, w.y, 0)) continue;   // behind a counter: safe
        this.damage(w, g.dmg * f, S.worms.find(o => o.id === b.owner), p.x, p.y);
      }
    }
    this.ev('boom', b.x, b.y, R);
  };
  P.hitPoint = function (w, x, y) { let best = w.pts[0], bq = 1e12; for (const p of w.pts) { const q = (p.x - x) ** 2 + (p.y - y) ** 2; if (q < bq) { bq = q; best = p; } } return best; };

  P.fire = function (w) {
    const S = this.S, g = HW.gunOf(w);
    // w.cd sits in (-dt, 0] when a shot is due: carry the remainder so the average cadence is exactly g.interval
    w.cd = g.interval + (w.cd > -0.05 ? w.cd : 0); if (!w.sg) w.ammo--; w.shield = 0; w.mercy = 0;   // a special gun never runs dry, it just times out
    if (w.comp) w.comp.st.shots++;
    const mz = w.r + 6 + HW.gunSprOf(w).len, ca = Math.cos(w.aim), sa = Math.sin(w.aim);
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
    if (!MAP.los(w.x, w.y, bx, by, g.br * 0.5)) { bx = w.x + ca * w.r * 0.5; by = w.y + sa * w.r * 0.5; }   // muzzle poked into an obstacle: the shot starts at the head and hits it
    const wob = w.trip > 0 ? Math.sin(S.t * 5 + w.id) * 0.35 : 0;   // mushrooms: the gun sways
    // rockets speed up as they fly, so their lifetime is worked out from the range they should cover
    let life = g.range / g.speed;
    if (g.accel) { const t1 = (g.vmax - g.speed) / g.accel, d1 = g.speed * t1 + 0.5 * g.accel * t1 * t1; life = g.range >= d1 ? t1 + (g.range - d1) / g.vmax : (Math.sqrt(g.speed * g.speed + 2 * g.accel * g.range) - g.speed) / g.accel; }
    for (let i = 0; i < g.pellets; i++) {
      const a = w.aim + wob + (g.pellets > 1 ? (i / (g.pellets - 1) - 0.5) * g.spread + rnd(-0.04, 0.04) : rnd(-g.spread, g.spread));
      const sp = g.speed * (g.pellets > 1 ? rnd(0.85, 1.1) : 1);
      S.bullets.push({ id: S.nextId++, ch: g.kind, owner: w.id, x: bx, y: by, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life, age: 0, hit: null, pierce: g.pierce || 0, c: (Math.random() * 5) | 0 });
    }
    this.ev('shot', mx, my, g.kind, w.id);
  };
  P.useAbility = function (w) {
    const S = this.S, C = CHARS[w.ch]; if (!C.ability || w.abil > 0 || w.stuck > 0) return;
    w.abil = CFG.ABIL_CD; w.shield = 0; w.mercy = 0;
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
    const g = HW.gunOf(w), R = Math.min(g.range, 300); let best = null, bs = 1e9;
    for (const o of this.S.worms) {
      if (o === w || !o.alive || o.shield > 0) continue;
      if (w.x < o.bx0 - R || w.x > o.bx1 + R || w.y < o.by0 - R || w.y > o.by1 + R) continue;
      for (let i = 0; i < o.pts.length; i += 3) {
        const dx = o.pts[i].x - w.x, dy = o.pts[i].y - w.y, d = Math.sqrt(dx * dx + dy * dy); if (d > R) continue;
        const da = Math.abs(angDiff(Math.atan2(dy, dx), w.ang)); if (da > 0.95) continue;
        const s = d * (1 + da * 1.5) * (i === 0 ? 0.8 : 1); if (s < bs && MAP.los(w.x, w.y, o.pts[i].x, o.pts[i].y, 0)) { bs = s; best = Math.atan2(dy, dx); }
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
      // last minute: food and pickups pour in
      if (HW.FRENZY && !M.frenzy && M.t <= HW.FRENZY.t) { M.frenzy = true; this.ev('frenzy', 0, 0); }
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
    let lead = null;
    for (const c of S.comps) {
      const w = c.worm; if (!w || !w.alive) continue;
      if (w.mass > c.peak) { c.peak = w.mass; c.score = Math.round(c.peak) + c.pts; }
      if (!lead || w.mass > lead.mass) lead = w;
    }
    S.leader = lead && lead.mass > 60 ? lead.id : 0;   // the crowned worm (same rule as the crown in render.js): worth a bounty
    const rush = M.frenzy ? HW.FRENZY.rate : 1;
    // bot respawns
    S.botTimer -= dt; if (S.botTimer <= 0) { S.botTimer = 0.8; this.fillBots(); }

    for (const w of S.worms) {
      if (!w.alive) continue;
      if (w.bot) HW.botThink(this, w, dt);
      const C = CHARS[w.ch], I = w.inp;
      HW.turnHead(w, I, dt, S.t, !!w.bot);
      // aim
      if (I.ax * I.ax + I.ay * I.ay > 0.09) w.aim = Math.atan2(I.ay, I.ax);
      else { let a = null; if (I.auto && I.fire) a = this.autoAim(w); if (a === null) a = w.ang; w.aim += clamp(angDiff(a, w.aim), -14 * dt, 14 * dt); }
      // timers
      if (w.shield > 0) w.shield -= dt; if (w.cd > 0) w.cd -= dt; if (w.abil > 0) w.abil -= dt;
      if (w.slow > 0) w.slow -= dt; if (w.trip > 0) w.trip -= dt; if (w.pukeImm > 0) w.pukeImm -= dt; if (w.mercy > 0) w.mercy -= dt;
      // power-ups and the special gun run out
      if (w.rage > 0 && (w.rage -= dt) <= 0) this.ev('poweroff', w.x, w.y, w.id, 0);
      if (w.big > 0 && (w.big -= dt) <= 0) this.ev('poweroff', w.x, w.y, w.id, 1);
      if (w.guard > 0 && (w.guard -= dt) <= 0) this.ev('poweroff', w.x, w.y, w.id, 2);
      if (w.sauce > 0 && (w.sauce -= dt) <= 0) this.ev('poweroff', w.x, w.y, w.id, 3);
      if (w.chill > 0) w.chill -= dt; if (w.tauntT > 0) w.tauntT -= dt;
      if (w.sg && (w.sgT -= dt) <= 0) { w.sg = 0; w.sgT = 0; w.cd = Math.max(w.cd, 0.25); this.ev('gunoff', w.x, w.y, w.id); }
      if (I.taunt) { I.taunt = false; if (w.tauntT <= 0 && HW.TAUNTS) { w.tauntT = 2.5; if (w.comp) w.comp.st.taunt++; this.ev('taunt', w.x, w.y, w.id, (Math.random() * HW.TAUNTS.length) | 0); } }
      // move
      const hot = w.sauce > 0;   // hot sauce: boosting is free
      w.boosting = !!(I.boost && (hot || w.mass > CFG.MIN_MASS + 4) && w.stuck <= 0);
      if (w.boosting && w.comp) w.comp.st.boost += dt;
      if (w.boosting && !hot) {
        const c = CFG.BOOST_COST * dt; w.mass -= c; w.boostAcc += c * 0.6;
        if (w.boostAcc >= 1) { w.boostAcc -= 1; const tl = w.pts[w.pts.length - 1]; this.addFood(tl.x + rnd(-4, 4), tl.y + rnd(-4, 4), 1); }
      }
      const sp = HW.headSpeed(w);
      if (w.stuck > 0) w.stuck -= dt;
      HW.moveHead(w, sp, dt);
      HW.follow(w);
      // fire / ability
      if (I.fire && w.cd <= 0) { if (w.ammo > 0 || w.sg) this.fire(w); else if (!w.dryT || S.t - w.dryT > 0.5) { w.dryT = S.t; this.ev('dry', w.x, w.y, w.id); } }
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
          const er = w.r + CHARS[w.ch].eat * (w.big > 0 ? POWERS[1].eat : 1);
          if (d < w.r + (it.v >= CFG.BIG ? 7 : 3)) { eatList.push(it, w); break; }
          if (d < er) { const k = Math.min(1, 260 * dt / d); it.x += dx * k; it.y += dy * k; }
        } else if (d < w.r + (it.k === 'a' ? 9 : it.k === 'v' || it.k === 'm' ? 11 : 14)) { eatList.push(it, w); break; }
      }
    }
    for (let i = 0; i < eatList.length; i += 2) {
      const it = eatList[i], w = eatList[i + 1]; if (!S.items.has(it.id)) continue;
      this.remItem(it);
      if (it.k === 'f') { w.mass += it.v; this.ev('eat', it.x, it.y, w.id, it.v); }
      else if (it.k === 'a') { const g = CHARS[w.ch].gun; w.ammo = Math.min(g.max, w.ammo + g.pickup); this.ev('ammo', it.x, it.y, w.id); S.respawns.push({ k: 'a', t: 7 }); }
      else if (it.k === 'v') {
        // veggies: slow, and you shrink (the mass is gone, not dropped)
        if (w.shield <= 0) {
          const loss = Math.max(0, Math.min(w.mass - CFG.MIN_MASS - 2, 3 + w.mass * CFG.VEG_LOSS)); w.mass -= loss; w.slow = CFG.SLOW_T;
          const cut = w.abil > 0 ? Math.min(w.abil, CFG.VEG_ABIL) : 0; w.abil -= cut; if (w.comp) w.comp.st.veg++;   // ...but your fart / puke is ready sooner
          this.ev('veg', it.x, it.y, w.id, Math.round(loss), Math.round(cut));
        }
        S.respawns.push({ k: 'v', t: 5 });
      }
      else if (it.k === 'm') {
        if (w.shield <= 0) { w.trip = CFG.TRIP_T; const cut = w.abil > 0 ? Math.min(w.abil, CFG.SHROOM_ABIL) : 0; w.abil -= cut; if (w.comp) w.comp.st.shr++; this.ev('shroom', it.x, it.y, w.id, Math.round(cut)); }
        S.respawns.push({ k: 'm', t: 8 });
      }
      else if (it.k === 'p') {
        // power-up: 0 rampage, 1 supersize, 2 shot shield, 3 hot sauce
        const P0 = POWERS[it.type] || POWERS[0];
        if (it.type === 0) w.rage = P0.t; else if (it.type === 1) { w.big = P0.t; w.mass += P0.mass; } else if (it.type === 2) w.guard = P0.t; else w.sauce = P0.t;
        if (w.comp) w.comp.st.pick++; this.ev('power', it.x, it.y, w.id, it.type, w.pid);
        S.respawns.push({ k: 'p', t: rnd(PCFG.POWER_WAIT[0], PCFG.POWER_WAIT[1]) });
      }
      else if (it.k === 'g') {
        w.sg = it.type + 1; w.sgT = SGUNS[it.type].t; w.cd = Math.min(w.cd, 0.2); if (w.comp) w.comp.st.pick++;
        this.ev('gun', it.x, it.y, w.id, it.type, w.pid);
        S.respawns.push({ k: 'g', t: rnd(PCFG.GUN_WAIT[0], PCFG.GUN_WAIT[1]) });
      }
      else if (it.k === 'x') {
        w.mass += it.v; if (w.comp) w.comp.st.pick++; this.ev('gold', it.x, it.y, w.id, it.v, w.pid);
        S.respawns.push({ k: 'x', t: rnd(HW.GOLD.wait[0], HW.GOLD.wait[1]) });
      }
    }
    for (let i = S.respawns.length - 1; i >= 0; i--) {
      const r = S.respawns[i]; r.t -= dt * (r.k === 'p' || r.k === 'g' || r.k === 'x' ? rush : 1); if (r.t > 0) continue; S.respawns.splice(i, 1);
      this.dropItem(r.k);
    }
    if (S.counts.f < CFG.FOOD * (rush > 1 ? 1.25 : 1) && Math.random() < dt * 5 * rush) this.addFood();
    if (S.counts.f > 520) {
      // too much litter: clear the oldest crumbs first, then anything, so the cap always holds
      let n = 0; for (const it of S.items.values()) { if (it.k === 'f' && it.v < CFG.BIG) { this.remItem(it); if (++n > 20) break; } }
      if (n === 0) for (const it of S.items.values()) { if (it.k === 'f') { this.remItem(it); if (++n > 20) break; } }
    }

    // head vs body. Touching another worm is a BUMP, not instant death: the head is held at the surface
    // (it cannot pass through) and only a worm that keeps driving in for CFG.CRASH_T dies, so there is
    // a clear moment of impact and time to wrench the wheel round. A glancing scrape counts for less
    // than a square hit, and the count runs back down once you are clear.
    // Every touch is collected first and judged afterwards, so the outcome never depends on the order
    // worms happen to be stored in.
    const touch = this.touch || (this.touch = []); touch.length = 0;
    for (const a of S.worms) {
      if (!a.alive) continue; a.hold = false; if (a.bumpT > 0) a.bumpT -= dt;
      if (a.shield > 0) { a.crash = 0; continue; }
      let wb = null, wi = -1, wq = 0, wc = 0, deep = 1e9;
      for (const b of S.worms) {
        if (b === a || !b.alive || b.shield > 0) continue;
        const m = a.r + b.r;
        if (a.x < b.bx0 - m || a.x > b.bx1 + m || a.y < b.by0 - m || a.y > b.by1 + m) continue;
        // the part of b that a's head is closest to decides what was hit: b's head (0) or its body
        const cd = a.r * 0.7 + b.r * 0.78, p = b.pts; let hit = -1, hq = cd * cd;   // a graze is forgiven: the circles must really overlap
        for (let i = 0; i < p.length; i++) { const dx = p[i].x - a.x, dy = p[i].y - a.y, q = dx * dx + dy * dy; if (q < hq) { hq = q; hit = i; } }
        if (hit < 0) continue;
        if (a.rage > 0 && !(b.rage > 0)) { touch.push(a, b, hit); continue; }   // a rampage does not wait: it goes straight through them
        const d = Math.sqrt(hq) - cd; if (d < deep) { deep = d; wb = b; wi = hit; wq = hq; wc = cd; }   // deepest contact decides
      }
      if (!wb) { if (a.crash > 0) a.crash = Math.max(0, a.crash - dt * 2); continue; }
      const q = wb.pts[wi], d = Math.sqrt(wq) || 0.01, ux = (q.x - a.x) / d, uy = (q.y - a.y) / d;
      const into = Math.cos(a.ang) * ux + Math.sin(a.ang) * uy;   // 1 = square on, 0 = sliding along it
      // The count runs at full speed square on and falls away fast as you turn off (cosine squared), so a
      // quick worm that reacts can wrench itself clear of even a square hit, and an oblique one is easy.
      a.crash += dt * Math.max(0.1, into > 0 ? into * into : 0);
      a.hold = true; a.hx = q.x - ux * (wc + 0.5); a.hy = q.y - uy * (wc + 0.5);
      if (a.bumpT <= 0) { a.bumpT = 0.1; this.ev('bump', a.x + ux * a.r, a.y + uy * a.r, a.id, Math.min(100, Math.round(a.crash / CFG.CRASH_T * 100))); }
      if (a.crash >= CFG.CRASH_T) touch.push(a, wb, wi);
    }
    // hold the bumping heads at the surface (after all the tests, so nobody's test saw a moved head)
    for (const a of S.worms) {
      if (!a.hold || !a.alive) continue;
      a.x = clamp(a.hx, a.r, CFG.W - a.r); a.y = clamp(a.hy, a.r, CFG.H - a.r);
      if (MAP.push(a.x, a.y, a.r, PT)) { a.x = clamp(PT.x, a.r, CFG.W - a.r); a.y = clamp(PT.y, a.r, CFG.H - a.r); }
      a.pts[0].x = a.x; a.pts[0].y = a.y;
    }
    if (touch.length) {
      const dead = [];
      const mark = (w, by, cause) => { for (let i = 0; i < dead.length; i += 3) if (dead[i] === w) return; dead.push(w, by, cause); };
      // 1) a head that ran into a body dies, whatever else is going on. Except on a rampage: then the
      //    worm that got run into dies (unless it is rampaging too, in which case the usual rule holds).
      for (let i = 0; i < touch.length; i += 3) {
        if (touch[i + 2] <= 0) continue; const a = touch[i], b = touch[i + 1];
        if (a.rage > 0 && !(b.rage > 0)) mark(b, a, 'rampage'); else mark(a, b, 'crash');
      }
      // 2) head against head: the lighter worm dies, equal worms both die. A worm that has just
      //    crashed into a body has already lost: it cannot also win (or lose) a head-on this step.
      const n = dead.length;
      for (let i = 0; i < touch.length; i += 3) {
        if (touch[i + 2] !== 0) continue; const a = touch[i], b = touch[i + 1];
        let out = false; for (let k = 0; k < n; k += 3) if (dead[k] === a || dead[k] === b) { out = true; break; }
        if (out) continue;
        // rampage beats supersize beats nothing; between equals the heavier worm wins
        const pa = a.rage > 0 ? 2 : a.big > 0 ? 1 : 0, pb = b.rage > 0 ? 2 : b.big > 0 ? 1 : 0;
        if (pa > pb) mark(b, a, pa === 2 ? 'rampage' : 'bonk');
        else if (pb > pa) mark(a, b, pb === 2 ? 'rampage' : 'bonk');
        else { if (a.mass <= b.mass) mark(a, b, 'bonk'); if (b.mass <= a.mass) mark(b, a, 'bonk'); }
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
      const b = S.bullets[i], g = GUNS[b.ch]; let dead = false; b.age += dt;
      if (g.accel) { const v = Math.sqrt(b.vx * b.vx + b.vy * b.vy), nv = Math.min(g.vmax, v + g.accel * dt); if (v > 0) { b.vx *= nv / v; b.vy *= nv / v; } }
      const steps = g.speed > 600 ? 4 : 2;   // the ray gun's bolt is fast: smaller steps so it cannot skip a thin worm
      for (let s = 0; s < steps && !dead; s++) {
        b.x += b.vx * dt / steps; b.y += b.vy * dt / steps;
        if (b.x < 0 || b.y < 0 || b.x > CFG.W || b.y > CFG.H) { dead = true; break; }
        if (MAP.hit(b.x, b.y, g.br * 0.5)) { b.x -= b.vx * dt / steps; b.y -= b.vy * dt / steps; dead = true; this.ev('clang', b.x, b.y); break; }   // stopped by a counter, table...
        for (const w of S.worms) {
          if (!w.alive || w.id === b.owner || w.shield > 0) continue;
          if (b.hit && b.hit.indexOf(w.id) >= 0) continue;
          const lim = g.br + w.r; if (this.nearestSeg(w, b.x, b.y, lim) > lim * lim) continue;
          if (g.blast) { dead = true; break; }
          this.damage(w, g.dmg, S.worms.find(o => o.id === b.owner), b.x, b.y);
          if (g.chill && w.alive && w.guard <= 0) { if (w.chill <= 0) this.ev('chill', w.x, w.y, w.id); w.chill = g.chill; }   // freeze ray
          if (w.guard > 0) { dead = true; break; }   // the shot shield stops even shots that pierce
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
