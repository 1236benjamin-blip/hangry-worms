"""Smoke test: the page loads, the demo runs behind the title, a solo game starts and plays for a few seconds on a phone.
  HW_URL=http://127.0.0.1:8377/index.html HW_PORT=9415 python3 test/smoke.py <scratch dir>"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html"); FAIL = []
def ok(c, msg, extra=""):
    print(("ok   " if c else "FAIL ") + msg, extra if (extra != "" and not c) or os.environ.get("HW_VERBOSE") else "")
    if not c: FAIL.append(msg)
J = lambda t, js: json.loads(t.eval("JSON.stringify(%s)" % js))
b = Browser(profile=SP + "/prof")
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 2.0)
    t.shot(SP + "/title.png")
    ok(not t.errors, "the page loads without errors", t.errors)
    m = J(t, """(()=>{const A=HW.App,S=A.sim.S,C=HW.CFG,cn={};for(const it of S.items.values())cn[it.k]=(cn[it.k]||0)+1;
      return {W:HW.Render.W,H:HW.Render.H,scale:HW.Render.scale,screen:A.screen,mode:A.mode,worms:S.worms.length,items:S.items.size,cn,counts:S.counts,diff:S.diff,mapW:HW.MAP.W,cfgW:C.W,obs:HW.MAP.obs.length,
        cfg:{FOOD:C.FOOD,AMMO:C.AMMO,VEG:C.VEG,SHROOM:C.SHROOM,WORMS:C.WORMS,SHIELD:C.SHIELD},t:S.t,buttons:document.querySelectorAll('#ui button').length,
        css:(()=>{const r=HW.Render.canvas.getBoundingClientRect();return [r.width,r.height,innerWidth,innerHeight]})()}})()""")
    c = m["cfg"]
    ok(m["screen"] == "title" and m["mode"] == "menu" and m["buttons"] == 6, "title screen with its six buttons", m)
    ok(250 <= m["H"] <= 300 and 560 <= m["W"] <= 700 and abs(m["css"][0] - m["css"][2]) < 4 and abs(m["css"][1] - m["css"][3]) < 4, "low-res canvas (%dx%d) stretched over the whole phone screen" % (m["W"], m["H"]), m)
    ok(m["mapW"] == 2400 and m["cfgW"] == 2400 and m["obs"] > 30, "the arena is the 2400 px one with obstacles", m)
    ok(m["worms"] == c["WORMS"] == 12 and m["t"] > 0.5 and m["diff"] == 1, "a 12-bot demo match is running behind the menu (intermediate bots)", m)
    ok(m["cn"].get("f", 0) >= c["FOOD"] * 0.8 and m["cn"].get("a", 0) >= c["AMMO"] - 4 and m["cn"].get("v", 0) >= c["VEG"] - 4 and m["cn"].get("m", 0) >= c["SHROOM"] - 3 and all(m["cn"].get(k, 0) == m["counts"][k] for k in m["counts"]),
       "the floor is stocked: about %d food, %d crates, %d veggies, %d mushrooms" % (c["FOOD"], c["AMMO"], c["VEG"], c["SHROOM"]), (m["cn"], m["counts"]))
    t.eval("HW.App.sel.mode='solo';HW.App.show('select')"); t.pump(0.6); t.shot(SP + "/select.png")
    ok(t.eval("HW.App.screen") == "select" and t.eval("document.querySelectorAll('#ui button.card').length") == 5 and t.eval("!!document.querySelector('#ui button[data-diff]')"), "select screen: five worms and the BOTS button")
    t.eval("HW.App.startLocal([0])"); t.pump(3.5); t.shot(SP + "/play.png")
    g = J(t, """(()=>{const A=HW.App,S=A.sim.S,me=A.locals[0].me;return {mode:A.mode,screen:A.screen,alive:!!(me&&me.alive),shield:me?me.shield:-1,t:S.t,clock:S.match.t,worms:S.worms.length,humans:S.players.length,
      fin:S.worms.every(w=>isFinite(w.x)&&isFinite(w.y)&&isFinite(w.mass)&&!HW.MAP.hit(w.x,w.y,Math.max(0,w.r-1))),lives:S.players[0].comp.lives,diff:S.diff,appDiff:A.diff}})()""")
    ok(g["mode"] == "play" and g["screen"] == "" and g["humans"] == 1 and g["worms"] == 12, "a solo game starts: you and 11 bots", g)
    ok(g["alive"] and g["lives"] == 3 and 1.0 < g["t"] < 4.5 and 295 < g["clock"] < 299.5 and 0 < g["shield"] < 3.2, "a few seconds in: alive, clock running, spawn shield (4 s) still up", g)   # loose: a busy machine runs the page slow
    ok(g["fin"] and g["diff"] == g["appDiff"], "every worm is somewhere sensible; the bots play at the chosen difficulty", g)
    px = J(t, "(()=>{const c=HW.Render.ctx,d=c.getImageData(0,0,HW.Render.W,HW.Render.H).data,s=new Set();for(let i=0;i<d.length;i+=4*37)s.add((d[i]<<16)|(d[i+1]<<8)|d[i+2]);return s.size})()")
    ok(px > 30, "the game is actually being drawn (%d different colours on screen)" % px, px)
    ok(os.path.getsize(SP + "/play.png") > 20000, "screenshots written (title.png, select.png, play.png)")
    ok(not t.errors, "no page errors", t.errors)
finally:
    b.close()
print("\n%d failed: %s" % (len(FAIL), FAIL) if FAIL else "\nsmoke test passed")
sys.exit(1 if FAIL else 0)
