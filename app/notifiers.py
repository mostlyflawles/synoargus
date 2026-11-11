"""Notifierare: Pushbullet, webhook, MQTT, email, Telegram och ntfy."""
import asyncio
import base64
import json
import logging
import re
import uuid
from datetime import datetime
from urllib.parse import quote

import httpx

from .config import type_name

log = logging.getLogger("synoargus.notify")

KINDS = ("pushbullet", "webhook", "mqtt", "email", "telegram", "ntfy")
SECRET_FIELDS = ("api_key", "password", "token", "bot_token")

PLACEHOLDER_RE = re.compile(r"%([A-Za-zÅÄÖåäö_]+)%")


def placeholder_values(event):
    valid = [d for d in event.get("detections", []) if d.get("valid")]
    try:
        dt = datetime.fromisoformat(event["time"])
    except Exception:
        dt = datetime.now()
    lg = event.get("lang") or "sv"
    v = {
        "kamera": event["camera"],
        # bevakningshändelser har inga typer: då är %vad% händelsens text
        "vad": ", ".join(type_name(t, lg) for t in event["types"]) or event.get("watch_event", ""),
        "vad_en": ", ".join(event["types"]) or event.get("watch_key", ""),
        "händelse": event.get("watch_event", ""),
        "händelse_id": event.get("watch_key", ""),
        "antal": str(len(valid)),
        "meddelande": event["message"],
        "säkerhet": str(round(max(d["confidence"] for d in valid))) if valid else "",
        "tid": dt.strftime("%H:%M:%S"),
        "datum": dt.strftime("%Y-%m-%d"),
        "bild": event.get("image_url") or "",
        "händelse_nr": str(event.get("event_id") or ""),     # för /api/notify
    }
    # engelska namn på samma platshållare
    for en, sv in ALIASES.items():
        v[en] = v[sv]
    return v


ALIASES = {"camera": "kamera", "what": "vad", "what_en": "vad_en", "count": "antal", "message": "meddelande",
           "confidence": "säkerhet", "time": "tid", "date": "datum", "image": "bild", "event": "händelse",
           "event_id": "händelse_id", "event_no": "händelse_nr"}


def has_placeholders(text):
    return bool(PLACEHOLDER_RE.search(text or ""))


def render(template, event, url=False):
    """Byter %kamera% m.fl. mot värden. url=True kodar värdena för adresser."""
    vals = placeholder_values(event)

    def rep(m):
        key = m.group(1).lower()
        key = {"sakerhet": "säkerhet", "handelse": "händelse", "handelse_id": "händelse_id",
               "handelse_nr": "händelse_nr"}.get(key, key)
        if key not in vals:
            return m.group(0)
        return quote(vals[key], safe="") if url else vals[key]
    return PLACEHOLDER_RE.sub(rep, template or "")


def new_notifier(kind):
    base = {"id": uuid.uuid4().hex[:8], "type": kind, "name": "", "enabled": True,
            "cameras": [], "types": [], "modes": [],
            "deliver": "direct",    # direct | request (skickas bara när /api/notify anropas)
            "fallback_min": 0}      # request: skicka ändå efter så många minuter (0 = aldrig)
    if kind == "pushbullet":
        base.update({"api_key": "", "device_iden": "", "send_image": True, "title": "", "body": ""})
    elif kind == "webhook":
        base.update({"url": "", "method": "POST", "auth": "none", "username": "", "password": "",
                     "token": "", "send_image": False, "verify_tls": True})
    elif kind == "mqtt":
        base.update({"host": "", "port": 1883, "username": "", "password": "", "base_topic": "synoargus",
                     "send_image": False, "retain": False, "qos": 0})
    elif kind == "email":
        base.update({"host": "", "port": 587, "security": "starttls", "username": "", "password": "",
                     "from_addr": "", "to": "", "subject": "", "body": "", "send_image": True})
    elif kind == "telegram":
        base.update({"bot_token": "", "chat_id": "", "text": "", "send_image": True, "silent": False})
    elif kind == "ntfy":
        base.update({"server": "https://ntfy.sh", "topic": "", "auth": "none", "token": "", "username": "",
                     "password": "", "title": "", "body": "", "priority": 3, "tags": "", "send_image": True})
    return base


def applies(n, camera, types, mode=None):
    if not n.get("enabled", True):
        return False
    if n.get("modes") and mode not in n["modes"]:
        return False
    if n.get("cameras") and camera not in n["cameras"]:
        return False
    if n.get("types") and not set(n["types"]) & set(types):
        return False
    return True


