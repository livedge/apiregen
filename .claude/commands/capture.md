---
description: "Guide the user through capturing web traffic as HAR files for analysis."
allowed-tools: Bash, AskUserQuestion
---

# Capture Traffic

You are guiding the user through capturing web traffic as HAR files for API reverse engineering.

## Project structure

All apiregen data lives in a `.apiregen/` directory:

```
project/
  .apiregen/
    config.json         # target metadata (type, url)
    captures/           # HAR files
    source/             # extracted JS/HTML, decompiled APK source
    reports/            # analysis artifacts
```

## Procedure

### Step 1 — Project setup

If no `.apiregen/` directory exists in the user's working directory, gather project details.

**First**, use AskUserQuestion to pick target type:

- Question: "What type of target are you analyzing?"
- Header: "Target"
- multiSelect: false
- Options:
  - label: "Web (Desktop)", description: "Website accessed via desktop browser — captures via Camoufox or DevTools"
  - label: "Web (Mobile)", description: "Website accessed via mobile browser or real device Chrome via ADB"
  - label: "Android APK", description: "Android app — decompile with jadx, capture traffic via mitmproxy + Frida"

**Then**, ask the user conversationally (plain text, no AskUserQuestion) for:
- The base URL of the target site (for web targets), or
- The Android package name (for APK targets)

Do NOT preset URL options in AskUserQuestion — just ask directly and wait for the user to type the URL/package name.

Run init:
```bash
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen init <project-path> -t <web-desktop|web-mobile|apk> -u <url-or-package>
```

If `.apiregen/config.json` already exists, read the target type from it to determine which capture flow to use — skip the questions.

---

### Step 2 — Capture method (depends on target type)

Read `target.type` from `.apiregen/config.json` and branch accordingly.

---

## Web (Desktop) capture

Use AskUserQuestion:

**Question:** "How do you want to capture traffic?"
- Header: "Capture"
- multiSelect: false
- Options:
  - label: "Camoufox (Recommended)", description: "Anti-detection Firefox browser. Best for bot-protected sites. HTTP only — WebSocket frames are NOT captured, only the upgrade handshake."
  - label: "Camoufox + mitmproxy", description: "Camoufox chained through mitmproxy. Captures everything Camoufox does PLUS WebSocket frames, raw POST bodies, and any non-HTTP protocols. Use when the target has real-time push (STOMP, socket.io, graphql-ws)."
  - label: "Browser DevTools", description: "Manually save HAR from Chrome/Firefox Network tab. Simplest option. No WebSocket frames."
  - label: "mitmproxy only", description: "Proxy with manual browser config. Captures WebSocket frames. Best when you want to use your normal browser session."

### WebSocket frame capture — important distinction

HAR files recorded by **browsers** (Camoufox, DevTools) only capture the HTTP upgrade handshake for WebSocket connections — not the frames themselves. Playwright's HAR writer drops WS frames entirely. If the target uses real-time protocols (STOMP, socket.io, graphql-ws, SignalR, custom WS), you **must** use a mitmproxy-based flow to see the actual subscription messages and data pushes.

### Camoufox (HTTP only)

```bash
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen capture -m browser -o <project>/.apiregen/captures/<session>.har
```

- Launches anti-detection browser, records all traffic
- User browses naturally, closes window when done
- HAR saved automatically, page source extracted to `.apiregen/source/`
- **WS frames: NOT captured** — only the upgrade handshake request

### Camoufox + mitmproxy (WS frames included)

mitmdump captures to a **flow stream file** which is written incrementally — no dependency on graceful shutdown. Convert to HAR afterwards.

```bash
# 1. Pick an unused port (8080 may be blocked on Windows — try 9080 if so)

# 2. Start mitmdump writing a flow stream (runs in background — safe to kill)
uv run --directory ${CLAUDE_PLUGIN_ROOT} mitmdump \
  --listen-host 127.0.0.1 \
  --listen-port 9080 \
  -w "<project>/.apiregen/captures/<session>.flows"

# 3. In another terminal, launch Camoufox through the proxy
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen capture \
  -m browser \
  --proxy http://127.0.0.1:9080 \
  -o <project>/.apiregen/captures/<session>-browser.har

# 4. Browse the site. Both captures run simultaneously.
# 5. Close the Camoufox browser (saves browser HAR + extracts source).
# 6. Stop mitmdump — any kill method works since the flow stream is always flushed.

# 7. Convert the flow stream to HAR (includes WebSocket frames)
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen flows-to-har \
  <project>/.apiregen/captures/<session>.flows
# → writes <session>.har alongside the .flows file
```

Result: two HAR files:
- `<session>-browser.har` — Camoufox view (HTTP only, plus extracted source in `.apiregen/source/`)
- `<session>.har` — mitmproxy view (HTTP + WebSocket frames, converted from .flows)

