"""
PointOne desktop app (Windows) — alert popup + POS webview + device auth.

Flow:
  1. First run: no saved device token -> auth screen. Staff enters email.
  2. App POSTs device info (hostname, IP, MAC, geo location) to
     store.chaikaapi.co.in  ->  approval request created for that store.
  3. Admin approves on the store.chaikaapi.co.in page.
  4. App polls status -> receives device token -> saved in %APPDATA%\\pointone.
  5. Main screen: POS tab (pos.storeos.co.in in the webview) + Alerts tab.

Run:
  python pointone.py            # normal app
  python pointone.py --test     # auth bypass (dev), auto device token
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid

import requests

try:
    import webview
except ImportError:
    webview = None

IS_WIN = sys.platform == "win32"

APP_NAME = "PointOne"
POS_URL = "https://pos.storeos.co.in"
API_BASE = "https://store.chaikaapi.co.in"          # ckapp backend
AUTH_REQUEST_URL = f"{API_BASE}/pointone/auth/request"
AUTH_STATUS_URL = f"{API_BASE}/pointone/auth/status"
ALERTS_POLL_URL = f"{API_BASE}/pointone/alerts/pending"

if IS_WIN:
    APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
else:
    APPDATA = os.path.expanduser("~")
CONFIG_DIR = os.path.join(APPDATA, "pointone")
TOKEN_FILE = os.path.join(CONFIG_DIR, "device.json")
ALERT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alert.py")


# ---------------------------------------------------------------- device info
def device_info():
    info = {
        "hostname": socket.gethostname(),
        "os": sys.platform,
        "os_version": os.environ.get("OS", ""),
        "mac": "-".join(f"{(uuid.getnode() >> i) & 0xFF:02x}" for i in range(40, -1, -8)),
    }
    # local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["local_ip"] = s.getsockname()[0]
        s.close()
    except Exception:
        info["local_ip"] = ""
    # public IP + rough location (best effort, never blocks auth)
    try:
        r = requests.get("https://ipapi.co/json/", timeout=6)
        j = r.json()
        info["public_ip"] = j.get("ip", "")
        info["city"] = j.get("city", "")
        info["region"] = j.get("region", "")
        info["country"] = j.get("country_name", "")
        info["location"] = f"{j.get('latitude','')},{j.get('longitude','')}"
    except Exception:
        info["public_ip"] = info["city"] = info["region"] = ""
        info["country"] = info["location"] = ""
    return info


def load_token():
    try:
        with open(TOKEN_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def save_token(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------- alert popup
def run_alert(title, text, image=None, interval=10, test=False):
    """Run alert.py as its own process (so exit code 0=ACK, 1=Cancel is real)."""
    cmd = [sys.executable, ALERT_SCRIPT, "--title", title or "ALERT",
           "--text", text or "Check this", "--interval", str(interval)]
    if image:
        cmd += ["--image", image]
    if test:
        cmd += ["--test"]
    if getattr(sys, "frozen", False):
        # packaged exe: re-invoke ourselves in --alert mode (runs alert.py in-process)
        cmd = [sys.executable, "--alert", "--title", title or "ALERT",
               "--text", text or "Check this", "--interval", str(interval)]
        if image:
            cmd += ["--image", image]
        if test:
            cmd += ["--test"]
    try:
        r = subprocess.run(cmd, creationflags=0x00000008 if IS_WIN else 0)
        return r.returncode
    except Exception as e:
        return -1


# ---------------------------------------------------------------- API (js <-> python)
class Api:
    def __init__(self):
        self.pending_request_id = None
        self.stop_polling = threading.Event()

    # --- auth ---
    def auth_status(self):
        tok = load_token()
        if tok:
            return {"authenticated": True, "email": tok.get("email", ""), "store": tok.get("store", "")}
        return {"authenticated": False}

    def request_approval(self, email):
        email = (email or "").strip().lower()
        if not email or "@" not in email:
            return {"ok": False, "error": "Enter a valid email"}
        try:
            r = requests.post(AUTH_REQUEST_URL, json={"email": email, "device": device_info()}, timeout=15)
            if r.status_code != 200:
                return {"ok": False, "error": f"Server said {r.status_code}: {r.text[:120]}"}
            data = r.json()
            if not data.get("ok"):
                return {"ok": False, "error": data.get("error", "Request rejected")}
            self.pending_request_id = data["request_id"]
            self.stop_polling.clear()
            threading.Thread(target=self._poll_approval, args=(data["request_id"],), daemon=True).start()
            return {"ok": True, "request_id": data["request_id"]}
        except Exception as e:
            return {"ok": False, "error": f"Cannot reach server: {e}"}

    def _poll_approval(self, request_id):
        for _ in range(360):  # up to ~30 min
            if self.stop_polling.is_set():
                return
            time.sleep(5)
            try:
                r = requests.get(AUTH_STATUS_URL, params={"request_id": request_id}, timeout=10)
                if r.status_code != 200:
                    continue
                data = r.json()
                if data.get("status") == "approved":
                    save_token({"email": data.get("email", ""), "store": data.get("store", ""),
                                "token": data.get("token", ""), "approved_at": data.get("approved_at", "")})
                    if webview:
                        webview.windows[0].evaluate_js("window.__setView('main')")
                    return
                if data.get("status") in ("denied", "expired"):
                    if webview:
                        webview.windows[0].evaluate_js(
                            f"window.__authResult({json.dumps(data.get('status'))})")
                    return
            except Exception:
                continue

    def cancel_approval(self):
        self.stop_polling.set()
        self.pending_request_id = None
        return {"ok": True}

    # --- views ---
    def set_view(self, view):
        if webview:
            webview.windows[0].evaluate_js(f"window.__setView({json.dumps(view)})")
        return {"ok": True}

    def open_pos(self):
        if webview:
            webview.windows[0].load_url(POS_URL)
        return {"ok": True}

    def back_home(self):
        if webview:
            webview.windows[0].load_url(APP_HTML_URL)
        return {"ok": True}

    # --- alerts ---
    def test_alert(self):
        code = run_alert("TEST ALERT", "PointOne alert popup test", interval=5, test=True)
        return {"ok": True, "code": code}

    def device_json(self):
        return device_info()


# ---------------------------------------------------------------- HTML UI
APP_HTML_URL = None  # set after window creation (data URL)

AUTH_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
body{font-family:'Segoe UI',sans-serif;background:#17181c;color:#d5d5d5;display:flex;
justify-content:center;align-items:center;height:100vh;margin:0}
.card{background:#202228;border:1px solid #2c2d33;border-radius:10px;padding:32px;width:360px;text-align:center}
h1{font-size:20px;font-weight:600;color:#e8e8e8;margin:0 0 6px}
p.sub{font-size:12px;color:#8a8a92;margin:0 0 20px}
input{width:100%;box-sizing:border-box;padding:10px 12px;border-radius:6px;border:1px solid #3a3b42;
background:#17181c;color:#e8e8e8;font-size:14px;outline:none}
button{margin-top:14px;width:100%;padding:11px;border:0;border-radius:6px;background:#3a6ea5;
color:#fff;font-size:14px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5}
#msg{font-size:12px;color:#8a8a92;margin-top:14px;min-height:30px;line-height:1.5}
.wait{display:none;margin-top:18px;font-size:13px;color:#b8b8b8}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#e0a53a;margin-right:8px;
animation:p 1.2s infinite alternate}@keyframes p{to{opacity:.3}}
</style></head><body><div class="card">
<h1>PointOne</h1><p class="sub">Device activation — store approval required</p>
<div id="step1">
<input id="email" placeholder="store staff email" onkeydown="if(event.key==='Enter')go()">
<button id="btn" onclick="go()">Request approval</button><div id="msg"></div></div>
<div class="wait" id="wait"><span class="dot"></span>Waiting for admin approval on store.chaikaapi.co.in…</div>
</div><script>
async function go(){
 const b=document.getElementById('btn');b.disabled=true;b.textContent='Sending…';
 const r=await pywebview.api.request_approval(document.getElementById('email').value);
 if(!r.ok){document.getElementById('msg').textContent=r.error;b.disabled=false;b.textContent='Request approval';return;}
 document.getElementById('step1').style.display='none';
 document.getElementById('wait').style.display='block';
}
window.__authResult=function(status){
 document.getElementById('wait').style.display='none';
 document.getElementById('step1').style.display='block';
 document.getElementById('msg').textContent='Request '+status+'. Ask admin, then try again.';
};
</script></body></html>"""

