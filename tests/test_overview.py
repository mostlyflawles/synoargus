"""Översikt: go2rtc streams (addresses, credentials, masking), the timeline, recording lookup and the request language."""
import asyncio, json, os, time, types
import _env; HERE = _env.setup()
os.environ["SYNOARGUS_DATA"] = os.path.join(HERE, "data"); os.environ["SYNOARGUS_MODELS"] = os.path.join(HERE, "models")
import httpx
from app import main, auth, storage, streams as S, i18n
from app.config import config, camera_defaults

storage.init()
config.update(lambda d: (d.__setitem__("setup_done", True), d["auth"].__setitem__("allowed_users", ["anna"]),
                         d["synology"].update({"user": "svc", "password": "p@ss"}),
                         d.__setitem__("cameras", {"Yard": camera_defaults("Yard", 5), "Hall": camera_defaults("Hall", 7)})))
class Req:
    cookies = {auth.SESSION_COOKIE: auth.make_session(config.get("secret"), "anna", "dsm")}
    client = types.SimpleNamespace(host="192.168.1.5"); headers = {}; url = types.SimpleNamespace(scheme="http", netloc="nas:8686")
R = Req(); run = asyncio.run

# ---- masking and credentials
assert S.mask("rtsp://u:secret@10.0.0.2:554/x") == "rtsp://***@10.0.0.2:554/x"
assert S.mask("go2rtc: dial rtsp://a:b@h/x failed") == "go2rtc: dial rtsp://***@h/x failed"
assert S._with_credentials("rtsp://10.0.0.2:554/x", "svc", "p@ss") == "rtsp://svc:p%40ss@10.0.0.2:554/x"
assert S._with_credentials("rtsp://a:b@10.0.0.2/x", "svc", "p") == "rtsp://a:b@10.0.0.2/x"
assert S.stream_name({"name": "Yard", "ss_id": 5}) == "cam5" and S.stream_name({"name": "A b", "ss_id": None}) == "cam_A_b"
assert S.mask('cameraId=1&StmKey=\\"0123456789abcdef\\"') == 'cameraId=1&StmKey=\\"***\\"'
assert S.mask("rtsp.cgi?Sms=1.unicast&StmKey=0123456789abcdef") == "rtsp.cgi?Sms=1.unicast&StmKey=***"
print("A mask OK")

# ---- recordings without start/stop (only file names), as some Surveillance Station versions answer
from app.synology import parse_recordings
t0 = 1794388911.527
thin = [{"cameraId": 1, "id": 2, "filePath": "20261111AM/OutDoor1-Public-20261111-105152-1794390712421-7.mp4"},
        {"cameraId": 1, "id": 1, "filePath": "20261111AM/OutDoor1-Public-20261111-102151-1794388911527-7.mp4"},
        {"cameraId": 5, "id": 3, "filePath": "x/Cam-20261111-100000-1794387600000-1.mp4"},
        {"cameraId": 5, "id": 4, "startTime": 1794389000, "stopTime": 1794389060},
        {"cameraId": 7, "id": 5, "filePath": "nothing-useful.mp4"},
        {"cameraId": 8, "id": 6, "filePath": "In-20261111-090000-1794384000000-2.mp4"}]
p = parse_recordings(thin, now=t0 + 2400)
by = {r["id"]: r for r in p}
assert set(by) == {1, 2, 3, 4, 6}, p
assert by[1]["start"] == t0 and by[1]["stop"] == 1794390712.421           # up to the next file
assert by[2]["stop"] == t0 + 2400                                          # the latest: until now
assert by[3]["stop"] == 1794389000                                         # up to the next one of the same camera
assert by[6]["stop"] == 1794384000 + 1800 * 1.05                           # alone: a normal length at most
assert by[4]["stop"] == 1794389060 and not by[4].get("estimated")          # real times are kept
assert [r["start"] for r in p] == sorted(r["start"] for r in p)
print("A2 recordings from file names OK")

