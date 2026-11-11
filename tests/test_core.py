import asyncio, json, os, sys, types
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data")
os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models")
import numpy as np
import httpx
run = asyncio.run

# ---------------- A. YOLOX-avkodning
from app.detector import decode_yolox, yolox_prep, _yolox_grids, available_models
from PIL import Image
img = Image.new("RGB", (1920, 1080), (50, 60, 70))
t, r, px, py = yolox_prep(img, 640)
assert t.shape == (1, 3, 640, 640) and abs(r - 1/3) < 1e-6 and t.max() > 1.5  # 0-255, BGR
grids, strides = _yolox_grids(640); assert grids.shape == (8400, 2)
out = np.zeros((1, 8400, 85), np.float32); out[0, :, 4] = 0.0
# en person med centrum (300, 200), storlek 60x150 i 640-rummet, i stride 8-cellen (37, 25)
i = 25 * 80 + 37; gx, gy, s = 37, 25, 8
out[0, i, 0] = 300 / s - gx; out[0, i, 1] = 200 / s - gy
out[0, i, 2] = np.log(60 / s); out[0, i, 3] = np.log(150 / s)
out[0, i, 4] = 0.9; out[0, i, 5 + 0] = 0.95
# dubblett bredvid (ska bort i NMS) och en katt med låg poäng
out[0, i + 1] = out[0, i]; out[0, i + 1, 0] -= 1/8; out[0, i + 1, 4] = 0.8
j = 100; out[0, j, 4] = 0.1; out[0, j, 5 + 15] = 0.5
d = decode_yolox(out, r, 1920, 1080, 640)
assert len(d) == 1 and d[0]["label"] == "person", d
assert abs(d[0]["x1"] - (300 - 30) * 3) <= 2 and abs(d[0]["y2"] - (200 + 75) * 3) <= 2, d
assert abs(d[0]["confidence"] - 85.5) < 0.2
print("A yolox ok", d[0])
# tiny 416
g2, _ = _yolox_grids(416); assert g2.shape[0] == 3549

# models discovery
os.makedirs(os.path.join(HERE, "models", "yolox_s"), exist_ok=True); open(os.path.join(HERE, "models", "yolox_s", "yolox_s.xml"), "w").close()
os.makedirs(os.path.join(HERE, "data", "models", "yolo26s"), exist_ok=True); open(os.path.join(HERE, "data", "models", "yolo26s", "m.xml"), "w").close()
ms = available_models(os.environ["SYNOARGUS_MODELS"], os.path.join(HERE, "data", "models"))
assert ms["yolox_s"]["family"] == "yolox" and ms["yolox_s"]["source"] == "builtin"
assert ms["yolo26s"]["family"] == "ultralytics" and ms["yolo26s"]["source"] == "user"
print("A models ok")

# ---------------- B. notifierare
from app import notifiers
from app.config import config, type_count
assert type_count("person", 2, "sv") == "2 personer" and type_count("person", 2, "en") == "2 people" and type_count("cat", 3, "en") == "3 cats"
ev = {"camera": "Backyard", "types": ["cat", "person"], "message": "Backyard: 2 people, Cat", "lang": "en",
      "time": "2026-11-09T22:58:14+01:00", "image_url": "http://nas:8686/captures/x.jpg",
      "detections": [{"label": "person", "confidence": 87.4, "valid": True, "x1": 1, "y1": 1, "x2": 9, "y2": 9},
                     {"label": "cat", "confidence": 55, "valid": True, "x1": 1, "y1": 1, "x2": 9, "y2": 9}]}
assert notifiers.render("%camera%;%what%|%vad%|%what_en%", ev) == "Backyard;Cat, Person|Cat, Person|cat, person"
ev_sv = dict(ev, lang="sv")
assert notifiers.render("%vad% %säkerhet% %confidence%", ev_sv) == "Katt, Person 87 87"
jpeg = b"\xff\xd8fakejpeg"

httpx.CALLS.clear()
n = notifiers.new_notifier("telegram"); n.update(bot_token="123:ABC", chat_id="-100", text="%what% @ %time%")
ok, e = run(notifiers.send(n, ev, jpeg)); assert ok, e
c = httpx.CALLS[-1]; assert c["url"].endswith("/bot123:ABC/sendPhoto") and c["data"]["caption"] == "Cat, Person @ 22:58:14" and "photo" in c["files"]
httpx.RESPONSES.append(httpx.Response(400, {"ok": False, "description": "chat not found"}))
ok, e = run(notifiers.send(n, ev, jpeg)); assert not ok and "chat not found" in e, e
n["send_image"] = False; run(notifiers.send(n, ev, jpeg)); assert httpx.CALLS[-1]["url"].endswith("/sendMessage")
print("B telegram ok")

