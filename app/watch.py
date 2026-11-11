"""Bevakning (experimentell): håller koll på en zon i en kamerabild och säger till när något avviker.

Bygger bara på rörelse: skillnaden mellan två bilder i rad, uppdelad i zonen och resten av bilden.
Utanför zonen följs rörelsen som spår (var den började, var den tog slut, hur länge den varade).

Händelser:
  arrive        ett spår slutar vid zonen (eller zonen blir aktiv)
  quiet         zonen är stilla i X s utan att något har lämnat den
  resume        rörelse i zonen igen efter "quiet"
  leave_toward  ett spår går från zonen mot kameran (nedåt i bilden / växer)
  leave_other   ett spår går från zonen åt annat håll
  enter         ett spår som inte började vid zonen har varat i X s
  linger        ett sådant spår stannar (vid zonen eller i bilden) i X s, eller är kvar länge
  timeout       bevakningen har pågått i X min

WatchCore är fristående (numpy + Pillow) så att den kan provas mot inspelade klipp.
"""
import asyncio
import io
import logging
import time
from collections import deque
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import notifiers, storage, validate
from .i18n import lang, tr

log = logging.getLogger("synoargus.watch")

W = 480                     # arbetsbredd i pixlar (höjden följer bildens proportioner)
CELL = 6                    # rutnät för att hitta sammanhängande rörelse
PIX_DIFF = 12               # så mycket måste en pixel ändras (0–255)
GLOBAL_SKIP = 0.20          # ändras mer än så av hela bilden är det ljus/exponering, inte rörelse
ZONE_WINDOW = 6.0           # sekunder som zonens aktivitet bedöms över
ZONE_ACTIVE_SHARE = 0.4     # andel bilder i fönstret med rörelse för att zonen ska räknas som aktiv
ZONE_ARRIVE_S = 5.0         # zonen aktiv så länge utan känd ankomst = ankomst
ARRIVE_DELAY = 6.0          # ett spår som tar slut vid zonen räknas som ankomst efter så lång tid
LOST_AFTER = 1.2            # sekunder utan träff innan ett spår räknas som stilla/försvunnet
PARK_KEEP = 120.0           # så länge kan ett stillastående spår tas upp igen
LEAVE_MIN = 3.0             # ett spår från zonen måste vara så länge för att räknas
LEAVE_DECIDE = 12.0         # senast då avgörs riktningen
REAL_WINDOW = 4.0           # ett spår är "på riktigt" när det har förflyttat sig rakt under så lång tid
                            # (längre än en gungning, så att en skugga som pendlar inte räknas)
VISITOR_S = 8.0             # så länge efter ett besök vid zonen räknas nya spår där som besökarens
STEAL_MAX = 4.0             # så länge får ett spår som går in i zonen följas där (någon som går förbi)
BG_ALPHA = 0.05             # hur snabbt bakgrunden följer ljusändringar
PRESENT_SHARE = 0.12        # andel av ytan som måste skilja sig från bakgrunden för att någon ska stå kvar
EVENT_KEYS = ("arrive", "quiet", "resume", "leave_toward", "leave_other", "enter", "linger", "timeout")
VEHICLES = ("car", "truck", "bus", "motorcycle", "bicycle", "train", "boat")

DEFAULT_EVENTS = {
    "arrive": {"on": True},
    "quiet": {"on": True, "seconds": 60},
    "resume": {"on": False},
    "leave_toward": {"on": True},
    "leave_other": {"on": True},
    "enter": {"on": True, "seconds": 3, "ignore_vehicles": True, "only_occupied": True, "cooldown": 30},
    "linger": {"on": True, "seconds": 12, "stay_seconds": 60, "cooldown": 30},
    "timeout": {"on": True, "minutes": 90},
}
SECONDS_LIMITS = {"quiet": (5, 3600), "enter": (1, 60), "linger": (3, 600)}


def defaults():
    return {"zone": None, "fps": 3, "test": False, "auto_stop_min": 120, "stop_on": ["leave_toward"],
            "use_exclusion_zones": True,
            "events": {k: {**v, "text": "", "notifiers": []} for k, v in DEFAULT_EVENTS.items()}}


