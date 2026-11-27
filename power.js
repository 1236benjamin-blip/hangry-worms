// Hangry Worms - power-ups and special guns: what they do (numbers) and what they look like (sprites).
// The rules that use these live in sim.js; this file only describes them.
'use strict';
(function (HW) {
  const sprite = HW.sprite;

  // ---------- power-ups (item kind 'p', type = index here) ----------
  // rampage: faster, and running into another worm kills THEM instead of you. Shots, farts and puke still work on you.
  // super:   supersize. Bigger body, wins every head-on, takes less damage, eats from further away, keeps a bit of the growth.
  HW.POWERS = [
    { id: 'rampage', name: 'RAMPAGE', t: 9, speed: 1.4, col: '#ffd23f' },
    { id: 'super', name: 'SUPERSIZE', t: 12, scale: 1.5, mass: 20, armor: 0.5, eat: 1.8, col: '#ff5a4d' },
    // guard: a bubble that stops every shot and blast for its duration. Running into worms, farts and puke still get you.
    { id: 'guard', name: 'SHOT SHIELD', t: 10, col: '#4cc9f0' },
    // sauce: boosting costs no mass, is a bit quicker and leaves a trail of fire
    { id: 'sauce', name: 'HOT SAUCE', t: 8, boost: 1.15, col: '#ff7a1c' }
  ];
  // the golden burger: one on the map at a time, worth a feast and a half, shown on every minimap (item kind 'x')
  HW.GOLD = { v: 30, wait: [35, 55] };
  // kill streaks: [kills in a row without dying, callout, bonus points]
  HW.STREAKS = [[2, 'DOUBLE KILL', 10], [3, 'FOOD COMA', 20], [5, 'ALL YOU CAN EAT', 40], [7, 'UNSTOPPABLE GLUTTON', 60]];
  // last minute of a match: pickups and food turn up this much faster. The crowned leader is always worth this many times the kill points.
  HW.FRENZY = { t: 60, rate: 2 }; HW.BOUNTY = 2;
  HW.TAUNTS = ['NOM NOM', 'BURP', 'EAT MY DUST', 'BEN SUCKS', 'TOO SLOW', 'YUM', 'HANGRY!', 'GET IN MY BELLY', 'IS THAT ALL?', 'SALAD BREATH'];
  // how many lie around at once and how long a new one takes to turn up after a pick-up (seconds, min..max)
  HW.PCFG = { POWERS: 3, GUNS: 3, POWER_WAIT: [30, 48], GUN_WAIT: [28, 46], CHILL_MULT: 0.4 };

  // ---------- special guns (item kind 'g', type = index here) ----------
  // Picked up, a special gun replaces your own for `t` seconds with no ammo count. Same fields as the
  // character guns in sim.js. kind continues after the five character guns (0..4), and is what a bullet
  // carries so every device knows how to fly and draw it.
  HW.SGUNS = [
    { id: 'ray', name: 'RAY GUN', desc: 'ZAPS STRAIGHT THROUGH EVERYBODY.', t: 14, interval: 0.34, speed: 720, dmg: 10, br: 3, range: 520, pellets: 1, spread: 0.01, pierce: 99, kind: 5 },
    { id: 'bazooka', name: 'ROCKET LAUNCHER', desc: 'ENORMOUS BLAST.', t: 14, interval: 1.0, speed: 230, dmg: 30, br: 5, range: 460, pellets: 1, spread: 0.01, blast: 115, accel: 340, vmax: 420, kind: 6 },
    { id: 'flame', name: 'HOT SAUCE FLAMETHROWER', desc: 'SHORT RANGE. MELTS WORMS.', t: 12, interval: 0.055, speed: 235, dmg: 1.5, br: 5, range: 150, pellets: 1, spread: 0.2, pierce: 2, kind: 7 },
    { id: 'mini', name: 'POPCORN MINIGUN', desc: 'A WALL OF POPCORN.', t: 12, interval: 0.065, speed: 370, dmg: 2.3, br: 2, range: 340, pellets: 1, spread: 0.09, kind: 8 },
    // chill: seconds a hit worm crawls at PCFG.CHILL_MULT of its speed (hits refresh it, they do not stack)
    { id: 'freeze', name: 'FREEZE RAY', desc: 'CHILLS WORMS TO A CRAWL.', t: 14, interval: 0.3, speed: 520, dmg: 5, br: 4, range: 420, pellets: 1, spread: 0.03, chill: 3.5, kind: 9 }
  ];

  // ---------- sprites ----------
  // the shiny pizza
  HW.pizzaSpr = sprite([
    '....kkkkkk....',
    '..kkttttttkk..',
    '.kttyyyyyyttk.',
    '.ktyrryyyhytk.',
    'ktyyrryygyyytk',
    'ktyyyyyyyyrrtk',
    'ktygyyhyyyrrtk',
    'ktyyyyyyyyyytk',
    'ktyrryyygyyytk',
    'ktyrryyyyyhytk',
    '.ktyyyyrryytk.',
    '.kttyyyrryttk.',
    '..kkttttttkk..',
    '....kkkkkk....']);
  // supersize fries (XL on the box)
  HW.superSpr = sprite([
    '.k.k.k.k.k.k.',
    'kykykykykykyk',
    'kyhyhyhyhyhyk',
    'kyyyyyyyyyyyk',
    'kkkkkkkkkkkkk',
    'krrrrrrrrrrrk',
    'krwrwrwrrrrrk',
    'krwrwrwrrrrrk',
    'krrwrrwrrrrrk',
    'krwrwrwrrrrrk',
    'krwrwrwwwrrrk',
    '.krrrrrrrrrk.',
    '.kRRRRRRRRRk.',
    '..kkkkkkkkk..']);
  // shot shield
  HW.guardSpr = sprite([
    '.kkkkkkkkkkk.',
    'kciiiiiiiiick',
    'kcicccccccCck',
    'kcicccwcccCck',
    'kciccwwwccCck',
    'kcicwwwwwcCck',
    'kciccwwwccCck',
    'kcicccwcccCck',
    '.kciccccCCck.',
    '.kcicccCCCck.',
    '..kcicCCCck..',
    '...kcCCCck...',
    '....kcCck....',
    '.....kkk.....']);
  // hot sauce bottle
  HW.sauceSpr = sprite([
    '...kkk...',
    '...kgk...',
    '...kgk...',
    '..kkkkk..',
    '..krrrk..',
    '.krrrrrk.',
    '.krwwwrk.',
    '.krwywrk.',
    '.krwowrk.',
    '.krwwwrk.',
    '.krrrrrk.',
    '.kRRRRRk.',
    '..kkkkk..']);
  HW.powerSpr = [HW.pizzaSpr, HW.superSpr, HW.guardSpr, HW.sauceSpr];
  // golden burger: the ordinary burger recast in gold
  HW.goldSpr = sprite(HW.FOOD[0].s, { o: '#ffd23f', O: '#c9960a', e: '#fffbe0', g: '#ffe98a', l: '#ffffff', y: '#fff1a0', b: '#b8860b', k: '#3a2a00' });

  // special guns as held by a worm, pointing right: c sprite, px/py grip point, len = grip to muzzle (same shape as HW.gunSpr)
  HW.sgunSpr = [
    // ray gun: fat coolant bulb, ringed barrel, glowing tip
    { c: sprite([
      '....kkkk.........',
      '...kcciik..k.k...',
      '.kkkcccckkkakak..',
      'kPPkciccaaaaaaakk',
      'kPpkccccssasasalk',
      'kPPkkkkkkkkkkkkk.',
      'kPPk.kqk.........',
      '.kk..kqk.........',
      '.....kkk.........']), px: 5, py: 4, len: 12 },
    // rocket launcher: a long steel tube with a red warhead in the mouth
    { c: sprite([
      'kk..........kk......',
      'kakkkkkkkkkkaakkkkk.',
      'kasssssssssssssswrk.',
      'kaSSSySSSSSSSSSSrrrk',
      'kaqqqqqqqqqqqqqqRrk.',
      'kakkkkbBkkkkbBkkkk..',
      'kk...kbBk..kbBk.....',
      '......kk....kk......']), px: 8, py: 3, len: 12 },
    // flamethrower: a hot sauce bottle for a tank, scorched nozzle
    { c: sprite([
      '.kkk............',
      'krrrkkkkkkkkk...',
      'krwrkaaaaaaaqkk.',
      'krrrksssssssqok.',
      'krRrkkkkkkkkkkk.',
      'krRrk.kqk.......',
      '.kkk..kkk.......']), px: 6, py: 3, len: 10 },
    // minigun: barrel cluster fed from a popcorn bucket
    { c: sprite([
      '..kkkk............',
      '.kwrwrk...........',
      '.krwrwkkkkkkkkkkk.',
      'kkkkkkkaaaaaaaaaqk',
      'kqqSSSkkkkkkkkkkkk',
      'kqqSSSksssssssssqk',
      'kkkkkkkkkkkkkkkkk.',
      '..kbBk............',
      '..kkkk............']), px: 5, py: 4, len: 13 },
    // freeze ray: the ray gun's frosty cousin, iced barrel, snowflake tip
    { c: sprite([
      '....kkkk.........',
      '...kiwwik.k.k.k..',
      '.kkkiiiikkikikik.',
      'kCCkiwiiccccccciw',
      'kCckiiiiCCcCcCcik',
      'kCCkkkkkkkkkkkkk.',
      'kCCk.kqk.........',
      '.kk..kqk.........',
      '.....kkk.........']), px: 5, py: 4, len: 12 }
  ];
  // shots that are sprites (flames and popcorn are drawn as plain squares)
  HW.raySpr = sprite([
    '.luuuuuuul.',
    'lwwwwwwwwwl',
    '.luuuuuuul.']);
  HW.iceSpr = sprite([
    '.icccccci.',
    'iwwwwwwwwi',
    '.icccccci.']);
  HW.bigRocketSpr = sprite([
    '.kkkkkkkk..',
    'kraaaaaawk.',
    'kRsssssswwk',
    'kraaaaaawk.',
    '.kkkkkkkk..']);
})(window.HW);
