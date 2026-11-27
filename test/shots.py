"""Screens tour: every menu screen at three phone sizes (does it fit without scrolling or clipping?), then a busy fight.
Writes a screenshot of each to the scratch dir for looking at.
  HW_URL=http://127.0.0.1:8377/index.html HW_PORT=9415 python3 test/shots.py <scratch dir>"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html"); FAIL = []
def ok(c, msg, extra=""):
    print(("ok   " if c else "FAIL ") + msg, extra if (extra != "" and not c) or os.environ.get("HW_VERBOSE") else "")
    if not c: FAIL.append(msg)
J = lambda t, js: json.loads(t.eval("JSON.stringify(%s)" % js))
LOW = {}
SIZES = [(844, 390, 3), (667, 375, 2), (932, 430, 3)]   # iPhone 12-14, iPhone SE / 8 (the small one), iPhone Pro Max
# where everything visible in the menu layer is, against the screen
FIT = """(()=>{const u=document.getElementById('ui'),k=[...u.querySelectorAll('*')].map(e=>e.getBoundingClientRect()).filter(r=>r.width>0&&r.height>0);
  if(!k.length)return {n:0};
  return {n:k.length,top:Math.min(...k.map(r=>r.top)),bottom:Math.max(...k.map(r=>r.bottom)),left:Math.min(...k.map(r=>r.left)),right:Math.max(...k.map(r=>r.right)),sh:u.scrollHeight,ch:u.clientHeight,sw:u.scrollWidth,cw:u.clientWidth,iw:innerWidth,ih:innerHeight,
    small:[...u.querySelectorAll('button')].map(b=>b.getBoundingClientRect()).filter(r=>r.height<26||r.width<44).length,
    minH:Math.min(...[...u.querySelectorAll('button')].map(b=>b.getBoundingClientRect().height))}})()"""
# the emptiest spot in the arena (see test/power.py): room for a fight with no obstacle in the way
SPOT = """(()=>{const M=HW.MAP;let spot=null,far=0;for(let y=300;y<M.H-300;y+=40)for(let x=300;x<M.W-300;x+=40){let d=1e9;
  for(const o of M.obs){const dx=Math.max(o.x0-x,0,x-o.x1),dy=Math.max(o.y0-y,0,y-o.y1);d=Math.min(d,Math.hypot(dx,dy))}if(d>far){far=d;spot={x,y,far:d}}}return spot})()"""
b = Browser(profile=SP + "/prof")
try:
    t = b.tab()
    for (w, h, dpr) in SIZES:
        tag = "%dx%d" % (w, h)
        t.device(w, h, dpr, True, True); t.goto(URL, 1.0)
        # best scores on every difficulty, so the title carries its longest line
        t.eval("localStorage.setItem('hw_best3_0','1234');localStorage.setItem('hw_best3_1','2345');localStorage.setItem('hw_best3_2','3456');localStorage.setItem('hw_diff','1')"); t.goto(URL, 1.2)
        def fits(name, shot):
            t.pump(0.3); f = J(t, FIT); t.shot(SP + "/s_%s_%s.png" % (tag, shot))
            good = f["n"] > 0 and f["top"] >= -0.5 and f["bottom"] <= f["ih"] + 0.5 and f["left"] >= -0.5 and f["right"] <= f["iw"] + 0.5 and f["sh"] <= f["ch"] + 1 and f["sw"] <= f["cw"] + 1
            ok(good, "%s: %s fits on the screen without scrolling or clipping" % (tag, name), f)
            ok(f.get("small", 1) == 0, "%s: %s - no button is smaller than 44 x 26 css px" % (tag, name), f)   # 26 is a floor, not a goal: see NOTES (the small phone's buttons are 27 px tall)
            LOW[tag] = min(LOW.get(tag, 999), f.get("minH", 999))
        ok(t.eval("HW.App.screen") == "title" and t.eval("HW.App.diff") == 1, "%s: title screen up" % tag)
        fits("title (with a best score on all three difficulties)", "title")
        t.eval("HW.App.show('help')"); fits("how to play", "help")
        for ch in range(5):
            t.eval("HW.App.sel.mode='solo';HW.App.sel.step=0;HW.App.sel.picks=[%d,1];HW.App.show('select')" % ch)
            fits("pick your worm (%s, with the BOTS button)" % t.eval("HW.CHARS[%d].name" % ch), "select%d" % ch)
        t.eval("HW.App.sel.mode='two';HW.App.sel.step=1;HW.App.sel.picks=[0,0];HW.App.show('select')"); fits("pick your worm, player 2 of 2", "select_2p")
        t.eval("HW.App.sel.mode='join';HW.App.sel.step=0;HW.App.show('select')"); fits("pick your worm, joining a room", "select_join")
        t.eval("HW.App.sel.code='ABCD';HW.App.show('join')"); fits("enter room code", "join")
        t.eval("HW.App.connMsg='JOINING ROOM ABCD...';HW.App.show('connecting')"); fits("connecting", "connecting")

        # ---- in a game: pause, results with every extra line there can be ----
        t.eval("HW.App.startLocal([0])"); t.pump(0.8)
        ok(t.eval("HW.App.mode") == "play" and t.eval("HW.App.sim.S.diff") == 1, "%s: solo game started" % tag)
        t.eval("HW.App.setPause(true)"); fits("pause", "pause")
        t.eval("HW.App.show('help')"); fits("how to play, from the pause menu", "help_ingame")
        t.eval("HW.App.setPause(false)")
        # four awards (the most there can be), a new best score: the tallest results screen
        t.eval("(()=>{const S=HW.App.sim.S,c=S.players[0].comp,m=HW.App.locals[0].me;c.st.veg=5;c.st.shr=4;c.st.pick=6;c.st.taunt=7;if(m){m.mass=4000;m.shield=9}})()"); t.pump(0.3)
        t.eval("HW.App.sim.S.match.t=0.2"); t.pump(1.0)
        aw = J(t, "HW.App.sim.S.match.awards")
        ok(t.eval("HW.App.screen") == "results" and len(aw) == 4, "%s: results screen up, with four awards" % tag, aw)
        ok(t.eval("document.querySelectorAll('#ui .panel').length") == 4 and t.eval("document.querySelectorAll('#ui button').length") == 2, "%s: results show the podium, the awards panel, PLAY AGAIN and MENU" % tag)
        fits("results (podium, new best score, four awards)", "results")
        t.eval("HW.App.quit()"); t.pump(0.3)
        # hosting a room: the pause menu grows a room code and a share button, the results a countdown (no PeerJS needed for the layout)
        t.eval("HW.App.startLocal([2]);HW.Net._loop(()=>HW.App.sim);HW.App.sim.S.autoNext=15"); t.pump(0.6)
        t.eval("HW.App.setPause(true)"); fits("pause while hosting a room (room code, share button)", "pause_host")
        t.eval("HW.App.setPause(false)")
        t.eval("(()=>{const S=HW.App.sim.S,c=S.players[0].comp,m=HW.App.locals[0].me;c.st.veg=5;c.st.shr=4;c.st.pick=6;c.st.taunt=7;if(m){m.mass=5000;m.shield=9}})()"); t.pump(0.3)
        t.eval("HW.App.sim.S.match.t=0.2"); t.pump(1.2)
        ok(t.eval("HW.App.screen") == "results", "%s: host results screen up" % tag)
        fits("results while hosting (plus NEXT MATCH IN ...)", "results_host")
        t.eval("HW.App.quit()"); t.pump(0.3)
        # two players on one screen: two result lines
        t.eval("HW.App.startLocal([1,3])"); t.pump(0.8)
        t.eval("(()=>{const S=HW.App.sim.S;S.players[0].comp.st.veg=5;S.players[1].comp.st.shr=4;S.players[0].comp.st.pick=6;S.players[1].comp.st.taunt=7;S.match.t=0.2})()"); t.pump(1.2)
        ok(t.eval("HW.App.screen") == "results", "%s: two-player results screen up" % tag)
        fits("results for two players", "results_2p")
        t.eval("HW.App.quit()"); t.pump(0.3)
        ok(not t.errors, "%s: no page errors on the tour" % tag, t.errors)

    # ---- a busy fight on the middle phone: play as Jeff, everybody herded close, guns loaded ----
    t.device(844, 390, 3, True, True); t.goto(URL, 1.0); t.eval("HW.App.startLocal([4])"); t.pump(1.0)
    sp = J(t, SPOT); ok(sp["far"] > 200, "fight: open ground found (nothing within %d px)" % sp["far"], sp)
    r = J(t, """(()=>{const S=HW.App.sim.S,M=HW.MAP,m=HW.App.locals[0].me,sx=%d,sy=%d;m.x=sx;m.y=sy;m.mass=120;m.ammo=8;m.shield=0;for(const p of m.pts){p.x=sx;p.y=sy}let i=0,bad=0;
      for(const w of S.worms){if(w===m)continue;const a=i++*0.6;let k=1;
        // ring them round the player; pull one in if its place would be inside an obstacle
        do{w.x=sx+Math.cos(a)*(150+i*8)*k;w.y=sy+Math.sin(a)*(110+i*6)*k;k-=0.1}while(k>0.3&&M.hit(w.x,w.y,w.r+6));
        if(M.hit(w.x,w.y,w.r))bad++;w.mass=60+i*12;w.shield=0;w.ammo=99;w.abil=i%%3?30:0;for(const p of w.pts){p.x=w.x;p.y=w.y}}
      HW.Input.touch.used=true;HW.Input.lastKind='touch';window.__ev={};const s=HW.App.sim,ev=s.ev;s.ev=function(k){__ev[k]=(__ev[k]||0)+1;return ev.apply(this,arguments)};
      return {placed:i,bad}})()""" % (sp["x"], sp["y"]))
    ok(r["placed"] == 11 and r["bad"] == 0, "fight: eleven bots placed round the player, none inside an obstacle", r)
    t.touch("touchStart", [(1, 150, 250), (2, 650, 250)]); t.touch("touchMove", [(1, 190, 250), (2, 700, 230)])
    t.pump(1.6); t.shot(SP + "/s_fight1.png"); t.pump(1.5); t.shot(SP + "/s_fight2.png"); t.touch("touchEnd", [])
    ev = J(t, "__ev")
    ok(ev.get("shot", 0) >= 5 and ev.get("hit", 0) >= 1, "fight: shots fired and landed (%d shots, %d hits, %d deaths)" % (ev.get("shot", 0), ev.get("hit", 0), ev.get("die", 0)), ev)
    g = J(t, "(()=>{const S=HW.App.sim.S;return S.worms.every(w=>isFinite(w.x)&&isFinite(w.y)&&isFinite(w.mass)&&!HW.MAP.hit(w.x,w.y,Math.max(0,w.r-1)))&&S.bullets.every(b=>isFinite(b.x)&&isFinite(b.y))})()")
    ok(g, "fight: every worm and bullet is somewhere sensible afterwards")
    ok(all(os.path.getsize(SP + "/" + f) > 15000 for f in ("s_fight1.png", "s_fight2.png")), "fight: screenshots written (s_fight1.png, s_fight2.png)")
    ok(not t.errors, "no page errors in the fight", t.errors)
finally:
    b.close()
print("\nshortest menu button per screen size (css px):", ", ".join("%s: %.0f" % kv for kv in LOW.items()))
print("\n%d failed: %s" % (len(FAIL), FAIL) if FAIL else "\nall screens fit; screenshots are in " + SP)
sys.exit(1 if FAIL else 0)
