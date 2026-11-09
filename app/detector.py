"""Objektdetektering via OpenVINO.

Modeller (OpenVINO IR, .xml + .bin) letas upp i två mappar:
  /models        inbyggda i imagen (YOLOX, Apache 2.0)
  /data/models   egna modeller, t.ex. YOLO26 gjorda med konverteraren
En egen modell med samma namn som en inbyggd vinner.

Två modellfamiljer stöds:
  yolox        YOLOX (Megvii). BGR 0-255, utfyllnad uppe till vänster, rå utdata [1, N, 85].
  ultralytics  YOLOv8/11/26 m.fl. RGB 0-1, centrerad utfyllnad, utdata [1, 84, N] eller [1, N, 6].
Familjen läses från synoargus.json i modellmappen, annars gissas den.
"""
import glob
import json
import logging
import os
import threading
import time

import numpy as np
from PIL import Image

log = logging.getLogger("synoargus.detector")

COCO = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
    "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
    "teddy bear", "hair drier", "toothbrush",
]


def read_meta(path):
    meta = {}
    p = os.path.join(path, "synoargus.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    if "source" in meta:  # äldre infofiler: "source" betydde ursprung
        meta["origin"] = meta.pop("source")
    if "family" not in meta:
        name = os.path.basename(path).lower()
        if name.startswith("yolox"):
            meta["family"] = "yolox"
        else:
            meta["family"] = "ultralytics"
    return meta


def available_models(*dirs):
    """Returnerar {namn: {path, source, family, ...}}. Senare mappar vinner."""
    found = {}
    for i, base in enumerate(dirs):
        for d in sorted(glob.glob(os.path.join(base, "*"))):
            if os.path.isdir(d) and glob.glob(os.path.join(d, "*.xml")):
                meta = read_meta(d)
                found[os.path.basename(d)] = {**meta, "path": d, "source": "builtin" if i == 0 else "user"}
    return found


# ------------------------------------------------------------------ förbehandling

def letterbox(img, size):
    """Ultralytics: skalar om med bibehållna proportioner, centrerat, RGB 0-1."""
    w, h = img.size
    r = min(size / w, size / h)
    nw, nh = int(round(w * r)), int(round(h * r))
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    px, py = (size - nw) // 2, (size - nh) // 2
    canvas.paste(img.resize((nw, nh), Image.BILINEAR), (px, py))
    arr = np.asarray(canvas, dtype=np.float32) / 255.0
    return np.ascontiguousarray(arr.transpose(2, 0, 1)[None]), r, px, py


def yolox_prep(img, size):
    """YOLOX: skalar om, utfyllnad uppe till vänster, BGR 0-255."""
    w, h = img.size
    r = min(size / w, size / h)
    nw, nh = int(w * r), int(h * r)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    canvas.paste(img.resize((nw, nh), Image.BILINEAR), (0, 0))
    arr = np.asarray(canvas, dtype=np.float32)[:, :, ::-1]  # RGB -> BGR
    return np.ascontiguousarray(arr.transpose(2, 0, 1)[None]), r, 0, 0


# ------------------------------------------------------------------ efterbehandling

def nms(boxes, scores, iou=0.5):
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        a = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        b = (boxes[order[1:], 2] - boxes[order[1:], 0]) * (boxes[order[1:], 3] - boxes[order[1:], 1])
        ovr = inter / (a + b - inter + 1e-9)
        order = order[1:][ovr <= iou]
    return keep


def _classwise_nms(boxes, scores, cls):
    keep = []
    for c in np.unique(cls):
        idx = np.where(cls == c)[0]
        keep += list(idx[nms(boxes[idx], scores[idx])])
    return boxes[keep], scores[keep], cls[keep]


def _finish(boxes, scores, cls, r, px, py, w, h):
    dets = []
    for b, s, c in zip(boxes, scores, cls):
        x1 = float(np.clip((b[0] - px) / r, 0, w))
        y1 = float(np.clip((b[1] - py) / r, 0, h))
        x2 = float(np.clip((b[2] - px) / r, 0, w))
        y2 = float(np.clip((b[3] - py) / r, 0, h))
        if x2 - x1 < 1 or y2 - y1 < 1:
            continue
        label = COCO[c] if 0 <= c < len(COCO) else str(c)
        dets.append({"label": label, "confidence": round(float(s) * 100, 1),
                     "x1": round(x1), "y1": round(y1), "x2": round(x2), "y2": round(y2)})
    dets.sort(key=lambda d: -d["confidence"])
    return dets


def decode(out, r, px, py, w, h, min_conf=0.15):
    """Ultralytics: [1, N, 6] (end-to-end) eller [1, 84, N] / [1, N, 84] (kräver NMS)."""
    out = np.asarray(out)
    if out.ndim == 3:
        out = out[0]
    if out.shape[-1] == 6 and out.shape[0] != 6:
        sel = out[out[:, 4] >= min_conf]
        boxes, scores, cls = sel[:, :4].copy(), sel[:, 4], sel[:, 5].astype(int)
    else:
        nc = 4 + len(COCO)
        if out.shape[0] == nc or (out.shape[1] != nc and out.shape[0] < out.shape[1]):
            out = out.T  # -> [N, 84]
        cls_scores = out[:, 4:]
        cls = cls_scores.argmax(1)
        scores = cls_scores[np.arange(len(cls)), cls]
        m = scores >= min_conf
        cx, cy, bw, bh = out[m, 0], out[m, 1], out[m, 2], out[m, 3]
        boxes = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], 1)
        boxes, scores, cls = _classwise_nms(boxes, scores[m], cls[m])
    return _finish(boxes, scores, cls, r, px, py, w, h)


