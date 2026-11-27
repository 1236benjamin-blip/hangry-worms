// Hangry Worms - rendering (low-res pixel canvas, scaled up by CSS)
'use strict';
(function (HW) {
  const CFG = HW.CFG, CHARS = HW.CHARS, text = HW.text;
  const R = HW.Render = { W: 640, H: 360, scale: 2, target: 270 };
  R.setTarget = function (t) { if (R.target !== t) { R.target = t; R.resize(); if (HW.Input) HW.Input.layout(); } };
  let cv, cx, vc, vx, pattern;

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
    const g = HW.gunSpr[w.ch];
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
  function drawBullet(c, b, ox, oy) {
    const x = Math.round(b.x - ox), y = Math.round(b.y - oy);
    switch (b.ch) {
      case 0: c.drawImage(HW.foodSpr[0], x - 6, y - 5); break;
      case 1: c.fillStyle = '#1a1423'; c.fillRect(x - 2, y - 2, 5, 5); c.fillStyle = '#9be7ff'; c.fillRect(x - 1, y - 1, 3, 3); c.fillStyle = '#fff'; c.fillRect(x - 1, y - 1, 1, 1); break;
      case 2: c.fillStyle = '#1a1423'; c.fillRect(x - 2, y - 3, 4, 6); c.fillRect(x - 3, y - 2, 6, 4); c.fillStyle = GUMC[b.c % 5]; c.fillRect(x - 2, y - 2, 4, 4); c.fillStyle = '#fff'; c.fillRect(x - 1, y - 1, 1, 1); break;
      case 3: c.save(); c.translate(x, y); c.rotate(Math.atan2(b.vy, b.vx)); c.drawImage(HW.skewerSpr, -9, -1); c.restore(); break;
      default: c.save(); c.translate(x, y); c.rotate(Math.atan2(b.vy, b.vx)); c.drawImage(HW.rocketSpr, -6, -2); c.restore();
        if (Math.random() < 0.7) fx.burst(b.x - b.vx * 0.02, b.y - b.vy * 0.02, ['#fff', '#bbb', '#f08a1c'], 1, 20, 0.45, 2);
    }
  }

  // draw the world for one viewport v = {x,y,w,h, cam:{x,y}, trip, slow}
  R.drawView = function (v, G, t) {
    if (vc.width !== v.w || vc.height !== v.h) { vc.width = v.w; vc.height = v.h; vx.imageSmoothingEnabled = false; pattern = null; }
    const M = Math.round(Math.min(v.w, v.h) * 0.2), ccx = v.w >= CFG.W + 2 * M ? CFG.W / 2 : Math.max(v.w / 2 - M, Math.min(CFG.W - v.w / 2 + M, v.cam.x)), ccy = v.h >= CFG.H + 2 * M ? CFG.H / 2 : Math.max(v.h / 2 - M, Math.min(CFG.H - v.h / 2 + M, v.cam.y));
    const c = vx, ox = Math.round(ccx - v.w / 2), oy = Math.round(ccy - v.h / 2);
    v.px = v.cam.x - ox; v.py = v.cam.y - oy;
    if (!pattern) pattern = c.createPattern(HW.floorTile, 'repeat');
    c.fillStyle = '#120e1c'; c.fillRect(0, 0, v.w, v.h);
    const fx0 = Math.max(0, -ox), fy0 = Math.max(0, -oy), fx1 = Math.min(v.w, CFG.W - ox), fy1 = Math.min(v.h, CFG.H - oy);
    if (fx1 > fx0 && fy1 > fy0) {
      c.save(); c.translate(-(((ox % 64) + 64) % 64), -(((oy % 64) + 64) % 64)); c.fillStyle = pattern;
      c.fillRect(fx0 + (((ox % 64) + 64) % 64), fy0 + (((oy % 64) + 64) % 64), fx1 - fx0, fy1 - fy0); c.restore();
      // wall
      c.fillStyle = '#e03c32';
      if (ox < 0) c.fillRect(-ox - 4, fy0 - 4, 4, fy1 - fy0 + 8); if (oy < 0) c.fillRect(fx0 - 4, -oy - 4, fx1 - fx0 + 8, 4);
      if (CFG.W - ox < v.w) c.fillRect(CFG.W - ox, fy0 - 4, 4, fy1 - fy0 + 8); if (CFG.H - oy < v.h) c.fillRect(fx0 - 4, CFG.H - oy, fx1 - fx0 + 8, 4);
    }
    for (const z of G.zones) if (z.k === 1 && z.x - ox > -z.r - 4 && z.x - ox < v.w + z.r + 4 && z.y - oy > -z.r - 4 && z.y - oy < v.h + z.r + 4) drawZone(c, z, ox, oy, t, false);
    // items
    for (const it of G.items.values()) {
      const x = it.x - ox, y = it.y - oy; if (x < -14 || y < -14 || x > v.w + 14 || y > v.h + 14) continue;
      let s;
      if (it.k === 'f') s = HW.foodSpr[it.type];
      else if (it.k === 'a') { s = HW.ammoSpr; if (((t * 3 + it.id) | 0) % 2) ring(c, Math.round(x), Math.round(y), 10, '#ffd23f', 8, t * 2, 1); }
      else if (it.k === 'v') s = HW.vegSpr[it.type];
      else { s = HW.shroomSpr[it.type]; ring(c, Math.round(x), Math.round(y), 9 + Math.sin(t * 3 + it.id) * 2, ['#ff7eb6', '#4cc9f0', '#ffd23f'][((t * 4 + it.id) | 0) % 3], 5, t * 1.5 + it.id, 1); }
      const bob = it.k === 'f' ? 0 : Math.round(Math.sin(t * 3 + it.id) * 1.2);
      c.drawImage(s, Math.round(x - s.width / 2), Math.round(y - s.height / 2) + bob);
    }
    // worms (biggest first so little ones stay visible)
    let leader = null; for (const w of G.worms) if (w.alive && (!leader || w.mass > leader.mass)) leader = w;
    for (const w of G.worms) {
      if (!w.alive || w.bx1 === undefined) continue;
      if (w.bx1 - ox < -30 || w.bx0 - ox > v.w + 30 || w.by1 - oy < -30 || w.by0 - oy > v.h + 30) continue;
      drawWorm(c, w, ox, oy, t, w === leader && w.mass > 60, w.id === v.meId);
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
    panel(c, mx - 1, my - 1, ms + 2, ms + 2, 0.9); c.fillStyle = 'rgba(255,255,255,0.06)'; c.fillRect(mx, my, ms, ms);
    for (const z of G.zones) { c.fillStyle = z.k === 0 ? '#7ed321' : '#c9c13a'; c.fillRect(mx + (z.x / CFG.W * ms | 0) - 1, my + (z.y / CFG.H * ms | 0) - 1, 3, 3); }
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
    // kill feed
    HW.fx.feed.slice(-3).forEach((f, i) => text(c, f.s, tcx, (small ? v.y + ms + 26 : topY + (o.roomCode ? 10 : 0)) + i * 9, f.c, { align: 0.5 }));

    if (me && me.alive) {
      const C = CHARS[me.ch], g = C.gun;
      // bottom centre: mass, ammo, ability meter
      const bx = v.x + v.w / 2, by = v.y + v.h - 12 - sa.b;
      text(c, 'MASS ' + Math.round(me.mass), bx - 8, by, '#fff', { align: 1 });
      text(c, 'AMMO ' + me.ammo, bx + 8, by, me.ammo === 0 ? (((t * 4) | 0) % 2 ? '#e03c32' : '#fff') : me.ammo <= g.max * 0.2 ? '#ffb0a8' : '#ffd23f');
      if (me.ammo === 0) text(c, 'NO AMMO! GRAB A CRATE', bx, by - 34, '#ff8a80', { align: 0.5 });
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
        const cause = { fart: 'GASSED BY ', puke: 'DROWNED IN PUKE BY ', shot: 'SHOT BY ', crash: 'CRASHED INTO ', bonk: 'HEAD-BUTTED BY ', left: '' }[p.lastCause] || '';
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

  // touch controls overlay (full screen)
  R.drawTouch = function (T, me, t) {
    const c = cx, L = T.layout;
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
    if (me && CHARS[me.ch].ability) {
      b = L.abil; const f = me.alive ? 1 - Math.max(0, me.abil) / CFG.ABIL_CD : 0, ready = f >= 1, col = CHARS[me.ch].ability === 'fart' ? '#7ed321' : '#c9c13a';
      c.globalAlpha = ready ? 0.9 : 0.45; c.drawImage(disc(T.abilHeld || (ready && ((t * 3) | 0) % 2) ? '#fff' : col, b.r), b.x - b.r, b.y - b.r); c.drawImage(disc('#1a1423', b.r - 2), b.x - b.r + 2, b.y - b.r + 2);
      // fill from the bottom as it recharges
      const d = disc(col, b.r - 3), hh = Math.round(d.height * f); c.globalAlpha = ready ? 0.9 : 0.5;
      if (hh > 0) c.drawImage(d, 0, d.height - hh, d.width, hh, b.x - b.r + 3, b.y - b.r + 3 + d.height - hh, d.width, hh);
      c.globalAlpha = 1; text(c, CHARS[me.ch].ability, b.x, b.y - 7, '#fff', { align: 0.5 });
      text(c, ready ? 'GO!' : Math.ceil(me.abil), b.x, b.y + 3, ready ? '#fff' : '#ccd', { align: 0.5 });
    }
    b = L.pause; panel(c, b.x, b.y, b.w, b.h, 0.5); c.fillStyle = '#ccd'; c.fillRect(b.x + 6, b.y + 4, 3, b.h - 8); c.fillRect(b.x + b.w - 9, b.y + 4, 3, b.h - 8);
  };

  R.clear = function () { cx.fillStyle = '#120e1c'; cx.fillRect(0, 0, R.W, R.H); };
  R.divider = function (x) { cx.fillStyle = '#1a1423'; cx.fillRect(x - 1, 0, 3, R.H); cx.fillStyle = '#ffd23f'; cx.fillRect(x, 0, 1, R.H); };
  R.drawWormPreview = function (c, w, t) { drawWorm(c, w, 0, 0, t, false); };
})(window.HW);
