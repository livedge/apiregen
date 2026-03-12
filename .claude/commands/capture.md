---
description: "Guide the user through capturing web traffic as HAR files for analysis."
allowed-tools: Bash
---

# Capture Traffic

You are guiding the user through capturing web traffic as HAR files for API reverse engineering.

## Input

The user may provide:
- **Target URL** — the site they want to capture traffic from
- **Preferred method** — browser (Camoufox) or manual (browser DevTools / mitmproxy)
- **Project name** — for organizing captures

## Procedure

### Step 1 — Project setup

If the user doesn't have a project yet, create one:

```bash
uv run --directory C:/OneDrive/Workspace/repos/libraries/ApiRegen apiregen init <project-name>
```

This creates a directory with `config.json` and `captures/` subdirectory.

### Step 2 — Choose capture method

Present the options:

**Option A: Camoufox browser (recommended for anti-bot sites)**
- Launches an anti-detection browser that records all traffic
- User browses naturally, closes the window when done
- HAR is saved automatically
- Run: `uv run --directory C:/OneDrive/Workspace/repos/libraries/ApiRegen apiregen capture -m browser -o <project>/captures/<session-name>.har`

**Option B: Browser DevTools (simplest)**
1. Open Chrome/Firefox/Edge
2. Open DevTools (F12) → Network tab
3. Check "Preserve log" to keep data across navigations
4. Browse the target site naturally
5. When done: right-click in the network list → "Save all as HAR with content"
6. Save the `.har` file into the project's `captures/` directory

**Option C: mitmproxy (advanced, captures all HTTP clients including mobile apps)**

Two modes are available:

**Integrated mode (recommended):**
- Runs mitmproxy as a local proxy, saves HAR automatically on Ctrl+C
- Run: `uv run --directory C:/OneDrive/Workspace/repos/libraries/ApiRegen apiregen capture -m mitmproxy -o <project>/captures/<session-name>.har`
- Use `--port` to change the listen port (default: 8080)
- WebSocket traffic is captured automatically

**Manual mode (for advanced users):**
1. Run: `mitmdump --set hardump=./<project>/captures/<session>.har`
2. Configure browser/device to use the proxy (default: localhost:8080)
3. Browse the target site
4. Stop mitmdump (Ctrl+C) to save

**Proxy setup (both modes):**
- Configure browser HTTP proxy: `localhost:8080` (or the port you chose)
- For HTTPS sites, trust the mitmproxy CA certificate:
  - First run of mitmproxy generates certs in `~/.mitmproxy/`
  - Import `mitmproxy-ca-cert.pem` into your browser/OS trust store
  - Or visit `http://mitm.it` while proxied to download certs for your platform
- For mobile devices: set the device's Wi-Fi proxy to your machine's IP and the proxy port

### Step 3 — Guide session naming

For multi-session analysis (needed for Phase 2), suggest naming conventions:
- `session1.har`, `session2.har`, `session3.har`
- Or descriptive: `browsing_main.har`, `after_login.har`, `different_time.har`

Each session should be a fresh browser session (close and reopen) to get fresh tokens/cookies.

### Step 4 — Verify the capture

After the user provides a HAR file, verify it's usable:

```bash
uv run --directory C:/OneDrive/Workspace/repos/libraries/ApiRegen python -c "
from apiregen.har import parse_har
from pathlib import Path
entries = parse_har(Path('<har-file-path>'), session='test')
print(f'Entries: {len(entries)}')
domains = set()
for e in entries:
    from urllib.parse import urlparse
    domains.add(urlparse(e.url).netloc)
print(f'Domains: {len(domains)}')
for d in sorted(domains):
    print(f'  {d}')
"
```

Report entry count and domains to the user. Confirm the target site's domain appears.

### Step 5 — Next steps

Once captures are ready, suggest:
- **Single session captured:** Run `/recon` for initial reconnaissance
- **Multiple sessions captured:** Ready for `/recon` and then `/mapping`
- **Need more sessions:** Guide them to capture again with a fresh browser session
