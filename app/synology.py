"""Klient för Synology Surveillance Station och DSM-inloggning."""
import asyncio
import logging

import httpx

from .i18n import tr

log = logging.getLogger("synoargus.synology")

PROFILE = {"high": 0, "balanced": 1, "low": 2}

AUTH_ERRORS = {
    400: "Fel användarnamn eller lösenord",
    401: "Kontot är inaktiverat eller ett gästkonto",
    402: "Kontot saknar behörighet",
    403: "Engångskod (tvåstegsverifiering) krävs",
    404: "Engångskoden stämmer inte",
    406: "Tvåstegsverifiering måste aktiveras för kontot",
    407: "För många försök, IP-adressen är spärrad",
    408: "Lösenordet har gått ut",
    409: "Lösenordet har gått ut",
    410: "Lösenordet måste bytas",
    411: "Kontot är låst",
}

API_ERRORS = {
    100: "Okänt fel",
    101: "Ogiltiga parametrar",
    102: "API:t finns inte",
    103: "Metoden finns inte",
    104: "API-versionen stöds inte",
    105: "Behörighet saknas (har kontot rätt till Surveillance Station?)",
    106: "Sessionen har gått ut",
    107: "Inloggad från flera ställen",
    119: "Sessionen är ogiltig",
}


class SynologyError(Exception):
    def __init__(self, code, msg=None, auth=False):
        self.code = code
        if not msg:
            text = (AUTH_ERRORS.get(code) if auth else None) or API_ERRORS.get(code) or AUTH_ERRORS.get(code) \
                or "Okänt fel"
            msg = tr("{text} (DSM-kod {code})", text=tr(text), code=code)
        super().__init__(msg)


def _client(verify):
    return httpx.AsyncClient(verify=verify, timeout=httpx.Timeout(15.0, connect=5.0))


async def dsm_login_check(url, verify, user, password, otp=None):
    """Kontrollerar ett DSM-konto (för inloggning i SynoArgus). Loggar ut direkt efteråt.

    Prövar först en vanlig DSM-session. Saknar kontot behörighet till DSM (t.ex. ett konto
    som bara får använda Surveillance Station) prövas en Surveillance Station-session.
    """
    entry = url.rstrip("/") + "/webapi/entry.cgi"
    last = 100
    async with _client(verify) as c:
        for session in ("SynoArgus", "SurveillanceStation"):
            params = {"api": "SYNO.API.Auth", "version": "6", "method": "login",
                      "account": user, "passwd": password, "session": session, "format": "sid"}
            if otp:
                params["otp_code"] = otp
            try:
                r = await c.get(entry, params=params)
                j = r.json()
            except Exception as e:
                raise SynologyError(0, tr("Kunde inte nå DSM på {url}: {e}", url=url, e=e))
            if j.get("success"):
                try:
                    await c.get(entry, params={"api": "SYNO.API.Auth", "version": "6", "method": "logout",
                                               "session": session, "_sid": j["data"]["sid"]})
                except Exception:
                    pass
                return True
            last = j.get("error", {}).get("code", 100)
            log.info("DSM-inloggning för %s med session %s gav kod %s", user, session, last)
            if last != 402:
                break
    raise SynologyError(last, auth=True)


class SurveillanceStation:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sid = None
        self._lock = asyncio.Lock()
        self._client = None
        self._client_key = None

    def _settings(self):
        s = self.cfg.get("synology")
        return s["url"].rstrip("/"), s["user"], s["password"], bool(s.get("verify_tls"))

    def _http(self):
        url, user, _, verify = self._settings()
        key = (url, user, verify)
        if self._client is None or self._client_key != key:
            if self._client is not None:
                asyncio.ensure_future(self._client.aclose())
            self._client = _client(verify)
            self._client_key = key
            self.sid = None
        return self._client

    def reset(self):
        self.sid = None

    async def _login(self):
        url, user, password, _ = self._settings()
        if not url or not user:
            raise SynologyError(0, tr("Synology-anslutningen är inte inställd"))
        r = await self._http().get(url + "/webapi/entry.cgi", params={
            "api": "SYNO.API.Auth", "version": "6", "method": "login",
            "account": user, "passwd": password, "session": "SurveillanceStation", "format": "sid"})
        j = r.json()
        if not j.get("success"):
            raise SynologyError(j.get("error", {}).get("code", 100), auth=True)
        self.sid = j["data"]["sid"]
        log.info("Inloggad i Surveillance Station som %s", user)

    async def _call(self, params, raw=False, retry=True):
        async with self._lock:
            if not self.sid:
                await self._login()
            sid = self.sid
        url, *_ = self._settings()
        r = await self._http().get(url + "/webapi/entry.cgi", params={**params, "_sid": sid})
        ctype = r.headers.get("content-type", "")
        if raw and ctype.startswith("image/"):
            return r.content
        try:
            j = r.json()
        except Exception:
            raise SynologyError(100, tr("Oväntat svar från Synology ({code}, {ctype})", code=r.status_code, ctype=ctype))
        if not j.get("success"):
            code = j.get("error", {}).get("code", 100)
            if retry and code in (105, 106, 107, 119):
                self.sid = None
                return await self._call(params, raw=raw, retry=False)
            raise SynologyError(code)
        return j.get("data")

    async def list_cameras(self):
        data = await self._call({
            "api": "SYNO.SurveillanceStation.Camera", "version": "9", "method": "List",
            "basic": "true", "streamInfo": "true"})
        cams = []
        for c in data.get("cameras", []):
            cams.append({
                "id": c.get("id"),
                "name": c.get("newName") or c.get("name"),
                "enabled": c.get("enabled", True),
                "status": c.get("status"),
            })
        return cams

    async def snapshot(self, cam_id):
        quality = self.cfg.get("synology", "quality") or "balanced"
        return await self._call({
            "api": "SYNO.SurveillanceStation.Camera", "version": "9", "method": "GetSnapshot",
            "id": str(cam_id), "profileType": str(PROFILE.get(quality, 1))}, raw=True)

    async def resolve_id(self, name):
        for c in await self.list_cameras():
            if c["name"] == name:
                return c["id"]
        raise SynologyError(0, tr("Kameran \"{name}\" finns inte i Surveillance Station", name=name))

    # -------------------------------------------------------- rörelsedetektering
    # Surveillance Station Web API: SYNO.SurveillanceStation.Camera.Event (MotionEnum / MDParamSave).
    # Dokumentationen är knapphändig, så svaret tolkas tolerant.

    async def motion_get(self, cam_id):
        last = None
        for version in ("1", "2"):
            try:
                return await self._call({"api": "SYNO.SurveillanceStation.Camera.Event", "version": version,
                                         "method": "MotionEnum", "camId": str(cam_id)})
            except SynologyError as e:
                last = e
                if e.code not in (102, 103, 104):
                    raise
        raise last

    async def motion_save(self, cam_id, params):
        p = {"api": "SYNO.SurveillanceStation.Camera.Event", "version": "1", "method": "MDParamSave",
             "camId": str(cam_id)}
        p.update({k: (str(v).lower() if isinstance(v, bool) else str(v)) for k, v in params.items()})
        return await self._call(p)


def find_md_params(data):
    """Letar upp den del av svaret som innehåller sensitivity och threshold."""
    if isinstance(data, dict):
        if "sensitivity" in data and "threshold" in data:
            return data
        for v in data.values():
            hit = find_md_params(v)
            if hit is not None:
                return hit
    elif isinstance(data, list):
        for v in data:
            hit = find_md_params(v)
            if hit is not None:
                return hit
    return None
