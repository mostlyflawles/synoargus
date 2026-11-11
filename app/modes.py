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
from datetime import datetime, timedelta
from datetime import time as dtime

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
        m = cfg.get("mode") or {}
        # senast kända Home Mode sparas, så att en omstart inte skriver över ett läge som satts för hand
        self.homemode = m.get("hm_state") if (cfg.get("mode_auto", "homemode") or {}).get("enabled") else None
        self.homemode_error = None
        self._sched_seen = None     # tidpunkt för senaste schemakontroll
        self._sched_saved = 0

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

            def remember(d):
                d.setdefault("mode", {})["hm_state"] = state
            self.cfg.update(remember)
            target = self.homemode_target()
            if not target:
                return
            if (self.cfg.get("mode") or {}).get("hold"):
                # schemaperiod: tillämpas när schemat återgår till Home Mode
                self.note("SynoArgus", tr("Home Mode {s} – väntar på schemat", s=tr("på") if state else tr("av")))
                return
            self.set(target, "homemode")

    def check_schedule(self, now=None):
        """Kör schemapunkter som har passerats sedan förra kontrollen (även efter omstart, högst 24 h bakåt).
        En punkt som är äldre än det senaste lägesbytet hoppas över – det senaste som ändrar läget gäller."""
        now = now or datetime.now()
        m = self.cfg.get("mode") or {}
        last = self._sched_seen
        if last is None:
            last = m.get("sched_seen") or (now.timestamp() - 60)
        last = min(max(last, now.timestamp() - 86400), now.timestamp())
        last_dt = datetime.fromtimestamp(last)
        due = []
        for e in self.cfg.get("mode_auto", "schedule") or []:
            try:
                hh, mm = (int(x) for x in str(e.get("time")).split(":"))
            except ValueError:
                continue
            for back in (0, 1):
                occ = datetime.combine((now - timedelta(days=back)).date(), dtime(hh, mm))
                if last_dt < occ <= now and occ.weekday() in (e.get("days") or list(range(7))):
                    due.append((occ, e))
        since = m.get("since") or 0
        fired = False
        for occ, e in sorted(due, key=lambda x: x[0]):
            if occ.timestamp() <= since:
                continue
            fired = True
            if e.get("mode") in SPECIAL:
                self.release(e["mode"])
            elif e.get("mode") in [x["id"] for x in self.modes()]:
                self.set(e["mode"], "schedule")
        self._sched_seen = now.timestamp()
        if fired or now.timestamp() - self._sched_saved > 600:
            self._sched_saved = now.timestamp()
            seen = self._sched_seen

            def remember(d):
                d.setdefault("mode", {})["sched_seen"] = seen
            self.cfg.update(remember)

    async def loop(self):
        while True:
            for step in (self.check_schedule, self.poll_homemode):   # schemat först: det får inte vänta på NAS:en
                try:
                    r = step()
                    if asyncio.iscoroutine(r):
                        await asyncio.wait_for(r, 30)
                except Exception as e:
                    log.warning("Lägesautomatik: %s", e or type(e).__name__)
            await asyncio.sleep(20)
