import asyncio, json, os, sys, types, copy
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data41")
os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models")

run = asyncio.run
from app import main, auth, storage
from app.config import config, camera_defaults
from app.synology import SynologyError
storage.init()
def setup(d):
    d["setup_done"] = True; d["auth"]["allowed_users"] = ["anna"]; d["public_url"] = "http://192.0.2.20:8686"
    d["cameras"] = {"Backyard": camera_defaults("Backyard", 3), "Garage": camera_defaults("Garage", 4)}
config.update(setup)
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; base_url = "http://192.0.2.20:8686/"; url = types.SimpleNamespace(scheme="http")
R = Req()

# ---- rörelse: ditt riktiga svar (förkortad region)
REAL = {"camRoi":{"channel":"","type":0},"enhanceMDWithPD":{"value":False},"history":{"camCap":False,"maxValue":99,"minValue":1,"ssCap":False,"value":90},"keep":True,"mode":0,"objectSize":{"camCap":False,"maxValue":99,"minValue":1,"ssCap":False,"value":50},"percentage":{"camCap":False,"maxValue":99,"minValue":1,"ssCap":False,"value":50},"region":"0001111000","relatedEvents":[],"sensitivity":{"camCap":False,"maxValue":99,"minValue":1,"ssCap":True,"value":95},"shortLiveSecond":{"camCap":False,"ssCap":True,"value":0},"source":1,"synocam_det_region":"","threshold":{"camCap":False,"maxValue":99,"minValue":1,"ssCap":True,"value":5}}
state = copy.deepcopy(REAL); saved = []
async def mget(cam_id): return copy.deepcopy(state)
async def msave(cam_id, p):
    saved.append(dict(p)); state["sensitivity"]["value"] = p["sensitivity"]; state["threshold"]["value"] = p["threshold"]; return {}
main.ss.motion_get = mget; main.ss.motion_save = msave
r = run(main.motion_get("Backyard", R))
assert r["supported"] and r["sensitivity"] == 95 and r["threshold"] == 5 and r["min"] == 1 and r["max"] == 99 and r["ss_cap"], r
r = run(main.motion_put("Backyard", R, {"sensitivity": 80, "threshold": 15}))
assert r == {"ok": True, "sensitivity": 80, "threshold": 15}, r
p = saved[-1]
assert p["region"] == "0001111000" and p["history"] == 90 and p["objectSize"] == 50 and p["shortLiveSecond"] == 0 and p["enhanceMDWithPD"] is False and p["keep"] is True and p["source"] == 1
assert "camRoi" not in p and "relatedEvents" not in p
from app.synology import _flat
f = _flat({**p, "camId": 3}); assert f["keep"] == "true" and f["enhanceMDWithPD"] == "false" and f["sensitivity"] == "80"
# över max -> begränsas
run(main.motion_put("Backyard", R, {"sensitivity": 150, "threshold": -3})); assert saved[-1]["sensitivity"] == 99 and saved[-1]["threshold"] == 1
# SS sparar inte -> fel
async def msave_noop(cam_id, p): return {}
main.ss.motion_save = msave_noop
try: run(main.motion_put("Backyard", R, {"sensitivity": 50, "threshold": 50})); raise SystemExit("should fail")
except main.HTTPException as e: assert e.status_code == 502 and "99/1" in e.detail, e.detail
# 101 -> försök igen med grundfält
calls = []
async def msave_101(cam_id, p):
    calls.append(p)
    if len(calls) == 1: raise SynologyError(101)
    state["sensitivity"]["value"] = p["sensitivity"]; state["threshold"]["value"] = p["threshold"]
main.ss.motion_save = msave_101
run(main.motion_put("Backyard", R, {"sensitivity": 70, "threshold": 20}))
assert "enhanceMDWithPD" in calls[0] and "enhanceMDWithPD" not in calls[1] and calls[1]["region"] == "0001111000"
# kamerans egen detektering
state["sensitivity"]["ssCap"] = False
try: run(main.motion_put("Backyard", R, {"sensitivity": 50, "threshold": 50})); raise SystemExit("ssCap")
except main.HTTPException as e: assert e.status_code == 400
print("motion OK")

