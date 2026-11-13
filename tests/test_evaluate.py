"""Utvärdera modeller: one image, every installed model, the camera's settings, timings, errors and the API."""
import asyncio, os, time, types
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models")
from PIL import Image
from app import main, auth, storage, evaluate as ev
from app.config import config, camera_defaults

storage.init()
cam = camera_defaults("Yard", 5); cam.update(types=["person"], threshold=50, min_width=0, min_height=0)
config.update(lambda d: (d.__setitem__("setup_done", True), d["auth"].__setitem__("allowed_users", ["anna"]),
                         d.__setitem__("cameras", {"Yard": cam}), d["detector"].update({"model": "m_s", "device": "AUTO"})))
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; url = types.SimpleNamespace(scheme="http", netloc="nas:8686")
R = Req(); run = asyncio.run

LOADED = []
class FakeDet:
    MODELS = {"m_n": 0.40, "m_s": 0.75, "broken": None}
    def __init__(self, *dirs): self.compiled = None; self.device = None; self.family = None; self.size = 640; self.meta = {}
    def models(self): return {k: {"family": "yolo"} for k in self.MODELS}
    def ensure(self, model, device="AUTO", fallback=None):
        if self.MODELS[model] is None: raise RuntimeError("Kunde inte ladda modellen: bad xml")
        LOADED.append((model, device)); self.model = model; self.family = "yolo"; self.compiled = object()
        self.device = "CPU" if device in ("AUTO", "CPU") else "CPU"     # no GPU here: falls back
        self.meta = {"license": "AGPL-3.0"}
    def detect(self, img):
        time.sleep(0.002)
        c = self.MODELS[self.model] * 100
        return [{"label": "person", "confidence": c, "x1": 10, "y1": 10, "x2": 40, "y2": 44},
                {"label": "car", "confidence": 90.0, "x1": 1, "y1": 1, "x2": 9, "y2": 9}]
ev.Detector = FakeDet

async def grab(c): return Image.new("RGB", (64, 48), (90, 120, 90))
main.engine.grab = grab
main.engine.detector.model, main.engine.detector.device = "m_s", "CPU"

async def flow(compare):
    job = await main.models_evaluate(R, {"camera": "Yard", "compare_devices": compare})
    assert job["running"] and job["total"] == (6 if compare else 3) and job["image"].startswith("data:image/jpeg"), job
    try:
        await main.models_evaluate(R, {"camera": "Yard"}); raise SystemExit("second start accepted")
    except main.HTTPException as e:
        assert e.status_code == 409
    while main.evaluator.running:
        await asyncio.sleep(0.02)
    return await main.models_evaluate_status(R, since=0)

st = run(flow(False))
res = {r["model"]: r for r in st["results"]}
assert not st["running"] and st["done"] == 3 and st["active"] == {"model": "m_s", "device": "CPU"}, st
assert LOADED == [("broken", "AUTO"), ("m_n", "AUTO"), ("m_s", "AUTO")] or sorted(LOADED) == sorted([("m_n", "AUTO"), ("m_s", "AUTO")]), LOADED
assert res["broken"]["error"] and res["broken"]["image"] is None
assert res["m_s"]["alarm"] and not res["m_n"]["alarm"]                        # 75 % passes the camera's 50 %, 40 % does not
assert [d["reason"] for d in res["m_n"]["detections"]] == ["säkerhet", "typ"]
assert res["m_s"]["ms"] >= 1 and res["m_s"]["first_ms"] >= 1 and res["m_s"]["load_s"] is not None and res["m_s"]["image"].startswith("data:")
assert res["m_s"]["license"] == "AGPL-3.0" and res["m_s"]["device"] == "CPU"
# images are only sent once: since=N gives the rest and no camera image
more = run(main.models_evaluate_status(R, since=2))
assert len(more["results"]) == 1 and "image" not in more and more["since"] == 2
print("A evaluate OK")

LOADED.clear()
st = run(flow(True))
assert [(r["model"], r["wanted"]) for r in st["results"]][:2] == [("broken", "CPU"), ("broken", "GPU")]
g = [r for r in st["results"] if r["model"] == "m_s" and r["wanted"] == "GPU"][0]
assert g["fallback"] and g["device"] == "CPU"                                   # no GPU: marked
print("B CPU/GPU OK")

try: run(main.models_evaluate(R, {"camera": "Nope"})); raise SystemExit("unknown camera accepted")
except main.HTTPException as e: assert e.status_code == 404
print("ALL evaluate OK")
