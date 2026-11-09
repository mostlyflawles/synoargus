"""SynoArgus – AI-larm för Synology Surveillance Station."""
import asyncio
import base64
import io
import logging
import os
import re
import time
from copy import deepcopy
from datetime import datetime

import httpx
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import auth, notifiers, storage
from .config import (CAPTURE_DIR, COMMON_TYPES, DEFAULT_MODEL, GITHUB_REPO, MODEL_DIR, TYPE_NAMES_SV,
                     USER_MODEL_DIR, camera_defaults, config)
from .detector import COCO as COCO_TYPES
from .detector import Detector
from .engine import Engine
from .filters import draw
from .i18n import tr
from .synology import SurveillanceStation, SynologyError, dsm_login_check, find_md_params
from .version import APP_BUILD, APP_BUILD_DATE, APP_NAME, APP_VERSION

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("synoargus")

HERE = os.path.dirname(__file__)
MASK = "********"

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)
ss = SurveillanceStation(config)
detector = Detector(MODEL_DIR, USER_MODEL_DIR)
engine = Engine(config, ss, detector)
_fails = {}  # ip -> [tidpunkter för misslyckade inloggningar]
_update = {"checked": 0, "data": None}


def err(code, text, **kw):
    return HTTPException(code, tr(text, **kw))


def unlocked():
    return os.environ.get("SYNOARGUS_UNLOCK", "").strip().lower() in ("1", "true", "ja", "yes")


# ------------------------------------------------------------------ tidszon

def apply_timezone(tz):
    from zoneinfo import ZoneInfo
    ZoneInfo(tz)  # kastar fel om okänd
    os.environ["TZ"] = tz
    try:
        time.tzset()
    except AttributeError:
        pass


# ------------------------------------------------------------------ hjälpare

def client_ip(request):
    return request.client.host if request.client else ""


def current_user(request):
    p = auth.verify(config.get("secret"), request.cookies.get(auth.SESSION_COOKIE, ""))
    return p["u"] if p else None


def require(request):
    if not config.get("setup_done"):
        raise err(409, "Installationen är inte klar")
    user = current_user(request)
    if not user or not auth.user_allowed(config, user):
        raise err(401, "Inte inloggad")
    return user


def set_session(resp, request, user, method):
    resp.set_cookie(auth.SESSION_COOKIE, auth.make_session(config.get("secret"), user, method),
                    max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="lax",
                    secure=request.url.scheme == "https")


def too_many(ip):
    now = time.time()
    lst = [t for t in _fails.get(ip, []) if now - t < 300]
    _fails[ip] = lst
    return len(lst) >= 5


SECRET_PATHS = [("synology", "password"), ("auth", "sso", "client_secret")]


def masked(d):
    d = deepcopy(d)
    for path in SECRET_PATHS:
        cur = d
        for p in path[:-1]:
            cur = cur.get(p, {})
        if cur.get(path[-1]):
            cur[path[-1]] = MASK
    for n in d.get("notifiers", []):
        for k in notifiers.SECRET_FIELDS:
            if n.get(k):
                n[k] = MASK
    d.pop("secret", None)
    return d


def masked_config():
    return masked(config.get())


def unmask(new, old):
    """Ersätter MASK med befintligt värde."""
    if not isinstance(new, dict):
        return new
    old = old if isinstance(old, dict) else {}
    out = {}
    for k, v in new.items():
        if v == MASK:
            out[k] = old.get(k, "")
        else:
            out[k] = unmask(v, old.get(k))
    return out


def unmask_notifiers(new_list, old_list):
    old = {n.get("id"): n for n in old_list or []}
    return [unmask(n, old.get(n.get("id"), {})) for n in new_list or []]


def cam_or_404(name):
    cam = (config.get("cameras") or {}).get(name)
    if not cam:
        raise err(404, "Okänd kamera")
    return cam


# ------------------------------------------------------------------ uppdateringskoll

def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s or "")[:4]) or (0,)


