# API Reverse Engineering Toolkit

## Project Overview

ApiRegen is an interactive API reverse engineering toolkit for MCP-compatible AI assistants and standalone CLI workflows. Users capture web traffic as HAR files, then the assistant uses the MCP tools in this repository to inspect requests, responses, headers, cookies, sessions, schemas, and endpoint behavior.

The Python code intentionally exposes data and low-level analysis primitives. Higher-level interpretation such as domain classification, auth assessment, protection detection, and endpoint semantics is done by the assistant using the captured traffic.

## Core Workflow

1. Capture traffic into `.har` files using browser DevTools, Camoufox, mitmproxy, or another compatible capture tool.
2. Load captures through the `apiregen-har` MCP server or the standalone CLI.
3. Build a page context profile from the traffic.
4. Compare multiple sessions to separate static values from dynamic tokens, cache busters, user inputs, and changing data.
5. Produce an API intelligence report.
6. Build a clustered API model with endpoint templates, schemas, token behavior, dependencies, replay commands, and coverage scores.
7. Generate OpenAPI/AsyncAPI definitions and typed client models from approved samples.

## Project Data Layout

All project data lives under `.apiregen/`:

```text
.apiregen/
├── config.json
├── captures/
├── source/
└── reports/
```

## Design Principles

- The user defines scope; captured traffic provides the evidence.
- Do not assume the API domain matches the page domain.
- Prefer multiple capture sessions before making claims about dynamic behavior.
- Report hard blockers and anti-automation protections early.
- Treat the API definition and report as the primary artifacts; generated code is derived from them.

## Compatibility

Claude Code consumes `CLAUDE.md`, slash commands, and plugin metadata from this repository. Other agents should treat this `AGENTS.md`, the README, and the MCP tool descriptions as the generic entry points.
