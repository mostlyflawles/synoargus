"""Filtrering av träffar (typ, säkerhet, storlek, zoner) och ritning av rutor."""
import io
import os

from PIL import Image, ImageDraw, ImageFont

from .config import TYPE_NAMES_SV


def in_zone(det, zone, w, h, ignore_all=False):
    """Är träffen innanför en uteslutningszon? Zonens koordinater är 0-1."""
    zx1, zy1 = min(zone["x1"], zone["x2"]) * w, min(zone["y1"], zone["y2"]) * h
    zx2, zy2 = max(zone["x1"], zone["x2"]) * w, max(zone["y1"], zone["y2"]) * h
    if zone.get("mode") == "intersect":
        return det["x1"] < zx2 and det["x2"] > zx1 and det["y1"] < zy2 and det["y2"] > zy1
    return det["x1"] >= zx1 and det["x2"] <= zx2 and det["y1"] >= zy1 and det["y2"] <= zy2


def evaluate(dets, types, threshold, min_w, min_h, zones, w, h):
    """Markerar varje träff med valid/reason. Returnerar (alla, giltiga)."""
    types = {t.lower() for t in types}
    out = []
    for d in dets:
        d = dict(d)
        reason = None
        if d["label"] not in types:
            reason = "typ"
        elif d["confidence"] < threshold:
            reason = "säkerhet"
        elif (d["x2"] - d["x1"]) < min_w or (d["y2"] - d["y1"]) < min_h:
            reason = "storlek"
        elif any(in_zone(d, z, w, h) for z in zones or []):
            reason = "zon"
        d["valid"] = reason is None
        d["reason"] = reason
        out.append(d)
    return out, [d for d in out if d["valid"]]


_FONTS = {}


def _font(size):
    if size not in _FONTS:
        font = None
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if os.path.exists(p):
                font = ImageFont.truetype(p, size)
                break
        if font is None:
            try:
                font = ImageFont.load_default(size=size)
            except TypeError:
                font = ImageFont.load_default()
        _FONTS[size] = font
    return _FONTS[size]


def draw(img, dets, zones=None, draw_all=False):
    """Ritar rutor runt giltiga träffar (och ev. övriga + zoner). Returnerar JPEG-bytes."""
    im = img.copy()
    d = ImageDraw.Draw(im)
    w, h = im.size
    lw = max(2, round(w / 400))
    font = _font(max(12, round(w / 55)))
    for z in zones or []:
        d.rectangle([min(z["x1"], z["x2"]) * w, min(z["y1"], z["y2"]) * h,
                     max(z["x1"], z["x2"]) * w, max(z["y1"], z["y2"]) * h],
                    outline=(80, 200, 120), width=lw)
    for det in dets:
        if not det.get("valid") and not draw_all:
            continue
        color = (255, 59, 48) if det.get("valid") else (160, 160, 160)
        box = [det["x1"], det["y1"], det["x2"], det["y2"]]
        d.rectangle(box, outline=color, width=lw)
        text = f"{TYPE_NAMES_SV.get(det['label'], det['label'])} {det['confidence']:.0f}%"
        tb = d.textbbox((0, 0), text, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        ty = det["y1"] - th - 2 * lw if det["y1"] - th - 2 * lw > 0 else det["y1"]
        d.rectangle([det["x1"], ty, det["x1"] + tw + 2 * lw, ty + th + 2 * lw], fill=color)
        d.text((det["x1"] + lw, ty + lw - tb[1]), text, fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()
