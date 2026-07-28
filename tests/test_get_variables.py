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
from typing import ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions import get_variables as get_variables_module
from src.actions.get_variables import GetVariablesParams, get_variables

run_get_variables = get_variables.__wrapped__


class FakeSoar:
    def __init__(self):
        self.summary = None
        self.message = None

    def set_summary(self, summary):
        self.summary = summary

    def set_message(self, message):
        self.message = message


class FakeServiceNowClient:
    calls: ClassVar[list[dict]] = []

    def __init__(self, asset):
        self.asset = asset

    def make_rest_call(self, endpoint, params=None, **kwargs):
        self.calls.append({"endpoint": endpoint, "params": params, **kwargs})

        if endpoint == "/table/sc_item_option_mtom":
            return {"result": [{"sc_item_option": "option-sys-id"}]}
        if endpoint == "/table/sc_item_option/option-sys-id":
            return {
                "result": {
                    "value": "Adobe Acrobat",
                    "item_option_new": "question-sys-id",
                }
            }
        if endpoint == "/table/item_option_new/question-sys-id":
            return {"result": {"question_text": "Optional Software"}}

        raise AssertionError(f"Unexpected endpoint: {endpoint}")


def test_get_variables_queries_request_item_and_handles_string_references(monkeypatch):
    FakeServiceNowClient.calls = []
    monkeypatch.setattr(get_variables_module, "ServiceNowClient", FakeServiceNowClient)

    soar = FakeSoar()
    output = run_get_variables(
        GetVariablesParams(sys_id="ritm-sys-id"),
        soar,
        SimpleNamespace(),
    )

    assert FakeServiceNowClient.calls[0] == {
        "endpoint": "/table/sc_item_option_mtom",
        "params": {
            "sysparm_query": "request_item=ritm-sys-id",
            "sysparm_display_value": "all",
        },
    }
    assert FakeServiceNowClient.calls[1] == {
        "endpoint": "/table/sc_item_option/option-sys-id",
        "params": {"sysparm_display_value": "all"},
    }
    assert output.model_dump() == {
        "sys_id": "ritm-sys-id",
        "Optional Software": "Adobe Acrobat",
    }
    assert soar.summary.num_variables == 1
    assert soar.message == "Num variables: 1"
