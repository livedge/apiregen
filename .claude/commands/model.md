---
description: "Build the clustered API model and generate OpenAPI/AsyncAPI specs from captured HAR traffic."
allowed-tools: mcp__apiregen-har__load_har, mcp__apiregen-har__har_api_model, mcp__apiregen-har__har_redacted_api_model, mcp__apiregen-har__har_openapi, mcp__apiregen-har__har_asyncapi, mcp__apiregen-har__har_coverage, mcp__apiregen-har__har_dependencies, mcp__apiregen-har__har_endpoint_summary, mcp__apiregen-har__har_replay
---

# API Model

Build the machine-readable API model from captured HAR traffic.

## Input

The user should provide a HAR file path or a directory containing HAR files. If not provided, ask for it.

## Procedure

1. Use `load_har` to load the captures.
2. Call `har_api_model` with `redact=true` to cluster endpoints and inspect the model.
3. Call `har_coverage` to identify low-confidence endpoints and capture gaps.
4. Call `har_dependencies` to identify endpoint chaining such as list/search responses feeding detail endpoint IDs.
5. Call `har_openapi` for REST/RPC endpoints.
6. Call `har_asyncapi` when WebSocket messages were captured.
7. Use `har_replay` for representative entry indices when the user wants runnable curl examples.

## Output

Summarize:

- Endpoint groups and path templates
- Inferred path/query parameters
- Request and response schemas
- Token/session behavior
- Endpoint dependencies
- Coverage confidence and gaps
- Generated artifact recommendations: `api-model.json`, `openapi.json`, `asyncapi.json`

Do not include raw secrets. Use redacted tool output by default.
