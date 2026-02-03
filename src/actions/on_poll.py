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

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
from collections.abc import Iterator

from soar_sdk.abstract import SOARClient
from soar_sdk.params import OnPollParams
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import TABLE_ENDPOINT
from ..helpers import ServiceNowClient

logger = getLogger()

# Regex patterns for artifact extraction
URI_REGEX = (
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)
HASH_REGEX = r"\b[0-9a-fA-F]{32}\b|\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{64}\b"
IP_REGEX = r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
IPV6_REGEX = "\\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|"
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
    "[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:)))(%.+)?\\s*"
)

SERVICENOW_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
SERVICENOW_DEFAULT_TABLE = "incident"


def _format_local_timestamp(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .astimezone()
        .strftime(SERVICENOW_DATETIME_FORMAT)
    )


def migrate_legacy_ingest_state(asset: Asset) -> None:
    """Seed SDK ingest state from legacy flat connector state after upgrade."""
    state = asset.ingest_state

    needs_last_time = "last_time" not in state
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


# TODO: duplication container handling.

"""
Does the SDK automatically dedupe containers by source_data_identifier (and/or label)? The docs dont state it explicitly; if it doesnt, duplicates are likely with inclusive time filters.
Are start_time/end_time populated for scheduled polls in your environment? If so, ignoring them can cause overlap or gaps.
"""


