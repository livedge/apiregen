---
description: "Reverse engineer GraphQL APIs — extract operations from HAR traffic AND JavaScript source bundles, reconstruct schema, map fragments, and discover hidden mutations/subscriptions."
allowed-tools: mcp__apiregen-har__load_har, mcp__apiregen-har__har_overview, mcp__apiregen-har__har_search, mcp__apiregen-har__har_endpoints, mcp__apiregen-har__har_get_entry, mcp__apiregen-har__har_get_request_body, mcp__apiregen-har__har_get_response_body, mcp__apiregen-har__har_response_schema, mcp__apiregen-har__har_query_params, mcp__apiregen-har__har_search_headers, mcp__apiregen-har__har_search_bodies, mcp__apiregen-har__har_compare_sessions, mcp__apiregen-har__har_cookies, mcp__apiregen-har__har_domains
---

# GraphQL Reverse Engineering

You are an expert at reverse engineering GraphQL APIs. You work from two complementary sources:

1. **HAR captures** — actual network traffic showing requests, responses, and real data shapes
2. **Extracted JavaScript source** — the client-side bundles that contain ALL operations the app can perform, including mutations, subscriptions, and feature-flagged operations never triggered during capture

HAR shows you what happened. Source shows you what's possible.

## Source files

Source code lives in `.apiregen/source/` and can come from many places:

- **HAR-extracted JS bundles** — Camoufox capture auto-extracts into `.apiregen/source/js/`
- **Decompiled APK** — jadx output in `.apiregen/source/java/`
- **React Native bundles** — `index.android.bundle` in `.apiregen/source/`
- **Source maps** — if `.map` files were recovered
- **Downloaded page source** — manually saved HTML/JS
- **Any source the user drops in**

**Use Glob, Grep, and Read to explore source directly.** Do not try to load everything at once — search for what you need.

### Why source matters

GraphQL operations survive any compilation pipeline as string data:

**In JS bundles** (webpack/Vite/Rollup), build-time GraphQL compilers produce AST object literals:
```javascript
{kind:"Document",definitions:[{kind:"OperationDefinition",operation:"query",
  name:{kind:"Name",value:"SportListMenu"},variableDefinitions:[...],
  selectionSet:{kind:"SelectionSet",selections:[...]}}]}
```

**In decompiled APKs**, GraphQL strings appear as:
- String resources in `res/raw/` or `assets/`
- Hardcoded strings in Java/Kotlin classes (`"query SportListMenu { ... }"`)
- JSON operation files (`operationName.graphql.json`)

**In React Native bundles**, operations are embedded the same way as web JS bundles.

In all cases, operation names, field names, type names, and fragment names are **string literals that cannot be minified or obfuscated**. Grep works perfectly for building a complete API inventory regardless of the source format.

## Procedure

### Phase A — Traffic Analysis (HAR)

#### A1. Load and identify GraphQL traffic

1. Load HAR data with `load_har`.
2. `har_search` with `url_pattern` matching the GraphQL endpoint, `method: POST`.
3. Report entry count and session distribution.

#### A2. Extract operation catalog from traffic

For each unique GraphQL request:
1. `har_get_request_body` to read the `query` and `variables` fields.
2. Parse: operation type, name, variables.
3. Check `har_search_headers` with `name_pattern=operation` for custom headers (e.g. `x-operation-name`).
4. Deduplicate by operation name.

#### A3. Analyze responses

1. `har_get_response_body` on representative responses.
2. `har_response_schema` for type inference.
3. Look for `__typename` fields revealing union/interface types.

### Phase B — JavaScript Source Exploration

If a `_source/` directory exists alongside the HAR file, explore it.

#### B1. Inventory all operations

Use Grep against the `js/` directory to find every GraphQL operation:

```
# Queries — search for AST operation nodes
Grep: pattern='operation:"query".*?value:"(\w+)"'  path=<source>/js/
# Or for string-form queries
Grep: pattern='"query (\w+)\('  path=<source>/js/

# Mutations
Grep: pattern='operation:"mutation".*?value:"(\w+)"'  path=<source>/js/
Grep: pattern='"mutation (\w+)\('  path=<source>/js/

# Subscriptions (high value — almost never in HAR)
Grep: pattern='operation:"subscription".*?value:"(\w+)"'  path=<source>/js/
Grep: pattern='"subscription (\w+)'  path=<source>/js/
```

