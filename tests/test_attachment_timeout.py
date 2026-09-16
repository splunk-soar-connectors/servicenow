# Copyright (c) 2026 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import servicenow_client
from src.consts import DEFAULT_REQUEST_TIMEOUT
from src.servicenow_client import ServiceNowClient


def test_upload_attachment_uses_default_request_timeout(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"result": {"sys_id": "attachment-id"}}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    client = object.__new__(ServiceNowClient)
    client._base_url = "https://example.com"
    client.timeout = DEFAULT_REQUEST_TIMEOUT
    monkeypatch.setattr(client, "get_auth", lambda: None)
    monkeypatch.setattr(servicenow_client.httpx, "Client", FakeClient)

    success, result, error = client.upload_attachment(
        "incident", "ticket-id", "evidence.txt", b"data", "text/plain"
    )

    assert success is True
    assert result == {"sys_id": "attachment-id"}
    assert error is None
    assert captured["timeout"] == DEFAULT_REQUEST_TIMEOUT
