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
import httpx

from src import helpers as helpers_module
from src.helpers import ServiceNowClient


def test_paginator_stops_when_total_count_reached(monkeypatch, asset_factory):
    client = ServiceNowClient(asset_factory())
    calls = []

    def fake_make_rest_call(endpoint, params):
        calls.append(params.copy())
        client._response_headers = {"X-Total-Count": "1"}
        return {"result": [{"number": "INC0000001"}]}

    monkeypatch.setattr(client, "make_rest_call", fake_make_rest_call)

    assert client.paginator("/table/incident", limit=100) == [{"number": "INC0000001"}]
    assert calls == [{"sysparm_offset": 0, "sysparm_limit": 100}]


def test_paginator_bounds_pages_when_total_count_is_missing(monkeypatch, asset_factory):
    client = ServiceNowClient(asset_factory())
    calls = []

    def fake_make_rest_call(endpoint, params):
        calls.append(params.copy())
        client._response_headers = {}
        return {"result": [{"number": f"INC{len(calls):07d}"}]}

    monkeypatch.setattr(helpers_module, "MAX_PAGES", 2)
    monkeypatch.setattr(client, "make_rest_call", fake_make_rest_call)

    assert client.paginator("/table/incident") == [
        {"number": "INC0000001"},
        {"number": "INC0000002"},
    ]
    assert len(calls) == 2


def test_paginator_ignores_invalid_total_count_header(monkeypatch, asset_factory):
    client = ServiceNowClient(asset_factory())
    calls = []
    responses = [
        {"result": [{"number": "INC0000001"}]},
        {"result": []},
    ]

    def fake_make_rest_call(endpoint, params):
        calls.append(params.copy())
        client._response_headers = {"X-Total-Count": "not-an-int"}
        return responses.pop(0)

    monkeypatch.setattr(client, "make_rest_call", fake_make_rest_call)

    assert client.paginator("/table/incident", limit=100) == [{"number": "INC0000001"}]
    assert len(calls) == 2


def test_make_rest_call_records_response_headers(monkeypatch, asset_factory):
    class FakeHTTPClient:
        def __init__(self, auth, timeout):
            self.auth = auth
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, **kwargs):
            return httpx.Response(
                200,
                json={"result": []},
                headers={"X-Total-Count": "42"},
            )

    client = ServiceNowClient(asset_factory())
    monkeypatch.setattr(helpers_module.httpx, "Client", FakeHTTPClient)
    monkeypatch.setattr(client, "get_auth", lambda: "auth")

    assert client.make_rest_call("/table/incident") == {"result": []}
    assert client._response_headers["x-total-count"] == "42"
