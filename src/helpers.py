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

"""Helper class for ServiceNow connector"""

import ast
import json
import re
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import httpx
from soar_sdk.abstract import SOARClient
from soar_sdk.auth import BasicAuth, OAuthBearerAuth
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from .consts import (
    API_URI,
    BASIC_AUTH_TYPE,
    DEFAULT_OFFSET,
    DEFAULT_LIMIT,
    MAX_PAGES,
    SC_CAT_ITEMS_ENDPOINT,
    TABLE_ENDPOINT,
    TicketNotFoundException,
    PASSWORD_GRANT_AUTH_TYPE,
)
from .oauth_client import (
    create_servicenow_oauth_client,
    migrate_legacy_oauth_state,
    ServiceNowOAuthClient,
)

if TYPE_CHECKING:
    from .app import Asset

logger = getLogger()

PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_path_segment(name: str, value: object) -> str:
    if value is None or not PATH_SEGMENT_RE.fullmatch(str(value)):
        raise ActionFailure(
            f"Invalid '{name}' parameter; expected one ServiceNow table name or identifier"
        )
    return str(value)


def validate_positive_integer(name: str, value: Optional[object], default: int) -> int:
    if value is None:
        return default

    try:
        integer_value = int(value)
    except (TypeError, ValueError) as e:
        raise ActionFailure(
            f"Please provide a valid integer value in the {name} parameter"
        ) from e

    if integer_value != value and not isinstance(value, str):
        raise ActionFailure(
            f"Please provide a valid integer value in the {name} parameter"
        )

    if integer_value <= 0:
        raise ActionFailure(
            f"Please provide a positive integer value in the {name} parameter"
        )

    return integer_value


