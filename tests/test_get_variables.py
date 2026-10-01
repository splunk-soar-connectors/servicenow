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

import pytest
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_reserved_variable_name_is_normalized():
    module = importlib.import_module("src.actions.get_variables")

    assert module._normalize_variable_name("sys_id") == "variable_sys_id"
    assert module._normalize_variable_name("requested_for") == "requested_for"


def test_get_variables_rejects_encoded_query_operators(monkeypatch):
    module = importlib.import_module("src.actions.get_variables")

    class FakeClient:
        def __init__(self, asset):
            pytest.fail("ServiceNow should not be called for an invalid sys_id")

    monkeypatch.setattr(module, "ServiceNowClient", FakeClient)
    params = module.GetVariablesParams(sys_id="item-id^ORrequest_item=other")

    with pytest.raises(ActionFailure, match="sys_id"):
        module.get_variables.__wrapped__(params, object(), object())
