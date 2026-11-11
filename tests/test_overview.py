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
assert S.mask('cameraId=1&StmKey=\\"3578496afb6f409b\\"') == 'cameraId=1&StmKey=\\"***\\"'
assert S.mask("rtsp.cgi?Sms=1.unicast&StmKey=3578496afb6f409b") == "rtsp.cgi?Sms=1.unicast&StmKey=***"
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
print("D timeline OK")

# ---- request language: the same text in the browser's language, the server keeps its own
tok = i18n.request_lang.set("en")
assert i18n.tr("Ingen inspelning") == "No recording"
i18n.request_lang.reset(tok)
print("E language OK")
print("ALL overview OK")
