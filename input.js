// Hangry Worms - input: keyboard, mouse, touch twin-stick, gamepads
'use strict';
(function (HW) {
  const mkStick = dz => ({ on: false, id: -1, ox: 0, oy: 0, dx: 0, dy: 0, t0: 0, aimed: false, lx: 0, ly: 0, edge: false, dz });
  const MOVE_DZ = 0.05, AIM_DZ = 0.1;   // squared stick deflection (1 = full) below which a stick is neutral
  const AIM_GRACE = 120;                // ms a thumb may sit still on the aim side before auto-aim fire starts
  // One full touch control set. Solo uses pad 0 over the whole screen. In split screen every player has a
  // pad inside their own half, so two people can share one phone (each holds an end, or it lies on a table).
  const mkPad = i => ({ i, move: mkStick(MOVE_DZ), aim: mkStick(AIM_DZ), boost: false, boostId: -1, abil: false, abilHeld: false, pause: false, tap: false, shot: false, taunt: false, layout: null });
  const In = HW.Input = {
    keys: {}, mouse: { x: 0, y: 0, down: false, rdown: false, clicked: false, active: false },
    tpads: [mkPad(0), mkPad(1)],   // pad 1 only has a layout while two local players are on screen
    touch: null,          // = tpads[0]. Also carries what belongs to the device, not to a player: used (the screen has been touched), last (when)
    lastKind: 'kb',       // what solo / P1 used last: 'kb' | 'pad' | 'touch'. P2 never changes it (P2 has dev.kind).
    pausePressed: false, enabled: false,
    safe: null            // optional override of the safe-area insets, CSS px: { l, r, t, b }
  };
  const PADS = In.tpads, T = In.touch = PADS[0], now = () => performance.now();
  T.used = false; T.last = 0;

  // ---------- touch layout ----------
  // Sizes are chosen in CSS px (what a thumb sees) and converted to canvas px, because one canvas px is
  // anything from 1 CSS px (split screen) to 1.7 (big phones) to 3 (tablets).
  let probe = null;
  function insets() {
    if (In.safe) return In.safe;
    try {
      if (!probe) {
        probe = document.createElement('div');
        probe.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;visibility:hidden;pointer-events:none;padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) env(safe-area-inset-bottom,0px) env(safe-area-inset-left,0px)';
        document.body.appendChild(probe);
      }
      const s = getComputedStyle(probe), f = v => parseFloat(v) || 0;
      return { t: f(s.paddingTop), r: f(s.paddingRight), b: f(s.paddingBottom), l: f(s.paddingLeft) };
    } catch (e) { return { t: 0, r: 0, b: 0, l: 0 }; }
  }
  // Layout of one pad inside its view: canvas columns vx .. vx + vw, full height. two = split screen.
  // A split-screen half is only 333 to 466 CSS px wide, so everything in it is a little smaller and closer.
  function padLayout(P, vx, vw, two, ins) {
    const Rn = HW.Render, W = Rn.W, H = Rn.H, sc = Rn.scale || 1, c = v => Math.round(v / sc), x1 = vx + vw, mid = vx + vw / 2, old = P.layout;
    // The notch and the rounded corners only matter on a screen edge this view really touches, not on the divider.
    const iL = vx <= 0 ? ins.l : 0, iR = x1 >= W ? ins.r : 0;
    // what render.js draws along the top of a view: minimap (left), clock (middle), leaderboard (right)
    const small = vw < 420, lbBottom = 4 + (small ? 3 : 5) * 9 + 3, mmRight = 5 + (small ? 50 : 60) + 1;
    // 19 canvas px is the smallest disc the labels fit in. Split screen: 52 and 56 CSS px buttons, still above the 48 px guideline.
    const rA = Math.max(19, c(two ? 26 : 28)), rB = Math.max(19, c(two ? 28 : 30)), stickR = Math.max(14, c(two ? 42 : 46)), ring = Math.round(stickR * 0.76);
    // A contact within 16 px of the glass edge is taken for a gripping hand, not a thumb (see toStick).
    const edge = c(16), hitB = c(8);
    // Screen edge: clear of the notch and the edge-swipe strip, and the boost hit zone stops where the palm strip
    // starts (a hand wrapped round an edge-to-edge screen must not boost). Divider: nobody grips there, 10 px
    // keeps the hit zones on their own side of it.
    const edgeR = x1 >= W ? Math.max(c(Math.max(iR + 8, 20)), edge + hitB) : c(10);
    // ability: tucked under the leaderboard, a long reach from the aiming thumb, small hit margin
    const abil = { x: x1 - edgeR - rA, y: lbBottom + c(8) + rA, r: rA, hit: rA + c(3) };
    // boost: straight above the resting aim thumb, never closer to the ability than a 12 px dead gap
    const boost = { x: x1 - edgeR - rB, y: 0, r: rB, hit: rB + hitB };
    boost.y = Math.min(Math.max(abil.y + abil.hit + boost.hit + c(12), H - c(180)), H - c(ins.b + 8) - rB);
    // pause: top edge, right of the minimap (and of the P1 label in split screen), clear of the kill feed.
    // One button pauses the whole game, so only P1's half carries it.
    let pause = null;
    if (!P.i) {
      pause = { x: 0, y: 3 + c(ins.t), w: Math.max(22, c(two ? 36 : 40)), h: Math.max(14, c(30)), pad: 0, padY: 0 };
      // A wide half (420 canvas px and up) has the kill feed right under its clock, where solo has empty floor:
      // the drawn button stays above that line. The hit zone below does not shrink with it.
      if (two && !small) pause.h = Math.max(12, Math.min(pause.h, 19 - pause.y));
      pause.padY = Math.max(c(7), Math.ceil(44 / sc) - pause.y - pause.h);   // from the top edge down, the hit zone is at least 44 CSS px tall
      pause.pad = two ? Math.max(c(5), Math.ceil((44 / sc - pause.w) / 2)) : pause.padY;   // sideways a half has less room: 46 CSS px wide
      pause.x = vx + c(iL) + mmRight + (two ? 20 : 0) + pause.pad + 2;
      // A notch inset can push it into the clock in a narrow half: then it goes to the other side of the clock.
      const ck = small ? 13 : 24, bx = Math.ceil(mid + ck) + 2 + pause.pad;
      if (two && pause.x + pause.w + 2 > mid - ck && bx + pause.w + pause.pad <= x1 - 96 - c(iR)) pause.x = bx;
    }
    // Where the thumbs are expected to rest (the sticks float: they start wherever a thumb lands on its half).
    let mx = vx + c(two ? Math.max(88, iL + 68) : Math.max(124, iL + 104)), ax = x1 - c(two ? Math.max(100, iR + 80) : Math.max(139, iR + 112));
    if (two) { mx = Math.min(mx, Math.floor(mid) - ring - 2); ax = Math.max(ax, Math.ceil(mid) + ring + 2); }   // drawn inside their own half of the view
    // taunt: a small button under the lives and kill count, out of the way of both thumbs (44 CSS px, like the pause hit zone)
    const rT = Math.max(11, Math.ceil(22 / sc)), taunt = { x: vx + c(iL) + 5 + rT, y: 5 + (small ? 50 : 60) + 22 + c(6) + rT, r: rT, hit: rT + c(2) };
    P.layout = {
      x0: vx, x1, mid, moveIdle: { x: mx, y: H - c(100) }, aimIdle: { x: ax, y: H - c(100) },
      boost, abil, pause, taunt, stickR, ring, scale: sc,
      edge, edgeB: c(Math.max(16, ins.b)),   // palm strips: sides, and bottom (that one also covers the home indicator)
      safe: { l: c(ins.l), r: c(ins.r), t: c(ins.t), b: c(ins.b) }   // insets in canvas px, for the HUD
    };
    // the canvas was re-scaled under a held thumb (rotation, fullscreen): keep its stick where the thumb is
    if (old && old.scale && old.scale !== sc) for (const s of [P.move, P.aim]) { s.ox *= old.scale / sc; s.oy *= old.scale / sc; }
  }
  // Views are split exactly as layoutViews() in main.js splits them.
  In.layout = function () {
    const W = HW.Render.W, ins = insets(), n = HW.App && HW.App.locals ? HW.App.locals.length : 1;
    if (n > 1) { const hw = Math.floor(W / 2); padLayout(PADS[0], 0, hw, true, ins); padLayout(PADS[1], W - hw, hw, true, ins); }
    else { padLayout(PADS[0], 0, W, false, ins); if (PADS[1].layout) { releasePad(PADS[1]); PADS[1].layout = null; } }
  };
  function pt(t) { const r = HW.Render.canvas.getBoundingClientRect(); return { x: (t.clientX - r.left) / r.width * HW.Render.W, y: (t.clientY - r.top) / r.height * HW.Render.H }; }
  const inC = (p, b, extra) => (p.x - b.x) ** 2 + (p.y - b.y) ** 2 < (b.hit + (extra || 0)) ** 2;
  const inPause = (p, b) => p.x >= b.x - b.pad && p.x <= b.x + b.w + b.pad && p.y <= b.y + b.h + b.padY;
  In.insets = insets;
  const hasAbil = P => { const l = HW.App && HW.App.locals && HW.App.locals[P.i], C = l && HW.CHARS[l.ch]; return !C || !!C.ability; };

  // ---------- touch ----------
  // Every finger on the canvas has exactly one job, remembered by its identifier, and one pad: the one whose
  // half it came down in. It keeps both until it lifts, so a thumb that slides over the divider never
  // drives the other player's worm.
  const owners = new Map();   // identifier -> { pad, role: 'move'|'aim'|'spare'|'boost'|'abil'|'pause', side, sx, sy }
  const padAt = p => PADS[1].layout && p.x >= PADS[1].layout.x0 ? PADS[1] : PADS[0];
  const stickOf = (P, side) => side ? P.aim : P.move, sideOf = (P, p) => p.x < P.layout.mid ? 0 : 1;
  const resting = s => s.dx * s.dx + s.dy * s.dy < s.dz;
  const hasRole = (P, r) => { for (const o of owners.values()) if (o.pad === P && o.role === r) return true; return false; };
  const findTouch = (list, id) => { if (list) for (let i = 0; i < list.length; i++) if (list[i].identifier === id) return list[i]; return null; };

  // a finger asks for the floating stick on its half of its pad
  function toStick(P, id, p, side) {
    const s = stickOf(P, side), L = P.layout, edge = p.x < L.edge || p.x > HW.Render.W - L.edge || p.y > HW.Render.H - L.edgeB;
    // The half is already held. A holder that is doing nothing, or that sits on the very edge of the glass
    // (a gripping palm), gives the stick to the new finger; a working thumb keeps it.
    if (s.on && !(resting(s) || (s.edge && !edge))) { owners.set(id, { pad: P, role: 'spare', side }); return; }
    if (s.on) owners.set(s.id, { pad: P, role: 'spare', side });
    if (!s.on || s.edge || !s.aimed) { s.t0 = now(); s.aimed = false; }   // a fresh gesture (not a hand-over between two working fingers)
    s.on = true; s.id = id; s.ox = p.x; s.oy = p.y; s.dx = s.dy = 0; s.edge = edge;
    owners.set(id, { pad: P, role: side ? 'aim' : 'move', side });
  }
  // a finger is gone. fire = it was lifted normally during play (not cancelled, not lost)
  function drop(id, e, fire) {
    const o = owners.get(id); if (!o) return; owners.delete(id); const P = o.pad;
    if (o.role === 'move' || o.role === 'aim') {
      const s = stickOf(P, o.side); if (s.id !== id) return;
      for (const [k, v] of owners) {            // another finger already resting on this half takes over
        const t = v.pad === P && v.role === 'spare' && v.side === o.side && e ? findTouch(e.touches, k) : null;
        if (t) { const p = pt(t); s.id = k; s.ox = p.x; s.oy = p.y; s.dx = s.dy = 0; s.edge = false; v.role = o.role; return; }
      }
      if (o.role === 'aim' && fire && !s.aimed && !s.edge && now() - s.t0 < AIM_GRACE) P.shot = true;   // quick tap = one auto-aimed shot
      s.on = false; s.id = -1; s.dx = s.dy = 0; s.aimed = false;
    } else if (o.role === 'boost') P.boost = hasRole(P, 'boost');
    else if (o.role === 'abil') { P.abilHeld = hasRole(P, 'abil'); if (fire) P.abil = true; }   // the ability goes off on release, still on the button
  }
  // Self-heal: a finger we still track that the browser no longer lists was lifted without a touchend
  // (system gesture, rotation, notification...). Without this a stick would stay stuck until the next pause.
  function sync(e) { if (e.touches) for (const id of Array.from(owners.keys())) if (!findTouch(e.touches, id)) drop(id, e, false); }

  function tstart(e) {
    if (!In.enabled) return; if (e.cancelable) e.preventDefault();
    T.used = true; if (!T.layout) return;
    sync(e);
    for (const t of e.changedTouches) {
      const id = t.identifier, p = pt(t), P = padAt(p), L = P.layout; drop(id, e, false); P.tap = true;
      if (!P.i) { In.lastKind = 'touch'; In.mouse.active = false; }   // P2's thumbs say nothing about what P1 is playing with
      if (L.pause && inPause(p, L.pause)) { P.pause = true; owners.set(id, { pad: P, role: 'pause' }); }
      else if (hasAbil(P) && inC(p, L.abil)) { owners.set(id, { pad: P, role: 'abil', side: sideOf(P, p), sx: p.x, sy: p.y }); P.abilHeld = true; }
      else if (inC(p, L.boost)) { owners.set(id, { pad: P, role: 'boost' }); P.boost = true; P.boostId = id; }
      else if (inC(p, L.taunt)) { owners.set(id, { pad: P, role: 'taunt' }); P.taunt = true; }
      else toStick(P, id, p, sideOf(P, p));
    }
  }
  function tmove(e) {
    if (!In.enabled) return; if (e.cancelable) e.preventDefault();
    if (!T.layout) return;
    for (const t of e.changedTouches) {
      const id = t.identifier, p = pt(t); let o = owners.get(id);
      if (!o) { const P = padAt(p); toStick(P, id, p, sideOf(P, p)); continue; }   // a finger that stayed down through a pause: pick it up again
      const P = o.pad, L = P.layout; if (!L) continue;
      if (o.role === 'abil' && !inC(p, L.abil, L.edge)) {  // slid off the ability button: it was an aim gesture, not a press
        owners.delete(id); P.abilHeld = hasRole(P, 'abil'); toStick(P, id, { x: o.sx, y: o.sy }, o.side); o = owners.get(id);
      }
      if (o.role !== 'move' && o.role !== 'aim') continue;
      const s = stickOf(P, o.side); if (s.id !== id) continue;
      let dx = p.x - s.ox, dy = p.y - s.oy; const d = Math.sqrt(dx * dx + dy * dy), SR = L.stickR;
      if (d > SR) { s.ox += dx * (d - SR) / d; s.oy += dy * (d - SR) / d; dx = p.x - s.ox; dy = p.y - s.oy; } // stick follows the thumb
      s.dx = dx / SR; s.dy = dy / SR;
      if (o.role === 'aim' && !resting(s)) { const m = Math.sqrt(s.dx * s.dx + s.dy * s.dy); s.lx = s.dx / m; s.ly = s.dy / m; s.aimed = true; }
    }
  }
  // Releases are handled even while a menu is up: the finger that opened the pause menu lifts after it appears.
  function tend(e) {
    if (e.cancelable) e.preventDefault();
    const fire = e.type === 'touchend' && In.enabled;
    for (const t of e.changedTouches) drop(t.identifier, e, fire);
    sync(e);
  }
  function releasePad(P) {
    for (const [k, v] of owners) if (v.pad === P) owners.delete(k);
    for (const s of [P.move, P.aim]) { s.on = false; s.id = -1; s.dx = s.dy = 0; s.aimed = false; }
    P.boost = P.abilHeld = false; P.boostId = -1;
  }
  function releaseTouch() { PADS.forEach(releasePad); }
  // called when a game starts and on pause / resume: drop everything transient, on every device
  let anchor = null;
  In.resetTouch = function () {
    releaseTouch(); for (const P of PADS) P.abil = P.pause = P.tap = P.shot = P.taunt = false;
    for (const k in hit) delete hit[k];
    In.mouse.clicked = false; In.mouse.active = false; anchor = null;   // mouse aim comes back when the mouse is really used (see mousemove)
    seats.clear();
  };

  // ---------- keyboard + mouse ----------
  const hit = {};   // keys that went down since the last read, so a tap shorter than one frame still counts
  function clearKeys() { In.keys = {}; for (const k in hit) delete hit[k]; }
  In.init = function (canvas) {
    canvas.addEventListener('touchstart', tstart, { passive: false }); canvas.addEventListener('touchmove', tmove, { passive: false });
    canvas.addEventListener('touchend', tend, { passive: false }); canvas.addEventListener('touchcancel', tend, { passive: false });
    // Any touch anywhere (menu buttons too) is followed by made-up mouse events; remember when it happened.
    // P2's thumbs on their own half are the exception: those touches are preventDefault-ed, so nothing made up
    // follows them, and P1 may be aiming with a real mouse at the same moment (touch-screen laptop).
    const p2only = e => {
      if (!In.enabled || e.target !== canvas || !e.cancelable || !PADS[1].layout || !e.changedTouches || !e.changedTouches.length) return false;
      for (const t of e.changedTouches) { const o = owners.get(t.identifier); if ((o ? o.pad : padAt(pt(t))) !== PADS[1]) return false; }
      return true;
    };
    const touched = e => { if (!p2only(e)) T.last = now(); };
    ['touchstart', 'touchmove', 'touchend', 'touchcancel'].forEach(n => window.addEventListener(n, touched, { capture: true, passive: true }));
    document.addEventListener('gesturestart', e => e.preventDefault());   // iOS pinch-zoom in menus

    window.addEventListener('keydown', e => {
      if (e.target && e.target.tagName === 'INPUT') return;
      if (e.metaKey || e.key === 'Meta') { clearKeys(); return; }   // macOS sends no keyup for keys let go while Cmd is down
      if (!e.repeat) { hit[e.code] = true; if (e.code === 'Escape' || e.code === 'KeyP') In.pausePressed = true; }   // a held Esc must not flicker the pause menu
      In.keys[e.code] = true;
      if (In.enabled && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space', 'Slash', 'Tab'].indexOf(e.code) >= 0) e.preventDefault();
    });
    window.addEventListener('keyup', e => { if (e.key === 'Meta') clearKeys(); else In.keys[e.code] = false; });
    const allUp = () => { clearKeys(); In.mouse.down = In.mouse.rdown = In.mouse.clicked = false; releaseTouch(); };
    window.addEventListener('blur', allUp); window.addEventListener('pagehide', allUp);
    document.addEventListener('visibilitychange', () => { if (document.hidden) allUp(); });

    const real = e => now() - T.last > 1000 && !(e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents);
    window.addEventListener('mousemove', e => {
      if (!real(e)) return; const M = In.mouse, p = pt(e); M.x = p.x; M.y = p.y;
      if (!(e.buttons & 1)) M.down = false; if (!(e.buttons & 2)) M.rdown = false;   // a mouseup we never saw
      // The cursor only aims once it has travelled during play. Parked where it clicked PLAY it must not
      // aim the gun, or keyboard-only players never get aim assist.
      if (!In.enabled || !anchor) anchor = { x: e.clientX, y: e.clientY };
      else if (!M.active && (e.clientX - anchor.x) ** 2 + (e.clientY - anchor.y) ** 2 > 400) { M.active = true; In.lastKind = 'kb'; }
    });
    canvas.addEventListener('mousedown', e => {
      if (!real(e)) return; const M = In.mouse, p = pt(e); M.x = p.x; M.y = p.y; M.active = true; In.lastKind = 'kb';
      if (e.button === 0) { M.down = true; M.clicked = true; } else if (e.button === 2) M.rdown = true;
    });
    window.addEventListener('mouseup', e => { if (e.button === 0) In.mouse.down = false; else if (e.button === 2) In.mouse.rdown = false; });
    canvas.addEventListener('contextmenu', e => e.preventDefault());

    // a controller that was being played dies mid-game: pause rather than leave the worm driving blind
    window.addEventListener('gamepaddisconnected', e => {
      const i = e.gamepad ? e.gamepad.index : -1, s = padSt.get(i); padSt.delete(i); seats.delete(i);
      if (s && s.used && In.enabled) In.pausePressed = true;
    });
  };

  // ---------- gamepads ----------
  In.pads = function () {
    const out = []; let l; try { l = navigator.getGamepads ? navigator.getGamepads() : []; } catch (e) { l = []; }
    for (let i = 0; l && i < l.length; i++) { const g = l[i]; if (g && g.connected !== false && g.buttons && g.buttons.length >= 4 && g.axes) out.push(g); }
    return out;
  };
  const bp = (g, i) => !!(g.buttons[i] && (g.buttons[i].pressed || g.buttons[i].value > 0.4));
  const num = v => typeof v === 'number' && v === v ? v : 0;
  const padSt = new Map();   // gamepad.index -> { id, la, ra, ha, used }
  function pst(g) { let s = padSt.get(g.index); if (!s || s.id !== g.id) { s = { id: g.id, la: false, ra: false, ha: false, used: false }; padSt.set(g.index, s); } return s; }
  const HATX = [0, 1, 1, 1, 0, -1, -1, -1], HATY = [-1, -1, 0, 1, 1, 1, 0, -1];
  // sticks + d-pad of one pad as { x, y, rx, ry }
  function padAxes(g) {
    const s = pst(g), a = g.axes; let x = num(a[0]), y = num(a[1]), rx = num(a[2]), ry = num(a[3]);
    // A stick is only believed after it has been seen at rest. On pads without the standard mapping
    // "axis 2" can be a trigger that idles at -1: that would aim left and fire forever.
    if (x * x + y * y < 0.09) s.la = true; if (rx * rx + ry * ry < 0.09) s.ra = true;
    if (!s.la || x * x + y * y < 0.0625) x = y = 0;   // round dead zone: no snapping to the 8 compass directions
    if (!s.ra) rx = ry = 0;
    if (g.mapping === 'standard') { if (bp(g, 14)) x = -1; if (bp(g, 15)) x = 1; if (bp(g, 12)) y = -1; if (bp(g, 13)) y = 1; }
    else if (a.length > 9) {   // unmapped pads in Chrome report the d-pad as a hat on axis 9: 8 steps from -1 to 1, about 1.29 when idle
      const h = num(a[9]), k = Math.round((h + 1) * 3.5);
      if (h > 1.1) s.ha = true; else if (s.ha && k >= 0 && k <= 7 && Math.abs((h + 1) * 3.5 - k) < 0.1) { x = HATX[k]; y = HATY[k]; }
    }
    return { x, y, rx, ry };
  }
  // Split screen: a player keeps the physical pad they started with. dev.pad (set by main.js every frame)
  // only says whether this player may take a free one. So when one of two pads dies, the other pad stays
  // with its player instead of jumping to the other worm.
  const seats = new Map();   // gamepad.index -> { dev, t }
  function seat(dev, all) {
    const pv = dev.prev, t = now(); let g = null;
    if (pv.pad >= 0) g = all.find(p => p.index === pv.pad) || null;
    if (!g && dev.pad >= 0) g = all.find(p => { const s = seats.get(p.index); return !s || s.dev === dev || t - s.t > 1000; }) || null;
    pv.pad = g ? g.index : -1; if (g) seats.set(g.index, { dev, t });
    return g;
  }

  // dev = { touch, tpad: 0 | 1 (which touch pad, default 0), kb: 'wasd'|'arrows'|'both'|null, mouse, pad: n | 'any' | -1, prev:{} }
  // view = viewport of this player (for mouse aim). Returns one input frame.
  // Also writes dev.kind ('kb'|'pad'|'touch', what this player used last) and dev.hasPad.
  In.read = function (dev, view) {
    const K = In.keys, o = { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false, tap: false, pause: false, taunt: false };
    let tauntDown = false;
    const pv = dev.prev || (dev.prev = {});
    const kd = c => { const h = hit[c]; if (h) hit[c] = false; return !!(K[c] || h); };
    const any = function () { let r = false; for (let i = 0; i < arguments.length; i++) if (kd(arguments[i])) r = true; return r; };   // no short-circuit: every latch is consumed
    let abilDown = false, pauseDown = false, tapDown = false, kind = null, mAim = false;
    if (dev.kb) {
      const wasd = dev.kb !== 'arrows', arr = dev.kb !== 'wasd';
      let x = 0, y = 0, f = false, b = false;
      if (wasd) { if (kd('KeyA')) x--; if (kd('KeyD')) x++; if (kd('KeyW')) y--; if (kd('KeyS')) y++; f = kd('Space'); b = kd('ShiftLeft'); abilDown = any('KeyE', 'KeyQ', 'KeyF'); tauntDown = kd('KeyT'); }
      if (arr) {
        if (kd('ArrowLeft')) x--; if (kd('ArrowRight')) x++; if (kd('ArrowUp')) y--; if (kd('ArrowDown')) y++;
        f = any('Enter', 'Slash', 'Numpad0', 'NumpadEnter') || f; b = kd('ShiftRight') || b; abilDown = any('Period', 'Comma', 'NumpadDecimal') || abilDown; tauntDown = any('Quote', 'Backslash', 'NumpadAdd') || tauntDown;
      }
      if (x || y) { o.mx = x; o.my = y; }
      if (f) { o.fire = true; o.auto = true; tapDown = true; }
      if (b) o.boost = true;
      if (x || y || f || b || abilDown) kind = 'kb';
    }
    if (dev.mouse && view) {
      const M = In.mouse, click = M.clicked; M.clicked = false;
      if (M.active) {
        const dx = M.x - (view.x + (view.px === undefined ? view.w / 2 : view.px)), dy = M.y - (view.y + (view.py === undefined ? view.h / 2 : view.py)), d = Math.sqrt(dx * dx + dy * dy);
        if (d > 6) { o.ax = dx / d; o.ay = dy / d; o.auto = false; mAim = true; }
      }
      if (M.down || click) { o.fire = true; tapDown = true; kind = 'kb'; }   // click latch: a trackpad tap is down+up inside one frame
      if (M.rdown) { o.boost = true; kind = 'kb'; }
    }
    dev.hasPad = false;
    if ((dev.pad !== -1 && dev.pad !== undefined) || pv.pad >= 0) {
      const all = In.pads(); let list = all;
      if (dev.pad !== 'any') { const g = seat(dev, all); list = g ? [g] : []; }
      dev.hasPad = list.length > 0;
      for (const g of list) {
        const a = padAxes(g), aim = a.rx * a.rx + a.ry * a.ry > 0.16, trig = bp(g, 7) || bp(g, 5); let act = false;
        // shooting with the pad: a cursor left lying on the screen stops aiming (it would beat the trigger's aim assist)
        if ((aim || trig) && dev.mouse && In.mouse.active) { In.mouse.active = false; anchor = null; if (mAim) { o.ax = o.ay = 0; mAim = false; } }
        if (a.x || a.y) { o.mx = a.x; o.my = a.y; act = true; }
        if (aim) { o.ax = a.rx; o.ay = a.ry; o.fire = true; o.auto = false; act = true; }
        if (trig) { o.fire = true; if (!aim) o.auto = true; tapDown = true; act = true; }
        if (bp(g, 6) || bp(g, 0)) { o.boost = true; if (bp(g, 0)) tapDown = true; act = true; }
        if (bp(g, 2) || bp(g, 4) || bp(g, 3)) { abilDown = true; act = true; }
        if (bp(g, 9)) { pauseDown = true; act = true; }
        if (bp(g, 1) || bp(g, 8)) { tauntDown = true; act = true; }   // B / Back: taunt
        if (act) { kind = 'pad'; pst(g).used = true; }
      }
    }
    const P = PADS[dev.tpad || 0];   // this player's touch pad (see In.layout)
    if (dev.touch && T.used && P.layout) {
      const m = P.move, a = P.aim;
      if (m.on && !resting(m)) { o.mx = m.dx; o.my = m.dy; }
      if (a.on) {
        // Dragged: shoot where the thumb points, and keep that direction while it passes back through the middle.
        // Never dragged: wait a moment (the first shot of a drag must not fly off somewhere else), then auto-aim.
        if (a.aimed) { o.ax = a.lx; o.ay = a.ly; o.auto = false; o.fire = true; }
        // A still contact on the very edge of the glass is a gripping hand, not a thumb: it never fires.
        else if (!a.edge && now() - a.t0 >= AIM_GRACE) { o.ax = o.ay = 0; o.auto = true; o.fire = true; }
      }
      if (P.shot) { P.shot = false; if (!o.fire) { o.ax = o.ay = 0; o.auto = true; o.fire = true; } }
      if (P.boost) o.boost = true;
      if (P.abil) { o.abil = true; P.abil = false; }
      if (P.pause) { o.pause = true; P.pause = false; }
      if (P.taunt) { o.taunt = true; P.taunt = false; }
      if (P.tap) { o.tap = true; P.tap = false; }
      if (m.on || a.on || P.boost || o.abil || o.tap) kind = 'touch';
    }
    if (abilDown && !pv.abil) o.abil = true; pv.abil = abilDown;
    if (pauseDown && !pv.pause) o.pause = true; pv.pause = pauseDown;
    if (tauntDown && !pv.taunt) o.taunt = true; pv.taunt = tauntDown;
    if (tapDown && !pv.tap) o.tap = true; pv.tap = tapDown;
    if (kind) { dev.kind = kind; if (dev.touch && !dev.tpad) In.lastKind = kind; }   // the control hints of solo / P1 follow P1 only
    return o;
  };

  // menu navigation edges from all pads
  let mPrev = {};
  In.menu = function () {
    const o = { dir: 0, a: false, b: false }; const cur = {};
    for (const g of In.pads()) {
      const a = padAxes(g);
      if (a.y < -0.6 || a.x < -0.6) cur.prev = true;
      if (a.y > 0.6 || a.x > 0.6) cur.next = true;
      if (bp(g, 0) || bp(g, 9)) cur.a = true; if (bp(g, 1)) cur.b = true;
    }
    if (cur.prev && !mPrev.prev) o.dir = -1; if (cur.next && !mPrev.next) o.dir = 1;
    if (cur.a && !mPrev.a) o.a = true; if (cur.b && !mPrev.b) o.b = true;
    mPrev = cur; return o;
  };
})(window.HW);
