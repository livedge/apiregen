"""MCP tool registrations for HAR investigation.

All 17 tools are registered via :func:`register_tools`, which captures the
:class:`HarStore` instance in closures — no module-level global state.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from apiregen.har import HarEntry
from apiregen.mcp.helpers import (
    domain_of,
    entry_summary,
    infer_schema,
    json_path_extract,
    path_of,
    truncate,
)
from apiregen.mcp.store import HarStore


def register_tools(mcp: FastMCP, store: HarStore) -> None:
    """Register all HAR investigation tools on *mcp*, closing over *store*."""

    @mcp.tool()
    def load_har(path: str) -> str:
        """Load HAR file(s) for investigation.

        Accepts a single ``.har`` file or a directory (loads all ``.har``
        files recursively).  Can be called multiple times to add more data.
        """
        p = Path(path)
        if p.is_file() and p.suffix.lower() == ".har":
            files = [p]
        elif p.is_dir():
            files = sorted(p.rglob("*.har"))
            if not files:
                return f"No .har files found in {path}"
        else:
            return f"Not found or not a .har file: {path}"

        count = store.load_paths(files)
        return json.dumps(
            {
                "loaded_entries": count,
                "files": [f.name for f in files],
                "total_entries": len(store.entries),
                "total_sessions": len(store.sessions),
            }
        )

    @mcp.tool()
    def har_clear() -> str:
        """Clear all loaded HAR data so you can start fresh."""
        n = store.clear()
        return f"Cleared {n} entries."

    @mcp.tool()
    def har_overview() -> str:
        """Summary statistics: request counts, status codes, methods, domains,
        content types, sessions, and body availability."""
        if err := store.ensure_loaded():
            return err

        methods = Counter(e.method for e in store.entries)
        status_groups = Counter(f"{e.status // 100}xx" for e in store.entries)
        statuses = Counter(e.status for e in store.entries)
        domains = Counter(domain_of(e.url) for e in store.entries)
        mime_types = Counter(e.mime_type for e in store.entries if e.mime_type)
        sessions = Counter(e.session for e in store.entries)

        return json.dumps(
            {
                "total_entries": len(store.entries),
                "sessions": dict(sessions.most_common()),
                "methods": dict(methods.most_common()),
                "status_groups": dict(status_groups.most_common()),
                "top_status_codes": dict(statuses.most_common(15)),
                "top_domains": dict(domains.most_common(30)),
                "top_content_types": dict(mime_types.most_common(15)),
                "entries_with_request_body": sum(
                    1 for e in store.entries if e.request_body
                ),
                "entries_with_response_body": sum(
                    1 for e in store.entries if e.response_body
                ),
                "total_response_bytes": sum(
                    len(e.response_body) for e in store.entries if e.response_body
                ),
                "loaded_files": store.loaded_files,
            },
            indent=2,
        )

    @mcp.tool()
    def har_domains() -> str:
        """List every domain contacted with request counts, HTTP methods,
        content types, status codes, session coverage, and sample paths."""
        if err := store.ensure_loaded():
            return err

        domain_data: dict[str, dict[str, Any]] = {}
        for e in store.entries:
            d = domain_of(e.url)
            if d not in domain_data:
                domain_data[d] = {
                    "domain": d,
                    "count": 0,
                    "methods": set(),
                    "content_types": set(),
                    "sessions": set(),
                    "status_codes": [],
                    "sample_paths": [],
                }
            info = domain_data[d]
            info["count"] += 1
            info["methods"].add(e.method)
            if e.mime_type:
                info["content_types"].add(e.mime_type)
            info["sessions"].add(e.session)
            info["status_codes"].append(e.status)
            path = path_of(e.url)
            if path and len(info["sample_paths"]) < 5 and path not in info["sample_paths"]:
                info["sample_paths"].append(path)

        result = []
        for info in sorted(domain_data.values(), key=lambda x: -x["count"]):
            sc = Counter(info["status_codes"])
            result.append(
                {
                    "domain": info["domain"],
                    "request_count": info["count"],
                    "methods": sorted(info["methods"]),
                    "content_types": sorted(info["content_types"]),
                    "sessions": sorted(info["sessions"]),
                    "session_count": len(info["sessions"]),
                    "status_codes": dict(sc.most_common(10)),
                    "sample_paths": info["sample_paths"],
                }
            )

        return json.dumps(result, indent=2)

    @mcp.tool()
    def har_search(
        domain: str | None = None,
        url_pattern: str | None = None,
        method: str | None = None,
        status_min: int | None = None,
        status_max: int | None = None,
        mime_type: str | None = None,
        session: str | None = None,
        has_request_body: bool | None = None,
        has_response_body: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """Search and filter HAR entries.  All filters are AND-combined.

        ``url_pattern`` is a regex.  Returns compact summaries with an
        ``index`` you can pass to ``har_get_entry`` / ``har_get_response_body``
        for full details.
        """
        if err := store.ensure_loaded():
            return err

        url_re = re.compile(url_pattern, re.IGNORECASE) if url_pattern else None

        matches: list[tuple[int, HarEntry]] = []
        for idx, entry in enumerate(store.entries):
            if domain and domain.lower() not in domain_of(entry.url).lower():
                continue
            if url_re and not url_re.search(entry.url):
                continue
            if method and entry.method.upper() != method.upper():
                continue
            if status_min is not None and entry.status < status_min:
                continue
            if status_max is not None and entry.status > status_max:
                continue
            if mime_type and mime_type.lower() not in (entry.mime_type or "").lower():
                continue
            if session and entry.session != session:
                continue
            if has_request_body is True and entry.request_body is None:
                continue
            if has_request_body is False and entry.request_body is not None:
                continue
            if has_response_body is True and entry.response_body is None:
                continue
            if has_response_body is False and entry.response_body is not None:
                continue
            matches.append((idx, entry))

        total = len(matches)
        page = matches[offset : offset + limit]

        return json.dumps(
            {
                "total_matches": total,
                "offset": offset,
                "limit": limit,
                "showing": len(page),
                "has_more": offset + limit < total,
                "entries": [entry_summary(i, e) for i, e in page],
            },
            indent=2,
        )

    @mcp.tool()
    def har_get_entry(index: int) -> str:
        """Full metadata for a single HAR entry: all request/response headers,
        query params, cookies, and timings.

        Bodies are **not** included -- use ``har_get_request_body`` or
        ``har_get_response_body`` to retrieve them separately.
        """
        if err := store.ensure_loaded():
            return err
        if index < 0 or index >= len(store.entries):
            return f"Invalid index {index}. Valid range: 0-{len(store.entries) - 1}"

        e = store.entries[index]
        return json.dumps(
            {
                "index": index,
                "url": e.url,
                "method": e.method,
                "status": e.status,
                "mime_type": e.mime_type,
                "session": e.session,
                "request_headers": dict(e.request_headers),
                "response_headers": dict(e.response_headers),
                "query_params": e.query_params,
                "cookies": e.cookies,
                "timings": e.timings,
                "request_body_size": len(e.request_body) if e.request_body else 0,
                "response_body_size": len(e.response_body) if e.response_body else 0,
            },
            indent=2,
        )

    @mcp.tool()
    def har_get_request_body(index: int, max_length: int = 10_000) -> str:
        """Retrieve the request body for a HAR entry.

        JSON bodies are pretty-printed.  Large bodies are truncated to
        ``max_length`` characters (default 10 000).
        """
        if err := store.ensure_loaded():
            return err
        if index < 0 or index >= len(store.entries):
            return f"Invalid index {index}. Valid range: 0-{len(store.entries) - 1}"

        e = store.entries[index]
        if e.request_body is None:
            return json.dumps({"index": index, "body": None, "message": "No request body"})

        body = e.request_body
        try:
            body = json.dumps(json.loads(body), indent=2)
        except (json.JSONDecodeError, ValueError):
            pass

        return json.dumps(
            {
                "index": index,
                "url": e.url[:200],
                "method": e.method,
                "content_type": ", ".join(e.request_headers.get("content-type", [])),
                "total_size": len(e.request_body),
                "truncated": len(body) > max_length,
                "body": truncate(body, max_length),
            },
            indent=2,
        )

    @mcp.tool()
    def har_get_response_body(
        index: int,
        max_length: int = 10_000,
        json_path: str | None = None,
    ) -> str:
        """Retrieve the response body for a HAR entry.

        JSON bodies are pretty-printed.  Use ``json_path`` for dot-notation
        extraction (e.g. ``data.items.0.name``).  Large bodies are truncated
        to ``max_length`` characters.
        """
        if err := store.ensure_loaded():
            return err
        if index < 0 or index >= len(store.entries):
            return f"Invalid index {index}. Valid range: 0-{len(store.entries) - 1}"

        e = store.entries[index]
        if e.response_body is None:
            return json.dumps(
                {"index": index, "body": None, "message": "No response body"}
            )

        body = e.response_body

        # JSON path extraction
        if json_path:
            try:
                parsed = json.loads(body)
                extracted = json_path_extract(parsed, json_path)
                return json.dumps(
                    {
                        "index": index,
                        "url": e.url[:200],
                        "json_path": json_path,
                        "value": extracted,
                    },
                    indent=2,
                    default=str,
                )
            except (json.JSONDecodeError, ValueError):
                return json.dumps(
                    {"error": "Response body is not valid JSON", "mime_type": e.mime_type}
                )

        # Pretty-print JSON
        try:
            body = json.dumps(json.loads(body), indent=2)
        except (json.JSONDecodeError, ValueError):
            pass

        return json.dumps(
            {
                "index": index,
                "url": e.url[:200],
                "status": e.status,
                "mime_type": e.mime_type,
                "total_size": len(e.response_body),
                "truncated": len(body) > max_length,
                "body": truncate(body, max_length),
            },
            indent=2,
        )

    @mcp.tool()
    def har_search_bodies(
        pattern: str,
        scope: str = "response",
        context_chars: int = 100,
        limit: int = 20,
    ) -> str:
        """Full-text regex search across request and/or response bodies.

        ``scope``: ``response`` (default), ``request``, or ``both``.
        Returns matching entries with context around each match.
        """
        if err := store.ensure_loaded():
            return err

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            return f"Invalid regex: {exc}"

        results: list[dict[str, Any]] = []
        for idx, entry in enumerate(store.entries):
            bodies: list[tuple[str, str]] = []
            if scope in ("response", "both") and entry.response_body:
                bodies.append(("response", entry.response_body))
            if scope in ("request", "both") and entry.request_body:
                bodies.append(("request", entry.request_body))

            for body_type, body in bodies:
                found = list(regex.finditer(body[:200_000]))
                if not found:
                    continue
                contexts = []
                for m in found[:3]:
                    start = max(0, m.start() - context_chars)
                    end = min(len(body), m.end() + context_chars)
                    contexts.append(
                        {
                            "match": m.group()[:200],
                            "context": body[start:end],
                            "position": m.start(),
                        }
                    )
                results.append(
                    {
                        "index": idx,
                        "url": entry.url[:200],
                        "method": entry.method,
                        "status": entry.status,
                        "session": entry.session,
                        "body_type": body_type,
                        "match_count": len(found),
                        "contexts": contexts,
                    }
                )
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

        return json.dumps(
            {
                "pattern": pattern,
                "scope": scope,
                "total_matches": len(results),
                "limit": limit,
                "entries": results,
            },
            indent=2,
        )

    @mcp.tool()
    def har_search_headers(
        name_pattern: str | None = None,
        value_pattern: str | None = None,
        scope: str = "both",
        limit: int = 30,
    ) -> str:
        """Search for HTTP headers by name and/or value regex.

        ``scope``: ``request``, ``response``, or ``both``.
        Useful for finding auth tokens, custom headers, CDN signatures, etc.
        """
        if err := store.ensure_loaded():
            return err

        name_re = re.compile(name_pattern, re.IGNORECASE) if name_pattern else None
        value_re = re.compile(value_pattern, re.IGNORECASE) if value_pattern else None

        results: list[dict[str, Any]] = []
        for idx, entry in enumerate(store.entries):
            header_sets: list[tuple[str, dict[str, list[str]]]] = []
            if scope in ("request", "both"):
                header_sets.append(("request", entry.request_headers))
            if scope in ("response", "both"):
                header_sets.append(("response", entry.response_headers))

            for header_type, headers in header_sets:
                for name, values in headers.items():
                    if name_re and not name_re.search(name):
                        continue
                    for val in values:
                        if value_re and not value_re.search(val):
                            continue
                        results.append(
                            {
                                "index": idx,
                                "url": entry.url[:150],
                                "session": entry.session,
                                "header_type": header_type,
                                "name": name,
                                "value": val[:500],
                            }
                        )
                        if len(results) >= limit:
                            return json.dumps(
                                {
                                    "total_shown": len(results),
                                    "limit": limit,
                                    "truncated": True,
                                    "matches": results,
                                },
                                indent=2,
                            )

        return json.dumps(
            {"total_shown": len(results), "matches": results}, indent=2
        )

    @mcp.tool()
    def har_endpoints(domain: str | None = None) -> str:
        """List unique API endpoints (method + path, ignoring query strings)
        grouped by domain.  Shows request count, sessions, and status codes
        per endpoint.  Optionally filter to a single domain."""
        if err := store.ensure_loaded():
            return err

        data: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(
            lambda: defaultdict(
                lambda: {"count": 0, "sessions": set(), "statuses": []}
            )
        )

        for entry in store.entries:
            d = domain_of(entry.url)
            if domain and domain.lower() not in d.lower():
                continue
            key = (entry.method, path_of(entry.url))
            info = data[d][key]
            info["count"] += 1
            info["sessions"].add(entry.session)
            info["statuses"].append(entry.status)

        result: dict[str, list[dict[str, Any]]] = {}
        for d in sorted(data):
            endpoints = []
            for (method, path), info in sorted(
                data[d].items(), key=lambda x: -x[1]["count"]
            ):
                sc = Counter(info["statuses"])
                endpoints.append(
                    {
                        "method": method,
                        "path": path,
                        "count": info["count"],
                        "sessions": sorted(info["sessions"]),
                        "status_codes": dict(sc.most_common(5)),
                    }
                )
            result[d] = endpoints

        return json.dumps(result, indent=2)

    @mcp.tool()
    def har_cookies(
        name_pattern: str | None = None, domain: str | None = None
    ) -> str:
        """Extract cookies from all HAR entries.

        Optionally filter by cookie ``name_pattern`` (regex) or ``domain``.
        Shows unique value count, sample values, sessions, and domains
        per cookie name.
        """
        if err := store.ensure_loaded():
            return err

        name_re = re.compile(name_pattern, re.IGNORECASE) if name_pattern else None

        cookie_data: dict[str, dict[str, set[str]]] = {}
        for entry in store.entries:
            d = domain_of(entry.url)
            if domain and domain.lower() not in d.lower():
                continue
            for cookie in entry.cookies:
                cname = cookie.get("name", "")
                if name_re and not name_re.search(cname):
                    continue
                if cname not in cookie_data:
                    cookie_data[cname] = {
                        "values": set(),
                        "sessions": set(),
                        "domains": set(),
                    }
                cookie_data[cname]["values"].add(cookie.get("value", "")[:200])
                cookie_data[cname]["sessions"].add(entry.session)
                cookie_data[cname]["domains"].add(d)

        result = []
        for name in sorted(cookie_data):
            info = cookie_data[name]
            vals = sorted(info["values"])
            result.append(
                {
                    "name": name,
                    "unique_values": len(vals),
                    "sample_values": vals[:5],
                    "sessions": sorted(info["sessions"]),
                    "domains": sorted(info["domains"]),
                }
            )

        return json.dumps(result, indent=2)

    @mcp.tool()
    def har_timing(sort_by: str = "total", limit: int = 20) -> str:
        """Request timing analysis.

        ``sort_by``: ``total``, ``wait`` (TTFB), ``dns``, or ``connect``.
        Returns the slowest individual requests and per-domain averages.
        """
        if err := store.ensure_loaded():
            return err

        def _total(timings: dict[str, Any]) -> float:
            return sum(
                max(0, v) for v in timings.values() if isinstance(v, (int, float))
            )

        def _sort_key(timings: dict[str, Any]) -> float:
            if sort_by in ("wait", "dns", "connect"):
                return max(0, timings.get(sort_by, 0))
            return _total(timings)

        indexed = [(i, e) for i, e in enumerate(store.entries) if e.timings]
        indexed.sort(key=lambda x: -_sort_key(x[1].timings))

        slowest = []
        for idx, entry in indexed[:limit]:
            slowest.append(
                {
                    "index": idx,
                    "url": entry.url[:200],
                    "method": entry.method,
                    "status": entry.status,
                    "total_ms": round(_total(entry.timings), 1),
                    "wait_ms": round(max(0, entry.timings.get("wait", 0)), 1),
                    "timings": entry.timings,
                }
            )

        domain_times: dict[str, list[float]] = defaultdict(list)
        for e in store.entries:
            if e.timings:
                domain_times[domain_of(e.url)].append(_total(e.timings))

        domain_avg = []
        for d, times in sorted(
            domain_times.items(), key=lambda x: -(sum(x[1]) / len(x[1]))
        ):
            domain_avg.append(
                {
                    "domain": d,
                    "avg_ms": round(sum(times) / len(times), 1),
                    "max_ms": round(max(times), 1),
                    "count": len(times),
                }
            )

        return json.dumps(
            {f"slowest_by_{sort_by}": slowest, "domain_averages": domain_avg},
            indent=2,
        )

    @mcp.tool()
    def har_compare_sessions(url_pattern: str) -> str:
        """Compare the same endpoint across sessions.

        Groups entries matching ``url_pattern`` (regex) by method + path,
        then shows per-session request counts, statuses, response sizes,
        and which headers / query-param values change between sessions.
        """
        if err := store.ensure_loaded():
            return err

        try:
            url_re = re.compile(url_pattern, re.IGNORECASE)
        except re.error as exc:
            return f"Invalid regex: {exc}"

        groups: dict[str, dict[str, list[tuple[int, HarEntry]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for idx, entry in enumerate(store.entries):
            if url_re.search(entry.url):
                key = f"{entry.method} {path_of(entry.url)}"
                groups[key][entry.session].append((idx, entry))

        if not groups:
            return f"No entries match pattern: {url_pattern}"

        result: dict[str, Any] = {}
        for endpoint, sessions in groups.items():
            if len(sessions) < 2:
                continue

            comparison: dict[str, Any] = {"sessions": {}}

            all_req_headers: dict[str, dict[str, set[str]]] = defaultdict(
                lambda: defaultdict(set)
            )
            all_query_vals: dict[str, set[str]] = defaultdict(set)

            for sess_name, entries_list in sessions.items():
                sample_idx, sample = entries_list[0]
                comparison["sessions"][sess_name] = {
                    "count": len(entries_list),
                    "sample_index": sample_idx,
                    "status": sample.status,
                    "response_size": (
                        len(sample.response_body) if sample.response_body else 0
                    ),
                }
                for _, e in entries_list:
                    for h, vals in e.request_headers.items():
                        for v in vals:
                            all_req_headers[h][sess_name].add(v)
                    for k, v in e.query_params.items():
                        all_query_vals[k].add(v)

            varying_headers: dict[str, Any] = {}
            for header, sess_vals in all_req_headers.items():
                all_values: set[str] = set()
                for vals in sess_vals.values():
                    all_values.update(vals)
                if len(all_values) > 1:
                    varying_headers[header] = {
                        s: sorted(v)[:3] for s, v in sess_vals.items()
                    }
            comparison["varying_headers"] = varying_headers
            comparison["query_param_values"] = {
                k: sorted(v)[:5] for k, v in all_query_vals.items()
            }
            result[endpoint] = comparison

        if not result:
            return (
                "Found matches but all are from a single session. "
                "Need captures from multiple sessions to compare."
            )

        return json.dumps(result, indent=2)

    @mcp.tool()
    def har_query_params(url_pattern: str) -> str:
        """Analyze query parameters for endpoints matching ``url_pattern``.

        Shows which parameters are constant vs varying, value counts,
        and sample values.
        """
        if err := store.ensure_loaded():
            return err

        try:
            url_re = re.compile(url_pattern, re.IGNORECASE)
        except re.error as exc:
            return f"Invalid regex: {exc}"

        param_values: dict[str, list[str]] = defaultdict(list)
        match_count = 0

        for entry in store.entries:
            if url_re.search(entry.url):
                match_count += 1
                for k, v in entry.query_params.items():
                    param_values[k].append(v)

        if not match_count:
            return f"No entries match pattern: {url_pattern}"

        params: dict[str, Any] = {}
        for param, values in sorted(param_values.items()):
            unique = sorted(set(values))
            info: dict[str, Any] = {
                "occurrences": len(values),
                "unique_values": len(unique),
                "constant": len(unique) == 1,
            }
            if len(unique) == 1:
                info["value"] = unique[0]
            elif len(unique) <= 10:
                info["values"] = unique
            else:
                info["sample_values"] = unique[:10]
            params[param] = info

        return json.dumps(
            {
                "pattern": url_pattern,
                "matching_entries": match_count,
                "parameters": params,
            },
            indent=2,
        )

    @mcp.tool()
    def har_response_schema(url_pattern: str, limit: int = 10) -> str:
        """Infer a JSON response schema from multiple samples matching
        ``url_pattern``.

        Examines up to ``limit`` JSON responses and reports field names,
        types, optionality (present in N/M samples), array lengths, and
        sample scalar values.  Great for understanding API structure before
        writing code.
        """
        if err := store.ensure_loaded():
            return err

        try:
            url_re = re.compile(url_pattern, re.IGNORECASE)
        except re.error as exc:
            return f"Invalid regex: {exc}"

        samples: list[Any] = []
        sample_entries: list[dict[str, Any]] = []
        for idx, entry in enumerate(store.entries):
            if url_re.search(entry.url) and entry.response_body:
                try:
                    parsed = json.loads(entry.response_body)
                    samples.append(parsed)
                    sample_entries.append(
                        {"index": idx, "session": entry.session, "status": entry.status}
                    )
                    if len(samples) >= limit:
                        break
                except (json.JSONDecodeError, ValueError):
                    continue

        if not samples:
            return f"No JSON responses found matching: {url_pattern}"

        schema = infer_schema(samples)
        return json.dumps(
            {
                "pattern": url_pattern,
                "sample_count": len(samples),
                "samples_from": sample_entries,
                "schema": schema,
            },
            indent=2,
        )
