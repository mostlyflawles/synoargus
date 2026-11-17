"""Läser hur en mp4-fil är uppbyggd: hur lång den säger att den är, var innehållsförteckningen (moov) ligger och om
det finns skräp efter sista riktiga delen. Surveillance Station kan skicka filer där bara början är riktig video och
resten är nollor; de upptäcks här och nollorna kan skäras bort.
"""
import os
import struct

_OK = set(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ")


def _valid_type(t):
    return len(t) == 4 and all(ch in _OK for ch in t) and t.strip(b" ")


def _mvhd_duration(moov):
    """Längden i sekunder ur mvhd inne i moov (bytes), eller None."""
    i = 0
    while i + 8 <= len(moov):
        size, typ = struct.unpack(">I4s", moov[i:i + 8])
        if size < 8:
            return None
        if typ == b"mvhd":
            body = moov[i + 8:i + size]
            if len(body) < 20:
                return None
            if body[0] == 1:
                if len(body) < 32:
                    return None
                scale, dur = struct.unpack(">IQ", body[20:32])
            else:
                scale, dur = struct.unpack(">II", body[12:20])
            return round(dur / scale, 3) if scale else None
        i += size
    return None


def inspect(path, partial=False):
    """{size, valid_end, trailing, duration_s, mdat_bytes, moov_at, complete}.

    partial=True: filen är bara början av en längre fil (den sista delen får sluta mitt i)."""
    size = os.path.getsize(path)
    info = {"size": size, "valid_end": 0, "trailing": 0, "duration_s": None, "mdat_bytes": 0, "moov_at": None,
            "complete": False}
    with open(path, "rb") as f:
        pos = 0
        while pos + 8 <= size:
            f.seek(pos)
            hdr = f.read(16)
            box, typ = struct.unpack(">I4s", hdr[:8])
            head = 8
            if box == 1 and len(hdr) >= 16:
                box, head = struct.unpack(">Q", hdr[8:16])[0], 16
            elif box == 0 and _valid_type(typ):
                box = size - pos                    # sträcker sig till slutet av filen
            if not _valid_type(typ) or box < head:
                break                               # inte en riktig del: resten är skräp
            if pos + box > size and not partial:
                break
            if typ == b"moov":
                info["moov_at"] = "start" if info["mdat_bytes"] == 0 else "end"
                f.seek(pos + head)
                info["duration_s"] = _mvhd_duration(f.read(min(box - head, 4 << 20)))
            elif typ == b"mdat":
                info["mdat_bytes"] += min(box, size - pos) - head
            pos += box
            info["valid_end"] = min(pos, size)
        info["trailing"] = max(0, size - info["valid_end"]) if pos < size else 0
    info["complete"] = info["duration_s"] is not None and info["trailing"] == 0 and info["valid_end"] == size
    return info


def trim(path, info=None):
    """Skär bort skräp efter sista riktiga delen. Returnerar antal borttagna byte."""
    info = info or inspect(path)
    if info["trailing"] and info["duration_s"] is not None and info["valid_end"] > 0:
        os.truncate(path, info["valid_end"])
        return info["trailing"]
    return 0


def is_short(info, expected_s):
    """Sant om filen säger sig vara mycket kortare än den bit som begärdes."""
    d = info.get("duration_s")
    return d is not None and expected_s >= 10 and d < expected_s * 0.5
