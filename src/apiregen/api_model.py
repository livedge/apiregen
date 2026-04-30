"""Build assistant-friendly API models from captured HAR entries."""

from __future__ import annotations

import copy
import json
import re
import shlex
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from apiregen.har import HarEntry


SENSITIVE_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "x-xsrf-token",
    "csrf",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "password",
    "secret",
    "session",
    "sid",
}


@dataclass
class ValuePattern:
    classification: str
    sample_values: list[str] = field(default_factory=list)
    unique_values: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "sample_values": self.sample_values,
            "unique_values": self.unique_values,
        }


@dataclass
class Coverage:
    sample_count: int
    session_count: int
    request_variants: int
    response_shapes: int
    status_codes: dict[int, int]
    confidence: str
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "session_count": self.session_count,
            "request_variants": self.request_variants,
            "response_shapes": self.response_shapes,
            "status_codes": self.status_codes,
            "confidence": self.confidence,
            "gaps": self.gaps,
        }


@dataclass
class Dependency:
    source_endpoint: str
    field: str
    target_parameter: str
    observed_value: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_endpoint": self.source_endpoint,
            "field": self.field,
            "target_parameter": self.target_parameter,
            "observed_value": self.observed_value,
        }


@dataclass
class EndpointModel:
    domain: str
    method: str
    path_template: str
    path_parameters: list[str]
    entries: list[int]
    query_parameters: dict[str, ValuePattern]
    tokens: dict[str, ValuePattern]
    request_schema: dict[str, Any] | None
    response_schema: dict[str, Any] | None
    coverage: Coverage
    dependencies: list[Dependency] = field(default_factory=list)
    websocket_schema: dict[str, Any] | None = None

    @property
    def key(self) -> str:
        return f"{self.method} {self.path_template}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "method": self.method,
            "path_template": self.path_template,
            "path_parameters": self.path_parameters,
            "entry_indices": self.entries,
            "query_parameters": {k: v.to_dict() for k, v in self.query_parameters.items()},
            "tokens": {k: v.to_dict() for k, v in self.tokens.items()},
            "request_schema": self.request_schema,
            "response_schema": self.response_schema,
            "websocket_schema": self.websocket_schema,
            "coverage": self.coverage.to_dict(),
            "dependencies": [d.to_dict() for d in self.dependencies],
        }


@dataclass
class ApiModel:
    endpoints: list[EndpointModel]
    source_entry_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_entry_count": self.source_entry_count,
            "endpoint_count": len(self.endpoints),
            "endpoints": [endpoint.to_dict() for endpoint in self.endpoints],
        }


def _domain(url: str) -> str:
    return urlparse(url).netloc


def _segments(url: str) -> list[str]:
    return [segment for segment in urlparse(url).path.split("/") if segment]


def _looks_dynamic(segment: str) -> bool:
    if not segment:
        return False
    if segment.isdigit():
        return True
    if re.fullmatch(r"[0-9a-fA-F]{8,}", segment):
        return True
    if re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        segment,
    ):
        return True
    if re.search(r"\d", segment) and re.fullmatch(r"[A-Za-z0-9_-]{5,}", segment):
        return True
    return False


