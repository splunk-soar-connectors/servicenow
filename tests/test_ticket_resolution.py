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
import pytest

from src.consts import TicketNotFoundException
from src.helpers import ServiceNowClient


def test_ticket_number_resolution_requires_exact_returned_number(
    monkeypatch, asset_factory
):
    client = ServiceNowClient(asset_factory())

    def fake_make_rest_call(endpoint, params):
        assert endpoint == "/table/incident"
        assert params == {"sysparm_query": "number=INC0000001"}
        return {
            "result": [
                {"number": "INC0000002", "sys_id": "ticket-sys-id"}
            ]
        }

    monkeypatch.setattr(client, "make_rest_call", fake_make_rest_call)

    with pytest.raises(
        TicketNotFoundException,
        match="ServiceNow returned a different ticket than the requested ticket number",
    ):
        client.get_sys_id_from_ticket_number("incident", "INC0000001")


def test_ticket_number_resolution_returns_sys_id_for_exact_match(
    monkeypatch, asset_factory
):
    client = ServiceNowClient(asset_factory())

    monkeypatch.setattr(
        client,
        "make_rest_call",
        lambda endpoint, params: {
            "result": [
                {"number": "INC0000001", "sys_id": "ticket-sys-id"}
            ]
        },
    )

    assert (
        client.get_sys_id_from_ticket_number("incident", "INC0000001")
        == "ticket-sys-id"
    )
