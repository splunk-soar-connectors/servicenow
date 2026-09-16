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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeSoar:
    def __init__(self):
        self.message = None

    def set_message(self, message):
        self.message = message


def test_update_ticket_attachment_failure_preserves_partial_result(monkeypatch):
    module = importlib.import_module("src.actions.update_ticket")

    class FakeClient:
        def __init__(self, asset):
            pass

        def make_rest_call(self, endpoint, data=None, method="get"):
            return {
                "result": {
                    "sys_id": "ticket-sys-id",
                    "number": "INC0000001",
                    "short_description": "updated",
                }
            }

    class FakeActionHelper:
        def __init__(self, soar, helper):
            pass

        def handle_vault_attachments(self, table, ticket_id, vault_ids):
            return [{"sys_id": "attachment-sys-id"}], {
                "bad-vault": "Vault ID not valid"
            }

    monkeypatch.setattr(module, "ServiceNowClient", FakeClient)
    monkeypatch.setattr(module, "ServiceNowActionHelper", FakeActionHelper)

    params = module.UpdateTicketParams(
        table="incident",
        vault_id="bad-vault",
        id="ticket-sys-id",
        fields='{"short_description": "updated"}',
        is_sys_id=True,
    )

    result = module.update_ticket.__wrapped__(params, FakeSoar(), SimpleNamespace())

    assert result.get_status() is False
    assert result.get_param() == params.model_dump(mode="json")
    assert result.get_data() == [
        {
            "sys_id": "ticket-sys-id",
            "number": "INC0000001",
            "short_description": "updated",
        }
    ]
    assert result.get_summary() == {
        "fields_updated": True,
        "successfully_added_attachments_count": 1,
        "vault_failure_details": {"Vault ID not valid": ["bad-vault"]},
    }
    assert "Successfully updated the ticket" in result.get_message()
