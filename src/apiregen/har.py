"""HAR file parser with typed dataclasses."""

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse


@dataclass
class HarEntry:
    url: str
    method: str
    status: int
    mime_type: str
    request_headers: dict[str, list[str]]
    response_headers: dict[str, list[str]]
    query_params: dict[str, str]
    request_body: str | None
    response_body: str | None
    cookies: list[dict]
    timings: dict
    session: str = ""  # source HAR filename for cross-session comparison


def _flatten_headers(headers: list[dict]) -> dict[str, list[str]]:
    """Convert HAR header list [{name, value}, ...] to {name: [values]}."""
    result: dict[str, list[str]] = {}
    for h in headers:
        name = h["name"].lower()
        result.setdefault(name, []).append(h["value"])
    return result


def _decode_body(content: dict) -> str | None:
    """Decode response body, handling base64 encoding."""
    text = content.get("text")
    if text is None:
        return None
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(text).decode("utf-8", errors="replace")
        except Exception:
            return None
    return text


def _extract_query_params(url: str) -> dict[str, str]:
    """Extract query parameters from URL, taking last value for each key."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return {k: v[-1] for k, v in params.items()}


def parse_har(path: Path, session: str = "") -> list[HarEntry]:
    """Load HAR file, decode base64 bodies, return typed entries."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)

    session_name = session or path.stem
    entries = []

    for entry in data.get("log", {}).get("entries", []):
        request = entry.get("request", {})
        response = entry.get("response", {})

        # Extract request body
        post_data = request.get("postData", {})
        request_body = post_data.get("text") if post_data else None

        har_entry = HarEntry(
            url=request.get("url", ""),
            method=request.get("method", ""),
            status=response.get("status", 0),
            mime_type=response.get("content", {}).get("mimeType", ""),
            request_headers=_flatten_headers(request.get("headers", [])),
            response_headers=_flatten_headers(response.get("headers", [])),
            query_params=_extract_query_params(request.get("url", "")),
            request_body=request_body,
            response_body=_decode_body(response.get("content", {})),
            cookies=request.get("cookies", []),
            timings=entry.get("timings", {}),
            session=session_name,
        )
        entries.append(har_entry)

    return entries
