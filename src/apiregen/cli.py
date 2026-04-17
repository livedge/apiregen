import asyncio
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

from apiregen.project import TARGET_TYPES, find_captures, find_project, init_project

console = Console()


@click.group()
def cli():
    """API reverse engineering toolkit."""


@cli.command()
def start():
    """Guided workflow — walks you through the entire process."""
    from apiregen.guided import run_guided

    run_guided()


@cli.command()
@click.argument("path", default=".")
@click.option(
    "-t",
    "--type",
    "target_type",
    type=click.Choice(list(TARGET_TYPES.keys()), case_sensitive=False),
    default=None,
    help="Target type.",
)
@click.option("-u", "--url", "target_url", default=None, help="Target URL.")
def init(path: str, target_type: str | None, target_url: str | None):
    """Initialize a .apiregen project in PATH (default: current directory)."""
    if target_type is None:
        for key, label in TARGET_TYPES.items():
            console.print(f"  [cyan]{key}[/cyan] — {label}")
        target_type = click.prompt(
            "Target type",
            type=click.Choice(list(TARGET_TYPES.keys()), case_sensitive=False),
        )

    if target_url is None:
        if target_type == "apk":
            target_url = click.prompt("Package name or URL (optional)", default="", show_default=False)
        else:
            target_url = click.prompt("Target URL (optional)", default="", show_default=False)
        target_url = target_url or None

    project_dir = init_project(path, target_type=target_type, target_url=target_url)
    console.print(f"[green]Project created:[/green] {project_dir}")


@cli.command()
@click.option("-o", "--output", default=None, type=click.Path(), help="Output HAR file path.")
@click.option(
    "-m",
    "--method",
    type=click.Choice(["browser", "mitmproxy"], case_sensitive=False),
    default=None,
    help="Capture method.",
)
@click.option(
    "--port",
    type=int,
    default=8080,
    show_default=True,
    help="Proxy listen port (mitmproxy mode only).",
)
@click.option(
    "--no-source",
    is_flag=True,
    default=False,
    help="Skip extracting page source and JS bundles (browser mode only).",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Route browser traffic through HTTP proxy (e.g. http://127.0.0.1:8080). Ignores HTTPS errors. Browser mode only.",
)
def capture(output: str | None, method: str | None, port: int, no_source: bool, proxy: str | None):
    """Capture API traffic as HAR."""
    if method is None:
        method = click.prompt(
            "Capture method",
            type=click.Choice(["browser", "mitmproxy"], case_sensitive=False),
            default="browser",
        )

    # Resolve output path — prefer .apiregen/captures/ if a project exists
    if output is None:
        proj = find_project()
        if proj:
            captures_dir = proj / "captures"
        else:
            captures_dir = Path("captures")
        captures_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = captures_dir / f"{timestamp}.har"
    else:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve source dir for extraction — search from output path first,
    # then CWD, so an explicit -o into a .apiregen/ project works correctly.
    source_dir = None
    if method == "browser" and not no_source:
        proj = find_project(output_path.resolve().parent) or find_project()
        if proj:
            source_dir = proj / "source"
        else:
            # Fallback: alongside HAR file
            source_dir = output_path.parent / f"{output_path.stem}_source"

    if method == "browser":
        from apiregen.capture.browser import capture_with_browser

        har_path = asyncio.run(capture_with_browser(output_path, source_dir=source_dir, proxy=proxy))
        console.print(f"[green]HAR saved:[/green] {har_path}")
    elif method == "mitmproxy":
        from apiregen.capture.mitmproxy import capture_with_mitmproxy

        har_path = asyncio.run(capture_with_mitmproxy(output_path, listen_port=port))
        console.print(f"[green]HAR saved:[/green] {har_path}")


@cli.command("flows-to-har")
@click.argument("flows_file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, type=click.Path(), help="Output HAR path (default: replace .flows with .har).")
def flows_to_har(flows_file: str, output: str | None):
    """Convert a mitmproxy .flows stream file to HAR format."""
    import subprocess

    flows_path = Path(flows_file)
    if output:
        har_path = Path(output)
    else:
        har_path = flows_path.with_suffix(".har")

    har_path.parent.mkdir(parents=True, exist_ok=True)

    # Use mitmdump in read-only mode to replay the flows file and dump HAR
    result = subprocess.run(
        [
            "uv", "run", "--directory",
            str(Path(__file__).resolve().parents[2]),
            "mitmdump",
            "-nr", str(flows_path),
            "--set", f"hardump={har_path}",
            "-q",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        console.print(f"[red]Conversion failed:[/red] {result.stderr}")
        raise SystemExit(1)

    console.print(f"[green]HAR saved:[/green] {har_path}")


@cli.command("extract-source")
@click.argument("har_file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, type=click.Path(), help="Output directory (default: .apiregen/source/).")
def extract_source(har_file: str, output: str | None):
    """Extract HTML and JS source files from a HAR capture."""
    from apiregen.capture.browser import extract_sources_from_har

    if output:
        source_dir = Path(output)
    else:
        proj = find_project()
        if proj:
            source_dir = proj / "source"
        else:
            source_dir = Path(har_file).parent / f"{Path(har_file).stem}_source"

    extract_sources_from_har(har_path=Path(har_file), source_dir=source_dir)


@cli.command()
@click.argument("project_dir", type=click.Path(exists=True), required=False)
@click.option("--port", type=int, default=None, help="Run as HTTP SSE server on this port instead of stdio.")
def mcp(project_dir: str | None, port: int | None):
    """Start the MCP server for HAR investigation."""
    import os

    if project_dir:
        os.environ["APIREGEN_HAR_PATH"] = project_dir

    from apiregen.mcp_server import mcp as mcp_app

    if port:
        mcp_app.run(transport="sse", port=port)
    else:
        mcp_app.run(transport="stdio")


@cli.command()
@click.argument("project_dir", type=click.Path(exists=True), required=False)
def recon(project_dir: str | None):
    """Show raw traffic summary for a project's captures."""
    from apiregen.har import parse_har
    from apiregen.recon import summarize
    from apiregen.rendering.recon import render_recon_result

    if project_dir:
        project_path = Path(project_dir)
    else:
        proj = find_project()
        if proj:
            project_path = proj
        else:
            console.print("[red]No .apiregen project found. Run 'apiregen init' first.[/red]")
            raise SystemExit(1)

    har_files = find_captures(project_path)

    if not har_files:
        console.print(f"[red]No .har files found in[/red] {project_path}/captures/")
        raise SystemExit(1)

    console.print(f"Found [cyan]{len(har_files)}[/cyan] capture(s)")

    all_entries = []
    for har_file in har_files:
        console.print(f"  Parsing [dim]{har_file.name}[/dim]...")
        entries = parse_har(har_file, session=har_file.stem)
        all_entries.extend(entries)
        console.print(f"    {len(entries)} entries")

    console.print()
    result = summarize(all_entries)
    render_recon_result(console, result)
    console.print()
    console.print("[dim]For full analysis, use /recon in Claude Code.[/dim]")
