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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import OnPollParams

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ManualPollWithoutCountParams(OnPollParams):
    def is_manual_poll(self) -> bool:
        return True


class ScheduledPollParams(OnPollParams):
    def is_manual_poll(self) -> bool:
        return False


def _scheduled_asset(state, max_container=10):
    return SimpleNamespace(
        timezone=None,
        ingest_state=state,
        on_poll_filter=None,
        on_poll_table=None,
        first_run_container=max_container,
        max_container=max_container,
        extract_ips=False,
        extract_hashes=False,
        extract_urls=False,
        severity=None,
    )


def _issue(sys_id, updated_on):
    return {
        "sys_id": sys_id,
        "number": f"INC-{sys_id}",
        "short_description": f"Incident {sys_id}",
        "description": "Test incident",
        "sys_updated_on": updated_on,
    }


def _emitted_source_ids(emitted):
    return [
        item.source_data_identifier
        for item in emitted
        if getattr(item, "source_data_identifier", None)
    ]


def test_on_poll_missing_manual_container_count_raises_action_failure():
    module = importlib.import_module("src.actions.on_poll")
    params = ManualPollWithoutCountParams(container_count=None)
    asset = SimpleNamespace(
        url="https://example.service-now.com",
        timezone=None,
        ingest_state={},
        on_poll_filter=None,
    )

    with pytest.raises(ActionFailure, match="container_count is required for Poll Now"):
        list(module.on_poll.__wrapped__(params, SimpleNamespace(), asset))


def test_format_time_query_uses_timestamp_directly_without_timezone():
    module = importlib.import_module("src.actions.on_poll")

    assert module._format_time_query(">=", "2026-09-03 12:00:00") == (
        "^sys_updated_on>=2026-09-03 12:00:00"
    )


def test_strip_format_controls_recursively():
    module = importlib.import_module("src.actions.on_poll")

    value = {
        "description": "A\u200bB",
        "nested": ["C\u202eD"],
        "count": 1,
    }

    assert module._strip_format_controls(value) == {
        "description": "AB",
        "nested": ["CD"],
        "count": 1,
    }


def test_manual_poll_uses_sdk_epoch_timestamps_as_utc(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    captured = {}

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            captured.update(payload)
            return []

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)

    params = ManualPollWithoutCountParams(
        container_count=1,
        start_time=1756890000000,
        end_time=1756893600000,
    )
    asset = SimpleNamespace(
        timezone="America/Los_Angeles",
        ingest_state={},
        on_poll_filter=None,
        on_poll_table=None,
        first_run_container=10,
        max_container=10,
    )

    list(module.on_poll.__wrapped__(params, SimpleNamespace(), asset))

    assert captured["sysparm_query"] == (
        "ORDERBYsys_updated_on"
        "^sys_updated_on>=2025-09-03 09:00:00"
        "^sys_updated_on<=2025-09-03 10:00:00"
    )


def test_scheduled_poll_prefers_utc_checkpoint_over_legacy_timezone(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    captured = {}

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            captured.update(payload)
            return []

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)

    params = ScheduledPollParams()
    asset = SimpleNamespace(
        timezone="America/Los_Angeles",
        ingest_state={
            "first_run": False,
            "last_time": "2025-09-03 02:00:00",
            "last_time_epoch_ms": 1756890000000,
        },
        on_poll_filter=None,
        on_poll_table=None,
        first_run_container=10,
        max_container=10,
    )

    list(module.on_poll.__wrapped__(params, SimpleNamespace(), asset))

    assert captured["sysparm_query"] == (
        "ORDERBYsys_updated_on^sys_updated_on>=2025-09-03 09:00:00"
    )


def test_recent_utc_checkpoint_is_not_clamped_in_western_asset_timezone(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    captured = {}

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            captured.update(payload)
            return []

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)

    checkpoint = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(
        minutes=1
    )
    checkpoint_ms = int(checkpoint.timestamp() * 1000)
    state = {
        "first_run": False,
        "last_time": checkpoint.astimezone(
            module.ZoneInfo("America/Los_Angeles")
        ).strftime(module.SERVICENOW_DATETIME_FORMAT),
        "last_time_epoch_ms": checkpoint_ms,
    }
    asset = _scheduled_asset(state)
    asset.timezone = "America/Los_Angeles"

    list(module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset))

    expected_checkpoint = checkpoint.strftime(module.SERVICENOW_DATETIME_FORMAT)
    assert captured["sysparm_query"] == (
        f"ORDERBYsys_updated_on^sys_updated_on>={expected_checkpoint}"
    )


