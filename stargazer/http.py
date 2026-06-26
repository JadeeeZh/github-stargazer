"""Tiny stdlib HTTP helper with a browser UA and polite backoff on 429/403."""
import time, urllib.request, urllib.error
from .config import UA


def get(url, timeout=25, tries=4, accept="text/html", max_bytes=None):
    """Return (text, status). status 200 on success, HTTP code or -1 on failure."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read(max_bytes) if max_bytes else r.read()
                return data.decode("utf-8", "ignore"), 200
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "", 404
            if e.code in (429, 403) and attempt < tries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            return "", e.code
        except Exception:
            if attempt < tries - 1:
                time.sleep(4)
                continue
            return "", -1
    return "", -1


def get_json(url, headers=None, timeout=25, tries=4):
    """GET returning (obj, status). Used for the GitHub API path."""
    import json
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if headers:
        h.update(headers)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore")), 200
        except urllib.error.HTTPError as e:
            if e.code in (429, 403) and attempt < tries - 1:
                time.sleep(8 * (attempt + 1))
                continue
            return None, e.code
        except Exception:
            if attempt < tries - 1:
                time.sleep(4)
                continue
            return None, -1
    return None, -1
