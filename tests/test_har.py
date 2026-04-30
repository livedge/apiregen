from __future__ import annotations

import base64
import json

from apiregen.har import parse_har


def test_parse_har_decodes_base64_response_and_extracts_query_params(tmp_path):
    body = json.dumps({"items": [{"id": 1}]})
    har_path = tmp_path / "session1.har"
    har_path.write_text(
        json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "request": {
                                "method": "GET",
                                "url": "https://api.example.test/v1/items?page=1&page=2&q=odds",
                                "headers": [{"name": "Accept", "value": "application/json"}],
                                "cookies": [{"name": "sid", "value": "abc"}],
                            },
                            "response": {
                                "status": 200,
                                "headers": [
                                    {"name": "Content-Type", "value": "application/json"}
                                ],
                                "content": {
                                    "mimeType": "application/json",
                                    "encoding": "base64",
                                    "text": base64.b64encode(body.encode()).decode(),
                                },
                            },
                            "timings": {"wait": 12},
                        }
                    ]
                }
            }
        )
    )

    entries = parse_har(har_path)

    assert len(entries) == 1
    assert entries[0].session == "session1"
    assert entries[0].query_params == {"page": "2", "q": "odds"}
    assert entries[0].request_headers == {"accept": ["application/json"]}
    assert entries[0].response_body == body
