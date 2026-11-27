// Hangry Worms - pixel font + sprites (all art is generated from these strings, no image files)
'use strict';
window.HW = window.HW || {};
(function (HW) {
  // One character per pixel. '.' (or a space) is transparent. Every row of a sprite must be the same length.
  const PAL = {
    k: '#1a1423', w: '#ffffff', y: '#ffd23f', o: '#f08a1c', O: '#c9601a', r: '#e03c32', R: '#9c2020',
    b: '#8a4b25', B: '#5a2e14', t: '#e8b574', T: '#f6d9a0', g: '#5cc04a', G: '#2f7d32', p: '#ff7eb6',
    P: '#9b5de5', c: '#4cc9f0', C: '#2b6fd6', s: '#9aa0a8', S: '#555b66', l: '#b5e61d', e: '#fff1c9',
    m: '#d94fd0', M: '#7b2a8f', n: '#6b7a3a', N: '#3e4a22',
    // extra shades: light steel, gunmetal, deep pink, mid tan, pale yellow, ice, light green, deep green, light red
    a: '#dfe3ea', q: '#2f3340', x: '#c9407e', d: '#c98a4a', h: '#ffe98a', i: '#c9f2ff', u: '#8fdc6a',
    J: '#1f5a28', v: '#ff7a6b'
  };
  HW.PAL = PAL;

  function mk(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
  HW.mk = mk;

  function sprite(rows, pal) {
    pal = pal || PAL;
    const w = Math.max.apply(null, rows.map(r => r.length)), h = rows.length;
    const c = mk(w, h), x = c.getContext('2d');
    for (let j = 0; j < h; j++) for (let i = 0; i < rows[j].length; i++) {
      const ch = rows[j][i]; if (ch === '.' || ch === ' ') continue;
      x.fillStyle = pal[ch] || PAL[ch] || '#f0f'; x.fillRect(i, j, 1, 1);
    }
    return c;
  }
  HW.sprite = sprite;

  // ---------- 5x7 font ----------
  const F = {
    A: '01110/10001/10001/11111/10001/10001/10001', B: '11110/10001/10001/11110/10001/10001/11110',
    C: '01110/10001/10000/10000/10000/10001/01110', D: '11110/10001/10001/10001/10001/10001/11110',
    E: '11111/10000/10000/11110/10000/10000/11111', F: '11111/10000/10000/11110/10000/10000/10000',
    G: '01110/10001/10000/10111/10001/10001/01111', H: '10001/10001/10001/11111/10001/10001/10001',
    I: '01110/00100/00100/00100/00100/00100/01110', J: '00111/00010/00010/00010/00010/10010/01100',
    K: '10001/10010/10100/11000/10100/10010/10001', L: '10000/10000/10000/10000/10000/10000/11111',
    M: '10001/11011/10101/10101/10001/10001/10001', N: '10001/11001/10101/10011/10001/10001/10001',
    O: '01110/10001/10001/10001/10001/10001/01110', P: '11110/10001/10001/11110/10000/10000/10000',
    Q: '01110/10001/10001/10001/10101/10010/01101', R: '11110/10001/10001/11110/10100/10010/10001',
    S: '01111/10000/10000/01110/00001/00001/11110', T: '11111/00100/00100/00100/00100/00100/00100',
    U: '10001/10001/10001/10001/10001/10001/01110', V: '10001/10001/10001/10001/10001/01010/00100',
    W: '10001/10001/10001/10101/10101/10101/01010', X: '10001/10001/01010/00100/01010/10001/10001',
    Y: '10001/10001/01010/00100/00100/00100/00100', Z: '11111/00001/00010/00100/01000/10000/11111',
    0: '01110/10001/10011/10101/11001/10001/01110', 1: '00100/01100/00100/00100/00100/00100/01110',
    2: '01110/10001/00001/00010/00100/01000/11111', 3: '11110/00001/00001/01110/00001/00001/11110',
    4: '00010/00110/01010/10010/11111/00010/00010', 5: '11111/10000/11110/00001/00001/10001/01110',
    6: '00110/01000/10000/11110/10001/10001/01110', 7: '11111/00001/00010/00100/01000/01000/01000',
    8: '01110/10001/10001/01110/10001/10001/01110', 9: '01110/10001/10001/01111/00001/00010/01100',
    '.': '00000/00000/00000/00000/00000/01100/01100', ',': '00000/00000/00000/00000/01100/00100/01000',
    '!': '00100/00100/00100/00100/00100/00000/00100', '?': '01110/10001/00001/00010/00100/00000/00100',
    ':': '00000/01100/01100/00000/01100/01100/00000', '-': '00000/00000/00000/11111/00000/00000/00000',
    '+': '00000/00100/00100/11111/00100/00100/00000', '/': '00001/00001/00010/00100/01000/10000/10000',
    '%': '11001/11010/00010/00100/01000/01011/10011', "'": '00100/00100/01000/00000/00000/00000/00000',
    '(': '00010/00100/01000/01000/01000/00100/00010', ')': '01000/00100/00010/00010/00010/00100/01000',
    '<': '00010/00100/01000/10000/01000/00100/00010', '>': '01000/00100/00010/00001/00010/00100/01000',
    '#': '01010/01010/11111/01010/11111/01010/01010', '*': '00000/10101/01110/11111/01110/10101/00000',
    '=': '00000/00000/11111/00000/11111/00000/00000', '_': '00000/00000/00000/00000/00000/00000/11111',
    '"': '01010/01010/01010/00000/00000/00000/00000', ';': '00000/01100/01100/00000/01100/00100/01000',
    '&': '01100/10010/10100/01000/10101/10010/01101',
    ' ': '00000/00000/00000/00000/00000/00000/00000'
  };
  const GLY = {}; for (const k in F) GLY[k] = F[k].split('/');
  const atlasCache = {};
  const ORDER = Object.keys(GLY);
  const IDX = {}; ORDER.forEach((k, i) => IDX[k] = i);
  function atlas(color) {
    let a = atlasCache[color]; if (a) return a;
    a = mk(ORDER.length * 6, 7); const x = a.getContext('2d'); x.fillStyle = color;
    ORDER.forEach((k, i) => { const g = GLY[k]; for (let r = 0; r < 7; r++) for (let c = 0; c < 5; c++) if (g[r][c] === '1') x.fillRect(i * 6 + c, r, 1, 1); });
    return atlasCache[color] = a;
  }
  // draw text; align: 0 left, 0.5 center, 1 right; returns width
  function text(ctx, str, x, y, color, opt) {
    opt = opt || {}; const s = opt.scale || 1; str = String(str).toUpperCase();
    const w = str.length * 6 * s - s; x = Math.round(x - w * (opt.align || 0)); y = Math.round(y);
    const pass = (col, ox, oy) => {
      const a = atlas(col);
      for (let i = 0; i < str.length; i++) {
        const gi = IDX[str[i]]; if (gi === undefined || str[i] === ' ') continue;
        ctx.drawImage(a, gi * 6, 0, 5, 7, x + i * 6 * s + ox, y + oy, 5 * s, 7 * s);
      }
    };
    if (opt.shadow !== false) pass(opt.shadowColor || '#1a1423', s, s);
    pass(color || '#fff', 0, 0);
    return w;
  }
  HW.text = text;
  HW.textW = (str, s) => String(str).length * 6 * (s || 1) - (s || 1);
  // Single centred glyph with a dark outline (used for the names written on the worms' bodies).
  // The outlined glyphs are pre-baked per colour into 8x9 cells so each letter is one drawImage.
  const OUTL = [[-1, 0], [1, 0], [0, -1], [0, 1], [1, 1]];
  const glyphCache = {};
  function glyphAtlas(color) {
    let a = glyphCache[color]; if (a) return a;
    a = mk(ORDER.length * 8, 9); const x = a.getContext('2d');
    ORDER.forEach((k, i) => {
      const g = GLY[k], put = (ox, oy) => { for (let r = 0; r < 7; r++) for (let c = 0; c < 5; c++) if (g[r][c] === '1') x.fillRect(i * 8 + 1 + c + ox, 1 + r + oy, 1, 1); };
      x.fillStyle = '#1a1423'; for (const o of OUTL) put(o[0], o[1]);
      x.fillStyle = color; put(0, 0);
    });
    return glyphCache[color] = a;
  }
  HW.glyph = function (ctx, ch, x, y, color) {
    const gi = IDX[ch]; if (gi === undefined) return;
    ctx.drawImage(glyphAtlas(color || '#fff'), gi * 8, 0, 8, 9, x - 3, y - 4, 8, 9);
  };

  // ---------- food (v = value: 1 snack, 2 meal, 3 feast; sim.js picks sprites by v) ----------
  const FOOD = [
    { n: 'burger', v: 3, s: [
      '...kkkkkk...',
      '.kkooeoookk.',
      'kooooooeoook',
      'koeooooooOOk',
      'kglgglgglglk',
      'kyyyyyyyyyyk',
      'kbbybbbbybbk',
      'koooooooooOk',
      '.kOOOOOOOOk.',
      '..kkkkkkkk..'] },
    { n: 'pizza', v: 3, s: [
      '.kkkkkkkkk.',
      'kTTttttttdk',
      'kkyyrryyykk',
      '.kyyrrygyk.',
      '.kkyyyyrkk.',
      '..kyhyrrk..',
      '..kkyyrkk..',
      '...kygyk...',
      '...kkykk...',
      '....kkk....'] },
    { n: 'taco', v: 2, s: [
      '....kkkk....',
      '..kkgrlgkk..',
      '.kgrhyyyglk.',
      'kglhyyyyyyrk',
      'kryyoyyyoygk',
      'kyyyyyyyyyyk',
      'kyyoyyyyoyOk',
      '.kOOOOOOOOk.',
      '..kkkkkkkk..'] },
    { n: 'fries', v: 1, s: [
      '..k..kk..',
      '.kykkyhk.',
      'kyyoyyhyk',
      'kyyoyyhyk',
      'kryoyyhrk',
      'krrrrrrRk',
      'krrwwrrRk',
      '.krrrrRk.',
      '.krrrrRk.',
      '..kkkkk..'] },
    { n: 'soda', v: 2, s: [
      '.....kkk.',
      '....kwwk.',
      '....krkk.',
      '.kkkkwkk.',
      'kwwwwwwak',
      '.krvrrRk.',
      '.kwwwwwk.',
      '.krvrrRk.',
      '.krrrrRk.',
      '..kkkkk..'] },
    { n: 'chips', v: 1, s: [
      '.kkkkkkk.',
      '.kiCiCik.',
      'kicccccCk',
      'kicyyycCk',
      'kcyohoyCk',
      'kcyohoyCk',
      'kccyyycCk',
      'kcccccCCk',
      '.kiCiCik.',
      '.kkkkkkk.'] },
    { n: 'candy', v: 1, s: [
      '.....kkk.....',
      'kk..kpwpk..kk',
      'kpkkpwpppkkpk',
      'kppkwpppxkppk',
      'kpkkpppxpkkpk',
      'kk..kpxpk..kk',
      '.....kkk.....'] },
    { n: 'donut', v: 2, s: [
      '...kkkk...',
      '.kkppppkk.',
      '.kpwppcpk.',
      'kppppppypk',
      'kpypkkpppk',
      'kpppkkpwpk',
      'kpcppppppk',
      '.ktppppdk.',
      '.kkttddkk.',
      '...kkkk...'] },
    { n: 'hotdog', v: 2, s: [
      '...kkkkkkk...',
      '.kkTTttttdkk.',
      'krryyrryyrrrk',
      'kRrrryyrryyRk',
      '.kkttttttdkk.',
      '..kdddddddk..',
      '...kkkkkkk...'] },
    { n: 'icecream', v: 2, s: [
      '...kkk...',
      '.kkpppkk.',
      'kpwwppppk',
      'kpwppppxk',
      'kpppppxxk',
      'kktdtdtkk',
      '.kdtdtdk.',
      '..ktdtk..',
      '..kdtdk..',
      '...ktk...',
      '....k....'] },
    { n: 'cookie', v: 1, s: [
      '..kkkkk..',
      '.kttTttk.',
      'ktBttttBk',
      'kttttBttk',
      'kTtBttttk',
      'ktttttBdk',
      'ktBtttddk',
      '.ktttddk.',
      '..kkkkk..'] },
    { n: 'choc', v: 1, s: [
      'kkkkkkkkk',
      'kdbbkdbbk',
      'kbbBkbbBk',
      'kkkkkkkkk',
      'kdbbkdbbk',
      'kbbBkbbBk',
      'kawawawak',
      'kPPPPPPMk',
      'kPyyyyyMk',
      'kPPPPPMMk',
      'kkkkkkkkk'] },
    { n: 'lolly', v: 1, s: [
      '...kkk...',
      '..krrrk..',
      '.krwwwwk.',
      'krwrrrrrk',
      'krwrwrwrk',
      'krrrrrwrk',
      '.kwwwwrk.',
      '..krrrk..',
      '...kwk...',
      '...kwk...',
      '...kak...',
      '...kkk...'] },
    { n: 'cupcake', v: 2, s: [
      '....k....',
      '...krk...',
      '..kwwik..',
      '.kwwiiwk.',
      'kwiiwwiik',
      'kkpxpxpkk',
      '.kpxpxpk.',
      '..kxpxk..',
      '..kkkkk..'] },
    { n: 'popcorn', v: 1, s: [
      '..kk.kkk.',
      '.kwekwwhk',
      'kwhwwewwk',
      'kewwhwwek',
      'krwrwrwrk',
      'krwrwrwrk',
      '.kwrwrwk.',
      '.kwrwrwk.',
      '..kkkkk..'] },
    { n: 'drumstick', v: 2, s: [
      '..kkkk.....',
      '.kotook....',
      'kotooook.kk',
      'koooooOkkwk',
      'kooooOOwwwk',
      'koooOOOkkwk',
      '.kOOOOk..kk',
      '..kkkk.....'] }
  ];
  HW.FOOD = FOOD;
  HW.foodSpr = FOOD.map(f => sprite(f.s));
  HW.foodSpr2 = HW.foodSpr.map(c => { const d = mk(c.width * 2, c.height * 2), x = d.getContext('2d'); x.imageSmoothingEnabled = false; x.drawImage(c, 0, 0, d.width, d.height); return d; });

  // ---------- veggies (slow you down): broccoli, carrot, salad bowl, green apple, celery ----------
  // Every veggie gets a faint sickly-green halo so "healthy = avoid" reads at a glance next to the junk food.
  function halo(c, color, alpha) {
    const w = c.width, h = c.height, s = mk(w, h), sx = s.getContext('2d');
    sx.drawImage(c, 0, 0); sx.globalCompositeOperation = 'source-in'; sx.fillStyle = color; sx.fillRect(0, 0, w, h);
    const r = mk(w + 2, h + 2), rx = r.getContext('2d');
    for (let j = 0; j <= 2; j++) for (let i = 0; i <= 2; i++) if (i !== 1 || j !== 1) rx.drawImage(s, i, j);
    const d = mk(w + 2, h + 2), x = d.getContext('2d');
    x.globalAlpha = alpha; x.drawImage(r, 0, 0); x.globalAlpha = 1; x.drawImage(c, 1, 1);
    return d;
  }
  HW.vegSpr = [
    sprite([
      '.....kkk.....',
      '.kkkkuggkkkk.',
      'kuugGgggGuggk',
      'kugggGgGggggk',
      'kggGggggggGGk',
      'kgGGgggGgGGGk',
      '.kkGGGGGGGkk.',
      '...kkullkk...',
      '....kulnk....',
      '....kulnk....',
      '....kkkkk....']),
    sprite([
      '.kk.kkk.kk.',
      'kgukgugkguk',
      'kggkgggkggk',
      '.kgggggggk.',
      '..kkkgkkk..',
      '.kohooooOk.',
      '.koooOOoOk.',
      '..kohooOk..',
      '..koOOoOk..',
      '...koOOk...',
      '....kOk....',
      '.....k.....']),
    sprite([
      '...kkkkkkk...',
      '.kkuglgrgukk.',
      'kglgugGgrlgGk',
      'kwwwwwwwwwwwk',
      '.kwwwwwwwwak.',
      '.kawwwwwwaak.',
      '..kkaaaaakk..',
      '....kkkkk....']),
    sprite([
      '......kkk..',
      '....kbkugk.',
      '.kkkkbkkkk.',
      'kguugkgggGk',
      'kguwgggggGk',
      'kguggggggGk',
      'kggggggggGk',
      'kgggggggGGk',
      '.kgggggGGk.',
      '.kkgGkGGkk.',
      '...kk.kk...']),
    sprite([
      '.kk.k.kk.',
      'kgukgkugk',
      'kggkgkggk',
      '.kgkgkgk.',
      '.kuGlGlk.',
      '.kuGlGlk.',
      '.kuGlGlk.',
      '.kuGlGlk.',
      '.kuGlGnk.',
      '.kuGlGnk.',
      '.keeeeek.',
      '.kkkkkkk.'])
  ].map(c => halo(c, '#9dff3c', 0.4));

  // ---------- magic mushrooms (trippy screen) ----------
  const SHROOM = [
    '....kkkkk....',
    '..kkmmwcmkk..',
    '.kmmmmccmmmk.',
    'kmwcmmmmmwcmk',
    'kmccmmmmmccmk',
    'kMmmmwccmmmMk',
    'kkyMyMyMyMykk',
    '..kkeeeeekk..',
    '...kekekek...',
    '...keeeeek...',
    '....kkkkk....'];
  HW.shroomSpr = [
    sprite(SHROOM),
    sprite(SHROOM, { m: PAL.P, M: '#5b2f9e', c: PAL.l, y: PAL.p })
  ];

  // double-size versions: veggies and mushrooms are always drawn big, food when it is worth a proper bite
  const twice = c => { const d = mk(c.width * 2, c.height * 2), x = d.getContext('2d'); x.imageSmoothingEnabled = false; x.drawImage(c, 0, 0, d.width, d.height); return d; };
  HW.vegSpr2 = HW.vegSpr.map(twice); HW.shroomSpr2 = HW.shroomSpr.map(twice);

  // ---------- ammo crate ----------
  HW.ammoSpr = sprite([
    '.kkkkkkkkkk.',
    'kynnnnnnnnyk',
    'knnnnnnnnnnk',
    'kNNNNyyNNNNk',
    'kNoONoONoONk',
    'kNhyNhyNhyNk',
    'kNhyNhyNhyNk',
    'kNOONOONOONk',
    'kynnnnnnnnyk',
    '.kkkkkkkkkk.']);

  // crown for the biggest worm (drawn with its left edge 4 px left of the head centre)
  HW.crownSpr = sprite([
    '.k..k..k.',
    'khkkhkkhk',
    'kyyyyyyyk',
    'kyrycyryk',
    'kooooooOk',
    '.kkkkkkk.']);

  // ---------- guns (pointing right; px/py = grip pivot; len = muzzle distance from pivot) ----------
  HW.gunSpr = [
    // Ben - Burger Cannon: chunky hand cannon with a burger-stack drum and a fat muzzle ring
    { c: sprite([
      '....kkk....kkk.',
      '.kkkoookkkkaask',
      'kaakgggkaaqasSk',
      'ksskbbbkssqasSk',
      'kSSkyyykSSqsSSk',
      'kbbkoookkkkSSSk',
      'kbBkkkk....kkk.',
      'kbBk...........',
      'kkkk...........']), px: 3, py: 4, len: 11 },
    // Chandler - Soda Scattergun: two side-by-side barrels, a cola can for a receiver, stubby wooden stock
    { c: sprite([
      '....kkkkkkkkkkkkk',
      '.kkkkvvvaaaaaaaqk',
      'kbbbkrwrsssssssqk',
      'kbddkrwrkkkkkkkkk',
      'kbbbkrwraaaaaaaqk',
      '.kkkkRRRsssssssqk',
      '....kkkkkkkkkkkkk']), px: 4, py: 3, len: 12 },
    // Nate - Gumball SMG: small boxy SMG with a gumball hopper on top and a stick magazine
    { c: sprite([
      '...kkkk.....',
      '..kpwyok....',
      '.kkyolpkkkk.',
      'kicccccccask',
      'kcCCCCCCCkkk',
      'kkcCkksSkk..',
      '.kkkkksSk...',
      '.....kkkk...']), px: 3, py: 4, len: 9 },
    // Wesley - kebab crossbow seen from above: swept-back limbs, drawn string, a loaded skewer
    { c: sprite([
      '.........k....',
      '........kdk...',
      '........adkk..',
      '.......a.kdk..',
      '.kkkkkakkkdk..',
      'kBbbbstrgtdttw',
      '.kkkkkakkkdk..',
      '.......a.kdk..',
      '........adkk..',
      '........kdk...',
      '.........k....']), px: 3, py: 5, len: 11 },
    // Jeff - rocket launcher: long tube, flared exhaust, sight, two grips, red warhead poking out
    { c: sprite([
      'kkk.......k........',
      'kgGkkkkkkkskkkkkk..',
      'kgGgNgggggggygNark.',
      'kGGGNGGGGGGGyGNsrrk',
      'kGJJNJJJJJJJoJNSRk.',
      'kGJkkkbBkkkbBkkkk..',
      'kkk..kbBk.kbBk.....',
      '......kk...kk......']), px: 7, py: 4, len: 12 }
  ];
  // projectiles (pointing right). Rocket is drawn with its centre at (6,2), skewer at (9,1).
  HW.rocketSpr = sprite([
    '..kkkkkk..',
    'oykrwwwrk.',
    'yhkSaaarrk',
    'oykrsssRk.',
    '..kkkkkk..']);
  HW.skewerSpr = sprite([
    '..bb.gg.rr....',
    'ttbdtgutrvttaw',
    '..BB.GG.RR....']);
  // hats: 11 px wide, drawn with the left edge 5 px left of the head centre
  HW.hatSpr = {
    ben: sprite([
      '..kkkkk....',
      '.kvrrrrk...',
      'kvrwwrrRkkk',
      'krrrrrrrRRk',
      'kkkkkkkkkkk']),
    jeff: sprite([
      '...kkkkk...',
      '..kgGGGGk..',
      '.kgGGJGGGk.',
      'kGGJGGGGJGk',
      'kkkkkkkkkkk']),
    wes: sprite([
      '..yyykccc..',
      '....kkk....',
      '...kryck...',
      '..krrycck..',
      '..kkkkkkk..']),
    wes2: sprite([
      '...cckyy...',
      '....kkk....',
      '...kryck...',
      '..krrycck..',
      '..kkkkkkk..'])
  };

  // ---------- worm segment circles ----------
  function shade(hex, f) {
    const n = parseInt(hex.slice(1), 16); let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    if (f < 0) { r *= 1 + f; g *= 1 + f; b *= 1 + f; } else { r += (255 - r) * f; g += (255 - g) * f; b += (255 - b) * f; }
    return 'rgb(' + (r | 0) + ',' + (g | 0) + ',' + (b | 0) + ')';
  }
  HW.shade = shade;
  const segCache = {};
  HW.seg = function (color, r) {
    const key = color + r; let c = segCache[key]; if (c) return c;
    const R = r + 1, d = R * 2 + 1; c = mk(d, d); const x = c.getContext('2d');
    const out = shade(color, -0.62), hi = shade(color, 0.35), lo = shade(color, -0.25);
    for (let j = -R; j <= R; j++) for (let i = -R; i <= R; i++) {
      const q = i * i + j * j;
      if (q > R * R + R * 0.6) continue;
      let col = color;
      if (q > r * r - r * 0.4) col = out;
      else if ((i + r * 0.35) * (i + r * 0.35) + (j + r * 0.35) * (j + r * 0.35) < r * r * 0.16) col = hi;
      else if ((i - r * 0.3) * (i - r * 0.3) + (j - r * 0.3) * (j - r * 0.3) > r * r * 0.75) col = lo;
      x.fillStyle = col; x.fillRect(i + R, j + R, 1, 1);
    }
    return segCache[key] = c;
  };

  // floor tile (diner checker, kept dark so food pops)
  HW.floorTile = (function () {
    const c = mk(64, 64), x = c.getContext('2d');
    const cols = ['#2a2440', '#262038'];
    for (let j = 0; j < 2; j++) for (let i = 0; i < 2; i++) {
      x.fillStyle = cols[(i + j) & 1]; x.fillRect(i * 32, j * 32, 32, 32);
      x.fillStyle = 'rgba(255,255,255,0.035)'; x.fillRect(i * 32, j * 32, 32, 1); x.fillRect(i * 32, j * 32, 1, 32);
      x.fillStyle = 'rgba(0,0,0,0.18)'; x.fillRect(i * 32, j * 32 + 31, 32, 1); x.fillRect(i * 32 + 31, j * 32, 1, 32);
    }
    let s = 7; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 26; i++) { x.fillStyle = rnd() < 0.5 ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.12)'; x.fillRect((rnd() * 64) | 0, (rnd() * 64) | 0, 1, 1); }
    return c;
  })();

  // floor tiles for the themed corners of the arena (index = MAP zone). All dark, so food still pops.
  HW.zoneTiles = (function () {
    let s = 11; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const tile = f => { const c = mk(64, 64); f(c.getContext('2d')); return c; };
    const specks = (x, n, a, b) => { for (let i = 0; i < n; i++) { x.fillStyle = rnd() < 0.5 ? a : b; x.fillRect((rnd() * 64) | 0, (rnd() * 64) | 0, 1, 1); } };
    return [
      // 0 kitchen: small steel-blue tiles
      tile(x => {
        for (let j = 0; j < 4; j++) for (let i = 0; i < 4; i++) { x.fillStyle = ['#1f2a3c', '#22304a', '#1d2838'][(i * 3 + j * 5) % 3]; x.fillRect(i * 16, j * 16, 16, 16); x.fillStyle = 'rgba(0,0,0,0.25)'; x.fillRect(i * 16 + 15, j * 16, 1, 16); x.fillRect(i * 16, j * 16 + 15, 16, 1); x.fillStyle = 'rgba(160,200,255,0.05)'; x.fillRect(i * 16, j * 16, 15, 1); }
        specks(x, 14, 'rgba(160,200,255,0.07)', 'rgba(0,0,0,0.15)');
      }),
      // 1 candy shop: purple and plum diagonal stripes
      tile(x => {
        x.fillStyle = '#2c1c40'; x.fillRect(0, 0, 64, 64); x.fillStyle = '#391f48';
        for (let j = 0; j < 64; j++) for (let i = 0; i < 64; i++) if (((i + j) >> 3) & 1) x.fillRect(i, j, 1, 1);
        x.fillStyle = 'rgba(255,126,182,0.10)'; for (let j = 0; j < 4; j++) for (let i = 0; i < 4; i++) x.fillRect(i * 16 + ((j & 1) ? 12 : 4), j * 16 + 6, 2, 2);
      }),
      // 2 salad bar: sickly green checker with leaf specks
      tile(x => {
        for (let j = 0; j < 2; j++) for (let i = 0; i < 2; i++) { x.fillStyle = (i + j) & 1 ? '#1b3024' : '#20382a'; x.fillRect(i * 32, j * 32, 32, 32); x.fillStyle = 'rgba(0,0,0,0.2)'; x.fillRect(i * 32 + 31, j * 32, 1, 32); x.fillRect(i * 32, j * 32 + 31, 32, 1); }
        specks(x, 22, 'rgba(140,220,110,0.10)', 'rgba(0,0,0,0.15)');
      }),
      // 3 grease pit: brown planks with stains
      tile(x => {
        for (let j = 0; j < 4; j++) {
          x.fillStyle = ['#32241a', '#2c1f17', '#35271c', '#2a1e16'][j]; x.fillRect(0, j * 16, 64, 16); x.fillStyle = 'rgba(0,0,0,0.3)'; x.fillRect(0, j * 16 + 15, 64, 1);
          x.fillRect((j * 23 + 9) % 64, j * 16, 1, 16); x.fillStyle = 'rgba(255,190,120,0.05)'; x.fillRect(0, j * 16, 64, 1);
        }
        specks(x, 18, 'rgba(255,170,80,0.08)', 'rgba(0,0,0,0.2)');
      }),
      // 4 food court: dim red and plum checker
      tile(x => {
        for (let j = 0; j < 2; j++) for (let i = 0; i < 2; i++) { x.fillStyle = (i + j) & 1 ? '#3a1f2a' : '#2a1d30'; x.fillRect(i * 32, j * 32, 32, 32); x.fillStyle = 'rgba(255,255,255,0.04)'; x.fillRect(i * 32, j * 32, 32, 1); x.fillRect(i * 32, j * 32, 1, 32); }
        specks(x, 16, 'rgba(255,140,140,0.07)', 'rgba(0,0,0,0.15)');
      })
    ];
  })();
})(window.HW);
