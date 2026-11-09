"""Lägen (t.ex. Hemma / Natt / Borta): vilka kameror larmar och vilka notifierare skickar.

Läget ändras av den som ändrar det senast:
  - manuellt i gränssnittet
  - webhook (/api/mode, t.ex. från Homey)
  - schema (vid en viss tid vissa dagar)
  - Home Mode i Surveillance Station (när det slås på eller av)

Schemat kan också välja "↩ Följ Home Mode" eller "↩ Föregående läge". Mellan ett schemabyte och
återgången väntar Home Mode-ändringar (de tillämpas vid "Följ Home Mode"). Ett manuellt byte eller
ett byte via webhook gäller direkt och avbryter väntan.
"""
import asyncio
import logging
import time
from datetime import datetime

from .i18n import lang, tr
from .synology import find_homemode

log = logging.getLogger("synoargus.modes")

FOLLOW_HM = "@homemode"
PREVIOUS = "@previous"
SPECIAL = (FOLLOW_HM, PREVIOUS)

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
                "follow_homemode": bool(self.cfg.get("mode_auto", "homemode", "enabled")),
                "hold": bool(m.get("hold")), "previous": m.get("previous"),
                "previous_name": self.name(m["previous"]) if m.get("previous") else None}

    def set(self, mode_id, source):
        if mode_id not in [m["id"] for m in self.modes()]:
            raise ValueError(mode_id)
        old = self.current()

        def upd(d):
            m = dict(d.get("mode") or {})
            if source == "schedule":
                if not m.get("hold"):
                    m["previous"] = old     # läget före schemaperioden
                m["hold"] = True
            elif source in ("manual", "webhook", "import"):
                m["hold"] = False
                m["previous"] = None
            m.update(current=mode_id, source=source, since=time.time())
            d["mode"] = m
        self.cfg.update(upd)
        if old != mode_id:
            log.info("Läge: %s -> %s (%s)", old, mode_id, source)
            src = {"manual": tr("manuellt"), "webhook": "webhook", "schedule": tr("schema"),
                   "schedule_return": tr("schema"), "homemode": "Home Mode", "import": "import"}.get(source, source)
            self.note("SynoArgus", tr("Läge: {a} → {b} ({src})", a=self.name(old), b=self.name(mode_id), src=src))
        return mode_id

    def homemode_target(self):
        hm = self.cfg.get("mode_auto", "homemode") or {}
        if not hm.get("enabled") or self.homemode is None:
            return None
        t = hm.get("on") if self.homemode else hm.get("off")
        return t if t in [m["id"] for m in self.modes()] else None

    def release(self, how):
        """Schemats återgång: Följ Home Mode (annars föregående läge) eller Föregående läge."""
        m = self.cfg.get("mode") or {}
        prev = m.get("previous")
        target = self.homemode_target() if how == FOLLOW_HM else None
        if target is None and prev in [x["id"] for x in self.modes()]:
            target = prev

        def clear(d):
            mm = dict(d.get("mode") or {})
            mm["hold"] = False
            mm["previous"] = None
            d["mode"] = mm
        self.cfg.update(clear)
        if target:
            self.set(target, "schedule_return")
        return target

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
            target = self.homemode_target()
            if not target:
                return
            if (self.cfg.get("mode") or {}).get("hold"):
                # schemaperiod: tillämpas när schemat återgår till Home Mode
                self.note("SynoArgus", tr("Home Mode {s} – väntar på schemat", s=tr("på") if state else tr("av")))
                return
            self.set(target, "homemode")

    def check_schedule(self, now=None):
        now = now or datetime.now()
        hhmm = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        for i, e in enumerate(self.cfg.get("mode_auto", "schedule") or []):
            key = (today, i, e.get("time"), e.get("mode"))
            if e.get("time") == hhmm and now.weekday() in (e.get("days") or list(range(7))) and key not in self._fired:
                self._fired.add(key)
                if e.get("mode") in SPECIAL:
                    self.release(e["mode"])
                elif e.get("mode") in [m["id"] for m in self.modes()]:
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