# ---- ensure: SS address with credentials, a manual address, no repeated PUTs, removal
class FakeSS:
    calls = 0
    async def live_paths(self, ids):
        FakeSS.calls += 1
        return {5: {"id": 5, "rtspPath": "rtsp://192.168.1.2:554/Sms=5.unicast"}, 7: {"id": 7, "rtspPath": ""}}, {"raw": 1}
st = S.Streams(config, FakeSS())
async def flow():
    httpx.CALLS.clear()
    names = await st.ensure()
    assert names == {"Yard": "cam5"}, names                       # Hall has no address
    put = [c for c in httpx.CALLS if c["method"] == "PUT"]
    assert len(put) == 1 and put[0]["params"] == {"name": "cam5", "src": "rtsp://svc:p%40ss@192.168.1.2:554/Sms=5.unicast"}, put
    assert "p%40ss" not in json.dumps(st.status()) and st.status()["sources"]["Yard"]["from"] == "ss"
    assert st.error is None
    httpx.CALLS.clear(); await st.ensure(); assert not httpx.CALLS and FakeSS.calls == 1   # cached
    config.update(lambda d: d["cameras"]["Hall"].__setitem__("stream_url", "rtsp://cam:pw@192.168.1.30/live"))
    st.refresh_soon(); await st.ensure()
    put = [c["params"]["name"] for c in httpx.CALLS if c["method"] == "PUT"]
    assert put == ["cam7"], httpx.CALLS                           # only the new one is sent again
    assert st.status()["sources"]["Hall"] == {"from": "manual", "url": "rtsp://***@192.168.1.30/live", "error": None}
    # go2rtc refuses one stream: the error is shown for that camera, retried next time and cleared when it works
    bad = httpx.Response(400, {}); bad.text = "bad source"; httpx.RESPONSES.append(bad)
    config.update(lambda d: d["cameras"]["Hall"].__setitem__("stream_url", "rtsp://cam:pw@192.168.1.30/live3"))
    st.refresh_soon(); await st.ensure()
    assert st.status()["sources"]["Hall"]["error"].startswith("go2rtc: HTTP 400") and "Hall" in st.error, st.status()
    httpx.CALLS.clear(); st.refresh_soon(); await st.ensure()
    assert [c["params"]["name"] for c in httpx.CALLS if c["method"] == "PUT"] == ["cam7"] and st.error is None, st.status()
    # go2rtc creates the stream but fails to save its config file (HTTP 400 yaml …): not an error if the stream exists
    yaml_err = httpx.Response(400, {}); yaml_err.text = "yaml: line 1: did not find expected key"
    listing = httpx.Response(200, {"cam7": {"producers": []}, "cam5": {}})
    httpx.RESPONSES.extend([yaml_err, listing])
    config.update(lambda d: d["cameras"]["Hall"].__setitem__("stream_url", "rtsp://cam:pw@192.168.1.30/live4"))
    st.refresh_soon(); await st.ensure()
    assert st.status()["sources"]["Hall"]["error"] is None and st.error is None, st.status()
    assert "streams: {}" not in S.CONFIG and not S.CONFIG.lstrip().startswith("#")
    config.update(lambda d: d["cameras"].pop("Yard"))
    httpx.CALLS.clear(); await st.ensure(force=True)
    assert [(c["method"], c["params"]) for c in httpx.CALLS] == [("DELETE", {"src": "cam5"})], httpx.CALLS
    config.update(lambda d: d["cameras"].__setitem__("Yard", camera_defaults("Yard", 5)))
run(flow())
print("B streams OK")

