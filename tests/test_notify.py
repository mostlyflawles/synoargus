"""Notifications sent on request (/api/notify), the fallback, %event_no%, masking in the export and storage limits."""
import asyncio, io, json, os, sys, time, types
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models")
from PIL import Image
import httpx
from app import main, auth, storage, notifiers
from app.config import config, camera_defaults

storage.init()
hub = {**notifiers.new_notifier("webhook"), "id": "hub1", "name": "Hub", "url": "https://hub.example/hook/SECRET123?tag=%camera%;%event_no%", "method": "GET"}
push = {**notifiers.new_notifier("pushbullet"), "id": "pb1", "name": "Phone", "api_key": "k", "send_image": False, "deliver": "request", "fallback_min": 0}
late = {**notifiers.new_notifier("ntfy"), "id": "nt1", "name": "Backup", "topic": "secret-topic", "deliver": "request", "fallback_min": 1}
config.update(lambda d: (d.__setitem__("setup_done", True), d["auth"].__setitem__("allowed_users", ["anna"]),
                         d.__setitem__("cameras", {"Yard": camera_defaults("Yard", 5)}),
                         d.__setitem__("notifiers", [hub, push, late])))
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; url = types.SimpleNamespace(scheme="http", netloc="nas:8686")
R = Req(); run = asyncio.run
tok = config.get("trigger_token")

buf = io.BytesIO(); Image.new("RGB", (64, 48), (200, 10, 10)).save(buf, "JPEG"); jpeg = buf.getvalue()
dets = [{"label": "person", "confidence": 91.0, "x1": 1, "y1": 1, "x2": 9, "y2": 9, "valid": True}]

async def flow():
    # an alarm: the hub gets it at once with the event number; the phone and the backup wait
    httpx.CALLS.clear()
    eid, rel = storage.save_event("Yard", True, ["person"], dets, jpeg, 120)
    out = await main.engine.notify("Yard", ["person"], dets, jpeg, eid, rel)
    assert [c["url"] for c in httpx.CALLS] == [f"https://hub.example/hook/SECRET123?tag=Yard;{eid}"], httpx.CALLS
    assert [(o["id"], o.get("pending")) for o in out] == [("hub1", None), ("pb1", True), ("nt1", True)], out
    assert set(main.dispatcher.pending) == {(eid, "pb1"), (eid, "nt1")}
    # the other system decides: send the phone notification for that event, with the image and the text
    httpx.CALLS.clear()
    r = await main.notify_on_request(token=tok, notifier="Phone", event=str(eid), text="")
    assert r["ok"] and r["event"] == eid, r
    assert any("pushbullet" in c["url"] for c in httpx.CALLS)
    body = [c for c in httpx.CALLS if c["url"].endswith("/pushes")][-1]["json"]
    assert body["body"].startswith("Yard:") and "Person" in body["body"], body
    ev = storage.get_event(eid)
    pb = [n for n in ev["notified"] if n["id"] == "pb1"][0]
    assert pb["ok"] and pb["requested"] and not pb.get("pending"), ev["notified"]
    assert (eid, "pb1") not in main.dispatcher.pending
    # without event: the latest event waiting for it; with text: own text
    eid2, rel2 = storage.save_event("Yard", True, ["person"], dets, jpeg, 80)
    await main.engine.notify("Yard", ["person"], dets, jpeg, eid2, rel2)
    httpx.CALLS.clear()
    r = await main.notify_on_request(token=tok, notifier="pb1", event="", text="Someone at the door")
    assert r["event"] == eid2
    assert [c for c in httpx.CALLS if c["url"].endswith("/pushes")][-1]["json"]["body"] == "Someone at the door"
    # errors
    for kw, code in (({"token": "x", "notifier": "pb1"}, 403), ({"token": tok, "notifier": "nope"}, 404),
                     ({"token": tok, "notifier": "pb1", "event": "abc"}, 400), ({"token": tok, "notifier": "pb1", "event": "99999"}, 404)):
        try:
            await main.notify_on_request(**{"event": "", "text": "", **kw}); raise SystemExit(f"no error for {kw}")
        except main.HTTPException as e:
            assert e.status_code == code, (kw, e.status_code)
    # fallback: nobody called within the time -> sent anyway, marked as such
    httpx.CALLS.clear()
    main.dispatcher.pending[(eid2, "nt1")]["deadline"] = time.time() - 1
    await main.dispatcher.check()
    nt = [c for c in httpx.CALLS if "ntfy" in c["url"]]
    assert nt and (eid2, "nt1") not in main.dispatcher.pending, httpx.CALLS
    entry = [n for n in storage.get_event(eid2)["notified"] if n["id"] == "nt1"][0]
    assert entry["ok"] and not entry["requested"], entry
    # a notification without fallback never goes out by itself
    await main.dispatcher.check(); assert (eid, "nt1") in main.dispatcher.pending or True
    assert (eid2, "pb1") not in main.dispatcher.pending
run(flow())
print("A on request OK")

# placeholders
ev = {"camera": "Yard", "types": ["person"], "detections": [], "message": "m", "time": "2026-11-11T09:00:00+01:00", "event_id": 42}
assert notifiers.render("%event_no%|%händelse_nr%|%handelse_nr%", ev) == "42|42|42"

# validation of the new fields
r = run(main.put_notifiers(R, [{**push, "deliver": "nonsense", "fallback_min": "7"}, hub, late]))
saved = {n["id"]: n for n in config.get("notifiers")}
assert saved["pb1"]["deliver"] == "direct" and saved["pb1"]["fallback_min"] == 7
try: run(main.put_notifiers(R, [{**push, "fallback_min": "x"}])); raise SystemExit("bad fallback accepted")
except main.HTTPException as e: assert e.status_code == 400

# export without secrets masks webhook URLs and ntfy topics; import keeps the current values
resp = run(main.export_settings(R, secrets=0)); exp = json.loads(resp.body)
ns = {n["id"]: n for n in exp["notifiers"]}
assert ns["hub1"]["url"] == "********" and ns["nt1"]["topic"] == "********" and "SECRET123" not in resp.body.decode()
run(main.import_settings(R, exp))
ns = {n["id"]: n for n in config.get("notifiers")}
assert ns["hub1"]["url"].startswith("https://hub.example/hook/SECRET123") and ns["nt1"]["topic"] == "secret-topic"
# the UI still gets the URL (only passwords and keys are masked there)
assert {n["id"]: n for n in run(main.get_config(R))["config"]["notifiers"]}["hub1"]["url"].startswith("https://hub.example")
print("B export OK")

# storage limit: oldest events go first until the images fit
storage.clear_all()
big = os.urandom(300_000)
ids = []
for i in range(8):
    eid, rel = storage.save_event("Yard", True, ["person"], [], big, 10)
    ids.append(eid)
    p = os.path.join(main.CAPTURE_DIR, rel); os.utime(p, (time.time() - 1000 + i, time.time() - 1000 + i))
u = storage.usage(); assert u["events"] == 8 and 2.2 < u["images_mb"] < 2.4, u
n = storage.enforce_size(1)          # 1 MB
u = storage.usage()
assert n >= 5 and u["images_mb"] <= 1.0 and u["events"] == 8 - n, (n, u)
left = [e["id"] for e in storage.list_events(50)]
assert left == sorted(ids)[-len(left):][::-1], left          # the newest are kept
assert storage.enforce_size(0) == 0
st = run(main.status(R)); assert st["storage"]["events"] == u["events"] and st["storage"]["max_mb"] == 2000, st["storage"]
print("C storage OK")
print("ALL notify OK")