class ServiceNowClient:
    """Client for ServiceNow API operations."""

    def __init__(
        self, asset: "Asset", *, verify_ssl: bool = True, timeout: float = 30.0
    ):
        """
        Initialize ServiceNow client.
        """
        self.asset = asset
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._response_headers: dict[str, str] = {}
        self._oauth_client: Optional[ServiceNowOAuthClient] = None

    def _normalize_base_url(self) -> str:
        """Normalize base URL by removing trailing slash"""
        base_url = (self.asset.url or "").rstrip("/")
        parsed_url = urlparse(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ActionFailure(
                "Invalid ServiceNow URL configured. Include the protocol, for example "
                "https://myservicenow.enterprise.com"
            )
        return base_url

    def _get_oauth_client(self) -> ServiceNowOAuthClient:
        if self._oauth_client is None:
            oauth_grant_type = getattr(
                self.asset, "oauth_grant_type", PASSWORD_GRANT_AUTH_TYPE
            )
            migrate_legacy_oauth_state(self.asset, oauth_grant_type)
            self._oauth_client = create_servicenow_oauth_client(
                base_url=self._normalize_base_url(),
                client_id=self.asset.client_id,
                client_secret=self.asset.client_secret,
                auth_state=self.asset.auth_state,
                username=self.asset.username or None,
                password=self.asset.password or None,
                grant_type=oauth_grant_type,
                verify_ssl=self.verify_ssl,
                timeout=self.timeout,
            )
        return self._oauth_client

    def force_new_oauth_token(self) -> None:
        """Fetch a fresh OAuth token while preserving refresh-token fallback."""
        self._get_oauth_client().force_new_token()

    def get_auth(self) -> httpx.Auth:
        """Return an httpx.Auth object for the configured credential type."""
        client_id = self.asset.client_id
        client_secret = self.asset.client_secret
        username = self.asset.username
        password = self.asset.password
        auth_type = getattr(self.asset, "oauth_grant_type", PASSWORD_GRANT_AUTH_TYPE)

        if auth_type == BASIC_AUTH_TYPE:
            if username and password:
                logger.info("Using Basic Auth authentication")
                return BasicAuth(username, password)
            raise ActionFailure(
                "Basic Auth requires username and password. Provide both values or "
                "select an OAuth authentication type."
            )

        if client_id or client_secret:
            if not client_id:
                raise ActionFailure(
                    "OAuth configuration is incomplete: client_id is required when "
                    "client_secret is configured. To use Basic Auth, select basic_auth "
                    "as the authentication type."
                )
            if not client_secret:
                raise ActionFailure(
                    "OAuth configuration is incomplete: client_secret is required when "
                    "client_id is configured. To use Basic Auth, select basic_auth as "
                    "the authentication type."
                )
            logger.info("Using OAuth authentication")
            return OAuthBearerAuth(self._get_oauth_client(), auto_refresh=True)

        if username and password:
            logger.info("Using Basic Auth authentication")
            return BasicAuth(username, password)

        raise ActionFailure(
            "Authentication credentials required. Provide either: "
            "(1) client_id and client_secret for OAuth, or "
            "(2) username and password for Basic Auth"
        )

    def _process_response(self, response: httpx.Response) -> dict:
        """
        Process HTTP response from ServiceNow API
        """
        # Try to parse response as JSON
        try:
            response_json = response.json()
        except Exception as e:
            # Non-JSON response - check for error status codes
            if response.status_code >= 400:
                # Extract a clean error message from HTML or text response
                error_message = self._extract_error_from_response(response)
                raise ActionFailure(
                    f"ServiceNow API request failed (HTTP {response.status_code}): {error_message}"
                ) from e
            # Non-error non-JSON response (e.g., 204 No Content)
            return {}

        # Handle error status codes with JSON responses
        if response.status_code >= 400:
            error_msg = self._extract_error_from_json(response_json)
            raise ActionFailure(
                f"ServiceNow API error (HTTP {response.status_code}): {error_msg}"
            )

        return response_json

    def _extract_error_from_json(self, response_json: dict) -> str:
        """
        Extract error message from ServiceNow JSON error response
        """
        # Standard ServiceNow REST API error format
        error = response_json.get("error", {})
        if isinstance(error, dict):
            message = error.get("message", "")
            detail = error.get("detail", "")
            if message:
                return f"{message}{f': {detail}' if detail else ''}"
        elif isinstance(error, str):
            detail = response_json.get("error_description", "")
            return f"{error}{f': {detail}' if detail else ''}"

        # Fallback: return whole response (truncated)
        error_str = str(response_json)
        return error_str[:200] + "..." if len(error_str) > 200 else error_str

    def _extract_error_from_response(self, response: httpx.Response) -> str:
        """
        Extract user-friendly error message from non-JSON response (HTML, text, etc.)
        """
        content = response.text
        if not content:
            return "Unknown error (empty response)"

        if "<html" in content.lower() or "<body" in content.lower():
            soup = BeautifulSoup(content, "html.parser")
            for element in soup(["script", "style", "footer", "nav"]):
                element.extract()
            content = soup.get_text(" ")

        content = " ".join(content.split())

        if not content:
            return "Unknown error (empty response)"

        return content[:500] + "..." if len(content) > 500 else content

    def make_rest_call(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        method: str = "get",
        api_uri: Optional[str] = None,
    ) -> dict:
        """Make a REST API call to ServiceNow."""
        if params is None:
            params = {}
        if api_uri is None:
            api_uri = API_URI

        base_url = self._normalize_base_url()
        url = f"{base_url}{api_uri}{endpoint}"

        try:
            with httpx.Client(auth=self.get_auth(), timeout=self.timeout) as client:
                response = client.request(
                    method=method.upper(),
                    url=url,
                    json=data,
                    headers={"Content-Type": "application/json"},
                    params=params,
                )
            self._response_headers = dict(response.headers)
        except ActionFailure:
            raise
        except httpx.RequestError as e:
            raise ActionFailure(f"Error connecting to server: {e}") from e
        except Exception as e:
            raise ActionFailure(f"Error connecting to server: {e}") from e

        return self._process_response(response)

    def get_sys_id_from_ticket_number(
        self,
        table_name: str,
        ticket_number: str,
    ) -> str:
        """
        Convert ticket number to sys_id by querying ServiceNow
        """
        table_name = validate_path_segment("table", table_name)
        params = {"sysparm_query": f"number={ticket_number}"}
        endpoint = TABLE_ENDPOINT.format(table_name)

        response = self.make_rest_call(endpoint, params=params)

        # Check if result exists - this is the "ticket not found" case
        if not response.get("result"):
            raise TicketNotFoundException(
                f"Ticket not found with number: {ticket_number}"
            )

        # Get sys_id from first result
        results = response.get("result", [])
        if not results or not isinstance(results, list) or len(results) == 0:
            raise TicketNotFoundException(
                f"Ticket not found with number: {ticket_number}"
            )

        ticket = results[0]
        if ticket.get("number") != ticket_number:
            raise TicketNotFoundException(
                "ServiceNow returned a different ticket than the requested ticket number"
            )

        sys_id = ticket.get("sys_id")
        if not sys_id:
            raise TicketNotFoundException(
                f"Unable to fetch ticket SYS ID for number: {ticket_number}"
            )
        sys_id = validate_path_segment("sys_id", sys_id)

        logger.info(f"Converted ticket number {ticket_number} to sys_id: {sys_id}")
        return sys_id

    def paginator(
        self, endpoint: str, payload: Optional[dict] = None, limit: Optional[int] = None
    ) -> list[dict]:
        """
        Paginate through ServiceNow API results
        """
        items_list = []
        if payload is None:
            payload = {}

        payload["sysparm_offset"] = DEFAULT_OFFSET
        payload["sysparm_limit"] = min(limit, DEFAULT_LIMIT) if limit else DEFAULT_LIMIT
        total_item_count = 0
        page_count = 0

        while True:
            response = self.make_rest_call(endpoint, params=payload)
            page_count += 1

            total_count_header = self._response_headers.get(
                "X-Total-Count"
            ) or self._response_headers.get("x-total-count")
            if total_count_header is not None:
                try:
                    total_item_count = int(total_count_header)
                except (TypeError, ValueError):
                    logger.warning(
                        "Ignoring invalid ServiceNow X-Total-Count header: "
                        f"{total_count_header}"
                    )

            result = response.get("result")
            if result:
                items_list.extend(result if isinstance(result, list) else [result])

            if limit and len(items_list) >= limit:
                return items_list[:limit]

            if not result:
                return items_list

            if (
                payload["sysparm_offset"] + payload["sysparm_limit"] >= total_item_count
                and total_item_count > 0
            ):
                return items_list

            if page_count >= MAX_PAGES:
                logger.warning(f"Reached the maximum of {MAX_PAGES} ServiceNow pages")
                return items_list

            payload["sysparm_offset"] += payload["sysparm_limit"]

            if limit:
                remaining = limit - len(items_list)
                if remaining <= 0:
                    return items_list
                payload["sysparm_limit"] = min(remaining, DEFAULT_LIMIT)

    def fetch_catalog_items(
        self,
        catalog_sys_id: Optional[str] = None,
        category_sys_id: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: Optional[int] = None,
        split_catalogs: bool = True,
    ) -> list[dict]:
        """
        Fetch catalog items/services with optional filters
        """
        # Build query parameters based on filters
        payload = {}
        query_parts = []

        # Add catalog filter if provided
        if catalog_sys_id:
            query_parts.append(f"sc_catalogsLIKE{catalog_sys_id}")

        # Add category filter if provided
        if category_sys_id:
            query_parts.append(f"category={category_sys_id}")

        # Add search text filter if provided
        if search_text:
            # Search across multiple fields with OR logic
            search_query = (
                f"nameLIKE{search_text}^OR"
                f"descriptionLIKE{search_text}^OR"
                f"sys_nameLIKE{search_text}^OR"
                f"short_descriptionLIKE{search_text}"
            )
            query_parts.append(search_query)

        # Combine all query parts with ^ (AND operator)
        if query_parts:
            payload["sysparm_query"] = "^".join(query_parts)

        # Use paginator to fetch services
        services = self.paginator(SC_CAT_ITEMS_ENDPOINT, payload=payload, limit=limit)

        if split_catalogs:
            # Process services: split sc_catalogs field if present
            for service in services:
                sc_catalogs = service.get("sc_catalogs")
                if sc_catalogs:
                    # Split comma-separated catalogs
                    service["catalogs"] = sc_catalogs.split(",")
                else:
                    service["catalogs"] = sc_catalogs

        return services

    def upload_attachment(
        self,
        table: str,
        ticket_id: str,
        filename: str,
        file_content: bytes,
        mime_type: Optional[str],
    ) -> tuple[bool, dict | None, str | None]:
        """
        Upload a file attachment to ServiceNow
        """
        content_type = mime_type if mime_type else "application/octet-stream"

        endpoint = "/attachment/file"
        params = {"table_name": table, "table_sys_id": ticket_id, "file_name": filename}

        try:
            base_url = self._normalize_base_url()
            url = f"{base_url}{API_URI}{endpoint}"

            # Match legacy attachment behavior: ServiceNow may take longer than
            # the default API timeout for large files.
            with httpx.Client(auth=self.get_auth(), timeout=None) as client:  # noqa: S113
                response = client.post(
                    url,
                    headers={"Content-Type": content_type},
                    params=params,
                    content=file_content,
                )

            # Process response
            if response.status_code >= 400:
                try:
                    error_message = self._extract_error_from_json(response.json())
                except Exception:
                    error_message = self._extract_error_from_response(response)

                error_message = (
                    f"Failed to upload attachment: HTTP {response.status_code}: "
                    f"{error_message}"
                )
                logger.error(error_message)
                return False, None, error_message

            try:
                response_json = response.json()
                return True, response_json.get("result", {}), None
            except Exception as e:
                error_message = f"Failed to parse attachment upload response: {e}"
                logger.error(error_message)
                return False, None, error_message

        except Exception as e:
            error_message = f"Error uploading attachment: {e}"
            logger.error(error_message)
            return False, None, error_message


class ServiceNowActionHelper:
    """SOAR-specific helper behavior for ServiceNow actions."""

    def __init__(self, soar: SOARClient, client: ServiceNowClient):
        """Initialize the action helper."""
        self.soar = soar
        self.client = client

    def handle_vault_attachments(
        self, table: str, ticket_id: str, vault_ids_str: str
    ) -> tuple[list[dict], dict[str, str]]:
        """
        Handle uploading SOAR vault files as ServiceNow attachments.
        """
        vault_ids = list(
            dict.fromkeys(
                vid.strip() for vid in vault_ids_str.split(",") if vid.strip()
            )
        )

        if not vault_ids:
            return [], {}

        attachment_details = []
        vault_errors = {}

        for vault_id in vault_ids:
            try:
                attachments = self.soar.vault.get_attachment(vault_id=vault_id)
                if not attachments:
                    error_msg = f"Vault file not found for vault_id: {vault_id}"
                    vault_errors[vault_id] = error_msg
                    logger.warning(error_msg)
                    continue

                vault_file = attachments[0]

                with vault_file.open("rb") as f:
                    file_content = f.read()

                upload_success, attachment_result, upload_error = (
                    self.client.upload_attachment(
                        table,
                        ticket_id,
                        vault_file.name,
                        file_content,
                        vault_file.mime_type,
                    )
                )

                if upload_success and attachment_result is not None:
                    attachment_details.append(attachment_result)
                    logger.info(f"Successfully attached file: {vault_file.name}")
                else:
                    error_msg = (
                        upload_error
                        or f"Attachment upload failed for file: {vault_file.name}"
                    )
                    vault_errors[vault_id] = error_msg
                    logger.error(
                        "Attachment upload failed for ticket %s, vault_id %s, file %s: %s",
                        ticket_id,
                        vault_id,
                        vault_file.name,
                        error_msg,
                    )

            except Exception as e:
                error_msg = f"Error attaching vault_id {vault_id}: {e}"
                vault_errors[vault_id] = str(e)
                logger.error(error_msg)

        return attachment_details, vault_errors


# Module-level utility functions for JSON field parsing


def parse_fields_json(fields_str: Optional[str]) -> dict:
    """
    Parse fields JSON string parameter

    Reusable utility function for parsing JSON field parameters
    used in create_ticket and update_ticket actions.
    """
    if not fields_str:
        return {}

    # Escape newlines inside JSON strings (legacy behavior)
    fields_str = escape_newlines_inside_json_strings(fields_str)

    try:
        # Try to parse as JSON first (recommended)
        fields = json.loads(fields_str)
    except json.JSONDecodeError:
        # Fall back to ast.literal_eval for backward compatibility
        try:
            fields = ast.literal_eval(fields_str)
        except Exception as e:
            raise ActionFailure(
                f"Error parsing fields parameter: {e}. "
                "Please ensure the input is valid JSON format"
            ) from e

    if not isinstance(fields, dict):
        raise ActionFailure("Fields parameter must be a JSON object/dictionary")

    return fields


def escape_newlines_inside_json_strings(s: str) -> str:
    """
    Escape newlines that appear inside JSON string values
    """
    lines = s.splitlines(True)
    result = []
    inside_string = False

    for line in lines:
        if '"' in line:
            quote_count = line.count('"')
            if quote_count % 2 != 0:
                inside_string = not inside_string

        if inside_string and not line.strip().endswith('"'):
            # Replace newline with \n
            result.append(line.replace("\n", "\\n"))
        else:
            result.append(line)

    return " ".join(result)
