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

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.servicenow_client import ServiceNowClient


@pytest.mark.parametrize(
    "ticket_number", ["INC001^ORnumber=INC002", "INC001^ORactive=true"]
)
def test_ticket_number_rejects_encoded_query_operators(ticket_number):
    client = object.__new__(ServiceNowClient)
    client.make_rest_call = lambda *args, **kwargs: pytest.fail(
        "ServiceNow should not be called for an invalid ticket number"
    )

    with pytest.raises(ActionFailure, match="ticket_number"):
        client.get_sys_id_from_ticket_number("incident", ticket_number)


@pytest.mark.parametrize("field", ["user_id", "username"])
def test_query_users_rejects_encoded_query_operators(monkeypatch, field):
    module = importlib.import_module("src.actions.query_users")

    class FakeClient:
        def __init__(self, asset):
            pass

        def paginator(self, *args, **kwargs):
            raise AssertionError(
                "ServiceNow should not be called for an invalid selector"
            )

    monkeypatch.setattr(module, "ServiceNowClient", FakeClient)

    values = {"max_results": 10}
    values[field] = "admin^ORuser_name=guest"
    params = module.QueryUsersParams(**values)

    with pytest.raises(ActionFailure, match=field):
        module.query_users.__wrapped__(params, SimpleNamespace(), SimpleNamespace())


@pytest.mark.parametrize("field", ["catalog_sys_id", "category_sys_id"])
def test_list_services_rejects_encoded_query_operators(monkeypatch, field):
    module = importlib.import_module("src.actions.list_services")

    class FakeClient:
        def __init__(self, asset):
            raise AssertionError(
                "ServiceNow should not be called for an invalid selector"
            )

    monkeypatch.setattr(module, "ServiceNowClient", FakeClient)

    values = {"max_results": 10}
    values[field] = "abc123^ORactive=true"
    params = module.ListServicesParams(**values)

    with pytest.raises(ActionFailure, match=field):
        module.list_services.__wrapped__(params, SimpleNamespace(), SimpleNamespace())
