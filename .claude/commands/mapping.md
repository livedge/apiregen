---
description: "Phase 2 — MAPPING: Build rich sample sets across sessions. Differential analysis of endpoints, tokens, and response patterns."
allowed-tools: mcp__apiregen-har__load_har, mcp__apiregen-har__har_clear, mcp__apiregen-har__har_overview, mcp__apiregen-har__har_search, mcp__apiregen-har__har_endpoints, mcp__apiregen-har__har_get_entry, mcp__apiregen-har__har_get_request_body, mcp__apiregen-har__har_get_response_body, mcp__apiregen-har__har_compare_sessions, mcp__apiregen-har__har_query_params, mcp__apiregen-har__har_response_schema, mcp__apiregen-har__har_search_headers, mcp__apiregen-har__har_search_bodies, mcp__apiregen-har__har_cookies, mcp__apiregen-har__har_domains
---

# Phase 2 — MAPPING

You are performing Phase 2 (Mapping) of the API reverse engineering workflow. Your goal is to build a **Sample Catalog** — a rich, annotated collection of endpoint behaviors observed across multiple sessions.

## Prerequisites

Phase 1 (Recon) should be complete. The user should have a Page Context Document identifying the key API domains and endpoints. If not, suggest running `/recon` first.

The user needs **multiple HAR captures from separate sessions** to enable differential analysis. If they only have one, explain why multiple sessions matter and guide them to capture more.

## Input

The user will provide:
1. **HAR files from multiple sessions** — path to a directory or multiple file paths
2. **Endpoints of interest** — which API endpoints or domains to focus on (from the Recon phase)

If the user hasn't provided these, ask for them.

## Procedure

### Step 1 — Load all sessions

1. Call `har_clear` to start fresh.
2. Call `load_har` for each HAR file or the directory containing them.
3. Confirm: number of entries, sessions, and files loaded.
4. Call `har_overview` to verify multi-session coverage.

### Step 2 — Endpoint inventory

1. Call `har_endpoints` for each API domain of interest.
2. For each endpoint, note: request count, which sessions it appears in, status codes.
3. Flag endpoints that only appear in one session — these have lower confidence.

### Step 3 — Cross-session differential analysis

For each key endpoint (prioritize those serving the user's data of interest):

1. Call `har_compare_sessions` with a URL pattern matching the endpoint.
2. Analyze the results:
   - **Varying headers** — which headers change between sessions? These are likely tokens, session IDs, or cache-busters.
   - **Stable headers** — which stay the same? These are likely API keys, client identifiers, or static config.
   - **Query param variance** — which params change (dynamic) vs stay constant (config/static)?
   - **Response size shifts** — significant size changes suggest different data (e.g., new events added).

### Step 4 — Token & session lifecycle

1. Call `har_search_headers` to find auth-related headers across all sessions.
2. Call `har_cookies` to analyze cookie patterns.
3. For each token/cookie identified:
   - Does it persist across sessions or rotate?
   - Does it change per-request within a session?
   - Estimate rotation cadence: per-session, per-request, time-based?
4. Identify nonces, signatures, and cache-busters in query params using `har_query_params`.

### Step 5 — Request pattern analysis

For each key endpoint:
1. Use `har_search` to find all instances, then `har_get_entry` on samples from different sessions.
2. Document:
   - Required vs optional headers
   - Fixed vs dynamic query parameters
   - Request body patterns (for POST/PUT) — use `har_get_request_body`
   - URL path parameters (IDs, slugs that change)

### Step 6 — Response pattern analysis

For each key endpoint:
1. Call `har_response_schema` to infer the JSON structure from multiple samples.
2. Use `har_get_response_body` with `json_path` to drill into specific fields.
3. Document:
   - Fields always present vs sometimes missing (check the "present_in" ratios)
   - Field value types and ranges
   - Response size variance
   - Different response shapes (success vs error, empty vs populated)
   - Array length ranges (pagination indicators)

### Step 7 — Dependency mapping

Identify dependencies between endpoints:
1. Look for IDs in one endpoint's response that appear as path parameters or query params in another.
2. Use `har_search_bodies` to find specific ID values across multiple endpoint responses.
3. Document the call chain: "You need `eventId` from endpoint A to call endpoint B."

### Step 8 — Gap analysis

Assess what's missing:
- Endpoints only seen in one session
- No error responses captured
- Pagination not fully explored
- Response shapes only seen for one category of data (e.g., only football, not hockey)
- Token rotation pattern unclear due to insufficient sessions

## Output

Produce a **Sample Catalog** with these sections for each key endpoint:

### Per-Endpoint Card

```
## [METHOD] /path/to/endpoint

**Domain:** api.example.com
**Seen in:** 3/3 sessions (high confidence)
**Status codes observed:** 200 (12x), 304 (3x)

### Request Pattern
- **Required headers:** Accept, Authorization, X-Client-ID
- **Dynamic headers:** Authorization (rotates per-session), X-Request-ID (per-request)
- **Query params:** lang=sk (constant), _ts=1709... (cache-buster, per-request)
- **Path params:** {sportId} — integer, seen values: 1, 2, 5

### Response Pattern
- **Shape:** JSON object with `data` array and `meta` object
- **Fields:** [schema summary from har_response_schema]
- **Array sizes:** 3–287 items
- **Key fields for user:** eventName, odds, startTime

### Token Requirements
- Authorization: Bearer token, rotates per-session, obtained from [source]
- Cookie: session_id, persists within session

### Dependencies
- Requires sportId from /api/sports endpoint
- eventId from response used by /api/events/{eventId}/detail
```

### Cross-Cutting Sections

1. **Token Lifecycle Summary** — all tokens, their rotation patterns, and how to obtain them
2. **Endpoint Dependency Graph** — which endpoints depend on data from others
3. **Confidence Assessment** — per-endpoint confidence rating based on sample count
4. **Gaps & Recommendations** — what additional captures would improve confidence
