"""Encapsulates loaded HAR data — replaces module-level global state."""

from __future__ import annotations

from pathlib import Path

from apiregen.har import HarEntry, parse_har


class HarStore:
    def __init__(self) -> None:
        self.entries: list[HarEntry] = []
        self.sessions: set[str] = set()
        self.loaded_files: list[str] = []

    def ensure_loaded(self) -> str | None:
        """Return an error string if no data is loaded, else ``None``."""
        if not self.entries:
            return "No HAR data loaded. Use load_har first."
        return None

    def load_paths(self, paths: list[Path]) -> int:
        """Parse HAR files and append to store. Returns entry count."""
        count = 0
        for p in paths:
            entries = parse_har(p, session=p.stem)
            self.entries.extend(entries)
            self.sessions.add(p.stem)
            self.loaded_files.append(str(p))
            count += len(entries)
        return count

    def clear(self) -> int:
        """Clear all loaded data. Returns previous entry count."""
        n = len(self.entries)
        self.entries.clear()
        self.sessions.clear()
        self.loaded_files.clear()
        return n
