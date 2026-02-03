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
from io import BytesIO
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.helpers import ServiceNowActionHelper


class FakeVault:
    def __init__(self, attachments_by_id):
        self.attachments_by_id = attachments_by_id

    def get_attachment(self, *, vault_id):
        value = self.attachments_by_id[vault_id]
        if isinstance(value, Exception):
            raise value
        return value


class FakeSoar:
    def __init__(self, attachments_by_id):
        self.vault = FakeVault(attachments_by_id)


class FakeVaultFile:
    name = "evidence.txt"
    mime_type = "text/plain"

    def open(self, mode):
        assert mode == "rb"
        return BytesIO(b"evidence")


class FakeClient:
    def __init__(self, upload_result=None):
        self.upload_result = upload_result or {"sys_id": "attachment-id"}
        self.upload_calls = []

    def upload_attachment(self, table, ticket_id, filename, file_content, mime_type):
        self.upload_calls.append(
            {
                "table": table,
                "ticket_id": ticket_id,
                "filename": filename,
                "file_content": file_content,
                "mime_type": mime_type,
            }
        )
        return self.upload_result


def test_handle_vault_attachments_returns_empty_for_empty_vault_ids():
    client = FakeClient()
    helper = ServiceNowActionHelper(FakeSoar({}), client)

    details, errors = helper.handle_vault_attachments("incident", "ticket-id", " , ")

    assert details == []
    assert errors == {}
    assert client.upload_calls == []


def test_handle_vault_attachments_records_missing_vault_file():
    client = FakeClient()
    helper = ServiceNowActionHelper(FakeSoar({"vault-id": []}), client)

    details, errors = helper.handle_vault_attachments(
        "incident", "ticket-id", "vault-id"
    )

    assert details == []
    assert errors == {"vault-id": "Vault file not found for vault_id: vault-id"}
    assert client.upload_calls == []


def test_handle_vault_attachments_uploads_first_vault_file():
    client = FakeClient()
    helper = ServiceNowActionHelper(FakeSoar({"vault-id": [FakeVaultFile()]}), client)

    details, errors = helper.handle_vault_attachments(
        "incident", "ticket-id", "vault-id"
    )

    assert details == [{"sys_id": "attachment-id"}]
    assert errors == {}
    assert client.upload_calls == [
        {
            "table": "incident",
            "ticket_id": "ticket-id",
            "filename": "evidence.txt",
            "file_content": b"evidence",
            "mime_type": "text/plain",
        }
    ]


def test_handle_vault_attachments_captures_vault_exceptions():
    client = FakeClient()
    helper = ServiceNowActionHelper(
        FakeSoar({"vault-id": RuntimeError("vault unavailable")}), client
    )

    details, errors = helper.handle_vault_attachments(
        "incident", "ticket-id", "vault-id"
    )

    assert details == []
    assert errors == {"vault-id": "vault unavailable"}
    assert client.upload_calls == []