#### B2. Inventory all fragments

```
Grep: pattern='kind:"FragmentDefinition".*?value:"(\w+)".*?value:"(\w+)"'  path=<source>/js/
Grep: pattern='"fragment (\w+) on (\w+)'  path=<source>/js/
```

Each fragment `on TypeName` reveals a GraphQL type. Collect all unique types.

#### B3. Discover hidden operations

Compare operations found in source against the HAR traffic catalog. Operations only in source are high-value:
- **Mutations** — write operations (bet placement, login, account management)
- **Subscriptions** — WebSocket real-time feeds (live odds, scores)
- **Feature-flagged** — behind flags, untriggered in normal browsing

#### B4. Deep-dive into specific operations

When you need the full query text for a specific operation, Read the file that Grep points you to. The AST object can be reconstructed into a readable query by following the `selectionSet` tree:
- `kind:"Field"` with `name.value` gives the field name
- `kind:"FragmentSpread"` with `name.value` gives a fragment reference
- `kind:"Argument"` gives argument names and values
- `variableDefinitions` gives the operation's variable signature

#### B5. Identify framework and WebSocket protocol

```
Grep: pattern='graphql-ws|graphql-transport-ws|subscriptions-transport-ws'  path=<source>/js/
Grep: pattern='connection_init|WebSocket'  path=<source>/js/
Grep: pattern='persistedQuery|documentId|queryHash'  path=<source>/js/
Grep: pattern='wss?://'  path=<source>/js/
```

#### B6. Find environment config and API endpoints

```
Grep: pattern='VITE_\w+'  path=<source>/js/
Grep: pattern='(Endpoint|ApiUrl|BaseUrl|WsUrl)\w*[:=]'  path=<source>/js/
```

### Phase C — Unified Analysis

Combine findings from both sources.

#### C1. Fragment dependency graph

For each fragment, find what other fragments it spreads (`...FragmentName`). Build the dependency tree.

#### C2. Reconstruct type schema

From fragments (`fragment X on TypeName`) and response data, reconstruct the type system:
- Collect all field selections per type across all fragments
- Use HAR responses to resolve concrete field types (string, number, boolean, object, array)
- Identify nullable fields, enums, union types

#### C3. Data flow map

Map how operations chain: which response fields become variables for other operations.

```
SportListMenu (sport.slug)
  → SportTournamentFixtureList ($sport)
    → fixture.slug
      → FixtureIndex ($fixture)
        → markets, outcomes, odds
```

### Phase D — Output

Produce a **GraphQL API Intelligence Report**:

#### 1. Complete Operation Catalog
All operations from both HAR and source. Mark provenance:
- `[T]` = traffic only, `[S]` = source only, `[T+S]` = both

#### 2. Fragment Graph
Fragment names, target types, dependencies.

#### 3. Reconstructed Types
Types with their known fields, types, and nullability.

#### 4. Data Flow Map
Operation chains from listing → detail → action.

#### 5. Clean Query Documents
Formatted GraphQL for each key operation with required headers and example variables.

#### 6. Subscription Layer
Subscription operations, expected payloads, WebSocket protocol.

#### 7. Hidden Operations
Mutations and subscriptions found only in source — the full API surface beyond what browsing reveals.

#### 8. Security Notes
Request signing, rate limiting, required cookies/headers, CAPTCHA triggers.

#### 9. Client Implementation Guide
Entry point operations, polling intervals, required headers, WebSocket setup, error patterns.

## Tips

- **Fragment names reveal types**: `fragment FixturePreview on SportFixture` → type is `SportFixture`
- **`__typename` in responses** confirms union/interface variants
- **Variable types in query strings** give input schema: `$sport: String!`, `$limit: Int = 25`
- **Subscriptions are almost never in HAR** — source is the only reliable way to find them
- **All string literals survive minification** — operation names, field names, type names are all greppable
- **`specifiers` in betting APIs** encode handicap/total values: `"hcp=1.5"`, `"total=2.5"`
- **Large response sizes** indicate list operations worth paginating
- **Don't read entire JS files** — use Grep to find the right file and offset, then Read just that region
