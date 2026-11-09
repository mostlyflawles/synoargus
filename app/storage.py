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
    return [{
        "id": r["id"], "ts": r["ts"], "camera": r["camera"], "alarm": bool(r["alarm"]),
        "types": json.loads(r["types"] or "[]"), "detections": json.loads(r["detections"] or "[]"),
        "image": r["image"], "ms": r["ms"], "notified": json.loads(r["notified"] or "[]"),
    } for r in rows]


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
