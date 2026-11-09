"""Hanterar rörelselarm från Surveillance Station: bild -> AI -> filter -> larm."""
import asyncio
import io
import logging
import time
from collections import deque
from datetime import datetime

from PIL import Image

from . import notifiers, storage
from .config import type_count, type_name
from .filters import draw, evaluate
from .i18n import lang, tr

log = logging.getLogger("synoargus.engine")


class CameraState:
    def __init__(self):
        self.busy = False
        self.last_end = 0.0
        self.last_alarm = 0.0
        self.last_result = None
        self.triggers = deque(maxlen=200)  # utlösningar från Surveillance Station (rörelsemätaren)


class Engine:
    def __init__(self, cfg, ss, detector):
        self.cfg = cfg
        self.ss = ss
        self.detector = detector
        self.state = {}
        self.recent = []  # senaste meddelanden för statussidan
        self.modes = None  # ModeManager, sätts i main
        self.on_trigger = None  # anropas vid varje reaktion (kalibreringen)
        self.priority_until = 0  # "Jag går förbi nu": kalibreringen går före larm till denna tid

    def priority_active(self):
        return time.time() < self.priority_until

    def _st(self, name):
        return self.state.setdefault(name, CameraState())

    def _note(self, camera, text):
        self.recent.insert(0, {"ts": time.time(), "camera": camera, "text": text})
        del self.recent[50:]

    def ensure_model(self):
        d = self.cfg.get("detector")
        self.detector.ensure(d.get("model") or "yolox_s", d.get("device") or "AUTO")

    async def grab(self, cam):
        cam_id = cam.get("ss_id")
        if cam_id is None:
            cam_id = await self.ss.resolve_id(cam["name"])

            def remember(data):
                if cam["name"] in data["cameras"]:
                    data["cameras"][cam["name"]]["ss_id"] = cam_id
            self.cfg.update(remember)
            cam["ss_id"] = cam_id
        jpeg = await self.ss.snapshot(cam_id)
        img = Image.open(io.BytesIO(jpeg))
        img.load()
        return img.convert("RGB")

    def analyse(self, cam, img):
        cfg = self.cfg
        dets = self.detector.detect(img)
        w, h = img.size
        return evaluate(
            dets, cam.get("types") or [],
            cfg.cam_setting(cam, "threshold"), cfg.cam_setting(cam, "min_width"),
            cfg.cam_setting(cam, "min_height"), cam.get("zones"), w, h)

    async def trigger(self, name):
        """Anropas av Surveillance Station. Returnerar en kort status."""
        cam = (self.cfg.get("cameras") or {}).get(name)
        if not cam:
            self._note(name, tr("Okänd kamera (lägg till den under Inställningar > Kameror)"))
            return "unknown"
        st = self._st(name)
        entry = {"ts": time.time(), "result": None, "outcome": None}
        st.triggers.append(entry)
        entry["result"] = self._check(cam, st)
        if self.on_trigger:
            asyncio.create_task(self.on_trigger(name, cam))
        if entry["result"] == "accepted":
            st.busy = True
            self._note(name, tr("Rörelse: analyserar"))
            asyncio.create_task(self._process(cam, st, entry))
        else:
            if entry["result"] == "mode" and self.modes:
                entry["mode"] = self.modes.name(self.modes.current())
            why = {"disabled": tr("kameran avstängd"), "cooldown": tr("tyst period"), "delay": tr("för tätt"),
                   "busy": tr("upptagen"), "mode": tr("läge {m}", m=entry.get("mode", ""))}.get(entry["result"],
                                                                                              entry["result"])
            self._note(name, tr("Rörelse: ignoreras ({why})", why=why))
        return entry["result"]

    def _check(self, cam, st):
        if not cam.get("enabled", True):
            return "disabled"
        modes = cam.get("modes") or []
        if modes and self.modes and self.modes.current() not in modes:
            return "mode"
        now = time.time()
        if st.busy:
            return "busy"
        if now - st.last_end < (self.cfg.cam_setting(cam, "delay_s") or 0):
            return "delay"
        if now - st.last_alarm < (self.cfg.cam_setting(cam, "cooldown_s") or 0):
            return "cooldown"
        return "accepted"

    def triggers(self, name, since=0):
        st = self.state.get(name)
        if not st:
            return []
        return [dict(t) for t in st.triggers if t["ts"] > since]

    async def _process(self, cam, st, entry=None):
        name = cam["name"]
        try:
            await asyncio.to_thread(self.ensure_model)
            if cam.get("wait_ms"):
                await asyncio.sleep(cam["wait_ms"] / 1000)
            tries = max(1, int(self.cfg.cam_setting(cam, "max_snapshots") or 1))
            interval = (self.cfg.get("defaults", "snapshot_interval_ms") or 700) / 1000
            queued = []
            if self.priority_active():
                # kalibreringen går före: ta bilderna nu, analysera när AI:n är ledig
                self._note(name, tr("Rörelse: i kö (kalibrering pågår)"))
                for i in range(tries):
                    queued.append(await self.grab(cam))
                    if i < tries - 1:
                        await asyncio.sleep(interval)
                while self.priority_active():
                    await asyncio.sleep(0.5)
            t0 = time.time()
            img = all_dets = valid = None
            for i in range(tries):
                img = queued[i] if i < len(queued) else await self.grab(cam)
                all_dets, valid = await asyncio.to_thread(self.analyse, cam, img)
                if valid:
                    break
                if i < tries - 1 and not queued:
                    await asyncio.sleep(interval)
            ms = round((time.time() - t0) * 1000)
            st.last_result = {"ts": time.time(), "alarm": bool(valid), "ms": ms}
            if entry is not None:
                entry["outcome"] = "alarm" if valid else "none"
                entry["types"] = sorted({d["label"] for d in valid or []})
            if not valid:
                if self.cfg.get("storage", "save_empty"):
                    jpeg = await asyncio.to_thread(draw, img, all_dets, None, True)
                    storage.save_event(name, False, [], all_dets, jpeg, ms)
                self._note(name, tr("Inget av intresse ({ms} ms)", ms=ms))
                return
            types = sorted({d["label"] for d in valid})
            jpeg = await asyncio.to_thread(draw, img, all_dets)
            event_id, rel = storage.save_event(name, True, types, all_dets, jpeg, ms)
            st.last_alarm = time.time()
            self._note(name, tr("Larm: {types}", types=", ".join(type_name(t, lang()) for t in types)))
            await self.notify(name, types, all_dets, jpeg, event_id, rel)
        except Exception as e:
            log.exception("Fel vid analys av %s", name)
            if entry is not None:
                entry["outcome"] = "error"
            self._note(name, tr("Fel: {e}", e=e))
        finally:
            st.busy = False
            st.last_end = time.time()

    def build_event(self, name, types, dets, event_id=None, rel=None):
        lg = lang()
        counts = {}
        for d in dets:
            if d.get("valid"):
                counts[d["label"]] = counts.get(d["label"], 0) + 1
        parts = [type_count(t, c, lg) for t, c in counts.items()] or [type_name(t, lg) for t in types]
        base = (self.cfg.get("public_url") or "").rstrip("/")
        return {
            "camera": name, "types": types, "detections": dets, "event_id": event_id, "lang": lg,
            "message": f"{name}: " + ", ".join(parts),
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "image_url": f"{base}/captures/{rel}" if base and rel else None,
        }

    async def notify(self, name, types, dets, jpeg, event_id=None, rel=None, only=None):
        event = self.build_event(name, types, dets, event_id, rel)
        mode = self.modes.current() if self.modes else None
        targets = [n for n in self.cfg.get("notifiers") or []
                   if (only and n["id"] == only) or (not only and notifiers.applies(n, name, types, mode))]
        results = await asyncio.gather(*(notifiers.send(n, event, jpeg) for n in targets))
        out = [{"id": n["id"], "name": n.get("name") or n["type"], "ok": ok, "error": err}
               for n, (ok, err) in zip(targets, results)]
        if event_id:
            storage.set_notified(event_id, out)
        return out
