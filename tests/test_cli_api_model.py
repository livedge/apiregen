from __future__ import annotations

import json

from click.testing import CliRunner

from apiregen.cli import cli


def write_project_har(tmp_path):
    project = tmp_path / ".apiregen"
    captures = project / "captures"
    captures.mkdir(parents=True)
    har_path = captures / "session.har"
    har_path.write_text(
        json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "request": {
                                "method": "GET",
                                "url": "https://api.example.test/events/123?token=secret",
                                "headers": [{"name": "Authorization", "value": "Bearer secret"}],
                            },
                            "response": {
                                "status": 200,
                                "headers": [{"name": "Content-Type", "value": "application/json"}],
                                "content": {
                                    "mimeType": "application/json",
                                    "text": '{"id":"123","name":"Match"}',
                                },
                            },
                            "timings": {},
                        }
                    ]
                }
            }
        )
    )
    return project


def test_cli_model_outputs_redacted_api_model(tmp_path):
    project = write_project_har(tmp_path)
    result = CliRunner().invoke(cli, ["model", str(project)])

    assert result.exit_code == 0
    model = json.loads(result.output)
    assert model["endpoints"][0]["path_template"] == "/events/{id}"
    assert "Bearer secret" not in result.output


def test_cli_openapi_outputs_spec(tmp_path):
    project = write_project_har(tmp_path)
    result = CliRunner().invoke(cli, ["openapi", str(project)])

    assert result.exit_code == 0
    spec = json.loads(result.output)
    assert spec["openapi"] == "3.1.0"
    assert "/events/{id}" in spec["paths"]


def test_cli_replay_outputs_redacted_curl(tmp_path):
    project = write_project_har(tmp_path)
    result = CliRunner().invoke(cli, ["replay", str(project), "0"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "token=<redacted>" in payload["curl"]
    assert "Bearer secret" not in payload["curl"]
