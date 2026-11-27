import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]
b = Browser(profile=SP + "/prof")
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto("http://127.0.0.1:8377/index.html", 1.0)
    t.eval("HW.App.startLocal([0])"); t.pump(6)
    print(t.eval("""(()=>{const A=HW.App,l=A.locals[0],v=l.view;let t0=performance.now();for(let i=0;i<300;i++)A.sim.step(1/60);const simMs=(performance.now()-t0)/300;A.sim.S.events=[];
      if(l.me){l.me.trip=7}; t0=performance.now();for(let i=0;i<300;i++){v.trip=(i<150)?0:5;HW.Render.drawView(v,A.G,i/60);HW.Render.drawHUD(v,{G:A.G,me:l.me,player:l.player,t:i/60})}
      HW.Render.ctx.getImageData(0,0,1,1);const drawMs=(performance.now()-t0)/300;return 'sim '+simMs.toFixed(3)+'ms/step, draw+hud '+drawMs.toFixed(3)+'ms/frame, canvas '+HW.Render.W+'x'+HW.Render.H+', worms '+A.G.worms.length+', items '+A.G.items.size})()"""))
    print(t.errors)
finally: b.close()
