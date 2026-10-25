"""HTTP access with disk cache, per-host throttling, retries, secret redaction and offline fixtures.

Fixture mode (tests / offline demos): set CDRI_FIXTURES=<dir> containing routes.json:
    [{"match": "<regex on URL>", "file": "body.json", "status": 200}, ...]
In fixture mode the network is never touched; an unmatched URL raises Offline.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import __version__, config

UA = f"cdri/{__version__} (Cross-Domain Research Intelligence; +https://github.com/)"
SECRET_PARAMS = re.compile(r"(api_key|apikey|key|token|access_token)=([^&]+)", re.I)
MIN_INTERVAL = {"api.semanticscholar.org": 1.1, "export.arxiv.org": 3.0, "eutils.ncbi.nlm.nih.gov": 0.4,
                "api.crossref.org": 0.2, "api.openalex.org": 0.15, "www.ebi.ac.uk": 0.2, "dblp.org": 1.0,
                "api.github.com": 0.5, "api.biorxiv.org": 0.5, "api.unpaywall.org": 0.2}
_last_call: Dict[str, float] = {}


class HTTPFailure(Exception):
    def __init__(self, status: str, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.status = status  # rate_limited | error | not_found | offline
        self.code = code


class Offline(HTTPFailure):
    def __init__(self, message: str):
        super().__init__("offline", message)


@dataclass
class Response:
    url: str
    code: int
    body: bytes
    headers: Dict[str, str] = field(default_factory=dict)
    from_cache: bool = False

    def json(self):
        return json.loads(self.body.decode("utf-8", errors="replace"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def redact(url: str) -> str:
    return SECRET_PARAMS.sub(lambda m: f"{m.group(1)}=***", url)


def _fixture_routes() -> Optional[List[dict]]:
    d = os.environ.get("CDRI_FIXTURES")
    if not d:
        return None
    p = Path(d) / "routes.json"
    routes = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    for r in routes:
        r["_dir"] = d
    return routes


def _from_fixture(url: str, routes: List[dict]) -> Response:
    for r in routes:
        if re.search(r["match"], urllib.parse.unquote(url)):
            code = int(r.get("status", 200))
            body = (Path(r["_dir"]) / r["file"]).read_bytes() if r.get("file") else b""
            if code == 429:
                raise HTTPFailure("rate_limited", f"429 from fixture for {redact(url)}", 429)
            if code == 404:
                raise HTTPFailure("not_found", f"404 from fixture for {redact(url)}", 404)
            if code >= 400:
                raise HTTPFailure("error", f"HTTP {code} from fixture", code)
            return Response(url=redact(url), code=code, body=body, headers={"content-type": r.get("content_type", "")})
    raise Offline(f"no fixture matches {redact(url)}")


def _cache_path(url: str) -> Path:
    host = urllib.parse.urlparse(url).netloc or "local"
    key = hashlib.sha1(redact(url).encode()).hexdigest()
    d = config.cache_dir("http") / host
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.bin"


def get(url: str, *, headers: Optional[Dict[str, str]] = None, ttl_days: float = 7.0, retries: int = 3,
        timeout: int = 30, use_cache: bool = True, accept: str = "application/json") -> Response:
    routes = _fixture_routes()
    if routes is not None:
        return _from_fixture(url, routes)
    cp = _cache_path(url)
    meta_p = cp.with_suffix(".meta.json")
    if use_cache and cp.exists() and meta_p.exists():
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        if time.time() - meta.get("t", 0) < ttl_days * 86400:
            return Response(url=redact(url), code=meta.get("code", 200), body=cp.read_bytes(),
                            headers=meta.get("headers", {}), from_cache=True)
    if config.offline():
        raise Offline(f"offline mode and no cache for {redact(url)}")
    host = urllib.parse.urlparse(url).netloc
    h = {"User-Agent": UA + (f" mailto:{config.env('mailto')}" if config.env("mailto") else ""), "Accept": accept}
    h.update(headers or {})
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        wait = MIN_INTERVAL.get(host, 0.2) - (time.time() - _last_call.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URLs built by adapters
                body = r.read()
                resp = Response(url=redact(url), code=r.status, body=body,
                                headers={k.lower(): v for k, v in r.headers.items()})
            if use_cache:
                cp.write_bytes(body)
                meta_p.write_text(json.dumps({"t": time.time(), "code": resp.code,
                                              "headers": {"content-type": resp.headers.get("content-type", "")}}),
                                  encoding="utf-8")
            return resp
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise HTTPFailure("not_found", f"404 for {redact(url)}", 404)
            if exc.code == 429 or exc.code >= 500:
                last_exc = exc
                if attempt < retries - 1:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * (2 ** attempt)
                    time.sleep(min(delay, 20))
                    continue
                status = "rate_limited" if exc.code == 429 else "error"
                raise HTTPFailure(status, f"HTTP {exc.code} for {redact(url)} after {retries} attempts", exc.code)
            raise HTTPFailure("error", f"HTTP {exc.code} for {redact(url)}", exc.code)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
    raise HTTPFailure("error", f"network failure for {redact(url)}: {last_exc}")


def get_json(url: str, **kw):
    resp = get(url, **kw)
    try:
        return resp.json()
    except ValueError:
        if os.environ.get("CDRI_FIXTURES") is None:
            cp = _cache_path(url)
            cp.unlink(missing_ok=True)
            cp.with_suffix(".meta.json").unlink(missing_ok=True)
        head = resp.body[:400].decode("utf-8", errors="replace").lower()
        if "<html" in head or "not a bot" in head or "captcha" in head:
            raise HTTPFailure("blocked", f"non-JSON HTML (likely anti-bot challenge, HTTP {resp.code}) for "
                                         f"{redact(url)}", resp.code)
        raise HTTPFailure("error", f"invalid JSON (HTTP {resp.code}) for {redact(url)}", resp.code)