_GRIDS = {}


def _yolox_grids(size):
    if size not in _GRIDS:
        grids, strides = [], []
        for s in (8, 16, 32):
            g = size // s
            yv, xv = np.meshgrid(np.arange(g), np.arange(g), indexing="ij")
            grid = np.stack((xv, yv), 2).reshape(-1, 2)
            grids.append(grid)
            strides.append(np.full((grid.shape[0], 1), s))
        _GRIDS[size] = (np.concatenate(grids).astype(np.float32), np.concatenate(strides).astype(np.float32))
    return _GRIDS[size]


def decode_yolox(out, r, w, h, size, min_conf=0.15, decoded=False):
    """YOLOX: [1, N, 85] = cx,cy,w,h (råa), objektpoäng, 80 klasspoäng."""
    out = np.asarray(out, dtype=np.float32)
    if out.ndim == 3:
        out = out[0]
    if not decoded:
        grids, strides = _yolox_grids(size)
        if grids.shape[0] != out.shape[0]:
            raise RuntimeError(f"YOLOX-utdata har {out.shape[0]} rader, väntade {grids.shape[0]}")
        xy = (out[:, :2] + grids) * strides
        wh = np.exp(np.clip(out[:, 2:4], -10, 10)) * strides
    else:
        xy, wh = out[:, :2], out[:, 2:4]
    scores_all = out[:, 4:5] * out[:, 5:]
    cls = scores_all.argmax(1)
    scores = scores_all[np.arange(len(cls)), cls]
    m = scores >= min_conf
    xy, wh, scores, cls = xy[m], wh[m], scores[m], cls[m]
    boxes = np.concatenate([xy - wh / 2, xy + wh / 2], 1)
    boxes, scores, cls = _classwise_nms(boxes, scores, cls)
    return _finish(boxes, scores, cls, r, 0, 0, w, h)


# ------------------------------------------------------------------ detektorn

class Detector:
    def __init__(self, *model_dirs):
        self.model_dirs = model_dirs
        self._lock = threading.Lock()       # laddning
        self._infer = threading.Lock()      # en analys i taget (OpenVINO-anropet är inte trådsäkert)
        self.compiled = None
        self.loaded = None      # (önskad modell, önskad enhet)
        self.model = None       # modell som faktiskt används
        self.family = None
        self.meta = {}
        self.device = None
        self.size = 640
        self.error = None
        self.warning = None
        self.last_ms = None

    def models(self):
        return available_models(*self.model_dirs)

    def ensure(self, model, device="AUTO", fallback="yolox_s"):
        with self._lock:
            if self.compiled is not None and self.loaded == (model, device):
                return
            import openvino as ov
            models = self.models()
            if not models:
                self.error = "Inga modeller hittades"
                raise RuntimeError(self.error)
            chosen = model
            self.warning = None
            if chosen not in models:
                chosen = fallback if fallback in models else sorted(models)[0]
                self.warning = f"Modellen {model} finns inte, använder {chosen}"
                log.warning(self.warning)
            info = models[chosen]
            core = ov.Core()
            cache = os.path.join(os.environ.get("SYNOARGUS_DATA", "/data"), "ov_cache")
            os.makedirs(cache, exist_ok=True)
            core.set_property({"CACHE_DIR": cache})
            net = core.read_model(glob.glob(os.path.join(info["path"], "*.xml"))[0])
            try:
                self.size = int(net.inputs[0].get_partial_shape()[2].get_length())
            except Exception:
                self.size = 640
            devices = core.available_devices
            wanted = []
            if device == "GPU" or (device == "AUTO" and any(d.startswith("GPU") for d in devices)):
                wanted.append("GPU")
            wanted.append("CPU")
            last = None
            for dev in wanted:
                try:
                    t = time.time()
                    compiled = core.compile_model(net, dev, {"PERFORMANCE_HINT": "LATENCY"})
                    with self._infer:
                        self.compiled = compiled
                        self.model, self.family, self.meta, self.device = chosen, info["family"], info, dev
                    self.loaded = (model, device)
                    self.error = None
                    log.info("Modell %s (%s) laddad på %s (%d px) på %.1f s",
                             chosen, info["family"], dev, self.size, time.time() - t)
                    return
                except Exception as e:  # GPU kan saknas eller vara för gammal
                    last = e
                    log.warning("Kunde inte ladda %s på %s: %s", chosen, dev, e)
            self.error = str(last)
            raise RuntimeError(f"Kunde inte ladda modellen: {last}")

    def detect(self, img):
        """img: PIL.Image (RGB). Returnerar träffar i originalbildens pixlar."""
        with self._infer:
            compiled, size, family, meta = self.compiled, self.size, self.family, self.meta
            if compiled is None:
                raise RuntimeError("Ingen modell är laddad")
            w, h = img.size
            t = time.time()
            if family == "yolox":
                tensor, r, px, py = yolox_prep(img, size)
                out = compiled(tensor)[compiled.outputs[0]]
                dets = decode_yolox(out, r, w, h, size, decoded=bool(meta.get("decoded")))
            else:
                tensor, r, px, py = letterbox(img, size)
                out = compiled(tensor)[compiled.outputs[0]]
                dets = decode(out, r, px, py, w, h)
            self.last_ms = round((time.time() - t) * 1000)
        return dets

    def status(self):
        models = self.models()
        return {
            "model": self.model, "family": self.family, "device": self.device, "size": self.size,
            "last_ms": self.last_ms, "error": self.error, "warning": self.warning,
            "available": [{"name": n, "source": m["source"], "family": m["family"],
                           "license": m.get("license")} for n, m in sorted(models.items())],
        }
