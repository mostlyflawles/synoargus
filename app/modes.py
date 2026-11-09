"""Lägen (t.ex. Hemma / Natt / Borta): vilka kameror larmar och vilka notifierare skickar.

Läget ändras av den som ändrar det senast:
  - manuellt i gränssnittet
  - webhook (/api/mode, t.ex. från Homey)
  - schema (vid en viss tid vissa dagar)
  - Home Mode i Surveillance Station (när det slås på eller av)
"""
import asyncio
import logging
import time
from datetime import datetime

from .i18n import lang, tr
from .synology import find_homemode

log = logging.getLogger("synoargus.modes")

DEFAULT_NAMES = {
    "sv": {"home": "Hemma", "night": "Natt", "away": "Borta"},
    "en": {"home": "Home", "night": "Night", "away": "Away"},
}


class ModeManager:
    def __init__(self, cfg, ss, note=None):
        self.cfg = cfg
        self.ss = ss
        self.note = note or (lambda camera, text: None)
        self.homemode = None        # True/False/None (okänt)
        self.homemode_error = None
        self._fired = set()         # schemapunkter som redan körts (datum, index)

    # ---------------------------------------------------------------- namn
    def modes(self):
        return self.cfg.get("modes") or []

    def name(self, mode_id):
        for m in self.modes():
            if m["id"] == mode_id:
                return m.get("name") or DEFAULT_NAMES.get(lang(), DEFAULT_NAMES["sv"]).get(mode_id) or mode_id
        return mode_id

    def resolve(self, value):
        """Läge från id eller namn (oavsett språk och skiftläge)."""
        v = (value or "").strip().lower()
        for m in self.modes():
            names = {m["id"].lower(), (m.get("name") or "").lower()}
            names |= {d.get(m["id"], "").lower() for d in DEFAULT_NAMES.values()}
            if v and v in names:
                return m["id"]
        return None

    def current(self):
        cur = (self.cfg.get("mode") or {}).get("current")
        ids = [m["id"] for m in self.modes()]
        if cur not in ids and ids:
            return ids[0]
        return cur

    def info(self):
        m = self.cfg.get("mode") or {}
        cur = self.current()
        return {"current": cur, "name": self.name(cur), "source": m.get("source"), "since": m.get("since"),
                "homemode": self.homemode, "homemode_error": self.homemode_error,
                "follow_homemode": bool(self.cfg.get("mode_auto", "homemode", "enabled"))}

    def set(self, mode_id, source):
        if mode_id not in [m["id"] for m in self.modes()]:
            raise ValueError(mode_id)
        old = self.current()
        self.cfg.update(lambda d: d.__setitem__("mode", {"current": mode_id, "source": source,
                                                          "since": time.time()}))
        if old != mode_id:
            log.info("Läge: %s -> %s (%s)", old, mode_id, source)
            src = {"manual": tr("manuellt"), "webhook": "webhook", "schedule": tr("schema"),
                   "homemode": "Home Mode", "import": "import"}.get(source, source)
            self.note("SynoArgus", tr("Läge: {a} → {b} ({src})", a=self.name(old), b=self.name(mode_id), src=src))
        return mode_id

    # ---------------------------------------------------------------- automatik
    async def poll_homemode(self):
        hm = self.cfg.get("mode_auto", "homemode") or {}
        if not hm.get("enabled"):
            self.homemode = None
            self.homemode_error = None
            return
        try:
            state = find_homemode(await self.ss.homemode_get())
            self.homemode_error = None if state is not None else "?"
        except Exception as e:
            state = None
            self.homemode_error = str(e)
        if state is None:
            return
        if state != self.homemode:
            self.homemode = state
            target = hm.get("on") if state else hm.get("off")
            if target and target in [m["id"] for m in self.modes()]:
                self.set(target, "homemode")

    def check_schedule(self, now=None):
        now = now or datetime.now()
        hhmm = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        for i, e in enumerate(self.cfg.get("mode_auto", "schedule") or []):
            key = (today, i, e.get("time"), e.get("mode"))
            if e.get("time") == hhmm and now.weekday() in (e.get("days") or list(range(7))) and key not in self._fired:
                self._fired.add(key)
                if e.get("mode") in [m["id"] for m in self.modes()]:
                    self.set(e["mode"], "schedule")
        # glöm gamla dagar
        self._fired = {k for k in self._fired if k[0] == today}

    async def loop(self):
        while True:
            try:
                await self.poll_homemode()
                self.check_schedule()
            except Exception as e:
                log.warning("Lägesautomatik: %s", e)
            await asyncio.sleep(20)
