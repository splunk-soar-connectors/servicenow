# Copyright (c) 2016-2026 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Migration and checkpoint-safety tests for the ServiceNow on_poll action."""

import importlib
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from soar_sdk.params import OnPollParams

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ScheduledPollParams(OnPollParams):
    def is_manual_poll(self) -> bool:
        return False


class BackendState:
    def __init__(self, state=None):
        self.state = state

    def load_state(self):
        return self.state


class IngestState(dict):
    """Small AssetState-compatible mapping for migration tests."""

    def __init__(self, initial=None, legacy_state=None):
        super().__init__(initial or {})
        self.backend = BackendState(legacy_state)


def _asset(state, timezone_name=None, max_container=10):
    return SimpleNamespace(
        timezone=timezone_name,
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


def _source_ids(items):
    return [
        item.source_data_identifier
        for item in items
        if getattr(item, "source_data_identifier", None)
    ]


def _run_with_response(monkeypatch, asset, response, captured=None):
    module = importlib.import_module("src.actions.on_poll")
    captured = {} if captured is None else captured

    class FakeServiceNowClient:
        def __init__(self, _asset):
            pass

        def paginator(self, _endpoint, payload, limit):
            captured["payload"] = payload
            captured["limit"] = limit
            return response

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda _soar, _asset: "medium")
    emitted = list(
        module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset)
    )
    return module, emitted, captured


def test_migrate_legacy_state_copies_checkpoint_and_first_run():
    module = importlib.import_module("src.actions.on_poll")
    state = IngestState(
        {"unrelated": "preserve"},
        {"last_time": "2025-09-03 02:00:00", "first_run": False},
    )
    asset = _asset(state, "America/Los_Angeles")

    module.migrate_legacy_ingest_state(asset)

    assert state == {
        "unrelated": "preserve",
        "last_time": "2025-09-03 02:00:00",
        "first_run": False,
    }


def test_migrate_legacy_state_infers_not_first_run_from_checkpoint():
    module = importlib.import_module("src.actions.on_poll")
    state = IngestState({}, {"last_time": "2025-09-03 02:00:00"})

    module.migrate_legacy_ingest_state(_asset(state, "America/Los_Angeles"))

    assert state["last_time"] == "2025-09-03 02:00:00"
    assert state["first_run"] is False


def test_migrate_legacy_state_does_not_overwrite_existing_sdk_state():
    module = importlib.import_module("src.actions.on_poll")
    state = IngestState(
        {
            "last_time": "2025-09-03 09:00:00",
            "last_time_epoch_ms": 1756890000000,
            "first_run": False,
        },
        {"last_time": "2025-09-03 02:00:00", "first_run": True},
    )
    original = dict(state)

    module.migrate_legacy_ingest_state(_asset(state, "America/Los_Angeles"))

    assert state == original


def test_migrate_legacy_state_is_idempotent_and_handles_empty_backend():
    module = importlib.import_module("src.actions.on_poll")
    state = IngestState({"first_run": True, "custom": "value"}, None)
    asset = _asset(state)

    module.migrate_legacy_ingest_state(asset)
    first_result = dict(state)
    module.migrate_legacy_ingest_state(asset)

    assert state == first_result == {"first_run": True, "custom": "value"}


@pytest.mark.parametrize(
    ("timezone_name", "legacy_local", "updated_utc", "expected_legacy"),
    [
        (
            "UTC",
            "2025-01-15 09:00:00",
            "2025-01-15 09:00:00",
            "2025-01-15 09:00:00",
        ),
        (
            "Asia/Kolkata",
            "2025-01-15 14:30:00",
            "2025-01-15 09:00:00",
            "2025-01-15 14:30:00",
        ),
        (
            "America/Los_Angeles",
            "2025-07-01 02:00:00",
            "2025-07-01 09:00:00",
            "2025-07-01 02:00:00",
        ),
        (
            "America/Los_Angeles",
            "2025-11-02 01:30:00",
            "2025-11-02 09:30:00",
            "2025-11-02 01:30:00",
        ),
    ],
)
def test_legacy_checkpoint_migrates_to_same_utc_instant(
    monkeypatch, timezone_name, legacy_local, updated_utc, expected_legacy
):
    module = importlib.import_module("src.actions.on_poll")
    state = IngestState(
        {"first_run": False},
        {"last_time": legacy_local, "first_run": False},
    )
    asset = _asset(state, timezone_name)

    _, emitted, captured = _run_with_response(
        monkeypatch, asset, [_issue("id-1", updated_utc)]
    )

    expected_epoch_ms = int(
        datetime.strptime(updated_utc, module.SERVICENOW_DATETIME_FORMAT)
        .replace(tzinfo=timezone.utc)
        .timestamp()
        * 1000
    )
    assert _source_ids(emitted) == ["id-1", "id-1"]
    assert captured["payload"]["sysparm_query"] == (
        "ORDERBYsys_updated_on^sys_updated_on>="
        f"javascript:gs.dateGenerate('{legacy_local[:10]}','{legacy_local[11:]}')"
    )
    assert state["last_time_epoch_ms"] == expected_epoch_ms
    assert state["last_time"] == expected_legacy


