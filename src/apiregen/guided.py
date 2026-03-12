"""Guided end-to-end API reverse engineering workflow."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from apiregen.har import parse_har
from apiregen.project import find_captures, init_project
from apiregen.recon import summarize
from apiregen.rendering.recon import render_recon_result

console = Console(highlight=False)


# ── Step 1: Project setup & scoping ─────────────────────────────────────────


def _step_init() -> Path:
    """Create project and gather target info."""
    console.print()
    console.print(Panel("[bold]Step 1 - Project setup[/bold]", style="cyan"))

    name = Prompt.ask("Project name (e.g. the site you're targeting)")

    project_dir = Path(name)
    if project_dir.exists() and (project_dir / "config.json").exists():
        console.print(f"[yellow]Project '{name}' already exists - resuming.[/yellow]")
    else:
        project_dir = init_project(name)
        console.print(f"[green]Created project:[/green] {project_dir}")

    console.print()
    target_url = Prompt.ask("Target URL (e.g. https://example.com)")
    data_interest = Prompt.ask(
        "What data are you interested in? (e.g. events, odds, prices, products)"
    )

    # Save scoping info to config
    config_path = project_dir / "config.json"
    config = json.loads(config_path.read_text())
    config["target_url"] = target_url
    config["data_interest"] = data_interest
    config_path.write_text(json.dumps(config, indent=2))

    console.print()
    console.print(f"  Target:  [bold]{target_url}[/bold]")
    console.print(f"  Looking for: [bold]{data_interest}[/bold]")

    return project_dir


# ── Step 2: Capture ─────────────────────────────────────────────────────────


def _choose_capture_method() -> str:
    """Let user pick a capture method."""
    console.print()
    console.print(Panel("[bold]Step 2 - Capture traffic[/bold]", style="cyan"))
    console.print(
        "[bold]A)[/bold] [cyan]Camoufox browser[/cyan] - anti-detection browser, records automatically\n"
        "[bold]B)[/bold] [cyan]mitmproxy[/cyan] - local proxy, captures any HTTP client\n"
        "[bold]C)[/bold] [cyan]Browser DevTools[/cyan] - manual export from Chrome/Firefox/Edge\n"
    )

    choice = Prompt.ask(
        "Choose capture method",
        choices=["a", "b", "c"],
        default="a",
    )
    return {"a": "browser", "b": "mitmproxy", "c": "devtools"}[choice]


def _capture_session(project_dir: Path, session_num: int) -> Path | None:
    """Run one capture session, return HAR path or None if manual."""
    captures_dir = project_dir / "captures"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = captures_dir / f"session{session_num}_{timestamp}.har"

    method = _choose_capture_method()

    if method == "browser":
        from apiregen.capture.browser import capture_with_browser

        console.print()
        console.print("Launching browser - browse the target site, then [bold]close the window[/bold] to save.")
        console.print()
        asyncio.run(capture_with_browser(output_path))
        console.print(f"[green]Capture saved:[/green] {output_path}")
        return output_path

    elif method == "mitmproxy":
        from apiregen.capture.mitmproxy import capture_with_mitmproxy

        asyncio.run(capture_with_mitmproxy(output_path))
        return output_path

    elif method == "devtools":
        console.print()
        console.print(Panel("[bold]Manual capture - Browser DevTools[/bold]", style="cyan"))
        console.print(
            "1. Open your browser and navigate to the target site\n"
            "2. Open DevTools ([bold]F12[/bold]) > [bold]Network[/bold] tab\n"
            "3. Check [bold]Preserve log[/bold] to keep data across navigations\n"
            "4. Browse the pages that contain your data of interest\n"
            "5. Right-click in the network list > [bold]Save all as HAR with content[/bold]\n"
            f"6. Save the file to: [bold]{captures_dir}[/bold]\n"
        )
        Prompt.ask("Press [bold]Enter[/bold] when you've saved the HAR file")

        # Check if any new HAR files appeared
        har_files = sorted(captures_dir.glob("*.har"), key=lambda p: p.stat().st_mtime)
        if har_files:
            latest = har_files[-1]
            console.print(f"[green]Found:[/green] {latest}")
            return latest
        else:
            console.print("[yellow]No HAR files found in captures directory.[/yellow]")
            har_path_str = Prompt.ask("Enter the path to your HAR file (or leave empty to skip)", default="")
            if har_path_str:
                src = Path(har_path_str)
                if src.exists():
                    import shutil
                    dest = captures_dir / src.name
                    shutil.copy2(src, dest)
                    console.print(f"[green]Copied to:[/green] {dest}")
                    return dest
            return None

    return None


# ── Step 3: Verify capture ──────────────────────────────────────────────────


def _verify_capture(har_path: Path) -> list:
    """Parse and verify a HAR file, return entries."""
    console.print()
    console.print(f"Verifying [dim]{har_path.name}[/dim]...")

    entries = parse_har(har_path, session=har_path.stem)
    if not entries:
        console.print("[red]No entries found in the HAR file.[/red]")
        return []

    from urllib.parse import urlparse
    domains = set()
    for e in entries:
        netloc = urlparse(e.url).netloc
        if netloc:
            domains.add(netloc)

    console.print(f"  [green]{len(entries)}[/green] requests across [green]{len(domains)}[/green] domains")
    for d in sorted(domains)[:10]:
        console.print(f"    {d}")
    if len(domains) > 10:
        console.print(f"    [dim]... and {len(domains) - 10} more[/dim]")

    return entries


# ── Step 4: Analysis ────────────────────────────────────────────────────────


def _step_analyze(project_dir: Path) -> None:
    """Show raw traffic summary for all captures."""
    console.print()
    console.print(Panel("[bold]Step 3 - Summary[/bold]", style="cyan"))

    har_files = find_captures(project_dir)
    if not har_files:
        console.print("[red]No captures found. Cannot summarize.[/red]")
        return

    console.print(f"Summarizing [cyan]{len(har_files)}[/cyan] capture(s)...")

    all_entries = []
    for har_file in har_files:
        entries = parse_har(har_file, session=har_file.stem)
        all_entries.extend(entries)
        console.print(f"  [dim]{har_file.name}[/dim] - {len(entries)} entries")

    console.print()
    result = summarize(all_entries)
    render_recon_result(console, result)

    # Show data interest reminder
    config_path = project_dir / "config.json"
    config = json.loads(config_path.read_text())
    data_interest = config.get("data_interest", "")
    if data_interest:
        console.print()
        console.print(
            Panel(
                f"You're looking for: [bold]{data_interest}[/bold]\n\n"
                "Use [bold]/recon[/bold] in Claude Code for intelligent analysis\n"
                "of these domains and their relevance to your data.",
                title="Data of interest",
                border_style="green",
            )
        )


# ── Main guided flow ────────────────────────────────────────────────────────


def run_guided() -> None:
    """Run the full guided API reverse engineering workflow."""
    console.print()
    console.print(
        Panel(
            "[bold]API Reverse Engineering Toolkit[/bold]\n\n"
            "This wizard will walk you through:\n"
            "  1. Project setup & scoping\n"
            "  2. Traffic capture\n"
            "  3. Recon analysis\n",
            style="bold cyan",
        )
    )

    # Step 1: Init
    project_dir = _step_init()

    # Step 2: Capture loop
    session_num = len(find_captures(project_dir)) + 1

    while True:
        har_path = _capture_session(project_dir, session_num)

        if har_path and har_path.exists():
            entries = _verify_capture(har_path)
            if not entries:
                console.print("[yellow]Capture appears empty. Try again?[/yellow]")
                if not Confirm.ask("Retry capture?", default=True):
                    break
                continue

        session_num += 1

        # Ask what to do next
        console.print()
        console.print(
            "[bold]What next?[/bold]\n"
            "[bold]A)[/bold] Capture another session (recommended for better analysis)\n"
            "[bold]B)[/bold] Run analysis on what we have\n"
            "[bold]C)[/bold] Stop here\n"
        )
        next_step = Prompt.ask("Choose", choices=["a", "b", "c"], default="b")

        if next_step == "a":
            console.print("[dim]Starting another capture session...[/dim]")
            continue
        elif next_step == "c":
            console.print("[dim]Done. You can run analysis later with:[/dim]")
            console.print(f"  [bold]apiregen recon {project_dir}[/bold]")
            return
        else:
            break

    # Step 3: Analysis
    has_captures = bool(find_captures(project_dir))
    if has_captures:
        _step_analyze(project_dir)

    # Offer to capture more
    console.print()
    more_prompt = (
        "Would you like to capture additional sessions for deeper analysis?"
        if has_captures
        else "No captures yet. Would you like to try capturing again?"
    )
    if Confirm.ask(more_prompt, default=not has_captures):
        while True:
            har_path = _capture_session(project_dir, session_num)
            if har_path and har_path.exists():
                _verify_capture(har_path)
            session_num += 1

            if not Confirm.ask("Capture another session?", default=False):
                break

        # Re-run analysis with new data
        _step_analyze(project_dir)

    console.print()
    console.print(
        Panel(
            f"Project: [bold]{project_dir}[/bold]\n"
            f"Captures: [bold]{len(find_captures(project_dir))}[/bold] session(s)\n\n"
            "Next steps:\n"
            f"  [bold]apiregen recon {project_dir}[/bold] - re-run analysis\n"
            "  [bold]/recon[/bold]    - detailed recon in Claude Code\n"
            "  [bold]/mapping[/bold]  - cross-session differential analysis\n"
            "  [bold]/report[/bold]   - full API intelligence report\n"
            "  [bold]/typegen[/bold]  - generate typed classes from endpoints",
            title="Done",
            border_style="green",
        )
    )
