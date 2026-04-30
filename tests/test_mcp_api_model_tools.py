from __future__ import annotations

import asyncio
import json

from mcp.server.fastmcp import FastMCP

from apiregen.har import HarEntry
from apiregen.mcp.store import HarStore
from apiregen.mcp.tools import register_tools


def sample_entry() -> HarEntry:
    return HarEntry(
        url="https://api.example.test/events/123?token=secret",
        method="GET",
        status=200,
        mime_type="application/json",
        request_headers={"authorization": ["Bearer secret"]},
        response_headers={"content-type": ["application/json"]},
        query_params={"token": "secret"},
        request_body=None,
        response_body='{"id":"123","name":"Match"}',
        cookies=[],
        timings={},
        session="s1",
    )


async def call_tool_text(mcp: FastMCP, name: str, arguments: dict) -> str:
    result = await mcp.call_tool(name, arguments)
    content_blocks = result[0]
    return content_blocks[0].text


def test_mcp_exposes_api_model_tools():
    mcp = FastMCP("test")
    store = HarStore()
    store.entries.append(sample_entry())
    store.sessions.add("s1")
    register_tools(mcp, store)

    tool_names = {tool.name for tool in asyncio.run(mcp.list_tools())}

    assert {
        "har_api_model",
        "har_openapi",
        "har_asyncapi",
        "har_coverage",
        "har_dependencies",
        "har_replay",
        "har_redacted_api_model",
    }.issubset(tool_names)


def test_mcp_api_model_and_replay_tools_return_json_and_redacted_curl():
    mcp = FastMCP("test")
    store = HarStore()
    store.entries.append(sample_entry())
    store.sessions.add("s1")
    register_tools(mcp, store)

    model_text = asyncio.run(call_tool_text(mcp, "har_api_model", {}))
    model = json.loads(model_text)
    replay_text = asyncio.run(call_tool_text(mcp, "har_replay", {"index": 0}))
    replay = json.loads(replay_text)

    assert model["endpoint_count"] == 1
    assert model["endpoints"][0]["path_template"] == "/events/{id}"
    assert "Bearer secret" not in replay["curl"]
    assert "token=<redacted>" in replay["curl"]
