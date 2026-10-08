"""Optional access key for the whole API.

Off by default (the server only listens on loopback). When ADMIN_API_KEY or CHEAT_CLIP_API_KEY
is set, every /api request needs the key: scripts send it as `X-API-Key` / `Authorization: Bearer`,
the web UI exchanges it once for an HttpOnly session cookie so <video>, <img>, download links
and EventSource (which cannot set headers) are covered too.
"""
import hashlib
import hmac
import os

SESSION_COOKIE = "cheat_clip_session"
SESSION_MAX_AGE = 30 * 24 * 3600


def configured_api_key() -> str:
    return (os.environ.get("ADMIN_API_KEY") or os.environ.get("CHEAT_CLIP_API_KEY") or "").strip()


def session_token(key: str) -> str:
    # Derived value, so the raw key never sits in the browser's cookie jar.
    return hmac.new(key.encode(), b"cheat-clip-pro-session-v1", hashlib.sha256).hexdigest()


def key_matches(provided: str, expected: str) -> bool:
    return bool(provided) and hmac.compare_digest(provided.encode(), expected.encode())


def request_is_authorized(headers, cookies) -> bool:
    key = configured_api_key()
    if not key:
        return True
    provided = (headers.get("x-api-key") or "").strip()
    authorization = headers.get("authorization") or ""
    if not provided and authorization.startswith("Bearer "):
        provided = authorization[7:].strip()
    if key_matches(provided, key):
        return True
    return key_matches(cookies.get(SESSION_COOKIE, ""), session_token(key))