n = notifiers.new_notifier("ntfy"); n.update(topic="sa-test", title="Larm %kamera%", body="Hittade %vad% åäö", priority=5, tags="rotating_light")
ok, e = run(notifiers.send(n, ev_sv, jpeg)); assert ok, e
c = httpx.CALLS[-1]; h = c["headers"]
assert c["method"] == "PUT" and c["url"] == "https://ntfy.sh/sa-test" and c["content"] == jpeg
assert h["Title"] == "Larm Backyard" and h["Message"].startswith("=?UTF-8?B?") and h["Priority"] == "5" and h["Click"] == ev["image_url"]
import base64
assert base64.b64decode(h["Message"][10:-2]).decode() == "Hittade Katt, Person åäö"
n["send_image"] = False; n["auth"] = "token"; n["token"] = "tk"
run(notifiers.send(n, ev_sv, jpeg)); c = httpx.CALLS[-1]
assert c["method"] == "POST" and c["url"] == "https://ntfy.sh" and c["json"]["topic"] == "sa-test" and c["json"]["tags"] == ["rotating_light"] and c["headers"]["Authorization"] == "Bearer tk"
print("B ntfy ok")

n = notifiers.new_notifier("webhook"); n.update(url="https://webhook.homey.app/abc/synoargus?tag=%camera%;%what%", method="GET")
run(notifiers.send(n, ev, jpeg)); c = httpx.CALLS[-1]
assert c["url"] == "https://webhook.homey.app/abc/synoargus?tag=Backyard;Cat%2C%20Person" and c["params"] is None
print("B webhook ok")

sent = {}
class FakeSMTP:
    def __init__(self, host, port, timeout=None, context=None): sent.update(host=host, port=port)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self, context=None): sent["tls"] = True
    def login(self, u, p): sent["login"] = (u, p)
    def send_message(self, msg): sent["msg"] = msg
import smtplib; smtplib.SMTP = FakeSMTP
n = notifiers.new_notifier("email"); n.update(host="smtp.example.com", username="me@example.com", password="pw", to="a@x.se; b@x.se", subject="SA: %kamera%")
ok, e = run(notifiers.send(n, ev_sv, jpeg)); assert ok, e
m = sent["msg"]; assert m["Subject"] == "SA: Backyard" and m["To"] == "a@x.se, b@x.se" and sent["tls"] and sent["port"] == 587
assert any(p.get_filename() == "synoargus.jpg" for p in m.iter_attachments())
assert "Backyard: 2 people, Cat" in m.get_body(("plain",)).get_content()
print("B email ok")

# ---------------- C. API-funktioner
from app import main, auth, storage
storage.init()
def setup_cfg(d):
    d["setup_done"] = True; d["auth"]["allowed_users"] = ["anna"]
    d["synology"].update(url="http://nas:5000", user="sa", password="hemligt")
    d["cameras"] = {"Hall": {**__import__("app.config", fromlist=["x"]).camera_defaults("Hall", 1)},
                    "Backyard": {**__import__("app.config", fromlist=["x"]).camera_defaults("Backyard", 2)}}
    d["notifiers"] = [{**notifiers.new_notifier("telegram"), "id": "t1", "bot_token": "SECRET", "chat_id": "1"}]
config.update(setup_cfg)
tok = config.get("trigger_token")
class Req:
    def __init__(self):
        self.cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
        self.client = types.SimpleNamespace(host="192.168.1.5"); self.headers = {}
        self.base_url = "http://nas:8686/"
        self.url = types.SimpleNamespace(scheme="http", path="/")
R = Req()

r = run(main.control(token=tok, camera="all", action="off")); assert r["cameras"] == {"Hall": False, "Backyard": False}
r = run(main.control(token=tok, camera="Hall", action="toggle")); assert r["cameras"] == {"Hall": True}
r = run(main.control(token=tok, camera="all", action="status")); assert r["cameras"] == {"Hall": True, "Backyard": False}
for bad in [dict(token="x"), dict(token=tok, camera="Nope", action="on"), dict(token=tok, action="explode")]:
    try: run(main.control(**bad)); raise SystemExit("should fail " + str(bad))
    except main.HTTPException as e: assert e.status_code in (400, 403, 404)
