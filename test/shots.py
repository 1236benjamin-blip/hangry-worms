import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html")
b = Browser(profile=SP + "/prof")
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 1.2)
    t.eval("HW.App.show('help')"); t.pump(0.3); t.shot(SP + "/s_help.png")
    t.eval("HW.App.sel.mode='two';HW.App.sel.step=1;HW.App.sel.picks=[0,0];HW.App.show('select')"); t.pump(0.4); t.shot(SP + "/s_sel2.png")
    t.eval("HW.App.sel.mode='join';HW.App.show('join')"); t.pump(0.3); t.shot(SP + "/s_join.png")
    # small phone
    t.device(667, 375, 2, True, True); t.pump(0.3); t.eval("HW.App.sel.mode='solo';HW.App.show('select')"); t.pump(0.4); t.shot(SP + "/s_small.png")
    t.device(844, 390, 3, True, True); t.pump(0.3)
    # busy fight scene: play as Jeff, herd everyone close, give ammo
    t.eval("HW.App.startLocal([4])"); t.pump(1.0)
    t.eval("""(()=>{const S=HW.App.sim.S,m=HW.App.locals[0].me;m.x=950;m.y=950;m.mass=120;m.ammo=8;let i=0;for(const w of S.worms){if(w===m)continue;const a=i++*0.6;w.x=950+Math.cos(a)*(150+i*8);w.y=950+Math.sin(a)*(110+i*6);w.mass=60+i*12;w.shield=0;w.ammo=99;w.abil=i%3?30:0;for(const p of w.pts){p.x=w.x;p.y=w.y}}HW.Input.touch.used=true;HW.Input.lastKind='touch'})()""")
    t.touch("touchStart", [(1, 150, 250), (2, 650, 250)]); t.touch("touchMove", [(1, 190, 250), (2, 700, 230)])
    t.pump(1.6); t.shot(SP + "/s_fight1.png"); t.pump(1.5); t.shot(SP + "/s_fight2.png")
    print(t.errors)
finally: b.close()
