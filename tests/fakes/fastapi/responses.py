"""Minimal stand-ins for the FastAPI response classes used by the app (tests only)."""
import json


class Headers(dict):
    """Case-insensitive header dict."""
    def __setitem__(self, k, v): super().__setitem__(k.lower(), v)
    def __getitem__(self, k): return super().__getitem__(k.lower())
    def get(self, k, d=None): return super().get(k.lower(), d)
    def __contains__(self, k): return super().__contains__(k.lower())


class Response:
    media_type = None

    def __init__(self, content=b"", status_code=200, headers=None, media_type=None):
        self.status_code = status_code
        self.media_type = media_type or self.media_type
        self.body = self.render(content)
        self.headers = Headers()
        for k, v in (headers or {}).items():
            self.headers[k] = v
        self.cookies = {}

    def render(self, content):
        return content if isinstance(content, bytes) else str(content or "").encode()

    def set_cookie(self, key, value="", **kw):
        self.cookies[key] = {"value": value, **kw}

    def delete_cookie(self, key, **kw):
        self.cookies[key] = {"value": "", "max_age": 0, **kw}


class JSONResponse(Response):
    media_type = "application/json"

    def render(self, content):
        return json.dumps(content, ensure_ascii=False).encode()


class RedirectResponse(Response):
    def __init__(self, url, status_code=307, headers=None):
        super().__init__(b"", status_code, headers)
        self.headers["location"] = str(url)


class FileResponse(Response):
    def __init__(self, path, status_code=200, headers=None, media_type=None, **kw):
        super().__init__(b"", status_code, headers, media_type)
        self.path = path


class StreamingResponse(Response):
    def __init__(self, content, status_code=200, headers=None, media_type=None):
        super().__init__(b"", status_code, headers, media_type)
        self.body_iterator = content
