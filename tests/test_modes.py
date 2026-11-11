import asyncio, json, os, sys, types, time
from datetime import datetime
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data43"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models43")

run = asyncio.run
from app import main, auth, storage, notifiers
from app.config import config, camera_defaults
storage.init()
def setup(d):
    d["setup_done"] = True; d["auth"]["allowed_users"] = ["anna"]
    d["cameras"] = {"Out": {**camera_defaults("Out", 5)}, "Hall": {**camera_defaults("Hall", 7), "modes": ["night", "away"]}}
    d["notifiers"] = [{**notifiers.new_notifier("telegram"), "id": "tg", "modes": ["night", "away"]},
                      {**notifiers.new_notifier("webhook"), "id": "hm", "url": "http://homey/x"}]
config.update(setup)
tok = config.get("trigger_token")
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; base_url = "http://nas:8686/"; url = types.SimpleNamespace(scheme="http")
R = Req(); M = main.modes

# standardnamn och upplösning (sv/en/id)
assert M.current() == "away" and M.name("night") == "Natt"
assert M.resolve("NATT") == "night" and M.resolve("home") == "home" and M.resolve("Away") == "away" and M.resolve("x") is None
# webhook
r = run(main.mode_webhook(token=tok, mode="hemma")); assert r["mode"] == "home" and r["name"] == "Hemma"
assert config.get("mode")["source"] == "webhook"
try: run(main.mode_webhook(token=tok, mode="party")); raise SystemExit("x")
except main.HTTPException as e: assert e.status_code == 404
try: run(main.mode_webhook(token="fel", mode="home")); raise SystemExit("x")
except main.HTTPException as e: assert e.status_code == 403
print("webhook OK")

# kamera Hall larmar inte i Hemma -> resultat "mode", analyseras inte
res = run(main.trigger("Hall", token=tok)); assert res["result"] == "mode"
tr_ = run(main.camera_triggers("Hall", R, since=0))["triggers"][-1]; assert tr_["mode"] == "Hemma"
assert any("ignoreras" in x["text"] and "Hemma" in x["text"] for x in main.engine.recent), main.engine.recent[:3]
# Out larmar i alla lägen -> accepterad (analys startar, men utan modell -> fel, det spelar ingen roll här)
async def go(): return await main.trigger("Out", token=tok)
res = run(go()); assert res["result"] == "accepted"
print("camera modes OK")

# notifierare filtreras på läge
tg, hm = config.get("notifiers")
assert not notifiers.applies(tg, "Out", ["person"], "home") and notifiers.applies(tg, "Out", ["person"], "night")
assert notifiers.applies(hm, "Out", ["person"], "home")
print("notifier modes OK")

# schema
config.update(lambda d: d["mode_auto"].__setitem__("schedule", [{"time": "23:00", "days": [0, 1, 2, 3, 4], "mode": "night"}]))
M.check_schedule(_env.day(0, 23, 0))   # måndag
assert M.current() == "night" and config.get("mode")["source"] == "schedule"
M.set("home", "manual"); M.check_schedule(_env.day(0, 23, 0)); assert M.current() == "home"  # körs bara en gång per dag
M.check_schedule(_env.day(5, 23, 0)); assert M.current() == "home"  # lördag inte med
print("schedule OK")

# Home Mode
state = {"on": True}
async def hm_get(): return {"on": state["on"], "reason": 0}
main.ss.homemode_get = hm_get
config.update(lambda d: d["mode_auto"].__setitem__("homemode", {"enabled": True, "on": "home", "off": "away"}))
M.set("night", "manual")
run(M.poll_homemode()); assert M.current() == "home" and M.homemode is True
M.set("night", "manual"); run(M.poll_homemode()); assert M.current() == "night"  # ingen ändring i Home Mode -> manuellt gäller
state["on"] = False; run(M.poll_homemode()); assert M.current() == "away"
async def hm_err(): raise main.SynologyError(105)
main.ss.homemode_get = hm_err; run(M.poll_homemode()); assert M.homemode_error and M.current() == "away"
print("homemode OK")

# ta bort ett läge -> städas från kameror, notifierare, schema
cur = config.get("modes")
run(main.put_settings(R, {"modes": [m for m in cur if m["id"] != "night"] + [{"id": "mx", "name": "Semester"}]}))
assert config.get("cameras")["Hall"]["modes"] == ["away"] and config.get("notifiers")[0]["modes"] == ["away"]
assert config.get("mode_auto")["schedule"] == [] and M.resolve("semester") == "mx"
try: run(main.put_settings(R, {"modes": []})); raise SystemExit("x")
except main.HTTPException as e: assert e.status_code == 400
r = run(main.mode_set(R, {"mode": "Semester"})); assert r["current"] == "mx" and r["name"] == "Semester"
print("settings OK")

# engelska standardnamn
config.update(lambda d: d.__setitem__("language", "en")); assert M.name("home") == "Home" and M.resolve("Hemma") == "home"
# regler skapas aktiva i Home Mode
rule = main._new_rule("Out", 5, "http://x/api/trigger/Out?token=t"); assert rule["activeInHomeMode"] is True
print("ALL 0.4.3 OK")
