"""Utvärdera modeller: samma bild från en kamera analyseras av varje installerad modell.

Varje modell laddas i en egen, tillfällig Detector så att den modell som används för larm inte påverkas.
Modellerna körs en i taget och släpps direkt efteråt (NAS:en har lite minne). Analystiden mäts flera gånger efter
en första uppvärmning, eftersom den första körningen alltid är långsammare.
"""
import asyncio
import base64
import gc
import io
import json
import logging
import os
import statistics
import time

from .detector import Detector
from .filters import draw, evaluate

log = logging.getLogger("synoargus.evaluate")

RUNS = 3                    # mätningar efter uppvärmningen


class ModelEvaluator:
    def __init__(self, cfg, engine, model_dirs):
        self.cfg = cfg
        self.engine = engine
        self.model_dirs = model_dirs
        self.job = None             # pågående eller senaste körningen
        self._task = None
        self._cancel = False
        self.dir = os.path.join(os.environ.get("SYNOARGUS_DATA", "/data"), "evaluations")
        self.on_pause = lambda on: None     # sätts i main: pausar larm och bevakning medan det pågår

    @property
    def running(self):
        return bool(self._task and not self._task.done())

    def status(self, camera=None):
        """Den pågående utvärderingen om den gäller kameran (eller ingen kamera angavs), annars kamerans sparade."""
        if self.job and (camera is None or self.job.get("camera") == camera) and (self.running or camera is None):
            return self.job
        if camera:
            saved = self._load(camera)
            if saved:
                return saved
        return {"running": False, "camera": camera} if camera else (self.job or {"running": False})

    # ---------------------------------------------------------------- en sparad utvärdering per kamera
    def _path(self, camera):
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in camera)
        return os.path.join(self.dir, safe + ".json")

    def _load(self, camera):
        try:
            with open(self._path(camera)) as f:
                job = json.load(f)
            return job if job.get("camera") == camera else None
        except (OSError, ValueError):
            return None

    def _save(self, job):
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = self._path(job["camera"]) + ".tmp"
            with open(tmp, "w") as f:
                json.dump(job, f)
            os.replace(tmp, self._path(job["camera"]))
        except OSError as e:
            log.warning("Kunde inte spara utvärderingen: %s", e)

    def delete(self, camera):
        if self.running and self.job and self.job.get("camera") == camera:
            raise RuntimeError("running")
        try:
            os.remove(self._path(camera))
        except OSError:
            pass
        if self.job and self.job.get("camera") == camera:
            self.job = None

    def cancel(self):
        """Avbryter efter modellen som körs just nu (en pågående laddning kan inte avbrytas)."""
        if self.running:
            self._cancel = True
            self.job["cancelling"] = True
        return self.running

    async def start(self, cam, devices):
        if self.running:
            raise RuntimeError("busy")
        img = await self.engine.grab(cam)
        models = sorted(Detector(*self.model_dirs).models())
        plan = [(m, d) for m in models for d in devices]
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        self.job = {"running": True, "camera": cam["name"], "started": time.time(), "finished": None,
                    "total": len(plan), "done": 0, "current": None, "results": [], "error": None,
                    "active": {"model": self.engine.detector.model, "device": self.engine.detector.device},
                    "width": img.size[0], "height": img.size[1],
                    "image": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}
        self._cancel = False
        self.on_pause(True)
        self._task = asyncio.create_task(self._run(cam, img, plan))
        return self.job

    async def _run(self, cam, img, plan):
        job = self.job
        try:
            for model, device in plan:
                if self._cancel:
                    job["cancelled"] = True
                    break
                job["current"] = {"model": model, "device": device}
                res = await asyncio.to_thread(self._one, cam, img, model, device)
                job["results"].append(res)
                job["done"] += 1
        except Exception as e:      # oväntat fel: visa det, men behåll det som hann bli klart
            log.warning("Utvärdering: %s", e)
            job["error"] = str(e)
        finally:
            self.on_pause(False)    # larm och bevakning startar alltid igen
        job["current"] = None
        job["recommended"] = recommend(job["results"])
        job["running"] = False
        job.pop("cancelling", None)
        job["finished"] = time.time()
        self._save(job)

    def _one(self, cam, img, model, device):
        det = Detector(*self.model_dirs)
        res = {"model": model, "device": None, "wanted": device, "load_s": None, "ms": None, "first_ms": None,
               "detections": [], "alarm": False, "image": None, "error": None}
        try:
            t = time.time()
            det.ensure(model, device, fallback=model)
            res["load_s"] = round(time.time() - t, 1)
            res["device"], res["family"], res["size"] = det.device, det.family, det.size
            res["license"] = (det.meta or {}).get("license")
            if device != "AUTO" and det.device != device:       # t.ex. GPU saknas: CPU användes i stället
                res["fallback"] = True
            res["gpu_unsupported"] = bool(getattr(det, "gpu_skipped", False))   # grafikkretsen klarar inte modellen
            t = time.time()
            det.detect(img)
            res["first_ms"] = round((time.time() - t) * 1000)
            times = []
            for _ in range(RUNS):
                t = time.time()
                raw = det.detect(img)
                times.append((time.time() - t) * 1000)
            res["ms"] = round(statistics.median(times))
            cfg, w, h = self.cfg, img.size[0], img.size[1]
            dets, valid = evaluate(raw, cam.get("types") or [], cfg.cam_setting(cam, "threshold"),
                                   cfg.cam_setting(cam, "min_width"), cfg.cam_setting(cam, "min_height"),
                                   cam.get("zones"), w, h)
            res["detections"], res["alarm"] = dets, bool(valid)
            jpeg = draw(img, dets, cam.get("zones"), True)
            res["image"] = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        except Exception as e:
            res["error"] = str(e)
            log.warning("Utvärdering av %s på %s: %s", model, device, e)
        finally:
            det.compiled = None
            del det
            gc.collect()
        return res


def recommend(results):
    """Bäst avvägning: bland modellerna som hittade det kameran letar efter, och som inte är mer än dubbelt så
    långsamma som den snabbaste av dem (minst 500 ms tillåts), den med högst säkerhet; vid lika den snabbaste.
    None om ingen modell hittade något (då finns inget att jämföra)."""
    cands = []
    for r in results:
        if r.get("error") or not r.get("alarm") or not r.get("ms"):
            continue
        best = max((d.get("confidence", 0) for d in r.get("detections") or [] if d.get("valid")), default=0)
        cands.append((r, best))
    if not cands:
        return None
    limit = max(500, 2 * min(r["ms"] for r, _ in cands))
    ok = [(r, b) for r, b in cands if r["ms"] <= limit]
    r, _ = max(ok, key=lambda x: (round(x[1]), -x[0]["ms"]))
    return {"model": r["model"], "device": r.get("device")}
