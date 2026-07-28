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
from types import SimpleNamespace
from typing import ClassVar

import pytest
from soar_sdk.exceptions import ActionFailure

from src.actions import run_query as run_query_module
from src.actions.run_query import RunQueryParams, run_query
from src.consts import SERVICENOW_SENSITIVE_PROPS

run_run_query = run_query.__wrapped__


def test_run_query_strips_sensitive_properties(monkeypatch, asset_factory):
    class FakeServiceNowClient:
        calls: ClassVar[list[dict]] = []

        def __init__(self, asset):
            self.asset = asset

        def paginator(self, endpoint, payload, limit):
            self.calls.append(
                {"endpoint": endpoint, "payload": payload, "limit": limit}
            )
            return [
                {
                    "number": "INC0000001",
                    "short_description": "safe",
                    "admin_password": "admin-secret",  # pragma: allowlist secret
                    "database_password": "db-secret",  # pragma: allowlist secret
                    "password": "generic-secret",  # pragma: allowlist secret
                    "user_password": "user-secret",  # pragma: allowlist secret
                }
            ]

    class FakeSoar:
        def __init__(self):
            self.summary = None

        def set_summary(self, summary):
            self.summary = summary

    monkeypatch.setattr(run_query_module, "ServiceNowClient", FakeServiceNowClient)

    output = run_run_query(
        RunQueryParams(
            query="sysparm_query=number=INC0000001",
            query_table="incident",
            max_results=1,
        ),
        FakeSoar(),
        asset_factory(),
    )

    dumped = output[0].model_dump()
    assert SERVICENOW_SENSITIVE_PROPS == [
        "admin_password",
        "database_password",
        "user_password",
    ]
    for sensitive_prop in SERVICENOW_SENSITIVE_PROPS:
        assert sensitive_prop not in dumped

    assert dumped["password"] == "generic-secret"  # pragma: allowlist secret
    assert dumped["number"] == "INC0000001"
    assert dumped["short_description"] == "safe"


@pytest.mark.parametrize("max_results", [0, -1])
def test_run_query_rejects_non_positive_max_results(max_results, asset_factory):
    with pytest.raises(ActionFailure, match=r"positive|non-negative"):
        run_run_query(
            RunQueryParams(
                query="sysparm_query=number=INC0000001",
                query_table="incident",
                max_results=max_results,
            ),
            SimpleNamespace(set_summary=lambda summary: None),
            asset_factory(),
        )
