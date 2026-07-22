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
from zoneinfo import ZoneInfo

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import helpers as helpers_module
from src.helpers import ServiceNowClient
from src.actions import add_comment as add_comment_module
from src.actions import add_work_note as add_work_note_module
from src.actions import on_poll as on_poll_module
from src.actions import run_query as run_query_module
from src.actions import update_ticket as update_ticket_module
from src.actions.add_comment import AddCommentParams, add_comment
from src.actions.add_work_note import AddWorkNoteParams, add_work_note
from src.actions.run_query import RunQueryParams, run_query
from src.actions.update_ticket import UpdateTicketParams, update_ticket
from src.consts import SERVICENOW_SENSITIVE_PROPS, TicketNotFoundException
from soar_sdk.exceptions import ActionFailure

run_add_comment = add_comment.__wrapped__
run_add_work_note = add_work_note.__wrapped__
run_run_query = run_query.__wrapped__
run_update_ticket = update_ticket.__wrapped__


def make_asset():
    return SimpleNamespace(
        url="https://example.service-now.com",
        username="user",
        password="pass",
        client_id=None,
        client_secret=None,
        auth_state=SimpleNamespace(),
    )


def make_poll_asset(**overrides):
    values = {
        "url": "https://example.service-now.com",
        "username": "user",
        "password": "pass",
        "client_id": None,
        "client_secret": None,
        "auth_state": SimpleNamespace(),
        "ingest_state": {"last_time": "2026-01-02 03:04:05", "first_run": False},
        "on_poll_filter": "",
        "on_poll_table": "",
        "max_container": 50,
        "first_run_container": 10,
        "severity": "",
        "extract_ips": False,
        "extract_hashes": False,
        "extract_urls": False,
        "timezone": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def collect_on_poll_outputs(monkeypatch, issues, asset):
    class FakeServiceNowClient:
        calls: ClassVar[list[dict]] = []

        def __init__(self, asset):
            self.asset = asset

        def paginator(self, endpoint, *, payload, limit):
            self.calls.append(
                {"endpoint": endpoint, "payload": payload, "limit": limit}
            )
            return issues

    class FakeSoar:
        def get(self, endpoint):
            return SimpleNamespace(
                json=lambda: {
                    "severity": [
                        {"name": "medium", "is_default": True},
                    ]
                }
            )

    params = SimpleNamespace(is_manual_poll=lambda: False)
    monkeypatch.setattr(on_poll_module, "ServiceNowClient", FakeServiceNowClient)

    return (
        list(on_poll_module.on_poll.__wrapped__(params, FakeSoar(), asset)),
        FakeServiceNowClient.calls,
    )


def test_ticket_number_resolution_requires_exact_returned_number(monkeypatch):
    client = ServiceNowClient(make_asset())

    def fake_make_rest_call(endpoint, params):
        assert endpoint == "/table/incident"
        assert params == {"sysparm_query": "number=INC0000001"}
        return {
            "result": [
                {"number": "INC0000002", "sys_id": "0123456789abcdef0123456789abcdef"}
            ]
        }

    monkeypatch.setattr(client, "make_rest_call", fake_make_rest_call)

    with pytest.raises(
        TicketNotFoundException,
        match="ServiceNow returned a different ticket than the requested ticket number",
    ):
        client.get_sys_id_from_ticket_number("incident", "INC0000001")


def test_ticket_number_resolution_returns_sys_id_for_exact_match(monkeypatch):
    client = ServiceNowClient(make_asset())

    monkeypatch.setattr(
        client,
        "make_rest_call",
        lambda endpoint, params: {
            "result": [
                {"number": "INC0000001", "sys_id": "0123456789abcdef0123456789abcdef"}
            ]
        },
    )

    assert (
        client.get_sys_id_from_ticket_number("incident", "INC0000001")
        == "0123456789abcdef0123456789abcdef"
    )


def test_run_query_strips_sensitive_properties(monkeypatch):
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
                    "admin_password": "admin-secret",
                    "database_password": "db-secret",
                    "password": "generic-secret",
                    "user_password": "user-secret",
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
        make_asset(),
    )

    dumped = output[0].model_dump()
    assert SERVICENOW_SENSITIVE_PROPS == [
        "admin_password",
        "database_password",
        "user_password",
    ]
    for sensitive_prop in SERVICENOW_SENSITIVE_PROPS:
        assert sensitive_prop not in dumped

    assert dumped["password"] == "generic-secret"
    assert dumped["number"] == "INC0000001"
    assert dumped["short_description"] == "safe"


