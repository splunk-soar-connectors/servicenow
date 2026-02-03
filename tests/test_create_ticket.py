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
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions import create_ticket as create_ticket_module
from src.actions.create_ticket import CreateTicketParams, create_ticket

run_create_ticket = create_ticket.__wrapped__


class FakeSoar:
    def __init__(self):
        self.message = None
        self.summary = None

    def get_executing_container_id(self):
        return "1234"

    def set_message(self, message):
        self.message = message

    def set_summary(self, summary):
        self.summary = summary


class FakeServiceNowClient:
    payloads: ClassVar[list[dict]] = []

    def __init__(self, asset):
        self.asset = asset

    def make_rest_call(self, endpoint, data=None, method=None):
        self.payloads.append({"endpoint": endpoint, "data": data, "method": method})
        return {
            "result": {
                "sys_id": "ticket-sys-id",
                "description": data["description"],
            }
        }


def test_create_ticket_preserves_legacy_description_footnote(monkeypatch):
    FakeServiceNowClient.payloads = []
    monkeypatch.setattr(create_ticket_module, "ServiceNowClient", FakeServiceNowClient)

    output = run_create_ticket(
        CreateTicketParams(
            short_description="Test ticket",
            description="Ticket body",
            table="incident",
            vault_id="",
            fields="",
        ),
        FakeSoar(),
        SimpleNamespace(),
    )

    expected_description = "Ticket body\n\nAdded by Phantom for container id: 1234"
    assert FakeServiceNowClient.payloads == [
        {
            "endpoint": "/table/incident",
            "data": {
                "short_description": "Test ticket",
                "description": expected_description,
            },
            "method": "post",
        }
    ]
    assert output.description == expected_description
