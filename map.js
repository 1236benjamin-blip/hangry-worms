// Hangry Worms - the arena: size, obstacles (they block worms and shots), floor zones, floor graffiti
// The layout is fixed and the same on every device, so online clients never need to be sent the map.
'use strict';
(function (HW) {
  const W = 2400, H = 2400;
  // One quadrant (top left) is written out by hand; the other three are the same pieces turned 90 degrees
  // round the middle. k: counter (long), vend (vending machine), crate, table (round), can (round)
  const BASE = [
    { k: 'counter', x: 300, y: 700, w: 280, h: 36 },
    { k: 'counter', x: 700, y: 260, w: 36, h: 260 },
    { k: 'table', x: 440, y: 430, r: 38 },
    { k: 'can', x: 560, y: 960, r: 24 },
    { k: 'vend', x: 940, y: 560, w: 60, h: 46 },
    { k: 'crate', x: 220, y: 220, w: 42, h: 42 },
    { k: 'table', x: 800, y: 800, r: 30 },
    { k: 'crate', x: 1020, y: 250, w: 42, h: 42 },
    { k: 'can', x: 250, y: 1010, r: 22 }
  ];
  const RING = [{ k: 'counter', x: 1040, y: 940, w: 320, h: 36 }];   // four counters round the middle: the food court
  const turn = o => o.r ? { k: o.k, x: W - o.y, y: o.x, r: o.r } : { k: o.k, x: W - o.y - o.h, y: o.x, w: o.h, h: o.w };
  const obs = [];
  let q = BASE, g = RING;
  for (let i = 0; i < 4; i++) {
    for (const o of q) obs.push(Object.assign({ zone: i }, o));
    for (const o of g) obs.push(Object.assign({ zone: 4 }, o));
    q = q.map(turn); g = g.map(turn);
  }
  obs.push({ k: 'table', x: W / 2, y: H / 2, r: 44, zone: 4 });
  obs.forEach((o, i) => {
    o.i = i;
    if (o.r) { o.x0 = o.x - o.r; o.y0 = o.y - o.r; o.x1 = o.x + o.r; o.y1 = o.y + o.r; }
    else { o.x0 = o.x; o.y0 = o.y; o.x1 = o.x + o.w; o.y1 = o.y + o.h; }
  });

  // floor zones: 0 kitchen (top left), 1 candy shop (top right), 2 salad bar (bottom right), 3 grease pit (bottom left), 4 food court
  const zones = [];
  let z = { x: 150, y: 150, w: 820, h: 820 };
  for (let i = 0; i < 4; i++) { zones.push(Object.assign({ zone: i }, z)); z = turn(Object.assign({ k: '' }, z)); }
  zones.push({ zone: 4, x: 900, y: 900, w: 600, h: 600 });

  // grid lookup: every cell lists the obstacles within PAD of it, so a test only looks at one short list
  const CELL = 120, PAD = 44, GW = Math.ceil(W / CELL), GH = Math.ceil(H / CELL), grid = [], NONE = [];
  for (let i = 0; i < GW * GH; i++) grid.push(NONE);
  for (const o of obs) {
    const i0 = Math.max(0, Math.floor((o.x0 - PAD) / CELL)), i1 = Math.min(GW - 1, Math.floor((o.x1 + PAD) / CELL));
    const j0 = Math.max(0, Math.floor((o.y0 - PAD) / CELL)), j1 = Math.min(GH - 1, Math.floor((o.y1 + PAD) / CELL));
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) { const k = j * GW + i; if (grid[k] === NONE) grid[k] = []; grid[k].push(o); }
  }
  const cell = (x, y) => { const i = (x / CELL) | 0, j = (y / CELL) | 0; return x >= 0 && y >= 0 && i < GW && j < GH ? grid[j * GW + i] : NONE; };

  const M = HW.MAP = { W, H, obs, zones, PAD };

  // does a circle of radius r (at most MAP.PAD) at (x, y) touch an obstacle? returns the obstacle or null
  M.hit = function (x, y, r) {
    const l = cell(x, y);
    for (let n = 0; n < l.length; n++) {
      const o = l[n];
      if (o.r) { const dx = x - o.x, dy = y - o.y, m = o.r + r; if (dx * dx + dy * dy < m * m) return o; }
      else {
        const cx = x < o.x0 ? o.x0 : x > o.x1 ? o.x1 : x, cy = y < o.y0 ? o.y0 : y > o.y1 ? o.y1 : y, dx = x - cx, dy = y - cy;
        if (dx * dx + dy * dy < r * r || (dx === 0 && dy === 0)) return o;
      }
    }
    return null;
  };
  // Move a circle out of whatever it overlaps. Writes the new position and the surface normal into out
  // ({x, y, nx, ny}) and returns true if it had to move.
  M.push = function (x, y, r, out) {
    out.x = x; out.y = y; out.nx = 0; out.ny = 0;
    const l = cell(x, y); let moved = false;
    for (let n = 0; n < l.length; n++) {
      const o = l[n];
      if (o.r) {
        const dx = out.x - o.x, dy = out.y - o.y, m = o.r + r, d2 = dx * dx + dy * dy; if (d2 >= m * m) continue;
        const d = Math.sqrt(d2), nx = d > 0.01 ? dx / d : 1, ny = d > 0.01 ? dy / d : 0;
        out.x = o.x + nx * m; out.y = o.y + ny * m; out.nx = nx; out.ny = ny; moved = true;
      } else {
        const cx = out.x < o.x0 ? o.x0 : out.x > o.x1 ? o.x1 : out.x, cy = out.y < o.y0 ? o.y0 : out.y > o.y1 ? o.y1 : out.y;
        const dx = out.x - cx, dy = out.y - cy, d2 = dx * dx + dy * dy;
        if (d2 > 1e-6) { if (d2 >= r * r) continue; const d = Math.sqrt(d2); out.nx = dx / d; out.ny = dy / d; out.x = cx + out.nx * r; out.y = cy + out.ny * r; }
        else {
          // the middle of the circle is inside the box: leave through the nearest side
          const a = out.x - o.x0, b = o.x1 - out.x, c = out.y - o.y0, e = o.y1 - out.y, m = Math.min(a, b, c, e);
          if (m === a) { out.x = o.x0 - r; out.nx = -1; out.ny = 0; } else if (m === b) { out.x = o.x1 + r; out.nx = 1; out.ny = 0; }
          else if (m === c) { out.y = o.y0 - r; out.nx = 0; out.ny = -1; } else { out.y = o.y1 + r; out.nx = 0; out.ny = 1; }
        }
        moved = true;
      }
    }
    return moved;
  };
  // line of sight: true when nothing stands between the two points (pad widens every obstacle a little)
  M.los = function (ax, ay, bx, by, pad) {
    pad = pad || 0;
    const lx0 = Math.min(ax, bx) - pad, lx1 = Math.max(ax, bx) + pad, ly0 = Math.min(ay, by) - pad, ly1 = Math.max(ay, by) + pad, dx = bx - ax, dy = by - ay;
    for (let n = 0; n < obs.length; n++) {
      const o = obs[n]; if (o.x1 < lx0 || o.x0 > lx1 || o.y1 < ly0 || o.y0 > ly1) continue;
      if (o.r) {
        const l2 = dx * dx + dy * dy, t = l2 > 0 ? Math.max(0, Math.min(1, ((o.x - ax) * dx + (o.y - ay) * dy) / l2)) : 0;
        const px = ax + dx * t - o.x, py = ay + dy * t - o.y, m = o.r + pad; if (px * px + py * py < m * m) return false;
      } else {
        // clip the segment against the box (slab test)
        let t0 = 0, t1 = 1, ok = true; const x0 = o.x0 - pad, x1 = o.x1 + pad, y0 = o.y0 - pad, y1 = o.y1 + pad;
        if (Math.abs(dx) < 1e-9) { if (ax < x0 || ax > x1) ok = false; }
        else { let u = (x0 - ax) / dx, v = (x1 - ax) / dx; if (u > v) { const s = u; u = v; v = s; } if (u > t0) t0 = u; if (v < t1) t1 = v; if (t0 > t1) ok = false; }
        if (ok) {
          if (Math.abs(dy) < 1e-9) { if (ay < y0 || ay > y1) ok = false; }
          else { let u = (y0 - ay) / dy, v = (y1 - ay) / dy; if (u > v) { const s = u; u = v; v = s; } if (u > t0) t0 = u; if (v < t1) t1 = v; if (t0 > t1) ok = false; }
        }
        if (ok) return false;
      }
    }
    return true;
  };
  // a random free spot at least `edge` from the walls and `r` clear of every obstacle
  const tmp = { x: 0, y: 0, nx: 0, ny: 0 };
  M.spot = function (edge, r, box) {
    for (let t = 0; t < 12; t++) {
      const x = box ? box.x + Math.random() * box.w : edge + Math.random() * (W - 2 * edge), y = box ? box.y + Math.random() * box.h : edge + Math.random() * (H - 2 * edge);
      if (!M.hit(x, y, r)) return { x, y };
    }
    const x = edge + Math.random() * (W - 2 * edge), y = edge + Math.random() * (H - 2 * edge);
    M.push(x, y, r, tmp); return { x: tmp.x, y: tmp.y };
  };

  // ---------- floor graffiti (drawn by render.js; purely for laughs) ----------
  // [text, zone it belongs in (-1 = anywhere), size]
  M.GRAFFITI = [
    ['EAT MORE', -1, 5], ['BEN SUCKS', -1, 5], ['NO VEGGIES', -1, 4], ['JUNK FOOD 4 EVER', -1, 3], ['DIET STARTS NEVER', -1, 3],
    ['FRIES BEFORE GUYS', 3, 3], ['GREASE IS A FOOD GROUP', 3, 2], ['EXTRA CHEESE', 3, 4], ['DEEP FRY EVERYTHING', 3, 3], ['5 SECOND RULE', 3, 3],
    ['SALAD BAR (GROSS)', 2, 3], ['DANGER: VEGGIES', 2, 4], ['BROCCOLI = DEATH', 2, 3], ['KALE? NOPE', 2, 4], ['SALAD IS A TRAP', 2, 3], ['WHO ORDERED THIS', 2, 2],
    ['SUGAR RUSH', 1, 4], ['DESSERT FIRST', 1, 3], ['CANDY IS A VEGETABLE', 1, 2], ['SPRINKLES ON EVERYTHING', 1, 2], ['MUSHROOMS ARE WEIRD', 1, 3],
    ['DO NOT LICK FLOOR', 0, 3], ['CHEF QUIT', 0, 4], ['CALORIES DONT COUNT HERE', 0, 2], ['SECOND BREAKFAST', 0, 3], ['WASH YOUR HANDS (LOL)', 0, 2],
    ['ALL U CAN EAT', 4, 4], ['BURP ZONE', 4, 3], ['WHO FARTED?', -1, 4], ['CHEW LOUDER', -1, 3], ['BEN EATS SALAD', -1, 3], ['BEN SUCKS', -1, 3],
    ['JEFF SMELLS', -1, 3], ['NATE ATE IT', -1, 3], ['WESLEY WUZ HERE', -1, 2], ['CHANDLER OWES ME FRIES', -1, 2], ['NO SHIRT NO SHOES NO SALAD', -1, 2],
    ['VEGGIES R 4 LOSERS', -1, 3], ['HANGRY?', -1, 5], ['MORE BURGERS', -1, 4], ['FART RESPONSIBLY', -1, 3], ['I THOUGHT YOU SAID NO KALE', -1, 2],
    ['SEND SNACKS', -1, 4], ['YOUR MOM EATS KALE', -1, 2], ['PIZZA IS A SALAD', -1, 3], ['BURP', -1, 5], ['SO HUNGRY', -1, 3], ['EAT IT OR WEAR IT', -1, 2]
  ];
})(window.HW);