async def check_update(force=False):
    if not force and _update["data"] and time.time() - _update["checked"] < 3600:
        return _update["data"]
    data = {"current": APP_VERSION, "latest": None, "newer": False, "url": None, "notes": None,
            "repo": GITHUB_REPO, "error": None}
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SynoArgus"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", headers=headers)
            if r.status_code == 200:
                j = r.json()
                data.update(latest=j.get("tag_name"), url=j.get("html_url"), notes=(j.get("body") or "")[:3000])
            else:
                r = await c.get(f"https://api.github.com/repos/{GITHUB_REPO}/tags", headers=headers)
                r.raise_for_status()
                tags = [t["name"] for t in r.json() if re.match(r"v?\d", t.get("name", ""))]
                if tags:
                    latest = max(tags, key=_ver)
                    data.update(latest=latest, url=f"https://github.com/{GITHUB_REPO}/releases")
        if data["latest"]:
            data["newer"] = _ver(data["latest"]) > _ver(APP_VERSION)
    except Exception as e:
        data["error"] = str(e) or type(e).__name__
    _update.update(checked=time.time(), data=data)
    return data


# ------------------------------------------------------------------ start

@app.on_event("startup")
async def startup():
    storage.init()
    log.info("%s %s (bygge %s) startar", APP_NAME, APP_VERSION, APP_BUILD)
    try:
        apply_timezone(config.get("timezone") or "UTC")
    except Exception as e:
        log.warning("Ogiltig tidszon %s: %s", config.get("timezone"), e)
    if unlocked():
        def unlock(d):
            d["auth"]["allowed_users"] = []
            d["auth"]["dsm_login"] = True
        config.update(unlock)
        log.warning("SYNOARGUS_UNLOCK är satt: alla DSM-konton kan logga in. Ta bort raden när du är klar.")

    async def load():
        try:
            await asyncio.to_thread(engine.ensure_model)
        except Exception as e:
            log.error("Modellen kunde inte laddas: %s", e)

    async def housekeeping():
        while True:
            try:
                n = await asyncio.to_thread(storage.cleanup, config.get("storage", "days_to_keep"))
                if n:
                    log.info("Rensade %d gamla händelser", n)
            except Exception as e:
                log.warning("Rensning misslyckades: %s", e)
            await asyncio.sleep(3600)

    async def update_loop():
        await asyncio.sleep(60)
        while True:
            await check_update(force=True)
            await asyncio.sleep(86400)

    asyncio.create_task(load())
    asyncio.create_task(housekeeping())
    asyncio.create_task(update_loop())


@app.middleware("http")
async def headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Robots-Tag"] = "noindex"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ------------------------------------------------------------------ anrop från Surveillance Station / Homey

def check_token(token):
    if not config.get("setup_done"):
        raise err(409, "Installationen är inte klar")
    if token != config.get("trigger_token"):
        raise err(403, "Fel token")


@app.api_route("/api/trigger/{camera}", methods=["GET", "POST"])
async def trigger(camera: str, token: str = ""):
    check_token(token)
    result = await engine.trigger(camera)
    return {"camera": camera, "result": result}


@app.api_route("/api/control", methods=["GET", "POST"])
async def control(token: str = "", camera: str = "all", action: str = "status"):
    """Slå på/av analys per kamera: ?camera=all|<namn>&action=on|off|toggle|status"""
    check_token(token)
    action = action.lower()
    if action not in ("on", "off", "toggle", "status"):
        raise err(400, "Okänd åtgärd (on, off, toggle eller status)")
    cams = config.get("cameras") or {}
    targets = list(cams) if camera.lower() == "all" else [camera]
    for t in targets:
        if t not in cams:
            raise err(404, "Okänd kamera")
    if action != "status":
        def apply(d):
            for t in targets:
                c = d["cameras"][t]
                c["enabled"] = (action == "on") or (action == "toggle" and not c.get("enabled", True))
        config.update(apply)
    cams = config.get("cameras") or {}
    return {"cameras": {n: bool(c.get("enabled", True)) for n, c in cams.items() if n in targets}}


# ------------------------------------------------------------------ installation och inloggning

