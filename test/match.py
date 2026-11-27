"""Match rules: 3 lives, kills, score (size + kill points, bounty, streaks), timer, results podium + awards, play again,
2P spectating, online sync + auto next match.
  HW_URL=http://127.0.0.1:8377/index.html HW_PORT=9415 python3 test/match.py <scratch dir>
The online part runs twice: over a loopback connection inside one page (always), and between two tabs through the real
PeerJS cloud. If the cloud cannot be reached from this machine the second one is SKIPPED with a message (set
HW_REQUIRE_ONLINE=1 to make that a failure instead). HW_INJECT=a.js,b.js evaluates those files before the loopback part."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html"); FAIL = []
def ok(c, msg, extra=""):
    print(("ok   " if c else "FAIL ") + msg, extra if (extra != "" and not c) or os.environ.get("HW_VERBOSE") else "")
    if not c: FAIL.append(msg)
b = Browser(profile=SP + "/prof")
J = lambda t, js: json.loads(t.eval("JSON.stringify(%s)" % js))
KILLME = "(()=>{const s=HW.App.sim,p=s.S.players[%d];if(p.worm&&p.worm.alive){s.kill(p.worm,null,'shot');return true}return false})()"
def die(t, i=0, others=()):
    for _ in range(60):
        if t.eval(KILLME % i): return True
        t.pump(0.2)
    return False
FIT = "(()=>{const u=document.getElementById('ui'),k=[...u.querySelectorAll('*')].map(e=>e.getBoundingClientRect()).filter(r=>r.width>0);return {top:Math.min(...k.map(r=>r.top)),bottom:Math.max(...k.map(r=>r.bottom)),sh:u.scrollHeight,ch:u.clientHeight,ih:innerHeight}})()"

# ---- a host and a client joined by a loopback connection inside one page: the real host code, the real client mirror, no PeerJS ----
LOOP = r"""
window.MT = (() => {
  const Net = HW.Net; let vt = 5000;
  const INP = () => ({ mx: 0, my: 0, ax: 0, ay: 0, fire: false, boost: false, abil: false, auto: false });
  function mkConn() { return { open: true, serialization: 'json', dataChannel: { bufferedAmount: 0 }, h: {}, out: [], on(ev, f) { this.h[ev] = f; }, send(m) { this.out.push(JSON.stringify(m)); }, close() { if (this.open) { this.open = false; if (this.h.close) this.h.close(); } }, recv(m) { this.h.data(m); } }; }
  function setup(diff, ch) {
    const keepNow = Net.now; Net.now = () => vt;
    const sim = new HW.Sim({ diff }); sim.S.events = []; sim.S.adds.length = 0; sim.S.rems.length = 0;
    const X = { sim, accept: Net._loop(() => sim), keepNow, G: Net.newMirror(), pid: -1, init: null, first: 0, ev: [], other: [], ver: 0 };
    X.host = sim.addPlayer(0); X.host.inp = INP();
    // the protocol version is private to net.js: knock with each in turn until the host lets us in
    for (let v = 1; v <= 30 && !X.init; v++) { const conn = mkConn(), c = X.accept(conn); if (!c) continue; conn.recv({ t: 'hello', ch, v }); if (c.player) { X.conn = conn; X.c = c; X.ver = v; break; } }
    if (X.conn) tick(X, 12);
    return X;
  }
  function deliver(X) {
    for (const s of X.conn.out) { const m = JSON.parse(s);
      if (m.t === 'init') { X.init = m; X.pid = m.pid; } else if (m.t === 'it' || m.t === 'pt') Net.applyPart(X.G, m);
      else if (m.t === 's') { Net.applySnap(X.G, m); if (m.first) X.first++; for (const e of m.e || []) X.ev.push(e); } else X.other.push(m); }
    X.conn.out.length = 0;
  }
  // like main.js advance(): step the sim, feed the network, hand the client what was sent
  function tick(X, frames) {
    for (let f = 0; f < frames; f++) {
      const dt = 3 / 60 + 1e-6; vt += dt; for (let i = 0; i < 3; i++) X.sim.step(1 / 60);
      const S = X.sim.S, evs = S.events; S.events = [];
      if (Net.hostTick(X.sim, dt, evs)) { S.adds.length = 0; S.rems.length = 0; deliver(X); }
      Net.clientUpdate(X.G, dt);
    }
  }
  function done(X) { Net.close(); Net.now = X.keepNow; }
  const mine = X => X.G.comps.find(q => q.pid === X.pid), myWorm = X => X.sim.S.players.find(p => p.pid === X.pid).worm;
  return { setup, tick, done, mine, myWorm, INP };
})();
"""
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 1.2)
    ok(J(t, "HW.App.sim.S.match.t") == 300 and t.eval("HW.App.sim.S.comps.length") == 12, "menu demo: 12 bot seats, clock idle")
    t.pump(1.0); ok(J(t, "HW.App.sim.S.match.t") == 300, "clock does not run with no humans")
    t.eval("HW.App.startLocal([0])"); t.pump(1.2)
    m = J(t, "(()=>{const S=HW.App.sim.S,c=S.players[0].comp;return {t:S.match.t,lives:c.lives,comps:S.comps.length,bots:S.comps.filter(c=>c.pid<0).length,worms:S.worms.length}})()")
    ok(m["lives"] == 3 and m["comps"] == 12 and m["bots"] == 11 and m["worms"] == 12, "solo start: 3 lives, 11 bot seats + you", m)
    ok(298 < m["t"] < 300, "clock running", m["t"])

    # ---- kill credit + score. The numbers come from the rules: CFG.KILL_PTS a kill, times HW.BOUNTY for the crowned leader,
    #      plus the HW.STREAKS bonus when a streak length is reached ----
    R = J(t, "({K:HW.CFG.KILL_PTS,B:HW.BOUNTY||1,ST:HW.STREAKS||[],LIVES:HW.CFG.LIVES})"); K = R["K"]
    bonus = lambda n: sum(q[2] for q in R["ST"] if q[0] == n)
    ok(K > 0 and R["LIVES"] == 3, "a kill is worth CFG.KILL_PTS = %d points" % K, R)
    KILL = """(()=>{const s=HW.App.sim,S=s.S,p=S.players[0],me=p.worm,c=p.comp;if(!me||!me.alive)return null;me.shield=0;
      const v=S.worms.find(w=>w.isBot&&w.alive&&(%s));if(!v)return null;
      const o={leader:S.leader,vid:v.id,wasLeader:v.id===S.leader,kills0:c.kills,pts0:c.pts,streak0:me.streak};s.kill(v,me,'shot');
      return Object.assign(o,{kills:c.kills,pts:c.pts,score:c.score,peak:Math.round(c.peak),streak:me.streak,wkills:me.kills})})()"""
    c = J(t, KILL % "w.id!==S.leader")
    ok(c and not c["wasLeader"] and c["kills"] == c["kills0"] + 1 and c["streak"] == c["streak0"] + 1, "kill counted (a worm that is not the crowned leader)", c)
    ok(c and c["pts"] - c["pts0"] == K + bonus(c["streak"]) and c["score"] == c["peak"] + c["pts"], "score = biggest size + points; a plain kill is worth KILL_PTS (%d)" % K, c)
    t.pump(0.3)
    hud = J(t, "(()=>{const c=HW.App.sim.S.players[0].comp;return {kills:c.kills,score:c.score,pts:c.pts,peak:Math.round(c.peak)}})()")
    ok(hud["kills"] == 1 and hud["score"] == hud["peak"] + hud["pts"], "the score keeps to size + points as the worm grows", hud)
    t.shot(SP + "/m_hud.png")
    # crown a bot, then kill it: the bounty and (second kill in a row) the streak bonus come on top
    t.eval("(()=>{const S=HW.App.sim.S,v=S.worms.find(w=>w.isBot&&w.alive);v.mass=400;HW.App.locals[0].me.shield=5})()"); t.pump(0.3)
    c = J(t, KILL % "w.id===S.leader")
    want = (K * R["B"] + bonus(c["streak"])) if c else -1
    ok(c and c["wasLeader"] and c["kills"] == 2 and c["pts"] - c["pts0"] == want and c["score"] == c["peak"] + c["pts"], "killing the crowned leader pays the bounty (x%d), plus the bonus for %d in a row: +%d" % (R["B"], c["streak"] if c else 0, want), c)

    ok(die(t), "life 1 lost"); t.pump(0.4); ok(J(t, "HW.App.sim.S.players[0].comp.lives") == 2, "2 lives left"); t.shot(SP + "/m_dead.png")
    ok(J(t, "(()=>{const p=HW.App.sim.S.players[0];return p.worm===null||!p.worm.alive||p.worm.streak===0})()"), "dying ends the kill streak")
    ok(die(t), "life 2 lost"); ok(die(t), "life 3 lost"); t.pump(0.3)
    ok(J(t, "HW.App.sim.S.players[0].comp.out") is True and J(t, "HW.App.sim.S.match.over") is False, "out of lives; short beat before the end")
    t.eval("HW.App.sim.S.players[0].comp.st.veg=3")   # three veggies eaten: good for the rabbit food award
    t.pump(2.2)
    ok(J(t, "HW.App.sim.S.match.over") is True and J(t, "HW.App.sim.S.match.reason") == "lives" and t.eval("HW.App.screen") == "results", "solo match ends when you are out of lives -> results screen")
    t.shot(SP + "/m_results.png")
    txt = t.eval("document.querySelectorAll('#ui button').length"); ok(txt == 2, "results has PLAY AGAIN + MENU", txt)
    aw = J(t, "(()=>{const S=HW.App.sim.S;return {aw:S.match.awards,cid:S.players[0].comp.cid,cids:S.comps.map(c=>c.cid),panels:document.querySelectorAll('#ui .panel').length}})()")
    ok(1 <= len(aw["aw"]) <= 4 and all(a[0] in aw["cids"] for a in aw["aw"]) and any(a[0] == aw["cid"] and "VEGGIES" in a[1] and a[2] == 3 for a in aw["aw"]), "results: the match hands out awards (yours: most veggies eaten)", aw)
    ok(aw["panels"] == 4, "results: podium for 1st, 2nd and 3rd plus the awards panel", aw["panels"])
    f = J(t, FIT); ok(f["top"] >= -0.5 and f["bottom"] <= f["ih"] + 0.5 and f["sh"] <= f["ch"] + 1, "results: it all fits on the phone screen", f)
    st0 = J(t, "HW.App.sim.S.t"); w0 = J(t, "HW.App.sim.S.worms.map(w=>w.x)"); t.pump(0.5); ok(J(t, "HW.App.sim.S.worms.map(w=>w.x)") == w0, "arena frozen after the end")
    # play again via a real tap
    r = J(t, "(()=>{const b=document.querySelector('#ui button.go').getBoundingClientRect();return [b.left+b.width/2,b.top+b.height/2]})()")
    t.touch("touchStart", [(0, r[0], r[1])]); t.touch("touchEnd", []); t.pump(1.5)
    m = J(t, "(()=>{const S=HW.App.sim.S,c=S.players[0].comp;return {n:S.match.n,over:S.match.over,t:S.match.t,lives:c.lives,kills:c.kills,pts:c.pts,veg:c.st.veg,aw:S.match.awards.length,screen:HW.App.screen,alive:!!(S.players[0].worm&&S.players[0].worm.alive),worms:S.worms.length}})()")
    ok(m["n"] == 2 and not m["over"] and m["lives"] == 3 and m["kills"] == 0 and m["screen"] == "" and m["alive"] and m["worms"] == 12, "PLAY AGAIN: fresh match, 3 lives, 0 kills", m)
    ok(m["pts"] == 0 and m["veg"] == 0 and m["aw"] == 0, "PLAY AGAIN: points, award counters and awards start from nothing", m)
    # timer ending
    t.eval("HW.App.sim.S.match.t=0.6"); t.pump(1.2)
    ok(J(t, "HW.App.sim.S.match.reason") == "time" and t.eval("HW.App.screen") == "results", "match ends on the clock"); t.shot(SP + "/m_results_time.png")
    t.eval("HW.App.quit()"); t.pump(0.3); ok(t.eval("HW.App.screen") == "title", "MENU returns to title")
    # 2 players: one out -> spectates, match goes on; both out -> ends
    t.device(1280, 720, 1); t.eval("HW.App.startLocal([1,1])"); t.pump(1.2)
    for _ in range(3): ok(die(t, 0), "P1 loses a life")
    t.pump(2.5)
    m = J(t, "(()=>{const S=HW.App.sim.S;return {over:S.match.over,p1out:S.players[0].comp.out,p2lives:S.players[1].comp.lives,p2alive:!!(S.players[1].worm&&S.players[1].worm.alive)}})()")
    ok(m["p1out"] and not m["over"] and m["p2lives"] >= 1, "2P: P1 out, match continues for P2", m); t.shot(SP + "/m_2p_spectate.png")
    for _ in range(3): die(t, 1)
    t.pump(2.4); ok(J(t, "HW.App.sim.S.match.over") is True, "2P: ends when both are out"); t.shot(SP + "/m_2p_results.png")
    ok(not t.errors, "no page errors (local)", t.errors)
    t.eval("HW.App.quit()"); t.pump(0.3)

    # ---------- online, loopback: host sim -> real snapshots -> client mirror, all in this page ----------
    for f in [f for f in os.environ.get("HW_INJECT", "").split(",") if f]: t.eval(open(f).read() + "\n;0"); print("injected " + f)   # A/B: try a patched net.js / sim.js
    t.eval(LOOP + ";0")
    r = J(t, """(()=>{const X=window.MX=MT.setup(2,2),S=X.sim.S,G=X.G,me=MT.mine(X);
      return {ver:X.ver,pid:X.pid,d:X.init&&X.init.d,first:X.first,comps:G.comps.length,bots:S.comps.filter(c=>c.pid<0).length,lives:me&&me.lives,gt:G.match.t,ht:S.match.t,n:G.match.n,over:G.match.over,
        worms:G.worms.length,hw:S.worms.length,items:G.items.size,hi:S.items.size}})()""")
    ok(r["ver"] > 0 and r["pid"] == 1 and r["first"] == 1, "loopback: a client joins the host (protocol version %d)" % r["ver"], r)
    ok(r["d"] == 2, "loopback: the client is told the host's bot difficulty", r)
    ok(r["comps"] == 12 and r["bots"] == 10 and r["lives"] == 3 and abs(r["gt"] - r["ht"]) < 1.5 and not r["over"], "loopback: the client sees the match clock, the 12 seats and its 3 lives", r)
    ok(r["worms"] == r["hw"], "loopback: the client sees every worm", r)
    r = J(t, "(()=>{const X=MX,w=MT.myWorm(X);X.sim.kill(w,null,'shot');MT.tick(X,8);return MT.mine(X).lives})()")
    ok(r == 2, "loopback: the client sees its life lost", r)
    r = J(t, """(()=>{const X=MX,S=X.sim.S;S.players[1].comp.st.veg=3;S.autoNext=4;S.match.t=0.2;MT.tick(X,20);const G=X.G;
      const a={hostOver:S.match.over,over:G.match.over,reason:G.match.reason,next:G.match.next,n:G.match.n,awards:G.match.awards||null,hostAwards:S.match.awards};
      MT.tick(X,90);const me=MT.mine(X);a.after={n:G.match.n,over:G.match.over,lives:me&&me.lives,hostN:S.match.n,kills:me&&me.kills,score:me&&me.score};return a})()""")
    ok(r["hostOver"] and r["over"] and r["reason"] == "time" and 0 < r["next"] <= 4, "loopback: the host's match ends on the clock and the client sees it, with the countdown to the next one", r)
    ok(r["after"]["n"] == 2 and r["after"]["hostN"] == 2 and not r["after"]["over"] and r["after"]["lives"] == 3, "loopback: the next match starts automatically for everyone, lives back to 3", r)
    awards_ok = r["hostAwards"] and r["awards"] == r["hostAwards"]
    # ---- the newer things a client has to be shown as well (what render.js and main.js read from the mirror) ----
    r2 = J(t, """(()=>{const X=MX,s=X.sim,S=s.S,G=X.G;MT.tick(X,30);const w=MT.myWorm(X),h=X.host.worm;if(!w||!h)return null;
      w.shield=0;h.shield=0;const ids=[s.addItem('p',1,w.x+60,w.y,0).id,s.addItem('g',3,w.x-60,w.y,0).id,s.addItem('x',0,w.x,w.y+70,HW.GOLD.v).id];
      w.rage=5;w.big=5;w.guard=5;w.sauce=5;w.sg=3;w.sgT=9;MT.tick(X,8);const mw=G.wmap.get(w.id)||{};
      const items=ids.map(id=>{const it=G.items.get(id);return it?[it.k,it.type,it.v]:null});
      // a ray gun bolt fired next to the client
      h.x=w.x+80;h.y=w.y+120;for(const p of h.pts){p.x=h.x;p.y=h.y}h.sg=1;h.sgT=9;h.cd=0;h.aim=0;X.host.inp.ax=1;X.host.inp.fire=true;MT.tick(X,2);X.host.inp.fire=false;
      const kinds=[...new Set(G.bullets.map(b=>b.ch))],hostKinds=[...new Set(S.bullets.map(b=>b.ch))];
      return {items,mw:{rage:mw.rage||0,big:mw.big||0,guard:mw.guard||0,sauce:mw.sauce||0,sg:mw.sg||0,r:mw.r},hr:w.r,kinds,hostKinds,frenzy:G.match.frenzy}})()""")
    ok(r2 and r2["items"] == [["p", 1, 0], ["g", 3, 0], ["x", 0, 30]], "net.js: an online client is sent the pickups (power-up, special gun, golden burger)", r2 and r2["items"])
    ok(r2 and r2["mw"]["rage"] > 0 and r2["mw"]["big"] > 0 and r2["mw"]["guard"] > 0 and r2["mw"]["sauce"] > 0 and r2["mw"]["sg"] == 3 and r2["mw"]["r"] == r2["hr"], "net.js: an online client is sent a worm's power-ups and special gun (rampage, supersize, shield, sauce)", r2 and (r2["mw"], r2["hr"]))
    ok(r2 and 5 in r2["hostKinds"] and 5 in r2["kinds"], "net.js: an online client is sent special-gun shots as what they are (ray gun bolt = kind 5)", r2 and (r2["kinds"], r2["hostKinds"]))
    ok(bool(awards_ok), "net.js: an online client is sent the end-of-match awards", (r["awards"], r["hostAwards"]))
    t.eval("MT.done(MX)")
    ok(not t.errors, "no page errors (loopback)", t.errors)

    # ---------- online, for real: two tabs through the PeerJS cloud ----------
    p = b.tab(); p.goto(URL, 0.5)
    net = json.loads(p.eval("""(async()=>{const get=async u=>{try{const c=new AbortController(),to=setTimeout(()=>c.abort(),8000);await fetch(u,{mode:'no-cors',cache:'no-store',signal:c.signal});clearTimeout(to);return true}catch(e){return false}};
      const lib=(await get('https://unpkg.com/peerjs@1.5.4/dist/peerjs.min.js'))||(await get('https://cdn.jsdelivr.net/npm/peerjs@1.5.4/dist/peerjs.min.js')),sig=await get('https://0.peerjs.com/peerjs/id');
      return JSON.stringify({lib,sig})})()""", timeout=40))
    if not (net["lib"] and net["sig"]):
        msg = "SKIP online through the real PeerJS cloud: this machine cannot reach %s. The 9 checks of that part did not run (the loopback checks above did)." % " or ".join(
            n for n, good in (("the PeerJS library (unpkg.com / cdn.jsdelivr.net)", net["lib"]), ("the PeerJS signalling server (0.peerjs.com)", net["sig"])) if not good)
        print(msg)
        if os.environ.get("HW_REQUIRE_ONLINE"): ok(False, "online: the PeerJS cloud can be reached (HW_REQUIRE_ONLINE is set)", net)
    else:
        h = t; h.eval("HW.App.startHost(0)"); code = None
        for i in range(40):
            h.pump(0.5); code = h.eval("HW.Net.code")
            if code: break
        ok(bool(code), "room opened", code)
        if code:
            c = b.tab(); c.device(844, 390, 3, True, True); c.goto(URL, 1.2); c.eval("HW.App.startJoin(2,'%s')" % code)
            for i in range(60):
                c.pump(0.25); h.pump(0.25)
                if c.eval("HW.App.mode") == "play": break
            ok(c.eval("HW.App.mode") == "play", "client joined")
            if c.eval("HW.App.mode") == "play":
                for i in range(8): c.pump(0.25); h.pump(0.25)
                cm = J(c, "(()=>{const G=HW.App.G;return {t:G.match.t,over:G.match.over,comps:G.comps.length,mine:G.comps.find(q=>q.pid===HW.App.myPid)}})()")
                hm = J(h, "(()=>{const S=HW.App.sim.S;return {t:S.match.t,comps:S.comps.length,bots:S.comps.filter(c=>c.pid<0).length}})()")
                ok(cm["comps"] == 12 and hm["bots"] == 10 and cm["mine"] and cm["mine"]["lives"] == 3 and abs(cm["t"] - hm["t"]) < 3, "client sees match clock, seats and its 3 lives", (cm["t"], hm["t"]))
                die(h, 1)
                for i in range(6): c.pump(0.25); h.pump(0.25)
                ok(J(c, "HW.App.G.comps.find(q=>q.pid===HW.App.myPid).lives") == 2, "client sees its life lost")
                h.eval("HW.App.sim.S.autoNext=4;HW.App.sim.S.match.t=0.5")
                for i in range(6): c.pump(0.25); h.pump(0.25)
                # (the host tab is hidden in this harness, so it does not draw; its sim state is what matters)
                ok(J(h, "HW.App.sim.S.match.over") is True and c.eval("HW.App.screen") == "results", "host match over, client shows the results screen", c.eval("HW.App.screen"))
                c.shot(SP + "/m_online_client_results.png"); h.shot(SP + "/m_online_host_results.png")
                ok(c.eval("document.querySelectorAll('#ui button').length") == 1, "client results: MENU only (host restarts)")
                for i in range(40):
                    c.pump(0.2); h.pump(0.2)
                    if c.eval("HW.App.G.match.n") == 2 and c.eval("!!HW.App.locals[0].me"): break
                cm = J(c, "(()=>{const G=HW.App.G;return {n:G.match.n,over:G.match.over,screen:HW.App.screen,lives:G.comps.find(q=>q.pid===HW.App.myPid).lives,me:!!HW.App.locals[0].me}})()")
                ok(cm["n"] == 2 and not cm["over"] and cm["screen"] == "" and cm["lives"] == 3 and cm["me"], "next match starts automatically for everyone", cm)
                ok(not h.errors and not c.errors, "no page errors (online)", (h.errors, c.errors))
finally:
    b.close()
print("\n" + ("ALL MATCH CHECKS PASSED" if not FAIL else "%d FAILED: " % len(FAIL) + "; ".join(FAIL))); sys.exit(1 if FAIL else 0)
