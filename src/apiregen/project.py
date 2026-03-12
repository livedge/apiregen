import json
from datetime import datetime, timezone
from pathlib import Path


def init_project(name: str) -> Path:
    """Create a new API recon project directory."""
    project_dir = Path(name)
    if project_dir.exists():
        raise FileExistsError(f"Directory '{name}' already exists")

    project_dir.mkdir(parents=True)
    (project_dir / "captures").mkdir()

    config = {
        "name": name,
        "created": datetime.now(timezone.utc).isoformat(),
        "sessions": [],
    }
    (project_dir / "config.json").write_text(json.dumps(config, indent=2))

    return project_dir


def find_captures(project_dir: Path) -> list[Path]:
    """Return all .har files in the project's captures directory, sorted by name."""
    captures_dir = project_dir / "captures"
    if not captures_dir.is_dir():
        return []
    return sorted(captures_dir.glob("*.har"))
