"""Kontroll av värden innan de sparas (från webbgränssnittet eller en importerad fil).

Ogiltiga värden ger ValueError med fältets namn. Okända fält tas bort.
"""
import re

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class Invalid(ValueError):
    """Ogiltigt värde; args[0] är fältets namn."""


def _int(v, field, lo, hi, none_ok=False):
    if v is None or v == "":
        if none_ok:
            return None
        raise Invalid(field)
    if isinstance(v, bool):
        raise Invalid(field)
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise Invalid(field)
    if f != f or f in (float("inf"), float("-inf")):
        raise Invalid(field)
    return max(lo, min(hi, int(round(f))))


def _float(v, field, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise Invalid(field)
    if f != f:
        raise Invalid(field)
    return max(lo, min(hi, f))


def _str(v, field, maxlen=500):
    if v is None:
        return ""
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        raise Invalid(field)
    return str(v)[:maxlen]


def _strlist(v, field, allowed=None, maxlen=200):
    if v is None:
        return []
    if not isinstance(v, list):
        raise Invalid(field)
    out = []
    for x in v:
        if not isinstance(x, str):
            raise Invalid(field)
        if (allowed is None or x in allowed) and x not in out:
            out.append(x[:maxlen])
    return out


def box(z, field):
    if not isinstance(z, dict):
        raise Invalid(field)
    x1, y1, x2, y2 = (_float(z.get(k), field, 0.0, 1.0) for k in ("x1", "y1", "x2", "y2"))
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    return {"x1": round(x1, 4), "y1": round(y1, 4), "x2": round(x2, 4), "y2": round(y2, 4)}


CAMERA_LIMITS = {
    "threshold": (10, 95), "min_width": (0, 8000), "min_height": (0, 8000), "cooldown_s": (0, 86400),
    "delay_s": (0, 3600), "max_snapshots": (1, 5),
}


def camera(body, labels):
    """Rensar kamerafälten i body. Returnerar bara de fält som fanns med."""
    if not isinstance(body, dict):
        raise Invalid("camera")
    out = {}
    if "enabled" in body:
        out["enabled"] = bool(body["enabled"])
    if "types" in body:
        out["types"] = _strlist(body["types"], "types", labels)
    for k, (lo, hi) in CAMERA_LIMITS.items():
        if k in body:
            out[k] = _int(body[k], k, lo, hi, none_ok=True)
    if "wait_ms" in body:
        out["wait_ms"] = _int(body["wait_ms"] or 0, "wait_ms", 0, 10000)
    if "ss_id" in body:
        out["ss_id"] = _int(body["ss_id"], "ss_id", 0, 10 ** 9, none_ok=True)
    if "modes" in body:
        out["modes"] = _strlist(body["modes"], "modes")
    if "stream_url" in body:
        u = _str(body["stream_url"], "stream_url", 1000).strip()
        if u and u != "********" and not u.startswith(("rtsp://", "rtsps://", "http://", "https://")):
            raise Invalid("stream_url")
        out["stream_url"] = u
    if "zones" in body:
        zones = body["zones"] or []
        if not isinstance(zones, list) or len(zones) > 50:
            raise Invalid("zones")
        out["zones"] = [{**box(z, "zones"), "mode": "intersect" if z.get("mode") == "intersect" else "contains"}
                        for z in zones]
    if isinstance(body.get("action_rule"), dict):
        ar = body["action_rule"]
        out["action_rule"] = {"name": _str(ar.get("name"), "action_rule", 200),
                              "created": _float(ar.get("created") or 0, "action_rule", 0, 1e11),
                              "confirmed": bool(ar.get("confirmed"))}
    return out


DEFAULT_LIMITS = {**CAMERA_LIMITS, "snapshot_interval_ms": (200, 5000)}


def settings(new, model_names=None):
    """Rensar de delar av inställningarna som finns i new (på plats). Okända underfält tas bort."""
    if "defaults" in new:
        d = new["defaults"]
        if not isinstance(d, dict):
            raise Invalid("defaults")
        new["defaults"] = {k: _int(d[k], k, lo, hi) for k, (lo, hi) in DEFAULT_LIMITS.items() if k in d}
    if "storage" in new:
        s = new["storage"]
        if not isinstance(s, dict):
            raise Invalid("storage")
        out = {}
        if "days_to_keep" in s:
            out["days_to_keep"] = _int(s["days_to_keep"], "days_to_keep", 0, 3650)
        if "max_mb" in s:
            out["max_mb"] = _int(s["max_mb"], "max_mb", 0, 10 ** 7)
        if "save_empty" in s:
            out["save_empty"] = bool(s["save_empty"])
        new["storage"] = out
    if "synology" in new:
        s = new["synology"]
        if not isinstance(s, dict):
            raise Invalid("synology")
        out = {}
        if "url" in s:
            url = _str(s["url"], "url").strip().rstrip("/")
            if url and not url.startswith(("http://", "https://")):
                raise Invalid("url")
            out["url"] = url
        for k in ("user", "password"):
            if k in s:
                out[k] = _str(s[k], k)
        if "verify_tls" in s:
            out["verify_tls"] = bool(s["verify_tls"])
        if "quality" in s:
            out["quality"] = s["quality"] if s["quality"] in ("high", "balanced", "low") else "balanced"
        new["synology"] = out
    if "detector" in new:
        d = new["detector"]
        if not isinstance(d, dict):
            raise Invalid("detector")
        out = {}
        if "model" in d:
            m = _str(d["model"], "model", 100)
            if not re.match(r"^[A-Za-z0-9._-]+$", m) or (model_names is not None and m not in model_names):
                raise Invalid("model")
            out["model"] = m
        if "device" in d:
            out["device"] = d["device"] if d["device"] in ("AUTO", "CPU", "GPU") else "AUTO"
        new["detector"] = out
    if "public_url" in new:
        u = _str(new["public_url"], "public_url").strip().rstrip("/")
        if u and not u.startswith(("http://", "https://")):
            raise Invalid("public_url")
        new["public_url"] = u
    if "timezone" in new:
        new["timezone"] = _str(new["timezone"], "timezone", 64)
    if "auth" in new:
        a = new["auth"]
        if not isinstance(a, dict):
            raise Invalid("auth")
        out = {}
        if "dsm_login" in a:
            out["dsm_login"] = bool(a["dsm_login"])
        if "allowed_users" in a:
            au = a["allowed_users"]
            if isinstance(au, str):
                au = [u.strip() for u in au.replace("\n", ",").split(",") if u.strip()]
            out["allowed_users"] = [u.strip() for u in _strlist(au, "allowed_users") if u.strip()]
        if "sso" in a:
            sso = a["sso"]
            if not isinstance(sso, dict):
                raise Invalid("sso")
            o = {}
            if "enabled" in sso:
                o["enabled"] = bool(sso["enabled"])
            for k in ("issuer", "client_id", "client_secret", "redirect_url"):
                if k in sso:
                    o[k] = _str(sso[k], k, 1000)
            out["sso"] = o
        new["auth"] = out
    if "mode_auto" in new:
        ma = new["mode_auto"]
        if not isinstance(ma, dict):
            raise Invalid("mode_auto")
        out = {}
        if "homemode" in ma:
            hm = ma["homemode"] if isinstance(ma["homemode"], dict) else {}
            out["homemode"] = {"enabled": bool(hm.get("enabled")), "on": _str(hm.get("on"), "homemode", 100),
                               "off": _str(hm.get("off"), "homemode", 100)}
        if "schedule" in ma:
            sched = ma["schedule"] or []
            if not isinstance(sched, list) or len(sched) > 100:
                raise Invalid("schedule")
            rows = []
            for e in sched:
                if not isinstance(e, dict) or not TIME_RE.match(str(e.get("time") or "")):
                    raise Invalid("schedule")
                days = e.get("days")
                days = sorted({int(x) for x in days if isinstance(x, (int, float)) and 0 <= int(x) <= 6}) \
                    if isinstance(days, list) else list(range(7))
                rows.append({"time": e["time"], "days": days or list(range(7)), "mode": _str(e.get("mode"), "schedule", 100)})
            out["schedule"] = rows
        new["mode_auto"] = out
    if "modes" in new:
        if not isinstance(new["modes"], list):
            raise Invalid("modes")
        clean, seen = [], set()
        for m in new["modes"]:
            if not isinstance(m, dict):
                raise Invalid("modes")
            mid = _str(m.get("id"), "modes", 100).strip()
            if mid and mid not in seen and not mid.startswith("@"):
                seen.add(mid)
                clean.append({"id": mid, "name": _str(m.get("name"), "modes", 60).strip()})
        if not clean:
            raise Invalid("modes")
        new["modes"] = clean
    return new


def notifier_list(items, kinds):
    if not isinstance(items, list) or len(items) > 100:
        raise Invalid("notifiers")
    for n in items:
        if not isinstance(n, dict) or n.get("type") not in kinds:
            raise Invalid("notifiers")
        if "id" in n and not isinstance(n["id"], str):
            raise Invalid("notifiers")
        for k in ("cameras", "types", "modes"):
            if k in n:
                n[k] = _strlist(n[k], "notifiers")
        if "deliver" in n:
            n["deliver"] = "request" if n["deliver"] == "request" else "direct"
        if "fallback_min" in n:
            n["fallback_min"] = _int(n["fallback_min"] or 0, "fallback_min", 0, 1440)
        for k, v in n.items():
            if isinstance(v, (dict, list)) and k not in ("cameras", "types", "modes"):
                raise Invalid("notifiers")
    return items
