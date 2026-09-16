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
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.consts import BASIC_AUTH_TYPE, PASSWORD_GRANT_AUTH_TYPE
from src.servicenow_client import ServiceNowClient


class FakeAsset:
    url = "https://example.service-now.com"
    username = "user"
    password = "pass"
    client_id = ""
    client_secret = "leftover-secret"
    oauth_grant_type = PASSWORD_GRANT_AUTH_TYPE


class BasicAuthAsset(FakeAsset):
    oauth_grant_type = BASIC_AUTH_TYPE


def test_partial_oauth_config_is_not_reported_as_connection_error():
    client = ServiceNowClient(FakeAsset())

    with pytest.raises(ActionFailure) as exc_info:
        client.make_rest_call("/table/incident")

    message = str(exc_info.value)
    assert "OAuth configuration is incomplete" in message
    assert "select basic_auth as the authentication type" in message
    assert "Error connecting to server" not in message


def test_basic_auth_selection_ignores_retained_oauth_secret():
    client = ServiceNowClient(BasicAuthAsset())

    auth = client.get_auth()

    assert auth.__class__.__name__ == "BasicAuth"
