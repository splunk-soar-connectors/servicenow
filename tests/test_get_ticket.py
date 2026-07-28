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

from src.actions import get_ticket as get_ticket_module
from src.actions.get_ticket import GetTicketParams, get_ticket


run_get_ticket = get_ticket.__wrapped__


def test_get_ticket_continues_when_journal_lookup_fails(
    monkeypatch, fake_soar, asset_factory
):
    class FakeServiceNowClient:
        def __init__(self, asset):
            self.asset = asset

        def make_rest_call(self, endpoint, params=None):
            if endpoint == "/table/incident/ticket-sys-id":
                return {
                    "result": {
                        "sys_id": "ticket-sys-id",
                        "number": "INC0000001",
                        "short_description": "Network issue",
                    }
                }
            if endpoint == "/attachment":
                return {"result": []}
            if endpoint == "/table/sys_journal_field":
                raise RuntimeError("journal field access denied")
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(get_ticket_module, "ServiceNowClient", FakeServiceNowClient)

    output = run_get_ticket(
        GetTicketParams(
            table="incident",
            id="ticket-sys-id",
            is_sys_id=True,
        ),
        fake_soar,
        asset_factory(),
    )

    assert output.model_dump() == {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Network issue",
        "comments_section": [],
        "worknotes_section": [],
    }
    assert fake_soar.message == "Successfully retrieved ticket INC0000001"
    assert fake_soar.summary.queried_ticket_id == "ticket-sys-id"
