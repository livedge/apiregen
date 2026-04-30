from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_versions_match_across_package_plugin_and_marketplace():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())

    marketplace_plugin = marketplace["plugins"][0]
    assert pyproject["project"]["version"] == plugin["version"]
    assert marketplace_plugin["version"] == plugin["version"]


def test_ci_validates_actual_plugin_manifest_path():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

    assert "test -f .claude-plugin/plugin.json" in ci
    assert "open('.claude-plugin/plugin.json')" in ci


def test_capture_command_uses_plugin_root_placeholder_not_local_absolute_path():
    capture = (ROOT / ".claude" / "commands" / "capture.md").read_text()

    assert "C:/OneDrive" not in capture
    assert "${CLAUDE_PLUGIN_ROOT}" in capture


def test_readme_describes_generic_mcp_clients_and_current_project_files():
    readme = (ROOT / "README.md").read_text()

    assert "MCP-compatible AI assistants" in readme
    assert "config.json" in readme
    assert "project.json" not in readme
    assert re.search(r"agents/\s+# 8 specialist agents", readme)


def test_transport_specialist_agents_are_registered_and_documented():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    readme = (ROOT / "README.md").read_text()
    recon = (ROOT / ".claude" / "commands" / "recon.md").read_text()

    expected = {
        "grpc-transport-specialist",
        "realtime-framework-specialist",
        "rpc-transport-specialist",
        "mobile-transport-specialist",
    }
    registered = {
        Path(agent_path).stem
        for agent_path in plugin["agents"]
    }

    assert expected.issubset(registered)
    for name in expected:
        assert (ROOT / ".claude" / "agents" / f"{name}.md").is_file()
        assert name in readme
        assert name in recon
