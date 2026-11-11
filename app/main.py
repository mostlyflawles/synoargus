"""SynoArgus – AI-larm för Synology Surveillance Station."""
import asyncio
import contextvars
import base64
import hmac
import io
import json
import logging
import os
import re
import time
from copy import deepcopy
from datetime import datetime

import httpx
from fastapi import Body, FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import auth, i18n, notifiers, storage, validate
from .config import (CAPTURE_DIR, COMMON_TYPES, DEFAULT_MODEL, GITHUB_REPO, MODEL_DIR, TYPE_NAMES_SV,
                     USER_MODEL_DIR, camera_defaults, config)
from .detector import COCO as COCO_TYPES
from .detector import Detector
from .engine import Engine
from .filters import draw
from .i18n import tr
from .modes import ModeManager, SPECIAL as SPECIAL_MODES
from .calibration import BusyError, CalibrationManager
from . import calibration as calibration_mod
from . import dispatch
from . import streams as streams_mod
from . import watch as watch_mod
from .synology import SurveillanceStation, SynologyError, dsm_login_check, find_md_params, find_rules
from .version import APP_BUILD, APP_BUILD_DATE, APP_NAME, APP_VERSION

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx loggar annars varje anrop med hela adressen (sessions-id, bot-nycklar, webhook-adresser)
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)
log = logging.getLogger("synoargus")

HERE = os.path.dirname(__file__)
MASK = "********"

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)
ss = SurveillanceStation(config)
detector = Detector(MODEL_DIR, USER_MODEL_DIR)
engine = Engine(config, ss, detector)
modes = ModeManager(config, ss, engine._note)
engine.modes = modes
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
    peer = request.client.host if request.client else ""
    return auth.real_ip(peer, request.headers.get("x-forwarded-for"))


def _via_proxy(request):
    """Anropet kommer från en omvänd proxy på hemnätet (t.ex. DSM) som har satt X-Forwarded-rubriker."""
    peer = request.client.host if request.client else ""
    return bool(request.headers.get("x-forwarded-for")) and auth.is_private(peer)


def is_https(request):
    if _via_proxy(request):
        proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
        if proto in ("http", "https"):
            return proto == "https"
    return request.url.scheme == "https"


def base_url(request):
    """Adressen som webbläsaren använde (https bakom en omvänd proxy)."""
    host = request.headers.get("host") or request.url.netloc
    if _via_proxy(request):
        host = (request.headers.get("x-forwarded-host") or host).split(",")[0].strip()
    if not re.match(r"^[A-Za-z0-9.\-:\[\]]+$", host or ""):
        host = request.url.netloc
    return f"{'https' if is_https(request) else 'http'}://{host}"


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
                    secure=is_https(request))


def too_many(*keys):
    """Spärr mot gissningar: 5 fel per adress eller 10 per konto på 5 minuter."""
    now = time.time()
    for k in [k for k, v in _fails.items() if not v or now - v[-1] > 300]:
        del _fails[k]
    for k in keys:
        lst = [t for t in _fails.get(k, []) if now - t < 300]
        if lst:
            _fails[k] = lst
        if len(lst) >= (10 if k.startswith("user:") else 5):
            return True
    return False


def failed(*keys):
    for k in keys:
        _fails.setdefault(k, []).append(time.time())
    if len(_fails) > 5000:      # håll minnet begränsat vid en attack
        for k in sorted(_fails, key=lambda k: _fails[k][-1])[:2500]:
            del _fails[k]


def invalid(e):
    return err(400, "Ogiltigt värde: {field}", field=e.args[0] if e.args else "?")


SECRET_PATHS = [("synology", "password"), ("auth", "sso", "client_secret")]


EXPORT_SECRET_FIELDS = ("url", "topic")     # webhook-adresser och ntfy-ämnen kan innehålla nycklar


def masked(d, export=False):
    d = deepcopy(d)
    for path in SECRET_PATHS:
        cur = d
        for p in path[:-1]:
            cur = cur.get(p, {})
        if cur.get(path[-1]):
            cur[path[-1]] = MASK
    if export:
        for c in (d.get("cameras") or {}).values():
            if c.get("stream_url"):
                c["stream_url"] = MASK      # kan innehålla kamerans lösenord
    for n in d.get("notifiers", []):
        for k in notifiers.SECRET_FIELDS + (EXPORT_SECRET_FIELDS if export else ()):
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


def safe_error(e):
    """Felmeddelande utan adresser (de kan innehålla nycklar)."""
    text = str(e) or type(e).__name__
    return re.sub(r"https?://\S+", "<url>", text)[:500]


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
    calibration_mod.init_db()
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
                n += await asyncio.to_thread(storage.enforce_size, config.get("storage", "max_mb"))
                if n:
                    log.info("Rensade %d gamla händelser", n)
            except Exception as e:
                log.warning("Rensning misslyckades: %s", e)
            await asyncio.sleep(600)

    async def update_loop():
        await asyncio.sleep(60)
        while True:
            await check_update(force=True)
            await asyncio.sleep(86400)

    asyncio.create_task(load())
    asyncio.create_task(housekeeping())
    asyncio.create_task(modes.loop())
    asyncio.create_task(calib.loop())
    asyncio.create_task(dispatcher.loop())
    await streams.start()
    asyncio.create_task(update_loop())


@app.middleware("http")
async def headers(request, call_next):
    lg = request.headers.get("x-lang")
    token = i18n.request_lang.set(lg if lg in ("sv", "en") else None)
    try:
        resp = await call_next(request)
    finally:
        i18n.request_lang.reset(token)
    resp.headers["X-Robots-Tag"] = "noindex"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/static/") and "cache-control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-cache"     # fråga alltid servern (304 om filen är oförändrad)
    return resp


# ------------------------------------------------------------------ anrop från Surveillance Station / Homey

def check_token(token):
    if not config.get("setup_done"):
        raise err(409, "Installationen är inte klar")
    if not hmac.compare_digest(str(token).encode(), str(config.get("trigger_token")).encode()):
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


