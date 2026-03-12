"""MCP server for deep investigation of HAR (HTTP Archive) captures.

Exposes tools for loading, searching, filtering, and analyzing captured
HTTP traffic.  Designed to be used from Claude Code or any MCP client.

Start with ``load_har`` to ingest HAR files, then use the other tools
to explore domains, search bodies/headers, inspect individual entries,
compare sessions, and infer response schemas.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from apiregen.mcp import HarStore, register_tools

mcp = FastMCP(
    "apiregen-har",
    instructions=(
        "Investigate HTTP traffic from HAR captures. "
        "Load HAR files first with load_har, then use other tools to "
        "search, filter, and analyze the recorded traffic."
    ),
)

store = HarStore()
register_tools(mcp, store)


def main() -> None:
    """Run the MCP server over stdio."""
    har_path = os.environ.get("APIREGEN_HAR_PATH")
    if har_path:
        p = Path(har_path)
        if p.is_file():
            store.load_paths([p])
        elif p.is_dir():
            store.load_paths(sorted(p.rglob("*.har")))

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