def clean(body):
    """Kontrollerar en bevakning innan den sparas."""
    if not isinstance(body, dict):
        raise validate.Invalid("watch")
    out = defaults()
    if body.get("zone"):
        z = validate.box(body["zone"], "zone")
        if z["x2"] - z["x1"] < 0.02 or z["y2"] - z["y1"] < 0.02:
            raise validate.Invalid("zone")
        out["zone"] = z
    out["fps"] = validate._int(body.get("fps", 3), "fps", 2, 4)
    out["test"] = bool(body.get("test"))
    out["use_exclusion_zones"] = bool(body.get("use_exclusion_zones", True))
    out["auto_stop_min"] = validate._int(body.get("auto_stop_min", 120), "auto_stop_min", 0, 1440)
    out["stop_on"] = validate._strlist(body.get("stop_on", out["stop_on"]), "stop_on", EVENT_KEYS)
    ev = body.get("events") if isinstance(body.get("events"), dict) else {}
    for k in EVENT_KEYS:
        e = ev.get(k) if isinstance(ev.get(k), dict) else {}
        o = out["events"][k]
        o["on"] = bool(e.get("on", o["on"]))
        o["text"] = validate._str(e.get("text"), "text", 300)
        o["notifiers"] = validate._strlist(e.get("notifiers"), "notifiers")
        o["cooldown"] = validate._int(e.get("cooldown", o.get("cooldown", 0)), "cooldown", 0, 3600)
        if k in SECONDS_LIMITS:
            o["seconds"] = validate._int(e.get("seconds", o["seconds"]), k, *SECONDS_LIMITS[k])
        if k == "enter":
            o["ignore_vehicles"] = bool(e.get("ignore_vehicles", True))
            o["only_occupied"] = bool(e.get("only_occupied", True))
        if k == "linger":
            o["stay_seconds"] = validate._int(e.get("stay_seconds", 60), "stay_seconds", 10, 3600)
        if k == "timeout":
            o["minutes"] = validate._int(e.get("minutes", 90), "minutes", 1, 1440)
    return out


def prep(img):
    """Bild -> liten gråskalebild (numpy) för rörelsemätning."""
    w, h = img.size
    size = (W, max(8, round(W * h / w)))
    g = img.convert("L")
    if g.size != size:
        g = g.resize(size, Image.BILINEAR)
    return np.asarray(g.filter(ImageFilter.BoxBlur(1.5)), dtype=np.int16)


def decode_small(jpeg):
    """Avkodar en JPEG direkt i låg upplösning (snabbt) och förbereder den."""
    img = Image.open(io.BytesIO(jpeg))
    img.draft("L", (W, W))
    return prep(img)


class Track:
    _next = 1

    def __init__(self, ts, pos, size, near_zone, bbox=None):
        self.id = Track._next
        Track._next += 1
        self.t0 = self.t_last = self.seg0 = ts      # seg0: när spåret senast började röra sig
        self.p0 = self.p_last = pos
        self.n = 1
        self.sizes = [size]
        self.hist = deque([(ts, pos)], maxlen=64)   # senaste positionerna
        self.born_zone = near_zone
        self.bbox = bbox
        self.lost = False
        self.real = False           # har rört sig målmedvetet (inte brus, inte en skugga som pendlar)
        self.fired = set()
        self.parked = False

    def add(self, ts, pos, size, bbox):
        if ts - self.t_last > 5:
            self.seg0 = ts
        self.p_last, self.t_last, self.bbox = pos, ts, bbox
        self.n += 1
        self.sizes.append(size)
        del self.sizes[:-40]
        self.hist.append((ts, pos))
        self.lost = False

    @property
    def age(self):
        return self.t_last - self.t0

    def size_ratio(self):
        a, b = self.sizes[:4], self.sizes[-4:]
        return (sorted(b)[len(b) // 2] + 1) / (sorted(a)[len(a) // 2] + 1)

    def moved(self, window):
        """(nettoförflyttning, rakhet 0–1) under de senaste window sekunderna. (0, 0) om spåret inte
        har följts sammanhängande hela tiden – då går det inte att skilja en förflyttning från en pendling."""
        pts = [(t, p) for t, p in self.hist if t >= self.t_last - window]
        if len(pts) < 3 or pts[0][0] > self.t_last - 0.85 * window:
            return 0.0, 0.0
        if max(b[0] - a[0] for a, b in zip(pts, pts[1:])) > 1.2:
            return 0.0, 0.0
        pts = [p for _, p in pts]
        net = float(np.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]))
        path = sum(float(np.hypot(b[0] - a[0], b[1] - a[1])) for a, b in zip(pts, pts[1:]))
        return net, (net / path if path > 1 else 0.0)


