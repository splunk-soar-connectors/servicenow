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

import httpx
import pytest
from soar_sdk.auth import BasicAuth, OAuthBearerAuth
from soar_sdk.auth.client import (
    AuthorizationRequiredError,
    OAuthClientError,
    SOARAssetOAuthClient,
    TokenRefreshError,
)
from soar_sdk.auth.models import OAuthConfig, OAuthToken
from soar_sdk.exceptions import ActionFailure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions import test_connectivity as test_connectivity_action
from src.helpers import ServiceNowClient
from src.oauth_client import ServiceNowOAuthClient


class FakeAuthState:
    def __init__(self):
        self.data = {}

    def get_all(self, *, force_reload=False):
        return self.data

    def put_all(self, new_value):
        self.data = new_value

    def delete(self, key):
        self.data.pop(key, None)


def make_asset(**overrides):
    values = {
        "url": "https://example.service-now.com",
        "username": None,
        "password": None,
        "client_id": None,
        "client_secret": None,
        "auth_state": FakeAuthState(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_oauth_client(username=None, password=None):
    config = OAuthConfig(
        client_id="client-id",
        client_secret="client-secret",  # pragma: allowlist secret
        token_endpoint="https://example.service-now.com/oauth_token.do",
    )
    return ServiceNowOAuthClient(
        config=config,
        auth_state=FakeAuthState(),
        username=username,
        password=password,
    )


def test_get_auth_uses_basic_auth_without_oauth_fields():
    helper = ServiceNowClient(
        make_asset(username="user", password="pass")  # pragma: allowlist secret
    )

    assert isinstance(helper._get_auth(), BasicAuth)


def test_public_get_auth_uses_basic_auth_without_oauth_fields():
    helper = ServiceNowClient(
        make_asset(username="user", password="pass")  # pragma: allowlist secret
    )

    assert isinstance(helper.get_auth(), BasicAuth)


def test_get_auth_uses_oauth_when_client_credentials_are_configured():
    helper = ServiceNowClient(
        make_asset(
            username="user",
            password="pass",  # pragma: allowlist secret
            client_id="client-id",
            client_secret="client-secret",  # pragma: allowlist secret
        ),
    )

    assert isinstance(helper._get_auth(), OAuthBearerAuth)


def test_public_get_auth_uses_oauth_when_client_credentials_are_configured():
    helper = ServiceNowClient(
        make_asset(
            username="user",
            password="pass",  # pragma: allowlist secret
            client_id="client-id",
            client_secret="client-secret",  # pragma: allowlist secret
        ),
    )

    assert isinstance(helper.get_auth(), OAuthBearerAuth)


def test_private_get_auth_alias_delegates_to_public_get_auth(monkeypatch):
    helper = ServiceNowClient(make_asset())
    expected_auth = object()

    monkeypatch.setattr(helper, "get_auth", lambda: expected_auth)

    assert helper._get_auth() is expected_auth


def test_get_auth_rejects_client_id_without_client_secret():
    helper = ServiceNowClient(
        make_asset(
            client_id="client-id",
            username="user",
            password="pass",  # pragma: allowlist secret
        )
    )

    with pytest.raises(ValueError, match="client_secret is required"):
        helper._get_auth()


def test_get_auth_rejects_client_secret_without_client_id():
    helper = ServiceNowClient(
        make_asset(
            client_secret="client-secret",  # pragma: allowlist secret
            username="user",
            password="pass",  # pragma: allowlist secret
        )
    )

    with pytest.raises(ValueError, match="client_id is required"):
        helper._get_auth()


def test_get_auth_rejects_missing_credentials():
    helper = ServiceNowClient(make_asset())

    with pytest.raises(ValueError, match="Authentication credentials required"):
        helper._get_auth()


def test_helper_rejects_url_without_protocol():
    helper = ServiceNowClient(make_asset(url="example.service-now.com"))

    with pytest.raises(ActionFailure, match="Include the protocol"):
        helper._normalize_base_url()


def test_helper_rejects_empty_url():
    helper = ServiceNowClient(make_asset(url=""))

    with pytest.raises(ActionFailure, match="Invalid ServiceNow URL"):
        helper._normalize_base_url()


def test_test_connectivity_preserves_request_failure_message(monkeypatch):
    messages = []

    class FakeSOAR:
        def set_message(self, message):
            messages.append(message)

    class FakeHelper:
        def __init__(self, asset):
            self.asset = asset

        def make_rest_call(self, *args, **kwargs):
            raise ActionFailure(
                "Invalid ServiceNow URL configured. Include the protocol"
            )

    monkeypatch.setattr(test_connectivity_action, "ServiceNowClient", FakeHelper)

    asset = make_asset(username="user", password="pass")  # pragma: allowlist secret
    with pytest.raises(Exception, match="Invalid ServiceNow URL configured"):
        test_connectivity_action.test_connectivity.__wrapped__(
            soar=FakeSOAR(), asset=asset
        )

    assert messages == [
        "Test Connectivity Failed: Action failure: Invalid ServiceNow URL configured. Include the protocol"
    ]


def test_oauth_client_returns_valid_sdk_token(monkeypatch):
    client = make_oauth_client(
        username="user",
        password="pass",  # pragma: allowlist secret
    )
    token = OAuthToken(access_token="stored-token")

    def get_valid_token(self, *, auto_refresh=True):
        return token

    monkeypatch.setattr(SOARAssetOAuthClient, "get_valid_token", get_valid_token)

    assert client.get_valid_token() is token


def test_oauth_client_bootstraps_with_password_grant_when_no_token(monkeypatch):
    client = make_oauth_client(
        username="user",
        password="pass",  # pragma: allowlist secret
    )
    token = OAuthToken(access_token="password-token")

    def get_valid_token(self, *, auto_refresh=True):
        raise AuthorizationRequiredError("No token")

    def fetch_token_with_password(username, password):
        assert username == "user"
        assert password == "pass"  # pragma: allowlist secret
        return token

    def fetch_token_with_client_credentials():
        raise AssertionError("client credentials must not be used")

    monkeypatch.setattr(SOARAssetOAuthClient, "get_valid_token", get_valid_token)
    monkeypatch.setattr(client, "fetch_token_with_password", fetch_token_with_password)
    monkeypatch.setattr(
        client,
        "fetch_token_with_client_credentials",
        fetch_token_with_client_credentials,
    )

    assert client.get_valid_token() is token


def test_oauth_client_falls_back_to_password_grant_when_refresh_fails(monkeypatch):
    client = make_oauth_client(
        username="user",
        password="pass",  # pragma: allowlist secret
    )
    token = OAuthToken(access_token="password-token")

    def get_valid_token(self, *, auto_refresh=True):
        raise TokenRefreshError("refresh failed")

    monkeypatch.setattr(SOARAssetOAuthClient, "get_valid_token", get_valid_token)
    monkeypatch.setattr(
        client, "fetch_token_with_password", lambda username, password: token
    )

    assert client.get_valid_token() is token


def test_oauth_client_refresh_token_falls_back_to_password_grant(monkeypatch):
    client = make_oauth_client(
        username="user",
        password="pass",  # pragma: allowlist secret
    )
    token = OAuthToken(access_token="password-token")

    def refresh_token(self, refresh_token):
        assert refresh_token == "stored-refresh"
        raise TokenRefreshError("refresh failed")

    def fetch_token_with_password(username, password):
        assert username == "user"
        assert password == "pass"  # pragma: allowlist secret
        return token

    monkeypatch.setattr(SOARAssetOAuthClient, "refresh_token", refresh_token)
    monkeypatch.setattr(client, "fetch_token_with_password", fetch_token_with_password)

    assert client.refresh_token("stored-refresh") is token


def test_oauth_client_refresh_token_reraises_without_username_password(monkeypatch):
    client = make_oauth_client()

    def refresh_token(self, refresh_token):
        raise TokenRefreshError("refresh failed")

    monkeypatch.setattr(SOARAssetOAuthClient, "refresh_token", refresh_token)

    with pytest.raises(TokenRefreshError, match="refresh failed"):
        client.refresh_token("stored-refresh")


def test_oauth_client_rejects_bootstrap_without_username_password(monkeypatch):
    client = make_oauth_client()

    def get_valid_token(self, *, auto_refresh=True):
        raise AuthorizationRequiredError("No token")

    def fetch_token_with_client_credentials():
        raise AssertionError("client credentials must not be used")

    monkeypatch.setattr(SOARAssetOAuthClient, "get_valid_token", get_valid_token)
    monkeypatch.setattr(
        client,
        "fetch_token_with_client_credentials",
        fetch_token_with_client_credentials,
    )

    with pytest.raises(OAuthClientError, match="requires username and password"):
        client.get_valid_token()


def test_oauth_client_rejects_refresh_failure_without_username_password(monkeypatch):
    client = make_oauth_client()

    def get_valid_token(self, *, auto_refresh=True):
        raise TokenRefreshError("refresh failed")

    monkeypatch.setattr(SOARAssetOAuthClient, "get_valid_token", get_valid_token)

    with pytest.raises(OAuthClientError, match="requires username and password"):
        client.get_valid_token()


def test_oauth_client_force_new_token_uses_stored_refresh_token(monkeypatch):
    client = make_oauth_client()
    stored_token = OAuthToken(access_token="old-token", refresh_token="stored-refresh")
    refreshed_token = OAuthToken(access_token="refreshed-token")

    def clear_tokens():
        raise AssertionError("force_new_token must not clear stored tokens")

    def refresh_token(refresh_token):
        assert refresh_token == "stored-refresh"
        return refreshed_token

    monkeypatch.setattr(client, "get_stored_token", lambda: stored_token)
    monkeypatch.setattr(client, "_clear_tokens", clear_tokens)
    monkeypatch.setattr(client, "refresh_token", refresh_token)

    assert client.force_new_token() is refreshed_token


def test_oauth_client_force_new_token_uses_password_grant_without_refresh_token(
    monkeypatch,
):
    client = make_oauth_client(
        username="user",
        password="pass",  # pragma: allowlist secret
    )
    password_token = OAuthToken(access_token="password-token")

    def fetch_token_with_password(username, password):
        assert username == "user"
        assert password == "pass"  # pragma: allowlist secret
        return password_token

    monkeypatch.setattr(client, "get_stored_token", lambda: None)
    monkeypatch.setattr(client, "fetch_token_with_password", fetch_token_with_password)

    assert client.force_new_token() is password_token


def test_oauth_client_force_new_token_rejects_without_refresh_or_password(monkeypatch):
    client = make_oauth_client()

    monkeypatch.setattr(
        client, "get_stored_token", lambda: OAuthToken(access_token="old-token")
    )

    with pytest.raises(OAuthClientError, match="requires a stored refresh token"):
        client.force_new_token()


def test_helper_force_new_oauth_token_delegates_to_oauth_client():
    helper = ServiceNowClient(make_asset())
    called = False

    class FakeOAuthClient:
        def force_new_token(self):
            nonlocal called
            called = True

    helper._oauth_client = FakeOAuthClient()

    helper.force_new_oauth_token()

    assert called


def test_helper_passes_verify_ssl_to_oauth_client(monkeypatch):
    captured = {}

    def fake_create_servicenow_oauth_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "src.helpers.create_servicenow_oauth_client",
        fake_create_servicenow_oauth_client,
    )

    helper = ServiceNowClient(
        make_asset(
            username="user",
            password="pass",  # pragma: allowlist secret
            client_id="client-id",
            client_secret="client-secret",  # pragma: allowlist secret
        ),
        verify_ssl=False,
    )

    assert helper._get_oauth_client() is helper._oauth_client
    assert captured["verify_ssl"] is False


def test_extract_error_from_response_simplifies_html_body():
    helper = ServiceNowClient(make_asset())
    response = httpx.Response(
        500,
        html="""
        <html>
          <head><title>ServiceNow Error</title><style>.hidden {}</style></head>
          <body>
            <nav>Navigation</nav>
            <h1>Server Error</h1>
            <script>alert("ignore")</script>
            <p>Detailed failure</p>
            <footer>Footer</footer>
          </body>
        </html>
        """,
    )

    assert helper._extract_error_from_response(response) == (
        "ServiceNow Error Server Error Detailed failure"
    )


def test_extract_error_from_response_truncates_plain_text():
    helper = ServiceNowClient(make_asset())
    response = httpx.Response(500, text="x" * 600)

    error = helper._extract_error_from_response(response)

    assert error == f"{'x' * 500}..."


def test_extract_error_from_response_handles_empty_body():
    helper = ServiceNowClient(make_asset())
    response = httpx.Response(500, text="")

    assert (
        helper._extract_error_from_response(response)
        == "Unknown error (empty response)"
    )
