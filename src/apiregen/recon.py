"""Raw data aggregation for HAR entries — no classification, no heuristics.

All intelligent analysis (domain classification, auth detection, protection
identification, stack detection) is done by Claude through the slash commands.
This module only counts and groups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from apiregen.har import HarEntry


@dataclass
class DomainInfo:
    domain: str
    request_count: int = 0
    content_types: set[str] = field(default_factory=set)
    methods: set[str] = field(default_factory=set)
    sample_paths: list[str] = field(default_factory=list)
    sessions_seen: set[str] = field(default_factory=set)


@dataclass
class ReconResult:
    domains: list[DomainInfo]
    total_entries: int
    session_count: int


def summarize(entries: list[HarEntry]) -> ReconResult:
    """Aggregate raw stats from HAR entries — no classification."""
    domains_map: dict[str, DomainInfo] = {}
    sessions: set[str] = set()

    for entry in entries:
        sessions.add(entry.session)
        domain = urlparse(entry.url).netloc
        if not domain:
            continue

        if domain not in domains_map:
            domains_map[domain] = DomainInfo(domain=domain)

        info = domains_map[domain]
        info.request_count += 1
        info.methods.add(entry.method)
        info.sessions_seen.add(entry.session)

        if entry.mime_type:
            info.content_types.add(entry.mime_type)

        path = urlparse(entry.url).path
        if path and len(info.sample_paths) < 5:
            if path not in info.sample_paths:
                info.sample_paths.append(path)

    domain_list = sorted(
        domains_map.values(),
        key=lambda d: -d.request_count,
    )

    return ReconResult(
        domains=domain_list,
        total_entries=len(entries),
        session_count=len(sessions),
    )
