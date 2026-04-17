import base64
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from rich.console import Console

console = Console()


async def capture_with_browser(
    output_path: Path,
    source_dir: Path | None = None,
    proxy: str | None = None,
) -> Path:
    """Launch a Camoufox browser and record all traffic to a HAR file.

    When *source_dir* is provided, HTML pages and JS bundles are
    extracted from the saved HAR into that directory for offline analysis.

    When *proxy* is provided (e.g. ``http://127.0.0.1:8080``), the browser
    routes all traffic through that proxy and ignores HTTPS certificate
    errors — intended for chaining with mitmproxy to capture WebSocket frames.
    """
    from camoufox.async_api import AsyncCamoufox

    console.print("[bold]Launching browser...[/bold]")
    if proxy:
        console.print(f"  [dim]Proxy: {proxy}[/dim]")
    console.print("Browse the target site, then close the browser window to save the capture.\n")

    context_kwargs: dict = {
        "record_har_path": str(output_path),
        "record_har_mode": "full",
        "record_har_content": "embed",
    }
    if proxy:
        context_kwargs["proxy"] = {"server": proxy}
        context_kwargs["ignore_https_errors"] = True

    async with AsyncCamoufox(headless=False) as browser:
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        await page.goto("about:blank")

        # Wait until the user closes the browser
        await page.wait_for_event("close", timeout=0)
        await context.close()

    if source_dir is not None:
        extract_sources_from_har(har_path=output_path, source_dir=source_dir)

    return output_path


def extract_sources_from_har(har_path: Path, source_dir: Path) -> None:
    """Extract HTML pages and JS bundles from a saved HAR file."""
    source_dir.mkdir(parents=True, exist_ok=True)
    js_dir = source_dir / "js"

    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    saved = 0
    for entry in har.get("log", {}).get("entries", []):
        url = entry.get("request", {}).get("url", "")
        resp = entry.get("response", {})
        content = resp.get("content", {})
        mime = content.get("mimeType", "")
        text = content.get("text", "")
        encoding = content.get("encoding", "")

        if not text:
            continue

        # Decode base64-encoded bodies
        if encoding == "base64":
            try:
                text = base64.b64decode(text).decode("utf-8", errors="replace")
            except Exception:
                continue

        is_html = "text/html" in mime
        is_js = "javascript" in mime

        if not (is_html or is_js):
            continue

        # Build a safe filename from the URL path
        parsed = urlparse(url)
        path = parsed.path.lstrip("/")
        name = re.sub(r"[^\w.\-]", "_", path) if path else parsed.netloc
        if not name:
            name = "index"

        if is_html:
            if not name.endswith(".html"):
                name += ".html"
            dest = source_dir / name
        else:
            if not name.endswith(".js"):
                name += ".js"
            js_dir.mkdir(exist_ok=True)
            dest = js_dir / name

        dest.write_text(text, encoding="utf-8")
        saved += 1

    if saved:
        console.print(f"[green]Page source saved:[/green] {source_dir} ({saved} files)")
    else:
        # Clean up empty directory
        if js_dir.exists() and not any(js_dir.iterdir()):
            js_dir.rmdir()
        if source_dir.exists() and not any(source_dir.iterdir()):
            source_dir.rmdir()
