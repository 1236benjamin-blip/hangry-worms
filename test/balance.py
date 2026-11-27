"""Bots-only fast-forward. Usage: HW_PORT=9411 python3 test/balance.py <scratch dir> [minutes=20] [runs=1]
Prints per-worm deaths / kills / KD / lifetimes / causes plus gun and ability usage, sanity checks and JS errors."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 20; RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 1
URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html")
JS = """(()=>{const s=new HW.Sim(),S=s.S,names=HW.CHARS.map(c=>c.name),W=HW.CFG.W,H=HW.CFG.H;
  const st=names.map(()=>({deaths:0,kills:0,life:0,early:0,peak:0,veg:0,shroom:0,gotStuck:0,diedStuck:0,killsBy:{},massAtDeath:0,cause:{},shots:0,hits:0,dmg:0,abil:0,stuckOthers:0,massT:0,dryT:0,liveT:0,slowT:0,stuckT:0,boostT:0}));
  const born=new Map(),chOf=new Map();let maxItems=0,bad=[],maxBul=0,maxWorms=0,t0=performance.now();
  const od=s.damage;s.damage=function(w,dmg,owner,x,y){if(owner&&w.alive&&w.shield<=0){const c=st[owner.ch];c.hits++;c.dmg+=Math.min(w.mass,dmg+w.mass*0.02);}return od.call(this,w,dmg,owner,x,y)};
  const ok=s.kill;s.kill=function(w,k,cause){if(w.alive&&w.stuck>0)st[w.ch].diedStuck++;return ok.call(this,w,k,cause)};
  const steps=%d;for(let i=0;i<steps;i++){s.step(1/60);
    for(const e of S.events){const k=e[0];
      if(k==='spawn'){born.set(e[3],S.t);const w=S.worms.find(o=>o.id===e[3]);if(w)chOf.set(w.id,w.ch);}
      else if(k==='die'){const c=st[e[6]],l=S.t-(born.get(e[3])||0);c.deaths++;c.life+=l;if(l<8)c.early++;c.massAtDeath+=e[11];c.cause[e[5]]=(c.cause[e[5]]||0)+1;if(e[7]>=0){const kc=st[e[7]];kc.kills++;kc.killsBy[e[5]]=(kc.killsBy[e[5]]||0)+1;}born.delete(e[3]);chOf.delete(e[3]);}
      else if(k==='shot')st[e[3]].shots++;
      else if(k==='veg'||k==='shroom'||k==='stuck'){const ch=chOf.get(e[3]);if(ch!==undefined)st[ch][k==='stuck'?'gotStuck':k]++;}
      else if(k==='fart'||k==='puke'){const ch=chOf.get(e[3]);if(ch!==undefined)st[ch].abil++;}
    }
    S.events=[];S.adds.length=0;S.rems.length=0;if(S.items.size>maxItems)maxItems=S.items.size;if(S.bullets.length>maxBul)maxBul=S.bullets.length;if(S.worms.length>maxWorms)maxWorms=S.worms.length;
    if(i%%20===0)for(const w of S.worms){const c=st[w.ch];c.liveT++;c.massT+=w.mass;if(w.ammo<=0)c.dryT++;if(w.slow>0)c.slowT++;if(w.stuck>0)c.stuckT++;if(w.boosting)c.boostT++;if(w.mass>c.peak)c.peak=Math.round(w.mass);
      if(bad.length<5&&!(isFinite(w.x)&&isFinite(w.y)&&isFinite(w.ang)&&isFinite(w.aim)&&isFinite(w.mass)&&w.x>=0&&w.y>=0&&w.x<=W&&w.y<=H&&w.mass>0&&w.pts.length>=9))bad.push('worm '+names[w.ch]+' '+[w.x,w.y,w.ang,w.mass,w.pts.length].join(','));}
    if(i%%600===0){for(const b of S.bullets)if(bad.length<5&&!(isFinite(b.x)&&isFinite(b.y)&&isFinite(b.vx)))bad.push('bullet '+b.x+','+b.y);
      const cn={f:0,a:0,v:0,m:0};for(const it of S.items.values()){cn[it.k]++;if(bad.length<5&&!(isFinite(it.x)&&isFinite(it.y)))bad.push('item '+it.k);}
      for(const k in cn)if(bad.length<5&&cn[k]!==S.counts[k])bad.push('count '+k+' '+cn[k]+' vs '+S.counts[k]);}}
  const r1=v=>+v.toFixed(1),pc=(a,b)=>Math.round(100*a/Math.max(1,b));
  return JSON.stringify({ms:(performance.now()-t0)/steps,maxItems,maxBul,maxWorms,alive:S.worms.length,bad,counts:S.counts,top:S.worms.map(w=>names[w.ch]+':'+Math.round(w.mass)).join(' '),
    st:st.map((c,i)=>({n:names[i],deaths:c.deaths,kills:c.kills,kd:+(c.kills/Math.max(1,c.deaths)).toFixed(2),avgLife:r1(c.life/Math.max(1,c.deaths)),earlyPct:pc(c.early,c.deaths),avgMass:r1(c.massT/Math.max(1,c.liveT)),massAtDeath:Math.round(c.massAtDeath/Math.max(1,c.deaths)),peak:c.peak,
      shots:c.shots,hitPct:pc(c.hits,c.shots),dmgPerShot:r1(c.dmg/Math.max(1,c.shots)),dryPct:pc(c.dryT,c.liveT),slowPct:pc(c.slowT,c.liveT),stuckPct:pc(c.stuckT,c.liveT),boostPct:pc(c.boostT,c.liveT),abil:c.abil,vegPerMin:+(c.veg/Math.max(1,c.liveT)*180).toFixed(2),shroomPerMin:+(c.shroom/Math.max(1,c.liveT)*180).toFixed(2),stuckPerMin:+(c.gotStuck/Math.max(1,c.liveT)*180).toFixed(2),diedStuckPct:pc(c.diedStuck,c.deaths),killsBy:c.killsBy,cause:c.cause}))})})()"""
b = Browser(profile=SP + "/prof")
try:
    t = b.tab()
    t.call("Network.enable"); t.call("Network.setCacheDisabled", {"cacheDisabled": True})  # else Chrome may serve a stale sim.js/bots.js for minutes after an edit
    t.goto(URL, 1.0)
    for f in filter(None, os.environ.get("HW_INJECT", "").split(",")): t.eval(open(f).read() + "\n;0"); print("injected", f)  # A/B: swap in another sim.js / bots.js
    tot = {}; allbad = []; ms = []
    for run in range(RUNS):
        d = json.loads(t.eval(JS % int(MIN * 3600), timeout=600))
        print("run %d: ms/step %.3f maxItems %d maxBullets %d maxWorms %d alive %d counts %s" % (run + 1, d["ms"], d["maxItems"], d["maxBul"], d["maxWorms"], d["alive"], d["counts"]))
        ms.append(d["ms"]); allbad += d["bad"]
        if d["bad"]: print("  SANITY FAILURES:", d["bad"])
        print("  " + d["top"])
        for c in d["st"]:
            a = tot.setdefault(c["n"], {"deaths": 0, "kills": 0, "life": 0.0, "cause": {}, "by": {}})
            for k, v in c["killsBy"].items(): a["by"][k] = a["by"].get(k, 0) + v
            a["deaths"] += c["deaths"]; a["kills"] += c["kills"]; a["life"] += c["avgLife"] * c["deaths"]
            for k, v in c["cause"].items(): a["cause"][k] = a["cause"].get(k, 0) + v
            if RUNS == 1 or os.environ.get("HW_VERBOSE"): print("  ", c)
    print("%-9s %6s %6s %5s %8s  died of / killed with" % ("worm", "deaths", "kills", "K/D", "avgLife"))
    for n, a in tot.items():
        print("%-9s %6d %6d %5.2f %8.1f  %s" % (n, a["deaths"], a["kills"], a["kills"] / max(1, a["deaths"]), a["life"] / max(1, a["deaths"]), " ".join("%s %d" % kv for kv in sorted(a["cause"].items())) + "  /  " + " ".join("%s %d" % kv for kv in sorted(a["by"].items()))))
    print("sim cost %.3f ms/step avg | sanity failures (NaN, out of arena, item count drift): %s" % (sum(ms) / len(ms), allbad or "none"))
    print("JS errors:", t.errors)
finally: b.close()
