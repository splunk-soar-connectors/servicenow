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

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import servicenow_client
from src.servicenow_client import ServiceNowClient


def make_client(monkeypatch, pages):
    client = object.__new__(ServiceNowClient)
    requests = []

    def make_rest_call(endpoint, params):
        headers, result = pages[len(requests)]
        requests.append(dict(params))
        client._response_headers = headers
        return {"result": result}

    monkeypatch.setattr(client, "make_rest_call", make_rest_call)
    return client, requests


@pytest.mark.parametrize("count_header", ["X-Total-Count", "x-total-count"])
def test_paginator_continues_after_empty_first_page(monkeypatch, count_header):
    records = [{"sys_id": "visible-1"}, {"sys_id": "visible-2"}]
    headers = {count_header: "4"}
    client, requests = make_client(monkeypatch, [(headers, []), (headers, records)])

    assert client.paginator("/table/incident", limit=2) == records
    assert requests == [
        {"sysparm_offset": 0, "sysparm_limit": 2},
        {"sysparm_offset": 2, "sysparm_limit": 2},
    ]


def test_paginator_continues_after_empty_middle_page(monkeypatch):
    records = [{"sys_id": f"visible-{index}"} for index in range(3)]
    headers = {"X-Total-Count": "9"}
    client, requests = make_client(
        monkeypatch,
        [(headers, records[:1]), (headers, []), (headers, records[1:])],
    )

    assert client.paginator("/table/incident", limit=3) == records
    assert requests == [
        {"sysparm_offset": 0, "sysparm_limit": 3},
        {"sysparm_offset": 3, "sysparm_limit": 2},
        {"sysparm_offset": 5, "sysparm_limit": 2},
    ]


def test_paginator_stops_at_total_count_when_all_pages_are_empty(monkeypatch):
    headers = {"X-Total-Count": "5"}
    client, requests = make_client(monkeypatch, [(headers, [])] * 3)

    assert client.paginator("/table/incident", limit=2) == []
    assert [request["sysparm_offset"] for request in requests] == [0, 2, 4]


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Total-Count": "invalid"}, {"X-Total-Count": "0"}],
)
def test_paginator_stops_on_empty_page_without_a_positive_count(monkeypatch, headers):
    client, requests = make_client(monkeypatch, [(headers, [])])

    assert client.paginator("/table/incident", limit=2) == []
    assert len(requests) == 1


def test_paginator_limits_empty_pages_when_total_count_is_inaccurate(monkeypatch):
    monkeypatch.setattr(servicenow_client, "MAX_PAGES", 2)
    headers = {"X-Total-Count": "100"}
    client, requests = make_client(monkeypatch, [(headers, [])] * 2)

    assert client.paginator("/table/incident", limit=1) == []
    assert [request["sysparm_offset"] for request in requests] == [0, 1]
