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

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.consts import BASIC_AUTH_TYPE
import src.helpers as helpers
from src.helpers import ServiceNowAPIError, ServiceNowClient


class BasicAuthAsset:
    url = "https://example.service-now.com"
    username = "user"
    password = "pass"
    client_id = ""
    client_secret = ""
    oauth_grant_type = BASIC_AUTH_TYPE


def test_non_success_response_preserves_service_now_status_code(monkeypatch):
    class MockClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def request(self, **_kwargs):
            return httpx.Response(403, json={"error": {"message": "Forbidden"}})

    monkeypatch.setattr(helpers.httpx, "Client", MockClient)

    with pytest.raises(ServiceNowAPIError) as exc_info:
        ServiceNowClient(BasicAuthAsset()).make_rest_call("/table/incident")

    assert exc_info.value.status_code == 403
    assert "Forbidden" in str(exc_info.value)
