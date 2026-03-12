"""Domain classification and Phase 1 RECON analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from apiregen.har import HarEntry

# Known tracking/analytics domains (partial matches)
TRACKING_DOMAINS = {
    "google-analytics.com",
    "googletagmanager.com",
    "analytics.google.com",
    "doubleclick.net",
    "facebook.net",
    "facebook.com/tr",
    "hotjar.com",
    "cookiebot.com",
    "consentmanager.",
    "sentry.io",
    "newrelic.com",
    "segment.io",
    "segment.com",
    "mixpanel.com",
    "amplitude.com",
    "clarity.ms",
    "mouseflow.com",
    "smartlook.com",
    "fullstory.com",
    "heap.io",
    "hubspot.com",
    "intercom.io",
    "crisp.chat",
    "tawk.to",
    "onetrust.com",
    "cookielaw.org",
    "bat.bing.com",
    "ads.linkedin.com",
    "snap.licdn.com",
    "connect.facebook.net",
}

STATIC_EXTENSIONS = {
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".map", ".webp", ".avif",
}

STATIC_MIME_PREFIXES = (
    "image/", "font/", "text/css", "application/javascript",
    "text/javascript", "application/x-javascript",
)

# CDN/WAF detection patterns
CDN_SIGNATURES = {
    "cloudflare": {"headers": ["cf-ray", "cf-cache-status"], "server": "cloudflare"},
    "akamai": {"headers": ["x-akamai-transformed", "x-akamai-request-id"], "server": "akamaighost"},
    "fastly": {"headers": ["x-served-by", "x-cache", "x-fastly-request-id"], "server": "fastly"},
    "imperva": {"headers": ["x-iinfo"], "server": "imperva"},
    "aws_cloudfront": {"headers": ["x-amz-cf-id", "x-amz-cf-pop"], "server": "cloudfront"},
}


# ── Typed result dataclasses ────────────────────────────────────────────────────


@dataclass
class DomainInfo:
    domain: str
    request_count: int = 0
    category: str = "other"  # "api" | "static" | "tracking" | "cdn" | "other"
    content_types: set[str] = field(default_factory=set)
    methods: set[str] = field(default_factory=set)
    sample_paths: list[str] = field(default_factory=list)
    sessions_seen: set[str] = field(default_factory=set)
    json_request_count: int = 0
    static_request_count: int = 0


@dataclass
class AuthResult:
    auth_headers: dict[str, list[str]]
    auth_cookies: dict[str, int]
    token_session_spread: dict[str, int]
    has_auth: bool


@dataclass
class ProtectionResult:
    providers: dict[str, bool]
    details: list[str]
    has_protection: bool


@dataclass
class ConnectionInfo:
    url: str
    session: str


@dataclass
class RealtimeResult:
    websockets: list[ConnectionInfo]
    sse: list[ConnectionInfo]
    has_realtime: bool


@dataclass
class StackResult:
    hints: list[str]


@dataclass
class ReconResult:
    domains: list[DomainInfo]
    auth: AuthResult
    protection: ProtectionResult
    real_time: RealtimeResult
    stack: StackResult
    session_count: int = 0


# ── Internal helpers ─────────────────────────────────────────────────────────────


def _extract_domain(url: str) -> str:
    return urlparse(url).netloc


def _is_tracking_domain(domain: str) -> bool:
    for pattern in TRACKING_DOMAINS:
        if pattern in domain:
            return True
    return False


def _classify_domain(info: DomainInfo) -> str:
    """Classify a domain based on its observed traffic patterns."""
    if _is_tracking_domain(info.domain):
        return "tracking"

    has_json = any("json" in ct or "graphql" in ct for ct in info.content_types)
    has_static = any(ct.startswith(STATIC_MIME_PREFIXES) for ct in info.content_types)

    # If it serves JSON and JSON requests are a significant portion, it's an API
    if has_json and info.json_request_count > 0:
        return "api"

    # If all content is static assets
    if has_static and not has_json:
        has_only_static_paths = all(
            any(p.endswith(ext) for ext in STATIC_EXTENSIONS)
            for p in info.sample_paths
        )
        if has_only_static_paths:
            return "cdn"
        return "static"

    return "other"


def _detect_auth(entries: list[HarEntry]) -> AuthResult:
    """Detect authentication patterns from request headers and cookies."""
    auth_headers: dict[str, set[str]] = {}
    auth_cookies: dict[str, set[str]] = {}
    sessions_by_token: dict[str, set[str]] = {}

    auth_header_names = {"authorization", "x-auth-token", "x-api-key", "x-csrf-token", "x-xsrf-token"}

    for entry in entries:
        for name in auth_header_names:
            if name in entry.request_headers:
                for val in entry.request_headers[name]:
                    auth_headers.setdefault(name, set()).add(val)
                    sessions_by_token.setdefault(name, set()).add(entry.session)

        for cookie in entry.cookies:
            cname = cookie.get("name", "").lower()
            if any(kw in cname for kw in ("token", "auth", "session", "csrf", "jwt", "sid")):
                auth_cookies.setdefault(cookie["name"], set()).add(cookie.get("value", ""))
                sessions_by_token.setdefault(f"cookie:{cookie['name']}", set()).add(entry.session)

    return AuthResult(
        auth_headers={k: list(v) for k, v in auth_headers.items()},
        auth_cookies={k: len(v) for k, v in auth_cookies.items()},
        token_session_spread={k: len(v) for k, v in sessions_by_token.items()},
        has_auth=bool(auth_headers or auth_cookies),
    )


def _detect_protection(entries: list[HarEntry]) -> ProtectionResult:
    """Detect CDN/WAF and anti-bot protections."""
    detected: dict[str, bool] = {}
    details: list[str] = []

    for entry in entries:
        resp_headers = entry.response_headers

        for provider, sigs in CDN_SIGNATURES.items():
            if detected.get(provider):
                continue
            for h in sigs["headers"]:
                if h in resp_headers:
                    detected[provider] = True
                    details.append(f"{provider}: detected via '{h}' header")
                    break
            server_vals = resp_headers.get("server", [])
            for sv in server_vals:
                if sigs["server"] in sv.lower():
                    detected[provider] = True
                    details.append(f"{provider}: detected via server header '{sv}'")
                    break

        if entry.response_body and entry.mime_type and "html" in entry.mime_type:
            body_lower = entry.response_body[:5000].lower()
            for signal, label in [
                ("recaptcha", "reCAPTCHA"),
                ("hcaptcha", "hCaptcha"),
                ("turnstile", "Cloudflare Turnstile"),
                ("challenge-platform", "Cloudflare Challenge"),
            ]:
                if signal in body_lower and label not in details:
                    details.append(f"CAPTCHA: {label} detected in HTML")

    return ProtectionResult(
        providers={k: v for k, v in detected.items() if v},
        details=details,
        has_protection=bool(detected),
    )


def _detect_realtime(entries: list[HarEntry]) -> RealtimeResult:
    """Detect WebSocket and SSE connections."""
    websockets: list[ConnectionInfo] = []
    sse: list[ConnectionInfo] = []

    for entry in entries:
        upgrade = entry.request_headers.get("upgrade", [])
        if any("websocket" in u.lower() for u in upgrade):
            websockets.append(ConnectionInfo(url=entry.url, session=entry.session))

        if "text/event-stream" in entry.mime_type:
            sse.append(ConnectionInfo(url=entry.url, session=entry.session))

    return RealtimeResult(
        websockets=websockets,
        sse=sse,
        has_realtime=bool(websockets or sse),
    )


def _detect_stack(entries: list[HarEntry]) -> StackResult:
    """Detect frontend framework and stack from traffic patterns."""
    hints: list[str] = []

    for entry in entries:
        powered_by = entry.response_headers.get("x-powered-by", [])
        for val in powered_by:
            if val not in hints:
                hints.append(f"X-Powered-By: {val}")

        url_lower = entry.url.lower()
        path = urlparse(entry.url).path.lower()
        if path.endswith(".js"):
            for framework, patterns in {
                "React": ["react", "react-dom"],
                "Angular": ["angular", "zone.js", "polyfills"],
                "Vue": ["vue.js", "vue.min.js", "vuex"],
                "Next.js": ["_next/"],
                "Nuxt": ["_nuxt/"],
                "Svelte": ["svelte"],
            }.items():
                if any(p in url_lower for p in patterns):
                    hint = f"Framework: {framework}"
                    if hint not in hints:
                        hints.append(hint)

        if "graphql" in entry.url.lower() or (
            entry.request_body and "query" in (entry.request_body[:100] if entry.request_body else "")
        ):
            hint = "API style: GraphQL"
            if hint not in hints:
                hints.append(hint)

    return StackResult(hints=hints)


# ── Public API ───────────────────────────────────────────────────────────────────


def analyze(entries: list[HarEntry]) -> ReconResult:
    """Run full recon analysis on HAR entries, possibly from multiple sessions."""
    domains_map: dict[str, DomainInfo] = {}
    sessions = set()

    for entry in entries:
        sessions.add(entry.session)
        domain = _extract_domain(entry.url)
        if not domain:
            continue

        if domain not in domains_map:
            domains_map[domain] = DomainInfo(domain=domain)

        info = domains_map[domain]
        info.request_count += 1
        info.methods.add(entry.method)
        info.sessions_seen.add(entry.session)

        if entry.mime_type:
            info.content_types.add(entry.mime_type)
            if "json" in entry.mime_type or "graphql" in entry.mime_type:
                info.json_request_count += 1
            elif entry.mime_type.startswith(STATIC_MIME_PREFIXES):
                info.static_request_count += 1

        path = urlparse(entry.url).path
        if path and len(info.sample_paths) < 5:
            if path not in info.sample_paths:
                info.sample_paths.append(path)

    for info in domains_map.values():
        info.category = _classify_domain(info)

    category_order = {"api": 0, "other": 1, "cdn": 2, "static": 3, "tracking": 4}
    domain_list = sorted(
        domains_map.values(),
        key=lambda d: (category_order.get(d.category, 99), -d.request_count),
    )

    return ReconResult(
        domains=domain_list,
        auth=_detect_auth(entries),
        protection=_detect_protection(entries),
        real_time=_detect_realtime(entries),
        stack=_detect_stack(entries),
        session_count=len(sessions),
    )
