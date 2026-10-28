# Copyright (c) 2016-2026 Splunk Inc.
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

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from soar_sdk.auth.client import OAuthClientError
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.servicenow_client import ServiceNowClient


def capture_failures(monkeypatch, module, asset):
    results = []
    soar = SimpleNamespace(set_message=lambda message: None)
    monkeypatch.setattr(
        module.app,
        "_build_magic_args",
        lambda *args, **kwargs: {"soar": soar, "asset": asset},
    )
    monkeypatch.setattr(module.app.actions_manager, "add_result", results.append)
    monkeypatch.setattr(
        module.app.actions_manager,
        "add_exception",
        lambda error: pytest.fail(f"Unexpected generic exception: {error}"),
    )
    return soar, results


@pytest.mark.parametrize(
    "action,params_class,values",
    [
        (
            "add_comment",
            "AddCommentParams",
            {"id": "INC001", "comment": "test", "table_name": "incident"},
        ),
        (
            "add_work_note",
            "AddWorkNoteParams",
            {"id": "INC001", "work_note": "test", "table_name": "incident"},
        ),
        (
            "update_ticket",
            "UpdateTicketParams",
            {"id": "INC001", "fields": '{"short_description":"test"}'},
        ),
    ],
)
@pytest.mark.parametrize(
    "response",
    [
        {"result": []},
        {"result": {}},
        {"result": [{"number": "INC002", "sys_id": "other-id"}]},
        {"result": [{"number": "INC001"}]},
    ],
)
def test_ticket_resolution_errors_are_controlled(
    monkeypatch, action, params_class, values, response
):
    module = importlib.import_module(f"src.actions.{action}")
    client = object.__new__(ServiceNowClient)
    calls = []

    def request(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return response

    client.make_rest_call = request
    monkeypatch.setattr(module, "ServiceNowClient", lambda asset: client)
    soar, results = capture_failures(monkeypatch, module, object())
    params = getattr(module, params_class)(**values)

    assert getattr(module, action)(params, soar) is False
    assert len(results) == 1
    assert results[0].get_status() is False
    assert "Traceback" not in results[0].get_message()
    assert any(
        message in results[0].get_message()
        for message in [
            "Ticket not found",
            "different ticket",
            "Unable to fetch ticket SYS ID",
        ]
    )
    assert calls == [
        ("/table/incident", {"params": {"sysparm_query": "number=INC001"}})
    ]


@pytest.mark.parametrize("response", [{}, {"result": {}}, {"result": None}])
def test_missing_catalog_item_is_controlled(monkeypatch, response):
    module = importlib.import_module("src.actions.describe_catalog_item")
    client = SimpleNamespace(make_rest_call=lambda **kwargs: response)
    monkeypatch.setattr(module, "ServiceNowClient", lambda asset: client)
    soar, results = capture_failures(monkeypatch, module, object())

    assert (
        module.describe_catalog_item(
            module.DescribeCatalogItemParams(sys_id="item-id"), soar
        )
        is False
    )
    assert (
        "No data found for the requested item having System ID: item-id"
        in results[0].get_message()
    )
    assert "Traceback" not in results[0].get_message()


@pytest.mark.parametrize("stage", ["authentication", "resource"])
def test_connectivity_operational_errors_are_controlled(monkeypatch, stage):
    module = importlib.import_module("src.actions.test_connectivity")
    asset = SimpleNamespace(
        oauth_grant_type="password",
        client_id="client-id",
        client_secret="client-secret",  # pragma: allowlist secret
    )
    calls = []

    def fresh_token():
        calls.append("authentication")
        if stage == "authentication":
            raise OAuthClientError("Token endpoint unavailable")

    def request(*args, **kwargs):
        calls.append("resource")
        raise ActionFailure("Incident API unavailable")

    client = SimpleNamespace(
        asset=asset, force_new_oauth_token=fresh_token, make_rest_call=request
    )
    monkeypatch.setattr(module, "ServiceNowClient", lambda asset: client)
    soar, results = capture_failures(monkeypatch, module, asset)

    assert module.test_connectivity(soar=soar) is False
    message = results[0].get_message()
    assert "Test Connectivity Failed" in message
    assert "Traceback" not in message
    assert (
        "Token endpoint unavailable"
        if stage == "authentication"
        else "Incident API unavailable"
    ) in message
    assert calls == (
        ["authentication"]
        if stage == "authentication"
        else ["authentication", "resource"]
    )


def test_connectivity_programming_error_is_not_reclassified(monkeypatch):
    module = importlib.import_module("src.actions.test_connectivity")
    asset = SimpleNamespace(
        oauth_grant_type="basic_auth", client_id=None, client_secret=None
    )

    def request(*args, **kwargs):
        raise RuntimeError("Unexpected defect")

    client = SimpleNamespace(asset=asset, make_rest_call=request)
    monkeypatch.setattr(module, "ServiceNowClient", lambda asset: client)
    with pytest.raises(RuntimeError, match="Unexpected defect"):
        module.test_connectivity.__wrapped__(SimpleNamespace(), asset)
