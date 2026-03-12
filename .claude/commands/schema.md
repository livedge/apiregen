---
description: "Infer and document the JSON response schema for specific API endpoints from HAR data."
allowed-tools: mcp__apiregen-har__load_har, mcp__apiregen-har__har_search, mcp__apiregen-har__har_get_entry, mcp__apiregen-har__har_get_response_body, mcp__apiregen-har__har_get_request_body, mcp__apiregen-har__har_response_schema, mcp__apiregen-har__har_query_params, mcp__apiregen-har__har_endpoints, mcp__apiregen-har__har_overview
---

# Schema Inference

You are extracting and documenting the JSON schema of API endpoints from captured HAR data. This is useful for understanding response structures before writing client code.

## Input

The user will provide:
1. **URL pattern** — regex matching the endpoint(s) to analyze (e.g., `/api/events`, `graphql`)
2. **HAR path** — if data isn't already loaded

## Procedure

### Step 1 — Find matching entries

1. Ensure HAR data is loaded (call `load_har` if needed).
2. Call `har_search` with the URL pattern to find all matching entries.
3. Report how many matches were found and across how many sessions.

### Step 2 — Infer the schema

1. Call `har_response_schema` with the URL pattern to get the automated schema inference.
2. Review the output — pay attention to:
   - **present_in ratios** — fields that aren't in every response are optional
   - **type unions** — fields with multiple types indicate polymorphism or nullability
   - **array_lengths** — min/max give a sense of pagination or variability
   - **unique_values** — enums or constrained fields

### Step 3 — Deep-dive into complex structures

For nested objects or arrays that need more detail:
1. Call `har_get_response_body` with `json_path` to drill into specific sub-structures.
2. Compare the same path across different entries (different sessions or different query params) to understand variance.

### Step 4 — Document request shape too

If the endpoint accepts request bodies (POST/PUT/PATCH):
1. Call `har_get_request_body` on a few samples.
2. Document the request body structure alongside the response schema.

### Step 5 — Identify enums and constants

From the schema inference results:
- Fields with a small set of `unique_values` are likely enums — list them.
- Fields that are identical across all samples are constants.
- Fields with `unique_count` much lower than sample count are low-cardinality — consider as enums.

## Output

Produce a clean schema document for each endpoint:

```
## GET /api/v1/events

### Request
- Query params: lang (string, constant: "sk"), sportId (integer), page (integer)

### Response (200)
Shape: { data: Event[], meta: { total: int, page: int, pageSize: int } }

#### Event
| Field       | Type     | Required | Notes                          |
|-------------|----------|----------|--------------------------------|
| id          | integer  | yes      | Stable across sessions         |
| name        | string   | yes      |                                |
| sportId     | integer  | yes      | Enum: 1, 2, 3, 5, 8           |
| startTime   | string   | yes      | ISO 8601 datetime              |
| odds        | Odds[]   | yes      | 3–12 items                     |
| status      | string   | no       | Only present for live events   |

#### Odds
| Field       | Type     | Required | Notes                          |
|-------------|----------|----------|--------------------------------|
| type        | string   | yes      | Enum: "home", "draw", "away"   |
| value       | number   | yes      | Range: 1.01–50.0               |
```

Keep the schema practical — focus on what matters for code generation, not exhaustive documentation.

## Next Step

After presenting the schema, suggest: "Want to generate typed classes from this schema? Run `/typegen` with the same endpoint pattern and your target language (e.g., `csharp`, `typescript`, `python`)."