# ---- the camera field: saved, masked in the export, a masked value keeps the old one
run(main.put_camera("Hall", R, {"stream_url": "rtsp://cam:pw@192.168.1.30/live2"}))
assert config.get("cameras")["Hall"]["stream_url"].endswith("/live2")
run(main.put_camera("Hall", R, {"stream_url": "********"}))
assert config.get("cameras")["Hall"]["stream_url"].endswith("/live2")
exp = json.loads(run(main.export_settings(R, secrets=0)).body)
assert exp["cameras"]["Hall"]["stream_url"] == "********"
try: run(main.put_camera("Hall", R, {"stream_url": "file:///etc/passwd"})); raise SystemExit("bad url accepted")
except main.HTTPException as e: assert e.status_code == 400
print("C camera field OK")

# ---- timeline and recording lookup
now = time.time()
recs = [{"id": 11, "cam": 5, "start": now - 3600, "stop": now - 3000, "reason": 1},
        {"id": 12, "cam": 5, "start": now - 1200, "stop": now - 600, "reason": 2},
        {"id": 13, "cam": 99, "start": now - 1200, "stop": now - 600, "reason": 2}]
async def fake_recordings(ids, start, end, limit=1000):
    return [r for r in recs if r["cam"] in ids], {"raw": True}
main.ss.recordings = fake_recordings
eid, _ = storage.save_event("Yard", True, ["person"], [], b"\xff\xd8x", 50)
tl = run(main.overview_timeline(R, start=now - 7200, end=now + 10, cam=""))
assert [(r["camera"], r["start"]) for r in tl["recordings"]] == [("Yard", now - 3600), ("Yard", now - 1200)], tl
assert tl["events"] and tl["events"][-1]["id"] == eid and tl["error"] is None
ov = run(main.overview(R)); assert ov["last_event"]["id"] == eid and {c["name"] for c in ov["cameras"]} == {"Yard", "Hall"}
r = run(main.overview_recording(R, cam="Yard", t=now - 1000, length=120, check=1))
assert abs(r["start"] - (now - 1000)) < 0.01 and r["stop"] == now - 600, r
gap = run(main.overview_recording(R, cam="Yard", t=now - 2000, length=120, check=1))
assert gap["found"] is False and gap["next"] == now - 1200, gap
gap = run(main.overview_recording(R, cam="Yard", t=now - 2000, length=120, check=0))
assert gap.status_code == 404
assert tl["events"][-1]["image"]
nx = run(main.overview_recording(R, cam="Yard", t=now - 3500, length=120, check=1))
assert nx["found"] and nx["next"] == now - 1200 and nx["ongoing"] is False, nx
print("D timeline OK")

# ---- playback log in the raw data, and streaming the recording
OPENS = []
class FakeResp:
    headers = {"content-type": "video/mpeg4"}
    async def aiter_bytes(self):
        yield b"a" * 1000; yield b"b" * 500
    async def aclose(self): pass
async def fake_open(rec_id, off, play):
    OPENS.append((rec_id, off, play)); await asyncio.sleep(0.05); return FakeResp()
main.ss.open_recording = fake_open
class RangeReq(Req):
    def __init__(self, rng=None): self.headers = {"range": rng} if rng else {}
async def get(rng=None):
    return await main.overview_recording(RangeReq(rng), cam="Yard", t=now - 1000, length=60, check=0)
# the browser asks several times at once: Surveillance Station is asked once, the part comes from the temporary file
async def many():
    return await asyncio.gather(get(), get("bytes=0-99"), get("bytes=1400-"), get("bytes=-10"))
