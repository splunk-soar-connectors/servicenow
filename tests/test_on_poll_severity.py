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

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions import on_poll


class FakeSoar:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, endpoint):
        self.calls.append(endpoint)
        return SimpleNamespace(json=lambda: self.response)


SEVERITIES = [
    {"name": "low", "is_default": False},
    {"name": "medium", "is_default": True},
    {"name": "high", "is_default": False},
]


def test_get_severity_uses_default_from_container_options():
    soar = FakeSoar({"severity": SEVERITIES})
    asset = SimpleNamespace(severity="")

    assert on_poll._get_severity(soar, asset) == "medium"
    assert soar.calls == ["/rest/container_options"]


def test_get_severity_validates_custom_severity_from_container_options():
    soar = FakeSoar({"severity": SEVERITIES})
    asset = SimpleNamespace(severity="High")

    assert on_poll._get_severity(soar, asset) == "high"
    assert soar.calls == ["/rest/container_options"]


def test_get_severity_rejects_unknown_custom_severity():
    soar = FakeSoar({"severity": SEVERITIES})
    asset = SimpleNamespace(severity="critical")

    with pytest.raises(Exception, match="Severity 'critical' does not exist"):
        on_poll._get_severity(soar, asset)


def test_get_severity_falls_back_to_medium_when_no_default_exists():
    soar = FakeSoar({"severity": [{"name": "low", "is_default": False}]})
    asset = SimpleNamespace(severity="")

    assert on_poll._get_severity(soar, asset) == "medium"


def test_get_severity_rejects_missing_container_options_severity():
    soar = FakeSoar({"status": []})
    asset = SimpleNamespace(severity="")

    with pytest.raises(Exception, match="severity options missing"):
        on_poll._get_severity(soar, asset)
