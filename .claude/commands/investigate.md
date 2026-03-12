---
description: "Deep-dive into a specific endpoint, domain, or pattern in the loaded HAR data."
allowed-tools: mcp__apiregen-har__load_har, mcp__apiregen-har__har_overview, mcp__apiregen-har__har_search, mcp__apiregen-har__har_endpoints, mcp__apiregen-har__har_get_entry, mcp__apiregen-har__har_get_request_body, mcp__apiregen-har__har_get_response_body, mcp__apiregen-har__har_compare_sessions, mcp__apiregen-har__har_query_params, mcp__apiregen-har__har_response_schema, mcp__apiregen-har__har_search_headers, mcp__apiregen-har__har_search_bodies, mcp__apiregen-har__har_cookies, mcp__apiregen-har__har_timing, mcp__apiregen-har__har_domains
---

# Investigate

You are performing a focused investigation of specific endpoints or patterns in captured HAR data. This is an ad-hoc deep-dive tool — use it when the user wants to explore something specific rather than running a full phase.

## Input

The user will provide one or more of:
- **A URL pattern or endpoint** to investigate (e.g., `/api/v1/events`, `graphql`, a domain name)
- **A search term** to find in headers or bodies (e.g., a specific token name, field value, error message)
- **A question** about the captured traffic (e.g., "how does pagination work?", "what auth is needed for the odds endpoint?")

If HAR data is not already loaded, ask the user for the path and load it first.

## Investigation Strategies

Choose the appropriate strategy based on what the user is asking:

### Endpoint deep-dive
When the user wants to understand a specific endpoint:
1. `har_search` with `url_pattern` to find all instances
2. `har_get_entry` on a representative sample to see full headers, params, cookies
3. `har_get_request_body` if it has a request body (POST/PUT)
4. `har_get_response_body` to see the response, using `json_path` to drill into nested structures
5. `har_response_schema` to infer the full response shape across multiple samples
6. `har_query_params` to understand parameter patterns
7. `har_compare_sessions` if multiple sessions are available — show what changes

### Auth investigation
When the user wants to understand authentication:
1. `har_search_headers` with auth-related header name patterns
2. `har_cookies` to find session/auth cookies
3. `har_compare_sessions` to see which tokens rotate between sessions
4. `har_get_entry` on requests to login or token endpoints
5. `har_search_bodies` to find tokens embedded in HTML or JS responses

### Data hunting
When the user wants to find where specific data lives:
1. `har_search_bodies` with the data term as pattern (e.g., a product name, a specific ID)
2. For each match, `har_get_entry` to see which endpoint returned it
3. `har_get_response_body` with `json_path` to understand the data structure
4. `har_response_schema` to see the full schema

### Performance investigation
When the user asks about timing or performance:
1. `har_timing` sorted by total, wait, or connect time
2. `har_search` filtered to specific domains to see request patterns
3. Look for polling patterns (repeated calls to same endpoint)

### Comparison investigation
When the user wants to understand differences:
1. `har_compare_sessions` with relevant URL pattern
2. `har_get_response_body` on matching entries from different sessions
3. Highlight: what changed (dynamic data) vs what stayed the same (structure, static config)

## Output

Provide findings in a clear, structured format:
- Lead with the answer to the user's question
- Show evidence (relevant headers, response excerpts, patterns found)
- Note confidence level based on sample count
- Suggest follow-up investigations if the picture is incomplete
- Use code blocks for URLs, headers, JSON structures