class WatchCore:
    def __init__(self, cfg, shape, exclusion=None, occupied=False):
        """cfg: en bevakning (se defaults()), shape: (höjd, bredd) på arbetsbilden."""
        self.cfg = cfg
        self.h, self.w = shape
        z = cfg["zone"]
        self.zone = (int(z["x1"] * self.w), int(z["y1"] * self.h), int(np.ceil(z["x2"] * self.w)), int(np.ceil(z["y2"] * self.h)))
        zw, zh = self.zone[2] - self.zone[0], self.zone[3] - self.zone[1]
        mx, my = max(CELL, round(zw * 0.15)), max(CELL, round(zh * 0.15))
        self.zone_m = (self.zone[0] - mx, self.zone[1] - my, self.zone[2] + mx, self.zone[3] + my)     # zon + marginal
        nx, ny = max(3 * CELL, round(zw * 0.6)), max(3 * CELL, round(zh * 0.6))
        self.zone_near = (self.zone[0] - nx, self.zone[1] - ny, self.zone[2] + nx, self.zone[3] + ny)  # "vid zonen"
        self.zone_min = max(8, round(zw * zh * 0.003))
        self.gh, self.gw = self.h // CELL, self.w // CELL
        ys, xs = np.mgrid[0:self.gh, 0:self.gw]
        cx, cy = xs * CELL + CELL / 2, ys * CELL + CELL / 2
        self.cell_ok = np.ones((self.gh, self.gw), dtype=bool)
        for e in (exclusion or []) if cfg.get("use_exclusion_zones", True) else []:
            self.cell_ok &= ~((cx >= e["x1"] * self.w) & (cx <= e["x2"] * self.w) & (cy >= e["y1"] * self.h) & (cy <= e["y2"] * self.h))
        self.match_r = 0.13 * self.w
        self.real_far = 0.05 * self.w
        self.edge = 0.08
        self.prev = None
        self.bg = None              # långsam bakgrund: avgör om någon som slutade röra sig fortfarande står där
        self.start_active = None    # var zonen redan aktiv när bevakningen startade?
        self.t_start = None
        self.zone_hist = deque()
        self.zone_active = False
        self.zone_active_since = None
        self.zone_quiet_since = None
        self.ever_active = False
        self.quiet_fired = False
        self.occ = 1 if occupied else 0
        self.tracks = []
        self.fired_at = {}
        self.visitor_ts = -1e9      # senast ett spår utifrån var vid zonen
        self.last_ts = None
        self.stats = {"frames": 0, "skipped": 0}

    # ---------------------------------------------------------------- hjälpare
    def _in(self, box, p):
        return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]

    def _at_edge(self, p):
        ex, ey = self.edge * self.w, self.edge * self.h
        return p[0] < ex or p[0] > self.w - ex or p[1] < ey or p[1] > self.h - ey

    def _emit(self, events, key, ts, track=None, **extra):
        """Lägger till händelsen om den är påslagen och inte nyss har skickats (tystnadstid)."""
        c = self.cfg["events"][key]
        if not c.get("on"):
            return
        if ts - self.fired_at.get(key, -1e9) < (c.get("cooldown") or 0):
            return
        self.fired_at[key] = ts
        events.append(self._ev(key, ts, track, **extra))

    def _ev(self, key, ts, track=None, **extra):
        e = {"key": key, "ts": ts, **extra}
        if track is not None and track.bbox:
            x1, y1, x2, y2 = track.bbox
            e["bbox"] = [x1 / self.w, y1 / self.h, x2 / self.w, y2 / self.h]
            e["track"] = track.id
        return e

    def _on(self, key):
        return self.cfg["events"][key].get("on")

    def _update_real(self, t):
        if not t.real and t.n >= 6 and t.age >= REAL_WINDOW:
            net, straight = t.moved(REAL_WINDOW)
            if net >= self.real_far and straight >= 0.5:
                t.real = True

    def _real(self, t, min_age):
        return t.real and t.age >= min_age

    def _passing(self, ts, pos):
        """Rörelsen i zonen hör till ett spår som kom utifrån och just gick in (någon som går förbi)."""
        for t in self.tracks:
            if (t.real and not t.born_zone and ts - t.t_last <= LOST_AFTER
                    and np.hypot(pos[0] - t.p_last[0], pos[1] - t.p_last[1]) <= self.match_r):
                if not self._in(self.zone_m, t.p_last):
                    t.in_zone = ts              # var utanför zonen alldeles nyss
                    return True
                if ts - getattr(t, "in_zone", ts) <= STEAL_MAX:
                    return True
        return False

    def _same_arrival(self, t):
        """Andra spår som tog slut vid zonen samtidigt hör till samma ankomst (t.ex. en person i två delar)."""
        for o in self.tracks:
            if o is not t and o.lost and abs(o.t_last - t.t_last) <= 3 and self._in(self.zone_near, o.p_last):
                o.merged = True

    def _zone_blob(self, pos, bbox):
        """Rörelse som hör till zonen: mitten i zonen och hela rörelsen nära den."""
        n = self.zone_near
        return self._in(self.zone_m, pos) and bbox[0] >= n[0] and bbox[1] >= n[1] and bbox[2] <= n[2] and bbox[3] <= n[3]

    def _blobs(self, diff):
        """Sammanhängande rörelse -> [(pixlar, (cx, cy), bbox, rutor)], störst först."""
        d = diff[:self.gh * CELL, :self.gw * CELL]
        counts = d.reshape(self.gh, CELL, self.gw, CELL).sum(axis=(1, 3))
        active = (counts >= 3) & self.cell_ok
        if not active.any():
            return []
        seen = np.zeros_like(active)
        out = []
        for y, x in zip(*np.nonzero(active)):
            if seen[y, x]:
                continue
            stack, cells = [(y, x)], []
            seen[y, x] = True
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny in range(max(0, cy - 2), min(self.gh, cy + 3)):       # grannar inom två rutor hör ihop
                    for nx in range(max(0, cx - 2), min(self.gw, cx + 3)):
                        if active[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            ws = np.array([counts[c] for c in cells], dtype=float)
            px = int(ws.sum())
            if px < 6:
                continue
            cys = np.array([c[0] for c in cells]) * CELL + CELL / 2
            cxs = np.array([c[1] for c in cells]) * CELL + CELL / 2
            bbox = (int(cxs.min() - CELL / 2), int(cys.min() - CELL / 2), int(cxs.max() + CELL / 2), int(cys.max() + CELL / 2))
            out.append((px, (float((cxs * ws).sum() / px), float((cys * ws).sum() / px)), bbox, cells))
        out.sort(key=lambda b: -b[0])
        return out[:10]

    # ---------------------------------------------------------------- en bild
    def feed(self, ts, gray):
        """Tar emot en förberedd bild. Returnerar händelser som inträffade."""
        events = []
        if self.t_start is None:
            self.t_start = ts
        self.stats["frames"] += 1
        prev, self.prev = self.prev, gray
        if prev is None or prev.shape != gray.shape or (self.last_ts and ts - self.last_ts > 5):
            self.last_ts = ts
            if self.bg is None or self.bg.shape != gray.shape:
                self.bg = gray.astype(np.float32)
            return events
        self.last_ts = ts
        diff = np.abs(gray - prev) > PIX_DIFF
        if diff.mean() > GLOBAL_SKIP:
            self.stats["skipped"] += 1
            return events

        # ---- bakgrunden följer ljuset, utom där något rör sig eller nyss slutade röra sig
        all_blobs = self._blobs(diff)
        protect = np.zeros(gray.shape, dtype=bool)
        for _, _, bbox, _ in all_blobs:
            protect[self._box(bbox)] = True
        for t in self.tracks:
            if t.lost and t.real and t.bbox:
                protect[self._box(t.bbox)] = True
        upd = ~protect
        self.bg[upd] += BG_ALPHA * (gray[upd] - self.bg[upd])

        # ---- rörelse som går genom eller förbi zonen räknas inte som aktivitet i den
        blobs = []
        for px, pos, bbox, cells in all_blobs:
            if self._zone_blob(pos, bbox) and not self._passing(ts, pos):
                continue
            blobs.append((px, pos, bbox))
            for cy, cx in cells:
                diff[cy * CELL:(cy + 1) * CELL, cx * CELL:(cx + 1) * CELL] = False

        # ---- zonen
        z = self.zone
        zact = int(diff[max(0, z[1]):z[3], max(0, z[0]):z[2]].sum()) >= self.zone_min
        self.zone_hist.append((ts, zact))
        while self.zone_hist and ts - self.zone_hist[0][0] > ZONE_WINDOW:
            self.zone_hist.popleft()
        share = sum(1 for _, a in self.zone_hist if a) / len(self.zone_hist)
        warm = ts - self.t_start >= min(ZONE_WINDOW, 3.0)
        active = warm and share >= ZONE_ACTIVE_SHARE
        if warm and self.start_active is None:
            self.start_active = active
        if active and not self.zone_active:
            self.zone_active_since = ts
            self.zone_quiet_since = None
            if self.quiet_fired:
                self.quiet_fired = False
                self._emit(events, "resume", ts)
        if not active and self.zone_active:
            self.zone_quiet_since = ts
            self.zone_active_since = None
        self.zone_active = active
        if active:
            self.ever_active = True
            if self.occ == 0 and ts - self.zone_active_since >= ZONE_ARRIVE_S:
                self.occ = 1
                # redan aktiv när bevakningen startade: ingen ankomst att rapportera
                if not self.start_active:
                    self._emit(events, "arrive", ts)
                self.start_active = False
        q = self.cfg["events"]["quiet"]
        if (self.occ > 0 and self.ever_active and not active and not self.quiet_fired and self.zone_quiet_since
                and ts - self.zone_quiet_since >= q["seconds"]):
            self.quiet_fired = True
            self._emit(events, "quiet", ts, seconds=round(ts - self.zone_quiet_since))

        # ---- spår
        used = set()
        for px, pos, bbox in blobs:
            best, best_d = None, None
            for t in self.tracks:
                if t.id in used:
                    continue
                d = float(np.hypot(pos[0] - t.p_last[0], pos[1] - t.p_last[1]))
                r = self.match_r * (1.6 if t.lost else 1.0)
                # ett spår som försvann vid zonen får komma ut på andra sidan (någon som går förbi)
                through = t.lost and self._in(self.zone_near, t.p_last) and self._in(self.zone_near, pos)
                if (d <= r or through) and (best_d is None or d < best_d):
                    best, best_d = t, d
            if best is None:
                # nära zonen strax efter att någon utifrån var där: en förbipasserande, inte någon som lämnar zonen
                from_zone = self._in(self.zone_near, pos) and ts - self.visitor_ts > VISITOR_S
                best = Track(ts, pos, px, from_zone, bbox)
                self.tracks.append(best)
            else:
                best.add(ts, pos, px, bbox)
                best.parked = False
                self._update_real(best)
                if best.real and not best.born_zone and self._in(self.zone_near, pos):
                    self.visitor_ts = ts
            used.add(best.id)

        en, li = self.cfg["events"]["enter"], self.cfg["events"]["linger"]
        watching = self.occ > 0 or not en.get("only_occupied", True)
        keep = []
        for t in self.tracks:
            gone = ts - t.t_last
            if gone > LOST_AFTER and not t.lost:
                t.lost = True
                # gick ihop med ett annat spår (t.ex. en hund som hinner ikapp sin ägare): inte "stannat"
                for o in self.tracks:
                    if o is not t and o.real and not o.lost and ts - o.t_last <= LOST_AFTER and any(
                            tt >= t.t_last - 1 and np.hypot(pp[0] - t.p_last[0], pp[1] - t.p_last[1]) <= 1.5 * self.match_r
                            for tt, pp in o.hist):
                        t.merged = True
                        break
            if getattr(t, "merged", False):
                continue
            if not t.lost:
                # ---- pågående spår
                if t.born_zone and "leave" not in t.fired and self._real(t, LEAVE_MIN):
                    if "left" not in t.fired:
                        t.fired.add("left")
                        self.occ = max(0, self.occ - 1)
                    toward = (t.p_last[1] - t.p0[1]) >= 0.06 * self.h or t.size_ratio() >= 1.8
                    if toward or t.age >= LEAVE_DECIDE:
                        t.fired.add("leave")
                        key = "leave_toward" if toward else "leave_other"
                        self._emit(events, key, ts, t)
                if not t.born_zone and watching:
                    if "enter" not in t.fired and self._real(t, en["seconds"]):
                        t.fired.add("enter")
                        self._emit(events, "enter", ts, t)
                    if "stay" not in t.fired and "enter" in t.fired and ts - t.seg0 >= li["stay_seconds"]:
                        t.fired.add("stay")
                        self._emit(events, "linger", ts, t, where="image", seconds=round(ts - t.seg0))
                keep.append(t)
                continue
            # ---- spår som har tagit slut
            if not t.real:
                if gone < 2.5:
                    keep.append(t)
                continue
            if t.born_zone and "left" in t.fired and "leave" not in t.fired:
                # lämnade zonen men spåret tog slut innan riktningen var avgjord
                t.fired.add("leave")
                toward = (t.p_last[1] - t.p0[1]) >= 0.06 * self.h or t.size_ratio() >= 1.8
                key = "leave_toward" if toward else "leave_other"
                self._emit(events, key, ts, t)
            if self._at_edge(t.p_last) and not self._in(self.zone_near, t.p_last):
                continue                                    # gick ut ur bilden
            if self._in(self.zone_near, t.p_last):
                if self.occ == 0 or t.born_zone:
                    if gone >= ARRIVE_DELAY:
                        self.occ += 1
                        self._same_arrival(t)
                        if "left" in t.fired:
                            continue                        # kom tillbaka till zonen
                        self._emit(events, "arrive", ts, t)
                        continue
                elif gone >= li["seconds"]:
                    if not self._present(t, gray):
                        continue                            # försvann (t.ex. in i mörkret), stannade inte
                    self.occ += 1
                    self._same_arrival(t)
                    self._emit(events, "linger", ts, t, where="zone", seconds=round(gone))
                    continue
                keep.append(t)
                continue
            if not t.parked and gone >= li["seconds"] and not t.born_zone and watching:
                t.parked = True
                if not self._present(t, gray):
                    continue                                # syns inte längre: gick ut ur bilden eller in i mörkret
                if "linger" not in t.fired:
                    t.fired.add("linger")
                    self._emit(events, "linger", ts, t, where="image", seconds=round(gone))
            if gone < PARK_KEEP:
                keep.append(t)
        self.tracks = keep
        return events

    def _box(self, bbox):
        x1, y1, x2, y2 = bbox
        return (slice(max(0, int(y1) - CELL), min(self.h, int(y2) + CELL)),
                slice(max(0, int(x1) - CELL), min(self.w, int(x2) + CELL)))

    def _present(self, t, gray):
        """Står det något kvar där spåret slutade? Jämför med bakgrunden från innan det kom."""
        if not t.bbox:
            return True
        sl = self._box(t.bbox)
        d = np.abs(gray[sl] - self.bg[sl]) > PIX_DIFF * 1.5
        return d.size > 0 and float(d.mean()) >= PRESENT_SHARE

    def state(self):
        return {"occupied": self.occ, "zone_active": bool(self.zone_active), "tracks": sum(1 for t in self.tracks if not t.lost),
                **self.stats}


# ====================================================================== körning

TITLES = {
    "arrive": "Ankomst till zonen",
    "quiet": "Stilla i zonen",
    "resume": "Rörelse i zonen igen",
    "leave_toward": "Lämnar zonen, mot kameran",
    "leave_other": "Lämnar zonen, åt annat håll",
    "enter": "Någon kommer in i bild",
    "linger": "Någon dröjer kvar",
    "timeout": "Bevakningen har pågått länge",
}


class Busy(Exception):
    """Något annat pågår: args = (vad, kamera)."""


class WatchManager:
    def __init__(self, cfg, engine, ss):
        self.cfg = cfg
        self.engine = engine
        self.ss = ss
        self.active = None          # {"camera", "started", "core", "source", ...} medan en bevakning pågår
        self.log = deque(maxlen=100)
        self.calib_active = lambda: None    # sätts i main: kameran som kalibreras, annars None
        self._task = None

    # ---------------------------------------------------------------- inställningar
    def get(self, camera):
        return (self.cfg.get("watches") or {}).get(camera)

    def running(self):
        return self.active["camera"] if self.active else None

    def status(self):
        a = self.active
        out = {"active": a["camera"] if a else None, "log": list(self.log)[:60]}
        if a:
            core = a.get("core")
            out.update(since=a["started"], elapsed=round(time.time() - a["started"]), test=a["test"],
                       source=a["source"], fps=round(a.get("fps", 0), 1), ms=round(a.get("ms", 0)),
                       snapshot_ms=round(a.get("snap_ms", 0)), error=a.get("error"),
                       state=core.state() if core else None)
        return out

    def _note(self, camera, key, text, **extra):
        self.log.appendleft({"ts": time.time(), "camera": camera, "key": key, "text": text, **extra})

    # ---------------------------------------------------------------- start och stopp
    async def start(self, camera, occupied=False, source="manuellt"):
        w = self.get(camera)
        if not w or not w.get("zone"):
            raise ValueError("zone")
        if camera not in (self.cfg.get("cameras") or {}):
            raise ValueError("camera")
        if self.active:
            if self.active["camera"] == camera:
                return False
            raise Busy("watch", self.active["camera"])
        other = self.calib_active()
        if other:
            raise Busy("calibration", other)
        self.active = {"camera": camera, "started": time.time(), "core": None, "source": source,
                       "test": bool(w.get("test")), "occupied": bool(occupied), "timeout_fired": False}
        self._note(camera, "start", tr("Bevakningen startade ({src})", src=tr(source)))
        self._task = asyncio.create_task(self._run(camera))
        return True

    async def stop(self, reason="manuellt"):
        a, self.active = self.active, None
        if not a:
            return False
        if self._task and not self._task.done() and self._task is not asyncio.current_task():
            self._task.cancel()
        self._note(a["camera"], "stop", tr("Bevakningen stoppades ({src})", src=tr(reason)))
        return True

    def reload(self, camera):
        """Nya inställningar medan bevakningen pågår: börja om mätningen (läget i zonen behålls)."""
        a = self.active
        if a and a["camera"] == camera and a.get("core"):
            a["occupied"] = a["core"].occ > 0
            a["core"] = None
            a["test"] = bool((self.get(camera) or {}).get("test"))

    # ---------------------------------------------------------------- slingan
    async def _run(self, camera):
        a = self.active
        last_err = 0
        times = deque(maxlen=30)
        try:
            while self.active is a:
                w = self.get(camera)
                cam = (self.cfg.get("cameras") or {}).get(camera)
                if not w or not w.get("zone") or not cam:
                    await self.stop("inställningarna saknas")
                    return
                t0 = time.time()
                try:
                    cam_id = cam.get("ss_id")
                    if cam_id is None:
                        cam_id = await self.ss.resolve_id(camera)
                    jpeg = await self.ss.snapshot(cam_id)
                    a["snap_ms"] = 0.8 * a.get("snap_ms", 0) + 0.2 * (time.time() - t0) * 1000 if a.get("snap_ms") else (time.time() - t0) * 1000
                    t1 = time.time()
                    events = await asyncio.to_thread(self._feed, a, w, cam, t0, jpeg)
                    ms = (time.time() - t1) * 1000
                    a["ms"] = 0.8 * a["ms"] + 0.2 * ms if a.get("ms") else ms
                    a["jpeg"] = jpeg
                    a["error"] = None
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    events = []
                    a["error"] = str(e)[:200] or type(e).__name__
                    if time.time() - last_err > 60:
                        last_err = time.time()
                        log.warning("Bevakning %s: %s", camera, a["error"])
                times.append(t0)
                if len(times) > 3:
                    a["fps"] = (len(times) - 1) / max(0.001, times[-1] - times[0])
                elapsed = t0 - a["started"]
                to = w["events"]["timeout"]
                if to.get("on") and not a["timeout_fired"] and elapsed >= to["minutes"] * 60:
                    a["timeout_fired"] = True
                    events.append({"key": "timeout", "ts": t0, "minutes": to["minutes"]})
                for e in events:
                    if self.active is not a:
                        break
                    await self._handle(a, w, cam, e)
                    if e["key"] in (w.get("stop_on") or []) and not e.get("ignored"):
                        await self.stop("händelse")
                        return
                if self.active is a and w.get("auto_stop_min") and elapsed >= w["auto_stop_min"] * 60:
                    await self.stop("tidsgräns")
                    return
                await asyncio.sleep(max(0.02, 1.0 / max(1, w.get("fps") or 3) - (time.time() - t0)))
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Bevakning %s", camera)
            if self.active is a:
                self.active = None
                self._note(camera, "stop", tr("Bevakningen stoppades ({src})", src=tr("fel")))

    def _feed(self, a, w, cam, ts, jpeg):
        gray = decode_small(jpeg)
        if a["core"] is None or (a["core"].h, a["core"].w) != gray.shape:
            a["core"] = WatchCore(w, gray.shape, cam.get("zones"), occupied=a.get("occupied"))
        return a["core"].feed(ts, gray)

    # ---------------------------------------------------------------- händelser
    def _text(self, w, e, label=None):
        key = e["key"]
        custom = (w["events"][key].get("text") or "").strip()
        if custom:
            return custom
        text = tr(TITLES[key])
        if key == "linger":
            text = tr("Någon har stannat vid zonen") if e.get("where") == "zone" else tr("Någon dröjer kvar i bild")
        elif key == "quiet":
            text = tr("Stilla i zonen i {s} s", s=e.get("seconds", w["events"]["quiet"]["seconds"]))
        elif key == "timeout":
            text = tr("Bevakningen har pågått i {m} min", m=e.get("minutes"))
        if label:
            from .config import type_name
            text += f" ({type_name(label, lang()).lower()})"
        return text

    def _classify(self, jpeg, bbox):
        """Frågar AI:n vad som rör sig (i ett utsnitt runt rörelsen). Returnerar etikett eller None."""
        try:
            self.engine.ensure_model()
            img = Image.open(io.BytesIO(jpeg)).convert("RGB")
            iw, ih = img.size
            cx, cy = (bbox[0] + bbox[2]) / 2 * iw, (bbox[1] + bbox[3]) / 2 * ih
            side = max(320, 2.5 * max((bbox[2] - bbox[0]) * iw, (bbox[3] - bbox[1]) * ih))
            side = min(side, iw, ih)
            x1 = min(max(0, cx - side / 2), iw - side)
            y1 = min(max(0, cy - side / 2), ih - side)
            dets = self.engine.detector.detect(img.crop((int(x1), int(y1), int(x1 + side), int(y1 + side))))
            dets = [d for d in dets if d.get("confidence", 0) >= 35]
            return max(dets, key=lambda d: d["confidence"])["label"] if dets else None
        except Exception as e:
            log.debug("Bevakning, AI: %s", e)
            return None

    def _image(self, jpeg, w, bbox):
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        iw, ih = img.size
        d = ImageDraw.Draw(img)
        lw = max(2, round(iw / 400))
        z = w["zone"]
        d.rectangle([z["x1"] * iw, z["y1"] * ih, z["x2"] * iw, z["y2"] * ih], outline=(64, 156, 255), width=lw)
        if bbox:
            pad = 0.01
            d.rectangle([(bbox[0] - pad) * iw, (bbox[1] - pad) * ih, (bbox[2] + pad) * iw, (bbox[3] + pad) * ih],
                        outline=(240, 120, 60), width=lw)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue()

    async def _handle(self, a, w, cam, e):
        camera, key = a["camera"], e["key"]
        jpeg = a.get("jpeg")
        label = None
        if key in ("enter", "linger") and e.get("bbox") and jpeg:
            label = await asyncio.to_thread(self._classify, jpeg, e["bbox"])
            if label in VEHICLES and w["events"]["enter"].get("ignore_vehicles"):
                e["ignored"] = True
                self._note(camera, key, tr("Fordon i bild – ignoreras"), ignored=True)
                return
        text = self._text(w, e, label)
        image = None
        if jpeg:
            try:
                image = await asyncio.to_thread(self._image, jpeg, w, e.get("bbox"))
            except Exception:
                image = jpeg
        sent = []
        if a["test"]:
            self._note(camera, key, text, test=True)
            return
        try:
            event_id, rel = storage.save_event(camera, True, [text], [], image, 0)
            base = (self.cfg.get("public_url") or "").rstrip("/")
            event = {"camera": camera, "types": [], "detections": [], "event_id": event_id, "lang": lang(),
                     "message": f"{camera}: {text}", "watch_event": text, "watch_key": key,
                     "time": datetime.now().astimezone().isoformat(timespec="seconds"),
                     "image_url": f"{base}/captures/{rel}" if base and rel else None}
            mode = self.engine.modes.current() if self.engine.modes else None
            chosen = w["events"][key].get("notifiers") or []
            targets = [n for n in self.cfg.get("notifiers") or [] if n.get("enabled", True) and (
                n["id"] in chosen if chosen else notifiers.applies(n, camera, n.get("types") or ["x"], mode))]
            results = await asyncio.gather(*(notifiers.send(n, event, image) for n in targets))
            sent = [{"id": n["id"], "name": n.get("name") or n["type"], "ok": ok, "error": err}
                    for n, (ok, err) in zip(targets, results)]
            storage.set_notified(event_id, sent)
        except Exception as ex:
            log.warning("Bevakning %s, %s: %s", camera, key, ex)
        self._note(camera, key, text, sent=sent)
