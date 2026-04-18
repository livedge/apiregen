# ApiRegen

API reverse engineering toolkit for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Capture web traffic as HAR files, then let Claude analyze the endpoints, classify domains, detect auth patterns, reverse engineer GraphQL/REST/WebSocket APIs, and generate typed client code.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Install

```bash
claude plugin marketplace add livedge/apiregen
claude plugin install apiregen
```

Restart Claude Code. Done.

## Usage

Open Claude Code in any project directory and use the slash commands.

### Slash commands

| Command | What it does |
|---------|-------------|
| `/capture` | Walks you through capturing web traffic as HAR files |
| `/recon` | Phase 1 — analyze traffic: domains, auth, protection, stack |
| `/mapping` | Phase 2 — cross-session differential analysis |
| `/report` | Phase 3 — full API intelligence report |
| `/schema` | Infer JSON response schema for specific endpoints |
| `/typegen` | Phase 4 — generate typed classes (TypeScript, C#, Python, etc.) |
| `/investigate` | Ad-hoc deep-dive into specific endpoints |

### Specialist agents (auto-triggered)

`/recon` automatically dispatches these agents when specific signals are detected — no extra command needed:

| Agent | Auto-triggers on |
|-------|-----------------|
| `rest-api-specialist` | Versioned REST paths (`/api/v1/`), `{data, meta}` envelopes, offset/limit/cursor pagination, Bearer/API-key auth, axios/fetch/Retrofit/OkHttp client signatures |
| `graphql-specialist` | `/graphql` endpoints with `{query, variables}` bodies, GraphQL AST literals in JS bundles, persisted queries (`documentId`, `sha256Hash`), Apollo/Relay/urql client imports |
| `websocket-specialist` | WebSocket upgrade handshakes, `ws://`/`wss://` URLs, graphql-ws / socket.io / SignalR / STOMP / MQTT subprotocols, binary frames (Protobuf/MessagePack), live/real-time data |

Multiple specialists can apply to the same target (e.g., REST for data + WebSocket for live updates).

### Typical workflow

1. `/capture` — capture traffic from target site (browser DevTools, Camoufox, or mitmproxy)
2. `/recon` — Claude analyzes the traffic and builds a context profile
3. `/mapping` — repeat captures across sessions; Claude flags static vs dynamic patterns
4. `/report` — Claude writes a complete API intelligence report
5. `/typegen` — generate typed client code from discovered endpoints

## MCP tools

The plugin ships an MCP server (`apiregen-har`) with 18 tools Claude uses behind the scenes:

**Loading & overview** — `load_har`, `har_clear`, `har_overview`, `har_domains`, `har_endpoints`
**Inspection** — `har_get_entry`, `har_get_request_body`, `har_get_response_body`
**Search** — `har_search`, `har_search_bodies`, `har_search_headers`
**Analysis** — `har_cookies`, `har_timing`, `har_query_params`, `har_response_schema`, `har_compare_sessions`
**Type generation** — `quicktype`, `quicktype_schema`

All intelligent analysis (domain classification, auth detection, protection identification, endpoint semantics) is performed by Claude — the Python code only parses and queries.

## Standalone CLI (optional)

For use outside Claude Code:

```bash
# Install with CLI dependencies
uv tool install apiregen[cli]

# Guided interactive workflow
apiregen start

# Individual commands
apiregen init myproject                              # create .apiregen/ project
apiregen capture -m browser                          # capture via Camoufox (stealth)
apiregen capture -m mitmproxy                        # capture via mitmproxy
apiregen flows-to-har session.flows                  # convert mitmproxy flows to HAR
apiregen extract-source capture.har                  # pull HTML/JS from HAR
apiregen recon myproject                             # raw traffic summary
apiregen mcp myproject                               # run MCP server standalone
```

Add browser capture: `uv tool install apiregen[cli,browser]`
Add mitmproxy support: `uv tool install apiregen[cli,mitmproxy]`
Everything: `uv tool install apiregen[all]`

## Project structure

```
src/apiregen/
├── cli.py                  # Click CLI: start, init, capture, flows-to-har,
│                           #   extract-source, mcp, recon
├── guided.py               # Interactive guided workflow
├── project.py              # .apiregen/ project discovery + init
├── har.py                  # HAR parser, HarEntry dataclass
├── recon.py                # Phase 1 recon — typed dataclass results
├── mcp_server.py           # MCP server entry point
├── capture/
│   ├── browser.py          # Camoufox-backed capture + source extraction
│   └── mitmproxy.py        # mitmproxy capture
├── mcp/
│   ├── store.py            # HarStore — encapsulated HAR state
│   ├── helpers.py          # Pure helpers (truncate, infer_schema, ...)
│   ├── tools.py            # 16 HAR investigation tools
│   └── quicktype.py        # 2 QuickType bridge tools
└── rendering/
    └── recon.py            # Rich-based CLI output for recon

.claude/
├── commands/               # 7 slash commands (.md)
└── agents/                 # 3 specialist agents (.md)

.claude-plugin/
├── plugin.json             # Plugin manifest
└── marketplace.json        # Marketplace entry

tests/                      # pytest scaffolding
```

An `.apiregen/` project directory contains:

```
.apiregen/
├── project.json            # target url, type, metadata
├── captures/               # HAR files, one per session
└── source/                 # extracted HTML + JS bundles
```

## How analysis works

The MCP server exposes the *data*; Claude provides the *intelligence*. A typical investigation loop:

1. Claude calls `load_har` to ingest captures
2. `har_overview` / `har_domains` reveal the API surface
3. `har_endpoints` + `har_search` narrow to interesting calls
4. `har_get_response_body` + `har_response_schema` sample payloads
5. `har_compare_sessions` separates static config from per-session tokens
6. `quicktype` turns approved samples into typed classes in the user's target language

Supported QuickType languages: ruby, javascript, flow, rust, kotlin, dart, python, csharp, go, cpp, java, scala3, typescript, swift, objc, elm, schema, pike, haskell, php.

## License

MIT
