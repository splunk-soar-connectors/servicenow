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
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.consts import BASIC_AUTH_TYPE
import src.servicenow_client as servicenow_client
from src.servicenow_client import ServiceNowAPIError, ServiceNowClient


class BasicAuthAsset:
    url = "https://example.service-now.com"
    username = "user"
    password = "pass"  # pragma: allowlist secret
    client_id = ""
    client_secret = ""
    oauth_grant_type = BASIC_AUTH_TYPE


@pytest.mark.parametrize(
    ("configured_url", "expected_url"),
    [
        ("https://example.service-now.com", "https://example.service-now.com/api"),
        ("https://example.service-now.com/", "https://example.service-now.com/api"),
        (
            "https://example.service-now.com:8443///",
            "https://example.service-now.com:8443/api",
        ),
    ],
)
def test_build_url_normalizes_instance_origin(configured_url, expected_url):
    asset = BasicAuthAsset()
    asset.url = configured_url

    assert ServiceNowClient(asset).build_url("api") == expected_url


@pytest.mark.parametrize(
    "configured_url",
    [
        "example.service-now.com",
        "ftp://example.service-now.com",
        "https://user:password@example.service-now.com",  # pragma: allowlist secret
        "https://example.service-now.com/custom/path",
        "https://example.service-now.com?token=secret",
        "https://example.service-now.com#fragment",
        "https://example.service-now.com invalid",
        "https://example.service-now.com:not-a-port",
    ],
)
def test_client_rejects_invalid_instance_url(configured_url):
    asset = BasicAuthAsset()
    asset.url = configured_url

    with pytest.raises(ActionFailure, match="Invalid ServiceNow URL configured"):
        ServiceNowClient(asset)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://attacker.example/api",
        "//attacker.example/api",
    ],
)
def test_build_url_rejects_absolute_endpoint(endpoint):
    with pytest.raises(ActionFailure, match="Invalid endpoint"):
        ServiceNowClient(BasicAuthAsset()).build_url(endpoint)


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

    monkeypatch.setattr(servicenow_client.httpx, "Client", MockClient)

    with pytest.raises(ServiceNowAPIError) as exc_info:
        ServiceNowClient(BasicAuthAsset()).make_rest_call("/table/incident")

    assert exc_info.value.status_code == 403
    assert "Forbidden" in str(exc_info.value)


def test_empty_successful_table_response_extracts_sys_id_from_location():
    client = ServiceNowClient(BasicAuthAsset())
    response = httpx.Response(
        201,
        headers={
            "Location": (
                "https://example.service-now.com/api/now/table/incident/"
                "created-ticket-sys-id"
            )
        },
        content=b"",
    )

    result = client._process_response(
        response,
        table_location_prefix="https://example.service-now.com/api/now/table",
    )

    assert result == {"result": {"sys_id": "created-ticket-sys-id"}}


def test_empty_successful_response_ignores_non_table_location():
    client = ServiceNowClient(BasicAuthAsset())
    response = httpx.Response(
        201,
        headers={"Location": "https://example.service-now.com/not-a-table/id"},
        content=b"",
    )

    result = client._process_response(
        response,
        table_location_prefix="https://example.service-now.com/api/now/table",
    )

    assert result == {}