def build_payload(event):
    return {
        "camera": event["camera"],
        "types": event["types"],
        "message": event["message"],
        "time": event["time"],
        "detections": [{k: d[k] for k in ("label", "confidence", "x1", "y1", "x2", "y2")}
                       for d in event["detections"] if d.get("valid")],
        "image_url": event.get("image_url"),
        "event_id": event.get("event_id"),
        "watch_event": event.get("watch_key"),      # bevakning: arrive, quiet, leave_toward ... annars null
    }


async def send_pushbullet(n, event, jpeg):
    headers = {"Access-Token": n["api_key"]}
    title = render(n.get("title") or "SynoArgus: %kamera%", event)
    body = render(n.get("body") or "%meddelande%", event)
    async with httpx.AsyncClient(timeout=20) as c:
        push = {"title": title, "body": body}
        if n.get("device_iden"):
            push["device_iden"] = n["device_iden"]
        if n.get("send_image", True) and jpeg:
            fname = f"synoargus_{event['camera']}.jpg".replace(" ", "_")
            r = await c.post("https://api.pushbullet.com/v2/upload-request", headers=headers,
                             json={"file_name": fname, "file_type": "image/jpeg"})
            r.raise_for_status()
            up = r.json()
            r = await c.post(up["upload_url"], data=up.get("data") or {},
                             files={"file": (fname, jpeg, "image/jpeg")})
            r.raise_for_status()
            push.update({"type": "file", "file_name": fname, "file_type": "image/jpeg",
                         "file_url": up["file_url"]})
        else:
            push["type"] = "note"
        r = await c.post("https://api.pushbullet.com/v2/pushes", headers=headers, json=push)
        r.raise_for_status()


async def send_webhook(n, event, jpeg):
    method = (n.get("method") or "POST").upper()
    headers = {}
    auth = None
    if n.get("auth") == "bearer" and n.get("token"):
        headers["Authorization"] = f"Bearer {n['token']}"
    elif n.get("auth") == "basic":
        auth = (n.get("username", ""), n.get("password", ""))
    payload = build_payload(event)
    templated = has_placeholders(n["url"])
    url = render(n["url"], event, url=True)
    async with httpx.AsyncClient(timeout=20, verify=n.get("verify_tls", True)) as c:
        if method == "GET":
            params = None if templated else {"camera": payload["camera"], "types": ",".join(payload["types"]),
                                             "message": payload["message"]}
            r = await c.get(url, params=params, headers=headers, auth=auth)
        elif n.get("send_image") and jpeg and method in ("POST", "PUT", "PATCH"):
            r = await c.request(method, url, headers=headers, auth=auth,
                                data={"payload": json.dumps(payload, ensure_ascii=False)},
                                files={"image": ("capture.jpg", jpeg, "image/jpeg")})
        else:
            r = await c.request(method, url, headers=headers, auth=auth, json=payload)
        r.raise_for_status()


def _mqtt_publish(n, topic, payload):
    import paho.mqtt.publish as publish
    auth = None
    if n.get("username"):
        auth = {"username": n["username"], "password": n.get("password") or None}
    publish.single(topic, payload=payload, qos=int(n.get("qos", 0)), retain=bool(n.get("retain")),
                   hostname=n["host"], port=int(n.get("port") or 1883), auth=auth,
                   client_id=f"synoargus-{uuid.uuid4().hex[:6]}", keepalive=30)


async def send_mqtt(n, event, jpeg):
    payload = build_payload(event)
    if n.get("send_image") and jpeg:
        payload["image"] = base64.b64encode(jpeg).decode()
    base = (n.get("base_topic") or "synoargus").strip("/")
    cam = event["camera"].replace("/", "_").replace("+", "_").replace("#", "_")
    topic = f"{base}/{cam}/notification"
    await asyncio.wait_for(asyncio.to_thread(
        _mqtt_publish, n, topic, json.dumps(payload, ensure_ascii=False)), timeout=20)


