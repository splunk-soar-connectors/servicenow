# Copyright (c) 2016-2026 Splunk Inc.
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
from urllib.parse import parse_qs

import httpx
import pytest
from soar_sdk.auth.client import OAuthClientError
from soar_sdk.auth.models import OAuthConfig

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.consts import (
    CLIENT_CREDENTIALS_GRANT_TYPE,
    OAUTH_GRANT_TYPE_STATE_KEY,
    PASSWORD_GRANT_AUTH_TYPE,
    PASSWORD_GRANT_TYPE,
)
from src.oauth_client import (
    ServiceNowOAuthClient,
)


class FakeBackend:
    def load_state(self):
        return {}


class FakeAuthState:
    asset_id = "asset-1"

    def __init__(self, state=None):
        self.state = state or {}
        self.backend = FakeBackend()

    def get_all(self, force_reload=False):
        return self.state

    def put_all(self, state):
        self.state = state


def make_config():
    return OAuthConfig(
        client_id="client-id",
        client_secret="client-secret",  # pragma: allowlist secret
        token_endpoint="https://example.service-now.com/oauth_token.do",
        authorization_endpoint=None,
    )


def make_http_client(requests, access_token, refresh_token=None):
    def handler(request):
        requests.append(parse_qs(request.content.decode()))
        response_json = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        if refresh_token:
            response_json["refresh_token"] = refresh_token
        return httpx.Response(
            200,
            json=response_json,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_client_credentials_fetches_token_without_username_or_password():
    requests = []
    auth_state = FakeAuthState()
    client = ServiceNowOAuthClient(
        config=make_config(),
        auth_state=auth_state,
        grant_type=CLIENT_CREDENTIALS_GRANT_TYPE,
        http_client=make_http_client(requests, "client-token"),
    )

    token = client.get_valid_token()

    assert token.access_token == "client-token"
    assert requests == [
        {
            "grant_type": [CLIENT_CREDENTIALS_GRANT_TYPE],
            "client_id": ["client-id"],
            "client_secret": ["client-secret"],
        }
    ]
    assert auth_state.state[OAUTH_GRANT_TYPE_STATE_KEY] == CLIENT_CREDENTIALS_GRANT_TYPE


def test_client_credentials_does_not_use_refresh_token_flow():
    requests = []
    auth_state = FakeAuthState(
        {
            "oauth": {
                "token": {
                    "access_token": "expired-token",
                    "token_type": "Bearer",
                    "expires_at": 1,
                    "refresh_token": "old-refresh-token",
                },
                "client_id": "client-id",
            },
            OAUTH_GRANT_TYPE_STATE_KEY: CLIENT_CREDENTIALS_GRANT_TYPE,
        }
    )
    client = ServiceNowOAuthClient(
        config=make_config(),
        auth_state=auth_state,
        grant_type=CLIENT_CREDENTIALS_GRANT_TYPE,
        http_client=make_http_client(requests, "new-client-token"),
    )

    token = client.get_valid_token()

    assert token.access_token == "new-client-token"
    assert requests[0]["grant_type"] == [CLIENT_CREDENTIALS_GRANT_TYPE]
    assert "refresh_token" not in requests[0]


def test_password_grant_auth_type_fetches_oauth_password_grant():
    requests = []
    auth_state = FakeAuthState()
    client = ServiceNowOAuthClient(
        config=make_config(),
        auth_state=auth_state,
        username="service-user",
        password="service-password",  # pragma: allowlist secret
        http_client=make_http_client(
            requests, "password-token", refresh_token="password-refresh-token"
        ),
    )

    token = client.get_valid_token()

    assert token.access_token == "password-token"
    assert token.refresh_token == "password-refresh-token"
    assert requests == [
        {
            "grant_type": [PASSWORD_GRANT_TYPE],
            "client_id": ["client-id"],
            "username": ["service-user"],
            "password": ["service-password"],
            "client_secret": ["client-secret"],
        }
    ]
    assert auth_state.state[OAUTH_GRANT_TYPE_STATE_KEY] == PASSWORD_GRANT_AUTH_TYPE


def test_password_grant_requires_refresh_token():
    requests = []
    auth_state = FakeAuthState()
    client = ServiceNowOAuthClient(
        config=make_config(),
        auth_state=auth_state,
        username="service-user",
        password="service-password",  # pragma: allowlist secret
        http_client=make_http_client(requests, "password-token"),
    )

    with pytest.raises(OAuthClientError, match="missing a refresh token"):
        client.get_valid_token()


def test_legacy_password_auth_type_is_treated_as_password_grant():
    requests = []
    auth_state = FakeAuthState(
        {
            "oauth": {
                "token": {
                    "access_token": "old-password-token",
                    "token_type": "Bearer",
                    "expires_at": 9999999999,
                },
                "client_id": "client-id",
            },
            OAUTH_GRANT_TYPE_STATE_KEY: PASSWORD_GRANT_TYPE,
        }
    )
    client = ServiceNowOAuthClient(
        config=make_config(),
        auth_state=auth_state,
        username="service-user",
        password="service-password",  # pragma: allowlist secret
        grant_type=PASSWORD_GRANT_AUTH_TYPE,
        http_client=make_http_client(
            requests, "password-token", refresh_token="password-refresh-token"
        ),
    )

    token = client.get_valid_token()

    assert token.access_token == "old-password-token"
    assert requests == []


def test_grant_type_change_discards_stored_password_token():
    requests = []
    auth_state = FakeAuthState(
        {
            "oauth": {
                "token": {
                    "access_token": "old-password-token",
                    "token_type": "Bearer",
                    "expires_at": 9999999999,
                },
                "client_id": "client-id",
            },
            OAUTH_GRANT_TYPE_STATE_KEY: PASSWORD_GRANT_AUTH_TYPE,
        }
    )
    client = ServiceNowOAuthClient(
        config=make_config(),
        auth_state=auth_state,
        grant_type=CLIENT_CREDENTIALS_GRANT_TYPE,
        http_client=make_http_client(requests, "client-token"),
    )

    token = client.get_valid_token()

    assert token.access_token == "client-token"
    assert requests[0]["grant_type"] == [CLIENT_CREDENTIALS_GRANT_TYPE]
    assert auth_state.state[OAUTH_GRANT_TYPE_STATE_KEY] == CLIENT_CREDENTIALS_GRANT_TYPE