@app.get("/api/state")
async def state(request: Request):
    user = current_user(request)
    ok = bool(user) and auth.user_allowed(config, user) and config.get("setup_done")
    a = config.get("auth")
    return {
        "app": APP_NAME, "version": APP_VERSION, "build": APP_BUILD, "build_date": APP_BUILD_DATE,
        "language": config.get("language") or "sv",
        "setup_done": config.get("setup_done"),
        "setup_allowed": not config.get("setup_done") and auth.is_private(client_ip(request)),
        "logged_in": bool(ok), "user": user if ok else None,
        "dsm_login": a.get("dsm_login", True), "unlocked": unlocked(),
        "sso": bool(a["sso"].get("enabled") and a["sso"].get("issuer") and a["sso"].get("client_id")),
    }


@app.post("/api/language")
async def set_language(request: Request, body: dict = Body(...)):
    """Språk kan väljas redan i installationsguiden (före inloggning) och under Inställningar."""
    lg = body.get("language")
    if lg not in ("sv", "en"):
        raise HTTPException(400, "sv | en")
    if config.get("setup_done"):
        require(request)
    config.update(lambda d: d.__setitem__("language", lg))
    return {"ok": True}


@app.post("/api/setup")
async def setup(request: Request, body: dict = Body(...)):
    if config.get("setup_done"):
        raise err(409, "Redan installerad")
    if not auth.is_private(client_ip(request)):
        raise err(403, "Installationen kan bara göras från hemnätet")
    syn = body.get("synology") or {}
    url = (syn.get("url") or "").strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise err(400, "Adressen måste börja med http:// eller https://")
    s = {"url": url, "user": (syn.get("user") or "").strip(), "password": syn.get("password") or "",
         "verify_tls": bool(syn.get("verify_tls")), "quality": syn.get("quality") or "balanced"}
    config.update(lambda d: d["synology"].update(s))
    ss.reset()
    try:
        cams = await ss.list_cameras()
    except SynologyError as e:
        raise err(400, "Kunde inte ansluta till Surveillance Station: {e}", e=e)
    except Exception as e:
        raise err(400, "Kunde inte nå NAS:en: {e}", e=e)
    login_user = (body.get("login_user") or "").strip()
    if login_user:
        try:
            await dsm_login_check(url, s["verify_tls"], login_user, body.get("login_password") or "",
                                  body.get("login_otp") or None)
        except SynologyError as e:
            raise err(400, "Ditt DSM-konto: {e}", e=e)
    else:
        login_user = s["user"]
    tz = (body.get("timezone") or "").strip()

    def finish(d):
        d["setup_done"] = True
        d["auth"]["allowed_users"] = [login_user]
        d["public_url"] = d.get("public_url") or str(request.base_url).rstrip("/")
        if tz:
            d["timezone"] = tz
        for c in cams:
            if c["name"] not in d["cameras"]:
                d["cameras"][c["name"]] = camera_defaults(c["name"], c["id"])
    if tz:
        try:
            apply_timezone(tz)
        except Exception:
            tz = ""
    config.update(finish)
    resp = JSONResponse({"ok": True, "cameras": len(cams), "user": login_user})
    set_session(resp, request, login_user, "dsm")
    return resp


@app.post("/api/login")
async def login(request: Request, body: dict = Body(...)):
    ip = client_ip(request)
    if too_many(ip):
        raise err(429, "För många försök, vänta 5 minuter")
    if not config.get("auth", "dsm_login"):
        raise err(400, "Inloggning med DSM-konto är avstängd, använd SSO")
    user = (body.get("user") or "").strip()
    if not auth.user_allowed(config, user):
        _fails.setdefault(ip, []).append(time.time())
        raise err(403, "Kontot har inte behörighet till SynoArgus")
    syn = config.get("synology")
    try:
        await dsm_login_check(syn["url"], bool(syn.get("verify_tls")), user, body.get("password") or "",
                              body.get("otp") or None)
    except SynologyError as e:
        if e.code not in (0, 403):
            _fails.setdefault(ip, []).append(time.time())
        raise HTTPException(428 if e.code == 403 else (502 if e.code == 0 else 401), str(e))
    resp = JSONResponse({"ok": True, "user": user})
    set_session(resp, request, user, "dsm")
    return resp


@app.get("/auth/sso")
async def sso_login():
    try:
        url, cookie = await auth.sso_start(config)
    except Exception as e:
        return RedirectResponse(f"/?fel={type(e).__name__}", status_code=302)
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(auth.STATE_COOKIE, cookie, max_age=600, httponly=True, samesite="lax")
    return resp


