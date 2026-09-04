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

"""On Poll Action for ServiceNow"""

import ipaddress
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional, Any, Union
from collections.abc import Iterator
from zoneinfo import ZoneInfo

from soar_sdk.abstract import SOARClient
from soar_sdk.params import OnPollParams
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact
from soar_sdk.logging import getLogger
from soar_sdk.exceptions import ActionFailure

from ..app import app, Asset
from ..consts import TABLE_ENDPOINT
from ..helpers import validate_path_segment
from ..servicenow_client import ServiceNowClient

logger = getLogger()

# Regex patterns for artifact extraction
URI_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#~]|[!*\\(\\),]|[^\x00-\x7f]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
HASH_REGEX = r"\b[0-9a-fA-F]{32}\b|\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{64}\b"
IP_REGEX = r"(?<![0-9A-Za-z_.-])\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?![0-9A-Za-z_.-])"
IPV6_REGEX = "(?<![0-9A-Za-z:])((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|"
IPV6_REGEX += "(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3})|:))"
IPV6_REGEX += (
    "|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:"
    "((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3})|:))|"
)
IPV6_REGEX += (
    "(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:"
    "((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\."
    "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|"
)
IPV6_REGEX += (
    "(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:"
    "[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\."
    "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|"
)
IPV6_REGEX += (
    "(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|"
    "((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\."
    "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|"
)
IPV6_REGEX += (
    "(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|"
    "((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\."
    "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|"
)
IPV6_REGEX += (
    "(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\\d|1\\d\\d|"
    "[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:)))(?:%[0-9A-Za-z._~-]+)?(?![0-9A-Za-z:])"
)

SERVICENOW_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
SERVICENOW_DEFAULT_TABLE = "incident"
UTC_CHECKPOINT_FIELD = "last_time_epoch_ms"
LAST_SYS_ID_FIELD = "last_sys_id"
ON_POLL_ORDERING = ("ORDERBYsys_updated_on", "ORDERBYsys_id")


def _format_utc_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        SERVICENOW_DATETIME_FORMAT
    )


def _format_epoch_checkpoint(checkpoint: Any) -> str | None:
    """Format a UTC epoch-millisecond checkpoint for a ServiceNow query."""
    if isinstance(checkpoint, bool):
        return None
    try:
        checkpoint_ms = int(checkpoint)
    except (TypeError, ValueError):
        return None
    if checkpoint_ms <= 0:
        return None
    return _format_utc_timestamp(checkpoint_ms / 1000.0)


def _parse_utc_checkpoint(timestamp: str) -> int | None:
    """Convert a UTC ServiceNow timestamp into epoch milliseconds."""
    try:
        parsed = datetime.strptime(timestamp, SERVICENOW_DATETIME_FORMAT).replace(
            tzinfo=timezone.utc
        )
    except (TypeError, ValueError):
        return None
    return int(parsed.timestamp() * 1000)


def _timezone_value(timezone_value: Any) -> ZoneInfo | None:
    if not timezone_value:
        return None
    if isinstance(timezone_value, ZoneInfo):
        return timezone_value
    return ZoneInfo(str(timezone_value))


