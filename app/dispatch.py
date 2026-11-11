"""Utskick av notifieringar: direkt eller på begäran.

En notifiering med "Skicka: bara när den anropas" skickas inte när händelsen inträffar. Den väntar tills något
annat system (en hemautomation, ett skript …) anropar /api/notify med händelsens nummer. Det systemet får i
sin tur veta om händelsen genom en vanlig notifiering, t.ex. en webhook med %event_no%.

Med en reservtid skickas den väntande notifieringen ändå om ingen har anropat inom så många minuter.
"""
import asyncio
import logging
import os
import time

from . import notifiers, storage
from .config import CAPTURE_DIR
from .i18n import tr

log = logging.getLogger("synoargus.dispatch")

PENDING_MAX_AGE = 24 * 3600       # så länge kan en händelse begäras via /api/notify


def on_request(n):
    return n.get("deliver") == "request"


class Dispatcher:
    def __init__(self, cfg):
        self.cfg = cfg
        self.pending = {}           # (event_id, notifier_id) -> {"deadline": ts | None, "created": ts}

    # ---------------------------------------------------------------- när en händelse inträffar
    async def send(self, event, jpeg, targets):
        """Skickar till de notifieringar som ska ha det direkt; övriga väntar på anrop.
        Returnerar listan som sparas med händelsen (visas under Händelser)."""
        event_id = event.get("event_id")
        direct = [n for n in targets if not on_request(n)]
        later = [n for n in targets if on_request(n)] if event_id else []
        if event_id:
            storage.set_meta(event_id, {k: v for k, v in event.items() if k != "detections"})
        results = await asyncio.gather(*(notifiers.send(n, event, jpeg) for n in direct))
        out = [{"id": n["id"], "name": n.get("name") or n["type"], "ok": ok, "error": err}
               for n, (ok, err) in zip(direct, results)]
        now = time.time()
        for n in later:
            mins = n.get("fallback_min") or 0
            self.pending[(event_id, n["id"])] = {"deadline": now + mins * 60 if mins else None, "created": now}
            out.append({"id": n["id"], "name": n.get("name") or n["type"], "ok": None, "pending": True})
        if event_id:
            storage.set_notified(event_id, out)
        return out

    # ---------------------------------------------------------------- på begäran
    def find_notifier(self, key):
        key = (key or "").strip()
        lst = self.cfg.get("notifiers") or []
        for n in lst:
            if n["id"] == key:
                return n
        hits = [n for n in lst if (n.get("name") or "").strip().lower() == key.lower()]
        return hits[0] if len(hits) == 1 else None

    def latest_pending(self, notifier_id):
        ids = [e for (e, nid) in self.pending if nid == notifier_id]
        return max(ids) if ids else None

    async def request(self, notifier, event_id=None, text=None, reason=None):
        """Skickar notifier för händelsen event_id (eller den senaste som väntar på den / senaste larmet)."""
        if event_id is None:
            event_id = self.latest_pending(notifier["id"])
        if event_id is None:
            ev = storage.list_events(1, only_alarms=True)
            event_id = ev[0]["id"] if ev else None
        row = storage.get_event(event_id) if event_id is not None else None
        if not row:
            raise LookupError("event")
        event, jpeg = self._rebuild(row)
        if text:
            event["message"] = str(text)[:1000]
        if reason:
            event["message"] = f"{event['message']} ({reason})"
        ok, err = await notifiers.send(notifier, event, jpeg)
        self.pending.pop((row["id"], notifier["id"]), None)
        entry = {"id": notifier["id"], "name": notifier.get("name") or notifier["type"], "ok": ok, "error": err,
                 "requested": not reason, "at": time.time()}
        notified = [x for x in row["notified"] if x.get("id") != notifier["id"]] + [entry]
        storage.set_notified(row["id"], notified)
        return row["id"], ok, err

    def _rebuild(self, row):
        meta = row.get("meta") or {}
        base = (self.cfg.get("public_url") or "").rstrip("/")
        event = {
            "camera": row["camera"], "types": meta.get("types", row["types"]), "detections": row["detections"],
            "event_id": row["id"], "lang": meta.get("lang"),
            "message": meta.get("message") or f"{row['camera']}: " + ", ".join(row["types"]),
            "time": meta.get("time") or "", "image_url": f"{base}/captures/{row['image']}" if base and row["image"] else None,
        }
        for k in ("watch_key", "watch_event"):
            if meta.get(k):
                event[k] = meta[k]
        jpeg = None
        if row["image"]:
            try:
                with open(os.path.join(CAPTURE_DIR, row["image"]), "rb") as f:
                    jpeg = f.read()
            except OSError:
                pass
        return event, jpeg

    # ---------------------------------------------------------------- reserv
    async def check(self):
        now = time.time()
        lst = {n["id"]: n for n in self.cfg.get("notifiers") or []}
        for (event_id, nid), p in list(self.pending.items()):
            n = lst.get(nid)
            if not n or now - p["created"] > PENDING_MAX_AGE:
                self.pending.pop((event_id, nid), None)
                continue
            if p["deadline"] and now >= p["deadline"]:
                self.pending.pop((event_id, nid), None)
                try:
                    await self.request(n, event_id, reason=tr("skickad utan bekräftelse"))
                except Exception as e:
                    log.warning("Reserv för notifiering %s: %s", n.get("name") or nid, e)

    async def loop(self):
        while True:
            await asyncio.sleep(15)
            try:
                await self.check()
            except Exception as e:
                log.warning("Notifieringar: %s", e)
