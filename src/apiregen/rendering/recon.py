"""Rich rendering for the RECON phase output."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from apiregen.recon import ReconResult


def render_recon_result(console: Console, result: ReconResult) -> None:
    """Print a full recon analysis to the console using Rich tables and panels."""

    # Domain table
    table = Table(title="Domains", show_lines=True)
    table.add_column("Domain", style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Requests", justify="right")
    table.add_column("Methods")
    table.add_column("Content Types")
    table.add_column("Sessions", justify="right")

    for d in result.domains:
        table.add_row(
            d.domain,
            d.category,
            str(d.request_count),
            ", ".join(sorted(d.methods)),
            ", ".join(sorted(d.content_types))[:60],
            str(len(d.sessions_seen)),
        )
    console.print(table)
    console.print()

    # Auth
    if result.auth.has_auth:
        auth_lines = []
        for header, values in result.auth.auth_headers.items():
            auth_lines.append(f"  Header: [bold]{header}[/bold] ({len(values)} unique value(s))")
        for cookie, count in result.auth.auth_cookies.items():
            auth_lines.append(f"  Cookie: [bold]{cookie}[/bold] ({count} unique value(s))")
        console.print(Panel("\n".join(auth_lines), title="Authentication", border_style="yellow"))
    else:
        console.print(Panel("No authentication patterns detected", title="Authentication", border_style="dim"))
    console.print()

    # Protection
    if result.protection.has_protection:
        prot_lines = [f"  {detail}" for detail in result.protection.details]
        console.print(Panel("\n".join(prot_lines), title="Protection / CDN / WAF", border_style="red"))
    else:
        console.print(Panel("No CDN/WAF/anti-bot signals detected", title="Protection", border_style="dim"))
    console.print()

    # Real-time
    if result.real_time.has_realtime:
        rt_lines = []
        for ws in result.real_time.websockets:
            rt_lines.append(f"  WebSocket: {ws.url} (session: {ws.session})")
        for sse in result.real_time.sse:
            rt_lines.append(f"  SSE: {sse.url} (session: {sse.session})")
        console.print(Panel("\n".join(rt_lines), title="Real-time", border_style="green"))
    else:
        console.print(Panel("No WebSocket or SSE connections detected", title="Real-time", border_style="dim"))
    console.print()

    # Stack hints
    if result.stack.hints:
        stack_lines = [f"  {h}" for h in result.stack.hints]
        console.print(Panel("\n".join(stack_lines), title="Stack / Framework", border_style="blue"))
    console.print()

    # Summary
    api_domains = [d for d in result.domains if d.category == "api"]
    console.print(
        f"[bold]Summary:[/bold] {len(result.domains)} domains, "
        f"{len(api_domains)} API domain(s), "
        f"{result.session_count} session(s)"
    )
