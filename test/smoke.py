import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html")
b = Browser(profile=SP + "/prof")
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 2.0)
    t.shot(SP + "/title.png")
    print("errors:", t.errors); print("log:", t.log[-8:])
    print(t.eval("JSON.stringify({W:HW.Render.W,H:HW.Render.H,screen:HW.App.screen,worms:HW.App.sim.S.worms.length,items:HW.App.sim.S.items.size})"))
    t.eval("HW.App.sel.mode='solo';HW.App.show('select')"); t.pump(0.6); t.shot(SP + "/select.png")
    t.eval("HW.App.startLocal([0])"); t.pump(3.5); t.shot(SP + "/play.png")
    print("errors:", t.errors)
finally:
    b.close()
