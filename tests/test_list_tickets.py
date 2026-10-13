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


def test_list_tickets_rejects_zero_max_results_before_pagination(monkeypatch):
    module = importlib.import_module("src.actions.list_tickets")

    class FakeClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload=None, limit=None):
            raise AssertionError("paginator should not be called")

    monkeypatch.setattr(module, "ServiceNowClient", FakeClient)

    params = module.ListTicketsParams(
        filter="",
        table="incident",
        max_results=0,
    )

    with pytest.raises(
        ActionFailure,
        match="Please provide a positive integer value in the max_results parameter",
    ):
        module.list_tickets.__wrapped__(params, SimpleNamespace(), SimpleNamespace())