full, first, tail, last10 = run(many())
assert len(OPENS) == 1 and OPENS[0][2] == 60000, OPENS
assert full.status_code == 200 and full.body == b"a" * 1000 + b"b" * 500 and full.headers["Accept-Ranges"] == "bytes"
assert full.media_type == "video/mp4"                                            # not SS's "video/mpeg4"
assert first.status_code == 206 and first.body == b"a" * 100 and first.headers["Content-Range"] == "bytes 0-99/1500"
assert tail.status_code == 206 and tail.body == b"b" * 100 and tail.headers["Content-Range"] == "bytes 1400-1499/1500"
assert last10.status_code == 206 and last10.body == b"b" * 10
assert run(get("bytes=5000-")).status_code == 416
assert len(OPENS) == 1
st = [p["status"] for p in list(main.PLAYBACKS)[-5:]]
assert st.count("fetched") == 1 and st.count("cached") == 4, st
pb = main.PLAYBACKS[-1]
assert pb["recording"] == 12 and pb["camera"] == "Yard" and pb["bytes"] == 1500, pb
# old temporary files are removed
cdir = main.REC_CACHE_DIR; files = os.listdir(cdir); assert len(files) == 1
old = os.path.join(cdir, files[0]); os.utime(old, (time.time() - 3600, time.time() - 3600))
main._rec_cache_clean(); assert not os.listdir(cdir)
raw = run(main.overview_raw(R))
assert raw["playbacks"][0]["recording"] == 12 and "recordings_parsed" in raw
print("D2 playback log OK")

# ---- mp4 parts: Surveillance Station sometimes sends only the first second and pads with zeros
import struct
from app import mp4info
def box(t, body): return struct.pack(">I4s", 8 + len(body), t) + body
def mp4(seconds, pad=0, moov_first=False):
    mvhd = box(b"mvhd", bytes(12) + struct.pack(">II", 1000, int(seconds * 1000)) + bytes(80))
    moov, mdat = box(b"moov", mvhd), box(b"mdat", b"v" * int(seconds * 100))
    head = box(b"ftyp", b"isom" + bytes(4))
    return head + (moov + mdat if moov_first else mdat + moov) + bytes(pad)
p_ = os.path.join(main.REC_CACHE_DIR, "x.mp4"); os.makedirs(main.REC_CACHE_DIR, exist_ok=True)
open(p_, "wb").write(mp4(1.04, pad=5000))
i = mp4info.inspect(p_)
assert i["duration_s"] == 1.04 and i["trailing"] == 5000 and i["moov_at"] == "end" and mp4info.is_short(i, 60), i
assert mp4info.trim(p_, i) == 5000 and mp4info.inspect(p_)["complete"]
open(p_, "wb").write(mp4(60))
assert not mp4info.is_short(mp4info.inspect(p_), 60) and mp4info.trim(p_) == 0
open(p_, "wb").write(mp4(1800, moov_first=True)[:400])              # only the beginning of a whole file
i = mp4info.inspect(p_, partial=True); assert i["duration_s"] == 1800 and i["moov_at"] == "start", i
open(p_, "wb").write(b"a" * 1500); assert mp4info.trim(p_) == 0 and os.path.getsize(p_) == 1500   # unknown: left alone
os.remove(p_)

class MP4Resp:
    headers = {"content-type": "video/mpeg4"}
    def __init__(self, data): self.data = data
    async def aiter_bytes(self):
        for i in range(0, len(self.data), 4096): yield self.data[i:i + 4096]
    async def aclose(self): pass
OPENS.clear()
async def ss_absolute(rec_id, off, play):         # treats playTimeMs as the end point
    OPENS.append((off, play))
    if off and play is not None and play <= off: return MP4Resp(mp4(1.0, pad=20000))
    return MP4Resp(mp4(60))
main.ss.open_recording = ss_absolute
main.REC_MODE["mode"] = None
for f in os.listdir(main.REC_CACHE_DIR): os.remove(os.path.join(main.REC_CACHE_DIR, f))
recs.append({"id": 20, "cam": 5, "start": now - 5000, "stop": now - 3700, "reason": 1})
res = run(main.overview_recording(RangeReq(), cam="Yard", t=now - 4400, length=60, check=0))
pb = main.PLAYBACKS[-1]
assert main.REC_MODE["mode"] == "absolute" and pb["short"] is False and pb["duration_s"] == 60, pb
assert OPENS == [(600000, 60000), (600000, 660000)], OPENS
assert mp4info.inspect(os.path.join(main.REC_CACHE_DIR, os.listdir(main.REC_CACHE_DIR)[0]))["duration_s"] == 60
run(main.overview_recording(RangeReq(), cam="Yard", t=now - 4300, length=60, check=0))
assert OPENS[-1] == (700000, 760000) and len(OPENS) == 3            # the learnt way is used directly
# the end of a recording is not a broken part
res = run(main.overview_recording(RangeReq(), cam="Yard", t=now - 3705, length=60, check=0))
assert main.PLAYBACKS[-1]["short"] is False

