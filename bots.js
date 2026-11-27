// Hangry Worms - bot brains
// A bot thinks a few times a second (slower when its skill is low) and only writes to its own
// input record, the same record a player's controls fill in. It works from what a player could
// see on screen, plus one thing a player has to guess: whether another worm's ability is ready.
'use strict';
(function (HW) {
  const CFG = HW.CFG, CHARS = HW.CHARS, MAP = HW.MAP, { rnd, clamp, angDiff } = HW.util;

  // Scratch state for the one bot that is thinking right now (set up in botThink)
  const haz = [];        // veggies and mushrooms close by: [x, y, x, y, ...]
  let hazR2 = 0;         // how close to one of those counts as touching it (squared)
  let skipZone = null;   // a cloud or puddle the head is already at the edge of (the plan is to leave it)
  let fear = false;      // Jeff only (both kill him): keep clear of worms that are ready to puke or fart
  let ram = false;       // on a rampage: other worms are there to be run over, not avoided
  let noRam = false;     // ...except humans, on the easiest setting
  let warm = false;      // start of a match: humans are left alone
  let giveWay = 0;       // seconds of a human's path ahead that this bot keeps out of (HW.DIFFS way)
  const PT = { x: 0, y: 0, nx: 0, ny: 0 };

  // a human the bots are not allowed to hurt right now: just spawned, or the match has only just begun
  const spared = o => o.pid >= 0 && (warm || o.mercy > 0);

  // would worm w be in trouble with its head at (x, y)?
  function blocked(sim, w, x, y, pad) {
    // the wall margin only counts on the way in: a worm that is already in a corner has to be able to leave it
    if ((x < 24 && x < w.x) || (y < 24 && y < w.y) || (x > CFG.W - 24 && x > w.x) || (y > CFG.H - 24 && y > w.y)) return true;
    if (MAP.hit(x, y, w.r + pad + 3)) return true;   // counters, tables, crates...
    const S = sim.S;
    for (const z of S.zones) { if (z.owner === w.id || z === skipZone) continue; const dx = z.x - x, dy = z.y - y, r = z.r + 14; if (dx * dx + dy * dy < r * r) return true; }
    for (let i = 0; i < haz.length; i += 2) { const dx = haz[i] - x, dy = haz[i + 1] - y; if (dx * dx + dy * dy < hazR2) return true; }
    for (const o of S.worms) {
      if (o === w || !o.alive || o.shield > 0.6) continue;
      const human = o.pid >= 0, wild = o.rage > 0;
      // rampage: everything is prey, except another rampaging worm and a human who is off limits
      const safe = human && (noRam || warm || o.mercy > 0);
      if (ram && !wild && !safe) continue;
      // (on a rampage a mere touch kills, with no time to turn away: those who must not be hurt get a lot of room)
      const m = o.r + w.r + pad + 3 + (safe && w.rage > 0 ? 24 : 0);
      // its head is about to sweep along this line: stay off it. A head that wins every collision gets more room,
      // and so does a human on the easier settings: bots do not cut across a player's nose
      let secs = 0.45, wide = 6;
      if (wild) { secs = 0.9; wide = 24; } else if (o.big > 0) { secs = 0.7; wide = 12; }
      const polite = human && giveWay > secs; if (polite) secs = giveWay;
      const reach = HW.headSpeed(o) * secs, far = Math.max(fear ? 150 : 95, reach * (polite ? 1.4 : 1) + wide + 8);
      if (x < o.bx0 - m - far || x > o.bx1 + m + far || y < o.by0 - m - far || y > o.by1 + m + far) continue;
      const ux = Math.cos(o.ang), uy = Math.sin(o.ang), rx = x - o.x, ry = y - o.y;
      const t = clamp(rx * ux + ry * uy, 0, reach), hx = rx - ux * t, hy = ry - uy * t, hq = hx * hx + hy * hy;
      const lane = m + wide + (polite ? t * 0.4 : 0);   // a player may turn: the lane kept free for them fans out
      if (hq < lane * lane) return true;
      if (fear && o.abil <= 1.5 && o.stuck <= 0) {
        if (CHARS[o.ch].ability === 'puke') { if (hq < 150 * 150) return true; }
        else if (CHARS[o.ch].ability) { const f = o.pts[Math.min(o.pts.length - 1, 16)], dx = f.x - x, dy = f.y - y; if (dx * dx + dy * dy < CFG.FART_R * CFG.FART_R) return true; }   // ...and off the spot a loaded fart would land on
      }
      if (x < o.bx0 - m || x > o.bx1 + m || y < o.by0 - m || y > o.by1 + m) continue;
      const p = o.pts, m2 = m * m;
      for (let i = 0; i < p.length; i += 2) { const dx = p[i].x - x, dy = p[i].y - y; if (dx * dx + dy * dy < m2) return true; }
    }
    return false;
  }

  // How far can worm w get if it steers for direction a?  0 (trouble at once) .. 4 (all clear).
  // A worm cannot turn on the spot, so the path tested is the real one: an arc of radius tr round
  // to the new heading and then a straight line. Testing a straight ray instead lets U-turns
  // sweep through whatever is beside the worm.
  const STEPS = [0.25, 0.5, 0.75, 1], PADS = [5, 6, 6, 6];
  function clearance(sim, w, a, look, tr) {
    const d = angDiff(a, w.ang), sg = d < 0 ? -1 : 1, arc = Math.abs(d) * tr;
    const s0 = Math.sin(w.ang), c0 = Math.cos(w.ang), ex = w.x + sg * tr * (Math.sin(a) - s0), ey = w.y - sg * tr * (Math.cos(a) - c0), ca = Math.cos(a), sa = Math.sin(a);
    for (let i = 0; i < 4; i++) {
      const s = look * STEPS[i]; let x, y;
      if (s < arc) { const h = w.ang + sg * s / tr; x = w.x + sg * tr * (Math.sin(h) - s0); y = w.y - sg * tr * (Math.cos(h) - c0); }
      else { x = ex + ca * (s - arc); y = ey + sa * (s - arc); }
      if (blocked(sim, w, x, y, PADS[i])) return i;
    }
    return 4;
  }

  // Which way to set off to get worm w to (x, y): straight there when nothing stands in the way, otherwise
  // towards the obstacle corner that makes the shortest way round. null: no simple way, forget it.
  // The corner is remembered (b.wx, b.wy, b.wT) so a bot in front of a counter does not dither between its two ends.
  function route(b, w, x, y, t) {
    const pad = w.r + 3;
    if (MAP.los(w.x, w.y, x, y, pad)) { b.wT = 0; return Math.atan2(y - w.y, x - w.x); }
    if (b.wT > t && MAP.los(w.x, w.y, b.wx, b.wy, pad) && MAP.los(b.wx, b.wy, x, y, pad)) { const dx = b.wx - w.x, dy = b.wy - w.y; if (dx * dx + dy * dy > 400) return Math.atan2(dy, dx); }
    const out = w.r + 18, x0 = Math.min(w.x, x) - 90, x1 = Math.max(w.x, x) + 90, y0 = Math.min(w.y, y) - 90, y1 = Math.max(w.y, y) + 90;
    let best = null, bl = 1e9;
    for (const o of MAP.obs) {
      if (o.x1 < x0 || o.x0 > x1 || o.y1 < y0 || o.y0 > y1) continue;
      for (let i = 0; i < 4; i++) {
        const cx = i & 1 ? o.x1 + out : o.x0 - out, cy = i & 2 ? o.y1 + out : o.y0 - out;
        if (cx < 30 || cy < 30 || cx > CFG.W - 30 || cy > CFG.H - 30) continue;
        const l = Math.hypot(cx - w.x, cy - w.y) + Math.hypot(x - cx, y - cy); if (l >= bl) continue;
        if (MAP.los(w.x, w.y, cx, cy, pad) && MAP.los(cx, cy, x, y, pad)) { bl = l; best = Math.atan2(cy - w.y, cx - w.x); b.wx = cx; b.wy = cy; }
      }
    }
    b.wT = best === null ? 0 : t + 4;
    return best;
  }

  const OFFS = [0, 0.55, -0.55, 1.1, -1.1, 1.7, -1.7, 2.4, -2.4, 3.1];
  // How a bot handles each gun (by gun kind: the five character guns, then the special guns). This is what makes
  // each gun play like itself. burst: shots before it eases up [fewest, most]: the SMG sprays, the skewer plinks,
  // cannon and rockets are single shots, flamethrower and minigun are held down. far: how far it opens fire from,
  // as a multiple of the difficulty's usual distance. min: never fired from closer than this. rest: length of the
  // breather between bursts (a gun on a timer is not for saving).
  const GP = [
    { burst: [2, 3.5], far: 1, min: 0, rest: 1 },
    { burst: [1, 3], far: 1, min: 0, rest: 1 },
    { burst: [7, 17], far: 1, min: 0, rest: 1 },
    { burst: [3, 6], far: 1, min: 0, rest: 1 },
    { burst: [1, 2], far: 1, min: 0, rest: 1 },
    { burst: [2, 5], far: 1.35, min: 0, rest: 0.6 },      // ray gun: from a distance
    { burst: [1, 2], far: 1.15, min: 75, rest: 0.6 },     // rocket launcher: not into its own face
    { burst: [16, 40], far: 0.72, min: 0, rest: 0.4 },    // flamethrower: only up close
    { burst: [16, 42], far: 1, min: 0, rest: 0.5 },       // minigun: long bursts
    { burst: [3, 7], far: 1.35, min: 0, rest: 0.6 }       // freeze ray: from a distance
  ];
  // what a pickup is worth going out of the way for, on the scale food is scored on (a feast is 8)
  const PVAL = [44, 32, 32, 16], GVAL = 32, XVAL = 36, GRAB = 420, HUNT = 20;
  const LAPSE = 0.06;   // chance per think of a lapse of attention is LAPSE * (1.3 - skill): about 5% for the worst bots, 2% for the best
  const AIM_ERR = 0.65; // the clumsiest bot's worst burst is off by about AIM_ERR * 0.95 radians

  HW.botThink = function (sim, w, dt) {
    const b = w.bot, S = sim.S, C = CHARS[w.ch], g = HW.gunOf(w), own = C.gun, I = w.inp, D = HW.DIFFS[S.diff];
    if (b.wT === undefined) { b.wT = 0; b.wx = 0; b.wy = 0; b.bump = false; b.escS = 1; b.escH = false; }   // route memory, bump seen, escape side (the rest of w.bot is set up in sim.js)
    if (b.panic > 0) b.panic -= dt;
    if (b.fireT > 0) b.fireT -= dt;
    if (b.burst > 0) b.burst -= dt;
    if (b.abT > 0) b.abT -= dt;
    if (b.abNo > 0) b.abNo -= dt;
    if (b.esc > 0) b.esc -= dt;
    // wedged against an obstacle or a wall for a while: head back out into the open
    b.sT -= dt;
    if (b.sT <= 0) {
      const mx = w.x - b.sx, my = w.y - b.sy;
      if (mx * mx + my * my < 22 * 22 && w.stuck <= 0) {
        b.esc = rnd(0.9, 1.6); b.wT = 0; b.escS = -b.escS;
        const m = w.r + 3, edge = w.x < m || w.y < m || w.x > CFG.W - m || w.y > CFG.H - m;
        b.escH = true;   // leaning on something: the look-ahead has nothing useful to say, just turn
        if (MAP.push(w.x, w.y, Math.min(MAP.PAD, w.r + 14), PT)) b.escA = Math.atan2(PT.ny, PT.nx) + rnd(-0.9, 0.9);   // straight off the thing it is leaning on
        // Against a wall: turn right round, the other way from last time. In a corner one of the two ways round is a
        // dead end (the walls' nudges cancel the turn exactly), so trying both in turn always gets out.
        else if (edge) b.escA = w.ang + b.escS * rnd(2.2, 2.9);
        else { b.escA = w.ang + b.escS * rnd(1.6, 2.8); b.escH = false; }
      }
      b.sx = w.x; b.sy = w.y; b.sT = 1.5;
    }
    // bumped into somebody: that gets noticed at once (CFG.CRASH_T of leaning on them is death)
    const bump = w.crash > 0 && w.rage <= 0;
    if (bump && !b.bump) b.think = Math.min(b.think, (0.03 + (1 - b.skill) * 0.1) * D.think);
    b.bump = bump;
    b.think -= dt; if (b.think > 0) return;
    b.think = (0.09 + Math.random() * 0.08 + (1 - b.skill) * 0.08) * D.think;
    // now and then a bot's attention wanders and it just holds its course for a moment: this is what
    // lets a player cut one off, and it happens more to the less skilled ones. Nobody dozes off next
    // to a fart cloud or a puke puddle though, or with its nose in somebody's side, or on a rampage (when a
    // touch kills, there must be no blundering into a player the bots are meant to be leaving alone).
    if (!bump && w.rage <= 0 && Math.random() < LAPSE * D.lapse * (1.3 - b.skill)) {
      let calm = true;
      for (const z of S.zones) { if (z.owner === w.id) continue; const dx = z.x - w.x, dy = z.y - w.y, r = z.r + 150; if (dx * dx + dy * dy < r * r) { calm = false; break; } }
      if (calm) { b.think += rnd(0.25, 0.6); I.fire = false; I.boost = false; return; }
    }

    // ---- what this bot is carrying ----
    const special = w.sg > 0, armed = special || w.ammo > 0, prof = GP[g.kind] || GP[0], shielded = w.guard > 0.5;
    // on a rampage (with enough of it left to finish the job: when it runs out mid-ram, the ram is a crash)
    ram = w.rage > 0.7; noRam = D.hunt < 200; giveWay = D.way;
    // at the start of a match, and just after a human spawns, the bots leave humans alone
    warm = S.players.length > 0 && CFG.MATCH_T - S.match.t < D.warm;
    // a gun on a timer or a shield against shots: reasons to go looking for a fight instead of waiting for one
    const keen = armed && (special || shielded);

    // ---- other worms: what to shoot, who to use the ability on, who to run from, who to run over ----
    let tgt = null, tw = null, td = 1e12, scary = null, sd = 1e9, mark = null, mq = 1e12;
    let prey = null, pd = 1e12, quarry = null, qd = 1e12, threat = null, thd = 1e12, contact = null, cq2 = 1e12;
    // never open fire from further than a player can see (about 170 px from the middle of their screen; less on easy).
    // The long guns reach a little further, the flamethrower much less.
    const R = Math.min(g.range * 0.8, D.engage * prof.far), HR = D.hunt, seek = Math.max(R, HR);
    const ready = C.ability && w.abil <= 0 && w.stuck <= 0, fp = w.pts[Math.min(w.pts.length - 1, 16)]; // fp: where a fart would come out
    const mid = w.pts[w.pts.length >> 1], tail = w.pts[w.pts.length - 1], fleeR = 150 + 170 * b.skill;
    for (const o of S.worms) {
      if (o === w || !o.alive || o.shield > 0) continue;
      const hx = o.x - w.x, hy = o.y - w.y, hq = Math.sqrt(hx * hx + hy * hy);
      const spare = spared(o);
      // Jeff dies in puke, so he keeps his distance from a worm that is ready to throw up
      if (C.weakPuke && CHARS[o.ch].ability === 'puke' && o.abil <= 1.5 && o.stuck <= 0 && hq < 210 && hq < sd) { sd = hq; scary = o; }
      // a rampaging worm kills whatever part of us it touches: get everything out of its way (unless we are on one too)
      if (o.rage > 0 && w.rage <= 0 && o.stuck <= 0) {
        const q = Math.min(hq, Math.hypot(o.x - mid.x, o.y - mid.y), Math.hypot(o.x - tail.x, o.y - tail.y));
        if (q < fleeR && q < sd) { sd = q; scary = o; }
      }
      if (hq < thd && !spare) { thd = hq; threat = o; }
      // leaning on this one? remember where, to steer straight off it
      if (bump && w.x > o.bx0 - 30 && w.x < o.bx1 + 30 && w.y > o.by0 - 30 && w.y < o.by1 + 30) { const p = sim.hitPoint(o, w.x, w.y), q = (p.x - w.x) ** 2 + (p.y - w.y) ** 2; if (q < cq2) { cq2 = q; contact = p; } }
      // ability target: the head that will be nearest to where the cloud / puddle can go
      if (ready && hq < 260 && !spare) {
        const lead = HW.headSpeed(o) * 0.3, px = o.x + Math.cos(o.ang) * lead, py = o.y + Math.sin(o.ang) * lead;
        const ax = C.ability === 'fart' ? px - fp.x : px - w.x, ay = C.ability === 'fart' ? py - fp.y : py - w.y, q = ax * ax + ay * ay;
        if (q < mq && (C.ability === 'fart' || o.stuck <= 0)) { mq = q; mark = o; b.mx = ax; b.my = ay; }
      }
      if (spare || w.x < o.bx0 - seek || w.x > o.bx1 + seek || w.y < o.by0 - seek || w.y > o.by1 + seek) continue;
      let np = null, nd = 1e12;
      for (let i = 0; i < o.pts.length; i += 3) { const dx = o.pts[i].x - w.x, dy = o.pts[i].y - w.y, d = dx * dx + dy * dy; if (d < nd) { nd = d; np = o.pts[i]; } }
      // rampage: the nearest thing to run over (not another rampaging worm: against that the usual rules hold)
      if (ram && o.rage <= 0 && !(noRam && o.pid >= 0) && nd < pd) { pd = nd; prey = np; }
      if (o.guard > 0) continue;   // shots bounce off a shot shield: do not waste them
      // a frozen worm is a sitting duck: it counts as nearer than it is, and is worth going after
      const frozen = o.chill > 0.4, e = frozen ? nd * 0.3 : nd;
      if (e < td) { td = e; tgt = np; tw = o; }
      if ((keen || (frozen && armed)) && nd < qd) { qd = nd; quarry = np; }
    }
    if (tgt) td = Math.hypot(tgt.x - w.x, tgt.y - w.y);
    if (tgt && !MAP.los(w.x, w.y, tgt.x, tgt.y, 2)) tgt = null;   // no shooting at what is behind a counter
    pd = Math.sqrt(pd); qd = Math.sqrt(qd);

    // ---- scratch state for blocked() ----
    haz.length = 0; hazR2 = (w.r + 19) * (w.r + 19); skipZone = null;
    fear = !!C.weakPuke && w.shield <= 0.8 && !(scary && sd < 160); // already too close: just run (see steering)
    let leave = null;
    for (const z of S.zones) { if (z.owner === w.id) continue; const dx = w.x - z.x, dy = w.y - z.y, r = z.r + 14; if (dx * dx + dy * dy < r * r) { skipZone = z; leave = Math.atan2(dy, dx); break; } }

    // ---- goal: food, pickups, and ammo when the gun is getting empty ----
    let ga = null, bs = 0, crate = null, cq = 1e12, toy = null, ts = 0, rush = false;   // rush: the goal is worth hurrying to
    const seeHaz = Math.max(26, (b.skill - 0.3) * 240) ** 2; // sharp bots spot veggies and mushrooms early, dozy ones blunder into them
    // A worm cannot reach things inside its own turning circle: chasing them means circling forever.
    // tr = turning radius (with slack for thinking time), tin = how deep inside the circle is hopeless
    const ca = Math.cos(w.ang), sa = Math.sin(w.ang), tr = C.speed / C.turn * 1.2, tin = Math.max(0, tr - w.r - C.eat * 0.7), near2 = tr * tr * 5;
    const grabR = GRAB * D.grab, see = Math.max(300, grabR), foodR2 = D.food * D.food;
    for (const it of S.items.values()) {
      const dx = it.x - w.x, dy = it.y - w.y;
      if (it.k === 'a') { const q = dx * dx + dy * dy; if (q < cq) { cq = q; crate = it; } continue; }
      if (dx > see || dx < -see || dy > see || dy < -see) continue;
      const q = dx * dx + dy * dy;
      if (it.k === 'p' || it.k === 'g' || it.k === 'x') {
        // power-ups, special guns, the golden burger: worth a detour. How much of one is a matter of difficulty:
        // easy bots only take what they nearly trip over, and leave it lying when a player is about
        if (q > grabR * grabR) continue;
        let v = it.k === 'p' ? PVAL[it.type] || 20 : it.k === 'g' ? (w.sgT > 5 ? 8 : GVAL) : XVAL;
        if (D.grab < 0.5) for (const p of S.players) { const h = p.worm; if (h && h.alive && (h.x - it.x) ** 2 + (h.y - it.y) ** 2 < 320 * 320) v = 0; }
        const d = Math.sqrt(q), s = v * D.grab / (d + 40) * (1 - Math.abs(angDiff(Math.atan2(dy, dx), w.ang)) * 0.12);
        if (s > ts && !blocked(sim, w, it.x, it.y, -6)) { ts = s; toy = it; }
        continue;
      }
      if (dx > 300 || dx < -300 || dy > 300 || dy < -300) continue;
      // veggies and mushrooms: bots never eat them on purpose, countdown bonus or not
      if (it.k !== 'f') { if (w.shield <= 0 && q < seeHaz) haz.push(it.x, it.y); continue; }
      if (q > foodR2) continue;   // easy bots are lazy eaters: they only bother with what is close, and stay smaller for it
      if (q < near2) { const fx = dx * ca + dy * sa, fy = Math.abs(dy * ca - dx * sa) - tr; if (fx * fx + fy * fy < tin * tin) continue; }
      const d = Math.sqrt(q), a = Math.atan2(dy, dx);
      const s = it.v / (d + 40) * (1 - Math.abs(angDiff(a, w.ang)) * 0.18);
      // not worth dying for: skip food lying against another worm, in a cloud or in a puddle, and food behind an obstacle
      if (s > bs && !blocked(sim, w, it.x, it.y, -6) && MAP.los(w.x, w.y, it.x, it.y, 0)) { bs = s; ga = a; }
    }
    if (crate && w.ammo < own.max && !special) {
      // empty: cross the map for a crate. low: go a fair way. otherwise only if it is on the way
      const d = Math.sqrt(cq), dry = w.ammo <= 0, low = w.ammo < own.max * 0.3;
      if (d < (dry ? 1400 : low ? 650 : 280)) {
        const dx = crate.x - w.x, dy = crate.y - w.y, fx = dx * ca + dy * sa, fy = Math.abs(dy * ca - dx * sa) - tr, cin = Math.max(0, tr - w.r - 7);
        const s = (dry ? 180 : low ? 90 : 12) / (d + 40) * (1 - Math.abs(angDiff(Math.atan2(dy, dx), w.ang)) * 0.18);
        if (s > bs && s > ts) {
          // a crate inside the turning circle: run straight on for a moment and come back at it
          const a = fx * fx + fy * fy < cin * cin ? w.ang : route(b, w, crate.x, crate.y, S.t);
          if (a !== null) { bs = s; ga = a; toy = null; }
        }
      }
    }
    if (toy && ts > bs) {
      const dx = toy.x - w.x, dy = toy.y - w.y, fx = dx * ca + dy * sa, fy = Math.abs(dy * ca - dx * sa) - tr, cin = Math.max(0, tr - w.r - 10);
      const a = fx * fx + fy * fy < cin * cin ? w.ang : route(b, w, toy.x, toy.y, S.t);
      if (a !== null) { bs = ts; ga = a; rush = Math.hypot(dx, dy) > 90; }
    }
    // press the attack: close in on the nearest worm until it is comfortably in range
    if (quarry && qd > R * 0.7 && qd < HR) {
      const s = HUNT / (qd + 40);
      if (s > bs && MAP.los(w.x, w.y, quarry.x, quarry.y, w.r)) { bs = s; ga = Math.atan2(quarry.y - w.y, quarry.x - w.x); rush = qd > R; }
    }
    if (ga === null) {
      b.wander += rnd(-0.35, 0.35);
      const cx = CFG.W / 2 - w.x, cy = CFG.H / 2 - w.y;
      if (Math.abs(cx) > CFG.W * 0.38 || Math.abs(cy) > CFG.H * 0.38) b.wander = Math.atan2(cy, cx) + rnd(-0.5, 0.5);
      ga = b.wander;
    }
    // rampage: go and run somebody over (straight at the nearest bit of them, while there is time to get there)
    let charge = false;
    if (ram && prey && pd < HR * 1.2 && pd < (w.rage - 0.4) * HW.headSpeed(w) && MAP.los(w.x, w.y, prey.x, prey.y, w.r)) { ga = Math.atan2(prey.y - w.y, prey.x - w.x); charge = true; }

    // ---- shooting: short bursts with a fixed aim error each, then a breather ----
    I.fire = false; I.ax = 0; I.ay = 0;
    const lowAmmo = !special && w.ammo < own.max * 0.3;
    // no shooting under the spawn shield (it would drop the shield); save the last rounds for close targets
    if (tgt && td < R * (lowAmmo ? 0.65 : 1) && td >= prof.min && armed && w.shield <= 0) {
      if (b.burst <= 0 && b.fireT <= 0) {
        const keenly = (w.stuck > 0 ? 0.6 : 1) * (keen ? prof.rest : 1); // stuck in puke: nothing to do but shoot back
        const n = prof.burst;
        b.burst = ((rnd(n[0], n[1] + 1) | 0) - 0.5) * g.interval;
        b.fireT = b.burst + keenly * D.rest * rnd(1.0, 3.0) / (0.4 + b.skill);
        // small worms die to very few hits, so bots are sloppier against them (up to twice the error)
        b.aimErr = (Math.random() + Math.random() - 1) * AIM_ERR * D.err * (1.45 - b.skill) * (tw.mass < 60 ? 2 - tw.mass / 60 : 1);
      }
      if (b.burst > 0) {
        // good shots aim where a head is going, not where it is
        let lx = 0, ly = 0;
        if (D.lead > 0 && tgt === tw.pts[0]) { const k = D.lead * td / g.speed * HW.headSpeed(tw); lx = Math.cos(tw.ang) * k; ly = Math.sin(tw.ang) * k; }
        const a = Math.atan2(tgt.y + ly - w.y, tgt.x + lx - w.x) + b.aimErr + rnd(-0.05, 0.05);
        // the wobble may have put a counter in the line of fire: hold that shot
        if (MAP.los(w.x, w.y, w.x + Math.cos(a) * td, w.y + Math.sin(a) * td, g.br * 0.5 + 1)) { I.ax = Math.cos(a); I.ay = Math.sin(a); I.fire = true; }
      }
    }

    // ---- ability: a moment of reaction time, then let rip if it still makes sense ----
    let want = false;
    if (mark) {
      if (C.ability === 'fart') want = mq < (CFG.FART_R * 0.8) ** 2;
      else {
        // worth it on Jeff (it kills him), on a rampaging worm (it stops it), when there is ammo to follow up, or to stop someone right on top of us
        const d = Math.sqrt(mq); want = d > 38 && d < 138 && (!!CHARS[mark.ch].weakPuke || mark.rage > 0 || special || w.ammo >= own.max * 0.15 || d < 75);
      }
    }
    if (!want || b.abNo > 0) b.abArm = false;
    else if (!b.abArm) {
      // on the easier settings a bot often fails to think of it at all, and against a player (who gets no warning) more often still
      if (Math.random() > (mark.pid >= 0 ? D.abil * D.abil : D.abil)) b.abNo = rnd(2, 4); else { b.abArm = true; b.abT = rnd(0.12, 0.3) + (1 - b.skill) * 0.4; }
    }
    else if (b.abT <= 0) { b.abArm = false; I.abil = true; if (C.ability === 'puke') { const a = Math.atan2(b.my, b.mx); I.ax = Math.cos(a); I.ay = Math.sin(a); } }

    // ---- incoming fire: sidestep shots that are about to hit the head (behind a shot shield there is no need) ----
    let dodge = null;
    if (S.bullets.length && w.stuck <= 0 && !shielded && !charge && Math.random() < (0.3 + 0.6 * b.skill) * D.dodge) {
      const sp0 = HW.headSpeed(w), mvx = ca * sp0, mvy = sa * sp0; let soon = 0.6;
      for (const u of S.bullets) {
        if (u.owner === w.id) continue;
        const rx = w.x - u.x, ry = w.y - u.y; if (rx > 280 || rx < -280 || ry > 280 || ry < -280) continue;
        const vx = u.vx - mvx, vy = u.vy - mvy, t = (rx * vx + ry * vy) / (vx * vx + vy * vy + 1);
        if (t < 0.03 || t > soon) continue;
        const gg = HW.GUNS[u.ch], blast = gg.blast || 0;
        if (!blast && t > u.life + 0.05) continue; // it fizzles out before it gets here
        const cx = rx - vx * t, cy = ry - vy * t, safe = w.r + gg.br + 10 + blast * 0.55;
        if (cx * cx + cy * cy > safe * safe) continue;
        // move straight away from the line the shot is flying along, on the side we are already on
        const side = u.vx * ry - u.vy * rx >= 0 ? 1 : -1;
        soon = t; dodge = Math.atan2(u.vy, u.vx) + side * 1.45;
      }
    }

    // ---- steering ----
    let hurry = false;
    // frozen: in trouble. Get away from whoever is nearest, as fast as the ice allows
    if (w.chill > 0 && !charge) { b.panic = Math.max(b.panic, 0.8); if (threat && thd < 230) { ga = Math.atan2(w.y - threat.y, w.x - threat.x); hurry = true; } }
    if (dodge !== null) { ga = dodge; hurry = true; }
    if (scary) { ga = Math.atan2(w.y - scary.y, w.x - scary.x); hurry = sd < 170 || scary.rage > 0; }
    if (leave !== null) { ga = leave; hurry = true; }
    else if (b.esc > 0 && !scary) ga = b.escA;
    // pushing into a worm: wrench the wheel round, away from the point of contact, on the side the nose is already on
    let off = null;
    if (contact) { const ta = Math.atan2(contact.y - w.y, contact.x - w.x), sd2 = angDiff(w.ang, ta); off = ta + (sd2 >= 0 ? 1 : -1) * 2.2; b.panic = Math.max(b.panic, 0.5); }
    const slow = w.slow > 0, sp = Math.max(HW.headSpeed(w), C.speed * 0.4);
    const look = (50 + sp * 0.55) * (0.7 + b.skill * 0.5), tr2 = sp / (C.turn * (slow ? 0.8 : 1) * 0.85);
    // what is right in front of the nose matters most (we can only turn so fast)
    const noseBlocked = blocked(sim, w, w.x + ca * look * 0.45, w.y + sa * look * 0.45, 6) || blocked(sim, w, w.x + ca * look * 0.2, w.y + sa * look * 0.2, 4);
    const base = noseBlocked ? w.ang : ga;
    let chosen = null, bestC = -1, bestA = base + 2.2;
    for (let i = noseBlocked ? 1 : 0; i < OFFS.length; i++) {
      const a = base + OFFS[i], c = clearance(sim, w, a, look, tr2);
      if (c === 4) { chosen = a; break; }
      if (c > bestC) { bestC = c; bestA = a; }
    }
    if (chosen === null) chosen = bestA; // boxed in: take the way that stays clear the longest
    if (off !== null) chosen = off;      // the look-ahead is no help when the nose is already in somebody's side
    else if (b.esc > 0 && b.escH && !scary && leave === null && (w.x - b.sx) ** 2 + (w.y - b.sy) ** 2 < 196) chosen = b.escA;   // ...or still pinned where it got wedged
    if (noseBlocked) b.panic = Math.max(b.panic, 0.3);
    I.mx = Math.cos(chosen); I.my = Math.sin(chosen);
    // boost to get out of trouble or to run somebody down, but never blind and never when it would starve us.
    // On hot sauce it costs nothing: then it is also used to get to a pickup or a fight first (flat out all the
    // time just means arriving everywhere too fast to steer).
    const open = !noseBlocked && Math.abs(angDiff(chosen, w.ang)) < 0.7, hot = w.sauce > 0.3;
    I.boost = open && (hot || w.mass > C.startMass * 0.8) && ((b.panic > 0.6 && Math.random() < 0.7) || hurry || (charge && pd < 240) || (hot && rush));
  };
})(window.HW);