**Why flows instead of direct HAR?** mitmdump's `hardump` addon only writes on graceful shutdown. On Windows, signaling Ctrl+C to a background process is unreliable, and any force-kill produces an empty HAR. The `.flows` format is written flow-by-flow, so it survives any termination.

Troubleshooting:
- **Port blocked/in use** → try another port (9080, 8888, 3128)
- **HTTPS errors despite `ignore_https_errors`** → install the mitmproxy CA cert once: double-click `%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.p12` (Windows) → install to Trusted Root CAs. Or visit `http://mitm.it` while proxied.

### Browser DevTools

1. Open Chrome/Firefox/Edge
2. Open DevTools (F12) → Network tab
3. Check "Preserve log"
4. Browse the target site
5. Right-click in network list → "Save all as HAR with content"
6. Save to `.apiregen/captures/`
- **WS frames: NOT captured** — Chrome DevTools shows them live in the network panel but does not export them to HAR

### mitmproxy only

```bash
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen capture -m mitmproxy -o <project>/.apiregen/captures/<session>.har
```

Configure browser proxy to `localhost:8080` manually. Trust the mitmproxy CA cert from `~/.mitmproxy/` (first run generates it).
- **WS frames: captured** in mitmproxy's HAR dialect

---

## Web (Mobile) capture

Use AskUserQuestion:

**Question:** "How do you want to capture mobile traffic?"
- Header: "Capture"
- multiSelect: false
- Options:
  - label: "Camoufox mobile emulation (Recommended)", description: "Anti-detection browser with mobile User-Agent and viewport. No device needed."
  - label: "Device Chrome via ADB", description: "Connect to real Chrome on Android device using Chrome DevTools remote debugging."
  - label: "mitmproxy + device", description: "Proxy all device traffic through mitmproxy. Captures everything including non-browser apps."

### Camoufox mobile emulation

Camoufox captures with mobile viewport and User-Agent:

```bash
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen capture -m browser -o <project>/.apiregen/captures/<session>.har
```

Tell the user: after Camoufox opens, use the browser's responsive design mode (Ctrl+Shift+M in Firefox) to set a mobile viewport (e.g. iPhone 14: 390x844) and change User-Agent to a mobile string. Then browse the target site.

### Device Chrome via ADB

Guide the user through connecting to Chrome on a real Android device:

```bash
# 1. Enable USB debugging on the device
#    Settings → Developer Options → USB Debugging → On

# 2. Enable Chrome DevTools remote debugging
#    On device: Chrome → Settings → Developer tools → enable "DevTools remote debugging"
#    Or: chrome://flags → enable "DevTools remote debugging"

# 3. Forward the DevTools port
adb forward tcp:9222 localabstract:chrome_devtools_remote

# 4. Open Chrome DevTools on desktop
#    Navigate to chrome://inspect in desktop Chrome
#    Device's Chrome tabs appear — click "inspect" to open DevTools
#    Use the Network tab to capture, then "Save all as HAR with content"
#    Save to .apiregen/captures/
```

### mitmproxy + device

```bash
# 1. Start mitmproxy on host
mitmproxy --listen-port 8080
# Or for HAR output:
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen capture -m mitmproxy -o <project>/.apiregen/captures/<session>.har

# 2. Set device WiFi proxy to host IP:8080
adb shell settings put global http_proxy <host-ip>:8080

# 3. Install mitmproxy CA cert on device
adb push ~/.mitmproxy/mitmproxy-ca-cert.cer /sdcard/Download/
# On device: Settings → Security → Install certificate → CA certificate → select the file

# 4. Browse the target in mobile Chrome
# 5. Stop mitmproxy (Ctrl+C) — HAR saved

# Clean up proxy when done:
adb shell settings put global http_proxy :0
```

---

## Android APK capture

APK traffic capture requires mitmproxy + SSL pinning bypass. Guide the user through the full pipeline.

### APK acquisition

Use AskUserQuestion:

**Question:** "How do you want to get the APK?"
- Header: "APK source"
- multiSelect: false
- Options:
  - label: "Pull from device (Recommended)", description: "Extract APK from a connected Android device via ADB"
  - label: "Download from web", description: "Download from APKMirror, APKPure, or similar"
  - label: "Already have it", description: "APK file is already on disk"

#### Pull from device

```bash
# Find the package
adb shell pm list packages | grep <app-name>

# Get APK path(s)
adb shell pm path <package-name>

# Pull all APK splits
mkdir -p <project>/.apiregen/source/apk
adb shell pm path <package-name> | sed 's/package://' | while read p; do adb pull "$p" <project>/.apiregen/source/apk/; done

# Merge split APKs (if multiple files pulled)
# Use APKEditor: https://github.com/AlanTse93/APKEditor
java -jar APKEditor.jar m -i <project>/.apiregen/source/apk/ -o <project>/.apiregen/source/apk/merged.apk
```

#### Download from web

