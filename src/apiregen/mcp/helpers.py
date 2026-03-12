"""Pure utility functions for MCP tools — no state dependencies."""

from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlparse

from apiregen.har import HarEntry


def entry_summary(idx: int, entry: HarEntry) -> dict[str, Any]:
    return {
        "index": idx,
        "method": entry.method,
        "url": entry.url[:300],
        "status": entry.status,
        "mime_type": entry.mime_type,
        "session": entry.session,
        "has_request_body": entry.request_body is not None,
        "response_size": len(entry.response_body) if entry.response_body else 0,
    }


def domain_of(url: str) -> str:
    return urlparse(url).netloc


def path_of(url: str) -> str:
    return urlparse(url).path


def truncate(text: str | None, max_length: int) -> str:
    if text is None:
        return ""
    if len(text) <= max_length:
        return text
    return (
        text[:max_length]
        + f"\n\n... truncated ({len(text):,} total chars, showing first {max_length:,})"
    )


def json_path_extract(data: Any, path: str) -> Any:
    """Simple dot-notation path extraction: ``data.items.0.name``."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return f"Key '{part}' not found. Available keys: {list(current.keys())}"
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return f"Invalid list index '{part}' (list has {len(current)} items)"
        else:
            return f"Cannot traverse into {type(current).__name__} with key '{part}'"
    return current


def infer_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def infer_schema(
    samples: list[Any], max_depth: int = 5, _depth: int = 0
) -> dict[str, Any]:
    """Infer a structural schema from *samples* (multiple JSON values)."""
    if _depth >= max_depth:
        return {"type": "...(max depth)"}

    types = Counter(infer_type(s) for s in samples)

    if len(types) == 1:
        t = next(iter(types))
    else:
        t = " | ".join(f"{k}({v})" for k, v in types.most_common())

    result: dict[str, Any] = {"type": t, "count": len(samples)}

    # Objects: recurse into fields
    obj_samples = [s for s in samples if isinstance(s, dict)]
    if obj_samples:
        all_keys: set[str] = set()
        for s in obj_samples:
            all_keys.update(s.keys())
        fields: dict[str, Any] = {}
        for key in sorted(all_keys):
            values = [s[key] for s in obj_samples if key in s]
            field_info = infer_schema(values, max_depth, _depth + 1)
            field_info["present_in"] = f"{len(values)}/{len(obj_samples)}"
            fields[key] = field_info
        result["fields"] = fields

    # Arrays: sample items
    arr_samples = [s for s in samples if isinstance(s, list)]
    if arr_samples:
        lengths = [len(s) for s in arr_samples]
        result["array_lengths"] = {"min": min(lengths), "max": max(lengths)}
        all_items: list[Any] = []
        for s in arr_samples:
            all_items.extend(s[:5])
        if all_items:
            result["items"] = infer_schema(all_items, max_depth, _depth + 1)

    # Scalars: sample values
    scalar_samples = [s for s in samples if isinstance(s, (str, int, float, bool))]
    if scalar_samples:
        unique = sorted(set(str(s) for s in scalar_samples))
        if len(unique) <= 10:
            result["unique_values"] = unique
        else:
            result["sample_values"] = unique[:5]
            result["unique_count"] = len(unique)

    return result
