"""Livevideo för Översikt via go2rtc (MIT, https://github.com/AlexxIT/go2rtc).

go2rtc körs som en separat process i containern och lyssnar bara på 127.0.0.1. Den hämtar kamerornas ström
från Surveillance Station (RTSP) och gör om den till fMP4 som webbläsaren spelar med Media Source Extensions.
Webbläsaren pratar aldrig med go2rtc direkt: SynoArgus släpper bara igenom inloggade användare (se main.live_ws).

Ljud: AAC skickas som det är; PCMA/PCMU (G.711, vanligt i IP-kameror) gör go2rtc själv om till FLAC.
"""
import asyncio
import logging
import os
import re
import shutil
import tempfile
import time

import httpx

log = logging.getLogger("synoargus.streams")

API = "http://127.0.0.1:1984"
WS = "ws://127.0.0.1:1984"
REFRESH_S = 600                  # läs om strömadresserna från Surveillance Station så här ofta
CONFIG = """# Skapad av SynoArgus – ändras inte för hand.
api:
  listen: "127.0.0.1:1984"
  origin: ""
rtsp:
  listen: ""
webrtc:
  listen: ""
srtp:
  listen: ""
rtmp:
  listen: ""
log:
  level: warn
streams: {}
"""


def mask(text):
    """Tar bort användarnamn och lösenord ur adresser (rtsp://user:pass@host -> rtsp://***@host)."""
    return re.sub(r"(\w+://)[^/@\s]+@", r"\1***@", str(text or ""))


def stream_name(cam):
    return f"cam{cam.get('ss_id')}" if cam.get("ss_id") is not None else \
        "cam_" + "".join(ch if ch.isalnum() else "_" for ch in cam["name"])


def _with_credentials(url, user, password):
    """Surveillance Stations RTSP-adress saknar ibland inloggning; lägg till SynoArgus konto."""
    if not url or "@" in url.split("//", 1)[-1].split("/", 1)[0] or not user:
        return url
    from urllib.parse import quote
    scheme, rest = url.split("://", 1)
    return f"{scheme}://{quote(user, safe='')}:{quote(password or '', safe='')}@{rest}"


class Streams:
    def __init__(self, cfg, ss):
        self.cfg = cfg
        self.ss = ss
        self.binary = os.environ.get("SYNOARGUS_GO2RTC") or shutil.which("go2rtc")
        self.proc = None
        self.error = None
        self.sources = {}           # stream name -> {"camera", "url", "from"}
        self.raw = None             # senaste svaret från Surveillance Station (för felsökning)
        self._refreshed = 0
        self._lock = asyncio.Lock()
        self._task = None

    @property
    def available(self):
        return bool(self.binary)

    def status(self):
        return {"available": self.available, "running": bool(self.proc and self.proc.returncode is None),
                "error": self.error,
                "sources": {v["camera"]: {"from": v["from"], "url": mask(v["url"])} for v in self.sources.values()}}

    # ---------------------------------------------------------------- processen
    async def start(self):
        if not self.available:
            self.error = "go2rtc saknas"
            return
        self._task = asyncio.create_task(self._supervise())

    async def _supervise(self):
        path = os.path.join(tempfile.gettempdir(), "synoargus-go2rtc.yaml")
        with open(path, "w") as f:
            f.write(CONFIG)
        delay = 2
        while True:
            try:
                self.proc = await asyncio.create_subprocess_exec(
                    self.binary, "-config", path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
                self.error = None
                self.sources = {}           # en ny process känner inte till några strömmar
                self._refreshed = 0
                started = time.time()
                async for line in self.proc.stdout:
                    text = mask(line.decode(errors="replace").strip())
                    if text:
                        log.info("go2rtc: %s", text[:300])
                await self.proc.wait()
                self.error = f"go2rtc avslutades ({self.proc.returncode})"
                log.warning(self.error)
                delay = 2 if time.time() - started > 60 else min(60, delay * 2)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.error = f"go2rtc: {e}"
                log.warning(self.error)
                delay = min(60, delay * 2)
            await asyncio.sleep(delay)

    async def stop(self):
        if self._task:
            self._task.cancel()
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()

    # ---------------------------------------------------------------- strömmar
    def refresh_soon(self):
        self._refreshed = 0
    async def ensure(self, force=False):
        """Ser till att varje kamera finns som ström i go2rtc. Returnerar {kameranamn: strömnamn}."""
        cams = self.cfg.get("cameras") or {}
        async with self._lock:
            if force or time.time() - self._refreshed > REFRESH_S or not self.sources:
                await self._refresh(cams)
        return {v["camera"]: k for k, v in self.sources.items()}

    async def _refresh(self, cams):
        syn = self.cfg.get("synology") or {}
        ids = [c["ss_id"] for c in cams.values() if c.get("ss_id") is not None]
        paths = {}
        if ids:
            try:
                paths, self.raw = await self.ss.live_paths(ids)
            except Exception as e:
                self.raw = {"error": str(e)}
                log.warning("Strömadresser från Surveillance Station: %s", e)
        wanted = {}
        for cam in cams.values():
            url, source = (cam.get("stream_url") or "").strip(), "manual"
            if not url:
                p = paths.get(cam.get("ss_id")) or {}
                url, source = p.get("rtspPath") or "", "ss"
                url = _with_credentials(url, syn.get("user"), syn.get("password"))
            if url:
                wanted[stream_name(cam)] = {"camera": cam["name"], "url": url, "from": source}
        async with httpx.AsyncClient(timeout=5) as c:
            for name, s in wanted.items():
                if self.sources.get(name, {}).get("url") == s["url"]:
                    continue
                try:
                    r = await c.put(API + "/api/streams", params={"name": name, "src": s["url"]})
                    if r.status_code >= 400:
                        raise RuntimeError(f"HTTP {r.status_code}")
                except Exception as e:
                    self.error = f"go2rtc: {mask(e)}"
                    log.warning("go2rtc, ström %s: %s", s["camera"], mask(e))
                    continue
            for name in set(self.sources) - set(wanted):
                try:
                    await c.delete(API + "/api/streams", params={"src": name})
                except Exception:
                    pass
        self.sources = wanted
        self._refreshed = time.time()