def test_paginator_stops_when_total_count_reached(monkeypatch):
    client = ServiceNowClient(make_asset())
    calls = []

    def fake_make_rest_call(endpoint, params):
        calls.append(params.copy())
        client._response_headers = {"X-Total-Count": "1"}
        return {"result": [{"number": "INC0000001"}]}

    monkeypatch.setattr(client, "make_rest_call", fake_make_rest_call)

    assert client.paginator("/table/incident", limit=100) == [{"number": "INC0000001"}]
    assert calls == [{"sysparm_offset": 0, "sysparm_limit": 100}]


def test_paginator_bounds_pages_when_total_count_is_missing(monkeypatch):
    client = ServiceNowClient(make_asset())
    calls = []

    def fake_make_rest_call(endpoint, params):
        calls.append(params.copy())
        client._response_headers = {}
        return {"result": [{"number": f"INC{len(calls):07d}"}]}

    monkeypatch.setattr(helpers_module, "MAX_PAGES", 2)
    monkeypatch.setattr(client, "make_rest_call", fake_make_rest_call)

    assert client.paginator("/table/incident") == [
        {"number": "INC0000001"},
        {"number": "INC0000002"},
    ]
    assert len(calls) == 2


def test_paginator_ignores_invalid_total_count_header(monkeypatch):
    client = ServiceNowClient(make_asset())
    calls = []
    responses = [
        {"result": [{"number": "INC0000001"}]},
        {"result": []},
    ]

    def fake_make_rest_call(endpoint, params):
        calls.append(params.copy())
        client._response_headers = {"X-Total-Count": "not-an-int"}
        return responses.pop(0)

    monkeypatch.setattr(client, "make_rest_call", fake_make_rest_call)

    assert client.paginator("/table/incident", limit=100) == [{"number": "INC0000001"}]
    assert len(calls) == 2


def test_make_rest_call_records_response_headers(monkeypatch):
    class FakeHTTPClient:
        def __init__(self, auth, timeout):
            self.auth = auth
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, **kwargs):
            return httpx.Response(
                200,
                json={"result": []},
                headers={"X-Total-Count": "42"},
            )

    client = ServiceNowClient(make_asset())
    monkeypatch.setattr(helpers_module.httpx, "Client", FakeHTTPClient)
    monkeypatch.setattr(client, "get_auth", lambda: "auth")

    assert client.make_rest_call("/table/incident") == {"result": []}
    assert client._response_headers["x-total-count"] == "42"


def test_on_poll_strips_format_controls_from_ingested_ticket_data(monkeypatch):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case\u202e title",
        "description": "Description\u200d text",
        "sys_updated_on": "2026-01-02 03:04:05",
    }

    outputs, _calls = collect_on_poll_outputs(
        monkeypatch,
        [issue],
        make_poll_asset(),
    )

    container = outputs[0]
    primary_artifact = outputs[1]
    assert container.name == "Case title"
    assert container.data["description"] == "Description text"
    assert primary_artifact.cef["short_description"] == "Case title"


def test_on_poll_extracts_internationalized_urls(monkeypatch):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": "Review http://例え.テスト/パス",
        "sys_updated_on": "2026-01-02 03:04:05",
    }

    outputs, _calls = collect_on_poll_outputs(
        monkeypatch,
        [issue],
        make_poll_asset(extract_urls=True),
    )

    urls = [
        item.cef["URL"] for item in outputs if getattr(item, "label", None) == "URL"
    ]
    assert urls == ["http://例え.テスト/パス"]


