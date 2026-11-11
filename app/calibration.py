"""Kalibrering av Surveillance Stations rörelsedetektering (känslighet/tröskel).

Under en period (12-72 h) per kamera:
  - Bildpar: var 30:e sekund två bilder med ~1 s mellanrum. SynoArgus mäter själv hur stor del av
    kamerans detekteringsområde som ändrades (vid flera pixelnivåer) och låter AI:n avgöra om en
    av kamerans typer syns och rör sig. Det ger två fördelningar: brus och mål i rörelse.
  - Reaktioner: varje anrop från Surveillance Station loggas, med AI-resultat.
Inga bilder sparas, bara siffror.

Rapporten visar hur de nuvarande inställningarna beter sig (brusandel, missade mål) och föreslår
nya värden i steg om 5, högst ±10 per värde. Synology beskriver inte sin algoritm, så kopplingen
mellan känslighet/tröskel och SynoArgus egen mätning är en uppskattning:
  känslighet S (1-99)  -> pixelförändring som räknas:  4 + (99 - S) * 60/98  (av 255)
  tröskel T (1-99)     -> andel av detekteringsområdet som måste ändras: T %
Förslaget används aldrig automatiskt och kan ångras.
"""
import asyncio
import json
import logging
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime

import numpy as np
from PIL import Image

from .config import DB_PATH

log = logging.getLogger("synoargus.calibration")

LEVELS = [4, 8, 12, 16, 24, 32, 48, 64]   # pixelnivåer (0-255) där andelen ändrad yta mäts
DIFF_SIZE = (160, 90)
PAIR_INTERVAL = 30          # sekunder mellan bildpar
WALK_FPS = 3                # "Jag går förbi nu": 3 bilder per sekund ...
WALK_SECONDS = 90           # ... i 90 sekunder
WALK_GAP = 1.0              # rörelsen mäts mellan bilder 1 s isär (bild i mot i+3)
REACTION_AI_GAP = 5         # högst en AI-analys per 5 s och kamera för reaktioner
MISS_BEFORE, MISS_AFTER = 60, 15   # en reaktion inom detta fönster räknas som träff
MIN_REACTIONS, MIN_TARGETS, MIN_NOISE = 20, 2, 30
MAX_STEP, STEP = 10, 5

_lock = threading.Lock()


class BusyError(Exception):
    """En kalibrering pågår redan (på kameran i args[0])."""


