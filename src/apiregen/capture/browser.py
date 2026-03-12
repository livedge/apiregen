from pathlib import Path

from rich.console import Console

console = Console()


async def capture_with_browser(output_path: Path) -> Path:
    """Launch a Camoufox browser and record all traffic to a HAR file."""
    from camoufox.async_api import AsyncCamoufox

    console.print("[bold]Launching browser...[/bold]")
    console.print("Browse the target site, then close the browser window to save the capture.\n")

    async with AsyncCamoufox(headless=False) as browser:
        context = await browser.new_context(
            record_har_path=str(output_path),
            record_har_mode="full",
            record_har_content="embed",
        )
        page = await context.new_page()
        await page.goto("about:blank")

        # Wait until the user closes the browser
        await page.wait_for_event("close", timeout=0)
        await context.close()

    return output_path
