"""Larmhistorik (SQLite) och bilder på disk, med automatisk rensning."""
import json
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta

from .config import CAPTURE_DIR, DB_PATH

_lock = threading.Lock()


def _db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init():
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    with _lock, _db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            camera TEXT NOT NULL,
            alarm INTEGER NOT NULL,
            types TEXT,
            detections TEXT,
            image TEXT,
            ms INTEGER,
            notified TEXT)""")
        con.execute("CREATE INDEX IF NOT EXISTS ix_events_ts ON events(ts)")
        cols = [r[1] for r in con.execute("PRAGMA table_info(events)")]
        if "meta" not in cols:      # 0.7: händelsens text m.m. för notifieringar på begäran
            con.execute("ALTER TABLE events ADD COLUMN meta TEXT")


def save_event(camera, alarm, types, dets, jpeg, ms, notified=None):
    ts = time.time()
    day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    rel = None
    if jpeg:
        os.makedirs(os.path.join(CAPTURE_DIR, day), exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in camera)
        rel = f"{day}/{datetime.fromtimestamp(ts).strftime('%H%M%S')}_{int(ts * 1000) % 1000:03d}_{safe}.jpg"
        with open(os.path.join(CAPTURE_DIR, rel), "wb") as f:
            f.write(jpeg)
    with _lock, _db() as con:
        cur = con.execute(
            "INSERT INTO events (ts, camera, alarm, types, detections, image, ms, notified) VALUES (?,?,?,?,?,?,?,?)",
            (ts, camera, 1 if alarm else 0, json.dumps(types), json.dumps(dets), rel, ms,
             json.dumps(notified or [])))
        return cur.lastrowid, rel


def events_between(start, end, camera=None, limit=2000):
    q = "SELECT * FROM events WHERE ts >= ? AND ts <= ?"
    args = [start, end]
    if camera:
        q += " AND camera = ?"
        args.append(camera)
    q += " ORDER BY ts LIMIT ?"
    args.append(limit)
    with _lock, _db() as con:
        rows = con.execute(q, args).fetchall()
    return [_row(r) for r in rows]


def set_meta(event_id, meta):
    with _lock, _db() as con:
        con.execute("UPDATE events SET meta=? WHERE id=?", (json.dumps(meta, ensure_ascii=False), event_id))


def get_event(event_id):
    with _lock, _db() as con:
        r = con.execute("SELECT * FROM events WHERE id=?", (int(event_id),)).fetchone()
    return _row(r) if r else None


def _row(r):
    return {
        "id": r["id"], "ts": r["ts"], "camera": r["camera"], "alarm": bool(r["alarm"]),
        "types": json.loads(r["types"] or "[]"), "detections": json.loads(r["detections"] or "[]"),
        "image": r["image"], "ms": r["ms"], "notified": json.loads(r["notified"] or "[]"),
        "meta": json.loads(r["meta"] or "null") if "meta" in r.keys() else None,
    }


def set_notified(event_id, notified):
    with _lock, _db() as con:
        con.execute("UPDATE events SET notified=? WHERE id=?", (json.dumps(notified), event_id))


def list_events(limit=50, before=None, camera=None, only_alarms=False):
    q = "SELECT * FROM events WHERE 1=1"
    args = []
    if before:
        q += " AND id < ?"
        args.append(before)
    if camera:
        q += " AND camera = ?"
        args.append(camera)
    if only_alarms:
        q += " AND alarm = 1"
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _lock, _db() as con:
        rows = con.execute(q, args).fetchall()
    return [_row(r) for r in rows]


def stats():
    since = time.time() - 86400
    with _lock, _db() as con:
        r = con.execute("SELECT COUNT(*) n, SUM(alarm) a FROM events WHERE ts >= ?", (since,)).fetchone()
    return {"analyses_24h": r["n"] or 0, "alarms_24h": r["a"] or 0}


def cleanup(days):
    """Tar bort händelser och bilder äldre än days dagar. 0 = spara för alltid."""
    if not days or days <= 0:
        return 0
    cutoff = time.time() - days * 86400
    with _lock, _db() as con:
        n = con.execute("DELETE FROM events WHERE ts < ?", (cutoff,)).rowcount
    limit_day = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for d in os.listdir(CAPTURE_DIR):
        p = os.path.join(CAPTURE_DIR, d)
        if os.path.isdir(p) and len(d) == 10 and d < limit_day:
            shutil.rmtree(p, ignore_errors=True)
    return n


def usage():
    """Använt utrymme: bilder (MB, antal), databasen (MB) och antal händelser."""
    img_bytes = img_n = 0
    for root, _, files in os.walk(CAPTURE_DIR):
        for f in files:
            try:
                img_bytes += os.path.getsize(os.path.join(root, f))
                img_n += 1
            except OSError:
                pass
    db_bytes = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            db_bytes += os.path.getsize(DB_PATH + suffix)
        except OSError:
            pass
    with _lock, _db() as con:
        r = con.execute("SELECT COUNT(*) n, MIN(ts) first FROM events").fetchone()
    mb = lambda b: round(b / 1048576, 1)
    return {"images_mb": mb(img_bytes), "images": img_n, "db_mb": mb(db_bytes), "total_mb": mb(img_bytes + db_bytes),
            "events": r["n"] or 0, "oldest": r["first"]}


def enforce_size(max_mb):
    """Tar bort de äldsta händelserna (med bilder) tills bilderna ryms inom max_mb. 0 = ingen gräns."""
    if not max_mb or max_mb <= 0:
        return 0
    limit = max_mb * 1048576
    files = []
    total = 0
    for root, _, names in os.walk(CAPTURE_DIR):
        for f in names:
            p = os.path.join(root, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            files.append((st.st_mtime, p, st.st_size))
            total += st.st_size
    if total <= limit:
        return 0
    files.sort()
    removed = []
    for _, p, size in files:
        if total <= limit * 0.9:          # lite marginal så att det inte rensas vid varje ny bild
            break
        try:
            os.remove(p)
        except OSError:
            continue
        total -= size
        removed.append(os.path.relpath(p, CAPTURE_DIR).replace(os.sep, "/"))
    n = 0
    with _lock, _db() as con:
        for i in range(0, len(removed), 500):
            part = removed[i:i + 500]
            n += con.execute(f"DELETE FROM events WHERE image IN ({','.join('?' * len(part))})", part).rowcount
    for d in os.listdir(CAPTURE_DIR):       # tomma dagmappar
        p = os.path.join(CAPTURE_DIR, d)
        if os.path.isdir(p) and not os.listdir(p):
            os.rmdir(p)
    return n


def clear_all():
    """Tar bort alla händelser och bilder."""
    with _lock, _db() as con:
        n = con.execute("DELETE FROM events").rowcount
    for d in os.listdir(CAPTURE_DIR):
        p = os.path.join(CAPTURE_DIR, d)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                os.remove(p)
            except OSError:
                pass
    with _lock:
        con = _db()
        try:
            con.execute("VACUUM")
        finally:
            con.close()
    return n