def _format_service_now_time(timestamp: float) -> str:
    """Format an SDK epoch timestamp as a UTC ServiceNow query value."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        SERVICENOW_DATETIME_FORMAT
    )


def _format_time_query(operator: str, value: str, timezone_value: Any = None) -> str:
    if not timezone_value:
        return f"^sys_updated_on{operator}{value}"

    query_date, query_time = value.split(" ")
    return (
        f"^sys_updated_on{operator}"
        f"javascript:gs.dateGenerate('{query_date}','{query_time}')"
    )


def _join_query_parts(*parts: str | None) -> str:
    """Join encoded-query parts while removing separator characters."""
    return "^".join(str(part).strip("^") for part in parts if part)


def _time_query_condition(operator: str, value: str, timezone_value: Any = None) -> str:
    """Return a ServiceNow time condition without a leading separator."""
    return _format_time_query(operator, value, timezone_value).lstrip("^")


def _build_ordered_query(custom_filter: str | None, *conditions: str | None) -> str:
    """Build a query with the stable On Poll ordering applied."""
    return _join_query_parts(custom_filter, *conditions, *ON_POLL_ORDERING)


def _build_scheduled_query(
    custom_filter: str | None,
    last_time: str | None,
    last_sys_id: str | None,
    timezone_value: Any = None,
    using_utc_checkpoint: bool = False,
) -> str:
    """Build a legacy or composite scheduled-poll checkpoint query."""
    query_timezone = None if using_utc_checkpoint else timezone_value

    if not last_time:
        return _build_ordered_query(custom_filter)

    if last_sys_id:
        records_after_time = _time_query_condition(">", last_time, query_timezone)
        records_at_time_after_id = _join_query_parts(
            _time_query_condition("=", last_time, query_timezone),
            f"sys_id>{last_sys_id}",
        )
        composite_filter = "^NQ".join(
            (
                _join_query_parts(custom_filter, records_after_time),
                _join_query_parts(custom_filter, records_at_time_after_id),
            )
        )
        return _join_query_parts(composite_filter, *ON_POLL_ORDERING)

    # Legacy assets have only a timestamp. Include the boundary timestamp once
    # so records at that timestamp cannot be skipped during migration.
    return _build_ordered_query(
        custom_filter, _time_query_condition(">=", last_time, query_timezone)
    )


def _sanitize_checkpoint_time(
    checkpoint: Any, timezone_value: Any = None
) -> str | None:
    checkpoint_timezone = _timezone_value(timezone_value) or timezone.utc
    try:
        checkpoint_time = datetime.strptime(
            str(checkpoint), SERVICENOW_DATETIME_FORMAT
        ).replace(tzinfo=checkpoint_timezone)
    except (TypeError, ValueError):
        return None

    current_time = datetime.now(checkpoint_timezone)
    if checkpoint_time > current_time:
        logger.info(
            f"ServiceNow checkpoint {checkpoint} is in the future; clamping it to the current time"
        )
        return current_time.strftime(SERVICENOW_DATETIME_FORMAT)
    return str(checkpoint)


def _strip_format_controls(value: Any) -> Any:
    if isinstance(value, str):
        return "".join(
            character for character in value if unicodedata.category(character) != "Cf"
        )
    if isinstance(value, dict):
        return {key: _strip_format_controls(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_strip_format_controls(item) for item in value]
    return value


def _ticket_text_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _ticket_text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _ticket_text_values(item)


def _valid_ip_address(value: str, version: int) -> str | None:
    try:
        address = ipaddress.ip_address(value.strip().split("%", 1)[0])
    except ValueError:
        return None

    if address.version != version:
        return None
    return str(address)


def migrate_legacy_ingest_state(asset: Asset) -> None:
    """Seed SDK ingest state from legacy flat connector state after upgrade."""
    state = asset.ingest_state

    needs_last_time = "last_time" not in state and UTC_CHECKPOINT_FIELD not in state
    needs_first_run = "first_run" not in state

    if not needs_last_time and not needs_first_run:
        return

    legacy_state = state.backend.load_state() or {}
    legacy_last_time = legacy_state.get("last_time")

    if needs_last_time and legacy_last_time is not None:
        state["last_time"] = legacy_last_time

    if needs_first_run and "first_run" in legacy_state:
        state["first_run"] = legacy_state["first_run"]
    elif needs_first_run and legacy_last_time is not None:
        state["first_run"] = False


@app.on_poll()
def on_poll(
    params: OnPollParams, soar: SOARClient, asset: Asset
) -> Iterator[Union[Container, Artifact]]:
    """Ingest ServiceNow records as SOAR containers and optional IOC artifacts."""
    logger.info("Starting On Poll action")

    # Compile regex patterns
    uri_regexc = re.compile(URI_REGEX)
    hash_regexc = re.compile(HASH_REGEX)
    ip_regexc = re.compile(IP_REGEX)
    ipv6_regexc = re.compile(IPV6_REGEX)
    timezone_value = getattr(asset, "timezone", None)

    client = ServiceNowClient(asset)

    # Determine poll type before reading scheduled checkpoint state.
    is_manual_poll = params.is_manual_poll()
    if not is_manual_poll:
        migrate_legacy_ingest_state(asset)

    # Get ingest state (for tracking last poll time and first run)
    # The asset provides ingest_state which is a partition of the asset state
    # specifically for ingestion-related data like last_time
    state = asset.ingest_state
    last_time = state.get("last_time")
    last_sys_id = state.get(LAST_SYS_ID_FIELD)
    if last_sys_id:
        try:
            last_sys_id = validate_path_segment(LAST_SYS_ID_FIELD, last_sys_id)
        except ActionFailure:
            logger.warning(
                f"Invalid {LAST_SYS_ID_FIELD} value; falling back to legacy time checkpoint"
            )
            last_sys_id = None
    utc_checkpoint = state.get(UTC_CHECKPOINT_FIELD)
    using_utc_checkpoint = utc_checkpoint is not None

    if using_utc_checkpoint:
        last_time = _format_epoch_checkpoint(utc_checkpoint)
        if last_time is None:
            logger.warning(
                f"Invalid {UTC_CHECKPOINT_FIELD} value; falling back to legacy last_time"
            )
            using_utc_checkpoint = False
            last_time = state.get("last_time")

    # Legacy state may have stored last_time as epoch seconds.
    if last_time and isinstance(last_time, float):
        last_time = _format_utc_timestamp(last_time)

    if last_time:
        sanitized_last_time = _sanitize_checkpoint_time(last_time, timezone_value)
        if sanitized_last_time is None:
            state.pop("last_time", None)
        elif sanitized_last_time != last_time:
            state["last_time"] = sanitized_last_time
        last_time = sanitized_last_time

    scheduled_first_run = False

    custom_filter = asset.on_poll_filter
    query = _build_ordered_query(custom_filter)

    if is_manual_poll:
        # Manual polling (Poll Now) - use SDK's container_count parameter
        max_tickets = params.container_count
        if max_tickets is None:
            raise ActionFailure("container_count is required for Poll Now")
        logger.info(f"Poll Now (manual): fetching up to {max_tickets} tickets")

        # If start_time provided (epoch milliseconds), use it for filtering
        if params.start_time:
            start_time_str = _format_service_now_time(params.start_time / 1000.0)
            query = _build_ordered_query(
                custom_filter,
                _time_query_condition(">=", start_time_str),
            )
            logger.info(f"Using provided start_time: {start_time_str}")

        # If end_time provided (epoch milliseconds), add upper bound filter
        if params.end_time:
            end_time_str = _format_service_now_time(params.end_time / 1000.0)
            query = _build_ordered_query(
                custom_filter,
                _time_query_condition(">=", start_time_str)
                if params.start_time
                else None,
                _time_query_condition("<=", end_time_str),
            )
            logger.info(f"Using provided end_time: {end_time_str}")

    elif state.get("first_run", True):
        # First scheduled poll
        scheduled_first_run = True
        max_tickets = int(asset.first_run_container)
        logger.info(f"First run (scheduled): fetching up to {max_tickets} tickets")
    else:
        # Subsequent scheduled polls
        if last_time and len(last_time.split(" ")) == 2:
            query = _build_scheduled_query(
                custom_filter,
                last_time,
                last_sys_id,
                timezone_value,
                using_utc_checkpoint,
            )
            max_tickets = int(asset.max_container)
            logger.info(
                f"Scheduled poll: fetching up to {max_tickets} tickets updated after {last_time}"
            )
        else:
            # Fallback to first_run behavior if last_time is invalid
            logger.warning(
                "Invalid or missing last_time, falling back to first_run behavior"
            )
            max_tickets = int(asset.first_run_container)

    table_name = (
        asset.on_poll_table if asset.on_poll_table else SERVICENOW_DEFAULT_TABLE
    )
    table_name = table_name.lower()
    table_name = validate_path_segment("on_poll_table", table_name)
    endpoint = TABLE_ENDPOINT.format(table_name)

    params_dict = {"sysparm_query": query, "sysparm_exclude_reference_link": "true"}

    logger.info(f"Fetching issues from table: {table_name}")
    try:
        issues = client.paginator(endpoint, payload=params_dict, limit=max_tickets)
    except Exception as e:
        raise ActionFailure(f"Failed to fetch issues from ServiceNow: {e}") from e

    if not issues:
        logger.info("No issues found. Nothing to ingest.")
        if scheduled_first_run:
            state["first_run"] = False
        return

    logger.info(f"Retrieved {len(issues)} issues from ServiceNow")

    sanitized_issues = [_strip_format_controls(issue) for issue in issues]
    if not is_manual_poll:
        missing_sys_id = [
            issue for issue in sanitized_issues if not issue.get("sys_id")
        ]
        if missing_sys_id:
            raise ActionFailure(
                "ServiceNow returned a scheduled-poll record without sys_id; "
                "checkpoint was not advanced"
            )

    # Get or validate severity
    severity = _get_severity(soar, asset)

    # Process each issue and yield Container and Artifacts
    containers_created = 0
    artifacts_created = 0

    for sanitized_issue in sanitized_issues:
        sdi = sanitized_issue.get("sys_id")
        if not sdi:
            logger.warning("Issue missing sys_id, skipping")
            continue

        sd = sanitized_issue.get("short_description", "")
        desc = sanitized_issue.get("description", "")

        # Use default container name if short_description is empty
        if not sd:
            sd = "Phantom added container name (short description of the ticket/record found empty)"

        # Yield Container - the SDK will handle creation and duplicate detection via source_data_identifier
        logger.debug(f"Yielding container for issue {sdi}")
        yield Container(
            name=sd,
            description=desc,
            severity=severity,
            source_data_identifier=sdi,
            data=sanitized_issue,
        )
        containers_created += 1

        # Yield primary artifact - will be automatically associated with the container above
        logger.debug(f"Yielding primary artifact for issue {sdi}")
        yield Artifact(
            name=sanitized_issue.get("number", "Phantom added artifact name..."),
            description=sd,
            label="issue",
            severity=severity,
            source_data_identifier=sdi,
            cef=sanitized_issue,
            data=sanitized_issue,
        )
        artifacts_created += 1

        # Extract IPs if enabled
        if asset.extract_ips:
            for ticket_text in _ticket_text_values(sanitized_issue):
                # Extract IPv4 addresses
                for match in ip_regexc.finditer(ticket_text):
                    ip_address = _valid_ip_address(match.group(), 4)
                    if not ip_address:
                        continue

                    logger.debug(f"Yielding IPv4 artifact: {ip_address}")
                    yield Artifact(
                        label="IP Address",
                        cef={"ip_address": ip_address},
                        cef_types={"ip_address": ["ip"]},
                        source_data_identifier=sdi,
                    )
                    artifacts_created += 1

                # Extract IPv6 addresses
                for match in ipv6_regexc.finditer(ticket_text):
                    ipv6_address = _valid_ip_address(match.group(), 6)
                    if not ipv6_address:
                        continue

                    logger.debug(f"Yielding IPv6 artifact: {ipv6_address}")
                    yield Artifact(
                        label="IPV6 Address",
                        cef={"ipv6_address": ipv6_address},
                        cef_types={"ipv6_address": ["ip"]},
                        source_data_identifier=sdi,
                    )
                    artifacts_created += 1

        # Extract hashes if enabled
        if asset.extract_hashes:
            for ticket_text in _ticket_text_values(sanitized_issue):
                for match in hash_regexc.finditer(ticket_text):
                    logger.debug(f"Yielding hash artifact: {match.group()}")
                    yield Artifact(
                        label="Hash",
                        cef={"hash": match.group()},
                        cef_types={"hash": ["hash"]},
                        source_data_identifier=sdi,
                    )
                    artifacts_created += 1

        # Extract URLs if enabled
        if asset.extract_urls:
            for ticket_text in _ticket_text_values(sanitized_issue):
                for match in uri_regexc.finditer(ticket_text):
                    logger.debug(f"Yielding URL artifact: {match.group()}")
                    yield Artifact(
                        label="URL",
                        cef={"URL": match.group()},
                        cef_types={"URL": ["url"]},
                        source_data_identifier=sdi,
                    )
                    artifacts_created += 1

    logger.info(
        f"Yielded {containers_created} containers and {artifacts_created} artifacts"
    )

    # Preserve legacy behavior: scheduled polls advance the checkpoint;
    # manual polls do not modify scheduled poll state.
    if not is_manual_poll and issues:
        last_issue = sanitized_issues[-1]
        if "sys_updated_on" not in last_issue:
            raise Exception("No updated time in last ingested incident.")

        updated_time_utc = _sanitize_checkpoint_time(last_issue["sys_updated_on"])
        if updated_time_utc is None:
            raise Exception("Invalid updated time in last ingested incident.")

        utc_checkpoint = _parse_utc_checkpoint(updated_time_utc)
        if utc_checkpoint is None:
            raise Exception("Invalid updated time in last ingested incident.")
        state[UTC_CHECKPOINT_FIELD] = utc_checkpoint
        state[LAST_SYS_ID_FIELD] = last_issue["sys_id"]

        updated_time = updated_time_utc

        # Apply timezone conversion if configured
        if timezone_value:
            try:
                dt = datetime.strptime(
                    updated_time, SERVICENOW_DATETIME_FORMAT
                ).replace(tzinfo=timezone.utc)
                timezone_obj = _timezone_value(timezone_value)
                if timezone_obj:
                    updated_time = dt.astimezone(timezone_obj).strftime(
                        SERVICENOW_DATETIME_FORMAT
                    )
            except Exception as e:
                logger.warning(f"Failed to convert timezone: {e}")

        state["last_time"] = updated_time
        # State is automatically saved when using asset.ingest_state (it's an AssetState object)
        logger.info(f"Updated last_time to {updated_time}")

        # Ensure first_run is set to False
        if state.get("first_run", True):
            state["first_run"] = False
            # State changes are automatically persisted with AssetState

    logger.info("On Poll completed successfully")


def _get_severity(soar: SOARClient, asset: Asset) -> str:
    """Resolve the severity to apply to ingested containers and artifacts."""
    severities = _get_container_severities(soar)

    if asset.severity:
        severity = asset.severity.lower()
        _validate_custom_severity(severities, severity)
        return severity

    default_severity = _find_default_severity(severities)
    if not default_severity:
        logger.warning(
            "No default severity configured in SOAR platform and no severity specified in asset config. "
            "Using fallback severity 'medium'"
        )
        return "medium"

    return default_severity.lower()


def _get_container_severities(soar: SOARClient) -> list[dict[str, Any]]:
    """Fetch severity options without requiring system settings permissions."""
    response = soar.get("/rest/container_options").json()

    if not isinstance(response, dict):
        raise Exception(
            "Could not get severities from platform: unexpected container options response"
        )

    severities = response.get("severity")
    if severities is None and isinstance(response.get("data"), dict):
        severities = response["data"].get("severity")

    if not isinstance(severities, list):
        raise Exception(
            "Could not get severities from platform: severity options missing from container options"
        )

    return severities


def _validate_custom_severity(severities: list[dict[str, Any]], severity: str) -> None:
    """Validate that the configured severity exists in SOAR."""
    severity_names = [s.get("name", "").lower() for s in severities]
    if severity not in severity_names:
        raise Exception(f"Severity '{severity}' does not exist in SOAR platform")


def _find_default_severity(severities: list[dict[str, Any]]) -> Optional[str]:
    """Find the default severity configured in SOAR."""
    for sev in severities:
        if sev.get("is_default", False):
            return sev.get("name")

    return None
