import asyncio
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

from apiregen.project import find_captures, init_project

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
@click.argument("name")
def init(name: str):
    """Initialize a new API recon project."""
    project_dir = init_project(name)
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
def capture(output: str | None, method: str | None, port: int):
    """Capture API traffic as HAR."""
    if method is None:
        method = click.prompt(
            "Capture method",
            type=click.Choice(["browser", "mitmproxy"], case_sensitive=False),
            default="browser",
        )

    if output is None:
        captures_dir = Path("captures")
        captures_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = captures_dir / f"{timestamp}.har"
    else:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if method == "browser":
        from apiregen.capture.browser import capture_with_browser

        har_path = asyncio.run(capture_with_browser(output_path))
        console.print(f"[green]HAR saved:[/green] {har_path}")
    elif method == "mitmproxy":
        from apiregen.capture.mitmproxy import capture_with_mitmproxy

        har_path = asyncio.run(capture_with_mitmproxy(output_path, listen_port=port))
        console.print(f"[green]HAR saved:[/green] {har_path}")


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
@click.argument("project_dir", type=click.Path(exists=True))
def recon(project_dir: str):
    """Show raw traffic summary for a project's captures."""
    from apiregen.har import parse_har
    from apiregen.recon import summarize
    from apiregen.rendering.recon import render_recon_result

    project_path = Path(project_dir)
    har_files = find_captures(project_path)

    if not har_files:
        console.print("[red]No .har files found in[/red] {}/captures/".format(project_dir))
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
