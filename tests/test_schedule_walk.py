import asyncio, json, os, sys, types, time, shutil
from datetime import datetime
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data51"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models51")

from PIL import Image, ImageDraw
from app import main, auth, storage, notifiers
from app import calibration as C
from app.config import config, camera_defaults
storage.init(); C.init_db()
config.update(lambda d: (d.__setitem__("setup_done", True), d["auth"].__setitem__("allowed_users", ["anna"]),
                         d.__setitem__("cameras", {"Out": camera_defaults("Out", 5), "Hall": camera_defaults("Hall", 7)})))
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; base_url = "http://nas:8686/"; url = types.SimpleNamespace(scheme="http")
R = Req(); M = main.modes
run = asyncio.run

# ================= A. schema med återgång (B-beteende)
HM = {"state": False}
async def hm_get(): return {"on": HM["state"]}
main.ss.homemode_get = hm_get
import app.modes as modes_mod
modes_mod.find_homemode = lambda raw: raw["on"]
config.update(lambda d: d.__setitem__("mode_auto", {"homemode": {"enabled": True, "on": "home", "off": "away"},
    "schedule": [{"time": "01:00", "days": list(range(7)), "mode": "night"},
                 {"time": "06:00", "days": list(range(7)), "mode": "@homemode"}]}))
M.homemode = None
run(M.poll_homemode()); assert M.current() == "away"               # Home Mode av -> Borta
HM["state"] = True; run(M.poll_homemode()); assert M.current() == "home"
M.check_schedule(_env.day(1, 1, 0)); assert M.current() == "night"
i = M.info(); assert i["hold"] and i["previous"] == "home"
HM["state"] = False; run(M.poll_homemode()); assert M.current() == "night", "Home Mode ska vänta"
M.check_schedule(_env.day(1, 1, 0)); assert M.current() == "night"  # samma minut körs inte två gånger
M.check_schedule(_env.day(1, 6, 0)); assert M.current() == "away", M.current()  # följer Home Mode (av)
assert not M.info()["hold"] and M.info()["previous"] is None
# Home Mode följs igen direkt efter återgång
HM["state"] = True; run(M.poll_homemode()); assert M.current() == "home"
print("A1 Följ Home Mode OK")

# manuellt byte under perioden avbryter väntan
M.check_schedule(_env.day(2, 1, 0)); assert M.current() == "night" and M.info()["hold"]
M.set("away", "manual"); assert not M.info()["hold"]
HM["state"] = False; run(M.poll_homemode()); assert M.current() == "away"
HM["state"] = True; run(M.poll_homemode()); assert M.current() == "home"   # följs direkt (ingen väntan)
# webhook avbryter också
M.check_schedule(_env.day(3, 1, 0)); assert M.info()["hold"]
r = run(main.mode_webhook(token=config.get("trigger_token"), mode="borta")); assert r["mode"] == "away" and not M.info()["hold"]
M.check_schedule(_env.day(3, 6, 0)); assert M.current() == "home"  # återgång: Home Mode på
print("A2 manuellt/webhook avbryter OK")

# föregående läge, två schemabyten i rad behåller läget före perioden
config.update(lambda d: d["mode_auto"].__setitem__("schedule", [
    {"time": "01:00", "days": list(range(7)), "mode": "night"},
    {"time": "03:00", "days": list(range(7)), "mode": "away"},
    {"time": "06:00", "days": list(range(7)), "mode": "@previous"}]))
M.set("home", "manual")
M.check_schedule(_env.day(4, 1, 0)); M.check_schedule(_env.day(4, 3, 0))
assert M.current() == "away" and M.info()["previous"] == "home"
M.check_schedule(_env.day(4, 6, 0)); assert M.current() == "home" and not M.info()["hold"]
# Följ Home Mode utan Home Mode påslaget -> föregående
config.update(lambda d: (d["mode_auto"]["homemode"].__setitem__("enabled", False),
    d["mode_auto"].__setitem__("schedule", [{"time": "01:00", "mode": "night"}, {"time": "06:00", "mode": "@homemode"}])))
run(M.poll_homemode())
M.check_schedule(_env.day(5, 1, 0)); M.check_schedule(_env.day(5, 6, 0)); assert M.current() == "home"
print("A3 föregående läge OK")

# inställningar: specialvärden behålls när lägen sparas
run(main.put_settings(R, {"modes": [{"id": "home", "name": ""}, {"id": "night", "name": ""}, {"id": "away", "name": ""}],
                          "mode_auto": {"homemode": {"enabled": True, "on": "home", "off": "away"},
                                        "schedule": [{"time": "01:00", "mode": "night"}, {"time": "06:00", "mode": "@homemode"},
                                                     {"time": "07:00", "mode": "@previous"}, {"time": "08:00", "mode": "gone"}]}}))
assert [e["mode"] for e in config.get("mode_auto", "schedule")] == ["night", "@homemode", "@previous"], config.get("mode_auto", "schedule")
st = run(main.state(R)); assert "hold" in st["mode"] and st["priority"] is None
print("A4 inställningar OK")