def _send_email(n, subject, body, jpeg):
    import smtplib
    import ssl
    from email.message import EmailMessage
    to = [a.strip() for a in (n.get("to") or "").replace(";", ",").split(",") if a.strip()]
    if not to:
        raise ValueError("Ingen mottagare / no recipient")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = n.get("from_addr") or n.get("username")
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    if jpeg and n.get("send_image", True):
        msg.add_attachment(jpeg, maintype="image", subtype="jpeg", filename="synoargus.jpg")
    sec = n.get("security") or "starttls"
    port = int(n.get("port") or (465 if sec == "ssl" else 587))
    ctx = ssl.create_default_context()
    if sec == "ssl":
        server = smtplib.SMTP_SSL(n["host"], port, context=ctx, timeout=20)
    else:
        server = smtplib.SMTP(n["host"], port, timeout=20)
    with server:
        if sec == "starttls":
            server.starttls(context=ctx)
        if n.get("username"):
            server.login(n["username"], n.get("password") or "")
        server.send_message(msg)


async def send_email(n, event, jpeg):
    subject = render(n.get("subject") or "SynoArgus: %kamera%", event)
    body = render(n.get("body") or "%meddelande%\n%datum% %tid%\n%bild%", event).rstrip()
    await asyncio.wait_for(asyncio.to_thread(_send_email, n, subject, body, jpeg), timeout=40)


async def send_telegram(n, event, jpeg):
    base = f"https://api.telegram.org/bot{n['bot_token']}"
    text = render(n.get("text") or "%meddelande%", event)
    silent = bool(n.get("silent"))
    async with httpx.AsyncClient(timeout=30) as c:
        if n.get("send_image", True) and jpeg:
            r = await c.post(base + "/sendPhoto",
                             data={"chat_id": n["chat_id"], "caption": text[:1024],
                                   "disable_notification": str(silent).lower()},
                             files={"photo": ("synoargus.jpg", jpeg, "image/jpeg")})
        else:
            r = await c.post(base + "/sendMessage", json={"chat_id": n["chat_id"], "text": text[:4096],
                                                          "disable_notification": silent})
        if r.status_code >= 400:
            try:
                desc = r.json().get("description")
            except Exception:
                desc = r.text[:200]
            raise RuntimeError(f"Telegram {r.status_code}: {desc}")


def _hdr(value):
    """HTTP-huvuden måste vara ASCII; ntfy förstår RFC 2047-kodning."""
    try:
        value.encode("ascii")
        return value
    except UnicodeEncodeError:
        return "=?UTF-8?B?" + base64.b64encode(value.encode()).decode() + "?="


async def send_ntfy(n, event, jpeg):
    server = (n.get("server") or "https://ntfy.sh").rstrip("/")
    topic = (n.get("topic") or "").strip("/")
    if not topic:
        raise ValueError("Inget ämne (topic)")
    headers = {}
    auth = None
    if n.get("auth") == "token" and n.get("token"):
        headers["Authorization"] = f"Bearer {n['token']}"
    elif n.get("auth") == "basic":
        auth = (n.get("username", ""), n.get("password", ""))
    title = render(n.get("title") or "SynoArgus: %kamera%", event)
    body = render(n.get("body") or "%meddelande%", event)
    prio = max(1, min(5, int(n.get("priority") or 3)))
    tags = [t.strip() for t in (n.get("tags") or "").split(",") if t.strip()]
    async with httpx.AsyncClient(timeout=30) as c:
        if n.get("send_image", True) and jpeg:
            headers.update({"Title": _hdr(title), "Message": _hdr(body), "Priority": str(prio),
                            "Filename": "synoargus.jpg"})
            if tags:
                headers["Tags"] = _hdr(",".join(tags))
            if event.get("image_url"):
                headers["Click"] = event["image_url"]
            r = await c.put(f"{server}/{topic}", content=jpeg, headers=headers, auth=auth)
        else:
            payload = {"topic": topic, "title": title, "message": body, "priority": prio}
            if tags:
                payload["tags"] = tags
            if event.get("image_url"):
                payload["click"] = event["image_url"]
            r = await c.post(server, json=payload, headers=headers, auth=auth)
        r.raise_for_status()


SENDERS = {"pushbullet": send_pushbullet, "webhook": send_webhook, "mqtt": send_mqtt,
           "email": send_email, "telegram": send_telegram, "ntfy": send_ntfy}


async def send(n, event, jpeg):
    """Skickar till en notifierare. Returnerar (ok, felmeddelande)."""
    try:
        await SENDERS[n["type"]](n, event, jpeg)
        return True, None
    except httpx.HTTPStatusError as e:
        msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
    log.warning("Notifierare %s (%s) misslyckades: %s", n.get("name") or n["id"], n["type"], msg)
    return False, msg