def test_utc_checkpoint_query_is_independent_of_asset_timezone(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    checkpoint_ms = 1756890000000
    queries = []

    class FakeServiceNowClient:
        def __init__(self, _asset):
            pass

        def paginator(self, _endpoint, payload, limit):
            queries.append(payload["sysparm_query"])
            return [_issue("id-1", "2025-09-03 10:00:00")]

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda _soar, _asset: "medium")

    for timezone_name in ("UTC", "America/Los_Angeles", "Asia/Kolkata"):
        state = IngestState(
            {
                "first_run": False,
                "last_time": "2025-09-03 02:00:00",
                "last_time_epoch_ms": checkpoint_ms,
            }
        )
        list(
            module.on_poll.__wrapped__(
                ScheduledPollParams(),
                SimpleNamespace(),
                _asset(state, timezone_name),
            )
        )

    assert queries == ["ORDERBYsys_updated_on^sys_updated_on>=2025-09-03 09:00:00"] * 3


def test_invalid_utc_checkpoint_falls_back_to_legacy_checkpoint(monkeypatch):
    state = IngestState(
        {
            "first_run": False,
            "last_time": "2025-09-03 02:00:00",
            "last_time_epoch_ms": "not-an-epoch",
        }
    )

    _, _, captured = _run_with_response(
        monkeypatch, _asset(state, "America/Los_Angeles"), []
    )

    assert captured["payload"]["sysparm_query"] == (
        "ORDERBYsys_updated_on^sys_updated_on>="
        "javascript:gs.dateGenerate('2025-09-03','02:00:00')"
    )


@pytest.mark.parametrize("checkpoint", [None, True, 0, -1, "invalid"])
def test_invalid_utc_checkpoint_values_are_rejected(checkpoint):
    module = importlib.import_module("src.actions.on_poll")

    assert module._format_epoch_checkpoint(checkpoint) is None


def test_migrated_checkpoint_is_used_after_restart(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    responses = [
        [_issue("id-1", "2025-09-03 09:00:00")],
        [_issue("id-2", "2025-09-03 09:01:00")],
    ]
    queries = []

    class FakeServiceNowClient:
        def __init__(self, _asset):
            pass

        def paginator(self, _endpoint, payload, limit):
            queries.append(payload["sysparm_query"])
            return responses.pop(0)

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda _soar, _asset: "medium")

    state = IngestState(
        {"first_run": False},
        {"last_time": "2025-09-03 02:00:00", "first_run": False},
    )
    asset = _asset(state, "America/Los_Angeles")
    first = list(
        module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset)
    )

    restarted_state = IngestState(dict(state))
    restarted_asset = _asset(restarted_state, "UTC")
    second = list(
        module.on_poll.__wrapped__(
            ScheduledPollParams(), SimpleNamespace(), restarted_asset
        )
    )

    assert _source_ids(first) == ["id-1", "id-1"]
    assert _source_ids(second) == ["id-2", "id-2"]
    assert queries == [
        "ORDERBYsys_updated_on^sys_updated_on>=javascript:gs.dateGenerate('2025-09-03','02:00:00')",
        "ORDERBYsys_updated_on^sys_updated_on>=2025-09-03 09:00:00",
    ]


