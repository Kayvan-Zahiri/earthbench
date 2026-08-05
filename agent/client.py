"""Mireye API surface the agent uses, including the endpoints added after the
benchmark ran: /v1/fetch/batch, /v1/field-requests and /v1/meta/fields.

Everything returns raw JSON. Interpretation lives in catalog.py and hazard.py,
so the transport layer never decides anything.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.error
import urllib.request

API = "https://api.mireye.com"
_CATALOG_CACHE = pathlib.Path(__file__).parent / ".catalog.json"


class MireyeError(RuntimeError):
    """An API call failed. Carries the status and the parsed body."""

    def __init__(self, status: int, body: dict, path: str):
        self.status, self.body, self.path = status, body, path
        code = body.get("error") or body.get("code") or body.get("detail") or ""
        super().__init__(f"{path} -> HTTP {status} {code}".strip())


def _key() -> str:
    key = os.environ.get("MIREYE_API_KEY", "").strip()
    if not key:
        for env in (pathlib.Path.cwd() / ".env", pathlib.Path.home() / "Desktop/jobs/.env"):
            if env.exists():
                for line in env.read_text().splitlines():
                    if line.startswith("MIREYE_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip("\"'")
                        break
            if key:
                break
    if not key:
        raise RuntimeError("MIREYE_API_KEY is not set (env or .env)")
    return key


def _request(method: str, path: str, body: dict | None = None, *, auth: bool = True) -> dict:
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {_key()}"
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode() or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw[:500]}
        raise MireyeError(exc.code, parsed, path) from None


# ---------------------------------------------------------------- catalog


def catalog(*, refresh: bool = False) -> list[dict]:
    """The 283-field catalog. Public, no token, so this works before signup.

    Cached on disk because the agent reads it on every plan and it changes at
    the pace of a data release, not a request.
    """
    if not refresh and _CATALOG_CACHE.exists():
        age = time.time() - _CATALOG_CACHE.stat().st_mtime
        if age < 86_400:
            return json.loads(_CATALOG_CACHE.read_text())
    data = _request("GET", "/v1/meta/fields", auth=False)
    fields = data if isinstance(data, list) else data.get("fields") or data.get("data") or []
    _CATALOG_CACHE.write_text(json.dumps(fields))
    return fields


# ---------------------------------------------------------------- reads


def fetch(lat: float, lng: float, fields: list[str]) -> dict:
    return _request("POST", "/v1/fetch", {"lat": lat, "lng": lng, "fields": fields})


def fetch_batch(locations: list[dict], fields: list[str]) -> list[dict]:
    """Up to 25 locations in one call.

    This is the endpoint that makes ranking possible at all. When the benchmark
    ran, /fetch and /ask each took a single coordinate, so comparing candidates
    meant N round trips and there was no way to hold them side by side.
    Returns the per-location results list, each with .ok and .fields.
    """
    if not locations:
        return []
    if len(locations) > 25:
        raise ValueError(f"/v1/fetch/batch takes at most 25 locations, got {len(locations)}")
    out = _request("POST", "/v1/fetch/batch", {"locations": locations, "fields": fields})
    return out.get("results", [])


def ask(lat: float, lng: float, question: str) -> dict:
    return _request("POST", "/v1/ask", {"lat": lat, "lng": lng, "question": question})


def usage() -> dict:
    return _request("GET", "/v1/users/me/usage")


# ---------------------------------------------------------------- field requests


def request_field(
    description: str,
    example_locations: list[dict],
    *,
    use_case: str | None = None,
    decision_threshold: str | None = None,
    known_sources: dict | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Ask Mireye to add a field that does not exist yet.

    The agent calls this when it needs a decisive field the catalog cannot
    supply. The free plan reports field_requests_included: 0, so this raises
    MireyeError with a plan/entitlement code on a free account. Callers should
    catch it and record the payload they *would* have sent, which is still the
    honest thing to show a user: here is the gap, and here is the ask.
    """
    body: dict = {"description": description, "example_locations": example_locations}
    if use_case:
        body["use_case"] = use_case
    if decision_threshold:
        body["decision_threshold"] = decision_threshold
    if known_sources:
        body["known_sources"] = known_sources
    if idempotency_key:
        body["idempotency_key"] = idempotency_key
    return _request("POST", "/v1/field-requests", body)


def field_request_status(request_id: str) -> dict:
    return _request("GET", f"/v1/field-requests/{request_id}")
