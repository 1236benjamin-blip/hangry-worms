# Hangry Worms - build notes

## What it is
A slither-style arena shooter in pixel art. Static site, no build step, no image or sound files: every sprite, the font and all sound effects are generated in code.

| File | What it does |
| --- | --- |
| `index.html` | Page shell, menu styles |
| `sprites.js` | 5x7 pixel font, all sprites (food, veggies, mushrooms, guns, hats), worm segment discs |
| `sim.js` | The game rules: worms, guns, abilities, hazards, collisions. Host-authoritative, runs at a fixed 60 steps/s |
| `bots.js` | Bot AI |
| `render.js` | Low-res canvas renderer, screen effects, HUD, minimap, touch controls overlay |
| `input.js` | Touch twin-stick, keyboard, mouse, gamepads |
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
- Eat food to gain mass (length). Head into another worm's body = death; the dead worm bursts into food.
- Head-on head collision: the lighter worm dies; equal masses both die. A head into any body always dies.
- Bullets knock mass out of the target; about 75% of it drops as food at the hit. A worm shot below the minimum mass dies.
- Ammo only comes from the green crates. Each gun gets its own amount per crate.
- Boost burns mass and leaves a food trail.
- Fart: toxic cloud for 10 s, kills any other worm whose head enters. Puke: puddle for 10 s, any other worm that enters is stuck for 10 s (it can still aim and shoot). 60 s recharge with a meter.
- Veggies: slow you for 3 s and tint the screen green. Mushrooms: wobbly, smeary, colour-shifting screen for 7 s.
- 3 s spawn shield (ends early if you shoot or use your ability; guns are locked for the first second so a held trigger can't waste it).
- Walls do not kill; you slide along them.
- 12 worms in the arena at all times; bots fill every seat a human is not using.
- Same worm picked twice: the second gets a different colour, and bots are recoloured so a human always keeps theirs.

## Matches (3 lives, kills, podium)
- A match is **5 minutes** on a visible clock. The clock only runs while a human is playing.
- Every human has **3 lives**. Bots respawn freely so the arena stays busy; each bot seat keeps the same worm for the whole match so the leaderboard is stable.
- The match **ends** when the clock hits zero or when every human is out of lives (in solo: your third death). Out of lives in 2-player or online: you spectate the biggest worm until the end.
- **Score = biggest size you reached + 20 per kill.** Eating and fighting both count. Kills are tracked per competitor (humans and bots) and shown on the HUD and the results.
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
- **2 players on one device:** split screen. P1 uses touch or WASD + mouse; P2 uses a controller or the arrow keys (Enter shoot, right Shift boost, period ability). With two controllers each player gets one. So two people can also share one keyboard.
- **Ability button fires on release** on touch (slide off to cancel), a still right thumb waits 120 ms before auto-aim firing, a controller keeps its player if another disconnects, and a controller dropping out pauses the game.
- **Bots only open fire within about 170 px** (roughly what a player can see) and are less accurate against small worms, so you are not shot from off screen.
- **Aim assist for keyboard-only and trigger shooting:** if you fire without aiming (Space, Enter, controller trigger), the gun snaps to the nearest worm in front of you.
- **Auto respawn after 3 s** (tap or fire to hurry) to keep rounds flowing.
- **A crown** marks the biggest worm; the minimap shows it too.
- **Menu has a live bot match running behind it.**
- Arena is 1900 x 1900 with a zoomed-in camera so worms are a readable size on a phone. Gun ranges were sized to the screen.
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
