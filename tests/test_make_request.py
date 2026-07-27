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
from typing import ClassVar

import httpx
import pytest
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions import make_request as make_request_module
from src.actions.make_request import (
    ServiceNowMakeRequestOutput,
    ServiceNowMakeRequestParams,
    make_request,
)
from src.helpers import ServiceNowClient

run_make_request = make_request.__wrapped__


class FakeHTTPClient:
    calls: ClassVar[list[dict]] = []
    response = httpx.Response(200, json={"result": "ok"})

    def __init__(self, *, timeout, verify):
        self.timeout = timeout
        self.verify = verify
        FakeHTTPClient.calls.append({"timeout": timeout, "verify": verify})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def request(self, **kwargs):
        FakeHTTPClient.calls[-1]["request"] = kwargs
        return FakeHTTPClient.response


def make_asset(**overrides):
    values = {
        "url": "https://example.service-now.com/",
        "username": "user",
        "password": "pass",  # pragma: allowlist secret
        "client_id": None,
        "client_secret": None,
        "auth_state": SimpleNamespace(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_params(**overrides):
    values = {"endpoint": "/api/now/table/incident"}
    values.update(overrides)
    return ServiceNowMakeRequestParams(**values)


@pytest.fixture(autouse=True)
def patch_http_and_auth(monkeypatch):
    FakeHTTPClient.calls = []
    FakeHTTPClient.response = httpx.Response(200, json={"result": "ok"})
    monkeypatch.setattr(make_request_module.httpx, "Client", FakeHTTPClient)
    monkeypatch.setattr(ServiceNowClient, "get_auth", lambda self: "auth-object")

    def fail_private_auth(self):
        raise AssertionError("make_request must use get_auth, not _get_auth")

    monkeypatch.setattr(ServiceNowClient, "_get_auth", fail_private_auth)


def latest_request():
    return FakeHTTPClient.calls[-1]["request"]


def test_rejects_full_url_endpoint():
    with pytest.raises(ActionFailure, match="Invalid endpoint"):
        run_make_request(
            make_params(endpoint="https://other.example.com/api/now/table/incident"),
            make_asset(),
        )

    assert FakeHTTPClient.calls == []


def test_adds_leading_slash_and_uses_public_auth_helper():
    run_make_request(make_params(endpoint="api/now/table/incident"), make_asset())

    request = latest_request()
    assert request["url"] == "https://example.service-now.com/api/now/table/incident"
    assert request["auth"] == "auth-object"


def test_auth_configuration_errors_return_action_failure(monkeypatch):
    def fail_auth(self):
        raise ValueError("Authentication credentials required")

    monkeypatch.setattr(ServiceNowClient, "get_auth", fail_auth)

    with pytest.raises(ActionFailure, match="Authentication configuration error"):
        run_make_request(make_params(), make_asset())

    assert FakeHTTPClient.calls == []


def test_preserves_embedded_endpoint_query():
    run_make_request(
        make_params(endpoint="/api/now/table/sys_user?sysparm_limit=1"),
        make_asset(),
    )

    assert latest_request()["url"] == (
        "https://example.service-now.com/api/now/table/sys_user?sysparm_limit=1"
    )


def test_defaults_to_get_and_verify_ssl_true():
    params = make_params()

    run_make_request(params, make_asset())

    assert params.http_method == "GET"
    assert params.verify_ssl is True
    assert latest_request()["method"] == "GET"
    assert FakeHTTPClient.calls[-1]["verify"] is True


def test_verify_ssl_false_is_used_for_api_request():
    run_make_request(make_params(verify_ssl=False), make_asset())

    assert FakeHTTPClient.calls[-1]["verify"] is False


def test_declares_allowed_http_methods():
    field = ServiceNowMakeRequestParams.model_fields["http_method"]

    assert field.json_schema_extra["value_list"] == [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "HEAD",
        "OPTIONS",
    ]


def test_sends_json_query_parameters_as_params():
    run_make_request(
        make_params(query_parameters='{"sysparm_limit": "1", "active": "true"}'),
        make_asset(),
    )

    request = latest_request()
    assert request["url"] == "https://example.service-now.com/api/now/table/incident"
    assert request["params"] == {"sysparm_limit": "1", "active": "true"}


def test_appends_raw_query_string_without_strict_validation():
    run_make_request(
        make_params(
            query_parameters="?sysparm_query=short_descriptionLIKEfoo^active=true"
        ),
        make_asset(),
    )

    assert latest_request()["url"] == (
        "https://example.service-now.com/api/now/table/incident?"
        "sysparm_query=short_descriptionLIKEfoo^active=true"
    )
    assert latest_request()["params"] is None


def test_appends_raw_query_string_to_endpoint_with_existing_query():
    run_make_request(
        make_params(
            endpoint="/api/now/table/incident?sysparm_limit=1",
            query_parameters="sysparm_query=active=true",
        ),
        make_asset(),
    )

    assert latest_request()["url"] == (
        "https://example.service-now.com/api/now/table/incident?"
        "sysparm_limit=1&sysparm_query=active=true"
    )


def test_parses_json_body_for_non_get_request():
    run_make_request(
        make_params(http_method="POST", body='{"short_description": "created"}'),
        make_asset(),
    )

    request = latest_request()
    assert request["method"] == "POST"
    assert request["json"] == {"short_description": "created"}
    assert request["content"] is None


def test_sends_non_json_body_as_raw_content():
    run_make_request(
        make_params(
            http_method="POST",
            headers='{"Content-Type": "application/xml", "Accept": "application/xml"}',
            body="<request><short_description>created</short_description></request>",
        ),
        make_asset(),
    )

    request = latest_request()
    assert request["method"] == "POST"
    assert request["headers"] == {
        "Content-Type": "application/xml",
        "Accept": "application/xml",
    }
    assert request["json"] is None
    assert request["content"] == (
        "<request><short_description>created</short_description></request>"
    )


def test_json_subtype_body_is_parsed_as_json():
    run_make_request(
        make_params(
            http_method="POST",
            headers='{"Content-Type": "application/vnd.collection+json"}',
            body='{"short_description": "created"}',
        ),
        make_asset(),
    )

    request = latest_request()
    assert request["json"] == {"short_description": "created"}
    assert request["content"] is None


def test_parses_json_headers_and_merges_default_content_type():
    run_make_request(
        make_params(
            headers='{"Accept": "application/json", "Content-Type": "custom/type"}'
        ),
        make_asset(),
    )

    assert latest_request()["headers"] == {
        "Content-Type": "custom/type",
        "Accept": "application/json",
    }


def test_invalid_json_body_raises_action_failure():
    with pytest.raises(ActionFailure, match="Invalid JSON body"):
        run_make_request(make_params(body="{not json"), make_asset())


def test_invalid_json_headers_raise_action_failure():
    with pytest.raises(ActionFailure, match="Invalid JSON headers"):
        run_make_request(make_params(headers="{not json"), make_asset())


def test_output_preserves_response_metadata_and_top_level_json_fields():
    FakeHTTPClient.response = httpx.Response(
        201,
        json={
            "result": {"sys_id": "abc"},
            "u_custom_field": "custom",
        },
    )

    output = run_make_request(make_params(http_method="POST"), make_asset())

    assert output.model_dump() == {
        "status_code": 201,
        "response_body": '{"result":{"sys_id":"abc"},"u_custom_field":"custom"}',
        "result": {"sys_id": "abc"},
        "u_custom_field": "custom",
    }


def test_output_keeps_status_and_body_for_non_dict_json_response():
    response = httpx.Response(200, json=[{"sys_id": "abc"}])

    output = ServiceNowMakeRequestOutput.from_response(response)

    assert output.model_dump() == {
        "status_code": 200,
        "response_body": '[{"sys_id":"abc"}]',
    }


def test_output_keeps_status_and_body_for_non_json_response():
    response = httpx.Response(204, text="")

    output = ServiceNowMakeRequestOutput.from_response(response)

    assert output.model_dump() == {"status_code": 204, "response_body": ""}


def test_http_error_response_returns_output():
    FakeHTTPClient.response = httpx.Response(
        404, json={"error": {"message": "not found"}}
    )

    output = run_make_request(make_params(), make_asset())

    assert output.model_dump() == {
        "status_code": 404,
        "response_body": '{"error":{"message":"not found"}}',
        "error": {"message": "not found"},
    }