@app.get("/auth/sso/callback")
async def sso_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse("/?fel=sso", status_code=302)
    try:
        user = await auth.sso_finish(config, code, state, request.cookies.get(auth.STATE_COOKIE))
    except Exception as e:
        log.warning("SSO misslyckades: %s", e)
        return RedirectResponse("/?fel=sso", status_code=302)
    if not auth.user_allowed(config, user):
        return RedirectResponse("/?fel=behorighet", status_code=302)
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(auth.STATE_COOKIE)
    set_session(resp, request, user, "sso")
    return resp


@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


# ------------------------------------------------------------------ inställningar

@app.get("/api/config")
async def get_config(request: Request):
    require(request)
    return {
        "config": masked_config(),
        "types": {"common": COMMON_TYPES, "all": COCO_TYPES, "names": TYPE_NAMES_SV},
        "models": detector.status()["available"],
        "trigger_base": str(request.base_url).rstrip("/"),
    }


def validate_auth(request, a):
    if isinstance(a.get("allowed_users"), str):
        a["allowed_users"] = [u.strip() for u in a["allowed_users"].replace("\n", ",").split(",") if u.strip()]
    me = current_user(request)
    if a.get("allowed_users") and me.lower() not in [u.lower() for u in a["allowed_users"]]:
        raise err(400, "Du ({me}) måste finnas med bland tillåtna konton", me=me)
    if not a.get("dsm_login") and not (a.get("sso") or {}).get("enabled"):
        raise err(400, "Minst ett inloggningssätt måste vara på")


@app.put("/api/settings")
async def put_settings(request: Request, body: dict = Body(...)):
    require(request)
    old = config.get()
    allowed = ("synology", "auth", "detector", "defaults", "storage", "public_url", "language", "timezone")
    new = unmask({k: v for k, v in body.items() if k in allowed}, old)
    if "auth" in new:
        validate_auth(request, new["auth"])
    if "timezone" in new:
        try:
            apply_timezone(new["timezone"])
        except Exception:
            raise err(400, "Ogiltig tidszon: {tz}", tz=new["timezone"])
    if new.get("language") not in (None, "sv", "en"):
        new.pop("language")

    def apply(d):
        for k, v in new.items():
            if isinstance(v, dict) and isinstance(d.get(k), dict):
                d[k] = {**d[k], **v}
            else:
                d[k] = v
    config.update(apply)
    if "synology" in new:
        ss.reset()
    if "detector" in new:
        try:
            await asyncio.to_thread(engine.ensure_model)
        except Exception as e:
            raise err(400, "Sparat, men modellen kunde inte laddas: {e}", e=e)
    return {"ok": True}


@app.get("/api/export")
async def export_settings(request: Request, secrets: int = 1):
    require(request)
    d = config.get()
    d.pop("secret", None)
    if not secrets:
        d = masked(d)
    d["_synoargus"] = {"version": APP_VERSION, "exported": datetime.now().astimezone().isoformat(timespec="seconds"),
                       "secrets": bool(secrets)}
    name = f"synoargus-settings-{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    return JSONResponse(d, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/import")
async def import_settings(request: Request, body: dict = Body(...)):
    require(request)
    if "_synoargus" not in body or not isinstance(body.get("cameras"), dict):
        raise err(400, "Filen är inte en SynoArgus-export")
    old = config.get()
    body = {k: v for k, v in body.items() if k not in ("_synoargus", "secret", "setup_done")}
    notis = unmask_notifiers(body.pop("notifiers", []), old.get("notifiers"))
    new = unmask(body, old)
    new["notifiers"] = notis
    a = new.get("auth") or {}
    me = current_user(request)
    if a.get("allowed_users") and me.lower() not in [u.lower() for u in a["allowed_users"]]:
        a["allowed_users"].append(me)  # lås inte ute den som importerar
    if not a.get("dsm_login") and not (a.get("sso") or {}).get("enabled"):
        a["dsm_login"] = True

    def apply(d):
        for k, v in new.items():
            if isinstance(v, dict) and isinstance(d.get(k), dict) and k != "cameras":
                d[k] = {**d[k], **v}
            else:
                d[k] = v
    config.update(apply)
    ss.reset()
    try:
        apply_timezone(config.get("timezone") or "UTC")
    except Exception:
        pass
    asyncio.create_task(asyncio.to_thread(engine.ensure_model))
    return {"ok": True, "cameras": len(new.get("cameras") or {}), "notifiers": len(notis)}