def _param_names(dynamic_positions: list[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    for idx, position in enumerate(dynamic_positions):
        names[position] = "id" if idx == 0 else f"id{idx + 1}"
    return names


def _template_for(entries: list[tuple[int, HarEntry]]) -> tuple[str, list[str]]:
    segment_lists = [_segments(entry.url) for _, entry in entries]
    max_len = max((len(parts) for parts in segment_lists), default=0)
    dynamic_positions = []
    for pos in range(max_len):
        values = {parts[pos] for parts in segment_lists if pos < len(parts)}
        if len(values) > 1 or any(_looks_dynamic(value) for value in values):
            dynamic_positions.append(pos)

    names = _param_names(dynamic_positions)
    template_parts = []
    for pos in range(max_len):
        if pos in names:
            template_parts.append("{" + names[pos] + "}")
        else:
            first = next((parts[pos] for parts in segment_lists if pos < len(parts)), "")
            template_parts.append(first)

    return "/" + "/".join(template_parts), list(names.values())


def _skeleton(entry: HarEntry) -> tuple[str, ...]:
    return tuple("{dynamic}" if _looks_dynamic(segment) else segment for segment in _segments(entry.url))


def _value_pattern(values: list[str]) -> ValuePattern:
    unique = sorted(set(values))
    if not values:
        classification = "absent"
    elif len(unique) == 1:
        classification = "static"
    elif len(unique) == len(values):
        classification = "dynamic"
    else:
        classification = "mixed"
    return ValuePattern(
        classification=classification,
        sample_values=unique[:5],
        unique_values=len(unique),
    )


def _parse_json_samples(values: list[str | None]) -> list[Any]:
    parsed = []
    for value in values:
        if not value:
            continue
        try:
            parsed.append(json.loads(value))
        except (TypeError, ValueError):
            continue
    return parsed


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def infer_json_schema(samples: list[Any], max_depth: int = 5, _depth: int = 0) -> dict[str, Any]:
    """Infer a compact JSON Schema from observed samples."""
    if not samples:
        return {"type": "object"}
    if _depth >= max_depth:
        return {}

    types = sorted({_json_type(sample) for sample in samples})
    schema: dict[str, Any] = {"type": types[0] if len(types) == 1 else types}

    object_samples = [sample for sample in samples if isinstance(sample, dict)]
    if object_samples:
        keys = sorted({key for sample in object_samples for key in sample})
        properties = {}
        required = []
        for key in keys:
            values = [sample[key] for sample in object_samples if key in sample]
            properties[key] = infer_json_schema(values, max_depth, _depth + 1)
            if len(values) == len(object_samples):
                required.append(key)
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required

    array_samples = [sample for sample in samples if isinstance(sample, list)]
    if array_samples:
        items = [item for sample in array_samples for item in sample[:10]]
        schema = {"type": "array", "items": infer_json_schema(items, max_depth, _depth + 1)}

    scalar_samples = [
        sample
        for sample in samples
        if isinstance(sample, (str, int, float, bool)) or sample is None
    ]
    if scalar_samples:
        unique = sorted({str(sample) for sample in scalar_samples})
        if 0 < len(unique) <= 5:
            schema["examples"] = unique

    return schema


def _shape_signature(body: str | None) -> str:
    samples = _parse_json_samples([body])
    if not samples:
        return "non-json" if body else "empty"
    schema = infer_json_schema(samples)
    return json.dumps(schema, sort_keys=True)


def _coverage(entries: list[HarEntry]) -> Coverage:
    sample_count = len(entries)
    session_count = len({entry.session for entry in entries})
    request_variants = len({entry.request_body or "" for entry in entries})
    response_shapes = len({_shape_signature(entry.response_body) for entry in entries})
    status_codes = dict(Counter(entry.status for entry in entries))
    gaps = []
    if session_count < 2:
        gaps.append("multiple sessions")
    if not any(entry.status >= 400 for entry in entries):
        gaps.append("error response")
    if not any(entry.response_body in (None, "", "[]", "{}") for entry in entries):
        gaps.append("empty response")
    if sample_count >= 3 and session_count >= 2 and len(gaps) <= 1:
        confidence = "high"
    elif sample_count >= 2 and session_count >= 2:
        confidence = "medium"
    else:
        confidence = "low"
    return Coverage(
        sample_count=sample_count,
        session_count=session_count,
        request_variants=request_variants,
        response_shapes=response_shapes,
        status_codes=status_codes,
        confidence=confidence,
        gaps=gaps,
    )


def _query_patterns(entries: list[HarEntry]) -> dict[str, ValuePattern]:
    values: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        parsed = urlparse(entry.url)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            values[key].append(value)
    return {key: _value_pattern(vals) for key, vals in sorted(values.items())}


def _token_patterns(entries: list[HarEntry]) -> dict[str, ValuePattern]:
    values: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        for name, header_values in entry.request_headers.items():
            lowered = name.lower()
            if _is_sensitive_name(lowered) or lowered.startswith("x-"):
                values[lowered].extend(header_values)
    return {key: _value_pattern(vals) for key, vals in sorted(values.items())}


def _is_sensitive_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in SENSITIVE_NAMES or any(part in lowered for part in SENSITIVE_NAMES)


def _extract_json_fields(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    fields = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(item, (str, int, float)):
                fields.append((path, str(item)))
            fields.extend(_extract_json_fields(item, path))
    elif isinstance(value, list):
        for item in value[:10]:
            fields.extend(_extract_json_fields(item, prefix))
    return fields


def _dependency_index(indexed_entries: list[tuple[int, HarEntry]]) -> dict[str, tuple[str, str]]:
    observed: dict[str, tuple[str, str]] = {}
    for _, entry in indexed_entries:
        for parsed in _parse_json_samples([entry.response_body]):
            for field_path, value in _extract_json_fields(parsed):
                if field_path.lower().endswith("id"):
                    observed.setdefault(value, (f"{entry.method} {urlparse(entry.url).path}", field_path))
    return observed


def _path_values(endpoint: EndpointModel, entry: HarEntry) -> dict[str, str]:
    template_parts = [part for part in endpoint.path_template.split("/") if part]
    actual_parts = _segments(entry.url)
    result = {}
    for template, actual in zip(template_parts, actual_parts, strict=False):
        if template.startswith("{") and template.endswith("}"):
            result[template[1:-1]] = actual
    return result


def _websocket_payload_schema(entries: list[HarEntry]) -> dict[str, Any] | None:
    payloads = []
    for entry in entries:
        for message in entry.websocket_messages:
            data = message.get("data") or message.get("payload")
            if not isinstance(data, str):
                continue
            payloads.extend(_parse_json_samples([data]))
    if not payloads:
        return None
    return infer_json_schema(payloads)


def build_api_model(entries: list[HarEntry]) -> ApiModel:
    """Cluster HAR entries into endpoint models with schemas and coverage."""
    domain_method_length: dict[tuple[str, str, tuple[str, ...]], list[tuple[int, HarEntry]]] = defaultdict(list)
    for idx, entry in enumerate(entries):
        domain_method_length[(_domain(entry.url), entry.method.upper(), _skeleton(entry))].append((idx, entry))

    endpoints = []
    dependency_values = _dependency_index(list(enumerate(entries)))
    for (domain, method, _), indexed_entries in sorted(domain_method_length.items()):
        path_template, path_parameters = _template_for(indexed_entries)
        grouped_entries = [entry for _, entry in indexed_entries]
        endpoint = EndpointModel(
            domain=domain,
            method=method,
            path_template=path_template,
            path_parameters=path_parameters,
            entries=[idx for idx, _ in indexed_entries],
            query_parameters=_query_patterns(grouped_entries),
            tokens=_token_patterns(grouped_entries),
            request_schema=infer_json_schema(_parse_json_samples([entry.request_body for entry in grouped_entries]))
            if any(entry.request_body for entry in grouped_entries)
            else None,
            response_schema=infer_json_schema(_parse_json_samples([entry.response_body for entry in grouped_entries]))
            if any(entry.response_body for entry in grouped_entries)
            else None,
            websocket_schema=_websocket_payload_schema(grouped_entries),
            coverage=_coverage(grouped_entries),
        )
        deps = []
        for entry in grouped_entries:
            for param, value in _path_values(endpoint, entry).items():
                source = dependency_values.get(value)
                if source and source[0] != endpoint.key:
                    deps.append(
                        Dependency(
                            source_endpoint=source[0],
                            field=source[1],
                            target_parameter=param,
                            observed_value=value,
                        )
                    )
        endpoint.dependencies = list({(d.source_endpoint, d.field, d.target_parameter, d.observed_value): d for d in deps}.values())
        endpoints.append(endpoint)

    return ApiModel(endpoints=endpoints, source_entry_count=len(entries))


def generate_openapi(model: ApiModel, title: str = "Reverse Engineered API") -> dict[str, Any]:
    spec: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": title, "version": "0.1.0"},
        "servers": [],
        "paths": {},
    }
    domains = sorted({endpoint.domain for endpoint in model.endpoints if endpoint.domain and not endpoint.websocket_schema})
    spec["servers"] = [{"url": f"https://{domain}"} for domain in domains]
    for endpoint in model.endpoints:
        if endpoint.websocket_schema:
            continue
        operation: dict[str, Any] = {
            "summary": endpoint.key,
            "parameters": [],
            "responses": {},
            "x-apiregen-coverage": endpoint.coverage.to_dict(),
        }
        for param in endpoint.path_parameters:
            operation["parameters"].append(
                {
                    "name": param,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            )
        for name, pattern in endpoint.query_parameters.items():
            operation["parameters"].append(
                {
                    "name": name,
                    "in": "query",
                    "required": pattern.classification == "static",
                    "schema": {"type": "string"},
                    "examples": {"observed": {"value": pattern.sample_values[0]}}
                    if pattern.sample_values
                    else {},
                }
            )
        if endpoint.request_schema:
            operation["requestBody"] = {
                "content": {"application/json": {"schema": endpoint.request_schema}}
            }
        status_code = str(next(iter(endpoint.coverage.status_codes), 200))
        operation["responses"][status_code] = {
            "description": "Observed response",
            "content": {"application/json": {"schema": endpoint.response_schema or {"type": "object"}}},
        }
        spec["paths"].setdefault(endpoint.path_template, {})[endpoint.method.lower()] = operation
    return spec


def generate_asyncapi(model: ApiModel, title: str = "Reverse Engineered Streaming API") -> dict[str, Any]:
    spec: dict[str, Any] = {
        "asyncapi": "3.0.0",
        "info": {"title": title, "version": "0.1.0"},
        "servers": {},
        "channels": {},
    }
    for endpoint in model.endpoints:
        if not endpoint.websocket_schema:
            continue
        server_name = endpoint.domain or "default"
        spec["servers"].setdefault(
            server_name,
            {"host": endpoint.domain, "protocol": "wss"},
        )
        spec["channels"][endpoint.key] = {
            "address": endpoint.path_template,
            "messages": {
                "observedMessage": {
                    "payload": endpoint.websocket_schema,
                    "x-apiregen-coverage": endpoint.coverage.to_dict(),
                }
            },
        }
    return spec


def _redacted_url(url: str) -> str:
    parsed = urlparse(url)
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, "<redacted>" if _is_sensitive_name(key) else value))
    redacted_query = urlencode(query).replace("%3Credacted%3E", "<redacted>")
    return urlunparse(parsed._replace(query=redacted_query))


def replay_curl(entry: HarEntry, redact: bool = True) -> str:
    """Generate a runnable curl command for one captured request."""
    url = _redacted_url(entry.url) if redact else entry.url
    parts = ["curl", "-X", entry.method.upper(), shlex.quote(url)]
    for name, values in sorted(entry.request_headers.items()):
        for value in values:
            header_value = "<redacted>" if redact and _is_sensitive_name(name) else value
            parts.extend(["-H", shlex.quote(f"{name}: {header_value}")])
    if entry.request_body is not None:
        body = redact_json_text(entry.request_body) if redact else entry.request_body
        parts.extend(["--data-raw", shlex.quote(body)])
    return " ".join(parts)


def redact_json_text(text: str) -> str:
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return text
    return json.dumps(_redact_value(parsed), separators=(",", ":"))


def _redact_value(value: Any, key: str = "") -> Any:
    if _is_sensitive_name(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {k: _redact_value(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, key) for item in value]
    if isinstance(value, str) and ("@" in value or re.search(r"bearer\s+", value, re.I)):
        return "<redacted>"
    return value


def _redact_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        result = {}
        for key, value in schema.items():
            if key == "examples":
                result[key] = ["<redacted>" for _ in value] if isinstance(value, list) else "<redacted>"
            elif _is_sensitive_name(key):
                result[key] = "<redacted>"
            else:
                result[key] = _redact_schema(value)
        return result
    if isinstance(schema, list):
        return [_redact_schema(item) for item in schema]
    if isinstance(schema, str) and "@" in schema:
        return "<redacted>"
    return schema


def redact_model(model: ApiModel) -> ApiModel:
    redacted = copy.deepcopy(model)
    for endpoint in redacted.endpoints:
        for name, pattern in endpoint.query_parameters.items():
            if _is_sensitive_name(name):
                pattern.sample_values = ["<redacted>"]
        for pattern in endpoint.tokens.values():
            pattern.sample_values = ["<redacted>"]
        endpoint.request_schema = _redact_schema(endpoint.request_schema)
        endpoint.response_schema = _redact_schema(endpoint.response_schema)
        endpoint.websocket_schema = _redact_schema(endpoint.websocket_schema)
    return redacted


def endpoint_summary(model: ApiModel) -> list[dict[str, Any]]:
    return [
        {
            "endpoint": endpoint.key,
            "domain": endpoint.domain,
            "coverage": endpoint.coverage.to_dict(),
            "dependencies": [dependency.to_dict() for dependency in endpoint.dependencies],
            "tokens": {name: pattern.to_dict() for name, pattern in endpoint.tokens.items()},
        }
        for endpoint in model.endpoints
    ]
