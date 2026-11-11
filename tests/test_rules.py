import asyncio, json, os, sys, types, copy, time
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data42"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models42")

run = asyncio.run
from app import main, auth, storage
from app.config import config, camera_defaults
from app.synology import SynologyError, _flat
storage.init()
CAMS = {"Front": 1, "Backyard": 5, "Hall": 7, "Garage": 8}
def setup(d):
    d["setup_done"] = True; d["auth"]["allowed_users"] = ["anna"]; d["public_url"] = "http://192.0.2.20:8686"
    d["cameras"] = {n: camera_defaults(n, i) for n, i in CAMS.items()}
config.update(setup)
config.update(lambda d: d.__setitem__("trigger_token", "exampletoken0000000000")); tok = config.get("trigger_token")
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; base_url = "http://192.0.2.20:8686/"; url = types.SimpleNamespace(scheme="http")
R = Req()

# ---- simulerad SS med riktig data. Save: med ruleId = redigera, utan = ny.
RULES = json.load(open(os.path.join(_env.TESTS, "fixtures", "action_rules.json")))["actRule"]
ORIG = copy.deepcopy(RULES)
nxt = [200]; SAVED = []
def decode(params):  # så som SS tar emot: allt kommer som text (via _flat)
    flat = _flat(params); out = {}
    for k, v in flat.items():
        if v[:1] in "[{": out[k] = json.loads(v)
        elif v in ("true", "false"): out[k] = v == "true"
        elif v.lstrip("-").isdigit() and len(v) < 12: out[k] = int(v)
        else: out[k] = v
    return out
async def lst(): return {"actRule": copy.deepcopy(RULES), "total": len(RULES)}
async def save(params):
    p = decode(params); SAVED.append(dict(p))
    if "ruleId" in p:
        for i, r in enumerate(RULES):
            if r["ruleId"] == p["ruleId"]: RULES[i] = p; return {}
    p["ruleId"] = nxt[0]; nxt[0] += 1; RULES.append(p); return {}
main.ss.action_rules = lst; main.ss.action_rule_save = save

def by_name(n): return [r for r in RULES if r["name"] == n]
homey_ids = {r["ruleId"] for r in ORIG if r["name"].startswith("Homey")}

# 1. den trasiga regeln (Home Mode-händelse) upptäcks
g = run(main.actionrule_get("Backyard", R))
assert len(g["rules"]) == 1 and g["rules"][0]["current"] and not g["rules"][0]["event_ok"], g["rules"]
r = run(main.actionrule_post("Backyard", R, {"action": "fix"}))
fixed = [x for x in RULES if x["ruleId"] == 154][0]
assert fixed["events"][0]["evtId"] == 5 and fixed["events"][0]["evtSrc"] == 0 and fixed["events"][0]["evtDevId"] == 5
assert fixed["actSchedule"] == "1" * 336 and r["rules"][0]["event_ok"]
print("fix OK")

# 2. skapa för tre kameror -> tre NYA regler, inget befintligt ändrat
for n in ("Front", "Hall", "Garage"):
    r = run(main.actionrule_post(n, R, {"action": "create"}))
    assert r["created"] and r["confirmed"], r
assert len(RULES) == len(ORIG) + 3, len(RULES)
for n, cid in [("Front", 1), ("Hall", 7), ("Garage", 8)]:
    x = by_name(f"SynoArgus - {n}"); assert len(x) == 1
    x = x[0]; assert x["ruleId"] >= 200 and x["events"][0]["evtDevId"] == cid and x["events"][0]["evtId"] == 5
    assert x["actions"][0]["extUrl"] == f"http://192.0.2.20:8686/api/trigger/{n}?token={tok}" and "id" not in x["actions"][0]
    assert x["actSchedule"] == "1" * 336
    assert config.get("cameras")[n]["action_rule"]["confirmed"]
for o in ORIG:
    if o["ruleId"] in homey_ids:
        cur = [r for r in RULES if r["ruleId"] == o["ruleId"]][0]
        assert cur == o, o["name"]
assert all("ruleId" not in s for s in SAVED[1:4]), [s.get("ruleId") for s in SAVED]
print("create x3 OK, Homey-regler orörda")

# 3. dubblett nekas
try: run(main.actionrule_post("Garage", R, {"action": "create"})); raise SystemExit("dup")
except main.HTTPException as e: assert e.status_code == 409

# 4. ny token -> "gammal adress" -> uppdatera
config.update(lambda d: d.__setitem__("trigger_token", "NYTT"))
g = run(main.actionrule_get("Garage", R)); assert not g["rules"][0]["current"] and g["rules"][0]["event_ok"]
r = run(main.actionrule_post("Garage", R, {"action": "update"})); assert r["updated"] == 1
assert by_name("SynoArgus - Garage")[0]["actions"][0]["extUrl"].endswith("token=NYTT")
assert by_name("SynoArgus - Hall")[0]["actions"][0]["extUrl"].endswith("token=" + tok)  # andra kameror orörda
print("update OK")

# 5. om SS skriver över i stället för att skapa -> fel upptäcks
async def bad_save(params):
    p = decode(params); RULES[0] = {**p, "ruleId": RULES[0]["ruleId"]}; return {}
main.ss.action_rule_save = bad_save
config.update(lambda d: d["cameras"]["Front"].pop("action_rule", None))
RULES[:] = [r for r in RULES if r["name"] != "SynoArgus - Front"]
try: run(main.actionrule_post("Front", R, {"action": "create"})); raise SystemExit("bad save undetected")
except main.HTTPException as e: assert e.status_code == 502 and "ny regel" in e.detail, e.detail
print("overwrite detected OK")

# 6. 105 -> sparad info + Administrator-text
async def denied(): raise SynologyError(105)
main.ss.action_rules = denied
g = run(main.actionrule_get("Garage", R))
assert "Administrator" in g["error"] and g["stored"]["name"] == "SynoArgus - Garage" and g["stored"]["confirmed"]
async def mdenied(cam_id): raise SynologyError(105)
main.ss.motion_get = mdenied
try: run(main.motion_get("Garage", R)); raise SystemExit("x")
except main.HTTPException as e: assert e.status_code == 403 and "All-Object Manager" in e.detail
print("105 OK")

# 7. modellernas märkning
from app.detector import available_models
for base, name, meta in [("models42", "yolox_s", {"family": "yolox", "source": "Megvii"}), ("data42/models", "yolo26s", {"family": "ultralytics", "origin": "yolo26s.pt"})]:
    d = os.path.join(HERE, base, name); os.makedirs(d, exist_ok=True); open(os.path.join(d, "m.xml"), "w").close()
    json.dump(meta, open(os.path.join(d, "synoargus.json"), "w"))
ms = available_models(os.path.join(HERE, "models42"), os.path.join(HERE, "data42", "models"))
assert ms["yolox_s"]["source"] == "builtin" and ms["yolo26s"]["source"] == "user" and ms["yolox_s"]["origin"] == "Megvii"
print("model source OK")