# ================= B. kalibrering: en i taget, förbigång 3 bilder/s, prioritet före larm
MD = {"sensitivity": {"value": 95, "minValue": 1, "maxValue": 99, "ssCap": True}, "threshold": {"value": 5, "minValue": 1, "maxValue": 99, "ssCap": True}, "region": "1" * 1200, "source": 1}
async def mget(cid): return json.loads(json.dumps(MD))
main.ss.motion_get = mget
grabs = []
async def grab(cam):
    grabs.append((time.time(), cam["name"]))
    await asyncio.sleep(0.02)
    img = Image.new("RGB", (640, 360), (90, 110, 90))
    x = int((time.time() * 300) % 500); ImageDraw.Draw(img).rectangle([x, 100, x + 60, 300], fill=(235, 235, 235))
    return img
AI = {"n": 0, "who": []}
def analyse(cam, img):
    time.sleep(0.5)            # ungefär J3455 med yolox_s
    AI["n"] += 1; AI["who"].append((time.time(), cam["name"]))
    v = [{"label": "person", "confidence": 90, "x1": 0, "y1": 100, "x2": 640, "y2": 300, "valid": True}]
    return v, v
main.engine.grab = grab; main.engine.analyse = analyse; main.engine.ensure_model = lambda: None
sent = []
async def fake_notify(name, types, dets, jpeg, event_id=None, rel=None, only=None): sent.append((time.time(), name)); return []
main.engine.notify = fake_notify
C.WALK_SECONDS = 6
config.update(lambda d: d["mode"].__setitem__("current", "home"))

async def flow():
    await main.calibration_post("Out", R, {"action": "start", "hours": 12})
    try:
        await main.calibration_post("Hall", R, {"action": "start", "hours": 12}); raise SystemExit("två samtidigt")
    except main.HTTPException as e:
        assert e.status_code == 409 and "Out" in e.detail, e.detail
    g = await main.calibration_get("Hall", R); assert g["active"] == "Out" and g["run"] is None
    t0 = time.time()
    await main.calibration_post("Out", R, {"action": "walk"})
    assert main.engine.priority_active()
    await asyncio.sleep(1.0)
    # larm från en annan kamera under förbigången: bild tas direkt, analys efteråt
    tr = time.time(); res = await main.engine.trigger("Hall"); assert res == "accepted"
    await asyncio.sleep(0.3)
    hall_grab = [t for t, n in grabs if n == "Hall"]; assert hall_grab and hall_grab[0] - tr < 0.3, "bilden ska tas direkt"
    g = await main.calibration_get("Out", R); w = g["run"]["walk"]; assert w and w["frames"] > 0
    st = await main.status(R); assert st["priority"] and st["priority"]["camera"] == "Out" and st["priority"]["left"] > 0
    while main.calib.walking():
        await asyncio.sleep(0.1)
    t_end = time.time()
    await asyncio.sleep(1.5)
    hall_ai = [t for t, n in AI["who"] if n == "Hall"]
    assert hall_ai and hall_ai[0] >= t_end - 0.6, ("larmets analys ska vänta", hall_ai, t_end)
    assert sent and sent[0][1] == "Hall"
    assert not main.engine.priority_active()
    frames = len([1 for t, n in grabs if n == "Out" and t0 <= t <= t_end])
    info = main.calib.walk_info
    print(f"B förbigång: {info['frames']} bilder på {C.WALK_SECONDS} s ({info['frames']/C.WALK_SECONDS:.1f}/s), {info['analysed']} analyserade")
    assert 2.5 * C.WALK_SECONDS <= info["frames"] <= 3 * C.WALK_SECONDS + 2
    assert info["analysed"] >= C.WALK_SECONDS and info["analysed"] < info["frames"]
    rep = (await main.calibration_get("Out", R))["run"]["report"]
    assert rep["walk_pairs"] == info["analysed"] and rep["target_pairs"] == info["analysed"], rep
    # samma bildpar på 1 s: kolla tidsavstånd i rådata
    smp = main.calib._samples(main.calib._run("Out")["id"]); assert all(s["walk"] for s in smp if s["kind"] == "pair")
    # under förbigång hoppar reaktionen för den kalibrerade kameran över AI
    await main.calibration_post("Out", R, {"action": "walk"})
    n0 = AI["n"]; await main.calib.on_reaction("Out", config.get("cameras")["Out"])
    # stopp avbryter förbigången och släpper prioriteten
    await main.calibration_post("Out", R, {"action": "stop"})
    await asyncio.sleep(0.2)
    assert not main.calib.walking() and not main.engine.priority_active()
    g = await main.calibration_get("Hall", R); assert g["active"] is None
    await main.calibration_post("Hall", R, {"action": "start", "hours": 12})   # nu går det
    assert (await main.calibration_get("Out", R))["run"]["status"] == "stopped"   # rapporten för Out finns kvar
    await main.calibration_post("Hall", R, {"action": "stop"})
run(flow())
print("B kalibrering OK")
print("ALL 0.5.1 OK")
