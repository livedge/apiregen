from __future__ import annotations

import base64
import gzip
import json

from apiregen.har import iter_har_entries, parse_har


def test_parse_har_decodes_base64_gzip_response_body(tmp_path):
    compressed = gzip.compress(b'{"ok": true}')
    har_path = tmp_path / "gzip.har"
    har_path.write_text(
        json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "request": {"method": "GET", "url": "https://api.example.test/data", "headers": []},
                            "response": {
                                "status": 200,
                                "headers": [{"name": "Content-Encoding", "value": "gzip"}],
                                "content": {
                                    "mimeType": "application/json",
                                    "encoding": "base64",
                                    "text": base64.b64encode(compressed).decode(),
                                },
                            },
                            "timings": {},
                        }
                    ]
                }
            }
        )
    )

    entries = parse_har(har_path)

    assert entries[0].response_body == '{"ok": true}'


def test_parse_har_preserves_websocket_messages(tmp_path):
    har_path = tmp_path / "ws.har"
    har_path.write_text(
        json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "request": {
                                "method": "GET",
                                "url": "wss://live.example.test/socket",
                                "headers": [{"name": "Upgrade", "value": "websocket"}],
                            },
                            "response": {"status": 101, "headers": [], "content": {}},
                            "_webSocketMessages": [
                                {"type": "send", "data": '{"subscribe":"events"}'},
                                {"type": "receive", "data": '{"eventId":"1"}'},
                            ],
                            "timings": {},
                        }
                    ]
                }
            }
        )
    )

    entries = parse_har(har_path)

    assert entries[0].websocket_messages == [
        {"type": "send", "data": '{"subscribe":"events"}'},
        {"type": "receive", "data": '{"eventId":"1"}'},
    ]


def test_iter_har_entries_streams_entries_without_changing_parse_result(tmp_path):
    har_path = tmp_path / "many.har"
    har_path.write_text(
        json.dumps(
            {
                "log": {
                    "entries": [
                        {
                            "request": {"method": "GET", "url": f"https://api.example.test/items/{idx}", "headers": []},
                            "response": {"status": 200, "headers": [], "content": {"text": "{}"}},
                            "timings": {},
                        }
                        for idx in range(3)
                    ]
                }
            }
        )
    )

    streamed = list(iter_har_entries(har_path))
    parsed = parse_har(har_path)

    assert [entry.url for entry in streamed] == [entry.url for entry in parsed]
