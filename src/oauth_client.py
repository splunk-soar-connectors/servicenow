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

from typing import TYPE_CHECKING, Any

import httpx
from soar_sdk.auth.client import (
    SOARAssetOAuthClient,
    OAuthClientError,
    TokenExpiredError,
    AuthorizationRequiredError,
    TokenRefreshError,
)
from soar_sdk.auth.models import OAuthConfig, OAuthToken
from soar_sdk.logging import getLogger
from soar_sdk.shims.phantom.encryption_helper import encryption_helper

if TYPE_CHECKING:
    from soar_sdk.asset_state import AssetState

logger = getLogger()


def migrate_legacy_oauth_state(asset: Any) -> None:
    """Seed SDK auth state from legacy flat OAuth token state after upgrade."""
    auth_state = asset.auth_state
    current_state = auth_state.get_all()

    current_oauth = current_state.get("oauth")
    if isinstance(current_oauth, dict) and current_oauth.get("token"):
        return

    legacy_state = auth_state.backend.load_state() or {}
    legacy_token = legacy_state.get("oauth_token")
    if not isinstance(legacy_token, dict):
        return

    access_token = legacy_token.get("access_token")
    refresh_token = legacy_token.get("refresh_token")

    if legacy_state.get("is_encrypted"):
        if access_token:
            access_token = encryption_helper.decrypt(access_token, auth_state.asset_id)
        if refresh_token:
            refresh_token = encryption_helper.decrypt(
                refresh_token, auth_state.asset_id
            )

    if not access_token and not refresh_token:
        return

    sdk_token: dict[str, Any] = {
        "access_token": access_token or "",
        "token_type": legacy_token.get("token_type") or "Bearer",
    }

    if refresh_token:
        sdk_token["refresh_token"] = refresh_token
        sdk_token["expires_at"] = 0

    if scope := legacy_token.get("scope"):
        sdk_token["scope"] = scope

    migrated_state = dict(current_state)
    migrated_state["oauth"] = {
        "token": sdk_token,
        "client_id": asset.client_id,
    }
    auth_state.put_all(migrated_state)


class ServiceNowOAuthClient(SOARAssetOAuthClient):
    """
    Extended OAuth client with ServiceNow OAuth support.

    Extends the SDK's OAuth client to add:
    - Resource Owner Password Credentials grant (backward compatibility)
    - Automatic token refresh and state persistence
    """

    def __init__(
        self,
        *args: Any,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._username = username
        self._password = password

    def get_valid_token(self, *, auto_refresh: bool = True) -> OAuthToken:
        """
        Get a valid token, falling back to password grant when needed.

        Overrides the SDK base to support the password grant flow for legacy instances.
        """
        try:
            return super().get_valid_token(auto_refresh=auto_refresh)
        except (TokenExpiredError, AuthorizationRequiredError, TokenRefreshError) as e:
            if not (self._username and self._password):
                raise OAuthClientError(
                    "OAuth authentication requires username and password to generate a "
                    "ServiceNow OAuth token when no valid refresh token is available."
                ) from e

            logger.info("Fetching new token with legacy password grant")
            return self.fetch_token_with_password(self._username, self._password)

    def refresh_token(self, refresh_token: str) -> OAuthToken:
        """
        Refresh an OAuth token, falling back to password grant for legacy compatibility.
        """
        try:
            return super().refresh_token(refresh_token)
        except TokenRefreshError:
            if not (self._username and self._password):
                raise

            logger.info("Refresh token failed; falling back to legacy password grant")
            return self.fetch_token_with_password(self._username, self._password)

    def force_new_token(self) -> OAuthToken:
        """
        Fetch a fresh OAuth token without discarding the stored refresh token.
        """
        token = self.get_stored_token()

        if token and token.refresh_token:
            return self.refresh_token(token.refresh_token)

        if self._username and self._password:
            logger.info("Fetching new token with legacy password grant")
            return self.fetch_token_with_password(self._username, self._password)

        raise OAuthClientError(
            "OAuth authentication requires a stored refresh token or username and "
            "password to generate a fresh ServiceNow OAuth token."
        )

    def fetch_token_with_password(
        self,
        username: str,
        password: str,
        *,
        extra_params: dict[str, Any] | None = None,
    ) -> OAuthToken:
        """
        Fetch an access token using Resource Owner Password Credentials grant.
        Kept for backward compatibility with legacy ServiceNow OAuth assets.
        """
        logger.debug("Fetching OAuth token with legacy password grant")

        data: dict[str, Any] = {
            "grant_type": "password",
            "client_id": self._config.client_id,
            "username": username,
            "password": password,
        }

        if self._config.client_secret:
            data["client_secret"] = self._config.client_secret

        scope = self._config.get_scope_string()
        if scope:
            data["scope"] = scope

        if extra_params:
            data.update(extra_params)

        try:
            response = self._http_client.post(
                self._config.token_endpoint,
                data=data,
                timeout=self._timeout,
            )
            response.raise_for_status()
            token_data = response.json()

        except httpx.HTTPStatusError as e:
            error_detail = self._extract_error_detail(e.response)
            raise OAuthClientError(
                f"Password grant token request failed: {error_detail}"
            ) from e

        except httpx.RequestError as e:
            raise OAuthClientError(f"Password grant token request failed: {e}") from e

        token = OAuthToken.model_validate(token_data)
        self._store_token(token)
        logger.debug("OAuth token fetched and stored successfully")

        return token


def create_servicenow_oauth_client(
    base_url: str,
    client_id: str,
    client_secret: str,
    auth_state: AssetState,
    *,
    username: str | None = None,
    password: str | None = None,
    verify_ssl: bool = True,
    timeout: float = 30.0,
) -> ServiceNowOAuthClient:
    """
    Factory function to create a ServiceNow OAuth client.
    """
    base_url = base_url.rstrip("/")

    config = OAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint=f"{base_url}/oauth_token.do",
        authorization_endpoint=None,
    )

    return ServiceNowOAuthClient(
        config=config,
        auth_state=auth_state,
        username=username,
        password=password,
        verify_ssl=verify_ssl,
        timeout=timeout,
    )
