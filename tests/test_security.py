"""Fixes from the code review: client address behind a proxy, login throttling, validation, masking,
schedule catch-up, Home Mode after a restart, config backup, no passwords in URLs."""
import asyncio, json, os, sys, time, types
from datetime import datetime, timedelta
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models")
import httpx
from app import main, auth, storage, validate
from app import config as config_mod
from app.config import config, camera_defaults
from app.synology import SynologyError
run = asyncio.run

class Req:
    def __init__(self, host="192.168.1.5", headers=None, login=True):
        self.cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")} if login else {}
        self.client = types.SimpleNamespace(host=host); self.headers = headers or {}
        self.url = types.SimpleNamespace(scheme="http", netloc="nas:8686")

# ---- client address: X-Forwarded-For only counts when the caller is a proxy on the home network
assert auth.real_ip("192.168.1.5", None) == "192.168.1.5"
assert auth.real_ip("172.17.0.1", "93.184.216.9") == "93.184.216.9"                    # via the NAS reverse proxy
assert auth.real_ip("172.17.0.1", "10.0.0.7, 93.184.216.9") == "93.184.216.9"          # the proxy's own entry is last
assert auth.real_ip("93.184.216.9", "192.168.1.5") == "93.184.216.9"                   # spoofed from the internet: ignored
assert auth.real_ip("172.17.0.1", "garbage") == "" and not auth.is_private("")
assert auth.real_ip("172.17.0.1", "93.184.216.9:4711") == "93.184.216.9"
assert main.client_ip(Req("93.184.216.9", {"x-forwarded-for": "192.168.1.5"})) == "93.184.216.9"
assert main.is_https(Req("172.17.0.1", {"x-forwarded-for": "93.184.216.9", "x-forwarded-proto": "https"}))
assert not main.is_https(Req("93.184.216.9", {"x-forwarded-for": "1.2.3.4", "x-forwarded-proto": "https"}))
assert main.base_url(Req("172.17.0.1", {"x-forwarded-for": "93.184.216.9", "x-forwarded-proto": "https", "host": "argus.example.com"})) == "https://argus.example.com"
assert main.base_url(Req("192.168.1.5", {"host": "nas:8686"})) == "http://nas:8686"
assert main.base_url(Req("192.168.1.5", {"host": "evil\"><script>"})) == "http://nas:8686"

# ---- setup from the internet is refused, also with a forged header; a failed setup stores nothing
for r in (Req("93.184.216.9", login=False), Req("93.184.216.9", {"x-forwarded-for": "192.168.1.5"}, login=False),
          Req("172.17.0.1", {"x-forwarded-for": "93.184.216.9"}, login=False)):
    try: run(main.setup(r, {"url": "https://evil.example", "user": "u", "password": "p"})); raise SystemExit("setup from outside")
    except main.HTTPException as e: assert e.status_code == 403
async def boom(): raise SynologyError(400, "wrong password")
main.ss.list_cameras = boom
try: run(main.setup(Req(login=False), {"url": "https://nas.local:5001", "user": "u", "password": "secret"})); raise SystemExit("x")
except main.HTTPException as e: assert e.status_code == 400
assert config.get("synology", "url") == "" and config.get("synology", "password") == "" and not config.get("setup_done")

# ---- login throttling: per address and per account (so rotating addresses does not help)
config.update(lambda d: (d.__setitem__("setup_done", True), d["auth"].__setitem__("allowed_users", ["anna"]),
                         d["synology"].update(url="https://nas.local:5001", user="svc", password="pw"),
                         d.__setitem__("cameras", {"Yard": camera_defaults("Yard", 5)})))
async def bad_login(url, verify, user, pw, otp=None): raise SynologyError(400, "wrong")
main.dsm_login_check = bad_login
main._fails.clear(); codes = []
for i in range(14):
    try: run(main.login(Req(f"93.184.216.{i}", login=False), {"user": "Anna", "password": "x"}))
    except main.HTTPException as e: codes.append(e.status_code)
assert codes[:10] == [401] * 10 and codes[10:] == [429] * 4, codes
main._fails.clear(); codes = []
for i in range(7):
    try: run(main.login(Req("93.184.216.50", login=False), {"user": f"user{i}", "password": "x"}))
    except main.HTTPException as e: codes.append(e.status_code)