Direct the user to APKMirror.com or APKPure.com. Save the APK to `<project>/.apiregen/source/apk/`.

### SSL pinning bypass

Use AskUserQuestion:

**Question:** "Is the device rooted?"
- Header: "Root"
- multiSelect: false
- Options:
  - label: "Yes (rooted/Magisk)", description: "Use Frida server for runtime SSL pinning bypass — most reliable"
  - label: "No (stock device)", description: "Patch the APK with objection to disable pinning — works without root"
  - label: "Using an emulator", description: "Emulators typically have root. Will use Frida server."

#### Rooted device / emulator: Frida runtime injection

```bash
# 1. Install Frida on host
pip install frida-tools

# 2. Check Frida version
frida --version

# 3. Download matching frida-server for device arch
#    From: https://github.com/frida/frida/releases
#    Pick: frida-server-<version>-android-arm64.xz (or arm for 32-bit)

# 4. Push and start frida-server on device
xz -d frida-server-*-android-arm64.xz
adb push frida-server-*-android-arm64 /data/local/tmp/frida-server
adb shell "chmod 755 /data/local/tmp/frida-server"
adb shell "su -c '/data/local/tmp/frida-server -D &'"

# 5. Verify Frida can see the device
frida-ps -U

# 6. Download the universal SSL pinning bypass script
curl -o <project>/.apiregen/ssl-bypass.js https://raw.githubusercontent.com/httptoolkit/frida-android-unpinning/main/frida-script.js

# 7. Install mitmproxy CA as system cert (Magisk method)
HASH=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
cp ~/.mitmproxy/mitmproxy-ca-cert.pem "${HASH}.0"
adb push "${HASH}.0" /sdcard/Download/
adb shell "su -c 'cp /sdcard/Download/${HASH}.0 /system/etc/security/cacerts/'"
adb shell "su -c 'chmod 644 /system/etc/security/cacerts/${HASH}.0'"
# Or use MagiskTrustUserCerts module (auto-moves user CAs to system on boot)

# 8. Set device proxy
adb shell settings put global http_proxy <host-ip>:8080

# 9. Start mitmproxy
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen capture -m mitmproxy -o <project>/.apiregen/captures/<session>.har

# 10. Launch app with Frida SSL bypass
frida -U -f <package-name> -l <project>/.apiregen/ssl-bypass.js

# 11. Use the app — traffic appears in mitmproxy
# 12. When done: Ctrl+C mitmproxy, HAR saved

# Clean up
adb shell settings put global http_proxy :0
```

#### Non-rooted device: objection patchapk

```bash
# 1. Install objection
pip install objection

# 2. Patch the APK (injects frida-gadget + patches network security config)
objection patchapk -s <project>/.apiregen/source/apk/merged.apk --network-security-config

# 3. Install patched APK (uninstall original first)
adb uninstall <package-name>
adb install merged.objection.apk

# 4. Install mitmproxy CA as user cert
adb push ~/.mitmproxy/mitmproxy-ca-cert.cer /sdcard/Download/
# On device: Settings → Security → Install certificate → CA certificate

# 5. Set device proxy
adb shell settings put global http_proxy <host-ip>:8080

# 6. Start mitmproxy
uv run --directory ${CLAUDE_PLUGIN_ROOT} apiregen capture -m mitmproxy -o <project>/.apiregen/captures/<session>.har

# 7. Launch the patched app, then connect objection
objection -g <package-name> explore
# In objection shell:
android sslpinning disable

# 8. Use the app — traffic captured
# 9. Ctrl+C mitmproxy when done

# Clean up
adb shell settings put global http_proxy :0
```

### Decompile for source analysis

After capturing traffic, decompile the APK for source-level analysis:

```bash
# Decompile to Java source with jadx
jadx -d <project>/.apiregen/source/java/ <project>/.apiregen/source/apk/merged.apk \
  --threads-count 8 \
  --deobf \
  --deobf-min 3 \
  --show-bad-code

# Decompile resources with apktool (AndroidManifest, layouts, assets)
apktool d <project>/.apiregen/source/apk/merged.apk -o <project>/.apiregen/source/assets/ -f
```

---

## Session naming

For multi-session analysis, suggest:
- `session-001.har`, `session-002.har`, `session-003.har`
- Or descriptive: `browsing.har`, `logged-in.har`, `checkout-flow.har`

Each session should be a fresh app/browser session to get fresh tokens and cookies.

## Verification

After capture, verify the HAR is usable:

```bash
uv run --directory ${CLAUDE_PLUGIN_ROOT} python -c "
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

## Next steps

- **HAR captured:** Run `/recon` for reconnaissance
- **Source available:** `/recon` will delegate to the right specialist (rest-api-specialist / graphql-specialist / websocket-specialist) based on detected API style
- **Multiple sessions:** Ready for `/mapping` (differential analysis)
- **Need more sessions:** Capture again with a fresh session