@app.api_route("/api/mode", methods=["GET", "POST"])
async def mode_webhook(token: str = "", mode: str = "status"):
    """Byt läge från t.ex. Homey: ?mode=<id eller namn>|status"""
    check_token(token)
    if mode.lower() != "status":
        target = modes.resolve(mode)
        if not target:
            raise err(404, "Okänt läge")
        modes.set(target, "webhook")
    i = modes.info()
    return {"mode": i["current"], "name": i["name"], "modes": [{"id": m["id"], "name": modes.name(m["id"])}
                                                              for m in modes.modes()]}


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
        "mode": modes.info() if ok else None,
        "priority": _priority() if ok else None,
        "watch": watch.running() if ok else None,
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
    if too_many("ip:" + client_ip(request)):
        raise err(429, "För många försök, vänta 5 minuter")
    before = config.get("synology")
    config.update(lambda d: d["synology"].update(s))
    ss.reset()
    try:
        try:
            cams = await ss.list_cameras()
        except SynologyError as e:
            raise err(400, "Kunde inte ansluta till Surveillance Station: {e}", e=e)
        except Exception as e:
            raise err(400, "Kunde inte nå NAS:en: {e}", e=type(e).__name__)
        login_user = (body.get("login_user") or "").strip()
        if login_user:
            try:
                await dsm_login_check(url, s["verify_tls"], login_user, body.get("login_password") or "",
                                      body.get("login_otp") or None)
            except SynologyError as e:
                raise err(400, "Ditt DSM-konto: {e}", e=e)
        else:
            login_user = s["user"]
    except HTTPException:
        failed("ip:" + client_ip(request))
        config.update(lambda d: d.__setitem__("synology", before))   # spara inget förrän det fungerar
        ss.reset()
        raise
    tz = (body.get("timezone") or "").strip()

    def finish(d):
        d["setup_done"] = True
        d["auth"]["allowed_users"] = [login_user]
        d["public_url"] = d.get("public_url") or base_url(request)
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
    user = str(body.get("user") or "").strip()
    keys = ("ip:" + client_ip(request), "user:" + user.lower())
    if too_many(*keys):
        raise err(429, "För många försök, vänta 5 minuter")
    if not config.get("auth", "dsm_login"):
        raise err(400, "Inloggning med DSM-konto är avstängd, använd SSO")
    if not auth.user_allowed(config, user):
        failed(*keys)
        raise err(403, "Kontot har inte behörighet till SynoArgus")
    syn = config.get("synology")
    try:
        await dsm_login_check(syn["url"], bool(syn.get("verify_tls")), user, body.get("password") or "",
                              body.get("otp") or None)
    except SynologyError as e:
        if e.code not in (0, 403):
            failed(*keys)
        raise HTTPException(428 if e.code == 403 else (502 if e.code == 0 else 401), str(e))
    resp = JSONResponse({"ok": True, "user": user})
    set_session(resp, request, user, "dsm")
    return resp


@app.get("/auth/sso")
async def sso_login(request: Request):
    try:
        url, cookie = await auth.sso_start(config)
    except Exception as e:
        return RedirectResponse(f"/?fel={type(e).__name__}", status_code=302)
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(auth.STATE_COOKIE, cookie, max_age=600, httponly=True, samesite="lax", secure=is_https(request))
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
        "mode": modes.info(),
        "trigger_base": base_url(request),
    }


def validate_auth(request, a):
    me = current_user(request)
    if a.get("allowed_users") and me.lower() not in [u.lower() for u in a["allowed_users"]]:
        raise err(400, "Du ({me}) måste finnas med bland tillåtna konton", me=me)
    if not a.get("dsm_login") and not (a.get("sso") or {}).get("enabled"):
        raise err(400, "Minst ett inloggningssätt måste vara på")