@app.get("/api/ss/cameras")
async def ss_cameras(request: Request):
    require(request)
    try:
        return {"cameras": await ss.list_cameras()}
    except Exception as e:
        raise HTTPException(502, str(e))


@app.put("/api/cameras/{name}")
async def put_camera(name: str, request: Request, body: dict = Body(...)):
    require(request)

    def apply(d):
        cam = d["cameras"].get(name) or camera_defaults(name, body.get("ss_id"))
        for k in ("enabled", "types", "threshold", "min_width", "min_height", "cooldown_s", "delay_s",
                  "max_snapshots", "wait_ms", "zones", "ss_id"):
            if k in body:
                cam[k] = body[k]
        cam["name"] = name
        d["cameras"][name] = cam
    config.update(apply)
    return {"ok": True}


@app.delete("/api/cameras/{name}")
async def delete_camera(name: str, request: Request):
    require(request)
    config.update(lambda d: d["cameras"].pop(name, None))
    return {"ok": True}


def _jpeg(img, q=85):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    return buf.getvalue()


@app.get("/api/cameras/{name}/snapshot")
async def camera_snapshot(name: str, request: Request):
    require(request)
    cam = (config.get("cameras") or {}).get(name) or camera_defaults(name)
    try:
        img = await engine.grab(cam)
    except Exception as e:
        raise HTTPException(502, str(e))
    return Response(_jpeg(img), media_type="image/jpeg")


@app.get("/api/cameras/{name}/live")
async def camera_live(name: str, request: Request, ai: int = 0):
    """En bild till livebilden, med AI-rutor om ai=1. Webbläsaren hämtar bild efter bild."""
    require(request)
    cam = (config.get("cameras") or {}).get(name) or camera_defaults(name)
    try:
        img = await engine.grab(cam)
        if ai:
            await asyncio.to_thread(engine.ensure_model)
            dets, _ = await asyncio.to_thread(engine.analyse, cam, img)
            jpeg = await asyncio.to_thread(draw, img, dets, cam.get("zones"), True)
        else:
            jpeg = await asyncio.to_thread(_jpeg, img, 80)
    except Exception as e:
        raise HTTPException(502, str(e))
    return Response(jpeg, media_type="image/jpeg", headers={"X-AI-ms": str(detector.last_ms or "")})


@app.post("/api/cameras/{name}/test")
async def camera_test(name: str, request: Request, body: dict = Body(default={})):
    """Tar en bild och kör AI:n utan att larma. Visar alla träffar och varför de godtas eller inte."""
    require(request)
    cam = deepcopy((config.get("cameras") or {}).get(name) or camera_defaults(name))
    cam.update({k: v for k, v in (body or {}).items() if k in cam})
    try:
        await asyncio.to_thread(engine.ensure_model)
        img = await engine.grab(cam)
        t = time.time()
        dets, valid = await asyncio.to_thread(engine.analyse, cam, img)
        ms = round((time.time() - t) * 1000)
        jpeg = await asyncio.to_thread(draw, img, dets, cam.get("zones"), True)
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"ms": ms, "width": img.size[0], "height": img.size[1], "detections": dets,
            "alarm": bool(valid), "image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}


# ------------------------------------------------------------------ rörelsedetektering i Surveillance Station

async def _ss_id(cam):
    if cam.get("ss_id") is None:
        cam["ss_id"] = await ss.resolve_id(cam["name"])
    return cam["ss_id"]


@app.get("/api/cameras/{name}/motion")
async def motion_get(name: str, request: Request):
    require(request)
    cam = cam_or_404(name)
    try:
        raw = await ss.motion_get(await _ss_id(cam))
    except Exception as e:
        raise HTTPException(502, str(e))
    p = find_md_params(raw)
    if p is None:
        return {"supported": False, "raw": raw}
    return {"supported": True, "sensitivity": p.get("sensitivity"), "threshold": p.get("threshold"),
            "source": p.get("source"), "raw": p}


