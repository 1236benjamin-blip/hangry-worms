# Hangry Worms - build notes

## What it is
A slither-style arena shooter in pixel art. Static site, no build step, no image or sound files: every sprite, the font and all sound effects are generated in code.

| File | What it does |
| --- | --- |
| `index.html` | Page shell, menu styles |
| `sprites.js` | 5x7 pixel font, all sprites (food, veggies, mushrooms, guns, hats), floor tiles, and the worm skins (`HW.SKINS`: a painted design and four palettes per character, baked per skin / radius / direction the first time each is drawn) |
| `power.js` | Power-ups, special guns, golden burger, streaks, bounty, frenzy and taunt lines: the numbers and the sprites |
| `map.js` | The arena: 2400 x 2400, the obstacles (`HW.MAP.hit / push / los`), floor zones, floor graffiti lines |
| `sim.js` | The game rules: worms, guns, abilities, hazards, pickups, collisions, scoring. Host-authoritative, runs at a fixed 60 steps/s |
| `bots.js` | Bot AI, three difficulty levels |
| `render.js` | Low-res canvas renderer, screen effects, HUD, minimap, touch controls overlay |
| `input.js` | Touch twin-stick (one control set per player in split screen), keyboard, mouse, gamepads |
| `net.js` | Online rooms over PeerJS (free cloud signalling, peer-to-peer data) |
| `main.js` | Menus, game loop, sound synth, glue |
| `test/` | Headless Chrome tests driven by a small standard-library Python CDP client (`cdp.py`) |

## The worms
| Worm | Size / speed | Gun | Ability | Notes |
| --- | --- | --- | --- | --- |
| Ben | Big, slowest | Burger Cannon: slow fire, big fast bullets, long range | Fart | Eats food from further away |
| Chandler | Big, a bit faster | Soda Scattergun: 5-pellet blast, brutal up close, very short range | Fart | |
| Nate | Small, fastest, agile | Gumball SMG: sprays fast, slow weak bullets | Puke | |
| Wesley | Small, fast, agile | Kebab Skewer: accurate, pierces through up to 4 worms | Puke | |
| Jeff | Big, slow | Meatball Rocket: big blast radius, only a few rockets | none | Fart and puke both kill him |

Balance idea: big worms hit hard and survive more hits but turn like trucks; small worms dodge and out-turn them but die to fewer hits. Jeff has the best gun and pays with no ability, tiny ammo and a double weakness.

