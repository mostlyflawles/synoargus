import asyncio, json, os, sys, types, time, random
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data50"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models50")

import numpy as np
from PIL import Image, ImageDraw
from app import calibration as C
random.seed(1)

# ---------- A. ren logik: simulerat dygn
LV = C.LEVELS
def lv_from(frac_at_16):  # avtagande fördelning över pixelnivåerna
    return [min(1.0, frac_at_16 * (16 / l) ** 1.3) for l in LV]
pairs = []
t0 = time.time() - 86400
for i in range(2880):   # var 30:e s i ett dygn
    ts = t0 + i * 30
    night = (i * 30 // 3600) % 24 < 6
    noise = random.uniform(0.0, 0.03) if not night else random.uniform(0.01, 0.06)  # natt brusigare
    pairs.append({"kind": "pair", "ts": ts, "levels": lv_from(noise), "target": False, "moving": False, "night": night, "walk": False})
for k in range(8):      # personer i rörelse: 8-25 % ändring
    ts = t0 + random.uniform(0, 86400)
    pairs.append({"kind": "pair", "ts": ts, "levels": lv_from(random.uniform(0.08, 0.25)), "target": True, "moving": True, "night": False, "walk": k < 3})
reacts = [{"kind": "reaction", "ts": t0 + random.uniform(0, 86400), "target": False, "night": False, "walk": False} for _ in range(130)]
reacts += [{"kind": "reaction", "ts": p["ts"] - 5, "target": True, "night": False, "walk": False} for p in pairs if p["target"]][:6]  # 2 personer missade
rep = C.build_report(pairs + reacts, 95, 5)
print("now: recall/noise", rep["proposal"]["recall_now"], round(rep["proposal"]["noise_now"], 3))
print("proposal:", {k: rep["proposal"][k] for k in ("sensitivity", "threshold", "recall", "noise")})
assert rep["enough"] and rep["full"] and rep["missed"] == 2 and rep["reactions"] == 136
assert rep["proposal"]["recall"] >= rep["proposal"]["recall_now"]
assert rep["proposal"]["noise"] < rep["proposal"]["noise_now"]
assert abs(rep["proposal"]["sensitivity"] - 95) <= 10 and abs(rep["proposal"]["threshold"] - 5) <= 10
assert 0.9 < rep["noise_share"] < 1 and sum(rep["hours"]) == 136
print("A logik OK, brusandel", round(rep["noise_share"], 2))

# bara brus -> ett steg mindre känsligt, markerat
r2 = C.build_report([p for p in pairs if not p["target"]] + reacts[:40], 95, 5)
p2 = r2["proposal"]; assert p2["only_noise"] and (95 - p2["sensitivity"]) + (p2["threshold"] - 5) <= 5 and not r2["full"]
# för lite data
r3 = C.build_report(pairs[:10], 95, 5); assert not r3["enough"] and r3["proposal"] is None
# gränser respekteras
r4 = C.build_report(pairs + reacts, 99, 1, lo=1, hi=99); pr = r4["proposal"]; assert 1 <= pr["threshold"] <= 99 and pr["sensitivity"] <= 99
print("A gränser OK")

# region_mask: 40x30 (din NAS verkar ha ett sådant rutnät)
reg = ("0" * 20 + "1" * 20) * 30
m = C.region_mask(reg, 160, 90); assert m.shape == (90, 160) and not m[:, :80].any() and m[:, 80:].all()
assert C.region_mask("0000", 160, 90) is None and C.region_mask("", 160, 90) is None

# ---------- B. bildpar med riktiga bilder
a = Image.new("RGB", (640, 360), (90, 110, 90)); b = a.copy()
ImageDraw.Draw(b).rectangle([400, 100, 460, 300], fill=(235, 235, 235))   # "person" dyker upp till höger
d = C.diff_map(a, b)
lv_all = C.levels_from(d, None); lv_left = C.levels_from(d, C.region_mask(("1" * 20 + "0" * 20) * 30, 160, 90))
assert lv_all[3] > 0.04 and lv_left[3] == 0.0   # rörelsen ligger utanför vänstra området
assert C.box_moving(d, {"x1": 400, "y1": 100, "x2": 460, "y2": 300}, (640, 360))
assert not C.box_moving(d, {"x1": 10, "y1": 10, "x2": 100, "y2": 100}, (640, 360))
assert C.is_night(Image.new("RGB", (100, 100), (80, 80, 80))) and not C.is_night(a)
print("B mätning OK")

# ---------- C. hela flödet via API med låtsas-NAS och låtsas-AI
from app import main, auth, storage
from app.config import config, camera_defaults
storage.init(); C.init_db()
config.update(lambda d: (d.__setitem__("setup_done", True), d["auth"].__setitem__("allowed_users", ["anna"]),
                         d.__setitem__("cameras", {"Out": camera_defaults("Out", 5)})))
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; base_url = "http://nas:8686/"; url = types.SimpleNamespace(scheme="http")
R = Req()
MD = {"sensitivity": {"value": 95, "minValue": 1, "maxValue": 99, "ssCap": True}, "threshold": {"value": 5, "minValue": 1, "maxValue": 99, "ssCap": True}, "region": "1" * 1200, "source": 1}
async def mget(cid): return json.loads(json.dumps(MD))
async def msave(cid, p): MD["sensitivity"]["value"] = p["sensitivity"]; MD["threshold"]["value"] = p["threshold"]
main.ss.motion_get = mget; main.ss.motion_save = msave
frames = iter([])
person = {"on": False}
async def grab(cam):
    img = Image.new("RGB", (640, 360), (90, 110, 90))
    if person["on"]:
        x = random.randint(100, 500); ImageDraw.Draw(img).rectangle([x, 100, x + 60, 300], fill=(235, 235, 235))
    return img
def analyse(cam, img):
    if person["on"]:
        v = [{"label": "person", "confidence": 90, "x1": 100, "y1": 100, "x2": 560, "y2": 300, "valid": True}]
        return v, v
    return [], []
main.engine.grab = grab; main.engine.analyse = analyse; main.engine.ensure_model = lambda: None
run = asyncio.run

async def flow():
    r = await main.calibration_post("Out", R, {"action": "start", "hours": 5})   # begränsas till 12 h
    run_ = r["run"]; assert run_["status"] == "running" and 11.9 * 3600 < run_["ends"] - run_["started"] < 12.1 * 3600
    try:
        await main.calibration_post("Out", R, {"action": "start", "hours": 24}); raise SystemExit("dup")
    except main.HTTPException as e: assert e.status_code == 409
    rid = run_["id"]; rr = main.calib._run("Out")
    for i in range(40):  # 40 brusbildpar
        await main.calib._pair(rr)
    person["on"] = True
    for i in range(4):
        await main.calib._pair(rr)
    for i in range(3):
        await main.calib.on_reaction("Out", config.get("cameras")["Out"]); main.calib._last_react_ai.clear()
    person["on"] = False
    for i in range(25):
        await main.calib.on_reaction("Out", config.get("cameras")["Out"]); main.calib._last_react_ai.clear()
    g = await main.calibration_get("Out", R)
    rep = g["run"]["report"]; assert rep["preliminary"] and rep["pairs"] == 44 and rep["target_pairs"] == 4 and rep["walk_pairs"] == 0   # "walking past" is covered by test_schedule_walk.py
    assert rep["reactions"] == 28 and rep["reactions_target"] == 3, rep
    # avsluta och använd förslaget
    await main.calibration_post("Out", R, {"action": "stop"})
    g = await main.calibration_get("Out", R); assert g["run"]["status"] == "stopped" and not g["run"]["report"].get("preliminary")
    with C._db() as con: assert con.execute("SELECT COUNT(*) FROM calib_samples").fetchone()[0] == 0  # rådata borta
    p = g["run"]["report"]["proposal"]; print("C förslag", p)
    if p and not p.get("unchanged"):
        await main.calibration_post("Out", R, {"action": "apply"})
        assert MD["sensitivity"]["value"] == p["sensitivity"] and MD["threshold"]["value"] == p["threshold"]
        g = await main.calibration_get("Out", R); assert g["run"]["applied"]["sensitivity"] == p["sensitivity"]
        await main.calibration_post("Out", R, {"action": "undo"})
        assert MD["sensitivity"]["value"] == 95 and MD["threshold"]["value"] == 5
    await main.calibration_post("Out", R, {"action": "clear"})
    assert (await main.calibration_get("Out", R))["run"] is None
run(flow())
print("C flöde OK")
