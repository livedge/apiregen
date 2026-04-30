from __future__ import annotations

import json

from apiregen.api_model import (
    build_api_model,
    endpoint_summary,
    generate_asyncapi,
    generate_openapi,
    replay_curl,
    redact_model,
)
from apiregen.har import HarEntry


def entry(
    url: str,
    *,
    method: str = "GET",
    session: str = "s1",
    request_headers: dict[str, list[str]] | None = None,
    response_body: str | None = None,
    request_body: str | None = None,
    status: int = 200,
    mime_type: str = "application/json",
    websocket_messages: list[dict] | None = None,
) -> HarEntry:
    return HarEntry(
        url=url,
        method=method,
        status=status,
        mime_type=mime_type,
        request_headers=request_headers or {},
        response_headers={"content-type": [mime_type]},
        query_params={},
        request_body=request_body,
        response_body=response_body,
        cookies=[],
        timings={"wait": 10},
        session=session,
        websocket_messages=websocket_messages or [],
    )


def test_build_api_model_clusters_paths_and_scores_coverage():
    entries = [
        entry("https://api.example.test/events/123/odds?lang=en", session="s1", response_body='{"price":1.2}'),
        entry("https://api.example.test/events/456/odds?lang=en", session="s2", response_body='{"price":1.3}'),
    ]

    model = build_api_model(entries)

    endpoint = model.endpoints[0]
    assert endpoint.domain == "api.example.test"
    assert endpoint.method == "GET"
    assert endpoint.path_template == "/events/{id}/odds"
    assert endpoint.path_parameters == ["id"]
    assert endpoint.coverage.sample_count == 2
    assert endpoint.coverage.session_count == 2
    assert endpoint.coverage.confidence == "medium"
    assert "error response" in endpoint.coverage.gaps


def test_build_api_model_does_not_cluster_unrelated_resources():
    entries = [
        entry("https://api.example.test/events/123", response_body='{"id":"123"}'),
        entry("https://api.example.test/users/456", response_body='{"id":"456"}'),
    ]

    model = build_api_model(entries)
    paths = sorted(endpoint.path_template for endpoint in model.endpoints)

    assert paths == ["/events/{id}", "/users/{id}"]


def test_api_model_detects_dynamic_headers_and_endpoint_dependencies():
    entries = [
        entry(
            "https://api.example.test/search?q=team",
            response_body='{"eventId":"evt-100"}',
        ),
        entry(
            "https://api.example.test/events/evt-100",
            request_headers={"authorization": ["Bearer one"]},
            response_body='{"name":"Match"}',
        ),
        entry(
            "https://api.example.test/events/evt-200",
            session="s2",
            request_headers={"authorization": ["Bearer two"]},
            response_body='{"name":"Other"}',
        ),
    ]

    model = build_api_model(entries)
    detail = next(e for e in model.endpoints if e.path_template == "/events/{id}")

    assert detail.tokens["authorization"].classification == "dynamic"
    assert detail.dependencies[0].source_endpoint == "GET /search"
    assert detail.dependencies[0].field == "eventId"


def test_generate_openapi_uses_clustered_paths_and_json_schema():
    entries = [
        entry(
            "https://api.example.test/events/123",
            response_body='{"id":"123","active":true}',
        )
    ]
    spec = generate_openapi(build_api_model(entries))

    assert spec["openapi"] == "3.1.0"
    assert "/events/{id}" in spec["paths"]
    operation = spec["paths"]["/events/{id}"]["get"]
    assert operation["parameters"][0]["name"] == "id"
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["type"] == "object"
    assert schema["properties"]["active"]["type"] == "boolean"


def test_generate_asyncapi_from_websocket_messages():
    entries = [
        entry(
            "wss://live.example.test/socket",
            method="GET",
            status=101,
            websocket_messages=[
                {"type": "send", "data": '{"subscribe":"odds"}'},
                {"type": "receive", "data": '{"eventId":"123","price":1.5}'},
            ],
        )
    ]

    spec = generate_asyncapi(build_api_model(entries))

    assert spec["asyncapi"] == "3.0.0"
    assert "live.example.test" in spec["servers"]
    assert "GET /socket" in spec["channels"]
    message = spec["channels"]["GET /socket"]["messages"]["observedMessage"]
    assert message["payload"]["properties"]["price"]["type"] == "number"


def test_replay_curl_redacts_sensitive_values_by_default():
    sample = entry(
        "https://api.example.test/events/123?token=secret",
        request_headers={
            "authorization": ["Bearer secret-token"],
            "accept": ["application/json"],
        },
    )

    command = replay_curl(sample)

    assert "curl" in command
    assert "authorization: <redacted>" in command
    assert "Bearer secret-token" not in command
    assert "token=<redacted>" in command


def test_redact_model_masks_headers_query_values_and_body_fields():
    model = build_api_model(
        [
            entry(
                "https://api.example.test/me?access_token=secret",
                request_headers={"cookie": ["sid=abc"], "x-api-key": ["key"]},
                response_body=json.dumps({"email": "u@example.test", "name": "User"}),
            )
        ]
    )

    redacted = redact_model(model).to_dict()
    endpoint = redacted["endpoints"][0]

    assert endpoint["query_parameters"]["access_token"]["sample_values"] == ["<redacted>"]
    assert endpoint["tokens"]["cookie"]["sample_values"] == ["<redacted>"]
    assert "<redacted>" in json.dumps(endpoint["response_schema"])
    assert "u@example.test" not in json.dumps(redacted)


def test_endpoint_summary_is_assistant_friendly():
    model = build_api_model([entry("https://api.example.test/events/123")])
    summary = endpoint_summary(model)

    assert summary[0]["endpoint"] == "GET /events/{id}"
    assert summary[0]["coverage"]["sample_count"] == 1
