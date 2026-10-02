"""Polite fetcher for freeislamiccalligraphy.com (INTERNAL test set only; never publish what it downloads).

Every request: robots.txt checked (urllib.robotparser), User-Agent "NunHackathon/0.3 (internal testing)", at most one
request per second, and an on-disk cache under data/private/fic/cache/ so re-runs do not hit the site again.
"""

from __future__ import annotations

import hashlib
import time
import urllib.request
import urllib.robotparser
from pathlib import Path

UA = "NunHackathon/0.3 (internal testing)"
BASE = "https://freeislamiccalligraphy.com"
CACHE = Path("data/private/fic/cache")
MIN_INTERVAL = 1.0  # seconds between requests

_robots = urllib.robotparser.RobotFileParser(BASE + "/robots.txt")
_last = 0.0
_loaded = False


def _wait() -> None:
    global _last
    dt = time.monotonic() - _last
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last = time.monotonic()


def allowed(url: str) -> bool:
    global _loaded
    if not _loaded:
        _wait()
        req = urllib.request.Request(BASE + "/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            _robots.parse(r.read().decode("utf-8", "replace").splitlines())
        _loaded = True
    return _robots.can_fetch(UA, url)


def get(url: str, binary: bool = False) -> tuple[bytes | str, str]:
    """→ (body, final URL after redirects). Raises PermissionError for robots-disallowed URLs."""
    if not allowed(url):
        raise PermissionError(f"robots.txt disallows {url}")
    key = hashlib.sha1(url.encode()).hexdigest()
    body_p, url_p = CACHE / key, CACHE / f"{key}.url"
    if body_p.exists():
        body, final = body_p.read_bytes(), url_p.read_text(encoding="utf-8")
    else:
        _wait()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    body, final = r.read(), r.geturl()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
                _wait()
        CACHE.mkdir(parents=True, exist_ok=True)
        body_p.write_bytes(body)
        url_p.write_text(final, encoding="utf-8")
    return (body if binary else body.decode("utf-8", "replace")), final