@app.put("/api/settings")
async def put_settings(request: Request, body: dict = Body(...)):
    require(request)
    old = config.get()
    allowed = ("synology", "auth", "detector", "defaults", "storage", "public_url", "language", "timezone",
               "modes", "mode_auto")
    new = unmask({k: v for k, v in body.items() if k in allowed}, old)
    try:
        validate.settings(new, {m["name"] for m in detector.status()["available"]})
    except validate.Invalid as e:
        raise invalid(e)
    if "auth" in new:
        validate_auth(request, {**old["auth"], **new["auth"]})
    if "timezone" in new:
        try:
            apply_timezone(new["timezone"])
        except Exception:
            raise err(400, "Ogiltig tidszon: {tz}", tz=new["timezone"])
    if new.get("language") not in (None, "sv", "en"):
        new.pop("language")
    def apply(d):
        for k, v in new.items():
            if k == "auth" and isinstance(v.get("sso"), dict):
                v = {**v, "sso": {**d["auth"].get("sso", {}), **v["sso"]}}
            if isinstance(v, dict) and isinstance(d.get(k), dict):
                d[k] = {**d[k], **v}
            else:
                d[k] = v
    config.update(apply)
    if "modes" in new:
        ids = {m["id"] for m in new["modes"]}

        def cleanup(d):  # ta bort borttagna lägen från kameror, notifierare och automatik
            for c in d["cameras"].values():
                c["modes"] = [x for x in c.get("modes") or [] if x in ids]
            for n in d["notifiers"]:
                n["modes"] = [x for x in n.get("modes") or [] if x in ids]
            hm = d["mode_auto"]["homemode"]
            for k in ("on", "off"):
                if hm.get(k) not in ids:
                    hm[k] = ""
            d["mode_auto"]["schedule"] = [e for e in d["mode_auto"].get("schedule") or [] if e.get("mode") in ids or e.get("mode") in SPECIAL_MODES]
            if d["mode"].get("current") not in ids:
                d["mode"]["current"] = new["modes"][0]["id"]
        config.update(cleanup)
    if "mode_auto" in new and (new["mode_auto"].get("homemode") or old["mode_auto"]["homemode"]) != old["mode_auto"]["homemode"]:
        modes.homemode = None  # ändrad koppling: läs om Home Mode direkt
        asyncio.create_task(modes.poll_homemode(), context=contextvars.Context())
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
        d = masked(d, export=True)
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
    keep = ("language", "timezone", "synology", "auth", "detector", "defaults", "storage", "public_url", "modes",
            "mode_auto", "trigger_token")
    try:
        notis = validate.notifier_list(body.get("notifiers") or [], notifiers.KINDS)
        notis = unmask_notifiers(notis, old.get("notifiers"))
        notis = [{**notifiers.new_notifier(n["type"]), **n} for n in notis]
        new = unmask({k: v for k, v in body.items() if k in keep}, old)
        validate.settings(new)
        if new.get("language") not in ("sv", "en"):
            new.pop("language", None)
        if not isinstance(new.get("trigger_token"), str) or len(new.get("trigger_token") or "") < 8:
            new.pop("trigger_token", None)
        cams = {}
        for cname, c in body["cameras"].items():
            if not isinstance(cname, str) or not cname.strip() or len(cname) > 200:
                raise validate.Invalid("cameras")
            cams[cname] = {**camera_defaults(cname), **validate.camera(c, COCO_TYPES), "name": cname}
            if cams[cname].get("stream_url") == MASK:
                cams[cname]["stream_url"] = ((old.get("cameras") or {}).get(cname) or {}).get("stream_url", "")
        new["cameras"] = cams
        new["notifiers"] = notis
        if isinstance(body.get("watches"), dict):
            new["watches"] = {k: watch_mod.clean(v) for k, v in body["watches"].items() if k in cams}
    except validate.Invalid as e:
        raise invalid(e)
    if "timezone" in new:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(new["timezone"])
        except Exception:
            new.pop("timezone")
    a = new.setdefault("auth", {})
    a = {**old["auth"], **a, "sso": {**old["auth"].get("sso", {}), **(a.get("sso") or {})}}
    new["auth"] = a
    me = current_user(request)
    if a.get("allowed_users") and me.lower() not in [u.lower() for u in a["allowed_users"]]:
        a["allowed_users"].append(me)  # lås inte ute den som importerar
    if not a.get("dsm_login") and not (a.get("sso") or {}).get("enabled"):
        a["dsm_login"] = True

    def apply(d):
        for k, v in new.items():
            if isinstance(v, dict) and isinstance(d.get(k), dict) and k not in ("cameras", "watches"):
                d[k] = {**d[k], **v}
            else:
                d[k] = v
        ids = {m["id"] for m in d["modes"]}
        if d["mode"].get("current") not in ids:
            d["mode"]["current"] = d["modes"][0]["id"]
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
        raise HTTPException(502, safe_error(e))


@app.put("/api/cameras/{name}")
async def put_camera(name: str, request: Request, body: dict = Body(...)):
    require(request)
    if not name.strip() or len(name) > 200:
        raise err(400, "Okänd kamera")
    try:
        clean = validate.camera(body, COCO_TYPES)
    except validate.Invalid as e:
        raise invalid(e)
    clean.pop("action_rule", None)
    if clean.get("stream_url") == MASK:
        clean.pop("stream_url")

    def apply(d):
        cam = d["cameras"].get(name) or camera_defaults(name, clean.get("ss_id"))
        cam.update(clean)
        cam["name"] = name
        d["cameras"][name] = cam
    config.update(apply)
    if "stream_url" in clean:
        streams.refresh_soon()
    return {"ok": True}


@app.delete("/api/cameras/{name}")
async def delete_camera(name: str, request: Request):
    require(request)
    if watch.running() == name:
        await watch.stop("manuellt")
    config.update(lambda d: (d["cameras"].pop(name, None), d.setdefault("watches", {}).pop(name, None)))
    return {"ok": True}


def _jpeg(img, q=85):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    return buf.getvalue()


@app.get("/api/cameras/{name}/snapshot")
async def camera_snapshot(name: str, request: Request):
    require(request)
    cam = cam_or_404(name)
    try:
        img = await engine.grab(cam)
    except Exception as e:
        raise HTTPException(502, safe_error(e))
    return Response(_jpeg(img), media_type="image/jpeg")


@app.get("/api/cameras/{name}/live")
async def camera_live(name: str, request: Request, ai: int = 0):
    """En bild till livebilden, med AI-rutor om ai=1. Webbläsaren hämtar bild efter bild."""
    require(request)
    cam = cam_or_404(name)
    try:
        img = await engine.grab(cam)
        if ai:
            await asyncio.to_thread(engine.ensure_model)
            dets, _ = await asyncio.to_thread(engine.analyse, cam, img)
            jpeg = await asyncio.to_thread(draw, img, dets, cam.get("zones"), True)
        else:
            jpeg = await asyncio.to_thread(_jpeg, img, 80)
    except Exception as e:
        raise HTTPException(502, safe_error(e))
    return Response(jpeg, media_type="image/jpeg", headers={"X-AI-ms": str(detector.last_ms or "")})


