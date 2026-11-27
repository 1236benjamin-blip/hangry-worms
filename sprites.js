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

  // ---------- worm skins ----------
  // A worm is a chain of discs 6 px apart, drawn tail to head, so all that ever shows of a body disc is a
  // crescent on its tail side. A design therefore cannot live on one disc; it is painted on the whole body
  // as a tube. body(a, b) returns a palette index for the point a radii behind the head (the design repeats
  // every 6 radii, so it grows with the worm) and b across the body (-1 left edge .. 1 right edge).
  // head(x, y) does the same for the head disc (x forward, y across, in radii). tail: palette index for
  // each of the 4 tapering tail discs, tip first. glow: palette index of the pulses that run down a boosting worm.
  // Every variant is its own palette for the same design. pals[v][0] is the worm's identity colour (minimap,
  // leaderboard, death burst): test/skins.py checks that all 20 stay far apart.
  const fr = x => x - Math.floor(x);
  const tri = x => Math.abs(fr(x) * 2 - 1) * 2 - 1;                                  // triangle wave -1..1, period 1
  const hash = (i, j, s) => fr(Math.sin(i * 127.1 + j * 311.7 + s * 74.7) * 43758.5453);
  // smooth blobby noise that repeats every `per` cells along x, so camouflage joins up with itself
  function noise(x, y, s, per) {
    const xi = Math.floor(x), yi = Math.floor(y), tx = x - xi, ty = y - yi, sx = tx * tx * (3 - 2 * tx), sy = ty * ty * (3 - 2 * ty);
    const h = (i, j) => hash(((i % per) + per) % per, j, s), a = h(xi, yi), b = h(xi + 1, yi), c = h(xi, yi + 1), d = h(xi + 1, yi + 1);
    return a + (b - a) * sx + (c + (d - c) * sx - a - (b - a) * sx) * sy;
  }
  // small marks scattered at fixed spots: [a, b, palette index, half length, half width, direction 0 along / 1 across / 2 diagonal]
  function marks(list, a, b, per) {
    for (let n = 0; n < list.length; n++) {
      const m = list[n]; let da = a - m[0]; if (per) { if (da > per / 2) da -= per; else if (da < -per / 2) da += per; } const db = b - m[1];
      if (m[5] === 2) { if (Math.abs(da - db) < m[4] * 1.4 && Math.abs(da + db) < m[3] * 1.4) return m[2]; }
      else if (Math.abs(da) < (m[5] ? m[4] : m[3]) && Math.abs(db) < (m[5] ? m[3] : m[4])) return m[2];
    }
    return -1;
  }
  const SEEDS = [[0.3, -0.5], [0.72, 0.28], [1.2, -0.22], [0.5, 0.72], [1.3, 0.62], [0.95, -0.74], [0.32, 0.08]].map(s => [s[0], s[1], 5, 0.13, 0.08, 2]);
  const HSEEDS = [[-0.55, -0.3], [-0.5, 0.35], [-0.12, 0.02], [-0.85, 0.02], [-0.15, -0.72], [-0.1, 0.74]].map(s => [s[0], s[1], 5, 0.12, 0.08, 2]);
  const SPRINK = [[0.3, -0.2, 3, 2], [0.75, 0.25, 4, 0], [1.2, -0.3, 5, 1], [1.7, 0.1, 6, 2], [2.2, -0.12, 7, 0], [2.6, 0.3, 3, 1], [3.1, -0.28, 4, 2], [3.6, 0.15, 5, 0],
    [4.1, -0.2, 6, 1], [4.55, 0.28, 7, 2], [5.0, -0.1, 3, 0], [5.5, 0.22, 4, 1], [5.8, -0.34, 5, 2]].map(s => [s[0], s[1], s[2], 0.17, 0.075, s[3]]);
  const HSPRINK = [[-0.5, -0.3, 3, 2], [-0.45, 0.3, 4, 0], [-0.05, 0, 5, 1], [0.5, -0.05, 7, 0], [-0.8, 0, 6, 1]].map(s => [s[0], s[1], s[2], 0.17, 0.08, s[3]]);
  const BUBBLES = [[0.08, -0.62, 0.21], [0.83, 0.6, 0.13], [1.58, -0.58, 0.17], [3.08, -0.64, 0.13], [3.83, 0.62, 0.22], [4.58, -0.6, 0.12], [5.33, 0.6, 0.17]];
  const DRIP = [1, 0.5, 0.85, 0.65];
  const SKINS = HW.SKINS = [
    { // BEN: a stack of cheeseburgers. bun, lettuce frill, tomato, cheese with drips, grilled patty, bun again
      // palette: 0 bun, 1 cheese, 2 lettuce, 3 tomato, 4 patty, 5 sesame seed, 6 grill marks, 7 bottom bun, 8 gap between burgers
      pals: [
        ['#f0911f', '#ffd23f', '#6fd03f', '#e23a2e', '#8a4b25', '#ffe9b0', '#5a2e14', '#d6781a', '#8f4a12'],   // classic
        ['#e2362c', '#ffb01f', '#b5e61d', '#ffe45c', '#4f3540', '#ffb9a0', '#ff6a1c', '#b9241f', '#6e1014'],   // inferno: chili bun, charred patty that still glows
        ['#e9e6f2', '#8fe3ff', '#b98cf0', '#ff7eb6', '#6d7190', '#9aa0b8', '#4a4e6c', '#c9c5da', '#8683a0'],   // ghost burger
        ['#a05a2c', '#f2c230', '#a9c93e', '#e8665e', '#5f3018', '#ffffff', '#3a1c0c', '#864820', '#55290f']    // pretzel bun with salt, mustard, pickles, bacon
      ],
      glow: 1, tail: [8, 7, 7, 0],
      body(a, b) {
        if (a < 1.7 || a >= 5.05) {
          if (a < 0.13 || a > 5.9) return 8;
          if (a >= 5.05) return 7;
          const m = marks(SEEDS, a, b); return m < 0 ? 0 : m;
        }
        if (a < 2.3 + Math.sin(b * 8) * 0.17) return 2;
        if (a < 2.85) return 3;
        if (a < 3.35 + Math.max(0, 0.55 - Math.abs(fr(b * 1.1) - 0.5) * 2.4)) return 1;
        if (a < 4.85) return fr((a + b * 0.7) * 1.3) < 0.17 ? 6 : 4;
        return 2;
      },
      head(x, y) { const m = marks(HSEEDS, x, y); return m < 0 ? 0 : m; }
    },
    { // CHANDLER: a fizzy drink can. a jagged bolt down the back, bubbles rising along the flanks, chrome lid for a head
      // palette: 0 can, 1 bolt, 2 flank, 3 bolt edge, 4 bubble, 5 chrome, 6 chrome shade
      pals: [
        ['#2b6fd6', '#ffffff', '#1d51ad', '#143a82', '#a5e0ff', '#dfe3ea', '#8d99ae'],   // blue cola
        ['#0e9494', '#f6ff7a', '#0a7272', '#064d50', '#a9ffee', '#dfe3ea', '#8d99ae'],   // mint fizz
        ['#d1245e', '#ffffff', '#a3174a', '#6e0e33', '#ffb0cc', '#dfe3ea', '#8d99ae'],   // cherry
        ['#c7b0ff', '#fff27a', '#9d84e0', '#5f48a8', '#ffffff', '#dfe3ea', '#8d99ae']    // grape
      ],
      glow: 1, tail: [6, 5, 5, 2],
      body(a, b) {
        const dz = Math.abs(b - tri(a / 1.5) * 0.42);
        if (dz < 0.19) return 1;
        if (dz < 0.3) return 3;
        for (let n = 0; n < BUBBLES.length; n++) {
          const m = BUBBLES[n]; let da = a - m[0]; if (da > 3) da -= 6; const q = da * da + (b - m[1]) * (b - m[1]);
          if (q < m[2] * m[2]) return m[2] > 0.16 && q < m[2] * m[2] * 0.2 ? 0 : 4;
        }
        return Math.abs(b) > 0.74 ? 2 : 0;
      },
      head(x, y) { const q = x * x + y * y; return q > 0.6 ? 5 : q > 0.42 ? 6 : 0; }
    },
    { // NATE: ninja tiger. slashes cut in from alternate sides, swept back so he looks fast standing still
      // palette: 0 fur, 1 stripe, 2 pale edge
      pals: [
        ['#7ed321', '#1f4a1c', '#d2f77a'],   // toxic
        ['#f5d547', '#3a2616', '#fff6b8'],   // classic
        ['#ff8fd0', '#6a2390', '#ffd3ee'],   // bubblegum
        ['#7ae8f0', '#1d3f8a', '#e3fdff']    // ice
      ],
      band: [['#e03c32', '#9c2020'], ['#e03c32', '#9c2020'], ['#3b1d63', '#241040'], ['#e03c32', '#9c2020']],   // his headband (render.js); red clashes with pink
      glow: 2, tail: [1, 0, 1, 0],
      body(a, b) {
        let pale = false;
        for (let s = -1; s <= 1; s += 2) {
          const e = s * b + 0.2; if (e <= 0) continue;
          const c = (s < 0 ? 0 : 0.75) + (1.2 - e) * 0.5, d = (fr((a - c) / 1.5 + 0.5) - 0.5) * 1.5, hw = 0.31 * Math.min(1, e) - 0.02;
          if (d > -hw && d < hw) return 1;
          if (d >= hw && d < hw + 0.13 && e > 0.45) pale = true;   // a glint along the back edge of each slash
        }
        return pale ? 2 : 0;
      },
      head(x, y) {
        const ay = Math.abs(y);
        if (x < -0.2 && ay < 0.04 + (-0.2 - x) * 0.2) return 1;
        if (ay > 0.3 && Math.abs(x + 0.35 + (1 - ay) * 0.45) < 0.26 * (ay - 0.3)) return 1;
        return 0;
      }
    },
    { // WESLEY: a frosted donut. icing over his back that drips down the dough, covered in sprinkles
      // palette: 0 icing, 1 dough, 2 icing shine, 3..7 sprinkles, 8 dough crust
      pals: [
        ['#9b5de5', '#e8b574', '#c79bff', '#ffd23f', '#ff7eb6', '#4cc9f0', '#ffffff', '#b5e61d', '#b07a3c'],   // grape glaze
        ['#6fc0ff', '#7a4a2a', '#c4e6ff', '#ffffff', '#ff7eb6', '#ffd23f', '#1d51ad', '#b5e61d', '#55301a'],   // blueberry on chocolate
        ['#f032c8', '#f6d9a0', '#ff8ae2', '#ffffff', '#ffd23f', '#4cc9f0', '#b5e61d', '#7a1466', '#c9a060'],   // raspberry
        ['#fff0a8', '#8a4b25', '#ffffff', '#e23a2e', '#4cc9f0', '#ff7eb6', '#5cc04a', '#9b5de5', '#5a2e14']    // custard on chocolate
      ],
      glow: 2, tail: [8, 1, 1, 1],
      body(a, b) {
        const ab = Math.abs(b), q = a / 1.5 + (b < 0 ? 0 : 0.5), lobe = Math.max(0, Math.cos(q * 6.2832));
        if (ab > 0.46 + 0.5 * DRIP[Math.floor(q + 0.5) % 4] * Math.sqrt(lobe)) return ab > 0.93 ? 8 : 1;
        const m = marks(SPRINK, a, b, 6); if (m >= 0) return m;
        return Math.abs(b + 0.42) < 0.07 && fr(a / 1.5) < 0.55 ? 2 : 0;
      },
      head(x, y) {
        if (x * x + y * y > 0.74) return 1;
        const m = marks(HSPRINK, x, y); return m < 0 ? 0 : m;
      }
    },
    { // JEFF: camouflage, to go with the helmet. four tones of blobs and a few dark flecks
      // palette: 0 base, 1 shade, 2 second colour, 3 pale, 4 fleck
      pals: [
        ['#6f8a3a', '#3f5a26', '#8a5a30', '#a8b866', '#26321a'],   // woodland
        ['#c49a62', '#96703e', '#7a5a3a', '#e8cf9a', '#5a4028'],   // desert
        ['#8497a8', '#566878', '#3e4a5a', '#d5e2ec', '#2a323e'],   // arctic
        ['#96609a', '#74488a', '#54346e', '#c890c0', '#ff9ad0']    // night ops (the flecks glow)
      ],
      glow: 3, tail: [1, 0, 2, 0],
      body(a, b) {
        const n1 = noise(a / 0.75, b / 0.7 + 3, 1, 8), n2 = noise(a / 0.6 + 0.3, b / 0.6 + 7, 2, 10);
        if (n2 > 0.7) return 2;
        if (n2 < 0.13) return 4;
        return n1 > 0.6 ? 1 : n1 < 0.32 ? 3 : 0;
      },
      head(x, y) { return SKINS[4].body(x + 2.2, y); }
    }
  ];
  SKINS.forEach(s => { s.colors = s.pals.map(p => [p[0], p[1]]); });

  // Baking. A body disc is one small canvas per skin, body radius, step of the design (r steps, since the design
  // is 6r px long and discs are 6 px apart) and direction the body runs in (16 of them); step r is the head.
  // Each is painted the first time it is drawn, so a worm reaching a new size never costs a hitch. They are
  // separate images, not cells of one sheet, because Chrome's software canvas is over twice as slow at
  // drawImage when the source rectangle keeps changing (measured; test/skins.py holds the cost to the old flat discs).
  // tone of a pixel: 0 flat, 1 lit, 2 shaded, 3 outline, 4 the faint rib between two segments
  const TONES = [0, 0.3, -0.25, -0.62, -0.17];
  function pack(hex, f) {
    const n = parseInt(hex.slice(1), 16); let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    if (f < 0) { r *= 1 + f; g *= 1 + f; b *= 1 + f; } else { r += (255 - r) * f; g += (255 - g) * f; b += (255 - b) * f; }
    return (0xff000000 | (b | 0) << 16 | (g | 0) << 8 | (r | 0)) >>> 0;   // ImageData byte order (little endian)
  }
  const made = [], sets = [], scratch = {}, glints = {};
  let clock = 0, live = 0, tails = 0;
  // Cap on body discs kept. 12 worms of the biggest size coiled through every direction need 12 * 14 * 16 = 2688;
  // past the cap, the skin and size drawn longest ago is dropped whole (and simply repainted if it comes back).
  HW.SKIN_CELLS = 3600;
  HW.skinStats = () => ({ skins: made.filter(Boolean).length, sets: sets.length, cells: live, max: HW.SKIN_CELLS, tails, glints: Object.keys(glints).length });
  HW.skin = function (ch, v) {
    const id = ch * 4 + (v & 3); let s = made[id]; if (s) return s;
    const D = SKINS[ch], pal = D.pals[v & 3], tone = new Uint32Array(pal.length * 5);
    pal.forEach((h, i) => TONES.forEach((f, j) => { tone[i * 5 + j] = pack(h, f); }));
    return made[id] = { id, def: D, pal, tone, sets: [], tail: [], arm: shade(pal[0], -0.3), glow: pal[D.glow], band: D.band ? D.band[v & 3] : null };
  };
  // the discs of skin s at body radius r: S.cells[step * 16 + direction] is a canvas, or empty until HW.skinBake paints it
  HW.skinSet = function (s, r) {
    let S = s.sets[r]; if (!S) { S = s.sets[r] = { s, r, cells: new Array((r + 1) * 16), n: 0, use: 0 }; sets.push(S); }
    S.use = ++clock; return S;
  };
  function pixels(d) { const s = scratch[d] || (scratch[d] = { im: new ImageData(d, d), px: null }); if (!s.px) s.px = new Uint32Array(s.im.data.buffer); s.px.fill(0); return s; }
  // A painted disc starts life as a small canvas, which can be drawn at once, and is swapped for an ImageBitmap
  // as soon as the browser has made one: drawing from thousands of different canvases costs Chrome about a
  // third more per call than drawing from bitmaps (measured with the CPU throttled 4x), and a bitmap is lighter to keep.
  const bmp = typeof createImageBitmap === 'function';
  function stamp(sc, d, arr, i) {
    const c = arr[i] = mk(d, d); c.getContext('2d').putImageData(sc.im, 0, 0);
    if (bmp) try { createImageBitmap(c).then(b => { if (arr[i] === c) { arr[i] = b; c.width = c.height = 0; } else b.close(); }, () => { }); } catch (e) { }
    return c;
  }
  const drop = c => { if (c.close) c.close(); else c.width = c.height = 0; };
  // ball shading for heads and tail discs: highlight up and to the left, shadow down and to the right
  const ball = (i, j, r, q) => q > r * r - r * 0.4 ? 3 : (i + r * 0.35) * (i + r * 0.35) + (j + r * 0.35) * (j + r * 0.35) < r * r * 0.16 ? 1 : (i - r * 0.3) * (i - r * 0.3) + (j - r * 0.3) * (j - r * 0.3) > r * r * 0.75 ? 2 : 0;
  HW.skinBake = function (S, step, dir) {
    const s = S.s, r = S.r, R = r + 1, d = r * 2 + 3, sc = pixels(d), px = sc.px, tone = s.tone, D = s.def, head = step === r;
    const th = dir * Math.PI / 8, fx = Math.cos(th), fy = Math.sin(th), lit = (fy - fx) * 0.7071;   // how much the body's side faces the light
    const side = r * Math.sin(Math.acos(3 / r) - 0.22);   // further out than this, the rim of a disc can be the edge of the worm (on the outside of a tight bend)
    for (let j = -R; j <= R; j++) for (let i = -R; i <= R; i++) {
      const q = i * i + j * j; if (q > R * R + R * 0.6) continue;
      const u = i * fx + j * fy, v = j * fx - i * fy; let idx, t;
      if (head) { idx = D.head(u / r, v / r); t = ball(i, j, r, q); }
      else {
        let a = ((step * 6 - u) / r) % 6; if (a < 0) a += 6; idx = D.body(a, v / r);
        // The outline only runs along the two sides of the tube. Across the body it would cut the design into
        // coins, so there the rim is just a shade darker: enough to still read as a segmented worm.
        const e = v / r * lit;
        t = q > r * r - r * 0.4 ? (v > side || v < -side ? 3 : 4) : e > 0.55 ? 1 : e < -0.5 ? 2 : 0;
      }
      px[(j + R) * d + i + R] = tone[idx * 5 + t];
    }
    S.n++; live++;
    while (live > HW.SKIN_CELLS && sets.length > 1) {
      let k = -1; for (let i = 0; i < sets.length; i++) if (sets[i] !== S && (k < 0 || sets[i].use < sets[k].use)) k = i;
      const o = sets[k]; sets.splice(k, 1); live -= o.n; o.s.sets[o.r] = null; o.cells.forEach((c, i) => { o.cells[i] = null; drop(c); });
    }
    return stamp(sc, d, S.cells, step * 16 + dir);
  };
  // tail discs: plain balls in the tail's own colours. rr: radius, 3..12; ft: 0 = the tip .. 3. At most 40 small canvases a skin.
  HW.skinTail = function (s, rr, ft) {
    const R = rr + 1, d = rr * 2 + 3, sc = pixels(d), px = sc.px, o = s.def.tail[ft] * 5;
    for (let j = -R; j <= R; j++) for (let i = -R; i <= R; i++) { const q = i * i + j * j; if (q <= R * R + R * 0.6) px[(j + R) * d + i + R] = s.tone[o + ball(i, j, rr, q)]; }
    tails++; return stamp(sc, d, s.tail, rr * 4 + ft);
  };
  // a see-through disc laid over a body segment: the sheen that slides down a worm, and the pulses of a boost
  HW.glint = function (color, r, strong) {
    const k = color + r + (strong ? 's' : ''); let c = glints[k]; if (c) return c;
    const d = r * 2 + 3; c = glints[k] = mk(d, d); const x = c.getContext('2d'); x.globalAlpha = strong ? 0.6 : 0.34; x.fillStyle = color;
    for (let j = -r + 1; j <= r - 1; j++) { const w = Math.floor(Math.sqrt((r - 1) * (r - 1) - j * j)); x.fillRect(r + 1 - w, j + r + 1, w * 2 + 1, 1); }
    return c;
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