OPENS.clear()
async def ss_broken(rec_id, off, play):            # always only the first second
    OPENS.append((off, play))
    return MP4Resp(mp4(1.0, pad=20000) if off else mp4(60))
main.ss.open_recording = ss_broken
main.REC_MODE["mode"] = None
run(main.overview_recording(RangeReq(), cam="Yard", t=now - 4200, length=60, check=0))
pb = main.PLAYBACKS[-1]
assert main.REC_MODE["mode"] == "broken" and pb["short"] is True and pb["trimmed"] == 20000, pb
assert len(OPENS) == 2
run(main.overview_recording(RangeReq(), cam="Yard", t=now - 4100, length=60, check=0))
assert len(OPENS) == 3                                                # no second try once known broken
cached = run(main.overview_recording(RangeReq(), cam="Yard", t=now - 4100, length=60, check=0))
assert main.PLAYBACKS[-1]["status"] == "cached" and main.PLAYBACKS[-1]["short"] is True

# the test in the raw data tries several ways and reports what came back
OPENS.clear(); main.ss.open_recording = ss_absolute
vt = run(main.recording_test(R, cam="Yard"))
assert vt["recording"] == 20 and vt["recording_length_s"] == 1300, vt
by = {r["variant"]: r for r in vt["results"]}
assert by["start, 60 s"]["ok"] and by["start, 60 s"]["duration_s"] == 60
mid = [r for r in vt["results"] if r["variant"].endswith("in, 60 s") and r["offsetTimeMs"] > 200000][0]
assert mid["ok"] is False and mid["duration_s"] == 1.0 and mid["padding_bytes"] == 20000, mid
assert [r for r in vt["results"] if "slutpunkt" in r["variant"]][0]["ok"] is True
assert by["hela filen (början)"]["offsetTimeMs"] is None and OPENS[-1] == (None, None)
assert not [f for f in os.listdir(main.REC_CACHE_DIR) if f.startswith("test_")]
assert run(main.overview_raw(R))["recording_variants"]["recording"] == 20
recs.pop()
print("D3 short parts, playTimeMs mode and fetch test OK")

# ---- Overview settings: validated, saved, exported
run(main.put_settings(R, {"overview": {"sound": 0, "debug": "yes", "junk": 1}}))
assert config.get("overview") == {"sound": False, "debug": True}, config.get("overview")
assert json.loads(run(main.export_settings(R, secrets=0)).body)["overview"] == {"sound": False, "debug": True}

# ---- all 80 types have Swedish names, groups only contain known types
from app.config import TYPE_NAMES_SV, TYPE_GROUPS
from app.detector import COCO
assert all(c in TYPE_NAMES_SV for c in COCO) and all(x in COCO for _, g in TYPE_GROUPS for x in g)
assert run(main.get_config(R))["types"]["groups"] == TYPE_GROUPS

# ---- shutdown closes open live streams and go2rtc
class FakeWS:
    closed = None
    async def close(self, code=1000): FakeWS.closed = code
stopped = []
async def fake_stop(): stopped.append(1)
main.LIVE_SOCKETS.add(FakeWS()); main.streams.stop = fake_stop
run(main.shutdown())
assert FakeWS.closed == 1001 and stopped and main.SHUTTING_DOWN
print("F settings, types, shutdown OK")

# ---- request language: the same text in the browser's language, the server keeps its own
tok = i18n.request_lang.set("en")
assert i18n.tr("Ingen inspelning") == "No recording"
i18n.request_lang.reset(tok)
print("E language OK")
print("ALL overview OK")
