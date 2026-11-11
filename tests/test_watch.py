"""Watch (Bevakning): the motion logic on synthetic scenes, then the manager, API and webhook."""
import asyncio, io, json, os, sys, time, types
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models")
import numpy as np
from PIL import Image
import httpx
from app import main, auth, storage, notifiers, watch
from app import calibration as C
from app.config import config, camera_defaults

W, H, FPS = 480, 270, 3
ZONE = {"x1": 0.44, "y1": 0.40, "x2": 0.58, "y2": 0.60}          # 211..278 x 108..162
rng = np.random.default_rng(1)
BG = (90 + rng.integers(0, 6, (H, W))).astype(np.int16)

def frame(objs):
    f = BG.copy()
    for x, y, w, h in objs:
        f[int(y):int(y + h), int(x):int(x + w)] = 200
    return f

def swing(t, amp=14):        # something moving back and forth inside the zone, period 3 s
    return (238 + amp * np.sin(2 * np.pi * t / 3), 120, 10, 22)

def play(scene, seconds, mod=None, occupied=False):
    cfg = watch.defaults(); cfg["zone"] = ZONE
    if mod: mod(cfg)
    core = watch.WatchCore(cfg, (H, W), occupied=occupied)
    ev = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        ev += core.feed(t, frame(scene(t)))
    return [(round(e["ts"]), e["key"], e.get("where")) for e in ev], core
keys = lambda ev: [k for _, k, _ in ev]

# 1. only the swing: nothing to report (it was already moving when the watch started)
ev, core = play(lambda t: [swing(t)], 40)
assert ev == [] and core.occ == 1 and core.zone_active, ev

# 2. someone walks past, straight through the zone, while the swing moves: one "enter", nothing else
walker = lambda t, v=22: (-20 + v * t, 125, 10, 30)
ev, core = play(lambda t: [swing(t), walker(t)], 40)
assert keys(ev) == ["enter"] and core.occ == 1, ev

# 3. someone walks up to the zone and stops there: enter, then "linger" at the zone
def stopper(t): return (-20 + 22 * min(t, 10), 125, 10, 30)      # stops at x=200, just left of the zone
ev, core = play(lambda t: [swing(t), stopper(t)], 40)
assert keys(ev) == ["enter", "linger"] and ev[1][2] == "zone" and 20 <= ev[1][0] <= 25, ev

# 4. the occupant leaves towards the camera (down in the picture, growing): leave_toward, and no "quiet" afterwards
def leaver(t):
    if t < 10: return [swing(t)]
    k = min(t - 10, 12)
    return [(240 - 6 * k, 130 + 10 * k, 10 + 2 * k, 22 + 4 * k)] if t < 22 else []
q10 = lambda c: c["events"]["quiet"].update(seconds=10)
ev, core = play(leaver, 60, q10)
assert keys(ev) == ["leave_toward"] and core.occ == 0, ev

# 5. leaves sideways: leave_other
def side(t):
    if t < 10: return [swing(t)]
    return [(250 + 20 * (t - 10), 125, 10, 22)] if t < 21 else []
ev, core = play(side, 50, q10)
assert keys(ev) == ["leave_other"] and core.occ == 0, ev

# 6. the swing stops but nobody leaves: quiet after 10 s, resume when it starts again
def pause(t): return [swing(t)] if t < 12 or t > 40 else [(238, 120, 10, 22)]
def qr(c): c["events"]["quiet"].update(seconds=10); c["events"]["resume"]["on"] = True
ev, core = play(pause, 55, qr)
assert keys(ev) == ["quiet", "resume"] and 22 <= ev[0][0] <= 30, ev

# 7. a shadow swinging outside the zone in step with the swing: nothing
shadow = lambda t: (60 + 45 * np.sin(2 * np.pi * t / 3), 200, 40, 6)
ev, core = play(lambda t: [swing(t), shadow(t)], 60)
assert ev == [], ev

# 8. someone arrives at an empty zone and starts swinging: arrive (and no "enter", the zone was empty)
def arrive(t):
    if t < 12: return [(244, 262 - 11 * t, 10, 22)]
    return [swing(t)] if t > 14 else [(244, 130, 10, 22)]
ev, core = play(arrive, 45)
assert keys(ev) == ["arrive"] and core.occ == 1, ev

# 9. flashes of noise and a change of the whole picture: nothing
def noise(t):
    o = [swing(t)]
    if int(t * FPS) % 20 == 5: o.append((rng.integers(0, 440), rng.integers(170, 250), 30, 12))
    return o
