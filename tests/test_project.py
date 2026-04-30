from __future__ import annotations

import json

from apiregen.project import init_project


def test_init_project_writes_config_json_with_target_metadata(tmp_path):
    project_dir = init_project(
        tmp_path / "target",
        target_type="web-desktop",
        target_url="https://example.test",
    )

    assert project_dir == tmp_path / "target" / ".apiregen"
    assert (project_dir / "captures").is_dir()
    assert (project_dir / "reports").is_dir()
    assert (project_dir / "source" / "js").is_dir()

    config = json.loads((project_dir / "config.json").read_text())
    assert config["name"] == "target"
    assert config["target"] == {
        "type": "web-desktop",
        "url": "https://example.test",
    }


def test_init_project_accepts_path_objects(tmp_path):
    project_dir = init_project(tmp_path / "apk-target", target_type="apk")

    assert project_dir == tmp_path / "apk-target" / ".apiregen"
    assert (project_dir / "source" / "java").is_dir()
    assert (project_dir / "source" / "assets").is_dir()
