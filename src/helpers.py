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
from typing import TYPE_CHECKING, Any, Optional

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.exceptions import ActionFailure, SoarAPIError
from soar_sdk.logging import getLogger

if TYPE_CHECKING:
    from .servicenow_client import ServiceNowClient

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


class ServiceNowActionHelper:
    """SOAR-specific helper behavior for ServiceNow actions."""

    def __init__(self, soar: SOARClient, client: "ServiceNowClient"):
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

            except (SoarAPIError, OSError) as e:
                error_msg = f"Error attaching vault_id {vault_id}: {e}"
                vault_errors[vault_id] = str(e)
                logger.error(error_msg)

        return attachment_details, vault_errors


def build_legacy_vault_failure_details(
    vault_errors: dict[str, str],
) -> dict[str, list[str]]:
    vault_failure_details: dict[str, list[str]] = {}
    for vault_id, error in vault_errors.items():
        vault_failure_details.setdefault(error, []).append(vault_id)
    return vault_failure_details


def build_failed_attachment_result(
    params: Any,
    message: str,
    summary: dict,
    result: dict | None = None,
) -> ActionResult:
    action_result = ActionResult(
        status=False,
        message=message,
        param=params.model_dump(mode="json"),
    )
    if result:
        action_result.add_data(result)
    action_result.set_summary(summary)
    return action_result


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
        except (ValueError, SyntaxError) as e:
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