print("C control ok")

# trigger på avstängd kamera registreras i mätaren
res = run(main.trigger("Backyard", token=tok)); assert res["result"] == "disabled"
tr = run(main.camera_triggers("Backyard", R, since=0)); assert tr["triggers"][-1]["result"] == "disabled"
print("C triggers ok")

# export utan hemligheter -> import behåller lösenord
resp = run(main.export_settings(R, secrets=0)); exp = json.loads(resp.body)
assert exp["synology"]["password"] == "********" and exp["notifiers"][0]["bot_token"] == "********" and "secret" not in exp
assert "attachment" in resp.headers["content-disposition"]
exp["cameras"]["Hall"]["types"] = ["person", "dog"]; exp["auth"]["allowed_users"] = ["someone"]
r = run(main.import_settings(R, exp)); assert r["cameras"] == 2
assert config.get("synology", "password") == "hemligt" and config.get("notifiers")[0]["bot_token"] == "SECRET"
assert config.get("cameras")["Hall"]["types"] == ["person", "dog"] and "anna" in config.get("auth", "allowed_users")
resp = run(main.export_settings(R, secrets=1)); assert json.loads(resp.body)["synology"]["password"] == "hemligt"
try: run(main.import_settings(R, {"foo": 1})); raise SystemExit("bad import accepted")
except main.HTTPException as e: assert e.status_code == 400
print("C export/import ok")

# språk + tidszon
run(main.put_settings(R, {"language": "en", "timezone": "Europe/Stockholm"}))
assert config.get("language") == "en" and os.environ["TZ"] == "Europe/Stockholm"
try: run(main.put_settings(R, {"timezone": "Mars/Olympus"})); raise SystemExit("bad tz")
except main.HTTPException as e: assert e.status_code == 400 and "Invalid time zone" in e.detail, e.detail
st = run(main.state(R)); assert st["language"] == "en" and st["logged_in"]
print("C settings ok")

# rensa händelser
storage.save_event("Hall", True, ["person"], [], b"\xff\xd8x", 100)
assert storage.list_events(); r = run(main.delete_events(R)); assert r["deleted"] == 1 and not storage.list_events()
assert not os.listdir(os.path.join(HERE, "data", "captures"))
print("C clear ok")

# rörelsedetektering (SS-svar efterliknas)
saved = {}; MD = {"source": 1, "keep": False, "sensitivity": 80, "threshold": 20, "objectSize": 5, "region": {"x": 1}}
async def fake_get(cam_id): return {"MDParam": dict(MD)}
async def fake_save(cam_id, params): saved.update(params); MD.update(sensitivity=params["sensitivity"], threshold=params["threshold"]); return {}
main.ss.motion_get = fake_get; main.ss.motion_save = fake_save
r = run(main.motion_get("Hall", R)); assert r["supported"] and r["sensitivity"] == 80 and r["threshold"] == 20
r = run(main.motion_put("Hall", R, {"sensitivity": 85, "threshold": 15}))
assert saved == {"source": 1, "keep": False, "objectSize": 5, "sensitivity": 85, "threshold": 15}, saved
async def fake_get2(cam_id): return {"something": "else"}
main.ss.motion_get = fake_get2
assert run(main.motion_get("Hall", R))["supported"] is False
print("C motion ok")

# uppdateringskoll
httpx.RESPONSES[:] = [httpx.Response(200, {"tag_name": "v99.0", "html_url": "https://github.com/x/releases/v99.0", "body": "New stuff"})]
u = run(main.check_update(force=True)); assert u["newer"] and u["latest"] == "v99.0", u
httpx.RESPONSES[:] = [httpx.Response(404, {}), httpx.Response(200, [{"name": "v0.3"}, {"name": "v0.4"}, {"name": "latest"}])]
u = run(main.check_update(force=True)); assert u["latest"] == "v0.4" and not u["newer"], u
print("C update ok")

# engelska felmeddelanden från Synology
from app.synology import SynologyError
assert str(SynologyError(400, auth=True)) == "Wrong username or password (DSM code 400)"
print("ALL OK")