def _db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _lock, _db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS calib_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, camera TEXT NOT NULL, started REAL, ends REAL,
            status TEXT, walk_until REAL DEFAULT 0, before TEXT, applied TEXT, report TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS calib_samples (
            run_id INTEGER, ts REAL, kind TEXT, levels TEXT, target INTEGER, moving INTEGER,
            night INTEGER, walk INTEGER, result TEXT)""")
        con.execute("CREATE INDEX IF NOT EXISTS ix_calib_samples ON calib_samples(run_id)")


# ------------------------------------------------------------------ mätning

def region_mask(region, w, h):
    """Detekteringsområdet (sträng med 0/1) som mask i storleken w x h. None = hela bilden."""
    if not isinstance(region, str) or not region or set(region) - set("01") or "1" not in region:
        return None
    n = len(region)
    best = None
    if n % 40 == 0 and n // 40 >= 3:   # Surveillance Station använder 40 kolumner
        best = (0, 40, n // 40)
    for cols in ([] if best else range(4, n + 1)):
        if n % cols:
            continue
        rows = n // cols
        if rows < 3:
            continue
        err = abs(cols / rows - w / h)
        if best is None or err < best[0]:
            best = (err, cols, rows)
    if best is None:
        return None
    _, cols, rows = best
    grid = np.array([c == "1" for c in region]).reshape(rows, cols)
    ys = (np.arange(h) * rows // h)
    xs = (np.arange(w) * cols // w)
    return grid[ys][:, xs]


def diff_map(a, b):
    ga = np.asarray(a.convert("L").resize(DIFF_SIZE, Image.BILINEAR), dtype=np.float32)
    gb = np.asarray(b.convert("L").resize(DIFF_SIZE, Image.BILINEAR), dtype=np.float32)
    return np.abs(ga - gb)


def levels_from(d, mask):
    vals = d[mask] if mask is not None else d.ravel()
    if vals.size == 0:
        vals = d.ravel()
    return [round(float((vals > lv).mean()), 5) for lv in LEVELS]


def is_night(img):
    hsv = np.asarray(img.convert("RGB").resize((64, 36)).convert("HSV"), dtype=np.float32)
    return bool(hsv[:, :, 1].mean() < 14)  # nästan ingen färg = IR/mörker


def box_moving(d, box, img_size, level=24, share=0.05):
    w, h = img_size
    sx, sy = DIFF_SIZE[0] / w, DIFF_SIZE[1] / h
    x1, y1 = int(box["x1"] * sx), int(box["y1"] * sy)
    x2, y2 = max(x1 + 1, int(box["x2"] * sx)), max(y1 + 1, int(box["y2"] * sy))
    part = d[y1:y2, x1:x2]
    return bool(part.size and (part > level).mean() > share)


# ------------------------------------------------------------------ förslag

def pix_threshold(sens):
    return 4 + (99 - sens) * 60 / 98


def frac_at(levels, pix):
    return float(np.interp(pix, LEVELS, levels))


def would_trigger(levels, sens, thr):
    return frac_at(levels, pix_threshold(sens)) * 100 >= thr


def evaluate(pairs, sens, thr):
    tgt = [p for p in pairs if p["target"] and p["moving"]]
    noise = [p for p in pairs if not p["target"]]
    recall = sum(would_trigger(p["levels"], sens, thr) for p in tgt) / len(tgt) if tgt else None
    noise_rate = sum(would_trigger(p["levels"], sens, thr) for p in noise) / len(noise) if noise else None
    return recall, noise_rate


def propose(pairs, cur_s, cur_t, lo=1, hi=99):
    """Bästa kandidat inom ±MAX_STEP i steg om STEP. Missa inte fler mål än i dag, minska bruset."""
    tgt = [p for p in pairs if p["target"] and p["moving"]]
    noise = [p for p in pairs if not p["target"]]
    r0, n0 = evaluate(pairs, cur_s, cur_t)
    cands = []
    for ds in range(-MAX_STEP, MAX_STEP + 1, STEP):
        for dt in range(-MAX_STEP, MAX_STEP + 1, STEP):
            s, t = cur_s + ds, cur_t + dt
            if not (lo <= s <= hi and lo <= t <= hi):
                continue
            r, n = evaluate(pairs, s, t)
            cands.append((s, t, r, n))
    if not cands:
        return None
    if tgt:
        need = r0 if r0 is not None else 0
        ok = [c for c in cands if c[2] is not None and c[2] >= min(need, 1.0) - 1e-9]
        ok = ok or cands
        # högst träffsäkerhet, sedan minst brus, sedan minsta ändring
        best = max(ok, key=lambda c: (round(c[2] or 0, 3), -(c[3] or 0),
                                      -abs(c[0] - cur_s) - abs(c[1] - cur_t)))
    elif noise:
        # bara brus: gå högst ett steg mot mindre känsligt
        ok = [c for c in cands if c[0] <= cur_s and c[1] >= cur_t and
              abs(c[0] - cur_s) + abs(c[1] - cur_t) <= STEP]
        best = min(ok, key=lambda c: (c[3] or 0, abs(c[0] - cur_s) + abs(c[1] - cur_t)))
    else:
        return None
    return {"sensitivity": best[0], "threshold": best[1], "recall": best[2], "noise": best[3],
            "recall_now": r0, "noise_now": n0, "only_noise": not tgt}


def build_report(samples, cur_s, cur_t, lo=1, hi=99, started=None, ends=None):
    pairs = [s for s in samples if s["kind"] == "pair"]
    reacts = [s for s in samples if s["kind"] == "reaction"]
    tgt_pairs = [p for p in pairs if p["target"] and p["moving"]]
    react_ts = sorted(r["ts"] for r in reacts)

    def reacted_near(ts):
        import bisect
        i = bisect.bisect_left(react_ts, ts - MISS_BEFORE)
        return i < len(react_ts) and react_ts[i] <= ts + MISS_AFTER
    missed = [p for p in tgt_pairs if not reacted_near(p["ts"])]
    analysed = [r for r in reacts if r["target"] is not None]
    with_target = [r for r in analysed if r["target"]]
    hours = [0] * 24
    for r in reacts:
        hours[datetime.fromtimestamp(r["ts"]).hour] += 1

    def part(night):
        ps = [p for p in pairs if bool(p["night"]) == night]
        rs = [r for r in analysed if bool(r["night"]) == night]
        prop = None
        if sum(1 for p in ps if p["target"] and p["moving"]) >= MIN_TARGETS and \
                sum(1 for p in ps if not p["target"]) >= MIN_NOISE // 2:
            prop = propose(ps, cur_s, cur_t, lo, hi)
        return {"pairs": len(ps), "targets": sum(1 for p in ps if p["target"] and p["moving"]),
                "reactions": len(rs), "noise_reactions": sum(1 for r in rs if not r["target"]),
                "proposal": prop}

    enough = len(reacts) >= MIN_REACTIONS or sum(1 for p in pairs if not p["target"]) >= MIN_NOISE
    full = enough and len(tgt_pairs) >= MIN_TARGETS
    proposal = propose(pairs, cur_s, cur_t, lo, hi) if enough else None
    day, night = part(False), part(True)
    conflict = False
    if day["proposal"] and night["proposal"]:
        def direction(p):  # + = känsligare, - = mindre känsligt
            return (p["sensitivity"] - cur_s) - (p["threshold"] - cur_t)
        dd, dn = direction(day["proposal"]), direction(night["proposal"])
        conflict = dd * dn < 0
    if proposal and proposal["sensitivity"] == cur_s and proposal["threshold"] == cur_t:
        proposal["unchanged"] = True
    return {
        "current": {"sensitivity": cur_s, "threshold": cur_t},
        "started": started, "ends": ends,
        "pairs": len(pairs), "target_pairs": len(tgt_pairs), "walk_pairs": sum(1 for p in pairs if p["walk"]),
        "reactions": len(reacts), "reactions_analysed": len(analysed), "reactions_target": len(with_target),
        "noise_share": (1 - len(with_target) / len(analysed)) if analysed else None,
        "missed": len(missed), "missed_times": [m["ts"] for m in missed[:20]],
        "hours": hours, "day": day, "night": night, "day_night_conflict": conflict,
        "enough": enough, "full": full, "proposal": proposal,
        "limits": {"min_reactions": MIN_REACTIONS, "min_targets": MIN_TARGETS, "min_noise": MIN_NOISE},
    }


# ------------------------------------------------------------------ körning

class CalibrationManager:
    def __init__(self, cfg, engine, md_view):
        self.cfg = cfg
        self.engine = engine
        self.md_view = md_view      # funktion: kamera -> (känslighet, tröskel, min, max, region)
        self._next = {}             # run_id -> tid för nästa bildpar
        self._busy = set()
        self._last_react_ai = {}
        self.slow = {}              # run_id -> True om analysen är långsam (glesare bildpar)
        self._walk_task = None
        self.watch_active = lambda: None    # sätts i main: kameran som bevakas, annars None
        self.walk_info = None       # {"camera", "until", "frames", "analysed"} under "Jag går förbi nu"

    # ---- databas
    def _run(self, camera):
        with _lock, _db() as con:
            r = con.execute("SELECT * FROM calib_runs WHERE camera=? ORDER BY id DESC LIMIT 1", (camera,)).fetchone()
        return dict(r) if r else None

    def running(self, camera):
        r = self._run(camera)
        return r if r and r["status"] == "running" else None

    def active(self):
        """Kameran som kalibreras just nu (bara en i taget), annars None."""
        with _lock, _db() as con:
            r = con.execute("SELECT camera FROM calib_runs WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
        return r[0] if r else None

    def walking(self):
        return bool(self._walk_task and not self._walk_task.done())

    def _samples(self, run_id):
        with _lock, _db() as con:
            rows = con.execute("SELECT * FROM calib_samples WHERE run_id=? ORDER BY ts", (run_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["levels"] = json.loads(d["levels"]) if d["levels"] else None
            d["target"] = None if d["target"] is None else bool(d["target"])
            out.append(d)
        return out

    def _add(self, run_id, kind, levels=None, target=None, moving=None, night=None, walk=False, result=None,
             ts=None):
        with _lock, _db() as con:
            con.execute("INSERT INTO calib_samples (run_id, ts, kind, levels, target, moving, night, walk, result) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (run_id, ts or time.time(), kind, json.dumps(levels) if levels else None,
                         None if target is None else int(target), int(bool(moving)), int(bool(night)),
                         int(bool(walk)), result))

    def _update(self, run_id, **kw):
        cols = ", ".join(f"{k}=?" for k in kw)
        with _lock, _db() as con:
            con.execute(f"UPDATE calib_runs SET {cols} WHERE id=?", (*kw.values(), run_id))

    # ---- åtgärder
    async def start(self, camera, hours):
        hours = max(12, min(72, int(hours)))
        other = self.active()
        if other:
            raise BusyError(other)
        if self.watch_active():
            raise BusyError("watch:" + self.watch_active())
        s, t, lo, hi, _ = await self.md_view(camera)
        now = time.time()
        with _lock, _db() as con:
            cur = con.execute("INSERT INTO calib_runs (camera, started, ends, status, before) VALUES (?,?,?,?,?)",
                              (camera, now, now + hours * 3600, "running",
                               json.dumps({"sensitivity": s, "threshold": t})))
            rid = cur.lastrowid
        self._next[rid] = now + 2
        log.info("Kalibrering startad för %s (%d h)", camera, hours)
        return rid

    def walk(self, camera):
        r = self.running(camera)
        if not r:
            raise ValueError("not running")
        if self.walking():
            return self.walk_info["until"]
        until = time.time() + WALK_SECONDS
        self._update(r["id"], walk_until=until)
        r["walk_until"] = until
        self.engine.priority_until = until      # kalibreringen går före larm
        self.walk_info = {"camera": camera, "until": until, "frames": 0, "analysed": 0}
        self._walk_task = asyncio.create_task(self._walk(r, until))
        return until

    def _stop_walk(self):
        if self.walking():
            self._walk_task.cancel()
        self.engine.priority_until = 0

    async def stop(self, camera):
        r = self.running(camera)
        if r:
            self._stop_walk()
            await self._finish(r, "stopped")

    def clear(self, camera):
        with _lock, _db() as con:
            ids = [x[0] for x in con.execute("SELECT id FROM calib_runs WHERE camera=? AND status!='running'",
                                             (camera,))]
            for i in ids:
                con.execute("DELETE FROM calib_samples WHERE run_id=?", (i,))
                con.execute("DELETE FROM calib_runs WHERE id=?", (i,))

    async def report(self, camera, preliminary=True):
        r = self._run(camera)
        if not r:
            return None
        if r["report"] and r["status"] != "running":
            rep = json.loads(r["report"])
        else:
            before = json.loads(r["before"] or "{}")
            try:
                _, _, lo, hi, _ = await self.md_view(camera)
            except Exception:
                lo, hi = 1, 99
            rep = build_report(self._samples(r["id"]), before.get("sensitivity"), before.get("threshold"),
                               lo, hi, r["started"], r["ends"])
            rep["preliminary"] = True
        return {"id": r["id"], "camera": camera, "status": r["status"], "started": r["started"], "ends": r["ends"],
                "walk_until": r["walk_until"], "before": json.loads(r["before"] or "null"),
                "applied": json.loads(r["applied"] or "null"), "report": rep, "slow": self.slow.get(r["id"], False),
                "walk": self.walk_info if self.walking() and self.walk_info["camera"] == camera else None}

    def set_applied(self, camera, values):
        r = self._run(camera)
        if r:
            self._update(r["id"], applied=json.dumps(values) if values else None)

    async def _finish(self, r, status):
        before = json.loads(r["before"] or "{}")
        try:
            _, _, lo, hi, _ = await self.md_view(r["camera"])
        except Exception:
            lo, hi = 1, 99
        rep = build_report(self._samples(r["id"]), before.get("sensitivity"), before.get("threshold"),
                           lo, hi, r["started"], r["ends"])
        if self.walk_info and self.walk_info["camera"] == r["camera"]:
            self._stop_walk()
        self._update(r["id"], status=status, report=json.dumps(rep))
        # rådata behövs inte längre när rapporten är sparad
        with _lock, _db() as con:
            con.execute("DELETE FROM calib_samples WHERE run_id=?", (r["id"],))
        self._next.pop(r["id"], None)
        log.info("Kalibrering för %s klar (%s)", r["camera"], status)

    # ---- insamling
    async def on_reaction(self, camera, cam):
        r = self.running(camera)
        if not r:
            return
        now = time.time()
        if now - self._last_react_ai.get(camera, 0) < REACTION_AI_GAP or self._any_busy() or self.walking():
            self._add(r["id"], "reaction", walk=now < (r["walk_until"] or 0))
            return
        self._last_react_ai[camera] = now
        try:
            img = await self.engine.grab(cam)
            await asyncio.to_thread(self.engine.ensure_model)
            dets, valid = await asyncio.to_thread(self.engine.analyse, cam, img)
            self._add(r["id"], "reaction", target=bool(valid), night=is_night(img), walk=now < (r["walk_until"] or 0))
        except Exception as e:
            log.debug("Kalibrering, reaktion %s: %s", camera, e)
            self._add(r["id"], "reaction", walk=now < (r["walk_until"] or 0))

    def _any_busy(self):
        return any(st.busy for st in self.engine.state.values())

    async def _pair(self, r):
        camera = r["camera"]
        cam = (self.cfg.get("cameras") or {}).get(camera)
        if not cam:
            return
        _, _, _, _, region = await self.md_view(camera)
        a = await self.engine.grab(cam)
        await asyncio.sleep(1.0)
        b = await self.engine.grab(cam)
        d = await asyncio.to_thread(diff_map, a, b)
        mask = region_mask(region, *DIFF_SIZE)
        levels = levels_from(d, mask)
        await asyncio.to_thread(self.engine.ensure_model)
        t0 = time.time()
        dets, valid = await asyncio.to_thread(self.engine.analyse, cam, b)
        ms = (time.time() - t0) * 1000
        self.slow[r["id"]] = ms > 2000
        moving = any(box_moving(d, v, b.size) for v in valid)
        self._add(r["id"], "pair", levels=levels, target=bool(valid), moving=moving, night=is_night(b),
                  walk=time.time() < (r["walk_until"] or 0))

    async def _walk(self, r, until):
        """3 bilder per sekund i 90 s. AI:n analyserar så många bilder den hinner (den nyaste först);
        varje analyserad bild jämförs med bilden ~1 s före. Bara analyserade bilder blir bildpar."""
        camera = r["camera"]
        cam = (self.cfg.get("cameras") or {}).get(camera)
        frames = deque(maxlen=WALK_FPS * 4)
        done = asyncio.Event()
        try:
            if not cam:
                return
            try:
                _, _, _, _, region = await self.md_view(camera)
            except Exception:
                region = None
            mask = region_mask(region, *DIFF_SIZE)
            await asyncio.to_thread(self.engine.ensure_model)

            async def grabber():
                t0, k = time.time(), 0
                try:
                    while time.time() < until:
                        delay = t0 + k / WALK_FPS - time.time()
                        if delay > 0:
                            await asyncio.sleep(delay)
                        try:
                            img = await self.engine.grab(cam)
                            frames.append((time.time(), img))
                            self.walk_info["frames"] += 1
                        except Exception as e:
                            log.debug("Kalibrering, bild %s: %s", camera, e)
                        k = max(k + 1, int((time.time() - t0) * WALK_FPS))   # hoppa över om vi ligger efter
                finally:
                    done.set()

            def partner(b_ts):
                best = None
                for ts, img in frames:
                    err = abs(b_ts - ts - WALK_GAP)
                    if err <= 0.4 and (best is None or err < best[0]):
                        best = (err, img)
                return best[1] if best else None

            async def analyser():
                last = 0
                while not done.is_set():
                    pick = None
                    for ts, img in reversed(frames):
                        if ts <= last:
                            break
                        a = partner(ts)
                        if a is not None:
                            pick = (ts, a, img)
                            break
                    if not pick:
                        await asyncio.sleep(0.1)
                        continue
                    ts, a, b = pick
                    last = ts
                    d = await asyncio.to_thread(diff_map, a, b)
                    levels = levels_from(d, mask)
                    dets, valid = await asyncio.to_thread(self.engine.analyse, cam, b)
                    moving = any(box_moving(d, v, b.size) for v in valid)
                    self._add(r["id"], "pair", levels=levels, target=bool(valid), moving=moving,
                              night=is_night(b), walk=True, ts=ts)
                    self.walk_info["analysed"] += 1

            await asyncio.gather(grabber(), analyser())
            log.info("Jag går förbi nu (%s): %d bilder, %d analyserade", camera,
                     self.walk_info["frames"], self.walk_info["analysed"])
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("Kalibrering, jag går förbi nu %s: %s", camera, e)
        finally:
            self.engine.priority_until = 0
            self._next[r["id"]] = time.time() + PAIR_INTERVAL

    async def loop(self):
        init_db()
        while True:
            try:
                with _lock, _db() as con:
                    runs = [dict(x) for x in con.execute("SELECT * FROM calib_runs WHERE status='running'")]
                now = time.time()
                for r in runs:
                    if now >= r["ends"]:
                        await self._finish(r, "done")
                        continue
                    if r["id"] in self._busy or now < self._next.get(r["id"], 0):
                        continue
                    if self.walking() or self._any_busy():   # vanliga larm går före de vanliga bildparen
                        continue
                    interval = PAIR_INTERVAL * (2 if self.slow.get(r["id"]) else 1)
                    self._next[r["id"]] = now + interval
                    self._busy.add(r["id"])

                    async def run_pair(r=r):
                        try:
                            await self._pair(r)
                        except Exception as e:
                            log.debug("Kalibrering, bildpar %s: %s", r["camera"], e)
                        finally:
                            self._busy.discard(r["id"])
                    asyncio.create_task(run_pair())
            except Exception as e:
                log.warning("Kalibrering: %s", e)
            await asyncio.sleep(2)
