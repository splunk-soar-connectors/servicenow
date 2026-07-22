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
from typing import Any, ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions import on_poll


class FakeBackend:
    def __init__(self, state: dict[str, Any] | None):
        self.state = state
        self.load_calls = 0

    def load_state(self) -> dict[str, Any] | None:
        self.load_calls += 1
        return self.state


class FakeIngestState(dict[str, Any]):
    def __init__(
        self,
        initial_state: dict[str, Any] | None = None,
        legacy_state: dict[str, Any] | None = None,
    ):
        super().__init__(initial_state or {})
        self.backend = FakeBackend(legacy_state)


def test_migrate_legacy_ingest_state_copies_on_poll_checkpoint_fields():
    state = FakeIngestState(
        legacy_state={"last_time": "2026-01-02 03:04:05", "first_run": False}
    )
    asset = SimpleNamespace(ingest_state=state)

    on_poll.migrate_legacy_ingest_state(asset)

    assert state["last_time"] == "2026-01-02 03:04:05"
    assert state["first_run"] is False
    assert state.backend.load_calls == 1


def test_migrate_legacy_ingest_state_copies_first_run_without_last_time():
    state = FakeIngestState(legacy_state={"first_run": False})
    asset = SimpleNamespace(ingest_state=state)

    on_poll.migrate_legacy_ingest_state(asset)

    assert "last_time" not in state
    assert state["first_run"] is False


def test_migrate_legacy_ingest_state_marks_first_run_false_when_checkpoint_exists():
    state = FakeIngestState(legacy_state={"last_time": "2026-01-02 03:04:05"})
    asset = SimpleNamespace(ingest_state=state)

    on_poll.migrate_legacy_ingest_state(asset)

    assert state["last_time"] == "2026-01-02 03:04:05"
    assert state["first_run"] is False


def test_migrate_legacy_ingest_state_does_not_overwrite_sdk_ingest_state():
    state = FakeIngestState(
        initial_state={"last_time": "2026-02-03 04:05:06", "first_run": False},
        legacy_state={"last_time": "2026-01-02 03:04:05", "first_run": True},
    )
    asset = SimpleNamespace(ingest_state=state)

    on_poll.migrate_legacy_ingest_state(asset)

    assert state["last_time"] == "2026-02-03 04:05:06"
    assert state["first_run"] is False
    assert state.backend.load_calls == 0


def test_on_poll_uses_migrated_last_time_for_scheduled_query(monkeypatch):
    state = FakeIngestState(
        legacy_state={"last_time": "2026-01-02 03:04:05", "first_run": False}
    )
    asset = SimpleNamespace(
        ingest_state=state,
        on_poll_filter="",
        on_poll_table="",
        max_container=50,
        first_run_container=10,
    )
    params = SimpleNamespace(is_manual_poll=lambda: False)

    class FakeServiceNowClient:
        calls: ClassVar[list[dict[str, Any]]] = []

        def __init__(self, asset):
            self.asset = asset

        def paginator(self, endpoint, *, payload, limit):
            self.calls.append(
                {"endpoint": endpoint, "payload": payload, "limit": limit}
            )
            return []

    monkeypatch.setattr(on_poll, "ServiceNowClient", FakeServiceNowClient)

    list(on_poll.on_poll.__wrapped__(params, SimpleNamespace(), asset))

    assert FakeServiceNowClient.calls == [
        {
            "endpoint": "/table/incident",
            "payload": {
                "sysparm_query": (
                    "ORDERBYsys_updated_on"
                    "^sys_updated_on>=2026-01-02 03:04:05"
                ),
                "sysparm_exclude_reference_link": "true",
            },
            "limit": 50,
        }
    ]


def test_on_poll_does_not_migrate_legacy_state_for_poll_now(monkeypatch):
    state = FakeIngestState(
        legacy_state={"last_time": "2026-01-02 03:04:05", "first_run": False}
    )
    asset = SimpleNamespace(
        ingest_state=state,
        on_poll_filter="",
        on_poll_table="",
        max_container=50,
        first_run_container=10,
    )
    params = SimpleNamespace(
        is_manual_poll=lambda: True,
        container_count=7,
        start_time=None,
        end_time=None,
    )

    class FakeServiceNowClient:
        calls: ClassVar[list[dict[str, Any]]] = []

        def __init__(self, asset):
            self.asset = asset

        def paginator(self, endpoint, *, payload, limit):
            self.calls.append(
                {"endpoint": endpoint, "payload": payload, "limit": limit}
            )
            return []

    monkeypatch.setattr(on_poll, "ServiceNowClient", FakeServiceNowClient)

    list(on_poll.on_poll.__wrapped__(params, SimpleNamespace(), asset))

    assert dict(state) == {}
    assert state.backend.load_calls == 0
    assert FakeServiceNowClient.calls[0]["payload"]["sysparm_query"] == (
        "ORDERBYsys_updated_on"
    )
    assert FakeServiceNowClient.calls[0]["limit"] == 7
