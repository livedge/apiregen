---
description: "Generate typed classes from API endpoints in loaded HAR data using QuickType."
allowed-tools: mcp__apiregen-har__load_har, mcp__apiregen-har__har_overview, mcp__apiregen-har__har_search, mcp__apiregen-har__har_endpoints, mcp__apiregen-har__har_get_entry, mcp__apiregen-har__har_get_response_body, mcp__apiregen-har__har_get_request_body, mcp__apiregen-har__har_response_schema, mcp__apiregen-har__har_domains, mcp__quicktype__quicktype, Write
---

# Type Generation from HAR Data

You are generating typed class definitions from API response data captured in HAR files. You orchestrate two tools: **apiregen-har** (extracts JSON from traffic) and **quicktype** (generates typed code from JSON).

## Input

The user will provide:
1. **Endpoint(s)** — URL pattern(s) or endpoint paths to generate types for (e.g., `/api/v1/events`, `push.nike.sk/snapshot`)
2. **Target language** — the programming language for generated types (e.g., `csharp`, `typescript`, `python`, `kotlin`, `rust`, `go`, `java`, `swift`, `dart`)
3. **HAR path** — if data isn't already loaded
4. **Output path** — where to write the generated code (ask if not provided)

If any are missing, ask. Default language to `typescript` if the user doesn't specify.

## Procedure

### Step 1 — Ensure HAR data is loaded

Check with `har_overview`. If nothing is loaded, ask the user for the HAR path and call `load_har`.

### Step 2 — Find matching entries

For each endpoint pattern the user specified:
1. Call `har_search` with `url_pattern` and `has_response_body=true` to find entries with JSON responses.
2. Report: how many matches, which sessions, status codes.
3. If no matches, suggest alternative patterns (use `har_endpoints` to show available endpoints).

### Step 3 — Extract JSON samples

For each endpoint:
1. Pick the **best representative sample** — prefer 200 status, largest response body, from the most recent session.
2. Call `har_get_response_body` on that entry to get the full JSON.
3. If the response is very large (>50KB), use `json_path` to extract the most interesting sub-structure. Tell the user what you're extracting and why.
4. If the endpoint has request bodies too (POST/PUT), also get those with `har_get_request_body` — they may define input types.

### Step 4 — Infer type name

Derive a sensible top-level type name from the endpoint:
- `/api/v1/events` → `EventsResponse`
- `/api/v1/menu` → `MenuResponse`
- `/snapshot?path=/n1/hybrid/match/{id}/` → `MatchSnapshot`
- GraphQL responses → name from the query operation

Tell the user the type name you're using. They can override it.

### Step 5 — Generate types with QuickType

For each endpoint's JSON sample:
1. Call `quicktype` with:
   - `json`: the extracted JSON body
   - `language`: the user's target language
   - `typeName`: the inferred type name
   - `justTypes`: `true` (we want clean type definitions, not serialization boilerplate)
2. Present the generated types to the user.

### Step 6 — Review and refine

Before writing to disk:
1. Show the generated code to the user.
2. Point out anything that looks off:
   - Fields that QuickType inferred as `string` but look like dates (`ISO 8601` patterns) — suggest `DateTimeOffset` / `Date` / `datetime`
   - Fields with small unique value sets that could be enums
   - Nullable fields that are always present in samples (may be required in practice)
   - Array fields where the item type could be named better
3. Ask if the user wants any adjustments before saving.

### Step 7 — Write output

1. If the user provided an output path, use it. Otherwise ask where to save.
2. Write the file using the Write tool.
3. If generating for multiple endpoints, either:
   - Combine into a single file (if the language supports it naturally — C#, TypeScript, Python)
   - Or write separate files and tell the user what was created

## Handling Multiple Endpoints

When the user wants types for several endpoints that share types (e.g., a Match type appears in both search results and snapshots):

1. Extract JSON from all endpoints first.
2. Generate types for each independently.
3. Identify **shared structures** — types that appear across endpoints (same field names and shapes).
4. Suggest consolidation: "The `Match` type from `/boxes/search` and `/snapshot` look identical — I'll generate one shared type."
5. If structures differ slightly (optional fields in one, required in another), note the differences and use the union (most permissive shape).

## Edge Cases

- **Truncated responses:** If `har_get_response_body` returns truncated data, try a different sample or warn the user that types may be incomplete.
- **Non-JSON responses:** Skip entries where the body isn't valid JSON. Report which were skipped.
- **Empty arrays:** If arrays are empty in the sample, QuickType can't infer item types. Flag this: "The `items` field was empty in this sample — the item type is unknown. Try a sample with data or provide the type manually."
- **Polymorphic responses:** If `har_response_schema` shows type unions for a field, warn the user and pick the most common type.

## Output Format

Present results clearly:

```
## Generated Types

**Endpoint:** GET /api-gw/nikeone/v1/boxes/search/portal
**Language:** C#
**Type name:** BoxSearchResponse
**Source entry:** index 42, session session1, status 200

[generated code]

**Saved to:** nike.sk/src/NikeSk.Client/GeneratedModels.cs
```
