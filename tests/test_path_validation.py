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
import sys
from pathlib import Path

import pytest
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions import create_ticket as create_ticket_module
from src.actions.create_ticket import CreateTicketParams, create_ticket
from src.helpers import validate_path_segment

run_create_ticket = create_ticket.__wrapped__


@pytest.mark.parametrize(
    "value",
    [
        "incident",
        "sys_user",
        "abc123.DEF-456_789",
    ],
)
def test_validate_path_segment_accepts_single_safe_segment(value):
    assert validate_path_segment("table", value) == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        "incident/sys_user",
        "incident?sysparm_query=active=true",
        "incident#fragment",
        "incident%2Fsys_user",
        "incident&sysparm_limit=1",
    ],
)
def test_validate_path_segment_rejects_path_and_query_delimiters(value):
    with pytest.raises(ActionFailure, match="Invalid 'table' parameter"):
        validate_path_segment("table", value)


def test_create_ticket_rejects_unsafe_table_before_rest_call(monkeypatch):
    class UnexpectedServiceNowClient:
        def __init__(self, asset):
            raise AssertionError("ServiceNowClient should not be constructed")

    monkeypatch.setattr(
        create_ticket_module, "ServiceNowClient", UnexpectedServiceNowClient
    )

    with pytest.raises(ActionFailure, match="Invalid 'table' parameter"):
        run_create_ticket(
            CreateTicketParams(
                short_description="Test ticket",
                description="Ticket body",
                table="incident/sys_user",
                vault_id="",
                fields="",
            ),
            SimpleNamespace(),
            SimpleNamespace(),
        )
