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
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import servicenow_client
from src.actions.run_query import RunQueryParams, run_query
from src.consts import BASIC_AUTH_TYPE
from src.servicenow_client import ServiceNowClient


@pytest.fixture
def asset():
    return SimpleNamespace(
        url="https://example.service-now.com",
        username="test-user",
        password="test-password",  # pragma: allowlist secret
        client_id=None,
        client_secret=None,
        oauth_grant_type=BASIC_AUTH_TYPE,
    )


def capture_requests(monkeypatch, responses):
    requests = []
    client_class = httpx.Client

    def handle_request(request):
        response = responses[len(requests)]
        requests.append(request)
        return response

    def make_client(**kwargs):
        return client_class(transport=httpx.MockTransport(handle_request), **kwargs)

    monkeypatch.setattr(servicenow_client.httpx, "Client", make_client)
    return requests


def test_run_query_preserves_filter_and_options_on_every_page(monkeypatch, asset):
    records = [
        {"number": "INC001", "sys_id": "id-1"},
        {"number": "INC002", "sys_id": "id-2"},
    ]
    requests = capture_requests(
        monkeypatch,
        [
            httpx.Response(
                200, json={"result": [record]}, headers={"X-Total-Count": "3"}
            )
            for record in records
        ],
    )
    summaries = []
    soar = SimpleNamespace(set_summary=summaries.append)
    params = RunQueryParams(
        query_table="incident",
        query=(
            "sysparm_query=active%3Dtrue%5Eshort_descriptionLIKEC%2B%2B%20%26%20audit"
            "&sysparm_fields=number%2Csys_id&sysparm_display_value=true&sysparm_view="
            "&sysparm_offset=99&sysparm_limit=99"
        ),
        max_results=2,
    )

    outputs = run_query.__wrapped__(params, soar, asset)

    assert [output.number for output in outputs] == ["INC001", "INC002"]
    assert summaries[0].total_tickets == 2
    assert len(requests) == 2
    for request, (offset, limit) in zip(
        requests, [("0", "2"), ("2", "1")], strict=True
    ):
        assert request.url.path == "/api/now/table/incident"
        query = request.url.params
        assert query["sysparm_query"] == "active=true^short_descriptionLIKEC++ & audit"
        assert query["sysparm_fields"] == "number,sys_id"
        assert query["sysparm_display_value"] == "true"
        assert query["sysparm_view"] == ""
        assert query.get_list("sysparm_offset") == [offset]
        assert query.get_list("sysparm_limit") == [limit]


@pytest.mark.parametrize("params", [None, {}])
def test_rest_call_preserves_url_query_without_extra_params(monkeypatch, asset, params):
    requests = capture_requests(monkeypatch, [httpx.Response(200, json={"result": []})])

    assert ServiceNowClient(asset).make_rest_call(
        "/table/incident?sysparm_query=number%3DINC001&sysparm_fields=number",
        params=params,
    ) == {"result": []}
    assert requests[0].url.params["sysparm_query"] == "number=INC001"
    assert requests[0].url.params["sysparm_fields"] == "number"