def test_legacy_checkpoint_still_uses_configured_timezone(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    captured = {}

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            captured.update(payload)
            return []

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)

    state = {"first_run": False, "last_time": "2025-09-03 02:00:00"}
    asset = _scheduled_asset(state)
    asset.timezone = "America/Los_Angeles"

    list(module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset))

    assert captured["sysparm_query"] == (
        "ORDERBYsys_updated_on"
        "^sys_updated_on>=javascript:gs.dateGenerate('2025-09-03','02:00:00')"
    )
    assert state == {
        "first_run": False,
        "last_time": "2025-09-03 02:00:00",
    }


def test_empty_first_scheduled_poll_does_not_create_checkpoint(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            return []

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)

    state = {"first_run": True, "last_time": ""}
    asset = _scheduled_asset(state)

    list(module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset))

    assert state["first_run"] is False
    assert state["last_time"] == ""
    assert "last_time_epoch_ms" not in state


def test_empty_scheduled_poll_preserves_existing_utc_checkpoint(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            return []

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)

    state = {
        "first_run": False,
        "last_time": "2025-09-03 02:00:00",
        "last_time_epoch_ms": 1756890000000,
    }
    original_state = state.copy()

    list(
        module.on_poll.__wrapped__(
            ScheduledPollParams(), SimpleNamespace(), _scheduled_asset(state)
        )
    )

    assert state == original_state


def test_failed_scheduled_poll_does_not_advance_utc_checkpoint(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            raise RuntimeError("ServiceNow unavailable")

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)

    state = {
        "first_run": False,
        "last_time": "2025-09-03 09:00:00",
        "last_time_epoch_ms": 1756890000000,
    }
    original_state = state.copy()

    with pytest.raises(ActionFailure, match="Failed to fetch issues from ServiceNow"):
        list(
            module.on_poll.__wrapped__(
                ScheduledPollParams(), SimpleNamespace(), _scheduled_asset(state)
            )
        )

    assert state == original_state


def test_scheduled_poll_writes_utc_checkpoint(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            return [
                {
                    "sys_id": "id-1",
                    "number": "INC001",
                    "short_description": "Test incident",
                    "description": "",
                    "sys_updated_on": "2025-09-03 09:00:00",
                }
            ]

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda soar, asset: "medium")

    state = {"first_run": False, "last_time": "2025-09-03 08:00:00"}
    asset = SimpleNamespace(
        timezone="America/Los_Angeles",
        ingest_state=state,
        on_poll_filter=None,
        on_poll_table=None,
        first_run_container=10,
        max_container=10,
        extract_ips=False,
        extract_hashes=False,
        extract_urls=False,
        severity=None,
    )

    list(module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset))

    assert state["last_time_epoch_ms"] == 1756890000000


def test_format_time_query_uses_date_generate_with_timezone():
    module = importlib.import_module("src.actions.on_poll")

    assert module._format_time_query(
        ">=", "2026-09-03 05:00:00", "America/Los_Angeles"
    ) == ("^sys_updated_on>=javascript:gs.dateGenerate('2026-09-03','05:00:00')")


def test_scheduled_poll_missing_sys_id_does_not_advance_checkpoint(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            return [
                {
                    "number": "INC001",
                    "short_description": "Test incident",
                    "description": "",
                    "sys_updated_on": "2025-09-03 09:00:00",
                }
            ]

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)

    state = {
        "first_run": False,
        "last_time": "2025-09-03 08:00:00",
        "last_time_epoch_ms": 1756886400000,
    }
    asset = SimpleNamespace(
        timezone=None,
        ingest_state=state,
        on_poll_filter=None,
        on_poll_table=None,
        first_run_container=10,
        max_container=10,
    )

    with pytest.raises(
        ActionFailure, match="record without sys_id; checkpoint was not advanced"
    ):
        list(
            module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset)
        )

    assert "last_sys_id" not in state
    assert state["last_time_epoch_ms"] == 1756886400000


