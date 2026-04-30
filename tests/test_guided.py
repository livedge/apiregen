from __future__ import annotations

import json

from apiregen import guided


def test_step_init_creates_apiregen_project_with_target_type(monkeypatch, tmp_path):
    answers = iter(
        [
            "sample",
            "web-desktop",
            "https://example.test",
            "prices",
        ]
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(guided.Prompt, "ask", lambda *args, **kwargs: next(answers))

    project_dir = guided._step_init()

    assert project_dir == tmp_path / "sample" / ".apiregen"
    config = json.loads((project_dir / "config.json").read_text())
    assert config["target"] == {
        "type": "web-desktop",
        "url": "https://example.test",
    }
    assert config["data_interest"] == "prices"
