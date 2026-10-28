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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"catalog_sys_id": "catalog-id"},
        {"category_sys_id": "category-id"},
        {"search_text": "missing"},
    ],
)
def test_empty_services_returns_controlled_failure(monkeypatch, filters):
    module = importlib.import_module("src.actions.list_services")

    class FakeClient:
        def __init__(self, asset):
            pass

        def fetch_catalog_items(self, **kwargs):
            return []

    monkeypatch.setattr(module, "ServiceNowClient", FakeClient)
    params = module.ListServicesParams(**filters)
    soar = SimpleNamespace(set_summary=lambda summary: None)
    result = module.list_services.__wrapped__(params, soar, object())

    assert result.get_status() is False
    assert result.get_param() == params.model_dump(mode="json")
    assert result.get_summary() == {"services_returned": 0}
    assert result.get_data() == []
    assert result.get_message() == (
        "No data found for the given input parameters" if filters else "No data found"
    )

    adapted_results = []
    manager = SimpleNamespace(add_result=adapted_results.append)
    assert module.app._adapt_action_result(result, manager, params) is False
    assert adapted_results == [result]
