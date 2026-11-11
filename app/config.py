"""Inställningar: läses och sparas som /data/config.json."""
import json
import logging
import os
import secrets
import threading
from copy import deepcopy

DATA_DIR = os.environ.get("SYNOARGUS_DATA", "/data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
CAPTURE_DIR = os.path.join(DATA_DIR, "captures")
DB_PATH = os.path.join(DATA_DIR, "history.db")
MODEL_DIR = os.environ.get("SYNOARGUS_MODELS", "/models")          # inbyggda modeller (i imagen)
USER_MODEL_DIR = os.path.join(DATA_DIR, "models")                   # egna modeller (konverteraren)
DEFAULT_MODEL = "yolox_s"
GITHUB_REPO = os.environ.get("SYNOARGUS_REPO", "mostlyflawles/synoargus")

# Typer som modellen kan (COCO). Vi visar de vanligaste först i gränssnittet.
COMMON_TYPES = ["person", "car", "truck", "bus", "bicycle", "motorcycle", "cat", "dog", "bird"]

TYPE_NAMES_SV = {
    "person": "Person", "car": "Bil", "truck": "Lastbil", "bus": "Buss", "bicycle": "Cykel",
    "motorcycle": "Motorcykel", "cat": "Katt", "dog": "Hund", "bird": "Fågel", "horse": "Häst",
    "sheep": "Får", "cow": "Ko", "bear": "Björn", "backpack": "Ryggsäck", "handbag": "Handväska",
    "suitcase": "Resväska", "umbrella": "Paraply", "boat": "Båt",
}

PLURAL_SV = {
    "person": "personer", "car": "bilar", "truck": "lastbilar", "bus": "bussar", "bicycle": "cyklar",
    "motorcycle": "motorcyklar", "cat": "katter", "dog": "hundar", "bird": "fåglar", "horse": "hästar",
    "sheep": "får", "cow": "kor", "bear": "björnar", "backpack": "ryggsäckar", "handbag": "handväskor",
    "suitcase": "resväskor", "umbrella": "paraplyer", "boat": "båtar",
}
PLURAL_EN = {"person": "people", "bus": "buses", "sheep": "sheep", "knife": "knives"}


def type_name(label, lang="sv"):
    if lang == "en":
        return label[:1].upper() + label[1:]
    return TYPE_NAMES_SV.get(label, label)


def type_count(label, n, lang="sv"):
    """'Person', '2 personer' / 'Person', '2 people'."""
    if n <= 1:
        return type_name(label, lang)
    if lang == "en":
        return f"{n} {PLURAL_EN.get(label, label + 's')}"
    return f"{n} {PLURAL_SV.get(label, type_name(label, lang).lower())}"

DEFAULTS = {
    "setup_done": False,
    "language": "sv",         # sv | en
    "timezone": os.environ.get("TZ") or "UTC",
    "secret": None,           # signerar inloggningscookies
    "trigger_token": None,    # skyddar /api/trigger
    "synology": {
        "url": "",            # t.ex. http://192.168.1.10:5000
        "user": "",
        "password": "",
        "verify_tls": False,
        "quality": "balanced",  # high | balanced | low
    },
    "auth": {
        "dsm_login": True,      # logga in med DSM-konto (användarnamn/lösenord)
        "allowed_users": [],    # tom lista = alla DSM-konton som kan logga in
        "sso": {
            "enabled": False,
            "issuer": "",       # t.ex. https://192.168.1.10:5001/webman/sso
            "client_id": "",
            "client_secret": "",
            "redirect_url": "", # t.ex. http://192.168.1.10:8686/auth/sso/callback
        },
    },
    "detector": {
        "model": DEFAULT_MODEL, # mappnamn under /models eller /data/models
        "device": "AUTO",       # AUTO | CPU | GPU
    },
    "defaults": {
        "threshold": 50,
        "min_width": 40,
        "min_height": 40,
        "cooldown_s": 60,       # tystnad efter skickat larm
        "delay_s": 5,           # minsta tid mellan två analyser
        "max_snapshots": 2,
        "snapshot_interval_ms": 700,
    },
    "storage": {
        "days_to_keep": 14,
        "max_mb": 2000,         # högst så många MB bilder (0 = ingen gräns); det som inträffar först gäller
        "save_empty": False,    # spara även analyser utan träff
    },
    "public_url": "",           # adress till SynoArgus, används i länkar i larm
    # Lägen: namn "" = standardnamn (Hemma/Natt/Borta) på valt språk
    "modes": [{"id": "home", "name": ""}, {"id": "night", "name": ""}, {"id": "away", "name": ""}],
    "mode": {"current": "away", "source": "default", "since": 0},
    "mode_auto": {
        "homemode": {"enabled": False, "on": "home", "off": "away"},  # följ Home Mode i Surveillance Station
        "schedule": [],             # [{"time": "23:00", "days": [0..6], "mode": "night"}] (0 = måndag)
    },
    "cameras": {},              # namn -> kamerainställningar, se camera_defaults()
    "watches": {},              # kameranamn -> bevakning, se watch.defaults()
    "notifiers": [],            # lista med notifierare
}


def camera_defaults(name, ss_id=None):
    return {
        "name": name,
        "ss_id": ss_id,
        "enabled": True,
        "types": ["person"],
        "threshold": None,      # None = standardvärde
        "min_width": None,
        "min_height": None,
        "cooldown_s": None,
        "delay_s": None,
        "max_snapshots": None,
        "wait_ms": 0,
        "zones": [],            # [{x1,y1,x2,y2 (0-1), mode: contains|intersect}]
        "modes": [],            # lägen där kameran larmar, tom = alla
        "stream_url": "",       # Översikt: egen adress till videoströmmen (tom = från Surveillance Station)
    }


def _merge(base, extra):
    out = deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in ("cameras", "watches"):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self):
        self._lock = threading.RLock()
        self.data = deepcopy(DEFAULTS)
        self.load()

    def load(self):
        with self._lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            os.makedirs(CAPTURE_DIR, exist_ok=True)
            os.makedirs(USER_MODEL_DIR, exist_ok=True)
            for path in (CONFIG_PATH, CONFIG_PATH + ".bak"):
                if not os.path.exists(path):
                    continue
                try:
                    with open(path, encoding="utf-8") as f:
                        self.data = _merge(DEFAULTS, json.load(f))
                    if path != CONFIG_PATH:
                        logging.getLogger("synoargus").warning("config.json gick inte att läsa – använder reservkopian")
                    break
                except (ValueError, OSError) as e:
                    logging.getLogger("synoargus").error("Kunde inte läsa %s: %s", path, e)
            changed = False
            if not self.data.get("secret"):
                self.data["secret"] = secrets.token_hex(32)
                changed = True
            if not self.data.get("trigger_token"):
                self.data["trigger_token"] = secrets.token_urlsafe(16)
                changed = True
            if changed:
                self.save()

    def save(self):
        with self._lock:
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            try:
                os.chmod(tmp, 0o600)
                if os.path.exists(CONFIG_PATH):
                    os.replace(CONFIG_PATH, CONFIG_PATH + ".bak")   # föregående version som reserv
            except OSError:
                pass
            os.replace(tmp, CONFIG_PATH)

    def get(self, *path, default=None):
        with self._lock:
            cur = self.data
            for p in path:
                if not isinstance(cur, dict) or p not in cur:
                    return default
                cur = cur[p]
            return deepcopy(cur)

    def update(self, fn):
        """Kör fn(data) under lås och spara."""
        with self._lock:
            fn(self.data)
            self.save()

    def cam_setting(self, cam, key):
        v = cam.get(key)
        if v is None:
            return self.get("defaults", key)
        return v


config = Config()