## Rules as built
- Eat food to gain mass (length). Driving your head into another worm's body kills you, but not instantly: first you BUMP. The head is held at their surface (it cannot pass through), sparks fly, the screen edges flash red with TURN!, and only if you keep driving in for 0.4 s do you die. The count runs slower the more you are turned away and drains once you are clear, so a quick turn saves you and a glancing touch is only a scrape. The dead worm bursts into food.
- Head-on head collision: the lighter worm dies; equal masses both die. A head into any body always dies.
- Bullets knock mass out of the target; about 75% of it drops as food at the hit. A worm shot below the minimum mass dies.
- Ammo only comes from the green crates. Each gun gets its own amount per crate.
- Boost burns mass and leaves a food trail.
- Fart: toxic cloud for 10 s, kills any other worm whose head enters. Puke: puddle for 10 s, any other worm that enters is stuck for 10 s (it can still aim and shoot). 60 s recharge with a meter.
- Veggies: you shrink (10% of your mass + 3) and are slowed for 4.5 s with a green screen. Mushrooms: wobbly, smeary, colour-shifting screen for 10 s, and your steering and aim sway. The upside: a veggie takes 10 s off your fart / puke countdown, a mushroom 15 s.
- 4 s spawn shield (ends early if you shoot or use your ability; guns are locked for the first second so a held trigger can't waste it).
- Walls do not kill; you slide along them. The same goes for obstacles.
- 12 worms in the arena at all times; bots fill every seat a human is not using.
- Same worm picked twice: the second gets a different colour, and bots are recoloured so a human always keeps theirs.

## The arena
- 2400 x 2400 (was 1900). The middle is the FOOD COURT, the corners are the KITCHEN, the CANDY SHOP, the SALAD BAR and the GREASE PIT, each with its own floor. Nearly half the veggies turn up in the salad bar.
- 37 obstacles: diner counters, round tables, crates, vending machines and giant soda cans. They block worms (you slide round them) and every kind of shot, and a rocket's blast does not reach round a counter. Nothing ever spawns inside one. They show on the minimap. The layout is one quadrant written by hand and turned three times round the middle (`map.js`), so it is the same on every device and never needs sending over the network.
- About 50 lines of floor graffiti ("EAT MORE", "BEN SUCKS", "SALAD IS A TRAP"...) and food spills, placed by a fixed seed so everybody sees the same floor. Add lines in `MAP.GRAFFITI`.
- Food: about 210 pieces on the map instead of 520, drawn double size and worth 3 / 5 / 8 instead of 1 / 2 / 3. Crumbs from boosting and small hits stay small. A dead worm leaves a trail of big pieces.

## Pickups (`power.js` has every number)
They do not start on the map: they turn up over the first half minute, glow, carry a name label and blink on the minimap. At most 3 power-ups, 3 guns and 1 golden burger lie around at once.

| Pickup | What it does |
| --- | --- |
| Shiny pizza: RAMPAGE | 9 s. 40% faster, and running into another worm kills THEM. Shots, farts and puke still work on you. Two rampaging worms follow the normal rules |
| XL fries: SUPERSIZE | 12 s. Half again as big, wins every head-on (except against a rampage), takes half damage, eats from further away, keeps 20 mass |
| SHOT SHIELD | 10 s. Stops every shot and blast, piercing ones included. Crashes, farts and puke still get you |
| HOT SAUCE | 8 s. Boosting costs no mass, is 15% quicker and leaves a fire trail |
| Golden burger | +30 mass. One at a time |
| RAY GUN | 14 s. Fast bolt straight through everybody |
| ROCKET LAUNCHER | 14 s. Very big blast |
| HOT SAUCE FLAMETHROWER | 12 s. Short range, heavy damage |
| POPCORN MINIGUN | 12 s. Very fast spray |
| FREEZE RAY | 14 s. Light damage; a hit worm crawls at 40% speed for 3.5 s (refreshes, does not stack) |

A special gun replaces your own for its time and uses no ammo. Obstacles stop all of them.

## More ways to score
- **Bounty:** the crowned worm (the biggest, once over 60) is worth double kill points.
- **Kill streaks:** kills in a row without dying: DOUBLE KILL +10, FOOD COMA (3) +20, ALL YOU CAN EAT (5) +40, UNSTOPPABLE GLUTTON (7) +60.
- **Feeding frenzy:** in the last minute food and pickups arrive twice as fast.
- **Taunts:** a speech bubble over your worm (LOL button on touch, T on the keyboard, B on a controller). Bots gloat after a kill sometimes.
- **Awards:** the results screen hands out up to four silly ones (most veggies eaten, best aim, most shots missed, most pickups, most boosting, most taunts, best streak, biggest worm).

## Bot difficulty
EASY (the default), INTERMEDIATE and HARD: the BOTS button on the pick-your-worm screen cycles them, the choice is remembered, and the host's choice applies online. It changes how skilled each bot is, how quickly it thinks, how far away it opens fire, how well it aims and leads, how long it rests between bursts, how often it dozes off, how reliably it dodges and uses its ability, and how long it leaves a freshly spawned human alone (`HW.DIFFS` in `sim.js`). The best score is saved per difficulty.

## Matches (3 lives, kills, podium)
- A match is **5 minutes** on a visible clock. The clock only runs while a human is playing.
- Every human has **3 lives**. Bots respawn freely so the arena stays busy; each bot seat keeps the same worm for the whole match so the leaderboard is stable.
- The match **ends** when the clock hits zero or when every human is out of lives (in solo: your third death). Out of lives in 2-player or online: you spectate the biggest worm until the end.
- **Score = biggest size you reached + kill points** (see "More ways to score"). Eating and fighting both count. Kills are tracked per competitor (humans and bots) and shown on the HUD and the results.
- HUD: clock top centre, hearts and kill count under the minimap, leaderboard top right showing 1st, 2nd, 3rd by score plus your own row.
- **Results screen:** podium for 1st, 2nd and 3rd with each worm, score and kills, your own placing, and "new best" when you beat your saved best score.
- Solo and 2-player: PLAY AGAIN or MENU. Online: the next match starts automatically 15 seconds later for everyone (the host can press PLAY AGAIN to skip the wait); nobody has to rejoin.
- A player who joins an online room mid-match gets 3 lives and plays out the rest of that match.
- `test/match.py` covers all of this in solo, 2-player and online.

## Decisions I made (things not in the brief, or changed)
- **Fart comes out near the head, not the tail tip.** It appears about 16 segments behind the head. At the very tail of a long worm it would never matter in a fight; here it protects you and punishes anyone cutting in close.
- **Puke is aimed.** The puddle lands a short way in front of you in the direction your gun points.
- **Abilities start with 20 s left on the meter after each spawn**, so dying and respawning is not a way to spam them.
- **Drop-in online rooms instead of a lobby.** The host just starts playing; friends join mid-game with the code or an invite link (`?join=CODE`). Simpler and nothing to get stuck in.
- **2 players on one device:** split screen. On a phone each half has its own full touch control set (move stick, aim stick, boost, ability, taunt); the pause button is in P1's half. A finger belongs to the half it came down in, even if it slides over the divider. Or P1 uses WASD + mouse and P2 a controller or the arrow keys (Enter shoot, right Shift boost, period ability). With two controllers each player gets one.
- **Ability button fires on release** on touch (slide off to cancel), a still right thumb waits 120 ms before auto-aim firing, a controller keeps its player if another disconnects, and a controller dropping out pauses the game.
- **Bots only open fire within about 170 px** (roughly what a player can see) and are less accurate against small worms, so you are not shot from off screen.
- **Aim assist for keyboard-only and trigger shooting:** if you fire without aiming (Space, Enter, controller trigger), the gun snaps to the nearest worm in front of you.
- **Auto respawn after 3 s** (tap or fire to hurry) to keep rounds flowing.
- **A crown** marks the biggest worm; the minimap shows it too.
- **Menu has a live bot match running behind it.**
- The camera is zoomed in so worms are a readable size on a phone. Gun ranges were sized to the screen.
- **XL fries, not a mushroom, for the grow power-up:** mushrooms are already the bad pickup, and a second kind would be confusing.
- **Rampage is not full invincibility.** It only changes what happens when worms touch. You can still be shot, gassed and glued, so there is always an answer to it.
- **Veggies and mushrooms charge your ability** (asked for): eating your greens is now a choice, not just a mistake.
- Numbers that stayed exactly as briefed: 10 s cloud/puddle, 10 s stuck, 60 s recharge.

## Tech notes
- Rendering is a low-resolution canvas (about 270 px tall, integer device-pixel scale) stretched with `image-rendering: pixelated`. This is what makes it cheap on phones: a full frame costs well under 1 ms on a laptop.
- Bodies are a chain of points that follow the head. Online clients only receive head positions and rebuild bodies locally with the same chain code, so snapshots stay tiny.
- Online: the host simulates everything and sends snapshots 20 times a second; clients send inputs and interpolate. PeerJS JSON messages have a ~16 KB limit, so the join handshake sends the arena in small chunks.
- While a host's tab is hidden, a Web Worker timer keeps the simulation and snapshots running (requestAnimationFrame stops in hidden tabs).
- PeerJS is loaded from a CDN only when someone picks an online option, so solo and local play never depend on it.

## Testing done (headless Chrome)
- `test/play.py`: phone landscape (844x390 @3x) with real touch events for menu taps, move stick, aim stick + firing, boost, ability and pause buttons; hazards; desktop keyboard + mouse; 2-player split screen with a simulated gamepad for P2; gamepad menu navigation.
- `test/online.py`: host in one tab, phone-sized client in another through the real PeerJS cloud: join by code, input round trip, ability, item and position sync, death and respawn, client leaving, host leaving.
- `test/match.py`: lives, kill credit, score, clock, results podium, play again, 2-player spectating, online match sync and automatic next match.
- `test/balance.py`: fast-forwards 20 minutes of bots-only play and prints kills, deaths, lifetimes and causes of death per worm. Used to tune damage, speeds and bot caution.
- `test/perf.py`: per-frame simulation and draw cost.

Run them with `python3 -m http.server 8377` in this folder, then `python3 test/play.py /tmp/out`.

## Publishing
- Live at https://1236benjamin-blip.github.io/hangry-worms/ (GitHub Pages, `main` branch, root folder). Repo: https://github.com/1236benjamin-blip/hangry-worms
- This Mac has no GitHub CLI or git credentials, so files were uploaded through the GitHub website. The local git history and the GitHub history are therefore separate: to update the live game, upload the changed files again on the repo's "Add file > Upload files" page (or set up git credentials and force-push the local history).

## Known issues / not done
- Not yet tested on a real phone or with a real controller (only emulated touch and a simulated gamepad). Button sizes and stick feel may want tuning after real play.
- iPhone Safari cannot go true fullscreen; "Add to Home Screen" gives the cleanest view. Android goes fullscreen and locks landscape when a game starts.
- Online uses the free public PeerJS server (STUN plus PeerJS's best-effort free TURN). Two players behind strict mobile-carrier or corporate NATs may fail to connect (there is no paid relay). Same Wi-Fi always works.
- If the host's phone goes to sleep or the browser is fully backgrounded on mobile, clients see WAITING FOR HOST and leave after 45 s; if the host quits, the room ends. A client that goes silent is idled after 1.5 s and removed after 30 s.
- Online is one player per device; split screen is offline only.
- Clients see their own worm with a small delay (no client-side prediction). Fine on normal connections, mushy on bad ones.
- Balance is tuned on bot-only simulations (bots now dodge a little and steer on real turning arcs). After the bot engagement range was capped, the spread is roughly K/D 0.8 to 1.25 with run-to-run variance; expect to revisit after real matches.
- In 2-player on a phone, P1's touch controls sit over P2's half of the screen (inherent to one touch + one controller).
- Scores from before the match system (pure size) and after (size + kills) share the same saved best.
- Bots are not affected by the screen effects, only by the slowdown (mushrooms just make them steer drunkenly).
