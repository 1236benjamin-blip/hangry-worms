// Hangry Worms - rendering (low-res pixel canvas, scaled up by CSS)
'use strict';
(function (HW) {
  const CFG = HW.CFG, CHARS = HW.CHARS, MAP = HW.MAP, text = HW.text;
  const R = HW.Render = { W: 640, H: 360, scale: 2, target: 270 };
  R.setTarget = function (t) { if (R.target !== t) { R.target = t; R.resize(); if (HW.Input) HW.Input.layout(); } };
  let cv, cx, vc, vx, pattern, zonePat;

  R.init = function (canvas) {
    cv = R.canvas = canvas; cx = R.ctx = cv.getContext('2d', { alpha: false });
    vc = HW.mk(16, 16); vx = vc.getContext('2d', { alpha: false });
    R.resize(); window.addEventListener('resize', R.resize); window.addEventListener('orientationchange', () => setTimeout(R.resize, 250));
  };
  R.resize = function () {
    const cw = window.innerWidth, chh = window.innerHeight, dpr = window.devicePixelRatio || 1;
    const minDev = Math.min(cw, chh) * dpr;
    let s = Math.max(1, Math.round(minDev / R.target));
    let W = Math.ceil(cw * dpr / s), H = Math.ceil(chh * dpr / s);
    // keep the long side sane on ultra-wide / huge screens
    while (Math.max(W, H) > R.target * 2.45) { s++; W = Math.ceil(cw * dpr / s); H = Math.ceil(chh * dpr / s); }
    R.W = W; R.H = H; R.scale = s / dpr; cv.width = W; cv.height = H;
    cv.style.width = (W * s / dpr) + 'px'; cv.style.height = (H * s / dpr) + 'px';
    cx.imageSmoothingEnabled = false;
  };

  // ---------- fx ----------
  const fx = HW.fx = { parts: [], texts: [], feed: [] };
  fx.burst = function (x, y, cols, n, sp, life, sz) {
    if (fx.parts.length > 500) return;
    for (let i = 0; i < n; i++) { const a = Math.random() * 6.283, v = sp * (0.3 + Math.random() * 0.7); fx.parts.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, t: life * (0.5 + Math.random() * 0.5), c: cols[(Math.random() * cols.length) | 0], s: sz || 2 }); }
  };
  fx.text = function (x, y, s, c) { if (fx.texts.length < 40) fx.texts.push({ x, y, s, c, t: 1.1 }); };
  fx.update = function (dt) {
    for (let i = fx.parts.length - 1; i >= 0; i--) { const p = fx.parts[i]; p.t -= dt; if (p.t <= 0) { fx.parts[i] = fx.parts[fx.parts.length - 1]; fx.parts.pop(); continue; } p.x += p.vx * dt; p.y += p.vy * dt; p.vx *= 0.94; p.vy *= 0.94; }
    for (let i = fx.texts.length - 1; i >= 0; i--) { const p = fx.texts[i]; p.t -= dt; p.y -= 16 * dt; if (p.t <= 0) fx.texts.splice(i, 1); }
    for (let i = fx.feed.length - 1; i >= 0; i--) { fx.feed[i].t -= dt; if (fx.feed[i].t <= 0) fx.feed.splice(i, 1); }
  };
  fx.clear = function () { fx.parts.length = 0; fx.texts.length = 0; fx.feed.length = 0; };

  const discCache = {};
  function disc(color, r) {
    const k = color + '_' + r; let c = discCache[k]; if (c) return c;
    c = HW.mk(r * 2 + 1, r * 2 + 1); const x = c.getContext('2d'); x.fillStyle = color;
    for (let j = -r; j <= r; j++) { const w = Math.floor(Math.sqrt(r * r + r * 0.8 - j * j)); x.fillRect(r - w, j + r, w * 2 + 1, 1); }
    return discCache[k] = c;
  }
  function pxLine(c, x0, y0, x1, y1, col, th) {
    const dx = x1 - x0, dy = y1 - y0, n = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy))));
    c.fillStyle = col; for (let i = 0; i <= n; i++) c.fillRect(Math.round(x0 + dx * i / n), Math.round(y0 + dy * i / n), th, th);
  }
  function ring(c, x, y, r, col, n, phase, sz) {
    c.fillStyle = col; for (let i = 0; i < n; i++) { const a = phase + i * 6.283 / n; c.fillRect(Math.round(x + Math.cos(a) * r), Math.round(y + Math.sin(a) * r), sz, sz); }
  }

  function segColor(ch, i, cols) {
    switch (ch) {
      case 0: return cols[(i >> 2) & 1];
      case 1: return cols[i % 6 < 2 ? 1 : 0];
      case 2: return cols[i % 5 === 2 ? 1 : 0];
      case 3: return cols[(i >> 1) & 1];
      default: return cols[(i * 7 + (i >> 2)) % 5 < 2 ? 1 : 0];
    }
  }

  function drawWorm(c, w, ox, oy, t, leader, isMe) {
    const C = CHARS[w.ch], cols = C.colors[w.variant % 4], p = w.pts, r = w.r, n = p.length;
    if (w.shield > 0 && ((t * 12) | 0) % 2) c.globalAlpha = 0.5;
    for (let i = n - 1; i >= 0; i--) {
      const ft = n - 1 - i; let rr = r; if (ft < 4) rr = Math.max(3, r - 4 + ft);
      const s = HW.seg(i === 0 ? cols[0] : segColor(w.ch, i, cols), rr);
      c.drawImage(s, Math.round(p[i].x - ox) - rr - 1, Math.round(p[i].y - oy) - rr - 1);
    }
    // name written along the body, always reading left to right
    const name = C.name, L = name.length, st = 3;
    if (n >= st + L) {
      const dxn = p[st + L - 1].x - p[st].x, dyn = p[st + L - 1].y - p[st].y;
      // sideways bodies read left to right; upright bodies read top to bottom on every 2nd segment so letters don't pile up
      if (w._vert === undefined) w._vert = Math.abs(dyn) > Math.abs(dxn); else if (Math.abs(dyn) > Math.abs(dxn) * 1.4) w._vert = true; else if (Math.abs(dxn) > Math.abs(dyn) * 1.4) w._vert = false;
      const d = w._vert ? dyn : dxn, step = w._vert && n >= st + L * 2 ? 2 : 1;
      if (w._rev === undefined) w._rev = d < 0; else if (d > 8) w._rev = false; else if (d < -8) w._rev = true;
      for (let k = 0; k < L; k++) { const q = p[st + (w._rev ? L - 1 - k : k) * step]; HW.glyph(c, name[k], Math.round(q.x - ox), Math.round(q.y - oy), '#ffffff'); }
    }
    // head
    const hx = Math.round(w.x - ox), hy = Math.round(w.y - oy);
    const dx = Math.cos(w.ang), dy = Math.sin(w.ang), ax = Math.cos(w.aim), ay = Math.sin(w.aim);
    // arms + gun
    const gx = hx + ax * (r + 5), gy = hy + ay * (r + 5), arm = HW.shade(cols[0], -0.3);
    pxLine(c, hx - ay * (r - 1), hy + ax * (r - 1), gx, gy, arm, 2);
    pxLine(c, hx + ay * (r - 1), hy - ax * (r - 1), gx + ax * 4, gy + ay * 4, arm, 2);
    const g = HW.gunSprOf(w);   // their own gun, or the special one they picked up
    c.save(); c.translate(Math.round(gx), Math.round(gy)); c.rotate(w.aim); if (ax < 0) c.scale(1, -1); c.drawImage(g.c, -g.px, -g.py); c.restore();
    c.fillStyle = HW.PAL.T; c.fillRect(Math.round(gx) - 1, Math.round(gy) - 1, 2, 2);
    // eyes
    const es = C.big ? 4 : 3;
    for (let s = -1; s <= 1; s += 2) {
      const ex = Math.round(hx + dx * r * 0.3 - dy * s * r * 0.5), ey = Math.round(hy + dy * r * 0.3 + dx * s * r * 0.5);
      if (w.ch === 1) { c.fillStyle = '#111'; c.fillRect(ex - 2, ey - 2, 5, 4); c.fillStyle = '#7fc4ff'; c.fillRect(ex - 1, ey - 1, 1, 1); }
      else {
        c.fillStyle = '#1a1423'; c.fillRect(ex - (es >> 1) - 1, ey - (es >> 1) - 1, es + 2, es + 2);
        c.fillStyle = w.stuck > 0 ? '#c8e86a' : '#fff'; c.fillRect(ex - (es >> 1), ey - (es >> 1), es, es);
        c.fillStyle = '#1a1423'; c.fillRect(ex - (es >> 1) + (ax > 0.3 ? es - 2 : ax < -0.3 ? 0 : (es - 2) >> 1), ey - (es >> 1) + (ay > 0.3 ? es - 2 : ay < -0.3 ? 0 : (es - 2) >> 1), 2, 2);
      }
    }
    if (w.ch === 1) pxLine(c, hx + dx * r * 0.3 - dy * r * 0.5, hy + dy * r * 0.3 + dx * r * 0.5, hx + dx * r * 0.3 + dy * r * 0.5, hy + dy * r * 0.3 - dx * r * 0.5, '#111', 1);
    // hats
    if (w.ch === 0) c.drawImage(HW.hatSpr.ben, hx - 5, hy - r - 3);
    else if (w.ch === 4) c.drawImage(HW.hatSpr.jeff, hx - 5, hy - r - 3);
    else if (w.ch === 3) c.drawImage(((t * 8) | 0) % 2 ? HW.hatSpr.wes : HW.hatSpr.wes2, hx - 5, hy - r - 4);
    else if (w.ch === 2) {
      const bx = hx - dx * r * 0.35, by = hy - dy * r * 0.35;
      pxLine(c, bx - dy * r, by + dx * r, bx + dy * r, by - dx * r, '#e03c32', 2);
      const wv = Math.sin(t * 9 + w.id) * 2;
      pxLine(c, bx - dy * r, by + dx * r, bx - dy * r - dx * 6 + wv, by + dx * r - dy * 6, '#e03c32', 1);
      pxLine(c, bx - dy * r, by + dx * r, bx - dy * r - dx * 5 - wv, by + dx * r - dy * 5 + 2, '#9c2020', 1);
    }
    if (leader) c.drawImage(HW.crownSpr, hx - 4, hy - r - 11 + Math.round(Math.sin(t * 4)));
    c.globalAlpha = 1;
    if (w.shield > 0) ring(c, hx, hy, r + 6, '#aef', 12, t * 4, 2);
    if (w.stuck > 0) {
      c.fillStyle = '#b5c930'; c.fillRect(hx - 3, hy + r - 2, 2, 3); c.fillRect(hx + 2, hy + r - 3, 2, 4);
      if (!isMe) text(c, 'STUCK ' + Math.ceil(w.stuck), hx, hy - r - 20, '#d7e84a', { align: 0.5 });
    }
    if (w.slow > 0) ring(c, hx, hy, r + 4, '#5cc04a', 6, -t * 3, 2);
    if (w.boosting && Math.random() < 0.5) { const tl = p[n - 1]; fx.burst(tl.x, tl.y, ['#fff', '#ffd23f'], 1, 30, 0.3, 1); }
  }

  // power-up effects and speech bubbles, drawn over a worm
  const RAINBOW = ['#ff5a4d', '#ffd23f', '#b5e61d', '#4cc9f0', '#9b5de5', '#ff7eb6'];
  function drawWormFx(c, w, ox, oy, t) {
    const p = w.pts, n = p.length, hx = Math.round(w.x - ox), hy = Math.round(w.y - oy), r = w.r;
    if (w.rage > 0) {
      // rampage: rainbow sparks all down the body, a spinning halo on the head. Blinks before it ends.
      if (w.rage > 1.5 || ((t * 10) | 0) % 2) {
        const k = (t * 14) | 0;
        for (let i = 0; i < n; i += 3) { c.fillStyle = RAINBOW[(i + k) % 6]; c.fillRect(Math.round(p[i].x - ox) - 1 + ((i * 7 + k) % 5) - 2, Math.round(p[i].y - oy) - 1 + ((i * 3 + k) % 5) - 2, 2, 2); }
        ring(c, hx, hy, r + 5, RAINBOW[k % 6], 10, t * 7, 2); ring(c, hx, hy, r + 8, RAINBOW[(k + 3) % 6], 6, -t * 5, 2);
      }
      if (Math.random() < 0.5) fx.burst(w.x, w.y, RAINBOW, 1, 40, 0.35, 2);
    }
    if (w.guard > 0 && (w.guard > 2 || ((t * 8) | 0) % 2)) {
      // shot shield: a bubble on the head and a glint along the body
      ring(c, hx, hy, r + 6, '#4cc9f0', 16, t * 2, 2); ring(c, hx, hy, r + 6, '#ffffff', 4, -t * 3, 2);
      c.fillStyle = '#9be7ff'; for (let i = 5; i < n; i += 5) { const a = t * 3 + i; c.fillRect(Math.round(p[i].x - ox + Math.cos(a) * (r + 2)), Math.round(p[i].y - oy + Math.sin(a) * (r + 2)), 2, 2); }
    }
    if (w.chill > 0) {
      ring(c, hx, hy, r + 4, '#c9f2ff', 8, t * 1.5, 2);
      c.fillStyle = '#c9f2ff'; for (let i = 2; i < n; i += 4) c.fillRect(Math.round(p[i].x - ox) - 1, Math.round(p[i].y - oy) - 1, 2, 2);
    }
    if (w.sauce > 0 && w.boosting) { const tl = p[n - 1]; fx.burst(tl.x, tl.y, ['#fff1c9', '#ffd23f', '#f08a1c', '#e03c32'], 2, 50, 0.45, 3); }
    if (w.big > 0 && w.big < 2 && ((t * 8) | 0) % 2) ring(c, hx, hy, r + 3, '#ff5a4d', 10, t, 2);   // about to shrink
    const T = w._say;
    if (T && T.t > t) {
      // speech bubble
      const tw = HW.textW(T.s, 1), bx = Math.round(hx - tw / 2) - 3, by = hy - r - 26;
      c.fillStyle = '#1a1423'; c.fillRect(bx - 1, by - 1, tw + 8, 13); c.fillRect(hx - 2, by + 11, 5, 3);
      c.fillStyle = '#ffffff'; c.fillRect(bx, by, tw + 6, 11); c.fillRect(hx - 1, by + 11, 3, 2);
      text(c, T.s, bx + 3, by + 2, '#1a1423', { shadow: false });
    }
  }

  const FARTC = ['#7ed321', '#a8e04a', '#4f9a1e', '#c6f06a'];
  const PUKEC = ['#c9c13a', '#a3b02c', '#d8d05a'];
  function drawZone(c, z, ox, oy, t, top) {
    const x = Math.round(z.x - ox), y = Math.round(z.y - oy);
    const fade = z.t < 2 ? (((t * 10) | 0) % 2 ? 0.35 : 0.8) : 1; let s = z.id * 9301 + 49297;
    const rn = () => (s = (s * 233280 + 12345) % 2147483647) / 2147483647;
    if (z.k === 1 && !top) {
      c.globalAlpha = 0.9 * fade;
      for (let i = 0; i < 16; i++) { const a = rn() * 6.283, d = rn() * z.r * 0.62, rr = Math.round(z.r * (0.22 + rn() * 0.2)); const dsc = disc(PUKEC[i % 3], rr); c.drawImage(dsc, x + Math.round(Math.cos(a) * d) - rr, y + Math.round(Math.sin(a) * d) - rr); }
      for (let i = 0; i < 22; i++) { const a = rn() * 6.283, d = rn() * z.r * 0.8; c.fillStyle = ['#f08a1c', '#e03c32', '#fff1c9', '#8a4b25'][i % 4]; c.fillRect(x + Math.round(Math.cos(a) * d), y + Math.round(Math.sin(a) * d), 2 + (i % 2), 2); }
      c.globalAlpha = 1; ring(c, x, y, z.r, '#d8d05a', 28, t * 0.4, 2);
    } else if (z.k === 0 && top) {
      c.globalAlpha = 0.5 * fade;
      for (let i = 0; i < 15; i++) { const a = rn() * 6.283 + t * (0.2 + rn() * 0.3), d = rn() * z.r * 0.66, rr = Math.round(z.r * (0.2 + rn() * 0.16) + Math.sin(t * 2 + i) * 2); const dsc = disc(FARTC[i % 4], rr); c.drawImage(dsc, x + Math.round(Math.cos(a) * d) - rr, y + Math.round(Math.sin(a) * d) - rr); }
      c.globalAlpha = 1; ring(c, x, y, z.r, '#c6f06a', 28, -t * 0.5, 2);
      if (fade === 1) text(c, 'TOXIC', x, y - 3, '#eaffb0', { align: 0.5 });
    }
  }

  const GUMC = ['#ff7eb6', '#4cc9f0', '#ffd23f', '#b5e61d', '#ff9a3c'];

  // ---------- arena art: floor zones, graffiti, stains, obstacles (all drawn once into small canvases) ----------
  // colours per zone: [main, dark, light]. 0 kitchen, 1 candy shop, 2 salad bar, 3 grease pit, 4 food court
  const THEME = [['#8d99ae', '#5b667a', '#c9d2e0'], ['#ff7eb6', '#b84a86', '#ffc0dc'], ['#5cc04a', '#2f7d32', '#a8e88a'], ['#d9781f', '#8a4b25', '#f2b46a'], ['#e03c32', '#9c2020', '#ff9a8a']];
  const ZNAME = ['KITCHEN', 'CANDY SHOP', 'SALAD BAR', 'GREASE PIT', 'FOOD COURT'];
  const PAINT = ['#ffffff', '#ffd23f', '#ff7eb6', '#4cc9f0', '#b5e61d', '#ff9a3c', '#ff5a4d'];
  let decals = null;
  function paintText(str, scale, ang, col, alpha) {
    const w = HW.textW(str, scale), h = 7 * scale, ca = Math.abs(Math.cos(ang)), sa = Math.abs(Math.sin(ang));
    const cw = Math.ceil(w * ca + h * sa) + 4, ch = Math.ceil(w * sa + h * ca) + 4, c = HW.mk(cw, ch), x = c.getContext('2d');
    x.imageSmoothingEnabled = false; x.globalAlpha = alpha; x.translate(cw >> 1, ch >> 1); x.rotate(ang);
    text(x, str, -w / 2, -h / 2, col, { scale, shadow: false });
    return c;
  }
  function buildDecals() {
    // the same seed on every device, so everybody sees BEN SUCKS in the same place
    let a = 90210; const rnd = () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
    decals = [];
    const free = (x, y, w, h, pad) => {
      if (x < 40 || y < 40 || x + w > CFG.W - 40 || y + h > CFG.H - 40) return false;
      for (const o of MAP.obs) if (o.x1 > x - 6 && o.x0 < x + w + 6 && o.y1 > y - 6 && o.y0 < y + h + 6) return false;
      for (const d of decals) if (d.x + d.c.width > x - pad && d.x < x + w + pad && d.y + d.c.height > y - pad && d.y < y + h + pad) return false;
      return true;
    };
    const put = (c, box, tries, pad) => {
      for (let t = 0; t < tries; t++) {
        const x = Math.round(box.x + rnd() * Math.max(1, box.w - c.width)), y = Math.round(box.y + rnd() * Math.max(1, box.h - c.height));
        if (free(x, y, c.width, c.height, pad)) { decals.push({ c, x, y }); return true; }
      }
      return false;
    };
    const all = { x: 50, y: 50, w: CFG.W - 100, h: CFG.H - 100 };
    // the name of each corner, stencilled on its floor
    MAP.zones.forEach(z => { const c = paintText(ZNAME[z.zone], 6, 0, THEME[z.zone][2], 0.2); if (!put(c, { x: z.x + 16, y: z.y + 12, w: z.w - 32, h: 70 }, 30, 4)) put(c, z, 60, 4); });
    for (const g of MAP.GRAFFITI) {
      const c = paintText(g[0], g[2], rnd() < 0.3 ? 0 : (rnd() - 0.5) * 0.6, PAINT[(rnd() * PAINT.length) | 0], 0.2 + rnd() * 0.1);
      put(c, g[1] >= 0 ? MAP.zones[g[1]] : all, 80, 14);
    }
    // spills: ketchup, mustard, cola, relish, milkshake
    const SPILL = ['#e03c32', '#ffd23f', '#8a4b25', '#5cc04a', '#ff7eb6'];
    for (let i = 0; i < 42; i++) {
      const R = 16 + (rnd() * 20 | 0), c = HW.mk(R * 2 + 2, R * 2 + 2), x = c.getContext('2d'), col = SPILL[(rnd() * SPILL.length) | 0];
      x.globalAlpha = 0.2;
      const m = HW.mk(R * 2 + 2, R * 2 + 2), mx = m.getContext('2d');   // blobs are merged first so overlaps do not get darker
      for (let k = 0; k < 7; k++) { const an = rnd() * 6.283, d = rnd() * R * 0.55, rr = Math.max(2, Math.round(R * (0.18 + rnd() * 0.3))); mx.drawImage(disc(col, rr), Math.round(R + Math.cos(an) * d) - rr, Math.round(R + Math.sin(an) * d) - rr); }
      for (let k = 0; k < 6; k++) { const an = rnd() * 6.283, d = R * (0.7 + rnd() * 0.3); mx.fillStyle = col; mx.fillRect(Math.round(R + Math.cos(an) * d), Math.round(R + Math.sin(an) * d), 2, 2); }
      x.drawImage(m, 0, 0); put(c, all, 30, 6);
    }
  }
  // one obstacle as a sprite (its shadow included, down and to the right)
  const SH = 5;
  function obstacleSprite(o) {
    if (o.spr) return o.spr;
    const T = THEME[o.zone], K = '#1a1423', w = o.r ? o.r * 2 + 1 : o.w, h = o.r ? o.r * 2 + 1 : o.h, c = HW.mk(w + SH, h + SH + 2), x = c.getContext('2d');
    if (o.r) {
      const r = o.r;
      x.globalAlpha = 0.4; x.drawImage(disc('#000000', r), SH - 1, SH + 1); x.globalAlpha = 1;
      x.drawImage(disc(K, r), 0, 0);
      if (o.k === 'table') {
        // round table with a checked cloth and somebody's lunch
        x.drawImage(disc(T[0], r - 1), 1, 1);
        x.fillStyle = T[2]; for (let j = -r + 3; j <= r - 3; j++) for (let i = -r + 3; i <= r - 3; i++) if (i * i + j * j < (r - 3) * (r - 3) && (((i + 64) >> 3) + ((j + 64) >> 3)) & 1) x.fillRect(r + i, r + j, 1, 1);
        x.fillStyle = T[1]; for (let i = 0; i < 40; i++) { const an = i * 6.283 / 40; x.fillRect(Math.round(r + Math.cos(an) * (r - 2)), Math.round(r + Math.sin(an) * (r - 2)), 1, 1); }
        x.drawImage(disc(K, 8), r - 8, r - 8); x.drawImage(disc('#ffffff', 7), r - 7, r - 7); x.drawImage(disc('#dfe3ea', 5), r - 5, r - 5);
        const f = HW.foodSpr[(o.i * 5) % HW.foodSpr.length]; x.drawImage(f, r - (f.width >> 1), r - (f.height >> 1));
      } else {
        // giant soda can seen from above
        x.drawImage(disc('#c9d2e0', r - 1), 1, 1); x.drawImage(disc('#8d99ae', r - 3), 3, 3); x.drawImage(disc(T[0], r - 5), 5, 5);
        x.fillStyle = T[2]; x.fillRect(r - Math.round(r * 0.45), r - Math.round(r * 0.5), 3, 2); x.fillRect(r - Math.round(r * 0.55), r - Math.round(r * 0.35), 2, 2);
        x.fillStyle = K; x.fillRect(r - 4, r - 2, 9, 5); x.fillStyle = '#dfe3ea'; x.fillRect(r - 3, r - 1, 7, 3); x.fillStyle = K; x.fillRect(r + 1, r, 2, 1);
      }
    } else {
      x.fillStyle = 'rgba(0,0,0,0.4)'; x.fillRect(SH, SH + 2, w, h);
      x.fillStyle = K; x.fillRect(0, 0, w, h);
      if (o.k === 'crate') {
        x.fillStyle = '#b06a3a'; x.fillRect(1, 1, w - 2, h - 2); x.fillStyle = '#d9925a'; x.fillRect(1, 1, w - 2, 2);
        x.fillStyle = '#7a4420'; x.fillRect(1, h - 5, w - 2, 4); x.fillRect(5, 1, 2, h - 2); x.fillRect(w - 7, 1, 2, h - 2);
        pxLine(x, 7, 4, w - 9, h - 7, '#7a4420', 2); pxLine(x, w - 9, 4, 7, h - 7, '#7a4420', 2);
        x.fillStyle = K; x.fillRect(3, 3, 1, 1); x.fillRect(w - 4, 3, 1, 1); x.fillRect(3, h - 8, 1, 1); x.fillRect(w - 4, h - 8, 1, 1);
      } else if (o.k === 'vend') {
        // vending machine lying in the way: glass front full of cans
        x.fillStyle = T[0]; x.fillRect(1, 1, w - 2, h - 2); x.fillStyle = T[2]; x.fillRect(1, 1, w - 2, 2); x.fillStyle = T[1]; x.fillRect(1, h - 5, w - 2, 4);
        const wide = w >= h, gw = wide ? w - 20 : w - 10, gh = wide ? h - 12 : h - 22;
        x.fillStyle = K; x.fillRect(4, 5, gw + 2, gh + 2); x.fillStyle = '#2b3a55'; x.fillRect(5, 6, gw, gh);
        for (let j = 0; j + 5 <= gh; j += 7) for (let i = 0; i + 4 <= gw; i += 6) { x.fillStyle = GUMC[(i + j * 3 + o.i) % 5]; x.fillRect(6 + i, 7 + j, 4, 5); x.fillStyle = 'rgba(255,255,255,0.5)'; x.fillRect(6 + i, 7 + j, 1, 2); }
        x.fillStyle = K; if (wide) { x.fillRect(w - 11, 6, 7, 4); x.fillRect(w - 9, 14, 3, 6); } else { x.fillRect(5, h - 13, 7, 4); x.fillRect(w - 10, h - 13, 5, 3); }
        x.fillStyle = '#ffd23f'; if (wide) x.fillRect(w - 10, 7, 5, 2); else x.fillRect(6, h - 12, 5, 2);
      } else {
        // diner counter: coloured top, chrome edge, plates of food along it
        x.fillStyle = '#c9d2e0'; x.fillRect(1, 1, w - 2, h - 2); x.fillStyle = '#8d99ae'; x.fillRect(1, h - 5, w - 2, 4);
        x.fillStyle = T[0]; x.fillRect(3, 3, w - 6, h - 10); x.fillStyle = T[2]; x.fillRect(3, 3, w - 6, 2); x.fillStyle = T[1]; x.fillRect(3, h - 9, w - 6, 2);
        const wide = w >= h, len = wide ? w : h, n = Math.max(1, Math.floor(len / 46));
        for (let i = 0; i < n; i++) {
          const q = Math.round((i + 0.5) * len / n), px = wide ? q : w >> 1, py = wide ? (h >> 1) - 2 : q;
          if ((i + o.i) % 3 === 2) { x.fillStyle = K; x.fillRect(px - 6, py - 4, 12, 8); x.fillStyle = '#dfe3ea'; x.fillRect(px - 5, py - 3, 10, 6); x.fillStyle = '#8d99ae'; x.fillRect(px - 5, py, 10, 1); }   // napkin box
          else { x.drawImage(disc(K, 8), px - 8, py - 8); x.drawImage(disc('#ffffff', 7), px - 7, py - 7); const f = HW.foodSpr[(o.i * 3 + i * 7) % HW.foodSpr.length]; x.drawImage(f, px - (f.width >> 1), py - (f.height >> 1)); }
        }
      }
    }
    return o.spr = c;
  }
  // power-ups, special guns and the golden burger: big, glowing and labelled so nobody misses them
  let powerSpr2 = null, goldSpr2 = null, sgunSpr2 = null;
  function drawPickup(c, it, x, y, t) {
    if (!powerSpr2) { const tw = s => { const d = HW.mk(s.width * 2, s.height * 2), q = d.getContext('2d'); q.imageSmoothingEnabled = false; q.drawImage(s, 0, 0, d.width, d.height); return d; }; powerSpr2 = HW.powerSpr.map(tw); goldSpr2 = tw(HW.goldSpr); sgunSpr2 = HW.sgunSpr.map(g => tw(g.c)); }
    const bob = Math.round(Math.sin(t * 3 + it.id) * 2), k = (t * 6 + it.id) | 0;
    if (it.k === 'g') {
      const G = HW.SGUNS[it.type], g = sgunSpr2[it.type];
      c.globalAlpha = 0.6; c.drawImage(disc('#1a1423', 23), x - 23, y - 23); c.globalAlpha = 1;
      ring(c, x, y, 23, '#4cc9f0', 16, t * 2, 2); ring(c, x, y, 26 + Math.sin(t * 4 + it.id) * 2, '#ffffff', 5, -t * 2.5, 2);
      c.drawImage(g, x - (g.width >> 1), y - (g.height >> 1) + bob);
      text(c, G.name, x, y - 38, '#9be7ff', { align: 0.5 });
      return;
    }
    const gold = it.k === 'x', s = gold ? goldSpr2 : powerSpr2[it.type], col = gold ? '#ffd23f' : HW.POWERS[it.type].col;
    ring(c, x, y, 20, col, 12, t * 2.5, 2); ring(c, x, y, 24 + Math.sin(t * 5 + it.id) * 2, k % 2 ? '#ffffff' : col, 6, -t * 3, 2);
    c.drawImage(s, x - (s.width >> 1), y - (s.height >> 1) + bob);
    // the shine: a few white glints hopping around the sprite
    c.fillStyle = '#ffffff'; for (let i = 0; i < 3; i++) { const a = ((k + i * 5) * 2.4) % 6.283, d = 6 + ((k * 3 + i * 4) % 8); c.fillRect(x + Math.round(Math.cos(a) * d), y + bob + Math.round(Math.sin(a) * d), 2, 2); }
    text(c, gold ? 'GOLDEN BURGER' : HW.POWERS[it.type].name, x, y - 34, col, { align: 0.5 });
  }
  const mmCache = {};
  // minimap background: zones tinted, obstacles as pale blocks
  function mmBg(ms) {
    let c = mmCache[ms]; if (c) return c;
    c = mmCache[ms] = HW.mk(ms, ms); const x = c.getContext('2d'), k = ms / CFG.W;
    for (const z of MAP.zones) { x.globalAlpha = 0.16; x.fillStyle = THEME[z.zone][0]; x.fillRect(Math.round(z.x * k), Math.round(z.y * k), Math.round(z.w * k), Math.round(z.h * k)); }
    x.globalAlpha = 0.55; x.fillStyle = '#cfd3e6';
    for (const o of MAP.obs) x.fillRect(Math.floor(o.x0 * k), Math.floor(o.y0 * k), Math.max(1, Math.round((o.x1 - o.x0) * k)), Math.max(1, Math.round((o.y1 - o.y0) * k)));
    return c;
  }
  function drawBullet(c, b, ox, oy) {
    const x = Math.round(b.x - ox), y = Math.round(b.y - oy);
    switch (b.ch) {
      case 0: c.drawImage(HW.foodSpr[0], x - 6, y - 5); break;
      case 1: c.fillStyle = '#1a1423'; c.fillRect(x - 2, y - 2, 5, 5); c.fillStyle = '#9be7ff'; c.fillRect(x - 1, y - 1, 3, 3); c.fillStyle = '#fff'; c.fillRect(x - 1, y - 1, 1, 1); break;
      case 2: c.fillStyle = '#1a1423'; c.fillRect(x - 2, y - 3, 4, 6); c.fillRect(x - 3, y - 2, 6, 4); c.fillStyle = GUMC[b.c % 5]; c.fillRect(x - 2, y - 2, 4, 4); c.fillStyle = '#fff'; c.fillRect(x - 1, y - 1, 1, 1); break;
      case 3: c.save(); c.translate(x, y); c.rotate(Math.atan2(b.vy, b.vx)); c.drawImage(HW.skewerSpr, -9, -1); c.restore(); break;
      case 4: c.save(); c.translate(x, y); c.rotate(Math.atan2(b.vy, b.vx)); c.drawImage(HW.rocketSpr, -6, -2); c.restore();
        if (Math.random() < 0.7) fx.burst(b.x - b.vx * 0.02, b.y - b.vy * 0.02, ['#fff', '#bbb', '#f08a1c'], 1, 20, 0.45, 2); break;
      // ---- special guns ----
      case 5: c.save(); c.translate(x, y); c.rotate(Math.atan2(b.vy, b.vx)); c.drawImage(HW.raySpr, -6, -1); c.restore(); if (Math.random() < 0.5) fx.burst(b.x, b.y, ['#b5e61d', '#fff'], 1, 12, 0.25, 1); break;
      case 6: c.save(); c.translate(x, y); c.rotate(Math.atan2(b.vy, b.vx)); c.drawImage(HW.bigRocketSpr, -6, -2); c.restore();
        fx.burst(b.x - b.vx * 0.02, b.y - b.vy * 0.02, ['#fff', '#bbb', '#f08a1c', '#e03c32'], 1, 26, 0.5, 2); break;
      case 7: {
        // a puff of flame: starts small and white-hot, swells and reddens
        const a = b.age || 0, sz = Math.min(11, 3 + (a * 16 | 0)), h = sz >> 1;
        c.fillStyle = a < 0.12 ? '#fff1c9' : a < 0.28 ? '#ffd23f' : a < 0.45 ? '#f08a1c' : '#e03c32'; c.fillRect(x - h, y - h, sz, sz);
        if (sz > 5) { c.fillStyle = a < 0.28 ? '#ffffff' : a < 0.45 ? '#ffd23f' : '#f08a1c'; c.fillRect(x - h + 2, y - h + 2, sz - 4, sz - 4); }
        break;
      }
      case 8: c.fillStyle = '#1a1423'; c.fillRect(x - 2, y - 3, 4, 6); c.fillRect(x - 3, y - 2, 6, 4); c.fillStyle = b.c & 1 ? '#fff1c9' : '#ffffff'; c.fillRect(x - 2, y - 2, 4, 4); c.fillStyle = '#ffd23f'; c.fillRect(x, y, 2, 2); break;
      case 9: c.save(); c.translate(x, y); c.rotate(Math.atan2(b.vy, b.vx)); c.drawImage(HW.iceSpr, -5, -1); c.restore(); if (Math.random() < 0.5) fx.burst(b.x, b.y, ['#c9f2ff', '#fff'], 1, 14, 0.3, 1); break;
    }
  }

  // draw the world for one viewport v = {x,y,w,h, cam:{x,y}, trip, slow}
  R.drawView = function (v, G, t) {
    if (vc.width !== v.w || vc.height !== v.h) { vc.width = v.w; vc.height = v.h; vx.imageSmoothingEnabled = false; pattern = null; zonePat = null; }
    const M = Math.round(Math.min(v.w, v.h) * 0.2), ccx = v.w >= CFG.W + 2 * M ? CFG.W / 2 : Math.max(v.w / 2 - M, Math.min(CFG.W - v.w / 2 + M, v.cam.x)), ccy = v.h >= CFG.H + 2 * M ? CFG.H / 2 : Math.max(v.h / 2 - M, Math.min(CFG.H - v.h / 2 + M, v.cam.y));
    const c = vx, ox = Math.round(ccx - v.w / 2), oy = Math.round(ccy - v.h / 2);
    v.px = v.cam.x - ox; v.py = v.cam.y - oy;
    if (!pattern) pattern = c.createPattern(HW.floorTile, 'repeat');
    if (!zonePat) zonePat = HW.zoneTiles.map(t => c.createPattern(t, 'repeat'));
    if (!decals) buildDecals();
    c.fillStyle = '#120e1c'; c.fillRect(0, 0, v.w, v.h);
    const fx0 = Math.max(0, -ox), fy0 = Math.max(0, -oy), fx1 = Math.min(v.w, CFG.W - ox), fy1 = Math.min(v.h, CFG.H - oy);
    if (fx1 > fx0 && fy1 > fy0) {
      // floor: the diner checker everywhere, a themed floor in each corner and in the middle. Drawn in world
      // coordinates so the patterns stay glued to the ground.
      c.save(); c.translate(-ox, -oy); c.fillStyle = pattern; c.fillRect(fx0 + ox, fy0 + oy, fx1 - fx0, fy1 - fy0);
      for (const z of MAP.zones) {
        const x0 = Math.max(z.x, ox), y0 = Math.max(z.y, oy), x1 = Math.min(z.x + z.w, ox + v.w), y1 = Math.min(z.y + z.h, oy + v.h); if (x1 <= x0 || y1 <= y0) continue;
        c.fillStyle = zonePat[z.zone]; c.fillRect(x0, y0, x1 - x0, y1 - y0);
        c.globalAlpha = 0.45; c.fillStyle = THEME[z.zone][1]; c.fillRect(z.x, z.y, z.w, 2); c.fillRect(z.x, z.y + z.h - 2, z.w, 2); c.fillRect(z.x, z.y, 2, z.h); c.fillRect(z.x + z.w - 2, z.y, 2, z.h); c.globalAlpha = 1;
      }
      c.restore();
      for (const d of decals) { const x = d.x - ox, y = d.y - oy; if (x < v.w && y < v.h && x + d.c.width > 0 && y + d.c.height > 0) c.drawImage(d.c, x, y); }
      // wall
      c.fillStyle = '#e03c32';
      if (ox < 0) c.fillRect(-ox - 4, fy0 - 4, 4, fy1 - fy0 + 8); if (oy < 0) c.fillRect(fx0 - 4, -oy - 4, fx1 - fx0 + 8, 4);
      if (CFG.W - ox < v.w) c.fillRect(CFG.W - ox, fy0 - 4, 4, fy1 - fy0 + 8); if (CFG.H - oy < v.h) c.fillRect(fx0 - 4, CFG.H - oy, fx1 - fx0 + 8, 4);
    }
    for (const z of G.zones) if (z.k === 1 && z.x - ox > -z.r - 4 && z.x - ox < v.w + z.r + 4 && z.y - oy > -z.r - 4 && z.y - oy < v.h + z.r + 4) drawZone(c, z, ox, oy, t, false);
    // items
    for (const it of G.items.values()) {
      const x = it.x - ox, y = it.y - oy; if (x < -26 || y < -26 || x > v.w + 26 || y > v.h + 26) continue;
      let s;
      if (it.k === 'f') s = it.v >= CFG.BIG ? HW.foodSpr2[it.type] : HW.foodSpr[it.type];   // proper food is double size, crumbs are small
      else if (it.k === 'a') { s = HW.ammoSpr; if (((t * 3 + it.id) | 0) % 2) ring(c, Math.round(x), Math.round(y), 10, '#ffd23f', 8, t * 2, 1); }
      else if (it.k === 'p' || it.k === 'g' || it.k === 'x') { drawPickup(c, it, Math.round(x), Math.round(y), t); continue; }
      else if (it.k === 'v') { s = HW.vegSpr2[it.type]; ring(c, Math.round(x), Math.round(y), 18, '#5cc04a', 8, -t * 0.8 + it.id, 2); }
      else { s = HW.shroomSpr2[it.type]; ring(c, Math.round(x), Math.round(y), 18 + Math.sin(t * 3 + it.id) * 3, ['#ff7eb6', '#4cc9f0', '#ffd23f'][((t * 4 + it.id) | 0) % 3], 7, t * 1.5 + it.id, 2); }
      const bob = it.k === 'f' ? 0 : Math.round(Math.sin(t * 3 + it.id) * 1.2);
      c.drawImage(s, Math.round(x - s.width / 2), Math.round(y - s.height / 2) + bob);
    }
    // obstacles
    for (const o of MAP.obs) {
      if (o.x1 - ox < -8 || o.x0 - ox > v.w + 2 || o.y1 - oy < -10 || o.y0 - oy > v.h + 2) continue;
      c.drawImage(obstacleSprite(o), Math.round(o.x0 - ox), Math.round(o.y0 - oy));
    }
    // worms (biggest first so little ones stay visible)
    let leader = null; for (const w of G.worms) if (w.alive && (!leader || w.mass > leader.mass)) leader = w;
    for (const w of G.worms) {
      if (!w.alive || w.bx1 === undefined) continue;
      if (w.bx1 - ox < -30 || w.bx0 - ox > v.w + 30 || w.by1 - oy < -30 || w.by0 - oy > v.h + 30) continue;
      drawWorm(c, w, ox, oy, t, w === leader && w.mass > 60, w.id === v.meId);
      if (w.rage > 0 || w.guard > 0 || w.chill > 0 || w.sauce > 0 || w.big > 0 || w._say) drawWormFx(c, w, ox, oy, t);
      // tags: an arrow over your own worm, P-numbers over other humans
      const tx = Math.round(w.x - ox), ty = Math.round(w.y - oy) - w.r - (w === leader && w.mass > 60 ? 20 : 12);
      if (w.id === v.meId) { const b = Math.round(Math.sin(t * 6)); c.fillStyle = '#1a1423'; c.fillRect(tx - 4, ty - 5 + b, 9, 3); c.fillRect(tx - 2, ty - 2 + b, 5, 2); c.fillRect(tx - 1, ty + b, 3, 2); c.fillStyle = '#fff'; c.fillRect(tx - 3, ty - 4 + b, 7, 1); c.fillRect(tx - 2, ty - 3 + b, 5, 1); c.fillRect(tx - 1, ty - 2 + b, 3, 1); c.fillRect(tx, ty - 1 + b, 1, 1); }
      else if (w.pid >= 0) text(c, 'P' + (w.pid + 1), tx, ty - 6, '#9be7ff', { align: 0.5 });
    }
    for (const b of G.bullets) { const x = b.x - ox, y = b.y - oy; if (x > -20 && y > -20 && x < v.w + 20 && y < v.h + 20) drawBullet(c, b, ox, oy); }
    for (const z of G.zones) if (z.k === 0 && z.x - ox > -z.r - 4 && z.x - ox < v.w + z.r + 4 && z.y - oy > -z.r - 4 && z.y - oy < v.h + z.r + 4) drawZone(c, z, ox, oy, t, true);
    for (const p of fx.parts) { const x = p.x - ox, y = p.y - oy; if (x < 0 || y < 0 || x > v.w || y > v.h) continue; c.fillStyle = p.c; c.fillRect(x | 0, y | 0, p.s, p.s); }
    for (const p of fx.texts) text(c, p.s, p.x - ox, p.y - oy, p.c, { align: 0.5 });

    // ---- composite to the main canvas with screen effects ----
    const m = cx;
    m.save(); m.beginPath(); m.rect(v.x, v.y, v.w, v.h); m.clip();
    if (v.trip > 0) {
      const k = Math.min(1, v.trip / 1.5), amp = 7 * k;
      m.globalAlpha = 0.3 * k; m.fillStyle = '#120e1c'; m.fillRect(v.x, v.y, v.w, v.h); // stops the additive passes burning in at the edges
      m.globalAlpha = 1 - 0.45 * k; // leaves trails of the previous frame = fuzzy
      for (let y = 0; y < v.h; y += 3) {
        const o = Math.sin(y * 0.045 + t * 3.1) * amp + Math.sin(y * 0.11 - t * 4.3) * amp * 0.4;
        m.drawImage(vc, 0, y, v.w, 3, v.x + Math.round(o), v.y + y + Math.round(Math.cos(y * 0.03 + t * 2) * amp * 0.35), v.w, 3);
      }
      m.globalAlpha = 0.16 * k; m.globalCompositeOperation = 'lighter';
      m.drawImage(vc, v.x + Math.round(Math.sin(t * 2.3) * 9), v.y + Math.round(Math.cos(t * 1.7) * 6));
      m.fillStyle = 'hsl(' + ((t * 90) % 360 | 0) + ',90%,50%)'; m.globalAlpha = 0.1 * k; m.fillRect(v.x, v.y, v.w, v.h);
      m.globalCompositeOperation = 'source-over'; m.globalAlpha = 1;
    } else m.drawImage(vc, v.x, v.y);
    if (v.slow > 0) {
      const k = Math.min(1, v.slow / 0.6);
      m.fillStyle = 'rgba(40,190,50,' + (0.2 * k).toFixed(3) + ')'; m.fillRect(v.x, v.y, v.w, v.h);
      m.fillStyle = 'rgba(20,120,30,' + (0.3 * k).toFixed(3) + ')'; m.fillRect(v.x, v.y, v.w, 6); m.fillRect(v.x, v.y + v.h - 6, v.w, 6); m.fillRect(v.x, v.y, 6, v.h); m.fillRect(v.x + v.w - 6, v.y, 6, v.h);
    }
    m.restore();
  };

  function panel(c, x, y, w, h, a) { c.fillStyle = 'rgba(16,12,28,' + (a || 0.6) + ')'; c.fillRect(x, y, w, h); }

  // HUD for one viewport. o = {me, player, G, t, touch, roomCode, keysHint, slotLabel}
  R.drawHUD = function (v, o) {
    const c = cx, G = o.G, me = o.me, t = o.t; c.save(); c.beginPath(); c.rect(v.x, v.y, v.w, v.h); c.clip();
    const small = v.w < 420;
    const sa = (HW.Input && HW.Input.touch.layout && HW.Input.touch.layout.safe) || { l: 0, r: 0, t: 0, b: 0 }; // notch / home-indicator insets, canvas px
    // minimap
    const ms = small ? 50 : 60, mx = v.x + 5 + (v.x <= 0 ? sa.l : 0), my = v.y + 5;
    panel(c, mx - 1, my - 1, ms + 2, ms + 2, 0.9); c.fillStyle = 'rgba(255,255,255,0.06)'; c.fillRect(mx, my, ms, ms); c.drawImage(mmBg(ms), mx, my);
    for (const z of G.zones) { c.fillStyle = z.k === 0 ? '#7ed321' : '#c9c13a'; c.fillRect(mx + (z.x / CFG.W * ms | 0) - 1, my + (z.y / CFG.H * ms | 0) - 1, 3, 3); }
    // pickups blink on the minimap so everybody knows where the fight will be
    if (((t * 3) | 0) % 2) for (const it of G.items.values()) {
      if (it.k !== 'p' && it.k !== 'g' && it.k !== 'x') continue;
      c.fillStyle = it.k === 'g' ? '#4cc9f0' : it.k === 'x' ? '#ffd23f' : HW.POWERS[it.type].col; c.fillRect(mx + (it.x / CFG.W * ms | 0) - 1, my + (it.y / CFG.H * ms | 0) - 1, 3, 3);
      c.fillStyle = '#ffffff'; c.fillRect(mx + (it.x / CFG.W * ms | 0), my + (it.y / CFG.H * ms | 0), 1, 1);
    }
    let leader = null;
    for (const w of G.worms) {
      if (!w.alive) continue; if (!leader || w.mass > leader.mass) leader = w; if (w === me) continue;
      c.fillStyle = CHARS[w.ch].colors[w.variant % 4][0]; const s = w.pid >= 0 ? 3 : 2;
      c.fillRect(mx + (w.x / CFG.W * ms | 0) - 1, my + (w.y / CFG.H * ms | 0) - 1, s, s);
      if (w.pid >= 0) { c.fillStyle = '#fff'; c.fillRect(mx + (w.x / CFG.W * ms | 0), my + (w.y / CFG.H * ms | 0), 1, 1); }
    }
    if (leader && leader !== me && leader.mass > 60) { c.fillStyle = '#ffd23f'; c.fillRect(mx + (leader.x / CFG.W * ms | 0) - 1, my + (leader.y / CFG.H * ms | 0) - 3, 3, 1); }
    if (me && me.alive && ((t * 4) | 0) % 2) { c.fillStyle = '#fff'; c.fillRect(mx + (me.x / CFG.W * ms | 0) - 1, my + (me.y / CFG.H * ms | 0) - 1, 3, 3); }
    // leaderboard
    // match leaderboard: 1st, 2nd, 3rd by score, plus your own row
    const comps = G.comps || [], ranked = comps.slice().sort((a, b) => b.score - a.score || b.kills - a.kills), mine = o.player ? comps.find(q => q.pid === o.player.pid) : null;
    const top = ranked.slice(0, small ? 3 : 4);
    if (mine && top.indexOf(mine) < 0 && top.length) top[top.length - 1] = mine; else if (!small && top.length > 3 && top.indexOf(mine) < 3) top.length = 3;
    const lw = 92, lx = v.x + v.w - lw - 4 - (v.x + v.w >= R.W ? sa.r : 0); panel(c, lx, v.y + 4, lw, top.length * 9 + 3, 0.55);
    top.forEach((q, i) => {
      const col = q === mine ? '#ffd23f' : q.pid >= 0 ? '#9be7ff' : '#ddd', y = v.y + 6 + i * 9;
      text(c, ranked.indexOf(q) + 1, lx + 3, y, col, { shadow: false });
      c.fillStyle = '#1a1423'; c.fillRect(lx + 14, y, 5, 7); c.fillStyle = CHARS[q.ch].colors[q.variant % 4][0]; c.fillRect(lx + 15, y + 1, 3, 5);
      text(c, q === mine ? 'YOU' : q.pid >= 0 ? 'P' + (q.pid + 1) + ' ' + CHARS[q.ch].name.slice(0, 4) : CHARS[q.ch].name, lx + 22, y, col, { shadow: false });
      text(c, q.score, lx + lw - 3, y, col, { align: 1, shadow: false });
    });
    // match clock
    const M = G.match, tcx = v.x + v.w / 2;
    if (M && !o.demo) { const s = Math.max(0, Math.ceil(M.t)), low = s <= 30; text(c, ((s / 60) | 0) + ':' + ('0' + (s % 60)).slice(-2), tcx, v.y + 4, low ? (((t * 2) | 0) % 2 ? '#ff5a4d' : '#fff') : '#fff', { align: 0.5, scale: small ? 1 : 2 }); }
    const topY = v.y + (small ? 13 : 21);
    if (o.roomCode) text(c, 'ROOM ' + o.roomCode, tcx, topY, '#9be7ff', { align: 0.5 });
    if (o.slotLabel) text(c, o.slotLabel, mx + ms + 5, v.y + 5, '#ffd23f');
    // lives + kills under the minimap
    if (mine) {
      for (let i = 0; i < CFG.LIVES; i++) {
        const hx = mx + i * 9, hy = my + ms + 4; c.fillStyle = '#1a1423'; c.fillRect(hx, hy, 8, 7);
        c.fillStyle = i < mine.lives ? '#ff4d5e' : '#4a4460'; c.fillRect(hx + 1, hy + 1, 2, 3); c.fillRect(hx + 5, hy + 1, 2, 3); c.fillRect(hx + 1, hy + 2, 6, 2); c.fillRect(hx + 2, hy + 4, 4, 1); c.fillRect(hx + 3, hy + 5, 2, 1);
      }
      text(c, 'KILLS ' + mine.kills, mx, my + ms + 14, '#fff');
    }
    // banner: streak callouts, power-up names, the last-minute frenzy
    if (v.banner && v.banner.t > 0) { const B = v.banner, big = !small && B.s.length < 22; text(c, B.s, tcx + (B.t > 1.6 ? Math.sin(t * 40) * 2 : 0), v.y + Math.round(v.h * 0.27), ((t * 8) | 0) % 2 ? B.c : '#ffffff', { align: 0.5, scale: big ? 2 : 1 }); }
    // kill feed
    HW.fx.feed.slice(-3).forEach((f, i) => text(c, f.s, tcx, (small ? v.y + ms + 26 : topY + (o.roomCode ? 10 : 0)) + i * 9, f.c, { align: 0.5 }));

    if (me && me.alive) {
      const C = CHARS[me.ch], g = C.gun, SG = me.sg ? HW.SGUNS[me.sg - 1] : null;
      // bottom centre: mass, ammo, ability meter
      const bx = v.x + v.w / 2, by = v.y + v.h - 12 - sa.b;
      text(c, 'MASS ' + Math.round(me.mass), bx - 8, by, '#fff', { align: 1 });
      if (SG) text(c, SG.name.split(' ').slice(-2).join(' ') + ' ' + Math.ceil(me.sgT), bx + 8, by, me.sgT < 3 && ((t * 6) | 0) % 2 ? '#fff' : '#4cc9f0');
      else text(c, 'AMMO ' + me.ammo, bx + 8, by, me.ammo === 0 ? (((t * 4) | 0) % 2 ? '#e03c32' : '#fff') : me.ammo <= g.max * 0.2 ? '#ffb0a8' : '#ffd23f');
      // running power-ups: a bar each, stacked above the ability meter
      let py = by - 34;
      for (let i = 0; i < HW.POWERS.length; i++) {
        const P = HW.POWERS[i], left = [me.rage, me.big, me.guard, me.sauce][i]; if (!(left > 0)) continue;
        const bw = 60, x0 = Math.round(bx - bw / 2); panel(c, x0 - 1, py - 1, bw + 2, 6, 0.8);
        c.fillStyle = left < 2 && ((t * 8) | 0) % 2 ? '#fff' : P.col; c.fillRect(x0, py, Math.round(bw * Math.min(1, left / P.t)), 4);
        text(c, P.name, x0 - 4, py - 2, P.col, { align: 1 }); py -= 10;
      }
      if (me.ammo === 0 && !SG) text(c, 'NO AMMO! GRAB A CRATE', bx, py - 2, '#ff8a80', { align: 0.5 });
      if (me.chill > 0) text(c, 'FROZEN!', bx, v.y + v.h / 2 - 58, '#c9f2ff', { align: 0.5 });
      if (C.ability) {
        const bw = 80, x0 = Math.round(bx - bw / 2), y0 = by - 12, f = 1 - Math.max(0, me.abil) / CFG.ABIL_CD;
        panel(c, x0 - 1, y0 - 1, bw + 2, 8, 0.8);
        c.fillStyle = f >= 1 ? (((t * 3) | 0) % 2 ? '#b5e61d' : '#7ed321') : '#5a6b8a'; c.fillRect(x0, y0, Math.round(bw * f), 6);
        text(c, f >= 1 ? C.ability + ' READY' + (o.abilKey ? ' ' + o.abilKey : '') : C.ability + ' ' + Math.ceil(me.abil), bx, y0 - 9, f >= 1 ? '#d9ff7a' : '#aab', { align: 0.5 });
      } else text(c, 'NO ABILITY', bx, by - 11, '#778', { align: 0.5 });
      if (me.shield > 0) text(c, 'SHIELD', bx, v.y + v.h / 2 - 34, '#aef', { align: 0.5 });
      if (me.stuck > 0) text(c, 'STUCK IN PUKE! ' + Math.ceil(me.stuck), bx, v.y + v.h / 2 - 46, '#d7e84a', { align: 0.5, scale: small ? 1 : 2 });
      if (v.slow > 0) text(c, 'EW, VEGGIES!', bx, v.y + 28, '#9cf08a', { align: 0.5 });
      if (v.trip > 0) text(c, 'WHOOOAAA', bx + Math.sin(t * 3) * 8, v.y + 38 + Math.cos(t * 4) * 3, 'hsl(' + ((t * 200) % 360 | 0) + ',90%,70%)', { align: 0.5 });
    } else if (o.player) {
      // death card
      const p = o.player, cxm = v.x + v.w / 2, cy = v.y + v.h / 2;
      panel(c, v.x, cy - 44, v.w, 88, 0.72);
      if (p.everSpawned) {
        const cause = { fart: 'GASSED BY ', puke: 'DROWNED IN PUKE BY ', shot: 'SHOT BY ', crash: 'CRASHED INTO ', bonk: 'HEAD-BUTTED BY ', rampage: 'RUN OVER BY ', left: '' }[p.lastCause] || '';
        text(c, 'YOU DIED', cxm, cy - 36, '#ff5a4d', { align: 0.5, scale: 2 });
        if (p.lastKiller) text(c, cause + p.lastKiller, cxm, cy - 14, '#fff', { align: 0.5 });
        text(c, 'SCORE ' + (p.lastScore || 0) + '   BEST ' + Math.round(p.best || 0), cxm, cy - 2, '#ffd23f', { align: 0.5 });
      } else text(c, 'GET READY', cxm, cy - 30, '#ffd23f', { align: 0.5, scale: 2 });
      if (mine && mine.out) {
        text(c, 'OUT OF LIVES', cxm, cy + 12, '#ff8a80', { align: 0.5 });
        text(c, 'WATCHING THE REST OF THE MATCH', cxm, cy + 24, '#889', { align: 0.5 });
      } else {
        const left = Math.max(0, 3 - p.deadT);
        if (mine && p.everSpawned) text(c, mine.lives === 1 ? 'LAST LIFE!' : mine.lives + ' LIVES LEFT', cxm, cy + 10, mine.lives === 1 ? '#ff8a80' : '#fff', { align: 0.5 });
        text(c, left > 0 ? 'RESPAWN IN ' + Math.ceil(left) : 'RESPAWNING', cxm, cy + 21, '#9be7ff', { align: 0.5 });
        text(c, o.touch ? 'TAP TO HURRY' : 'FIRE TO HURRY', cxm, cy + 32, '#889', { align: 0.5 });
      }
    }
    c.restore();
  };

  // touch controls overlay of one touch pad (HW.Input.tpads[i]): the whole screen in solo, one half each in split screen
  // C: the player's character (so the ability button shows while they are dead too)
  R.drawTouch = function (T, me, t, C) {
    const c = cx, L = T.layout; if (!L) return;
    const stick = (s, col, idleX, idleY) => {
      const x = s.on ? s.ox : idleX, y = s.on ? s.oy : idleY;
      c.globalAlpha = s.on ? 0.5 : 0.16; ring(c, x, y, L.ring || 26, col, 20, 0, 2);
      c.globalAlpha = s.on ? 0.75 : 0.2; const k = disc(col, 9); c.drawImage(k, Math.round(x + (s.on ? s.dx * (L.ring || 26) : 0)) - 9, Math.round(y + (s.on ? s.dy * (L.ring || 26) : 0)) - 9);
      c.globalAlpha = 1;
    };
    stick(T.move, '#ffffff', L.moveIdle.x, L.moveIdle.y); stick(T.aim, '#ff7b6b', L.aimIdle.x, L.aimIdle.y);
    if (!T.move.on) text(c, 'MOVE', L.moveIdle.x, L.moveIdle.y + (L.ring || 26) + 6, 'rgba(255,255,255,0.35)', { align: 0.5, shadow: false });
    if (!T.aim.on) text(c, 'AIM+SHOOT', L.aimIdle.x, L.aimIdle.y + (L.ring || 26) + 6, 'rgba(255,255,255,0.35)', { align: 0.5, shadow: false });
    // boost
    let b = L.boost; c.globalAlpha = T.boost ? 0.85 : 0.4; c.drawImage(disc('#ffd23f', b.r), b.x - b.r, b.y - b.r); c.drawImage(disc('#1a1423', b.r - 2), b.x - b.r + 2, b.y - b.r + 2);
    c.globalAlpha = 1; text(c, 'BOOST', b.x, b.y - 3, T.boost ? '#fff' : '#ffd23f', { align: 0.5, shadow: false });
    // ability
    const A = (C || (me ? CHARS[me.ch] : {})).ability, live = me && me.alive;
    if (A) {
      b = L.abil; const f = live ? 1 - Math.max(0, me.abil) / CFG.ABIL_CD : 0, ready = f >= 1, col = A === 'fart' ? '#7ed321' : '#c9c13a';
      c.globalAlpha = ready ? 0.9 : 0.45; c.drawImage(disc(T.abilHeld || (ready && ((t * 3) | 0) % 2) ? '#fff' : col, b.r), b.x - b.r, b.y - b.r); c.drawImage(disc('#1a1423', b.r - 2), b.x - b.r + 2, b.y - b.r + 2);
      // fill from the bottom as it recharges
      const d = disc(col, b.r - 3), hh = Math.round(d.height * f); c.globalAlpha = ready ? 0.9 : 0.5;
      if (hh > 0) c.drawImage(d, 0, d.height - hh, d.width, hh, b.x - b.r + 3, b.y - b.r + 3 + d.height - hh, d.width, hh);
      c.globalAlpha = 1; text(c, A, b.x, b.y - (live ? 7 : 3), live ? '#fff' : '#99a', { align: 0.5 });
      if (live) text(c, ready ? 'GO!' : Math.ceil(me.abil), b.x, b.y + 3, ready ? '#fff' : '#ccd', { align: 0.5 });
    }
    b = L.pause; if (!b) return;   // only P1's half carries the pause button
    const g = Math.min((b.w >> 1) - 9, Math.max(3, (b.h - 8) >> 1)), bx = b.x + (b.w >> 1);   // bars no further apart than they are tall (the split-screen button can be flat)
    panel(c, b.x, b.y, b.w, b.h, 0.5); c.fillStyle = '#ccd'; c.fillRect(bx - g - 3, b.y + 4, 3, b.h - 8); c.fillRect(bx + g, b.y + 4, 3, b.h - 8);
  };

  R.clear = function () { cx.fillStyle = '#120e1c'; cx.fillRect(0, 0, R.W, R.H); };
  R.divider = function (x) { cx.fillStyle = '#1a1423'; cx.fillRect(x - 1, 0, 3, R.H); cx.fillStyle = '#ffd23f'; cx.fillRect(x, 0, 1, R.H); };
  R.drawWormPreview = function (c, w, t) { drawWorm(c, w, 0, 0, t, false); };
})(window.HW);