def test_legacy_checkpoint_is_not_advanced_when_request_fails(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    state = IngestState(
        {"first_run": False},
        {"last_time": "2025-09-03 02:00:00", "first_run": False},
    )

    class FailingServiceNowClient:
        def __init__(self, _asset):
            pass

        def paginator(self, _endpoint, _payload, limit):
            raise RuntimeError("ServiceNow unavailable")

    monkeypatch.setattr(module, "ServiceNowClient", FailingServiceNowClient)

    with pytest.raises(Exception, match="Failed to fetch issues from ServiceNow"):
        list(
            module.on_poll.__wrapped__(
                ScheduledPollParams(),
                SimpleNamespace(),
                _asset(state, "America/Los_Angeles"),
            )
        )

    assert "last_time_epoch_ms" not in state
    assert state["last_time"] == "2025-09-03 02:00:00"
    assert state["first_run"] is False


def test_partial_generator_consumption_does_not_advance_checkpoint(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    state = IngestState(
        {
            "first_run": False,
            "last_time_epoch_ms": 1756890000000,
            "last_time": "2025-09-03 09:00:00",
        }
    )

    class FakeServiceNowClient:
        def __init__(self, _asset):
            pass

        def paginator(self, _endpoint, payload, limit):
            return [_issue("id-1", "2025-09-03 09:01:00")]

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda _soar, _asset: "medium")

    generator = module.on_poll.__wrapped__(
        ScheduledPollParams(), SimpleNamespace(), _asset(state)
    )
    next(generator)

    assert state["last_time_epoch_ms"] == 1756890000000
    assert state["last_time"] == "2025-09-03 09:00:00"


class FilteringPaginator:
    """Apply the subset of ServiceNow ordering/filtering relevant to on_poll."""

    def __init__(self, records):
        self.records = records
        self.queries = []

    def __call__(self, _endpoint, payload, limit):
        query = payload["sysparm_query"]
        self.queries.append(query)
        match = re.search(
            r"sys_updated_on>=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", query
        )
        checkpoint = match.group(1) if match else "0000-00-00 00:00:00"
        matching = [
            record for record in self.records if record["sys_updated_on"] >= checkpoint
        ]
        matching.sort(key=lambda record: record["sys_updated_on"])
        return matching[:limit]


def test_migrated_checkpoint_includes_boundary_and_newer_records_only(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    records = [
        _issue("before", "2025-09-03 08:59:59"),
        _issue("boundary", "2025-09-03 09:00:00"),
        _issue("after", "2025-09-03 09:00:01"),
    ]
    paginator = FilteringPaginator(records)

    class FakeServiceNowClient:
        def __init__(self, _asset):
            pass

        def paginator(self, endpoint, payload, limit):
            return paginator(endpoint, payload, limit)

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda _soar, _asset: "medium")

    state = IngestState(
        {
            "first_run": False,
            "last_time": "2025-09-03 09:00:00",
            "last_time_epoch_ms": 1756890000000,
        }
    )

    emitted = list(
        module.on_poll.__wrapped__(
            ScheduledPollParams(), SimpleNamespace(), _asset(state)
        )
    )

    assert _source_ids(emitted) == [
        "boundary",
        "boundary",
        "after",
        "after",
    ]
    assert state["last_time_epoch_ms"] == 1756890001000


def test_missing_final_updated_time_does_not_advance_checkpoint(monkeypatch):
    state = IngestState(
        {
            "first_run": False,
            "last_time": "2025-09-03 09:00:00",
            "last_time_epoch_ms": 1756890000000,
        }
    )
    response = [_issue("id-1", "2025-09-03 09:01:00")]
    response[0].pop("sys_updated_on")

    with pytest.raises(Exception, match="No updated time in last ingested incident"):
        _run_with_response(monkeypatch, _asset(state), response)

    assert state["last_time_epoch_ms"] == 1756890000000
    assert state["last_time"] == "2025-09-03 09:00:00"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Timestamp-only cursor cannot progress through more than one page of "
        "records sharing the same sys_updated_on value"
    ),
)
def test_all_same_timestamp_records_are_eventually_ingested(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    records = [
        _issue("id-a", "2025-09-03 09:00:00"),
        _issue("id-b", "2025-09-03 09:00:00"),
        _issue("id-c", "2025-09-03 09:00:00"),
        _issue("id-d", "2025-09-03 09:00:00"),
    ]
    paginator = FilteringPaginator(records)

    class FakeServiceNowClient:
        def __init__(self, _asset):
            pass

        def paginator(self, endpoint, payload, limit):
            return paginator(endpoint, payload, limit)

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda _soar, _asset: "medium")

    state = IngestState(
        {
            "first_run": False,
            "last_time": "2025-09-03 08:59:59",
        }
    )
    asset = _asset(state, max_container=2)
    observed = set()

    for _ in range(3):
        emitted = list(
            module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset)
        )
        observed.update(_source_ids(emitted))

    assert observed == {"id-a", "id-b", "id-c", "id-d"}


def test_record_visible_after_empty_poll_is_not_skipped(monkeypatch):
    module = importlib.import_module("src.actions.on_poll")
    records = [_issue("late", "2025-09-03 09:59:59")]
    paginator = FilteringPaginator(records)
    calls = 0

    class FakeServiceNowClient:
        def __init__(self, _asset):
            pass

        def paginator(self, endpoint, payload, limit):
            nonlocal calls
            calls += 1
            if calls == 1:
                return []
            return paginator(endpoint, payload, limit)

    monkeypatch.setattr(module, "ServiceNowClient", FakeServiceNowClient)
    monkeypatch.setattr(module, "_get_severity", lambda _soar, _asset: "medium")

    state = IngestState({"first_run": True, "last_time": ""})
    asset = _asset(state, max_container=10)

    first_poll = list(
        module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset)
    )
    second_poll = list(
        module.on_poll.__wrapped__(ScheduledPollParams(), SimpleNamespace(), asset)
    )

    assert first_poll == []
    assert _source_ids(second_poll) == ["late", "late"]
