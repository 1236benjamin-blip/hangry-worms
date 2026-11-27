// Hangry Worms - app: menus, game loop, sound, glue
'use strict';
(function (HW) {
  const CFG = HW.CFG, CHARS = HW.CHARS, R = HW.Render, In = HW.Input, Net = HW.Net, fx = HW.fx;
  const $ = id => document.getElementById(id);
  const store = { get(k, d) { try { const v = localStorage.getItem('hw_' + k); return v === null ? d : v; } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem('hw_' + k, v); } catch (e) { } } };

  // ---------- sound (tiny synth, no files) ----------
  const Snd = { ctx: null, on: store.get('snd', '1') === '1', last: {} };
  Snd.unlock = function () {
    if (!Snd.ctx) { const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return; try { Snd.ctx = new AC(); } catch (e) { return; } }
    if (Snd.ctx.state !== 'running') { try { Snd.ctx.resume().catch(() => { }); } catch (e) { } }
  };
  function gate(key, ms) { const n = performance.now(); if (n - (Snd.last[key] || 0) < ms) return false; Snd.last[key] = n; return true; }
  Snd.tone = function (f, d, type, vol, f2, delay) {
    const c = Snd.ctx; if (!c || !Snd.on || c.state !== 'running') return; const t = c.currentTime + (delay || 0);
    const o = c.createOscillator(), g = c.createGain(); o.type = type || 'square'; o.frequency.setValueAtTime(f, t);
    if (f2) o.frequency.exponentialRampToValueAtTime(Math.max(20, f2), t + d);
    g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + d); o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + d + 0.02);
  };
  Snd.noise = function (d, vol, freq, f2) {
    const c = Snd.ctx; if (!c || !Snd.on || c.state !== 'running') return; const t = c.currentTime;
    if (!Snd.nb) { Snd.nb = c.createBuffer(1, c.sampleRate, c.sampleRate); const a = Snd.nb.getChannelData(0); for (let i = 0; i < a.length; i++) a[i] = Math.random() * 2 - 1; }
    const s = c.createBufferSource(); s.buffer = Snd.nb; const fl = c.createBiquadFilter(); fl.type = 'lowpass'; fl.frequency.setValueAtTime(freq, t); if (f2) fl.frequency.exponentialRampToValueAtTime(f2, t + d);
    const g = c.createGain(); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + d); s.connect(fl); fl.connect(g); g.connect(c.destination); s.start(t, Math.random() * 0.5, d + 0.05);
  };
  Snd.ui = () => Snd.tone(520, 0.06, 'square', 0.08, 780);

  // ---------- app state ----------
  const App = HW.App = { mode: 'menu', screen: '', sim: null, G: null, locals: [], paused: false, t: 0, acc: 0, myPid: -1, netFrame: 0, previews: [], focus: 0, sel: { mode: 'solo', step: 0, picks: [+store.get('ch', 0) || 0, 1], code: '' }, demoCam: { x: CFG.W / 2, y: CFG.H / 2 } };
  // bot difficulty (index into HW.DIFFS). Easy is the default: new players should survive their first minute.
  App.diff = Math.max(0, Math.min(HW.DIFFS.length - 1, +store.get('diff', 0) || 0));
  App.playDiff = App.diff;   // difficulty of the game being played (an online client gets the host's)
  // best scores are kept per difficulty. Keys from before (size-only scores, one shared number) are dropped.
  try { localStorage.removeItem('hw_best'); } catch (e) { }
  const bestKey = d => 'best3_' + d, getBest = d => +store.get(bestKey(d), 0) || 0;
  const ui = $('ui');
  const isTouch = ('ontouchstart' in window) || navigator.maxTouchPoints > 0;

  function U() { const d = window.devicePixelRatio || 1; return Math.max(1, Math.floor(Math.min(window.innerWidth * d / 450, window.innerHeight * d / 222) * 2) / 2) / d; }
  function el(tag, cls, kids) { const e = document.createElement(tag); if (cls) e.className = cls; (kids || []).forEach(k => k && e.appendChild(k)); return e; }
  function px(str, color, scale) {
    str = String(str); const w = Math.max(1, HW.textW(str, 1) + 1), c = HW.mk(w, 8); HW.text(c.getContext('2d'), str, 0, 0, color || '#fff');
    const u = U() * (scale || 1); c.style.width = (w * u) + 'px'; c.style.height = (8 * u) + 'px'; c.className = 'px'; return c;
  }
  function btn(label, fn, cls, scale, color) {
    const b = el('button', 'btn ' + (cls || ''), [px(label, color || '#fff', scale || 1.5)]);
    b.addEventListener('click', e => { e.preventDefault(); Snd.unlock(); Snd.ui(); fn(); }); return b;
  }
  let toastT = 0;
  App.toast = function (s) { const t = $('toast'); t.innerHTML = ''; t.appendChild(px(s, '#ffd23f', 1.5)); t.style.display = 'block'; clearTimeout(toastT); toastT = setTimeout(() => t.style.display = 'none', 3200); };

  App.show = function (name) {
    App.screen = name; ui.innerHTML = ''; App.previews = []; App.focus = -1;
    ui.style.setProperty('--u', U() + 'px'); ui.className = name ? 'on' : ''; In.enabled = !name;
    if (name && SCREENS[name]) SCREENS[name]();
  };

  const SCREENS = {};
  SCREENS.title = function () {
    ui.classList.add('clear');
    ui.appendChild(el('div', 'col', [px('HANGRY WORMS', '#ffd23f', 5), px('EAT JUNK. SHOOT WORMS. FART ON FRIENDS.', '#9be7ff', 1.2)]));
    const go = m => () => { App.sel.mode = m; App.sel.step = 0; App.show('select'); };
    ui.appendChild(el('div', 'row', [
      el('div', 'col', [btn('PLAY', go('solo'), 'go', 2), btn('2 PLAYERS, 1 SCREEN', go('two'))]),
      el('div', 'col', [btn('HOST ONLINE GAME', go('host')), btn('JOIN ONLINE GAME', go('join'))])
    ]));
    ui.appendChild(el('div', 'row', [btn('HOW TO PLAY', () => App.show('help'), 'alt', 1.2), btn(Snd.on ? 'SOUND: ON' : 'SOUND: OFF', () => { Snd.on = !Snd.on; store.set('snd', Snd.on ? '1' : '0'); App.show('title'); }, 'alt', 1.2)]));
    const bests = HW.DIFFS.map((d, i) => getBest(i) > 0 ? d.name + ' ' + getBest(i) : '').filter(Boolean);
    if (bests.length) ui.appendChild(px('YOUR BEST:  ' + bests.join('   '), '#b5e61d', 1));
  };

  SCREENS.help = function () {
    const L = [
      ['EAT JUNK FOOD TO GROW. RUN YOUR HEAD INTO ANOTHER WORM AND YOU DIE.', '#fff'],
      ['SHOOT WORMS TO KNOCK FOOD OUT OF THEM. AMMO COMES FROM CRATES.', '#fff'],
      ['COUNTERS, TABLES AND CRATES BLOCK SHOTS AND WORMS. HIDE BEHIND THEM.', '#fff'],
      ['VEGGIES SHRINK YOU AND SLOW YOU DOWN. MUSHROOMS MAKE EVERYTHING WOBBLY.', '#9cf08a'],
      ['FART: TOXIC CLOUD, KILLS ANY OTHER WORM.  PUKE: STICKY PUDDLE, STUCK 10 SEC.', '#d7e84a'],
      ['PHONE: LEFT THUMB MOVES. RIGHT THUMB AIMS AND SHOOTS. BOOST + ABILITY BUTTONS.', '#9be7ff'],
      ['KEYBOARD: WASD OR ARROWS MOVE. MOUSE AIMS, CLICK SHOOTS (OR SPACE).', '#9be7ff'],
      ['          SHIFT BOOSTS. E USES YOUR ABILITY. ESC PAUSES.', '#9be7ff'],
      ['CONTROLLER: LEFT STICK MOVE. RIGHT STICK AIM + SHOOT. A OR LT BOOST. X ABILITY.', '#9be7ff'],
      ['2 PLAYERS: EACH HALF OF THE SCREEN HAS ITS OWN TOUCH CONTROLS.', '#ffb0a8'],
      ['           OR P1 WASD+MOUSE, P2 CONTROLLER OR ARROWS, ENTER, SHIFT, PERIOD.', '#ffb0a8'],
      ['ONLINE: ONE DEVICE HOSTS AND SHARES THE 4 LETTER ROOM CODE. UP TO 4 PLAYERS.', '#ffb0a8']
    ];
    ui.appendChild(px('HOW TO PLAY', '#ffd23f', 2.5));
    ui.appendChild(el('div', 'panel', L.map(l => px(l[0] || ' ', l[1], 0.85))));
    const hb = btn('BACK', () => App.show(App.mode === 'play' ? 'pause' : 'title'), 'alt'); hb.dataset.back = '1'; hb.dataset.def = '1'; ui.appendChild(hb);
  };

  function statBars(C) {
    const c = HW.mk(276, 8), x = c.getContext('2d'); let ox = 0;
    [['SIZE', C.stats.size], ['SPEED', C.stats.speed], ['POWER', C.stats.power], ['FIRE RATE', C.stats.rate]].forEach(s => {
      ox += HW.text(x, s[0], ox, 0, '#aab') + 4;
      for (let i = 0; i < 5; i++) { x.fillStyle = i < s[1] ? '#ffd23f' : '#3a3358'; x.fillRect(ox + i * 5, 1, 4, 5); }
      ox += 34;
    });
    const u = U(); c.style.width = (276 * u) + 'px'; c.style.height = (8 * u) + 'px'; c.className = 'px'; return c;
  }
  SCREENS.select = function () {
    const S = App.sel, two = S.mode === 'two', who = two ? S.step : 0, pick = S.picks[who], C = CHARS[pick];
    ui.appendChild(px(two ? 'PLAYER ' + (who + 1) + ': PICK YOUR WORM' : 'PICK YOUR WORM', '#ffd23f', 2));
    const cards = CHARS.map((c, i) => {
      const pv = HW.mk(100, 38), u = U(); pv.className = 'px'; pv.style.width = (100 * u * 0.76) + 'px'; pv.style.height = (38 * u * 0.76) + 'px';
      const variant = two && who === 1 && S.picks[0] === i ? 1 : 0;
      App.previews.push({ c: pv, ch: i, variant });
      const b = el('button', 'btn card' + (i === pick ? ' sel' : ''), [pv, px(c.name, i === pick ? '#ffd23f' : '#ccd', 1.2)]);
      b.addEventListener('click', () => { Snd.unlock(); Snd.ui(); S.picks[who] = i; if (who === 0) store.set('ch', i); App.show('select'); });
      return b;
    });
    ui.appendChild(el('div', 'row nw', cards));
    const ab = C.ability === 'fart' ? 'ABILITY: FART - TOXIC CLOUD THAT KILLS OTHER WORMS' : C.ability === 'puke' ? 'ABILITY: PUKE - PUDDLE THAT GLUES WORMS IN PLACE' : 'NO ABILITY. WEAKNESS: FART AND PUKE BOTH KILL HIM';
    ui.appendChild(el('div', 'panel', [px(C.name + ' - ' + C.blurb, '#fff', 1), statBars(C), px('GUN: ' + C.gun.name + ' - ' + C.gun.desc, '#9be7ff', 0.9), px(ab, C.ability ? '#d7e84a' : '#ffb0a8', 0.9),
    two ? px(who === 0 ? 'P1: LEFT HALF OF THE SCREEN, OR WASD + MOUSE' : 'P2: RIGHT HALF OF THE SCREEN, A CONTROLLER, OR ARROW KEYS', '#ffb0a8', 0.9) : null]));
    const back = () => { if (two && S.step === 1) { S.step = 0; App.show('select'); } else App.show('title'); };
    const next = () => {
      if (S.mode === 'solo') startLocal([S.picks[0]]);
      else if (two) { if (S.step === 0) { S.step = 1; App.show('select'); } else startLocal([S.picks[0], S.picks[1]]); }
      else if (S.mode === 'host') startHost(S.picks[0]);
      else App.show('join');
    };
    const label = S.mode === 'solo' ? 'PLAY!' : two ? (S.step === 0 ? 'NEXT' : 'PLAY!') : S.mode === 'host' ? 'HOST GAME' : 'NEXT';
    const nb = btn(label, next, 'go', 1.6); nb.dataset.def = '1';
    const bb = btn('BACK', back, 'alt'); bb.dataset.back = '1';
    // bot difficulty: tap to cycle. Not shown when joining (the host's setting applies).
    const DCOL = ['#b5e61d', '#ffd23f', '#ff8a80'];
    const db = S.mode === 'join' ? null : btn('BOTS: ' + HW.DIFFS[App.diff].name, () => { App.diff = (App.diff + 1) % HW.DIFFS.length; store.set('diff', App.diff); App.show('select'); }, 'alt', 1.2, DCOL[App.diff]);
    if (db) db.dataset.diff = '1';
    ui.appendChild(el('div', 'row', [bb, db, nb]));
  };

  SCREENS.join = function () {
    ui.appendChild(px('ENTER ROOM CODE', '#ffd23f', 2));
    const inp = el('input', 'code'); inp.maxLength = 4; inp.value = App.sel.code || ''; inp.autocapitalize = 'characters'; inp.autocomplete = 'off'; inp.spellcheck = false;
    inp.addEventListener('input', () => { inp.value = inp.value.toUpperCase().replace(/[^A-Z]/g, ''); App.sel.code = inp.value; });
    const go = () => { if ((App.sel.code || '').length === 4) startJoin(App.sel.picks[0], App.sel.code); else App.toast('THE CODE IS 4 LETTERS'); };
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    ui.appendChild(inp);
    ui.appendChild(px('ASK THE HOST FOR THE 4 LETTERS ON THEIR SCREEN', '#9be7ff', 0.9));
    const bb = btn('BACK', () => App.show('select'), 'alt'); bb.dataset.back = '1';
    ui.appendChild(el('div', 'row', [bb, btn('JOIN', go, 'go', 1.6)]));
    if (!isTouch) setTimeout(() => inp.focus(), 50);
  };
  SCREENS.connecting = function () {
    ui.appendChild(px(App.connMsg || 'CONNECTING...', '#ffd23f', 2));
    const bb = btn('CANCEL', () => quit(), 'alt'); bb.dataset.back = '1'; ui.appendChild(bb);
  };
  SCREENS.pause = function () {
    ui.appendChild(px(Net.role ? 'MENU' : 'PAUSED', '#ffd23f', 3));
    if (HW.DIFFS[App.playDiff]) ui.appendChild(px('BOTS: ' + HW.DIFFS[App.playDiff].name, '#9be7ff', 1));
    if (Net.role) {
      ui.appendChild(el('div', 'panel c', [px('ROOM CODE', '#9be7ff', 1), px(Net.code, '#ffd23f', 4), px(Net.role === 'host' ? 'FRIENDS: OPEN THE GAME, JOIN ONLINE GAME, TYPE THIS CODE' : 'THE GAME KEEPS RUNNING WHILE THIS MENU IS OPEN', '#ccd', 0.85)]));
      if (Net.role === 'host') ui.appendChild(btn('SHARE INVITE LINK', share, '', 1.2));
    }
    const rb = btn('RESUME', () => setPause(false), 'go', 1.6); rb.dataset.back = '1';
    ui.appendChild(el('div', 'row', [rb, btn(Snd.on ? 'SOUND: ON' : 'SOUND: OFF', () => { Snd.on = !Snd.on; store.set('snd', Snd.on ? '1' : '0'); App.show('pause'); }, 'alt'), btn('HOW TO PLAY', () => App.show('help'), 'alt'), btn('QUIT', quit, 'alt')]));
  };
  const ORD = n => n + (n % 10 === 1 && n !== 11 ? 'ST' : n % 10 === 2 && n !== 12 ? 'ND' : n % 10 === 3 && n !== 13 ? 'RD' : 'TH');
  function compName(q) {
    const local = App.locals.find(l => l.player && l.player.pid === q.pid);
    if (q.pid < 0) return CHARS[q.ch].name;
    return (local ? (App.locals.length > 1 ? 'P' + (local.slot + 1) : 'YOU') : 'P' + (q.pid + 1)) + ' ' + CHARS[q.ch].name;
  }
  SCREENS.results = function () {
    ui.classList.add('solid');
    const G = App.G, M = G.match || {}, ranked = (G.comps || []).slice().sort((a, b) => b.score - a.score || b.kills - a.kills);
    ui.appendChild(px(M.reason === 'lives' ? 'OUT OF LIVES!' : "TIME'S UP!", '#ffd23f', 2.6));
    const cols = ['#ffd23f', '#d9d9e0', '#e0934a'];
    const card = i => {
      const q = ranked[i]; if (!q) return null;
      const pv = HW.mk(100, 38), u = U(); pv.className = 'px'; pv.style.width = (100 * u * (i === 0 ? 1 : 0.8)) + 'px'; pv.style.height = (38 * u * (i === 0 ? 1 : 0.8)) + 'px';
      App.previews.push({ c: pv, ch: q.ch, variant: q.variant });
      const mineQ = App.locals.some(l => l.player && l.player.pid === q.pid);
      const d = el('div', 'panel c', [px(ORD(i + 1), cols[i], i === 0 ? 2.2 : 1.6), pv, px(compName(q), mineQ ? '#ffd23f' : '#fff', 1.1), px('SCORE ' + q.score, '#9be7ff', 1), px('KILLS ' + q.kills, '#ff8a80', 1)]);
      d.style.borderColor = cols[i]; if (i > 0) d.style.alignSelf = 'flex-end'; return d;
    };
    ui.appendChild(el('div', 'row nw', [card(1), card(0), card(2)]));
    const lines = [];
    for (const l of App.locals) {
      const q = ranked.find(r => l.player && r.pid === l.player.pid); if (!q) continue;
      const pos = ranked.indexOf(q) + 1, who = App.locals.length > 1 ? 'P' + (l.slot + 1) : 'YOU';
      lines.push(px(pos === 1 ? who + (who === 'YOU' ? ' WIN!' : ' WINS!') + '  SCORE ' + q.score + '  KILLS ' + q.kills : who + ' FINISHED ' + ORD(pos) + ' OF ' + ranked.length + '  -  SCORE ' + q.score + '  KILLS ' + q.kills, pos <= 3 ? '#b5e61d' : '#fff', 1.1));
      if (q.score > (App.bestBefore || 0) && App.locals.length === 1) lines.push(px('NEW BEST SCORE!', '#ffd23f', 1));
    }
    if (lines.length) ui.appendChild(el('div', 'col', lines));
    const row = [];
    if (Net.role !== 'client') { const b = btn('PLAY AGAIN', () => { if (App.sim) App.sim.restart(); }, 'go', 1.6); b.dataset.def = '1'; row.push(b); }
    const mb = btn('MENU', quit, 'alt'); mb.dataset.back = '1'; row.push(mb);
    ui.appendChild(el('div', 'row', row));
    if (Net.role) { App.nextEl = el('div', 'col', []); ui.appendChild(App.nextEl); App.nextShown = -1; }
  };
  function share() {
    const url = location.origin + location.pathname + '?join=' + Net.code;
    if (navigator.share) navigator.share({ title: 'Hangry Worms', text: 'Join my Hangry Worms room ' + Net.code, url }).catch(() => { });
    else if (navigator.clipboard) navigator.clipboard.writeText(url).then(() => App.toast('INVITE LINK COPIED'), () => App.toast('ROOM CODE: ' + Net.code));
    else App.toast('ROOM CODE: ' + Net.code);
  }

  // ---------- starting / stopping games ----------
  function mkLocal(slot, ch) { return { slot, ch, dev: {}, view: { x: 0, y: 0, w: 1, h: 1, cam: { x: CFG.W / 2, y: CFG.H / 2 }, trip: 0, slow: 0, shake: 0 }, player: null, me: null, abilSeq: 0, wantSpawn: false }; }
  function begin() {
    if (isTouch && In.lastKind !== 'pad') { In.touch.used = true; In.lastKind = 'touch'; }
    fx.clear(); App.mode = 'play'; App.paused = false; App.acc = 0; In.resetTouch(); In.pausePressed = false; In.layout(); App.show('');
    if (isTouch) {
      try { const d = document.documentElement; if (d.requestFullscreen && !document.fullscreenElement) d.requestFullscreen({ navigationUI: 'hide' }).then(() => { try { screen.orientation.lock('landscape').catch(() => { }); } catch (e) { } }).catch(() => { }); } catch (e) { }
    }
    try { if (navigator.wakeLock) navigator.wakeLock.request('screen').then(l => App.wake = l).catch(() => { }); } catch (e) { }
  }
  function newSim(diff) { return new HW.Sim({ diff: diff === undefined ? 1 : diff }); }   // the demo behind the menu plays at intermediate
  function startLocal(chars) {
    Net.close(); App.playDiff = App.diff; App.sim = newSim(App.diff); App.G = App.sim.S; App.sim.S.events = []; App.bestBefore = getBest(App.playDiff);
    App.locals = chars.map((ch, i) => { const l = mkLocal(i, ch); l.player = App.sim.addPlayer(ch); l.player.best = getBest(App.playDiff); l.player.inp = { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false }; return l; });
    begin();
  }
  function startHost(ch) {
    startLocal([ch]); App.sim.S.autoNext = 15; App.toast('OPENING ROOM...');
    Net.host(() => App.mode === 'play' && Net.role !== 'client' ? App.sim : null, (err, code) => {
      if (App.mode !== 'play') { Net.close(); return; }
      if (err) { App.sim.S.autoNext = 0; App.toast(err + ' - PLAYING OFFLINE'); } else App.toast('ROOM CODE: ' + code + '  (PAUSE TO SHARE)');
    });
  }
  function startJoin(ch, code) {
    Net.close(); App.connMsg = 'JOINING ROOM ' + code + '...'; App.mode = 'connecting'; App.show('connecting');
    const G = Net.newMirror();
    Net.join(code, ch, {
      onInit(m) { App.myPid = m.pid; App.playDiff = Math.max(0, Math.min(HW.DIFFS.length - 1, m.d | 0)); App.bestBefore = getBest(App.playDiff); },
      onPart(m) { Net.applyPart(G, m); },
      onSnap(m) {
        Net.applySnap(G, m);
        if (m.first && App.mode === 'connecting') { App.G = G; App.sim = null; App.locals = [mkLocal(0, ch)]; begin(); }
        if (App.mode === 'play' && App.G === G) for (const e of m.e) onEvent(e);
      },
      onClose(msg) { const was = App.mode; Net.close(); if (was === 'play' || was === 'connecting') { saveBest(); toMenu(); App.toast(msg); } }
    });
  }
  function toMenu() { App.mode = 'menu'; App.locals = []; App.sim = newSim(); App.G = App.sim.S; fx.clear(); App.show('title'); try { if (App.wake) App.wake.release(); } catch (e) { } }
  function quit() { saveBest(); Net.close(); toMenu(); }
  function saveBest() { for (const l of App.locals) { const b = Math.round((l.player && l.player.best) || 0); if (b > getBest(App.playDiff)) store.set(bestKey(App.playDiff), b); } }
  function setPause(p) { for (const l of App.locals) if (l.dev.prev) l.dev.prev.pause = true; App.paused = p; In.resetTouch(); App.show(p ? 'pause' : ''); }

  // ---------- events -> particles + sound ----------
  function near(x, y) { let d = 1e9; for (const l of App.locals) { const q = Math.abs(l.view.cam.x - x) + Math.abs(l.view.cam.y - y); if (q < d) d = q; } return d; }
  const mine = id => App.locals.some(l => l.me && l.me.id === id);
  const FOODC = ['#ffd23f', '#f08a1c', '#e03c32', '#ff7eb6', '#fff1c9'];
  function onEvent(e) {
    const k = e[0], x = e[1], y = e[2], demo = App.mode !== 'play', d = demo ? 1e9 : near(x, y), vol = d < 480 ? Math.max(0.15, 1 - d / 480) : 0;
    switch (k) {
      case 'shot': {
        fx.burst(x, y, ['#fff', '#ffd23f'], 3, 60, 0.15, 2); if (!vol) break; const v = vol * (mine(e[4]) ? 1 : 0.5);
        if (e[3] === 0) { if (gate('s0', 60)) { Snd.tone(150, 0.2, 'square', 0.16 * v, 50); Snd.noise(0.14, 0.2 * v, 900); } }
        else if (e[3] === 1) { if (gate('s1', 60)) Snd.noise(0.2, 0.3 * v, 2600, 400); }
        else if (e[3] === 2) { if (gate('s2', 55)) Snd.tone(700 + Math.random() * 200, 0.05, 'square', 0.06 * v, 400); }
        else if (e[3] === 3) { if (gate('s3', 60)) Snd.tone(1100, 0.1, 'triangle', 0.14 * v, 300); }
        else if (gate('s4', 60)) { Snd.noise(0.5, 0.25 * v, 600, 2400); Snd.tone(90, 0.3, 'sawtooth', 0.1 * v, 200); }
        break;
      }
      case 'eat': if (mine(e[3]) && gate('eat', 45)) Snd.tone(500 + e[4] * 110 + Math.random() * 60, 0.05, 'square', 0.05, 900); break;
      case 'hit': fx.burst(x, y, FOODC, 6, 90, 0.4, 2); if (mine(e[3])) { fx.text(x, y - 10, '-' + e[4], '#ff5a4d'); if (gate('ouch', 80)) Snd.tone(220, 0.12, 'sawtooth', 0.14, 90); for (const l of App.locals) if (l.me && l.me.id === e[3]) l.view.shake = 0.2; } else if (vol && gate('hit', 50)) Snd.tone(320, 0.05, 'square', 0.05 * vol, 160); break;
      case 'puff': fx.burst(x, y, ['#ccc', '#888'], 2, 30, 0.2, 1); break;
      case 'clang': fx.burst(x, y, ['#fff', '#c9d2e0', '#8d99ae'], 4, 70, 0.25, 1); if (vol && gate('clang', 70)) Snd.tone(1500 + Math.random() * 500, 0.04, 'triangle', 0.05 * vol, 700); break;
      case 'boom': fx.burst(x, y, ['#fff', '#ffd23f', '#f08a1c', '#e03c32', '#555'], 46, 260, 0.6, 3); fx.burst(x, y, ['#777', '#555'], 14, 90, 0.9, 4);
        if (vol) { Snd.noise(0.7, 0.5 * vol, 1400, 90); Snd.tone(110, 0.5, 'sine', 0.3 * vol, 35); for (const l of App.locals) if (Math.abs(l.view.cam.x - x) + Math.abs(l.view.cam.y - y) < 320) l.view.shake = Math.max(l.view.shake, 0.35); } break;
      case 'die': {
        const vc = CHARS[e[6]], cols = vc.colors[e[10] % 4]; fx.burst(x, y, [cols[0], cols[1], '#fff', '#e03c32'], 30, 170, 0.7, 3);
        if (demo) break;
        const meV = e[8] >= 0 && App.locals.some(l => l.player && l.player.pid === e[8]), meK = e[9] >= 0 && App.locals.some(l => l.player && l.player.pid === e[9]);
        if (vol) { Snd.noise(0.3, 0.3 * vol, 900, 200); Snd.tone(300, 0.35, 'square', 0.1 * vol, 60); }
        if (meV) { Snd.tone(400, 0.6, 'sawtooth', 0.16, 50); saveBest(); for (const l of App.locals) if (l.player && l.player.pid === e[8]) l.view.shake = 0.5; }
        if (meK) { Snd.tone(523, 0.1, 'square', 0.1); Snd.tone(784, 0.18, 'square', 0.1, 0, 0.1); }
        if (e[5] === 'left') break;
        const kn = e[7] >= 0 ? CHARS[e[7]].name : '', vn = vc.name, verb = { fart: ' GASSED ', puke: ' DROWNED ', shot: ' SHOT ', crash: ' ATE ', bonk: ' FLATTENED ' }[e[5]] || ' GOT ';
        if (kn && (meV || meK || e[8] >= 0 || e[9] >= 0 || d < 380)) fx.feed.push({ s: e[5] === 'crash' ? vn + ' CRASHED INTO ' + kn : kn + verb + vn, c: meK ? '#b5e61d' : meV ? '#ff8a80' : '#bbc', t: 4 });
        break;
      }
      case 'fart': fx.burst(x, y, ['#7ed321', '#a8e04a', '#c6f06a'], 26, 120, 0.8, 3); if (vol && gate('fart', 100)) { Snd.tone(95, 0.55, 'sawtooth', 0.22 * vol, 48); Snd.noise(0.5, 0.18 * vol, 300, 120); } break;
      case 'puke': fx.burst(x, y, ['#c9c13a', '#a3b02c', '#f08a1c'], 26, 110, 0.6, 3); if (vol && gate('puke', 100)) { Snd.noise(0.45, 0.3 * vol, 700, 250); Snd.tone(260, 0.4, 'triangle', 0.14 * vol, 110); } break;
      case 'stuck': fx.text(x, y - 16, 'STUCK!', '#d7e84a'); if (mine(e[3])) Snd.tone(180, 0.4, 'triangle', 0.16, 70); break;
      case 'veg': fx.text(x, y - 12, e[4] ? 'YUCK! -' + e[4] : 'YUCK!', '#9cf08a'); fx.burst(x, y, ['#5cc04a', '#2f7d32'], 8, 60, 0.4, 2); if (mine(e[3])) Snd.tone(200, 0.3, 'sawtooth', 0.12, 120); break;
      case 'shroom': fx.text(x, y - 12, 'WHOA!', '#ff7eb6'); fx.burst(x, y, ['#ff7eb6', '#4cc9f0', '#ffd23f'], 12, 70, 0.6, 2); if (mine(e[3])) { Snd.tone(300, 0.6, 'sine', 0.14, 900); Snd.tone(450, 0.6, 'sine', 0.1, 150, 0.1); } break;
      case 'ammo': fx.text(x, y - 12, '+AMMO', '#ffd23f'); if (mine(e[3])) { Snd.tone(660, 0.07, 'square', 0.1); Snd.tone(990, 0.1, 'square', 0.1, 0, 0.07); } break;
      case 'dry': if (mine(e[3]) && gate('dry', 200)) Snd.tone(1200, 0.03, 'square', 0.06); break;
    }
  }

  // ---------- frame ----------
  function layoutViews() {
    const n = App.locals.length, W = R.W, H = R.H;
    App.locals.forEach((l, i) => { const v = l.view; if (n === 1) { v.x = 0; v.y = 0; v.w = W; v.h = H; } else { const hw = Math.floor(W / 2); v.x = i * (W - hw); v.y = 0; v.w = hw; v.h = H; } });
    const np = In.pads().length;
    if (n === 1) App.locals[0].dev = Object.assign(App.locals[0].dev, { touch: true, kb: 'both', mouse: true, pad: 'any' });
    else {
      Object.assign(App.locals[0].dev, { touch: true, kb: 'wasd', mouse: true, pad: np >= 2 ? 0 : -1 });
      Object.assign(App.locals[1].dev, { touch: true, tpad: 1, kb: 'arrows', mouse: false, pad: np >= 1 ? np - 1 : -1 });   // tpad: which half's touch controls (see input.js)
    }
  }
  function playFrame(dt) {
    R.setTarget(App.locals.length > 1 ? 380 : 270); layoutViews(); const client = Net.role === 'client', G = App.G;
    const M = G.match;
    if (M && M.over && App.screen !== 'results') { App.paused = false; saveBest(); In.resetTouch(); App.show('results'); Snd.tone(523, 0.14, 'square', 0.1); Snd.tone(659, 0.14, 'square', 0.1, 0, 0.14); Snd.tone(784, 0.3, 'square', 0.1, 0, 0.28); }
    else if (M && !M.over && App.screen === 'results') { App.bestBefore = getBest(App.playDiff); fx.clear(); App.show(''); }
    if (App.screen === 'results') {
      In.pausePressed = false;
      if (App.nextEl) { const s = Math.ceil(Net.role === 'host' ? Math.max(0, (App.sim.S.autoNext || 0) - M.overT) : M.next || 0); if (s !== App.nextShown) { App.nextShown = s; App.nextEl.innerHTML = ''; App.nextEl.appendChild(px(s > 0 ? 'NEXT MATCH IN ' + s : 'NEXT MATCH STARTING...', '#9be7ff', 1)); } }
    }
    if (M && !M.over && M.t <= 10 && M.t > 0 && Math.ceil(M.t) !== App.lastTick) { App.lastTick = Math.ceil(M.t); Snd.tone(880, 0.06, 'square', 0.07); }
    if (In.pausePressed) { In.pausePressed = false; setPause(!App.paused); }
    const frozen = App.paused && !Net.role;
    for (const l of App.locals) {
      const o = App.paused || App.screen === 'results' ? { mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false, tap: false, pause: false } : In.read(l.dev, l.view);
      if (o.pause) { setPause(true); }
      let p;
      if (client) {
        p = l.player = G.players.find(q => q.pid === App.myPid) || { deadT: 0 }; l.me = p.wormId ? G.wmap.get(p.wormId) || null : null;
        if (o.abil) l.abilSeq++;
        const dead = !l.me; l.wantSpawn = dead && (p.deadT > 3 || (p.deadT > 1 && o.tap));
        if (l.me) { const aiming = o.ax * o.ax + o.ay * o.ay > 0.09; l.me.localAim = aiming; if (aiming) l.me.aim = Math.atan2(o.ay, o.ax); if (l.me.mass > (l.best || 0)) l.best = l.me.mass; }
        p.best = Math.max(p.best || 0, l.best || 0);
        G.myId = l.me ? l.me.id : 0; G.myInp = o;   // net.js predicts our own worm from these (see Net.clientUpdate)
        Net.sendInput(o, l.abilSeq, l.wantSpawn);
      } else {
        p = l.player; const I = p.inp; I.mx = o.mx; I.my = o.my; I.ax = o.ax; I.ay = o.ay; I.fire = o.fire; I.boost = o.boost; I.auto = o.auto; if (o.abil) I.abil = true;
        const alive = p.worm && p.worm.alive; if (!alive) { I.abil = false; if (p.deadT > 3 || (p.deadT > 1 && o.tap)) p.wantSpawn = true; }
        l.me = alive ? p.worm : null;
      }
    }
    if (client) Net.clientUpdate(G, dt);
    else if (!frozen) {
      advance(dt, 4, false);
      for (const l of App.locals) l.me = l.player.worm && l.player.worm.alive ? l.player.worm : null;
    }
    if (!frozen) fx.update(dt);
    const t = App.t;
    for (const l of App.locals) {
      const v = l.view, me = l.me;
      if (me) { const k = 1 - Math.exp(-dt * 10); v.cam.x += (me.x - v.cam.x) * k; v.cam.y += (me.y - v.cam.y) * k; v.trip = me.trip; v.slow = me.slow; }
      else {
        v.trip = 0; v.slow = 0;
        const cq = l.player && (G.comps || []).find(q => q.pid === l.player.pid);
        if (cq && cq.out && l.player.deadT > 1.5) { // out of lives: watch the biggest worm
          let top = null; for (const w of G.worms) if (w.alive && (!top || w.mass > top.mass)) top = w;
          if (top) { const k = 1 - Math.exp(-dt * 3); v.cam.x += (top.x - v.cam.x) * k; v.cam.y += (top.y - v.cam.y) * k; }
        }
      }
      let sx = 0, sy = 0; if (v.shake > 0) { v.shake -= dt; sx = (Math.random() - 0.5) * 10 * v.shake / 0.3; sy = (Math.random() - 0.5) * 10 * v.shake / 0.3; }
      v.meId = me ? me.id : 0; v.cam.x += sx; v.cam.y += sy; R.drawView(v, G, t); if (me) { v.px += me.x - v.cam.x; v.py += me.y - v.cam.y; } v.cam.x -= sx; v.cam.y -= sy;
      // P1 (and solo) follow In.lastKind; P2's touch controls show unless P2 is on a controller or the keyboard
      const useTouch = l.useTouch = !!(l.dev.touch && In.touch.used && (l.slot === 0 ? In.lastKind === 'touch' : isTouch && !l.dev.hasPad && (l.dev.kind || 'touch') === 'touch'));
      R.drawHUD(v, { G, me, player: l.player, t, touch: useTouch, roomCode: l.slot === 0 && Net.role ? Net.code : '', slotLabel: App.locals.length > 1 ? 'P' + (l.slot + 1) : '', abilKey: useTouch ? '' : (l.slot === 0 ? In.lastKind === 'pad' : l.dev.hasPad) ? '(X)' : l.slot === 1 ? '(.)' : '(E)' });
    }
    if (App.locals.length > 1) R.divider(App.locals[1].view.x);
    if (App.previews.length) drawPreviews();
    for (const l of App.locals) if (l.useTouch) R.drawTouch(In.tpads[l.dev.tpad || 0], l.me, t, CHARS[l.ch]);
  }
  // step the authoritative sim, play its events, feed the network
  function advance(dt, maxSteps, silent) {
    App.acc += dt; let n = 0;
    while (App.acc >= 1 / 60 && n++ < maxSteps) { App.sim.step(1 / 60); App.acc -= 1 / 60; } if (n >= maxSteps) App.acc = 0;
    const S = App.sim.S, evs = S.events; S.events = [];
    if (!silent) for (const e of evs) onEvent(e);
    if (Net.role === 'host') { if (Net.hostTick(App.sim, dt, evs)) { S.adds.length = 0; S.rems.length = 0; } } else { S.adds.length = 0; S.rems.length = 0; }
  }
  // A hosted room must keep running when the host's tab is hidden (rAF stops there).
  // A worker timer is not throttled like page timers, so it drives the sim in the background.
  let bgLast = 0;
  function bgTick() {
    if (!document.hidden || App.mode !== 'play' || Net.role !== 'host' || !App.sim) { bgLast = 0; return; }
    const now = performance.now(), dt = bgLast ? Math.min(0.25, (now - bgLast) / 1000) : 0.033; bgLast = now;
    for (const l of App.locals) { const I = l.player.inp; I.mx = I.my = I.ax = I.ay = 0; I.fire = I.boost = false; const p = l.player; if ((!p.worm || !p.worm.alive) && p.deadT > 3) p.wantSpawn = true; }
    advance(dt, 16, true);
  }
  try {
    const wk = new Worker(URL.createObjectURL(new Blob(['setInterval(function(){postMessage(0)},33)'], { type: 'text/javascript' })));
    wk.onmessage = bgTick;
  } catch (e) { setInterval(bgTick, 33); }
  function drawPreviews() {
    for (const p of App.previews) {
      const c = p.c.getContext('2d'); c.clearRect(0, 0, 100, 38); const C = CHARS[p.ch], pts = [];
      for (let i = 0; i < 15; i++) pts.push({ x: 76 - i * 6, y: 21 + Math.sin(App.t * 5 - i * 0.55) * (i === 0 ? 1 : 2.5) });
      R.drawWormPreview(c, { id: p.ch, ch: p.ch, variant: p.variant, x: pts[0].x, y: pts[0].y, ang: 0, aim: Math.sin(App.t * 1.5 + p.ch) * 0.5, pts, r: C.baseR, mass: C.startMass, alive: true, shield: 0, stuck: 0, slow: 0, boosting: false }, App.t);
    }
  }
  const demoView = { x: 0, y: 0, w: 1, h: 1, cam: App.demoCam, trip: 0, slow: 0 };
  function menuFrame(dt) {
    // a bots-only game plays behind the menu
    R.setTarget(270); if (!App.sim) { App.sim = newSim(); App.G = App.sim.S; }
    App.acc += dt; let n = 0; while (App.acc >= 1 / 60 && n++ < 3) { App.sim.step(1 / 60); App.acc -= 1 / 60; } if (n >= 3) App.acc = 0;
    const S = App.sim.S; for (const e of S.events) onEvent(e); S.events = []; S.adds.length = 0; S.rems.length = 0; fx.update(dt);
    let top = null; for (const w of S.worms) if (w.alive && (!top || w.mass > top.mass)) top = w;
    if (top) { const k = 1 - Math.exp(-dt * 2); App.demoCam.x += (top.x - App.demoCam.x) * k; App.demoCam.y += (top.y - App.demoCam.y) * k; }
    demoView.w = R.W; demoView.h = R.H; R.drawView(demoView, S, App.t);
    drawPreviews();
  }
  let kNav = { dir: 0, a: false, b: false };
  window.addEventListener('keydown', e => {
    if (!App.screen || e.repeat) return; const inField = e.target && e.target.tagName === 'INPUT';
    if (e.code === 'Escape') kNav.b = true;
    if (inField) return;
    if (e.code === 'ArrowUp' || e.code === 'ArrowLeft') { kNav.dir = -1; e.preventDefault(); } else if (e.code === 'ArrowDown' || e.code === 'ArrowRight') { kNav.dir = 1; e.preventDefault(); }
    else if (e.code === 'Enter' || e.code === 'Space') { if (!(document.activeElement && document.activeElement.tagName === 'BUTTON')) kNav.a = true; }
  });
  function menuNav() {
    const m = In.menu(); if (kNav.dir) m.dir = kNav.dir; if (kNav.a) m.a = true; if (kNav.b) m.b = true; kNav = { dir: 0, a: false, b: false };
    if (!App.screen) return;
    const bs = Array.from(ui.querySelectorAll('button'));
    if (!bs.length) return;
    if (m.dir) {
      if (App.focus < 0) App.focus = Math.max(0, bs.findIndex(b => b.dataset.def || b.classList.contains('sel') || b.classList.contains('go'))) - (bs.some(b => b.classList.contains('sel')) ? 0 : m.dir);
      App.focus = (App.focus + m.dir + bs.length) % bs.length;
      bs.forEach((b, i) => b.classList.toggle('focus', i === App.focus)); Snd.unlock();
    }
    if (m.a) { Snd.unlock(); let b = bs[App.focus]; if (!b) b = bs.find(q => q.dataset.def) || bs.find(q => q.classList.contains('go')); if (b) { const f = App.focus, sc = App.screen; b.click(); if (App.screen === sc && sc === 'select') { App.focus = f; const nb = ui.querySelectorAll('button')[f]; if (nb) nb.classList.add('focus'); } } }
    if (m.b) { const b = bs.find(q => q.dataset.back); if (b) b.click(); }
  }
  let last = 0;
  function frame(ts) {
    requestAnimationFrame(frame);
    const dt = Math.min(0.05, Math.max(0.001, (ts - last) / 1000)); last = ts; App.t += dt; App.dt = dt;
    if (In.keys.Escape && App.screen && App.mode !== 'play') { /* no-op */ }
    menuNav();
    if (App.mode === 'play') playFrame(dt); else { In.pausePressed = false; menuFrame(dt); }
  }

  function checkRotate() {
    const r = $('rotate'), portrait = window.innerHeight > window.innerWidth * 1.05;
    if (isTouch && portrait) { if (App.mode === 'play' && !Net.role && !App.paused) setPause(true); r.innerHTML = ''; r.style.display = 'flex'; const u = Math.max(1, Math.floor(window.innerWidth / 150)); const a = px('TURN YOUR PHONE', '#ffd23f', 1), b = px('SIDEWAYS', '#ffd23f', 1);[a, b].forEach(c => { c.style.width = (c.width * u) + 'px'; c.style.height = (8 * u) + 'px'; r.appendChild(c); }); }
    else r.style.display = 'none';
  }

  window.addEventListener('load', () => {
    R.init($('game')); In.init($('game')); In.layout();
    const onRes = () => { In.layout(); checkRotate(); if (App.screen && !(document.activeElement && document.activeElement.tagName === 'INPUT')) App.show(App.screen); };
    window.addEventListener('resize', onRes); window.addEventListener('orientationchange', () => setTimeout(onRes, 300));
    document.addEventListener('visibilitychange', () => { if (document.hidden && App.mode === 'play' && !Net.role && !App.paused) setPause(true); saveBest(); });
    window.addEventListener('pointerdown', () => Snd.unlock(), { passive: true }); window.addEventListener('touchend', () => Snd.unlock(), { passive: true }); window.addEventListener('keydown', () => Snd.unlock());
    window.addEventListener('gamepadconnected', () => { if (App.mode === 'play') App.toast('CONTROLLER CONNECTED'); });
    App.sim = newSim(); App.G = App.sim.S; checkRotate();
    const j = /[?&]join=([A-Za-z]{4})/.exec(location.search);
    if (j) { App.sel.mode = 'join'; App.sel.code = j[1].toUpperCase(); App.show('select'); } else App.show('title');
    requestAnimationFrame(frame);
  });
  App.startLocal = startLocal; App.startHost = startHost; App.startJoin = startJoin; App.quit = quit; App.setPause = setPause; App.Snd = Snd;
})(window.HW);