@app.post("/api/cameras/{name}/test")
async def camera_test(name: str, request: Request, body: dict = Body(default={})):
    """Tar en bild och kör AI:n utan att larma. Visar alla träffar och varför de godtas eller inte."""
    require(request)
    cam = deepcopy(cam_or_404(name))
    try:
        cam.update({k: v for k, v in validate.camera(body or {}, COCO_TYPES).items() if k in cam})
    except validate.Invalid as e:
        raise invalid(e)
    try:
        await asyncio.to_thread(engine.ensure_model)
        img = await engine.grab(cam)
        t = time.time()
        dets, valid = await asyncio.to_thread(engine.analyse, cam, img)
        ms = round((time.time() - t) * 1000)
        jpeg = await asyncio.to_thread(draw, img, dets, cam.get("zones"), True)
    except Exception as e:
        raise HTTPException(502, safe_error(e))
    return {"ms": ms, "width": img.size[0], "height": img.size[1], "detections": dets,
            "alarm": bool(valid), "image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}


# ------------------------------------------------------------------ rörelsedetektering i Surveillance Station

async def _ss_id(cam):
    if cam.get("ss_id") is None:
        cam["ss_id"] = await ss.resolve_id(cam["name"])
    return cam["ss_id"]


def _val(v):
    """Surveillance Station skickar värden som {"value": 95, "minValue": 1, "maxValue": 99, ...}."""
    return v.get("value") if isinstance(v, dict) else v


def _md_view(p):
    s, t = p.get("sensitivity"), p.get("threshold")
    lim = lambda v, k, d: v.get(k, d) if isinstance(v, dict) else d  # noqa: E731
    ss_cap = all(not isinstance(v, dict) or v.get("ssCap", True) for v in (s, t))
    return {"supported": True, "sensitivity": _val(s), "threshold": _val(t),
            "min": max(lim(s, "minValue", 1), lim(t, "minValue", 1)),
            "max": min(lim(s, "maxValue", 99), lim(t, "maxValue", 99)),
            "ss_cap": ss_cap, "source": _val(p.get("source"))}


@app.get("/api/cameras/{name}/motion")
async def motion_get(name: str, request: Request):
    require(request)
    cam = cam_or_404(name)
    try:
        raw = await ss.motion_get(await _ss_id(cam))
    except Exception as e:
        raise _ss_err(e, "motion")
    p = find_md_params(raw)
    if p is None:
        return {"supported": False, "raw": raw}
    return {**_md_view(p), "raw": p}


MD_SKIP = ("sensitivity", "threshold", "relatedEvents", "camRoi")
MD_MINIMAL = ("source", "mode", "keep", "history", "objectSize", "percentage", "region", "shortLiveSecond")


async def save_motion(cam, sens, thr):
    """Sparar känslighet och tröskel. Allt annat (t.ex. detekteringsområdet) skickas tillbaka oförändrat."""
    try:
        cam_id = await _ss_id(cam)
        current = find_md_params(await ss.motion_get(cam_id))
        if current is None:
            raise err(400, "Hittade inga värden för rörelsedetektering")
        view = _md_view(current)
        if not view["ss_cap"]:
            raise err(400, "Rörelsedetekteringen sköts av kameran, inte av Surveillance Station")
        params = {}
        for k, v in current.items():
            if k in MD_SKIP or isinstance(v, list):
                continue
            if isinstance(v, dict):
                if "value" in v:
                    params[k] = v["value"]
                continue
            params[k] = v
        params["sensitivity"] = max(view["min"], min(view["max"], int(sens)))
        params["threshold"] = max(view["min"], min(view["max"], int(thr)))
        try:
            await ss.motion_save(cam_id, params)
        except SynologyError as e:
            if e.code != 101:
                raise
            await ss.motion_save(cam_id, {k: params[k] for k in (*MD_MINIMAL, "sensitivity", "threshold")
                                          if k in params})
        after = find_md_params(await ss.motion_get(cam_id)) or {}
    except HTTPException:
        raise
    except Exception as e:
        raise _ss_err(e, "motion")
    _md_cache.pop(cam["name"], None)
    got_s, got_t = _val(after.get("sensitivity")), _val(after.get("threshold"))
    if got_s != params["sensitivity"] or got_t != params["threshold"]:
        raise err(502, "Surveillance Station sparade inte värdena (har nu {s}/{t})", s=got_s, t=got_t)
    return got_s, got_t


@app.put("/api/cameras/{name}/motion")
async def motion_put(name: str, request: Request, body: dict = Body(...)):
    require(request)
    cam = cam_or_404(name)
    try:
        sens, thr = int(body.get("sensitivity")), int(body.get("threshold"))
    except (TypeError, ValueError):
        raise err(400, "Ogiltiga värden")
    got_s, got_t = await save_motion(cam, sens, thr)
    return {"ok": True, "sensitivity": got_s, "threshold": got_t}


# ------------------------------------------------------------------ kalibrering

_md_cache = {}  # kamera -> (tid, värden) så att kalibreringen inte frågar Surveillance Station hela tiden


async def md_view_for(camera):
    hit = _md_cache.get(camera)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    cam = cam_or_404(camera)
    raw = find_md_params(await ss.motion_get(await _ss_id(cam))) or {}
    v = _md_view(raw) if raw else {"sensitivity": None, "threshold": None, "min": 1, "max": 99}
    out = (v["sensitivity"], v["threshold"], v["min"], v["max"], raw.get("region"))
    _md_cache[camera] = (time.time(), out)
    return out


calib = CalibrationManager(config, engine, md_view_for)


dispatcher = dispatch.Dispatcher(config)
streams = streams_mod.Streams(config, ss)


# ------------------------------------------------------------------ översikt (livebild och inspelningar)
OVERVIEW_PRESTART = 3          # "senaste händelsen" spelas från några sekunder före larmet


@app.get("/api/overview")
async def overview(request: Request):
    require(request)
    cams = [{"name": c["name"], "ss_id": c.get("ss_id"), "enabled": c.get("enabled", True)}
            for c in (config.get("cameras") or {}).values()]
    last = storage.list_events(1, only_alarms=True)
    return {"cameras": cams, "live": streams.status(),
            "last_event": {"ts": last[0]["ts"], "camera": last[0]["camera"], "id": last[0]["id"]} if last else None}


@app.websocket("/api/live/ws")
async def live_ws(ws: WebSocket, cam: str = ""):
    """Liveström (fMP4 över WebSocket) från go2rtc, bara för inloggade."""
    p = auth.verify(config.get("secret"), ws.cookies.get(auth.SESSION_COOKIE, ""))
    if not config.get("setup_done") or not p or not auth.user_allowed(config, p["u"]):
        await ws.close(code=4401)
        return
    if not streams.available:
        await ws.close(code=4503)
        return
    names = await streams.ensure()
    name = names.get(cam)
    if not name:
        await ws.close(code=4404)
        return
    import websockets
    await ws.accept()
    try:
        async with websockets.connect(f"{streams_mod.WS}/api/ws?src={name}", max_size=None,
                                      open_timeout=10, ping_interval=None) as up:
            async def down():
                async for msg in up:
                    if isinstance(msg, bytes):
                        await ws.send_bytes(msg)
                    else:
                        await ws.send_text(msg)

            async def upstream():
                while True:
                    m = await ws.receive()
                    if m.get("type") == "websocket.disconnect":
                        return
                    if m.get("text") is not None:
                        await up.send(m["text"])
                    elif m.get("bytes") is not None:
                        await up.send(m["bytes"])
            tasks = [asyncio.create_task(down()), asyncio.create_task(upstream())]
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
    except Exception as e:
        log.debug("Liveström %s: %s", cam, streams_mod.mask(e))
    try:
        await ws.close()
    except Exception:
        pass


def _cam_ids():
    return {c["ss_id"]: c["name"] for c in (config.get("cameras") or {}).values() if c.get("ss_id") is not None}


@app.get("/api/overview/timeline")
async def overview_timeline(request: Request, start: float = 0, end: float = 0, cam: str = ""):
    """Inspelningar (från Surveillance Station) och SynoArgus händelser mellan start och end."""
    require(request)
    end = end or time.time()
    start = start or end - 6 * 3600
    if end - start > 7 * 86400:
        start = end - 7 * 86400
    ids = _cam_ids()
    if cam:
        ids = {i: n for i, n in ids.items() if n == cam}
    recs, error = [], None
    if ids:
        try:
            items, _ = await ss.recordings(list(ids), start, end)
            recs = [{"camera": ids.get(r["cam"]), "start": r["start"], "stop": r["stop"], "reason": r["reason"]}
                    for r in items if r["cam"] in ids and r["stop"] >= start and r["start"] <= end]
        except SynologyError as e:
            error = _ss_err(e, "recordings").detail if e.code == 105 else str(e)
        except Exception as e:
            error = safe_error(e)
    evs = [{"ts": e["ts"], "camera": e["camera"], "types": e["types"], "id": e["id"], "alarm": e["alarm"]}
           for e in storage.events_between(start, end, cam or None)]
    return {"start": start, "end": end, "recordings": recs, "events": evs, "error": error}


@app.get("/api/overview/recording")
async def overview_recording(request: Request, cam: str, t: float, length: int = 120, check: int = 0):
    """En bit av inspelningen som täcker tiden t (mp4). Rubriken X-Start anger var biten börjar."""
    require(request)
    c = cam_or_404(cam)
    if c.get("ss_id") is None:
        raise err(404, "Ingen inspelning")
    length = max(10, min(600, int(length)))
    try:
        items, _ = await ss.recordings([c["ss_id"]], t - 6 * 3600, t + length)
    except SynologyError as e:
        raise _ss_err(e, "recordings") if e.code == 105 else HTTPException(502, str(e))
    cover = [r for r in items if r["cam"] == c["ss_id"] and r["start"] <= t < r["stop"]]
    if not cover:
        nxt = [r["start"] for r in items if r["cam"] == c["ss_id"] and r["start"] > t]
        body = {"found": False, "detail": tr("Ingen inspelning"), "next": min(nxt) if nxt else None}
        return body if check else JSONResponse(body, status_code=404)
    r = cover[-1]
    offset = max(0.0, t - r["start"])
    if check:
        return {"found": True, "start": r["start"] + offset, "stop": r["stop"]}
    try:
        resp = await ss.open_recording(r["id"], offset * 1000, length * 1000)
    except SynologyError as e:
        raise HTTPException(502, str(e))

    async def body():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
    return StreamingResponse(body(), media_type=resp.headers.get("content-type") or "video/mp4",
                             headers={"X-Start": str(r["start"] + offset), "X-Stop": str(r["stop"]),
                                      "Cache-Control": "no-store"})


@app.get("/api/overview/raw")
async def overview_raw(request: Request):
    """Rådata för felsökning (adresser utan lösenord)."""
    require(request)
    await streams.ensure(force=True)
    ids = _cam_ids()
    rec_raw = None
    if ids:
        try:
            _, rec_raw = await ss.recordings(list(ids), time.time() - 3600, time.time(), limit=5)
        except Exception as e:
            rec_raw = {"error": str(e)}
    return {"live": streams.status(), "live_paths": json.loads(streams_mod.mask(json.dumps(streams.raw))),
            "recordings": _mask_rules(rec_raw)}
engine.dispatcher = dispatcher
watch = watch_mod.WatchManager(config, engine, ss)


@app.api_route("/api/notify", methods=["GET", "POST"])
async def notify_on_request(token: str = "", notifier: str = "", event: str = "", text: str = ""):
    """Skickar en notifiering som väntar på anrop: ?notifier=<id eller namn>[&event=<nr>][&text=…]"""
    check_token(token)
    n = dispatcher.find_notifier(notifier)
    if not n:
        raise err(404, "Okänd notifiering")
    if not n.get("enabled", True):
        raise err(409, "Notifieringen är avstängd")
    ev = None
    if str(event).strip():
        try:
            ev = int(str(event).strip())
        except ValueError:
            raise err(400, "Ogiltigt värde: {field}", field="event")
    try:
        event_id, ok, e = await dispatcher.request(n, ev, text or None)
    except LookupError:
        raise err(404, "Händelsen finns inte (längre)")
    return {"ok": ok, "event": event_id, "notifier": n.get("name") or n["type"], "error": e}
watch.calib_active = calib.active
calib.watch_active = watch.running


def _busy_err(e):
    what, cam = e.args
    if what == "calibration":
        return err(409, "En kalibrering pågår på {cam}. Bevakning och kalibrering kan inte köras samtidigt.", cam=cam)
    return err(409, "En bevakning pågår redan på {cam}. Stoppa den först.", cam=cam)


async def _watch_start(camera, occupied, source):
    try:
        return await watch.start(camera, occupied=occupied, source=source)
    except watch_mod.Busy as e:
        raise _busy_err(e)
    except ValueError as e:
        if e.args and e.args[0] == "zone":
            raise err(400, "Rita en zon och spara bevakningen först")
        raise err(404, "Okänd kamera")


@app.api_route("/api/watch", methods=["GET", "POST"])
async def watch_webhook(token: str = "", camera: str = "", action: str = "status", occupied: int = 0):
    """Starta/stoppa bevakning från t.ex. Homey: ?camera=<namn>&action=start|stop|status[&occupied=1]"""
    check_token(token)
    action = action.lower()
    if action not in ("start", "stop", "status"):
        raise err(400, "Okänd åtgärd (start, stop eller status)")
    names = [c for c, w in (config.get("watches") or {}).items() if w.get("zone")]
    if action == "start":
        if not camera and len(names) == 1:
            camera = names[0]
        await _watch_start(camera, bool(occupied), "webhook")
    elif action == "stop":
        if not camera or watch.running() == camera:
            await watch.stop("webhook")
    st = watch.status()
    return {"active": st["active"], "elapsed": st.get("elapsed"), "state": st.get("state"), "configured": names}


@app.get("/api/watches")
async def watches_get(request: Request):
    require(request)
    return {"watches": config.get("watches") or {}, "defaults": watch_mod.defaults(), "status": watch.status(),
            "calibration": calib.active(), "base": (config.get("public_url") or base_url(request)).rstrip("/"),
            "token": config.get("trigger_token")}


@app.get("/api/watches/{name}/debug.jpg")
async def watch_debug(name: str, request: Request):
    """Det bevakningen ser just nu: zonen, rörelsen och spåren inritade."""
    require(request)
    jpeg = await asyncio.to_thread(watch.debug, name)
    if not jpeg:
        raise err(404, "Bevakningen är inte igång")
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/watches/status")
async def watches_status(request: Request):
    require(request)
    return watch.status()


@app.put("/api/watches/{name}")
async def watch_put(name: str, request: Request, body: dict = Body(...)):
    require(request)
    cam_or_404(name)
    try:
        w = watch_mod.clean(body)
    except validate.Invalid as e:
        raise invalid(e)
    known = {n["id"] for n in config.get("notifiers") or []}
    for e in w["events"].values():
        e["notifiers"] = [i for i in e["notifiers"] if i in known]
    config.update(lambda d: d.setdefault("watches", {}).__setitem__(name, w))
    watch.reload(name)
    return {"ok": True, "watch": w}


@app.delete("/api/watches/{name}")
async def watch_delete(name: str, request: Request):
    require(request)
    if watch.running() == name:
        await watch.stop("manuellt")
    config.update(lambda d: d.setdefault("watches", {}).pop(name, None))
    return {"ok": True}


@app.post("/api/watches/{name}/action")
async def watch_action(name: str, request: Request, body: dict = Body(...)):
    require(request)
    cam_or_404(name)
    action = (body or {}).get("action")
    if action == "start":
        await _watch_start(name, bool(body.get("occupied")), "manuellt")
    elif action == "stop":
        if watch.running() == name:
            await watch.stop("manuellt")
    else:
        raise err(400, "Okänd åtgärd")
    return watch.status()


async def _on_trigger(name, cam):
    try:
        await calib.on_reaction(name, cam)
    except Exception as e:
        log.debug("Kalibrering: %s", e)
engine.on_trigger = _on_trigger


@app.get("/api/cameras/{name}/calibration")
async def calibration_get(name: str, request: Request):
    require(request)
    cam_or_404(name)
    return {"run": await calib.report(name), "active": calib.active()}


@app.post("/api/cameras/{name}/calibration")
async def calibration_post(name: str, request: Request, body: dict = Body(...)):
    require(request)
    cam = cam_or_404(name)
    action = (body or {}).get("action")
    try:
        if action == "start":
            await calib.start(name, body.get("hours", 24))
        elif action == "stop":
            await calib.stop(name)
        elif action == "walk":
            if not calib.running(name):
                raise err(400, "Ingen kalibrering pågår")
            calib.walk(name)
        elif action == "clear":
            calib.clear(name)
        elif action in ("apply", "undo"):
            run = await calib.report(name)
            if not run or run["status"] == "running":
                raise err(400, "Ingen färdig kalibrering")
            if action == "apply":
                p = (run["report"] or {}).get("proposal")
                if not p:
                    raise err(400, "Inget förslag")
                await save_motion(cam, p["sensitivity"], p["threshold"])
                calib.set_applied(name, {"sensitivity": p["sensitivity"], "threshold": p["threshold"],
                                         "ts": time.time()})
            else:
                b = run["before"] or {}
                await save_motion(cam, b["sensitivity"], b["threshold"])
                calib.set_applied(name, None)
        else:
            raise err(400, "Okänd åtgärd")
    except BusyError as e:
        if str(e.args[0]).startswith("watch:"):
            raise err(409, "En bevakning pågår på {cam}. Bevakning och kalibrering kan inte köras samtidigt.",
                      cam=e.args[0][6:])
        raise err(409, "En kalibrering pågår redan på {cam}. Stoppa den eller vänta tills den är klar.", cam=e.args[0])
    except ValueError:
        raise err(409, "En kalibrering pågår redan")
    except HTTPException:
        raise
    except Exception as e:
        raise _ss_err(e, "motion")
    return {"run": await calib.report(name), "active": calib.active()}


# ------------------------------------------------------------------ action rules i Surveillance Station

def _walk_strings(obj, fn):
    """Går igenom ett JSON-objekt (även JSON inbäddat som text) och byter strängar med fn."""
    if isinstance(obj, dict):
        return {k: _walk_strings(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_strings(v, fn) for v in obj]
    if isinstance(obj, str):
        st = obj.strip()
        if st[:1] in "[{":
            try:
                inner = json.loads(st)
                return json.dumps(_walk_strings(inner, fn), separators=(",", ":"))
            except ValueError:
                pass
        return fn(obj)
    return obj


def _strings(obj):
    found = []
    _walk_strings(obj, lambda s: found.append(s) or s)
    return found


def _set_keys(obj, keys, value):
    if isinstance(obj, dict):
        return {k: (value if k in keys and not isinstance(v, (dict, list)) else _set_keys(v, keys, value))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_set_keys(v, keys, value) for v in obj]
    if isinstance(obj, str) and obj.strip()[:1] in "[{":
        try:
            return json.dumps(_set_keys(json.loads(obj), keys, value), separators=(",", ":"))
        except ValueError:
            return obj
    return obj


SENSITIVE_KEYS = ("password", "passwd", "iftttkey", "evtwebhooktoken", "headers", "httpbody", "username")


def _mask_rules(obj):
    """Rådata för felsökning: lösenord, nycklar och andra reglers adresser visas inte."""
    def url(sv):
        if not isinstance(sv, str) or not sv.startswith(("http://", "https://")):
            return sv
        if "/api/trigger/" in sv:
            return re.sub(r"token=[^&\s]+", "token=***", sv)
        m = re.match(r"^(https?://[^/?#]+)", sv)
        return (m.group(1) if m else "") + "/***"

    def walk(o):
        if isinstance(o, dict):
            return {k: (MASK if k.lower() in SENSITIVE_KEYS and v not in ("", None) and not isinstance(v, (dict, list))
                        else walk(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        if isinstance(o, str):
            st = o.strip()
            if st[:1] in "[{":
                try:
                    return json.dumps(walk(json.loads(st)), separators=(",", ":"))
                except ValueError:
                    pass
            return url(o)
        return o
    return walk(obj)


def _trigger_url(request, name):
    from urllib.parse import quote
    base = (config.get("public_url") or base_url(request)).rstrip("/")
    return f"{base}/api/trigger/{quote(name, safe='')}?token={quote(config.get('trigger_token'), safe='')}"


MOTION_EVENT = {"evtSrc": 0, "evtId": 5}  # källa kamera, händelse "rörelse upptäckt"
ID_KEYS = ("ruleId", "multiRuleId", "id")


def _rule_events(rule):
    ev = rule.get("events") or []
    if isinstance(ev, str):
        try:
            ev = json.loads(ev)
        except ValueError:
            ev = []
    return ev if isinstance(ev, list) else []


def _rule_summary(rule, name, url, cam_id=None):
    from urllib.parse import quote
    urls = [s for s in _strings(rule) if s.startswith("http") and "/api/trigger/" in s]
    marker = [f"/api/trigger/{quote(name, safe='')}?", f"/api/trigger/{name}?"]
    mine = [u for u in urls if any(m in u for m in marker)]
    if not mine:
        return None
    event_ok = any(e.get("evtSrc") == 0 and e.get("evtId") == 5 and
                   (cam_id is None or str(e.get("evtDevId")) == str(cam_id)) for e in _rule_events(rule))
    return {"id": rule.get("ruleId", rule.get("id")), "name": rule.get("name"), "enabled": rule.get("enabled"),
            "urls": mine, "current": url in mine, "event_ok": event_ok,
            "home_ok": rule.get("activeInHomeMode") is not False}


def _motion_events(name, cam_id):
    return [{"evtAttribute": 0, "evtDevEnable": True, "evtDevId": cam_id, "evtDevIds": str(cam_id),
             "evtDevName": name, "evtDevices": [{"devEnable": True, "devId": cam_id}], "evtDsId": 0,
             "evtId": 5, "evtItem": -1, "evtSrc": 0, "evtStatus": 1, "evtTrig": 1,
             "evtWebhookMethod": 1, "evtWebhookToken": ""}]


def _new_rule(name, cam_id, url):
    """Ny regel i det format Surveillance Station själv använder (utan id-fält = ny regel)."""
    action = {"actDevEnable": False, "actDevId": -1, "actDevIds": "0", "actDevName": "", "actDevices": {},
              "actDsId": 0, "actId": -1, "actItem": {"id": -1, "name": ""}, "actItemList": None,
              "actRetItem": {"id": -2, "name": ""}, "actRetPos": -2, "actSrc": 1, "actTimeDur": 10,
              "actTimeUnit": 1, "actTimes": 1, "blCondition": False, "bmkComment": "", "bmkLock": False,
              "bmkName": "", "bmkShowOsd": False, "conditionUnit": 0, "conditionValue": "", "enabled": True,
              "extUrl": url, "headers": "", "hostAccessUrl": "", "httpBody": "", "httpContentType": 0,
              "iftttEvent": "", "iftttKey": "", "param1": "", "param2": "", "param3": "", "password": "",
              "userName": "", "webhookReqMethod": 0}
    return {"name": f"SynoArgus - {name}", "ruleType": 0, "actType": 0, "evtMinIntvl": 10,
            "multiEvtSetting": 0, "activeInHomeMode": True, "enabled": True, "urlSplit": False,
            "actSchedule": "1" * 336, "events": _motion_events(name, cam_id), "actions": [action]}


def _rule_ids(rules):
    return {r.get("ruleId", r.get("id")) for r in rules}


def _ss_err(e, what):
    if isinstance(e, SynologyError) and e.code == 105:
        if what == "rules":
            return err(403, "Kontot behöver profilen Administrator i Surveillance Station för att läsa och skapa "
                            "regler. Du kan slå på det tillfälligt, skapa eller uppdatera reglerna och sedan byta "
                            "tillbaka – reglerna fortsätter att fungera.")
        if what == "recordings":
            return err(403, "Kontot saknar behörighet att läsa inspelningar i Surveillance Station. Ge kontot rätt "
                            "att visa inspelningar (t.ex. profilen All-Object Manager).")
        return err(403, "Kontot behöver profilen All-Object Manager (eller Administrator) i Surveillance Station "
                        "för att läsa och ändra rörelsedetekteringen.")
    if isinstance(e, HTTPException):
        return e
    return HTTPException(502, safe_error(e))


async def _rules():
    raw = await ss.action_rules()
    return raw, find_rules(raw) or []


def _remember_rule(name, info):
    def apply(d):
        if name in d["cameras"]:
            d["cameras"][name]["action_rule"] = info
    config.update(apply)


@app.get("/api/cameras/{name}/actionrule")
async def actionrule_get(name: str, request: Request):
    require(request)
    cam = cam_or_404(name)
    url = _trigger_url(request, name)
    stored = cam.get("action_rule")
    try:
        cam_id = await _ss_id(cam)
        raw, rules = await _rules()
    except Exception as e:
        return {"url": url, "rules": [], "stored": stored, "error": _ss_err(e, "rules").detail, "raw": None}
    mine = [r for r in (_rule_summary(x, name, url, cam_id) for x in rules) if r]
    if stored and not stored.get("confirmed") and any(r["current"] for r in mine):
        stored["confirmed"] = True
        _remember_rule(name, stored)
    return {"url": url, "rules": mine, "stored": stored, "count": len(rules), "raw": _mask_rules(raw)}


@app.post("/api/cameras/{name}/actionrule")
async def actionrule_post(name: str, request: Request, body: dict = Body(default={})):
    """create: ny regel (rörelse -> webhook till SynoArgus).
    update: byt adress i befintliga SynoArgus-regler för kameran.
    fix:    som update, och sätt händelsen till rörelse för rätt kamera."""
    require(request)
    cam = cam_or_404(name)
    url = _trigger_url(request, name)
    action = (body or {}).get("action", "create")
    created = False
    try:
        cam_id = await _ss_id(cam)
        _, rules = await _rules()
        before = _rule_ids(rules)
        if action in ("update", "fix"):
            changed = 0
            for rule in rules:
                sm = _rule_summary(rule, name, url, cam_id)
                if not sm or (sm["current"] and ((sm["event_ok"] and sm["home_ok"]) or action == "update")):
                    continue
                new = _walk_strings(rule, lambda x: url if x in sm["urls"] else x)
                if action == "fix":
                    new["activeInHomeMode"] = True  # SynoArgus avgör själv via lägen
                    if not sm["event_ok"]:
                        new["events"] = _motion_events(name, cam_id)
                        if not str(new.get("actSchedule", "1")).strip("1") == "":
                            new["actSchedule"] = "1" * 336
                await ss.action_rule_save(new)
                changed += 1
            result = {"updated": changed}
        else:
            if any(_rule_summary(r, name, url, cam_id) for r in rules):
                raise err(409, "Det finns redan en SynoArgus-regel för kameran")
            await ss.action_rule_save(_new_rule(name, cam_id, url))
            created = True
            _remember_rule(name, {"name": f"SynoArgus - {name}", "created": time.time(), "confirmed": False})
            result = {"created": True}
        try:
            _, rules = await _rules()
        except Exception:
            return {"ok": True, **result, "confirmed": False}
        after = _rule_ids(rules)
        if not before <= after:
            raise err(502, "Varning: en befintlig regel försvann efter ändringen. Kontrollera Action Rules "
                           "i Surveillance Station.")
        if created and len(after - before) != 1:
            raise err(502, "Regeln skapades inte som en ny regel. Kontrollera Action Rules i Surveillance Station.")
        found = [r for r in (_rule_summary(x, name, url, cam_id) for x in rules) if r and r["current"]]
        if not found:
            raise err(502, "Surveillance Station tog emot anropet men regeln syns inte. Skapa den manuellt.")
        if created:
            _remember_rule(name, {"name": f"SynoArgus - {name}", "created": time.time(), "confirmed": True})
    except HTTPException:
        raise
    except Exception as e:
        raise _ss_err(e, "rules")
    return {"ok": True, **result, "confirmed": True, "rules": found}


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
    try:
        validate.notifier_list(body, notifiers.KINDS)
    except validate.Invalid:
        raise err(400, "Okänd typ av notifiering")
    for n in body:
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
        raise err(404, "Spara notifieringen först")
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
    _usage_cache["t"] = 0
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
    return {"detector": detector.status(), "cameras": cams, "recent": engine.recent[:30],
            "update": _update["data"], "mode": modes.info(), "priority": _priority(),
            "watch": {k: v for k, v in watch.status().items() if k != "log"}, "storage": await _usage(),
            **storage.stats()}


_usage_cache = {"t": 0, "data": None}


async def _usage(force=False):
    """Använt utrymme (räknas om högst en gång per minut – det kan vara många filer)."""
    if force or not _usage_cache["data"] or time.time() - _usage_cache["t"] > 60:
        _usage_cache["data"] = await asyncio.to_thread(storage.usage)
        _usage_cache["t"] = time.time()
    return {**_usage_cache["data"], "max_mb": config.get("storage", "max_mb") or 0,
            "days_to_keep": config.get("storage", "days_to_keep") or 0}


@app.get("/api/storage")
async def storage_usage(request: Request):
    require(request)
    return await _usage(force=True)


def _priority():
    """Pågående "Jag går förbi nu" (larm fördröjs) för headern."""
    if not engine.priority_active():
        return None
    return {"camera": (calib.walk_info or {}).get("camera"), "until": engine.priority_until,
            "left": max(0, round(engine.priority_until - time.time()))}


@app.post("/api/mode/set")
async def mode_set(request: Request, body: dict = Body(...)):
    require(request)
    target = modes.resolve(str(body.get("mode") or ""))
    if not target:
        raise err(404, "Okänt läge")
    modes.set(target, "manual")
    return modes.info()


@app.get("/api/update")
async def update(request: Request, force: int = 0):
    require(request)
    return await check_update(force=bool(force))


# ------------------------------------------------------------------ webbgränssnitt

app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


@app.get("/manifest.webmanifest")
async def manifest():
    """Gör att SynoArgus kan installeras som app (kräver https)."""
    return JSONResponse({
        "name": "SynoArgus", "short_name": "SynoArgus", "id": "/", "start_url": "/", "scope": "/",
        "display": "standalone", "background_color": "#14324a", "theme_color": "#14324a",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ]}, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
async def service_worker():
    return FileResponse(os.path.join(HERE, "static", "sw.js"), media_type="text/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


_index_html = {}


@app.get("/")
async def index():
    """index.html med versionsnummer i filadresserna, så att webbläsaren hämtar nya filer efter en uppdatering."""
    if "html" not in _index_html:
        with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as f:
            html = f.read()
        v = f"{APP_VERSION}-{APP_BUILD}"
        _index_html["html"] = re.sub(r'(/static/[\w./-]+\.(?:js|css))(?=")', rf"\1?v={v}", html)
    return Response(_index_html["html"], media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})
