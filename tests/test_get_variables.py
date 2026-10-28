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
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.mark.parametrize(
    "question_names",
    [("sys_id", "variable_sys_id"), ("variable_sys_id", "sys_id"), ("requested_for",)],
)
def test_get_variables_preserves_question_keys(monkeypatch, question_names):
    module = importlib.import_module("src.actions.get_variables")

    class FakeClient:
        def __init__(self, asset):
            pass

        def make_rest_call(self, endpoint, params=None):
            if endpoint == "/table/sc_item_option_mtom":
                return {
                    "result": [
                        {"sc_item_option": {"value": name}} for name in question_names
                    ]
                }
            name = endpoint.rsplit("/", 1)[-1]
            if endpoint.startswith("/table/sc_item_option/"):
                return {
                    "result": {
                        "value": f"answer-{name}",
                        "item_option_new": {"value": name},
                    }
                }
            return {"result": {"question_text": name}}

    captured = {}
    soar = SimpleNamespace(
        set_summary=lambda summary: captured.update(summary=summary),
        set_message=lambda message: captured.update(message=message),
    )
    monkeypatch.setattr(module, "ServiceNowClient", FakeClient)
    result = module.get_variables.__wrapped__(
        module.GetVariablesParams(sys_id="request-item"), soar, object()
    )

    assert result.model_dump() == {name: f"answer-{name}" for name in question_names}
    assert captured["summary"].num_variables == len(question_names)
    assert module.get_variables_view.__wrapped__([result])["results"][0]["data"] == [
        result.model_dump()
    ]


def test_get_variables_rejects_encoded_query_operators(monkeypatch):
    module = importlib.import_module("src.actions.get_variables")

    class FakeClient:
        def __init__(self, asset):
            pytest.fail("ServiceNow should not be called for an invalid sys_id")

    monkeypatch.setattr(module, "ServiceNowClient", FakeClient)
    params = module.GetVariablesParams(sys_id="item-id^ORrequest_item=other")

    with pytest.raises(ActionFailure, match="sys_id"):
        module.get_variables.__wrapped__(params, object(), object())