# TODO:
@app.on_poll()
def on_poll(
    params: OnPollParams, soar: SOARClient, asset: Asset
) -> Iterator[Union[Container, Artifact]]:
    """
    Scheduled and manual ingestion of ServiceNow records into Splunk SOAR containers.

    Fetches tickets/records from ServiceNow, creates containers, and extracts artifacts
    including optional IOCs (IPs, hashes, URLs).

    Yields Container and Artifact objects. The SDK handles creation automatically.
    When a Container is yielded first, subsequent Artifacts without a container_id
    will be automatically associated with that container.
    """
    logger.info("Starting On Poll action")

    # Compile regex patterns
    uri_regexc = re.compile(URI_REGEX)
    hash_regexc = re.compile(HASH_REGEX)
    ip_regexc = re.compile(IP_REGEX)
    ipv6_regexc = re.compile(IPV6_REGEX)

    # Initialize helper
    helper = ServiceNowClient(asset)

    # Determine poll type before reading scheduled checkpoint state.
    is_manual_poll = params.is_manual_poll()
    if not is_manual_poll:
        migrate_legacy_ingest_state(asset)

    # Get ingest state (for tracking last poll time and first run)
    # The asset provides ingest_state which is a partition of the asset state
    # specifically for ingestion-related data like last_time
    state = asset.ingest_state
    last_time = state.get("last_time")

    # TODO: check when it will be float and if we can always have it in one way.
    # Convert last_time from float to datetime string if needed
    if last_time and isinstance(last_time, float):
        last_time = _format_local_timestamp(last_time)

    # Build base query
    query = "ORDERBYsys_updated_on"

    # Add custom filter from asset config if present
    custom_filter = asset.on_poll_filter
    if custom_filter:
        query += f"^{custom_filter}"

    if is_manual_poll:
        # Manual polling (Poll Now) - use SDK's container_count parameter
        max_tickets = params.container_count
        if (
            max_tickets is None
        ):  # TODO: test this and see if error returned is as expected.
            raise ValueError("container_count is required for Poll Now")
        logger.info(f"Poll Now (manual): fetching up to {max_tickets} tickets")

        # If start_time provided (epoch milliseconds), use it for filtering
        if params.start_time:
            start_time_str = _format_local_timestamp(params.start_time / 1000.0)
            query_prefix = start_time_str.split(" ")
            query += f"^sys_updated_on>=javascript:gs.dateGenerate('{query_prefix[0]}','{query_prefix[1]}')"
            logger.info(f"Using provided start_time: {start_time_str}")

        # If end_time provided (epoch milliseconds), add upper bound filter
        if params.end_time:
            end_time_str = _format_local_timestamp(params.end_time / 1000.0)
            query_prefix = end_time_str.split(" ")
            query += f"^sys_updated_on<=javascript:gs.dateGenerate('{query_prefix[0]}','{query_prefix[1]}')"
            logger.info(f"Using provided end_time: {end_time_str}")

    elif state.get("first_run", True):
        # First scheduled poll
        state["first_run"] = (
            False  # TODO: check if this should be set after successful first run instead?
        )
        max_tickets = int(asset.first_run_container)
        logger.info(f"First run (scheduled): fetching up to {max_tickets} tickets")
    else:
        # Subsequent scheduled polls
        if last_time and len(last_time.split(" ")) == 2:
            # Add time-based filter from state
            query_prefix = last_time.split(" ")
            query += f"^sys_updated_on>=javascript:gs.dateGenerate('{query_prefix[0]}','{query_prefix[1]}')"
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

    # Get table name
    table_name = (
        asset.on_poll_table if asset.on_poll_table else SERVICENOW_DEFAULT_TABLE
    )
    endpoint = TABLE_ENDPOINT.format(table_name)

    # Build query parameters
    params_dict = {"sysparm_query": query, "sysparm_exclude_reference_link": "true"}

    # Fetch issues using paginator
    logger.info(f"Fetching issues from table: {table_name}")
    try:
        issues = helper.paginator(endpoint, payload=params_dict, limit=max_tickets)
    except Exception as e:
        logger.error(f"Error fetching issues: {e}")
        raise Exception(
            f"Failed to fetch issues from ServiceNow: {e}"
        ) from e  # TODO: check if this is right way of raising exceptions

    if not issues:
        logger.info("No issues found. Nothing to ingest.")
        return

    logger.info(f"Retrieved {len(issues)} issues from ServiceNow")

    # Get or validate severity
    severity = _get_severity(soar, asset)

    # Process each issue and yield Container and Artifacts
    containers_created = 0
    artifacts_created = 0

    for issue in issues:
        sdi = issue.get("sys_id")
        if not sdi:
            logger.warning("Issue missing sys_id, skipping")
            continue

        sd = issue.get("short_description", "")
        desc = issue.get("description", "")

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
            data=issue,
        )
        containers_created += 1

        # Yield primary artifact - will be automatically associated with the container above
        logger.debug(f"Yielding primary artifact for issue {sdi}")
        yield Artifact(
            name=issue.get("number", "Phantom added artifact name..."),
            description=sd,
            label="issue",
            severity=severity,
            source_data_identifier=sdi,
            cef=issue,
            data=issue,
        )
        artifacts_created += 1

        # Extract IPs if enabled
        if asset.extract_ips:
            # Extract IPv4 addresses
            for match in ip_regexc.finditer(str(issue)):
                logger.debug(f"Yielding IPv4 artifact: {match.group()}")
                yield Artifact(
                    label="IP Address",
                    cef={"ip_address": match.group()},
                    source_data_identifier=sdi,
                )
                artifacts_created += 1

            # Extract IPv6 addresses
            for match in ipv6_regexc.finditer(str(issue)):
                logger.debug(f"Yielding IPv6 artifact: {match.group()}")
                yield Artifact(
                    label="IPV6 Address", cef={"ipv6_address": match.group()}
                )
                artifacts_created += 1

        # Extract hashes if enabled
        if asset.extract_hashes:
            for match in hash_regexc.finditer(str(issue)):
                logger.debug(f"Yielding hash artifact: {match.group()}")
                yield Artifact(label="Hash", cef={"hash": match.group()})
                artifacts_created += 1

        # Extract URLs if enabled
        if asset.extract_urls:
            for match in uri_regexc.finditer(str(issue)):
                logger.debug(f"Yielding URL artifact: {match.group()}")
                yield Artifact(label="URL", cef={"URL": match.group()})
                artifacts_created += 1

    # TODO: container and artifact count total is generic. Either map container -> artifact count or just log containe count.
    logger.info(
        f"Yielded {containers_created} containers and {artifacts_created} artifacts"
    )

    # Update state for scheduled polling only (not for manual polls)
    if not is_manual_poll and issues:
        # TODO: check if we should update state even for manual polls. (might not make sense since we wanna force stuff)
        # also check servicenow api ensures issues are in order all the time.
        if "sys_updated_on" not in issues[-1]:
            raise Exception("No updated time in last ingested incident.")

        updated_time = issues[-1]["sys_updated_on"]

        # Apply timezone conversion if configured
        if asset.timezone:
            try:
                dt = datetime.strptime(
                    updated_time, SERVICENOW_DATETIME_FORMAT
                ).replace(tzinfo=asset.timezone)
                utc_offset = dt.utcoffset() or timedelta(0)
                new_dt = dt + utc_offset
                updated_time = new_dt.strftime(SERVICENOW_DATETIME_FORMAT)
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
    """
    Get severity for containers and artifacts

    Args:
        soar: SOAR client
        asset: Asset configuration

    Returns:
        Severity string

    Raises:
        Exception: If severity validation fails
    """
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
    """
    Fetch severity options through container options.

    The /rest/container_options endpoint exposes severities without requiring
    system_settings view permissions.
    """
    try:
        response = soar.get("/rest/container_options").json()
    except Exception as e:
        logger.error(f"Failed to get container options from platform: {e}")
        raise

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
    """
    Validate that the custom severity exists in the SOAR platform

    Args:
        severities: Severity options from the SOAR platform
        severity: Severity to validate

    Raises:
        Exception: If severity doesn't exist
    """
    severity_names = [s.get("name", "").lower() for s in severities]
    if severity not in severity_names:
        raise Exception(f"Severity '{severity}' does not exist in SOAR platform")


def _find_default_severity(severities: list[dict[str, Any]]) -> Optional[str]:
    """
    Find the default severity configured in the SOAR platform

    Args:
        severities: Severity options from the SOAR platform

    Returns:
        Default severity name or None if not found
    """
    for sev in severities:
        if sev.get("is_default", False):
            return sev.get("name")

    return None
