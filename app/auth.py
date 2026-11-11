"""Inloggning: DSM-konto (via DSM:s API) eller SSO via Synology SSO Server (OpenID Connect)."""
import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import time
from urllib.parse import urlencode

import httpx

SESSION_COOKIE = "synoargus_session"
STATE_COOKIE = "synoargus_sso"
SESSION_DAYS = 30


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(secret, payload):
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(secret, token):
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        p = json.loads(_unb64(body))
        if p.get("exp", 0) < time.time():
            return None
        return p
    except Exception:
        return None


def make_session(secret, user, method):
    return sign(secret, {"u": user, "m": method, "exp": int(time.time()) + SESSION_DAYS * 86400})


def is_private(host):
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def real_ip(peer, forwarded):
    """Klientens adress. X-Forwarded-For används bara när anropet kommer från en proxy på hemnätet
    (t.ex. DSM:s omvända proxy), och då den adress som proxyn själv lade till (sist i listan)."""
    if forwarded and is_private(peer):
        last = forwarded.split(",")[-1].strip()
        if last.startswith("[") and "]" in last:      # [ipv6]:port
            last = last[1:last.index("]")]
        elif last.count(":") == 1:                    # ipv4:port
            last = last.split(":")[0]
        try:
            ipaddress.ip_address(last)
            return last
        except ValueError:
            return ""      # obegriplig rubrik: lita inte på anropet
    return peer or ""


def user_allowed(cfg, user):
    allowed = [u.strip().lower() for u in cfg.get("auth", "allowed_users") or [] if u.strip()]
    return not allowed or (user or "").lower() in allowed


# ---------------------------------------------------------------- SSO (OIDC)

_discovery = {}


async def discover(issuer, verify_tls):
    key = issuer.rstrip("/")
    hit = _discovery.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    async with httpx.AsyncClient(timeout=10, verify=verify_tls) as c:
        r = await c.get(key + "/.well-known/openid-configuration")
        r.raise_for_status()
        conf = r.json()
    _discovery[key] = (time.time() + 3600, conf)
    return conf


async def sso_start(cfg):
    sso = cfg.get("auth", "sso")
    conf = await discover(sso["issuer"], bool(cfg.get("synology", "verify_tls")))
    state, nonce = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    params = {
        "response_type": "code", "client_id": sso["client_id"], "redirect_uri": sso["redirect_url"],
        "scope": "openid email groups", "state": state, "nonce": nonce,
    }
    url = conf["authorization_endpoint"] + "?" + urlencode(params)
    cookie = sign(cfg.get("secret"), {"s": state, "n": nonce, "exp": int(time.time()) + 600})
    return url, cookie


async def sso_finish(cfg, code, state, state_cookie):
    st = verify(cfg.get("secret"), state_cookie or "")
    if not st or not hmac.compare_digest(st["s"], state or ""):
        raise ValueError("Ogiltig eller för gammal SSO-förfrågan, försök igen")
    sso = cfg.get("auth", "sso")
    verify_tls = bool(cfg.get("synology", "verify_tls"))
    conf = await discover(sso["issuer"], verify_tls)
    async with httpx.AsyncClient(timeout=10, verify=verify_tls) as c:
        r = await c.post(conf["token_endpoint"], data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": sso["redirect_url"],
            "client_id": sso["client_id"], "client_secret": sso["client_secret"]})
        if r.status_code >= 400:
            raise ValueError(f"SSO-servern godtog inte inloggningen ({r.status_code})")
        tok = r.json()
        claims = {}
        # id_token hämtades direkt från SSO-servern i ett eget anrop, så innehållet kan läsas.
        if tok.get("id_token"):
            try:
                claims = json.loads(_unb64(tok["id_token"].split(".")[1]))
            except Exception:
                claims = {}
            if claims.get("nonce") != st["n"]:
                raise ValueError("SSO-svaret hör inte till den här inloggningen")
        if conf.get("userinfo_endpoint") and tok.get("access_token"):
            try:
                ui = await c.get(conf["userinfo_endpoint"],
                                 headers={"Authorization": f"Bearer {tok['access_token']}"})
                if ui.status_code == 200:
                    claims.update(ui.json())
            except Exception:
                pass
    user = (claims.get("username") or claims.get("preferred_username") or claims.get("name")
            or claims.get("email") or claims.get("sub"))
    if not user:
        raise ValueError("SSO-servern skickade inget användarnamn")
    return str(user)
