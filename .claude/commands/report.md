---
description: "Phase 3 — REPORT: Synthesize recon and mapping into a complete API Intelligence Report."
allowed-tools: mcp__apiregen-har__load_har, mcp__apiregen-har__har_overview, mcp__apiregen-har__har_domains, mcp__apiregen-har__har_endpoints, mcp__apiregen-har__har_search, mcp__apiregen-har__har_get_entry, mcp__apiregen-har__har_get_request_body, mcp__apiregen-har__har_get_response_body, mcp__apiregen-har__har_compare_sessions, mcp__apiregen-har__har_query_params, mcp__apiregen-har__har_response_schema, mcp__apiregen-har__har_search_headers, mcp__apiregen-har__har_search_bodies, mcp__apiregen-har__har_cookies, mcp__apiregen-har__har_timing, mcp__apiregen-har__har_clear
---

# Phase 3 — REPORT

You are performing Phase 3 (Report) of the API reverse engineering workflow. Your goal is to produce an **API Intelligence Report** — a complete, human-readable document that synthesizes everything from Recon and Mapping into actionable intelligence.

## Prerequisites

Phases 1 (Recon) and 2 (Mapping) should ideally be complete. If the user is running this directly, you'll need to perform the analysis yourself using the HAR data.

## Input

The user will provide:
1. **HAR files** — all captures (path to directory or files)
2. **Target description** — what site and what data they want (if not already known from prior phases)
3. **Prior phase outputs** — Page Context Document and/or Sample Catalog (if available in conversation)

If no prior phases were run, load the HAR data and perform a condensed recon + mapping analysis before writing the report.

## Procedure

### Step 1 — Ensure data is loaded

1. Call `load_har` with all available captures.
2. Call `har_overview` to confirm coverage.
3. If only one session is loaded, note this limits differential analysis.

### Step 2 — Gather all intelligence

If prior phase outputs are available in conversation, use those. Otherwise, run these analyses:

1. `har_domains` — full domain classification
2. `har_endpoints` — for each API domain
3. `har_compare_sessions` — for each key endpoint pattern
4. `har_response_schema` — for each key endpoint
5. `har_search_headers` — auth and protection headers
6. `har_cookies` — session/auth cookies
7. `har_timing` — performance characteristics
8. `har_query_params` — for key endpoints

### Step 3 — Write the report

Produce the report following the structure below. Write for a human reader — clear, practical, no jargon without explanation.

## Report Structure

---

### Site Overview

One paragraph in plain language. Example tone: "tipsport.cz is an Angular-based betting platform. Event and odds data is served from `api.tipsport.cz/rest/` via REST endpoints. Live scores are delivered over a SignalR WebSocket on `live.tipsport.cz`. The site sits behind Cloudflare but API calls from an authenticated session are not challenged."

Cover: what the site is, what framework it uses, where the interesting data lives, overall architecture.

---

### Data Source Map

Directly answer the user's original question: "For each piece of data you wanted, here's exactly where it lives."

Present as a table:

| Data | Source | Endpoint | Notes |
|------|--------|----------|-------|
| Events | REST API | GET /api/v1/events | Returns paginated list |
| Odds | Embedded in events | (same) | Nested under `odds` field |
| Live scores | WebSocket | wss://live.example.com | Push updates |

---

### Endpoint Catalog

For each discovered API endpoint, provide:

- **Plain-language description** of what it does
- **Full URL pattern** with path parameters marked
- **Method** (GET/POST/etc.)
- **Parameters** it accepts (query params, path params, request body shape)
- **Response shape** — high-level description (not full schema, but key fields and structure)
- **Confidence rating** — based on how many samples were observed
- **Dependencies** — what you need from other endpoints to call this one

Group endpoints logically (by resource type or domain), not just alphabetically.

---

### Auth & Token Summary

Practical, actionable assessment:

- What tokens/cookies are required to make API calls
- How each is obtained (login endpoint? embedded in page? cookie from initial load?)
- Rotation cadence (per-session, per-request, time-based, or persistent)
- Can this be replicated programmatically, or is it tied to browser JS execution?
- Are there endpoints that work without authentication?

---

### Real-time Data Summary

If WebSocket/SSE connections were detected:

- Connection URL and protocol
- How to subscribe (message format, subscription payload)
- What data is pushed and how frequently
- Message format (JSON, protobuf, custom framing)

If none detected, state that clearly.

---

### Protection & Feasibility Assessment

**Be honest.** This is the most important section for the user's decision-making.

- What protections are in place (CDN/WAF, CAPTCHA, fingerprinting, request signing)
- What's straightforward to replicate programmatically
- What requires workarounds (headless browser, proxy rotation, etc.)
- **Hard blockers** if any exist — say so clearly
- Rate limiting signals observed (429 responses, retry-after headers, throttling patterns)
- Overall feasibility rating: Easy / Moderate / Difficult / Impractical

---

### Behavioral Notes

Operational details that matter for implementation:

- Observed polling intervals
- Pagination strategy (offset, cursor, page number) and defaults
- Sorting defaults
- Data freshness observations (how quickly do values change between captures?)
- API quirks: inconsistent field names, different schemas per category, undocumented behaviors
- Response caching patterns (cache headers, ETags)

---

### Gaps & Unknowns

What we couldn't determine or didn't capture:

- Endpoints only seen once (shape may vary)
- Error response format unknown
- Pagination limits untested
- Auth token source unclear
- Specific data categories not captured

For each gap, suggest what additional capture would fill it.

---

### Recommended Next Steps

Prioritized list of what to do next:

1. Additional captures needed (if any)
2. Which endpoints to target for code generation — suggest running `/typegen` with specific endpoint patterns and target language
3. Auth flow to implement first
4. Suggested approach (direct HTTP, headless browser, hybrid)

---

## Formatting

- Use markdown throughout
- Use tables for structured data (domain maps, endpoint catalogs)
- Use code blocks for URL patterns, header values, JSON shapes
- Keep language practical and direct — this report is for decision-making, not academic documentation
- Bold key findings and warnings
