"""Rich rendering for raw recon summary."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from apiregen.recon import ReconResult


def render_recon_result(console: Console, result: ReconResult) -> None:
    """Print raw domain summary to the console."""

    table = Table(title="Domains", show_lines=True)
    table.add_column("Domain", style="bold")
    table.add_column("Requests", justify="right")
    table.add_column("Methods")
    table.add_column("Content Types")
    table.add_column("Sessions", justify="right")

    for d in result.domains:
        table.add_row(
            d.domain,
            str(d.request_count),
            ", ".join(sorted(d.methods)),
            ", ".join(sorted(d.content_types))[:60],
            str(len(d.sessions_seen)),
        )
    console.print(table)
    console.print()
    console.print(
        f"[bold]Total:[/bold] {result.total_entries} requests, "
        f"{len(result.domains)} domains, "
        f"{result.session_count} session(s)"
    )
