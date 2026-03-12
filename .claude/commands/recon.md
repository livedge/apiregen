---
description: "Phase 1 — RECON: Analyze captured traffic to build a comprehensive context profile of the target site."
allowed-tools: mcp__apiregen-har__load_har, mcp__apiregen-har__har_overview, mcp__apiregen-har__har_domains, mcp__apiregen-har__har_endpoints, mcp__apiregen-har__har_search_headers, mcp__apiregen-har__har_search_bodies, mcp__apiregen-har__har_cookies, mcp__apiregen-har__har_get_entry, mcp__apiregen-har__har_get_response_body, mcp__apiregen-har__har_clear
---

# Phase 1 — RECON

You are performing Phase 1 (Recon) of the API reverse engineering workflow. Your goal is to build a **Page Context Document** — a comprehensive profile of the target site derived entirely from captured HAR traffic.

## Input

The user will provide:
1. **Target page** — the URL they want to reverse-engineer
2. **Data of interest** — what they want to extract (e.g., events, odds, products, prices)
3. **HAR file(s)** — path to a `.har` file or a directory containing them

If the user hasn't provided all three, ask for the missing pieces before proceeding.

## Procedure

### Step 1 — Load the capture

Use `load_har` to ingest the HAR file(s). Confirm how many entries and sessions were loaded.

### Step 2 — Overview & domain classification

1. Call `har_overview` to get summary statistics.
2. Call `har_domains` to list every domain contacted.
3. Classify each domain into one of these categories:
   - **Data API** — serves JSON/XML responses, dynamic data the user cares about
   - **Static assets** — JS bundles, CSS, images, fonts
   - **Analytics/Tracking** — Google Analytics, Facebook Pixel, Hotjar, Sentry, etc.
   - **CDN** — content delivery, caching layers
   - **Other** — anything that doesn't fit above
4. Identify which domains are likely to serve the data the user asked about. Remember: the API domain may be completely different from the target page domain.

### Step 3 — API surface analysis

For each domain classified as Data API:
1. Call `har_endpoints` filtered to that domain to list all unique endpoints.
2. Determine the API style: REST, GraphQL, RPC, or mixed.
   - Look for `/graphql` paths or `query`/`mutation` in request bodies.
   - Look for RESTful path patterns with resource names and IDs.
3. Identify base URL patterns (e.g., `api.example.com/v2/...`).

### Step 4 — Auth & session detection

1. Call `har_search_headers` with `name_pattern` matching common auth headers: `authorization`, `x-auth`, `x-api-key`, `x-csrf`, `x-xsrf`, `bearer`.
2. Call `har_cookies` to find session/auth cookies (look for names containing: token, auth, session, csrf, jwt, sid).
3. Determine:
   - Auth mechanism: cookies, bearer tokens, API keys, or combination
   - Whether public data flows without authentication
   - Any tokens embedded in the initial page load

### Step 5 — Protection layer detection

1. Call `har_search_headers` looking for CDN/WAF signatures:
   - Cloudflare: `cf-ray`, `cf-cache-status`
   - Akamai: `x-akamai`
   - Fastly: `x-served-by`, `x-fastly`
   - AWS CloudFront: `x-amz-cf`
   - Imperva: `x-iinfo`
2. Call `har_search_bodies` with `pattern` looking for CAPTCHA scripts: `recaptcha`, `hcaptcha`, `turnstile`, `challenges.cloudflare`.
3. Look for browser fingerprinting or request signing patterns in headers.

### Step 6 — Real-time layer detection

1. Call `har_search_headers` with `name_pattern="upgrade"` and `value_pattern="websocket"` to find WebSocket connections.
2. Call `har_search` with `mime_type="event-stream"` to find SSE connections.
3. For any real-time connections found, note the domain, path, and protocol hints.

### Step 7 — Frontend stack detection

1. Call `har_search_bodies` in response bodies looking for framework signatures:
   - React: `__REACT`, `_reactRootContainer`, `react-dom`
   - Angular: `ng-version`, `ng-app`, `angular`
   - Vue: `__VUE`, `vue-router`, `vuex`
   - Next.js: `__NEXT_DATA__`, `_next/`
   - Nuxt: `__NUXT__`
2. Look at the JS bundle URLs and content types for clues about the HTTP client library (axios, fetch wrappers).

## Output

Produce a **Page Context Document** with these sections:

### 1. Site Overview
One-paragraph plain-language summary of what the site is, what stack it uses, and where data comes from.

### 2. Domain Map
Table of every domain contacted, classified by category, with request counts.

### 3. API Surface
- Data API domains and their base URL patterns
- API style (REST / GraphQL / RPC / mixed)
- Key endpoints that likely serve the user's data of interest

### 4. Auth & Session
- Auth mechanism identified
- Required tokens/cookies
- Whether public data is accessible without auth

### 5. Protection Layer
- CDN/WAF detected
- CAPTCHA presence
- Anti-bot measures
- Initial feasibility assessment

### 6. Real-time Layer
- WebSocket/SSE connections found
- Domains and protocols

### 7. Frontend Stack
- Framework, HTTP client, state management hints

### 8. Recommended Next Steps
- Which endpoints to focus on in Phase 2 (Mapping)
- Whether additional captures are needed
- Any early warnings about feasibility

Format the document clearly with markdown headers and tables. This document will be referenced in all subsequent phases.
