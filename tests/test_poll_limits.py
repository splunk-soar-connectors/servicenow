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

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions.on_poll import _get_scheduled_poll_limits


@pytest.mark.parametrize("invalid_limit", [0, -1])
def test_scheduled_poll_limits_reject_non_positive_values(invalid_limit):
    asset = SimpleNamespace(
        first_run_container=invalid_limit,
        max_container=1,
    )

    with pytest.raises(ActionFailure, match="first_run_container"):
        _get_scheduled_poll_limits(asset)

    asset.first_run_container = 1
    asset.max_container = invalid_limit

    with pytest.raises(ActionFailure, match="max_container"):
        _get_scheduled_poll_limits(asset)


def test_scheduled_poll_limits_return_configured_positive_values():
    asset = SimpleNamespace(first_run_container=10, max_container=5)

    assert _get_scheduled_poll_limits(asset) == (10, 5)
