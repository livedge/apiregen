import asyncio
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt

console = Console()


def _check_mitmproxy_installed():
    """Check that mitmproxy is importable, exit with guidance if not."""
    try:
        from mitmproxy import options  # noqa: F401
        from mitmproxy.tools.dump import DumpMaster  # noqa: F401
    except ImportError:
        console.print(
            "[red]mitmproxy is not installed.[/red]\n"
            "Install it with: [bold]uv pip install apiregen[mitmproxy][/bold]\n"
            "Or: [bold]pip install mitmproxy[/bold]"
        )
        raise SystemExit(1)


def _ca_cert_path() -> Path:
    """Return the default mitmproxy CA cert path."""
    return Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"


async def capture_with_mitmproxy(
    output_path: Path,
    listen_host: str = "127.0.0.1",
    listen_port: int = 8080,
) -> Path:
    """Guided mitmproxy capture - walks the user through setup step by step."""
    _check_mitmproxy_installed()

    from mitmproxy import options
    from mitmproxy.tools.dump import DumpMaster

    # ── Step 1: Port selection ──────────────────────────────────────────
    console.print()
    console.print(Panel("[bold]Step 1/4 - Proxy port[/bold]", style="cyan"))
    console.print(f"The proxy will listen on [cyan]{listen_host}[/cyan].")
    if not Confirm.ask(f"Use port [bold]{listen_port}[/bold]?", default=True):
        listen_port = IntPrompt.ask("Enter port number", default=8080)

    # ── Step 2: CA certificate ──────────────────────────────────────────
    console.print()
    console.print(Panel("[bold]Step 2/4 - HTTPS certificate[/bold]", style="cyan"))
    ca_cert = _ca_cert_path()
    if ca_cert.exists():
        console.print(f"[green]CA cert found:[/green] {ca_cert}")
        console.print("If you've already trusted it in your browser, you're good to go.")
    else:
        console.print("[yellow]No CA cert found yet.[/yellow]")
        console.print(
            "mitmproxy will generate one on first run at:\n"
            f"  [dim]{ca_cert}[/dim]"
        )
        console.print(
            "\nTo capture HTTPS traffic, you'll need to trust it:\n"
            "  - Import the .pem file into your browser/OS trust store, or\n"
            "  - Visit [bold]http://mitm.it[/bold] while proxied to download certs"
        )
    console.print()
    if not Confirm.ask("Ready to continue?", default=True):
        console.print("[dim]Cancelled.[/dim]")
        raise SystemExit(0)

    # ── Step 3: Browser proxy setup ─────────────────────────────────────
    console.print()
    console.print(Panel("[bold]Step 3/4 - Configure your browser[/bold]", style="cyan"))
    console.print(
        f"Set your browser's HTTP proxy to [bold cyan]{listen_host}:{listen_port}[/bold cyan]\n"
        "\n"
        "  [bold]Chrome:[/bold]  Settings > System > Open proxy settings\n"
        "  [bold]Firefox:[/bold] Settings > Network Settings > Manual proxy\n"
        "  [bold]System:[/bold]  Use OS proxy settings (applies to all browsers)\n"
    )
    if not Confirm.ask("Is your browser proxy configured?", default=True):
        console.print("[dim]Take your time - press Enter when ready.[/dim]")
        Confirm.ask("Ready now?", default=True)

    # ── Step 4: Start proxy ─────────────────────────────────────────────
    console.print()
    console.print(Panel("[bold]Step 4/4 - Capture[/bold]", style="cyan"))
    console.print(
        f"Starting proxy on [bold]{listen_host}:{listen_port}[/bold]\n"
        f"HAR will be saved to: [bold]{output_path}[/bold]\n"
    )
    console.print("Browse the target site now.")
    console.print("Press [bold]Ctrl+C[/bold] when you're done to stop and save.\n")

    opts = options.Options(
        listen_host=listen_host,
        listen_port=listen_port,
        hardump=str(output_path),
    )
    master = DumpMaster(opts)

    loop = asyncio.get_running_loop()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, master.shutdown)

    try:
        await master.run()
    except KeyboardInterrupt:
        master.shutdown()

    console.print(f"\n[green]HAR saved:[/green] {output_path}")
    return output_path