ev, core = play(noise, 60); assert ev == [], ev
cfg = watch.defaults(); cfg["zone"] = ZONE; core = watch.WatchCore(cfg, (H, W))
core.feed(0, BG.copy()); core.feed(0.3, BG.copy() + 60); assert core.stats["skipped"] == 1

# 10. "only when the zone is occupied" off: a walker past an empty zone gives enter
ev, core = play(lambda t: [walker(t)], 30, lambda c: c["events"]["enter"].update(only_occupied=False))
assert keys(ev) == ["enter"], ev
ev, core = play(lambda t: [walker(t)], 30); assert ev == [], ev
# 11. someone walks into the picture and disappears in the middle of it (into darkness): enter, but no "linger"
def vanish(t): return [swing(t)] + ([(-20 + 22 * t, 200, 10, 30)] if t < 8 else [])
ev, core = play(vanish, 40); assert keys(ev) == ["enter"], ev
print("A logic OK")

# ---- settings are checked
w = watch.clean({"zone": {"x1": 0.6, "y1": 0.2, "x2": 0.4, "y2": 0.5}, "fps": 99, "events": {"quiet": {"seconds": "abc"}}}) if False else None
try: watch.clean({"zone": ZONE, "events": {"quiet": {"seconds": "abc"}}}); raise SystemExit("bad value accepted")
except ValueError: pass
w = watch.clean({"zone": {"x1": 0.6, "y1": 0.2, "x2": 0.4, "y2": 0.5}, "fps": 99, "stop_on": ["leave_toward", "nonsense"], "junk": 1,
                 "events": {"enter": {"seconds": 500, "on": False}, "linger": {"notifiers": ["a", 5]}}}) if False else watch.clean(
    {"zone": {"x1": 0.6, "y1": 0.2, "x2": 0.4, "y2": 0.5}, "fps": 99, "stop_on": ["leave_toward", "nonsense"], "junk": 1,
     "events": {"enter": {"seconds": 500, "on": False}}})
assert w["zone"]["x1"] == 0.4 and w["fps"] == 4 and w["stop_on"] == ["leave_toward"] and "junk" not in w
assert w["events"]["enter"]["seconds"] == 60 and not w["events"]["enter"]["on"] and w["events"]["quiet"]["seconds"] == 60
print("B settings OK")

# ---- manager, API and webhook
storage.init(); C.init_db()
hook = {**notifiers.new_notifier("webhook"), "id": "hk", "url": "http://hub/x?tag=%camera%;%event_id%;%what%", "method": "GET"}
other = {**notifiers.new_notifier("webhook"), "id": "ot", "url": "http://other/y", "method": "GET", "types": ["car"]}
config.update(lambda d: (d.__setitem__("setup_done", True), d["auth"].__setitem__("allowed_users", ["anna"]),
                         d.__setitem__("cameras", {"Yard": camera_defaults("Yard", 5), "Hall": camera_defaults("Hall", 7)}),
                         d.__setitem__("notifiers", [hook, other])))
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; url = types.SimpleNamespace(scheme="http", netloc="nas:8686")
R = Req(); run = asyncio.run
T0 = [0.0]
def jpeg_at(t):
    buf = io.BytesIO(); Image.fromarray(frame([swing(t), walker(t, 45)]).astype(np.uint8)).resize((960, 540)).save(buf, "JPEG", quality=92)
    return buf.getvalue()
async def snapshot(cam_id): return jpeg_at(time.time() - T0[0])
main.ss.snapshot = snapshot
main.engine.ensure_model = lambda: None
main.engine.detector.detect = lambda img: [{"label": "person", "confidence": 80, "x1": 0, "y1": 0, "x2": 10, "y2": 10}]