def test_on_poll_validates_ips_and_scans_text_values_only(monkeypatch):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": (
            "valid 192.0.2.10 invalid 999.999.999.999 ipv6 2001:db8::1%eth0"
        ),
        "198.51.100.77": True,
        "sys_updated_on": "2026-01-02 03:04:05",
    }

    outputs, _calls = collect_on_poll_outputs(
        monkeypatch,
        [issue],
        make_poll_asset(extract_ips=True),
    )

    ipv4s = [
        item.cef["ip_address"]
        for item in outputs
        if getattr(item, "label", None) == "IP Address"
    ]
    ipv6s = [
        item.cef["ipv6_address"]
        for item in outputs
        if getattr(item, "label", None) == "IPV6 Address"
    ]
    assert ipv4s == ["192.0.2.10"]
    assert ipv6s == ["2001:db8::1"]


def test_on_poll_preserves_configured_timezone_for_checkpoint(monkeypatch):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": "Description",
        "sys_updated_on": "2026-01-02 03:04:05",
    }
    asset = make_poll_asset(timezone=ZoneInfo("Asia/Kolkata"))

    _outputs, calls = collect_on_poll_outputs(monkeypatch, [issue], asset)

    assert calls[0]["payload"]["sysparm_query"] == (
        "ORDERBYsys_updated_on"
        "^sys_updated_on>=javascript:gs.dateGenerate('2026-01-02','03:04:05')"
    )
    assert asset.ingest_state["last_time"] == "2026-01-02 08:34:05"


def test_on_poll_uses_raw_utc_checkpoint_without_configured_timezone(monkeypatch):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": "Description",
        "sys_updated_on": "2026-01-02 03:04:05",
    }
    asset = make_poll_asset(timezone=None)

    _outputs, calls = collect_on_poll_outputs(monkeypatch, [issue], asset)

    assert calls[0]["payload"]["sysparm_query"] == (
        "ORDERBYsys_updated_on^sys_updated_on>=2026-01-02 03:04:05"
    )
    assert asset.ingest_state["last_time"] == "2026-01-02 03:04:05"


def test_on_poll_defers_first_run_state_until_generator_is_exhausted(monkeypatch):
    issue = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Case title",
        "description": "Description",
        "sys_updated_on": "2026-01-02 03:04:05",
    }
    asset = make_poll_asset(
        ingest_state={"last_time": "2026-01-01 00:00:00", "first_run": True}
    )

    class FakeServiceNowClient:
        def __init__(self, asset):
            self.asset = asset

        def paginator(self, endpoint, *, payload, limit):
            return [issue]

    class FakeSoar:
        def get(self, endpoint):
            return SimpleNamespace(
                json=lambda: {
                    "severity": [
                        {"name": "medium", "is_default": True},
                    ]
                }
            )

    params = SimpleNamespace(is_manual_poll=lambda: False)
    monkeypatch.setattr(on_poll_module, "ServiceNowClient", FakeServiceNowClient)

    generator = on_poll_module.on_poll.__wrapped__(params, FakeSoar(), asset)
    next(generator)
    assert asset.ingest_state["first_run"] is True

    list(generator)
    assert asset.ingest_state["first_run"] is False


def test_custom_view_context_menu_values_are_escaped():
    template_dir = Path(__file__).resolve().parents[1] / "templates"
    unescaped_lines = []

    for template_path in template_dir.glob("servicenow_*.html"):
        for line_number, line in enumerate(template_path.read_text().splitlines(), 1):
            if "context_menu(" not in line:
                continue
            if (
                "|escapejs" in line
                or "'value':'{{" in line
                or (
                    "'value':{{" in line
                    and '|default("")|tojson|forceescape' not in line
                )
            ):
                unescaped_lines.append(f"{template_path.name}:{line_number}")

    assert unescaped_lines == []


def test_add_comment_fails_on_empty_write_result(monkeypatch):
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
            make_asset(),
        )


def test_add_work_note_fails_on_empty_write_result(monkeypatch):
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
            make_asset(),
        )


def test_update_ticket_fails_on_empty_write_result(monkeypatch):
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
            make_asset(),
        )
