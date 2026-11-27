"""Tiny Chrome DevTools Protocol driver using only the Python standard library.
Used to test Hangry Worms in headless Chrome (no Node / Playwright on this machine)."""
import base64, json, os, socket, struct, subprocess, time, urllib.request

CHROME = os.environ.get("HW_CHROME") or next((p for p in ("/opt/pw-browsers/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/chromium", "/usr/bin/google-chrome") if os.path.exists(p)), "chromium")

class WS:
    def __init__(self, url):
        assert url.startswith("ws://"); rest = url[5:]; hostport, path = rest.split("/", 1)
        host, port = hostport.split(":"); self.s = socket.create_connection((host, int(port))); self.buf = b""
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (path, hostport, key)).encode())
        while b"\r\n\r\n" not in self.buf: self.buf += self.s.recv(4096)
        self.buf = self.buf.split(b"\r\n\r\n", 1)[1]
    def send(self, text):
        d = text.encode(); n = len(d); h = b"\x81"
        if n < 126: h += bytes([0x80 | n])
        elif n < 65536: h += bytes([0x80 | 126]) + struct.pack(">H", n)
        else: h += bytes([0x80 | 127]) + struct.pack(">Q", n)
        m = os.urandom(4); self.s.sendall(h + m + bytes(b ^ m[i % 4] for i, b in enumerate(d)))
    def _need(self, n):
        while len(self.buf) < n:
            c = self.s.recv(65536)
            if not c: raise IOError("ws closed")
            self.buf += c
        r, self.buf = self.buf[:n], self.buf[n:]; return r
    def recv(self, timeout=30):
        self.s.settimeout(timeout); out = b""
        while True:
            b0, b1 = self._need(2); op = b0 & 15; n = b1 & 127
            if n == 126: n = struct.unpack(">H", self._need(2))[0]
            elif n == 127: n = struct.unpack(">Q", self._need(8))[0]
            p = self._need(n)
            if op == 9: continue
            if op == 8: raise IOError("ws close frame")
            out += p
            if b0 & 0x80: return out.decode("utf8", "replace")

class Tab:
    def __init__(self, wsurl): self.ws = WS(wsurl); self.id = 0; self.log = []; self.errors = []
    def call(self, method, params=None, timeout=30):
        self.id += 1; i = self.id; self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv(timeout))
            if m.get("id") == i:
                if "error" in m: raise RuntimeError(method + ": " + json.dumps(m["error"]))
                return m.get("result", {})
            self._event(m)
    def _event(self, m):
        me = m.get("method")
        if me == "Runtime.consoleAPICalled":
            t = " ".join(str(a.get("value", a.get("description", ""))) for a in m["params"]["args"]); self.log.append(m["params"]["type"] + ": " + t)
            if m["params"]["type"] == "error": self.errors.append(t)
        elif me == "Runtime.exceptionThrown":
            d = m["params"]["exceptionDetails"]; t = (d.get("exception", {}).get("description") or d.get("text", "")) + " @" + str(d.get("url", "")) + ":" + str(d.get("lineNumber"))
            self.errors.append(t); self.log.append("EXC: " + t)
        elif me == "Log.entryAdded":
            e = m["params"]["entry"]; self.log.append("log-" + e["level"] + ": " + e["text"] + " " + e.get("url", ""))
            if e["level"] == "error": self.errors.append(e["text"] + " " + e.get("url", ""))
    def pump(self, secs):
        end = time.time() + secs
        while time.time() < end:
            try: self._event(json.loads(self.ws.recv(max(0.01, end - time.time()))))
            except socket.timeout: pass
    def init(self):
        for d in ("Page", "Runtime", "Log", "Network"): self.call(d + ".enable")
        self.call("Network.setCacheDisabled", {"cacheDisabled": True})
    def eval(self, js, timeout=30):
        r = self.call("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True}, timeout)
        if "exceptionDetails" in r: raise RuntimeError("JS: " + json.dumps(r["exceptionDetails"])[:600])
        return r["result"].get("value")
    def goto(self, url, wait=1.0): self.call("Page.navigate", {"url": url}); self.pump(wait)
    def device(self, w, h, dpr=1, mobile=False, touch=False):
        self.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": dpr, "mobile": mobile})
        self.call("Emulation.setTouchEmulationEnabled", {"enabled": touch, "maxTouchPoints": 5})
    def shot(self, path):
        r = self.call("Page.captureScreenshot", {"format": "png"}); open(path, "wb").write(base64.b64decode(r["data"])); return path
    def touch(self, typ, pts): self.call("Input.dispatchTouchEvent", {"type": typ, "touchPoints": [{"x": x, "y": y, "id": i} for (i, x, y) in pts]})
    def key(self, typ, code, key=None, vk=0): self.call("Input.dispatchKeyEvent", {"type": "keyDown" if typ == "down" else "keyUp", "code": code, "key": key or code, "windowsVirtualKeyCode": vk})
    def mouse(self, typ, x, y, button="none", buttons=0): self.call("Input.dispatchMouseEvent", {"type": typ, "x": x, "y": y, "button": button, "buttons": buttons, "clickCount": 1 if typ != "mouseMoved" else 0})

class Browser:
    def __init__(self, port=None, profile="/tmp/hw-prof", extra=()):
        port = port or int(os.environ.get("HW_PORT", "9377")); self.port = port
        self.p = subprocess.Popen([CHROME, "--headless=new", "--no-sandbox", "--remote-debugging-port=%d" % port, "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check",
                                   "--autoplay-policy=no-user-gesture-required", "--mute-audio", "--window-size=1280,720", "--disable-background-timer-throttling",
                                   "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows", "--remote-allow-origins=*"] + list(extra) + os.environ.get("HW_CHROME_ARGS", "").split() + ["about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try: urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=1); break
            except Exception: time.sleep(0.1)
    def tab(self, url="about:blank"):
        req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (self.port, url), method="PUT")
        info = json.loads(urllib.request.urlopen(req).read()); t = Tab(info["webSocketDebuggerUrl"]); t.init(); return t
    def close(self):
        self.p.terminate()
        try: self.p.wait(5)
        except Exception: self.p.kill()
