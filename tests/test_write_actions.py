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

import pytest
from soar_sdk.exceptions import ActionFailure

from src.actions import add_comment as add_comment_module
from src.actions import add_work_note as add_work_note_module
from src.actions import update_ticket as update_ticket_module
from src.actions.add_comment import AddCommentParams, add_comment
from src.actions.add_work_note import AddWorkNoteParams, add_work_note
from src.actions.update_ticket import UpdateTicketParams, update_ticket

run_add_comment = add_comment.__wrapped__
run_add_work_note = add_work_note.__wrapped__
run_update_ticket = update_ticket.__wrapped__


def test_add_comment_fails_on_empty_write_result(monkeypatch, asset_factory):
    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def make_rest_call(self, **kwargs):
            return {"result": {}}

    monkeypatch.setattr(add_comment_module, "ServiceNowClient", FakeServiceNowClient)

    with pytest.raises(ActionFailure, match="No results found after adding comment"):
        run_add_comment(
            AddCommentParams(
                table_name="incident",
                id="0123456789abcdef0123456789abcdef",
                comment="hello",
                is_sys_id=True,
            ),
            SimpleNamespace(),
            asset_factory(),
        )


def test_add_work_note_fails_on_empty_write_result(monkeypatch, asset_factory):
    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def make_rest_call(self, *args, **kwargs):
            return {"result": {}}

    monkeypatch.setattr(add_work_note_module, "ServiceNowClient", FakeServiceNowClient)

    with pytest.raises(ActionFailure, match="No data returned from ServiceNow"):
        run_add_work_note(
            AddWorkNoteParams(
                table_name="incident",
                id="0123456789abcdef0123456789abcdef",
                work_note="hello",
                is_sys_id=True,
            ),
            SimpleNamespace(),
            asset_factory(),
        )


def test_update_ticket_fails_on_empty_write_result(monkeypatch, asset_factory):
    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def make_rest_call(self, endpoint, data=None, method="get"):
            return {"result": {}}

    monkeypatch.setattr(update_ticket_module, "ServiceNowClient", FakeServiceNowClient)

    with pytest.raises(ActionFailure, match="Invalid response from ServiceNow"):
        run_update_ticket(
            UpdateTicketParams(
                table="incident",
                id="0123456789abcdef0123456789abcdef",
                fields='{"short_description": "updated"}',
                vault_id="",
                is_sys_id=True,
            ),
            SimpleNamespace(
                set_summary=lambda summary: None, set_message=lambda message: None
            ),
            asset_factory(),
        )
