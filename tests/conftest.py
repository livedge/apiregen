"""Shared test fixtures."""

from __future__ import annotations

import pytest

from apiregen.har import HarEntry


@pytest.fixture()
def make_entry():
    """Factory fixture for creating HarEntry instances with sensible defaults."""

    def _make(
        url: str = "https://api.example.com/data",
        method: str = "GET",
        status: int = 200,
        mime_type: str = "application/json",
        request_headers: dict[str, list[str]] | None = None,
        response_headers: dict[str, list[str]] | None = None,
        query_params: dict[str, str] | None = None,
        request_body: str | None = None,
        response_body: str | None = None,
        cookies: list[dict] | None = None,
        timings: dict | None = None,
        session: str = "session1",
    ) -> HarEntry:
        return HarEntry(
            url=url,
            method=method,
            status=status,
            mime_type=mime_type,
            request_headers=request_headers or {},
            response_headers=response_headers or {},
            query_params=query_params or {},
            request_body=request_body,
            response_body=response_body,
            cookies=cookies or [],
            timings=timings or {},
            session=session,
        )

    return _make