assert codes == [403] * 5 + [429] * 2, codes
main._fails.clear()
print("A address and login OK")

# ---- the DSM password travels in the request body, never in the URL
from app.synology import dsm_login_check, SurveillanceStation
httpx.CALLS.clear(); httpx.RESPONSES[:] = [httpx.Response(200, {"success": True, "data": {"sid": "S"}})]
run(dsm_login_check("https://nas.local:5001", True, "anna", "hemligt-lösen", None))
c = httpx.CALLS[0]; assert all("hemligt" not in json.dumps(x.get("url")) + json.dumps(x.get("params")) for x in httpx.CALLS)
assert c["method"] == "POST" and c["data"]["passwd"] == "hemligt-lösen"
import logging; assert logging.getLogger("httpx").level >= logging.WARNING
assert "token=abc" not in main.safe_error(RuntimeError("failed for url https://api.example/bot123:abc/send?token=abc"))
print("B no secrets in URLs OK")

# ---- values are checked before they are saved
R = Req()
for body, field in [({"threshold": "abc"}, "threshold"), ({"types": "person"}, "types"), ({"zones": [{"x1": "a"}]}, "zones"),
                    ({"min_width": float("nan")}, "min_width"), ({"cooldown_s": True}, "cooldown_s")]:
    try: run(main.put_camera("Yard", R, body)); raise SystemExit(f"accepted {body}")
    except main.HTTPException as e: assert e.status_code == 400 and field in e.detail, (e.detail, field)
run(main.put_camera("Yard", R, {"threshold": "150", "types": ["person", "unicorn"], "min_width": "", "max_snapshots": 99,
                                 "zones": [{"x1": 0.9, "y1": 0.1, "x2": 0.2, "y2": 0.5, "mode": "x", "evil": 1}], "hack": 1}))
c = config.get("cameras")["Yard"]
assert c["threshold"] == 95 and c["types"] == ["person"] and c["min_width"] is None and c["max_snapshots"] == 5 and "hack" not in c
assert c["zones"] == [{"x1": 0.2, "y1": 0.1, "x2": 0.9, "y2": 0.5, "mode": "contains"}]
for body, field in [({"defaults": {"threshold": "x"}}, "threshold"), ({"storage": {"days_to_keep": "many"}}, "days_to_keep"),
                    ({"synology": {"url": "ftp://x"}}, "url"), ({"public_url": "javascript:alert(1)"}, "public_url"),
                    ({"mode_auto": {"schedule": [{"time": "25:99", "mode": "night"}]}}, "schedule"), ({"modes": "x"}, "modes"),
                    ({"detector": {"model": "../../etc"}}, "model")]:
    try: run(main.put_settings(R, body)); raise SystemExit(f"accepted {body}")
    except main.HTTPException as e: assert e.status_code == 400 and field in e.detail, (e.detail, field)
run(main.put_settings(R, {"defaults": {"threshold": 5, "max_snapshots": "3"}, "storage": {"days_to_keep": 99999}}))
assert config.get("defaults", "threshold") == 10 and config.get("defaults", "max_snapshots") == 3 and config.get("storage", "days_to_keep") == 3650
assert config.get("defaults", "cooldown_s") is not None            # untouched fields stay
# a broken import file is refused and changes nothing
before = json.dumps(config.get(), sort_keys=True)
for bad in ({"_synoargus": {}, "cameras": {"A": {"threshold": []}}, "notifiers": []},
            {"_synoargus": {}, "cameras": {"A": {}}, "notifiers": ["x"]},
            {"_synoargus": {}, "cameras": {"A": {}}, "notifiers": [{"type": "nope"}]},
            {"_synoargus": {}, "cameras": {"A": {}}, "notifiers": [], "defaults": "x"}):
    try: run(main.import_settings(R, bad)); raise SystemExit(f"imported {bad}")
    except main.HTTPException as e: assert e.status_code == 400
assert json.dumps(config.get(), sort_keys=True) == before
r = run(main.import_settings(R, {"_synoargus": {}, "cameras": {"A": {"threshold": 70, "bogus": 1}}, "notifiers": [], "secret": "stolen",
                               "setup_done": False, "unknown_key": {"x": 1}, "auth": {"allowed_users": ["bob"]}}))