def test_scheduled_poll_persists_state_across_normal_multiple_runs(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    captured_queries = []
    responses = [
        [
            _issue("id-1", "2025-09-03 09:00:00"),
            _issue("id-2", "2025-09-03 09:01:00"),
            _issue("id-3", "2025-09-03 09:02:00"),
        ],
        [
            _issue("id-4", "2025-09-03 09:03:00"),
            _issue("id-5", "2025-09-03 09:04:00"),
        ],
    ]

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            captured_queries.append(payload["sysparm_query"])
            return responses.pop(0)

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda soar, asset: "medium")

    state = {"first_run": True, "last_time": ""}
    asset = _scheduled_asset(state, max_container=10)
    params = ScheduledPollParams()

    first_run = list(module.on_poll.__wrapped__(params, SimpleNamespace(), asset))
    assert _emitted_source_ids(first_run) == [
        "id-1",
        "id-1",
        "id-2",
        "id-2",
        "id-3",
        "id-3",
    ]
    assert state["first_run"] is False
    assert state["last_time_epoch_ms"] == 1756890120000

    second_run = list(module.on_poll.__wrapped__(params, SimpleNamespace(), asset))
    assert _emitted_source_ids(second_run) == ["id-4", "id-4", "id-5", "id-5"]
    assert state["last_time_epoch_ms"] == 1756890240000
    assert captured_queries[0] == "ORDERBYsys_updated_on"
    assert captured_queries[1] == (
        "ORDERBYsys_updated_on^sys_updated_on>=2025-09-03 09:02:00"
    )


def test_scheduled_poll_processes_multiple_ids_at_one_timestamp(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    captured = {}

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            captured.update(payload)
            return [
                _issue("id-b", "2025-09-03 09:00:00"),
                _issue("id-c", "2025-09-03 09:00:00"),
                _issue("id-d", "2025-09-03 09:00:00"),
            ]

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda soar, asset: "medium")

    state = {
        "first_run": False,
        "last_time": "2025-09-03 08:59:59",
    }
    emitted = list(
        module.on_poll.__wrapped__(
            ScheduledPollParams(), SimpleNamespace(), _scheduled_asset(state)
        )
    )

    assert _emitted_source_ids(emitted) == [
        "id-b",
        "id-b",
        "id-c",
        "id-c",
        "id-d",
        "id-d",
    ]
    assert state["last_time_epoch_ms"] == 1756890000000
    assert "sys_updated_on>=2025-09-03 08:59:59" in captured["sysparm_query"]


def test_scheduled_poll_processes_same_timestamp_ids_across_multiple_polls(
    monkeypatch,
):
    module = importlib.import_module("src.actions.on_poll")
    captured_queries = []
    responses = [
        [
            _issue("id-b", "2025-09-03 09:00:00"),
            _issue("id-c", "2025-09-03 09:00:00"),
        ],
        [
            _issue("id-d", "2025-09-03 09:00:00"),
            _issue("id-e", "2025-09-03 09:00:00"),
        ],
    ]

    class FakeServiceNowClient:
        def __init__(self, asset):
            pass

        def paginator(self, endpoint, payload, limit):
            captured_queries.append(payload["sysparm_query"])
            return responses.pop(0)

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda soar, asset: "medium")

    state = {
        "first_run": False,
        "last_time": "2025-09-03 08:59:59",
    }
    asset = _scheduled_asset(state, max_container=2)
    params = ScheduledPollParams()

    first_run = list(module.on_poll.__wrapped__(params, SimpleNamespace(), asset))
    assert _emitted_source_ids(first_run) == ["id-b", "id-b", "id-c", "id-c"]
    assert state["last_time_epoch_ms"] == 1756890000000

    second_run = list(module.on_poll.__wrapped__(params, SimpleNamespace(), asset))
    assert _emitted_source_ids(second_run) == ["id-d", "id-d", "id-e", "id-e"]
    assert state["last_time_epoch_ms"] == 1756890000000
    assert "sys_updated_on>=2025-09-03 08:59:59" in captured_queries[0]
    assert "sys_updated_on>=2025-09-03 09:00:00" in captured_queries[1]
