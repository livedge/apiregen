"""MCP tool for generating typed code from JSON samples via QuickType."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP


def _find_quicktype() -> str:
    """Locate the quicktype executable."""
    found = shutil.which("quicktype")
    if found:
        return found
    # Common npm global install paths on Windows
    for candidate in [
        Path.home() / "AppData" / "Roaming" / "npm" / "quicktype.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "quicktype",
    ]:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        "quicktype not found. Install with: npm install -g quicktype"
    )


def register_quicktype_tools(mcp: FastMCP) -> None:
    """Register the quicktype code generation tool on *mcp*."""

    @mcp.tool()
    def quicktype(
        json_sample: str,
        language: str = "typescript",
        type_name: str = "Root",
        just_types: bool = True,
        src_lang: str = "json",
        all_properties_optional: bool = False,
        no_combine_classes: bool = False,
    ) -> str:
        """Generate typed classes from a JSON sample using QuickType.

        Supported languages: csharp (cs), typescript (ts), python (py),
        kotlin, java, go, rust (rs), swift, dart, ruby, flow, elm,
        haskell, cpp (c++), objc, php, scala3, and more.

        ``src_lang`` can be ``json`` (default), ``schema`` (JSON Schema input),
        or ``graphql`` (with a schema file).

        Set ``just_types`` to True (default) for clean type definitions
        without serialization boilerplate.
        """
        # Write the JSON sample to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write(json_sample)
            input_path = f.name

        try:
            qt = _find_quicktype()
            cmd = [
                qt,
                "--src", input_path,
                "--src-lang", src_lang,
                "--lang", language,
                "--top-level", type_name,
                "--quiet",
            ]

            # --just-types produces empty output for some languages (C#)
            if just_types and language not in ("cs", "csharp"):
                cmd.append("--just-types")
            if all_properties_optional:
                cmd.append("--all-properties-optional")
            if no_combine_classes:
                cmd.append("--no-combine-classes")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                return json.dumps({"error": f"quicktype failed: {error}"})

            return json.dumps({
                "language": language,
                "type_name": type_name,
                "code": result.stdout,
            })

        finally:
            Path(input_path).unlink(missing_ok=True)

    @mcp.tool()
    def quicktype_schema(
        json_sample: str,
        type_name: str = "Root",
    ) -> str:
        """Generate a JSON Schema from a JSON sample using QuickType.

        Returns a JSON Schema (draft-06) that describes the structure of
        the input JSON. Useful for documenting API response shapes.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write(json_sample)
            input_path = f.name

        try:
            qt = _find_quicktype()
            result = subprocess.run(
                [
                    qt,
                    "--src", input_path,
                    "--src-lang", "json",
                    "--lang", "schema",
                    "--top-level", type_name,
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                return json.dumps({"error": f"quicktype failed: {error}"})

            return result.stdout

        finally:
            Path(input_path).unlink(missing_ok=True)
