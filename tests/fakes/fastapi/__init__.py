"""Minimal stand-in for FastAPI (tests only): the tests call the endpoint functions directly."""


class Request:
    """Only used as a type annotation by the app; the tests pass their own request objects."""
class HTTPException(Exception):
    def __init__(self, status_code, detail=None):
        super().__init__(detail); self.status_code = status_code; self.detail = detail
def Body(*a, **k): return None
class FastAPI:
    def __init__(self, **k): self.routes = {}
    def _reg(self, *paths, **k):
        def deco(f):
            self.routes[(paths[0] if paths else f.__name__)] = f; return f
        return deco
    get = post = put = delete = api_route = _reg
    def middleware(self, *a): return lambda f: f
    def on_event(self, *a): return lambda f: f
    def mount(self, *a, **k): pass
