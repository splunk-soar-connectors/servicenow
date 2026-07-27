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

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions import on_poll as on_poll_module


def _make_asset(**overrides):
    values = {
        "url": "https://example.service-now.com",
        "username": "user",
        "password": "pass",
        "client_id": None,
        "client_secret": None,
        "auth_state": SimpleNamespace(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _make_poll_asset(**overrides):
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


@pytest.fixture
def asset_factory():
    return _make_asset


@pytest.fixture
def poll_asset_factory():
    return _make_poll_asset


@pytest.fixture
def fake_soar():
    soar = SimpleNamespace(summary=None, message=None)
    soar.set_summary = lambda summary: setattr(soar, "summary", summary)
    soar.set_message = lambda message: setattr(soar, "message", message)
    return soar


@pytest.fixture
def collect_on_poll_outputs(monkeypatch):
    def _collect_on_poll_outputs(issues, asset):
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

    return _collect_on_poll_outputs
