# Minimal fake of httpx for tests: records requests, returns queued responses.
import json as _json
CALLS = []
RESPONSES = []

class Timeout:
    def __init__(self, *a, **k): pass

class HTTPStatusError(Exception):
    def __init__(self, msg, response=None):
        super().__init__(msg); self.response = response

class Response:
    def __init__(self, status=200, data=None, headers=None, content=b""):
        self.status_code = status; self._data = data; self.headers = headers or {"content-type": "application/json"}
        self.content = content; self.text = _json.dumps(data) if data is not None else ""
    def json(self):
        return self._data
    def raise_for_status(self):
        if self.status_code >= 400: raise HTTPStatusError("err", response=self)

class AsyncClient:
    def __init__(self, *a, **k): self.kw = k
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def aclose(self): pass
    async def _do(self, method, url, **kw):
        CALLS.append({"method": method, "url": url, **kw})
        return RESPONSES.pop(0) if RESPONSES else Response(200, {"ok": True})
    async def get(self, url, **kw): return await self._do("GET", url, **kw)
    async def post(self, url, **kw): return await self._do("POST", url, **kw)
    async def put(self, url, **kw): return await self._do("PUT", url, **kw)
    async def delete(self, url, **kw): return await self._do("DELETE", url, **kw)
    async def request(self, method, url, **kw): return await self._do(method, url, **kw)
