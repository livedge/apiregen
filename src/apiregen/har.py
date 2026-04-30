"""HAR file parser with typed dataclasses."""

import base64
import gzip
import json
import zlib
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
    websocket_messages: list[dict] = field(default_factory=list)


def _flatten_headers(headers: list[dict]) -> dict[str, list[str]]:
    """Convert HAR header list [{name, value}, ...] to {name: [values]}."""
    result: dict[str, list[str]] = {}
    for h in headers:
        name = h["name"].lower()
        result.setdefault(name, []).append(h["value"])
    return result


def _decode_bytes(raw: bytes, headers: dict[str, list[str]] | None = None) -> bytes:
    """Decode compressed HTTP bodies when the HAR stores raw encoded bytes."""
    encoding_values = []
    if headers:
        encoding_values = headers.get("content-encoding", [])
    encodings = ",".join(encoding_values).lower()

    try:
        if "gzip" in encodings:
            return gzip.decompress(raw)
        if "deflate" in encodings:
            return zlib.decompress(raw)
        if "br" in encodings:
            import brotli  # type: ignore[import-not-found]

            return brotli.decompress(raw)
        if "zstd" in encodings:
            import zstandard as zstd  # type: ignore[import-not-found]

            return zstd.ZstdDecompressor().decompress(raw)
    except Exception:
        return raw
    return raw


def _decode_body(content: dict, headers: dict[str, list[str]] | None = None) -> str | None:
    """Decode response body, handling base64 and common content encodings."""
    text = content.get("text")
    if text is None:
        return None
    if content.get("encoding") == "base64":
        try:
            raw = base64.b64decode(text)
            return _decode_bytes(raw, headers).decode("utf-8", errors="replace")
        except Exception:
            return None
    return text


def _extract_query_params(url: str) -> dict[str, str]:
    """Extract query parameters from URL, taking last value for each key."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return {k: v[-1] for k, v in params.items()}


def _decode_request_body(post_data: dict) -> str | None:
    text = post_data.get("text") if post_data else None
    if text is None:
        return None
    if post_data.get("encoding") == "base64":
        try:
            return base64.b64decode(text).decode("utf-8", errors="replace")
        except Exception:
            return None
    return text


def _entry_from_raw(entry: dict, session_name: str) -> HarEntry:
    request = entry.get("request", {})
    response = entry.get("response", {})

    post_data = request.get("postData", {})
    request_body = _decode_request_body(post_data)
    response_headers = _flatten_headers(response.get("headers", []))

    return HarEntry(
        url=request.get("url", ""),
        method=request.get("method", ""),
        status=response.get("status", 0),
        mime_type=response.get("content", {}).get("mimeType", ""),
        request_headers=_flatten_headers(request.get("headers", [])),
        response_headers=response_headers,
        query_params=_extract_query_params(request.get("url", "")),
        request_body=request_body,
        response_body=_decode_body(response.get("content", {}), response_headers),
        cookies=request.get("cookies", []),
        timings=entry.get("timings", {}),
        session=session_name,
        websocket_messages=entry.get("_webSocketMessages", [])
        or entry.get("_websocketMessages", [])
        or entry.get("webSocketMessages", []),
    )


def _entries_array_remainder(path: Path) -> tuple[object, str] | None:
    """Return an open file and text after the log.entries array starts."""
    f = path.open(encoding="utf-8")
    marker = '"entries"'
    buffer = ""
    while chunk := f.read(64 * 1024):
        buffer += chunk
        marker_index = buffer.find(marker)
        if marker_index == -1:
            buffer = buffer[-len(marker) :]
            continue
        bracket_index = buffer.find("[", marker_index)
        while bracket_index == -1:
            chunk = f.read(64 * 1024)
            if not chunk:
                f.close()
                return None
            buffer += chunk
            bracket_index = buffer.find("[", marker_index)
        return f, buffer[bracket_index + 1 :]
    f.close()
    return None


def iter_har_entries(path: Path, session: str = ""):
    """Yield HAR entries incrementally from ``log.entries``.

    This avoids materializing large captures as a full Python object before
    filtering or indexing them. It still decodes each individual entry with
    the standard JSON decoder once enough bytes for that entry are available.
    """
    session_name = session or path.stem
    located = _entries_array_remainder(path)
    if located is None:
        return

    f, buffer = located
    decoder = json.JSONDecoder()
    try:
        while True:
            buffer = buffer.lstrip()
            if buffer.startswith("]"):
                return
            if buffer.startswith(","):
                buffer = buffer[1:]
                continue
            try:
                raw_entry, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk = f.read(64 * 1024)
                if not chunk:
                    return
                buffer += chunk
                continue
            yield _entry_from_raw(raw_entry, session_name)
            buffer = buffer[end:]
    finally:
        f.close()


def parse_har(path: Path, session: str = "") -> list[HarEntry]:
    """Load HAR file, decode bodies, return typed entries."""
    return list(iter_har_entries(path, session=session))