@app.put("/api/cameras/{name}/motion")
async def motion_put(name: str, request: Request, body: dict = Body(...)):
    require(request)
    cam = cam_or_404(name)
    try:
        cam_id = await _ss_id(cam)
        current = find_md_params(await ss.motion_get(cam_id)) or {}
        params = {k: current[k] for k in ("source", "keep", "history", "objectSize", "percentage", "mode")
                  if k in current and not isinstance(current[k], (dict, list))}
        params["sensitivity"] = max(1, min(99, int(body["sensitivity"])))
        params["threshold"] = max(1, min(99, int(body["threshold"])))
        await ss.motion_save(cam_id, params)
        after = find_md_params(await ss.motion_get(cam_id)) or {}
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"ok": True, "sensitivity": after.get("sensitivity"), "threshold": after.get("threshold")}


@app.get("/api/cameras/{name}/triggers")
async def camera_triggers(name: str, request: Request, since: float = 0):
    require(request)
    return {"now": time.time(), "triggers": engine.triggers(name, since)}


# ------------------------------------------------------------------ notifierare

@app.put("/api/notifiers")
async def put_notifiers(request: Request, body: list = Body(...)):
    require(request)
    old = {n["id"]: n for n in config.get("notifiers") or []}
    out = []
    for n in body:
        if n.get("type") not in notifiers.KINDS:
            raise err(400, "Okänd typ av notifierare")
        base = notifiers.new_notifier(n["type"])
        if n.get("id") in old:
            base = old[n["id"]]
        merged = {**base, **unmask(n, old.get(n.get("id"), {}))}
        out.append(merged)
    config.update(lambda d: d.__setitem__("notifiers", out))
    return {"ok": True, "notifiers": masked_config()["notifiers"]}


@app.post("/api/notifiers/{nid}/test")
async def test_notifier(nid: str, request: Request):
    require(request)
    n = next((n for n in config.get("notifiers") or [] if n["id"] == nid), None)
    if not n:
        raise err(404, "Spara notifieraren först")
    img = Image.new("RGB", (640, 360), (40, 44, 52))
    dets = [{"label": "person", "confidence": 99.0, "x1": 260, "y1": 80, "x2": 380, "y2": 320, "valid": True}]
    jpeg = draw(img, dets)
    res = await engine.notify(tr("Testkamera"), ["person"], dets, jpeg, only=nid)
    r = res[0] if res else {"ok": False, "error": tr("Inget skickades")}
    if not r["ok"]:
        raise HTTPException(502, r["error"])
    return {"ok": True}


# ------------------------------------------------------------------ historik och status

@app.get("/api/events")
async def events(request: Request, before: int = 0, camera: str = "", alarms: int = 1, limit: int = 40):
    require(request)
    return {"events": storage.list_events(min(limit, 200), before or None, camera or None, bool(alarms))}


@app.delete("/api/events")
async def delete_events(request: Request):
    require(request)
    n = await asyncio.to_thread(storage.clear_all)
    return {"ok": True, "deleted": n}


@app.get("/captures/{path:path}")
async def capture(path: str, request: Request):
    require(request)
    full = os.path.realpath(os.path.join(CAPTURE_DIR, path))
    if not full.startswith(os.path.realpath(CAPTURE_DIR) + os.sep) or not os.path.isfile(full):
        raise err(404, "Bilden finns inte")
    return FileResponse(full, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/status")
async def status(request: Request):
    require(request)
    cams = {}
    for name in (config.get("cameras") or {}):
        st = engine.state.get(name)
        cams[name] = {"busy": st.busy, "last": st.last_result, "last_alarm": st.last_alarm or None} if st else {}
    return {"detector": detector.status(), "cameras": cams, "recent": engine.recent[:20],
            "update": _update["data"], **storage.stats()}


@app.get("/api/update")
async def update(request: Request, force: int = 0):
    require(request)
    return await check_update(force=bool(force))


# ------------------------------------------------------------------ webbgränssnitt

app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"), headers={"Cache-Control": "no-cache"})
