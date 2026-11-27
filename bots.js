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
  let fear = false;      // Jeff only: keep clear of worms that are ready to puke

  // would worm w be in trouble with its head at (x, y)?
  function blocked(sim, w, x, y, pad) {
    if (x < 24 || y < 24 || x > CFG.W - 24 || y > CFG.H - 24) return true;
    if (MAP.hit(x, y, w.r + pad + 3)) return true;   // counters, tables, crates...
    const S = sim.S;
    for (const z of S.zones) { if (z.owner === w.id || z === skipZone) continue; const dx = z.x - x, dy = z.y - y, r = z.r + 14; if (dx * dx + dy * dy < r * r) return true; }
    for (let i = 0; i < haz.length; i += 2) { const dx = haz[i] - x, dy = haz[i + 1] - y; if (dx * dx + dy * dy < hazR2) return true; }
    for (const o of S.worms) {
      if (o === w || !o.alive || o.shield > 0.6) continue;
      const m = o.r + w.r + pad + 3, far = fear ? 150 : 95;
      if (x < o.bx0 - m - far || x > o.bx1 + m + far || y < o.by0 - m - far || y > o.by1 + m + far) continue;
      // its head is about to sweep along this line: stay off it
      const reach = o.stuck > 0 ? 0 : CHARS[o.ch].speed * (o.boosting ? CFG.BOOST_MULT : 1) * (o.slow > 0 ? CFG.SLOW_MULT : 1) * 0.45;
      const ux = Math.cos(o.ang), uy = Math.sin(o.ang), rx = x - o.x, ry = y - o.y;
      const t = clamp(rx * ux + ry * uy, 0, reach), hx = rx - ux * t, hy = ry - uy * t, hq = hx * hx + hy * hy;
      if (hq < (m + 6) * (m + 6)) return true;
      if (fear && hq < 150 * 150 && o.abil <= 1.5 && o.stuck <= 0 && CHARS[o.ch].ability === 'puke') return true;
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

  const OFFS = [0, 0.55, -0.55, 1.1, -1.1, 1.7, -1.7, 2.4, -2.4, 3.1];
  // How many shots a bot looses off before it eases up, per gun: [fewest, most]. This is what makes
  // each gun play like itself: the SMG sprays, the skewer plinks, the cannon and rockets are single shots.
  const BURST = [[2, 3.5], [1, 3], [7, 17], [3, 6], [1, 2]];
  const LAPSE = 0.06;   // chance per think of a lapse of attention is LAPSE * (1.3 - skill): about 5% for the worst bots, 2% for the best
  const AIM_ERR = 0.65; // the clumsiest bot's worst burst is off by about AIM_ERR * 0.95 radians

  HW.botThink = function (sim, w, dt) {
    const b = w.bot, S = sim.S, C = CHARS[w.ch], g = C.gun, I = w.inp, D = HW.DIFFS[S.diff];
    if (b.panic > 0) b.panic -= dt;
    if (b.fireT > 0) b.fireT -= dt;
    if (b.burst > 0) b.burst -= dt;
    if (b.abT > 0) b.abT -= dt;
    if (b.abNo > 0) b.abNo -= dt;
    if (b.esc > 0) b.esc -= dt;
    // wedged against an obstacle or a wall for a while: pick a new way out
    b.sT -= dt;
    if (b.sT <= 0) {
      const mx = w.x - b.sx, my = w.y - b.sy;
      if (mx * mx + my * my < 22 * 22 && w.stuck <= 0) { b.esc = rnd(0.9, 1.6); b.escA = w.ang + (Math.random() < 0.5 ? 1 : -1) * rnd(1.6, 2.8); }
      b.sx = w.x; b.sy = w.y; b.sT = 1.5;
    }
    b.think -= dt; if (b.think > 0) return;
    b.think = (0.09 + Math.random() * 0.08 + (1 - b.skill) * 0.08) * D.think;
    // now and then a bot's attention wanders and it just holds its course for a moment: this is what
    // lets a player cut one off, and it happens more to the less skilled ones. Nobody dozes off next
    // to a fart cloud or a puke puddle though.
    if (Math.random() < LAPSE * D.lapse * (1.3 - b.skill)) {
      let calm = true;
      for (const z of S.zones) { if (z.owner === w.id) continue; const dx = z.x - w.x, dy = z.y - w.y, r = z.r + 150; if (dx * dx + dy * dy < r * r) { calm = false; break; } }
      if (calm) { b.think += rnd(0.25, 0.6); I.fire = false; I.boost = false; return; }
    }

    // ---- other worms: what to shoot, who to use the ability on, who to run from ----
    let tgt = null, tw = null, td = 1e12, scary = null, sd = 1e9, mark = null, mq = 1e12;
    // never open fire from further than a player can see (about 170 px from the middle of their screen; less on easy)
    const R = Math.min(g.range * 0.8, D.engage);
    // at the start of a match, and just after a human spawns, the bots leave humans alone
    const warm = S.players.length > 0 && CFG.MATCH_T - S.match.t < D.warm;
    const ready = C.ability && w.abil <= 0 && w.stuck <= 0, fp = w.pts[Math.min(w.pts.length - 1, 16)]; // fp: where a fart would come out
    for (const o of S.worms) {
      if (o === w || !o.alive || o.shield > 0) continue;
      const hx = o.x - w.x, hy = o.y - w.y, hq = Math.sqrt(hx * hx + hy * hy);
      const spare = o.pid >= 0 && (warm || o.mercy > 0);
      // Jeff dies in puke, so he keeps his distance from a worm that is ready to throw up
      if (C.weakPuke && CHARS[o.ch].ability === 'puke' && o.abil <= 1.5 && o.stuck <= 0 && hq < 210 && hq < sd) { sd = hq; scary = o; }
      // ability target: the head that will be nearest to where the cloud / puddle can go
      if (ready && hq < 260 && !spare) {
        const lead = o.stuck > 0 ? 0 : CHARS[o.ch].speed * 0.3, px = o.x + Math.cos(o.ang) * lead, py = o.y + Math.sin(o.ang) * lead;
        const ax = C.ability === 'fart' ? px - fp.x : px - w.x, ay = C.ability === 'fart' ? py - fp.y : py - w.y, q = ax * ax + ay * ay;
        if (q < mq && (C.ability === 'fart' || o.stuck <= 0)) { mq = q; mark = o; b.mx = ax; b.my = ay; }
      }
      if (spare || w.x < o.bx0 - R || w.x > o.bx1 + R || w.y < o.by0 - R || w.y > o.by1 + R) continue;
      for (let i = 0; i < o.pts.length; i += 3) { const dx = o.pts[i].x - w.x, dy = o.pts[i].y - w.y, d = dx * dx + dy * dy; if (d < td) { td = d; tgt = o.pts[i]; tw = o; } }
    }
    td = Math.sqrt(td);
    if (tgt && !MAP.los(w.x, w.y, tgt.x, tgt.y, 2)) tgt = null;   // no shooting at what is behind a counter

    // ---- scratch state for blocked() ----
    haz.length = 0; hazR2 = (w.r + 19) * (w.r + 19); skipZone = null;
    fear = !!C.weakPuke && w.shield <= 0.8 && !(scary && sd < 160); // already too close: just run (see steering)
    let leave = null;
    for (const z of S.zones) { if (z.owner === w.id) continue; const dx = w.x - z.x, dy = w.y - z.y, r = z.r + 14; if (dx * dx + dy * dy < r * r) { skipZone = z; leave = Math.atan2(dy, dx); break; } }

    // ---- goal: food, and ammo when the gun is getting empty ----
    let ga = null, bs = 0, crate = null, cq = 1e12;
    const seeHaz = Math.max(26, (b.skill - 0.3) * 240) ** 2; // sharp bots spot veggies and mushrooms early, dozy ones blunder into them
    // A worm cannot reach things inside its own turning circle: chasing them means circling forever.
    // tr = turning radius (with slack for thinking time), tin = how deep inside the circle is hopeless
    const ca = Math.cos(w.ang), sa = Math.sin(w.ang), tr = C.speed / C.turn * 1.2, tin = Math.max(0, tr - w.r - C.eat * 0.7), near2 = tr * tr * 5;
    for (const it of S.items.values()) {
      const dx = it.x - w.x, dy = it.y - w.y;
      if (it.k === 'a') { const q = dx * dx + dy * dy; if (q < cq) { cq = q; crate = it; } continue; }
      if (dx > 300 || dx < -300 || dy > 300 || dy < -300) continue;
      const q = dx * dx + dy * dy;
      if (it.k !== 'f') { if (w.shield <= 0 && q < seeHaz) haz.push(it.x, it.y); continue; }
      if (q < near2) { const fx = dx * ca + dy * sa, fy = Math.abs(dy * ca - dx * sa) - tr; if (fx * fx + fy * fy < tin * tin) continue; }
      const d = Math.sqrt(q), a = Math.atan2(dy, dx);
      const s = it.v / (d + 40) * (1 - Math.abs(angDiff(a, w.ang)) * 0.18);
      // not worth dying for: skip food lying against another worm, in a cloud or in a puddle, and food behind an obstacle
      if (s > bs && !blocked(sim, w, it.x, it.y, -6) && MAP.los(w.x, w.y, it.x, it.y, 0)) { bs = s; ga = a; }
    }
    if (crate && w.ammo < g.max) {
      // empty: cross the map for a crate. low: go a fair way. otherwise only if it is on the way
      const d = Math.sqrt(cq), dry = w.ammo <= 0, low = w.ammo < g.max * 0.3;
      if (d < (dry ? 1400 : low ? 650 : 280)) {
        const dx = crate.x - w.x, dy = crate.y - w.y, fx = dx * ca + dy * sa, fy = Math.abs(dy * ca - dx * sa) - tr, cin = Math.max(0, tr - w.r - 7);
        // a crate inside the turning circle: run straight on for a moment and come back at it
        const a = fx * fx + fy * fy < cin * cin ? w.ang : Math.atan2(dy, dx);
        const s = (dry ? 180 : low ? 90 : 12) / (d + 40) * (1 - Math.abs(angDiff(a, w.ang)) * 0.18);
        if (s > bs) { bs = s; ga = a; }
      }
    }
    if (ga === null) {
      b.wander += rnd(-0.35, 0.35);
      const cx = CFG.W / 2 - w.x, cy = CFG.H / 2 - w.y;
      if (Math.abs(cx) > CFG.W * 0.38 || Math.abs(cy) > CFG.H * 0.38) b.wander = Math.atan2(cy, cx) + rnd(-0.5, 0.5);
      ga = b.wander;
    }

    // ---- shooting: short bursts with a fixed aim error each, then a breather ----
    I.fire = false; I.ax = 0; I.ay = 0;
    const lowAmmo = w.ammo < g.max * 0.3;
    // no shooting under the spawn shield (it would drop the shield); save the last rounds for close targets
    if (tgt && td < R * (lowAmmo ? 0.65 : 1) && w.ammo > 0 && w.shield <= 0) {
      if (b.burst <= 0 && b.fireT <= 0) {
        const keen = w.stuck > 0 ? 0.6 : 1; // stuck in puke: nothing to do but shoot back
        const n = BURST[w.ch] || BURST[0];
        b.burst = ((rnd(n[0], n[1] + 1) | 0) - 0.5) * g.interval;
        b.fireT = b.burst + keen * D.rest * rnd(1.0, 3.0) / (0.4 + b.skill);
        // small worms die to very few hits, so bots are sloppier against them (up to twice the error)
        b.aimErr = (Math.random() + Math.random() - 1) * AIM_ERR * D.err * (1.45 - b.skill) * (tw.mass < 60 ? 2 - tw.mass / 60 : 1);
      }
      if (b.burst > 0) {
        // good shots aim where a head is going, not where it is
        let lx = 0, ly = 0;
        if (D.lead > 0 && tgt === tw.pts[0] && tw.stuck <= 0) { const k = D.lead * td / g.speed * CHARS[tw.ch].speed * (tw.boosting ? CFG.BOOST_MULT : 1) * (tw.slow > 0 ? CFG.SLOW_MULT : 1); lx = Math.cos(tw.ang) * k; ly = Math.sin(tw.ang) * k; }
        const a = Math.atan2(tgt.y + ly - w.y, tgt.x + lx - w.x) + b.aimErr + rnd(-0.05, 0.05); I.ax = Math.cos(a); I.ay = Math.sin(a); I.fire = true;
      }
    }

    // ---- ability: a moment of reaction time, then let rip if it still makes sense ----
    let want = false;
    if (mark) {
      if (C.ability === 'fart') want = mq < (CFG.FART_R * 0.8) ** 2;
      else {
        // worth it on Jeff (it kills him), when there is ammo to follow up, or to stop someone right on top of us
        const d = Math.sqrt(mq); want = d > 38 && d < 138 && (!!CHARS[mark.ch].weakPuke || w.ammo >= g.max * 0.15 || d < 75);
      }
    }
    if (!want || b.abNo > 0) b.abArm = false;
    else if (!b.abArm) {
      // on the easier settings a bot often fails to think of it at all
      if (Math.random() > D.abil) b.abNo = rnd(2, 4); else { b.abArm = true; b.abT = rnd(0.12, 0.3) + (1 - b.skill) * 0.4; }
    }
    else if (b.abT <= 0) { b.abArm = false; I.abil = true; if (C.ability === 'puke') { const a = Math.atan2(b.my, b.mx); I.ax = Math.cos(a); I.ay = Math.sin(a); } }

    // ---- incoming fire: sidestep shots that are about to hit the head ----
    let dodge = null;
    if (S.bullets.length && w.stuck <= 0 && Math.random() < (0.3 + 0.6 * b.skill) * D.dodge) {
      const sp0 = C.speed * (w.slow > 0 ? CFG.SLOW_MULT : 1), mvx = ca * sp0, mvy = sa * sp0; let soon = 0.6;
      for (const u of S.bullets) {
        if (u.owner === w.id) continue;
        const rx = w.x - u.x, ry = w.y - u.y; if (rx > 280 || rx < -280 || ry > 280 || ry < -280) continue;
        const vx = u.vx - mvx, vy = u.vy - mvy, t = (rx * vx + ry * vy) / (vx * vx + vy * vy + 1);
        if (t < 0.03 || t > soon) continue;
        const gg = CHARS[u.ch].gun, blast = gg.blast || 0;
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
    if (dodge !== null) { ga = dodge; hurry = true; }
    if (scary) { ga = Math.atan2(w.y - scary.y, w.x - scary.x); hurry = sd < 170; }
    if (leave !== null) { ga = leave; hurry = true; }
    else if (b.esc > 0) ga = b.escA;
    const slow = w.slow > 0, sp = C.speed * (w.boosting ? CFG.BOOST_MULT : 1) * (slow ? CFG.SLOW_MULT : 1);
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
    if (noseBlocked) b.panic = Math.max(b.panic, 0.3);
    I.mx = Math.cos(chosen); I.my = Math.sin(chosen);
    // boost to get out of trouble, but never blind and never when it would starve us
    const open = !noseBlocked && Math.abs(angDiff(chosen, w.ang)) < 0.7;
    I.boost = open && w.mass > C.startMass * 0.8 && ((b.panic > 0.6 && Math.random() < 0.7) || hurry);
  };
})(window.HW);