assert config.get("secret") != "stolen" and config.get("setup_done") and "unknown_key" not in config.get()
assert config.get("cameras")["A"]["threshold"] == 70 and "bogus" not in config.get("cameras")["A"]
assert "anna" in config.get("auth", "allowed_users")               # whoever imports is not locked out
print("C validation OK")

# ---- raw rule data for troubleshooting hides passwords and other rules' addresses
raw = {"actRule": [{"name": "Other", "actions": [{"extUrl": "http://192.0.2.50:80/api/app/x/station/SERIAL123/homemode_on", "userName": "admin", "password": "p4ss"}],
                    "blob": json.dumps({"password": "inner", "url": "https://hook.example/abc/secret"})},
                   {"name": "SynoArgus - Yard", "actions": [{"extUrl": "http://nas:8686/api/trigger/Yard?token=TOPSECRET", "password": ""}]}]}
m = json.dumps(main._mask_rules(raw))
assert "p4ss" not in m and "SERIAL123" not in m and "TOPSECRET" not in m and "inner" not in m and "abc/secret" not in m and "admin" not in m
assert "http://192.0.2.50:80/***" in m and "/api/trigger/Yard?token=***" in m and "Other" in m
print("D masking OK")

# ---- schedule: missed changes are caught up, but never over a later manual change
M = main.modes
config.update(lambda d: d["mode_auto"].update(homemode={"enabled": False, "on": "home", "off": "away"},
    schedule=[{"time": "01:00", "days": list(range(7)), "mode": "night"}, {"time": "06:00", "days": list(range(7)), "mode": "home"}]))
day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=3)
M.set("away", "manual"); M._sched_seen = (day + timedelta(minutes=50)).timestamp()
M.check_schedule(day + timedelta(hours=1, minutes=7)); assert M.current() == "night"       # the NAS was slow at 01:00: still done
M._sched_seen = (day + timedelta(hours=5)).timestamp()
M.check_schedule(day + timedelta(hours=9)); assert M.current() == "home"                   # container was down 05–09
# both missed: applied in order, the last one wins
M.set("away", "manual"); M._sched_seen = (day + timedelta(days=1, minutes=30)).timestamp()
M.check_schedule(day + timedelta(days=1, hours=8)); assert M.current() == "home"
# a manual change after the missed time is not overwritten
config.update(lambda d: d["mode"].update(current="away", source="manual", since=(day + timedelta(days=2, hours=2)).timestamp()))
M._sched_seen = (day + timedelta(days=2, minutes=30)).timestamp()
M.check_schedule(day + timedelta(days=2, hours=3)); assert M.current() == "away"
# more than a day behind: only the last 24 h count, and nothing is repeated
M._sched_seen = (day - timedelta(days=30)).timestamp()
config.update(lambda d: d["mode"].update(since=0)); M.check_schedule(day + timedelta(days=3, hours=7)); assert M.current() == "home"
M.set("away", "manual"); config.update(lambda d: d["mode"].update(since=0))
M.check_schedule(day + timedelta(days=3, hours=7, minutes=1)); assert M.current() == "away"
print("E schedule catch-up OK")

# ---- Home Mode after a restart does not overwrite a mode set by hand
import app.modes as modes_mod
HM = {"on": True}
async def hm_get(): return dict(HM)
main.ss.homemode_get = hm_get; modes_mod.find_homemode = lambda raw: raw["on"]
config.update(lambda d: d["mode_auto"]["homemode"].update(enabled=True))
M.homemode = None; run(M.poll_homemode()); assert M.current() == "home" and config.get("mode")["hm_state"] is True
M.set("night", "manual")
M2 = modes_mod.ModeManager(config, main.ss, lambda *a: None)       # "restart"
assert M2.homemode is True
run(M2.poll_homemode()); assert M2.current() == "night"
HM["on"] = False; run(M2.poll_homemode()); assert M2.current() == "away"       # a real change still applies
print("F Home Mode restart OK")

# ---- config.json: the previous version is kept and used if the file is damaged
path = config_mod.CONFIG_PATH
config.update(lambda d: d.__setitem__("public_url", "http://one")); config.update(lambda d: d.__setitem__("public_url", "http://two"))
assert json.load(open(path + ".bak"))["public_url"] == "http://one" and oct(os.stat(path).st_mode)[-3:] == "600"
open(path, "w").write("{ broken")
c2 = config_mod.Config(); assert c2.get("public_url") == "http://one" and c2.get("setup_done")
print("ALL security OK")