async def flow():
    tok = config.get("trigger_token")
    try: await main.watch_action("Yard", R, {"action": "start"}); raise SystemExit("no zone")
    except main.HTTPException as e: assert e.status_code == 400
    try: await main.watch_put("Yard", R, {"zone": ZONE, "fps": "x"}); raise SystemExit("bad fps")
    except main.HTTPException as e: assert e.status_code == 400 and "fps" in e.detail
    r = await main.watch_put("Yard", R, {"zone": ZONE, "fps": 4, "stop_on": [], "events": {"enter": {"notifiers": ["hk", "gone"], "cooldown": 30}}})
    assert r["watch"]["events"]["enter"]["notifiers"] == ["hk"]
    g = await main.watches_get(R); assert "Yard" in g["watches"] and g["status"]["active"] is None and g["token"] == tok
    # calibration and watch exclude each other
    async def mget(cid): return {"sensitivity": {"value": 90}, "threshold": {"value": 10}, "region": "1" * 1200}
    main.ss.motion_get = mget
    await main.calibration_post("Hall", R, {"action": "start", "hours": 12})
    try: await main.watch_action("Yard", R, {"action": "start"}); raise SystemExit("calibration running")
    except main.HTTPException as e: assert e.status_code == 409 and "Hall" in e.detail
    await main.calibration_post("Hall", R, {"action": "stop"}); await main.calibration_post("Hall", R, {"action": "clear"})
    # start through the webhook, zone already occupied
    try: await main.watch_webhook(token="wrong", camera="Yard", action="start"); raise SystemExit("token")
    except main.HTTPException as e: assert e.status_code == 403
    T0[0] = time.time(); httpx.CALLS.clear()
    r = await main.watch_webhook(token=tok, camera="", action="start", occupied=1)      # only one watch: camera can be left out
    assert r["active"] == "Yard" and r["configured"] == ["Yard"]
    try: await main.calibration_post("Hall", R, {"action": "start", "hours": 12}); raise SystemExit("watch running")
    except main.HTTPException as e: assert e.status_code == 409 and "Yard" in e.detail
    assert (await main.state(R))["watch"] == "Yard"
    await asyncio.sleep(8.5)
    st = await main.watches_status(R)
    assert st["active"] == "Yard" and st["fps"] > 2.5 and st["state"]["occupied"] == 1 and st["error"] is None, st
    texts = [l for l in st["log"] if l["key"] == "enter"]
    assert len(texts) == 1 and "person" in texts[0]["text"] and texts[0]["sent"][0]["ok"], st["log"]
    calls = [c["url"] for c in httpx.CALLS]
    assert len(calls) == 1 and calls[0].startswith("http://hub/x?tag=Yard;enter;"), calls     # only the chosen notifier
    evs = storage.list_events(10); assert len(evs) == 1 and evs[0]["camera"] == "Yard" and evs[0]["image"]
    print(f"C watch: {st['fps']} fps, {st['ms']} ms per image, events {[l['key'] for l in st['log']]}")
    r = await main.watch_webhook(token=tok, camera="Yard", action="stop"); assert r["active"] is None
    # vehicles are ignored, test mode sends nothing, stop_on stops the watch
    main.engine.detector.detect = lambda img: [{"label": "car", "confidence": 90, "x1": 0, "y1": 0, "x2": 10, "y2": 10}]
    httpx.CALLS.clear(); T0[0] = time.time()
    await main.watch_action("Yard", R, {"action": "start", "occupied": True}); await asyncio.sleep(7.5)
    st = await main.watches_status(R); assert any(l.get("ignored") for l in st["log"]) and not httpx.CALLS, st["log"]
    main.engine.detector.detect = lambda img: []
    await main.watch_put("Yard", R, {"zone": ZONE, "fps": 4, "test": True, "stop_on": ["enter"]})
    await main.watch_action("Yard", R, {"action": "stop"})
    httpx.CALLS.clear(); T0[0] = time.time(); n0 = len(storage.list_events(50))
    await main.watch_action("Yard", R, {"action": "start", "occupied": True}); await asyncio.sleep(7.5)
    st = await main.watches_status(R)
    assert st["active"] is None and st["log"][0]["key"] == "stop" and st["log"][1].get("test"), st["log"][:3]
    assert not httpx.CALLS and len(storage.list_events(50)) == n0
    # deleting the camera removes its watch
    await main.delete_camera("Yard", R); assert "Yard" not in (config.get("watches") or {})
run(flow())
print("C manager OK")
# placeholders for ordinary alarms are unchanged, watch events fill %what% and %event%
ev = {"camera": "Yard", "types": [], "detections": [], "message": "Yard: x", "time": "2026-11-09T22:00:00+01:00", "watch_event": "Quiet in the zone", "watch_key": "quiet"}
assert notifiers.render("%camera%|%what%|%händelse%|%event_id%|%count%", ev) == "Yard|Quiet in the zone|Quiet in the zone|quiet|0"
ev2 = {"camera": "Yard", "types": ["cat"], "detections": [], "message": "m", "time": "2026-11-09T22:00:00+01:00", "lang": "en"}
assert notifiers.render("%what%|%event%|", ev2) == "Cat||"
print("ALL watch OK")