MAIN_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
body{font-family:'Segoe UI',sans-serif;background:#17181c;color:#d5d5d5;margin:0;display:flex;flex-direction:column;height:100vh}
header{display:flex;align-items:center;gap:10px;padding:10px 16px;background:#202228;border-bottom:1px solid #2c2d33}
.h{font-weight:600;color:#e8e8e8;font-size:14px;margin-right:auto}
.tab{padding:7px 16px;border-radius:6px;border:1px solid #3a3b42;background:transparent;color:#b8b8b8;
font-size:13px;cursor:pointer}
.tab.on{background:#3a6ea5;border-color:#3a6ea5;color:#fff}
main{flex:1;display:flex;justify-content:center;align-items:center}
.panel{display:none;text-align:center}
.panel.on{display:block}
h2{font-size:18px;font-weight:600;color:#e8e8e8;margin:0 0 8px}
p{font-size:13px;color:#8a8a92;margin:0 0 22px}
button.big{padding:12px 26px;border:0;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;color:#fff;margin:0 6px}
.pos{background:#2e7d32}.alert{background:#555}.red{background:#a53a3a}
footer{padding:8px 16px;font-size:11px;color:#5c5c63;border-top:1px solid #2c2d33}
</style></head><body>
<header><span class="h">PointOne</span>
<button class="tab" id="t-pos" onclick="setv('pos')">POS</button>
<button class="tab" id="t-alerts" onclick="setv('alerts')">Alerts</button>
<button class="tab" id="t-info" onclick="setv('info')">This device</button></header>
<main>
<div class="panel" id="p-pos"><h2>POS</h2><p>Opens pos.storeos.co.in inside this window.</p>
<button class="big pos" onclick="pywebview.api.open_pos()">Open POS</button></div>
<div class="panel" id="p-alerts"><h2>Alerts</h2><p>Popup alert engine — same as the old alerter.</p>
<button class="big alert" onclick="pywebview.api.test_alert()">Send test alert</button></div>
<div class="panel" id="p-info"><h2>This device</h2><p id="devinfo">…</p>
<button class="big red" onclick="deactivate()">Deactivate device</button></div>
</main><footer id="who"></footer>
<script>
function setv(v){['pos','alerts','info'].forEach(x=>{
 document.getElementById('p-'+x).classList.toggle('on',x===v);
 document.getElementById('t-'+x).classList.toggle('on',x===v);});
 if(v==='info')pywebview.api.device_json().then(d=>{
  document.getElementById('devinfo').textContent=
   d.hostname+' · local '+d.local_ip+' · public '+(d.public_ip||'')+' · '+(d.city||'');});}
window.__setView=function(v){
 if(v==='main'){location.reload();}
 else setv(v);};
async function deactivate(){await pywebview.api.cancel_approval();
 // token removal handled server-side; simple local signout:
 location.href='about:blank';}
pywebview.api.auth_status().then(s=>{
 document.getElementById('who').textContent=s.authenticated?
  ('Activated: '+s.email+(s.store?' · store '+s.store:'')):'';});
setv('pos');
</script></body></html>"""


# ---------------------------------------------------------------- main
def alert_entrypoint():
    """Packaged exe: `pointone.exe --alert ...` runs alert.py in this process."""
    sys.argv = ["alert.py"] + sys.argv[2:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import alert
    alert.main()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--alert":
        alert_entrypoint()
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="dev: skip auth")
    args = ap.parse_args()

    if args.test and not load_token():
        save_token({"email": "dev@test", "store": "dev", "token": "dev"})

    if webview is None:
        print("pywebview not installed"); sys.exit(2)

    api = Api()
    authenticated = bool(load_token())
    html = MAIN_HTML if authenticated else AUTH_HTML

    window = webview.create_window(APP_NAME, html=html, js_api=api,
                                   width=1100, height=720, min_size=(800, 560))
    # expose view switcher for out-of-band navigation (auth approval, etc.)
    def _on_loaded():
        pass
    window.events.loaded += _on_loaded
    webview.start()


if __name__ == "__main__":
    main()
