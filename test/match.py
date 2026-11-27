"""Match rules: 3 lives, kills, score, timer, results podium, play again, 2P spectating, online sync + auto next match."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from cdp import Browser
SP = sys.argv[1]; URL = os.environ.get("HW_URL", "http://127.0.0.1:8377/index.html"); FAIL = []
def ok(c, msg, extra=""):
    print(("ok   " if c else "FAIL ") + msg, extra)
    if not c: FAIL.append(msg)
b = Browser(profile=SP + "/prof")
J = lambda t, js: json.loads(t.eval("JSON.stringify(%s)" % js))
KILLME = "(()=>{const s=HW.App.sim,p=s.S.players[%d];if(p.worm&&p.worm.alive){s.kill(p.worm,null,'shot');return true}return false})()"
def die(t, i=0, others=()):
    for _ in range(60):
        if t.eval(KILLME % i): return True
        t.pump(0.2)
    return False
try:
    t = b.tab(); t.device(844, 390, 3, True, True); t.goto(URL, 1.2)
    ok(J(t, "HW.App.sim.S.match.t") == 300 and t.eval("HW.App.sim.S.comps.length") == 12, "menu demo: 12 bot seats, clock idle")
    t.pump(1.0); ok(J(t, "HW.App.sim.S.match.t") == 300, "clock does not run with no humans")
    t.eval("HW.App.startLocal([0])"); t.pump(1.2)
    m = J(t, "(()=>{const S=HW.App.sim.S,c=S.players[0].comp;return {t:S.match.t,lives:c.lives,comps:S.comps.length,bots:S.comps.filter(c=>c.pid<0).length,worms:S.worms.length}})()")
    ok(m["lives"] == 3 and m["comps"] == 12 and m["bots"] == 11 and m["worms"] == 12, "solo start: 3 lives, 11 bot seats + you", m)
    ok(298 < m["t"] < 300, "clock running", m["t"])
    # kill credit + score
    t.eval("(()=>{const s=HW.App.sim,p=s.S.players[0],b=s.S.worms.find(w=>w.isBot);p.worm.shield=0;s.kill(b,p.worm,'shot')})()"); t.pump(0.3)
    c = J(t, "(()=>{const c=HW.App.sim.S.players[0].comp;return {kills:c.kills,score:c.score,peak:Math.round(c.peak)}})()")
    ok(c["kills"] == 1 and c["score"] == c["peak"] + 20, "kill counted, score = peak size + 20 per kill", c)
    t.shot(SP + "/m_hud.png")
    ok(die(t), "life 1 lost"); t.pump(0.4); ok(J(t, "HW.App.sim.S.players[0].comp.lives") == 2, "2 lives left"); t.shot(SP + "/m_dead.png")
    ok(die(t), "life 2 lost"); ok(die(t), "life 3 lost"); t.pump(0.3)
    ok(J(t, "HW.App.sim.S.players[0].comp.out") is True and J(t, "HW.App.sim.S.match.over") is False, "out of lives; short beat before the end")
    t.pump(2.2)
    ok(J(t, "HW.App.sim.S.match.over") is True and J(t, "HW.App.sim.S.match.reason") == "lives" and t.eval("HW.App.screen") == "results", "solo match ends when you are out of lives -> results screen")
    t.shot(SP + "/m_results.png")
    txt = t.eval("document.querySelectorAll('#ui button').length"); ok(txt == 2, "results has PLAY AGAIN + MENU", txt)
    st0 = J(t, "HW.App.sim.S.t"); w0 = J(t, "HW.App.sim.S.worms.map(w=>w.x)"); t.pump(0.5); ok(J(t, "HW.App.sim.S.worms.map(w=>w.x)") == w0, "arena frozen after the end")
    # play again via a real tap
    r = J(t, "(()=>{const b=document.querySelector('#ui button.go').getBoundingClientRect();return [b.left+b.width/2,b.top+b.height/2]})()")
    t.touch("touchStart", [(0, r[0], r[1])]); t.touch("touchEnd", []); t.pump(1.5)
    m = J(t, "(()=>{const S=HW.App.sim.S,c=S.players[0].comp;return {n:S.match.n,over:S.match.over,t:S.match.t,lives:c.lives,kills:c.kills,screen:HW.App.screen,alive:!!(S.players[0].worm&&S.players[0].worm.alive),worms:S.worms.length}})()")
    ok(m["n"] == 2 and not m["over"] and m["lives"] == 3 and m["kills"] == 0 and m["screen"] == "" and m["alive"] and m["worms"] == 12, "PLAY AGAIN: fresh match, 3 lives, 0 kills", m)
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
    print("local errors:", t.errors); ok(not t.errors, "no page errors (local)")
    t.eval("HW.App.quit()")

    # ---------- online ----------
    h = t; h.eval("HW.App.startHost(0)"); code = None
    for i in range(40):
        h.pump(0.5); code = h.eval("HW.Net.code")
        if code: break
    ok(bool(code), "room opened", code)
    c = b.tab(); c.device(844, 390, 3, True, True); c.goto(URL, 1.2); c.eval("HW.App.startJoin(2,'%s')" % code)
    for i in range(60):
        c.pump(0.25); h.pump(0.25)
        if c.eval("HW.App.mode") == "play": break
    ok(c.eval("HW.App.mode") == "play", "client joined")
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
    print("host errors:", h.errors, "client errors:", c.errors); ok(not h.errors and not c.errors, "no page errors (online)")
finally:
    b.close()
print("\n" + ("ALL MATCH CHECKS PASSED" if not FAIL else "FAILED: " + "; ".join(FAIL))); sys.exit(1 if FAIL else 0)
