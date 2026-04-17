import json
from datetime import datetime, timezone
from pathlib import Path

APIREGEN_DIR = ".apiregen"

TARGET_TYPES = {
    "web-desktop": "Website (desktop browser)",
    "web-mobile": "Website (mobile browser)",
    "apk": "Android APK",
}


def init_project(path: str, target_type: str, target_url: str | None = None) -> Path:
    """Create a new .apiregen project directory."""
    project_dir = Path(path) / APIREGEN_DIR
    if project_dir.exists():
        raise FileExistsError(f"Directory '{project_dir}' already exists")

    project_dir.mkdir(parents=True)
    (project_dir / "captures").mkdir()
    (project_dir / "reports").mkdir()

    # Source subdirectory structure depends on target type
    source_dir = project_dir / "source"
    source_dir.mkdir()
    if target_type == "apk":
        (source_dir / "java").mkdir()
        (source_dir / "assets").mkdir()
    else:
        (source_dir / "js").mkdir()

    config = {
        "name": Path(path).name or path,
        "created": datetime.now(timezone.utc).isoformat(),
        "target": {
            "type": target_type,
            "url": target_url,
        },
    }
    (project_dir / "config.json").write_text(json.dumps(config, indent=2))

    return project_dir


def find_project(start: Path | None = None) -> Path | None:
    """Walk up from *start* (default: cwd) looking for a .apiregen directory."""
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / APIREGEN_DIR
        if candidate.is_dir():
            return candidate
    return None


def find_captures(project_dir: Path) -> list[Path]:
    """Return all .har files in the project's captures directory, sorted by name."""
    captures_dir = project_dir / "captures"
    if not captures_dir.is_dir():
        captures_dir = project_dir
        if not captures_dir.is_dir():
            return []
    return sorted(captures_dir.glob("*.har"))
