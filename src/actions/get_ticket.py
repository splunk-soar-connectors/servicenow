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

"""Get Ticket Action"""

from pydantic import Field
from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger
from soar_sdk.exceptions import ActionFailure

from ..app import app, Asset
from ..helpers import ServiceNowClient, validate_path_segment
from ..consts import (
    SERVICENOW_TICKET_ID_MESSAGE,
    SERVICENOW_INVALID_PARAMETER_MESSAGE,
    TicketNotFoundException,
)

logger = getLogger()

"""
GetTicketOutput is permissive to preserve the legacy raw ServiceNow record passthrough, including custom u_* fields and unlisted columns.
"""


class GetTicketParams(Params):
    table: str = Param(
        description="Table to query",
        required=False,
        primary=True,
        default="incident",
        cef_types=["servicenow table"],
    )
    id: str = Param(
        description="SYS ID or ticket number of a record",
        primary=True,
        cef_types=["servicenow ticket sysid", "servicenow ticket number"],
    )
    is_sys_id: bool = Param(
        description="Whether the value provided in the ID parameter is SYS ID or ticket number",
        required=False,
    )


class AttachmentDetailsOutput(PermissiveActionOutput):
    average_image_color: str | None = None
    chunk_size_bytes: str | None = OutputField(example_values=["734003"])
    compressed: str | None = None
    content_type: str | None = None
    download_link: str | None = None
    file_name: str | None = None
    hash: str | None = None
    image_height: str | None = None
    image_width: str | None = None
    size_bytes: str | None = None
    size_compressed: str | None = None
    state: str | None = OutputField(example_values=["available"])
    sys_created_by: str | None = None
    sys_created_on: str | None = None
    sys_id: str | None = None
    sys_mod_count: str | None = None
    sys_tags: str | None = None
    sys_updated_by: str | None = None
    sys_updated_on: str | None = None
    table_name: str | None = None
    table_sys_id: str | None = None


class GetTicketOutput(PermissiveActionOutput):
    """ServiceNow ticket/record details"""

    # Primary fields for table display - order matters for rendering
    number: str | None = OutputField(
        column_name="TICKET NUMBER",
        cef_types=["servicenow ticket number"],
        example_values=["INC0000001"],
    )
    description: str | None = OutputField(
        column_name="DESCRIPTION",
        example_values=["User can't access email on mail.company.com.<br>\t\t"],
    )
    short_description: str | None = OutputField(
        column_name="SHORT DESCRIPTION",
        example_values=["phapp_servicenow_update, Run file reputation actions only"],
    )
    sys_id: str | None = OutputField(
        column_name="ID",
        cef_types=["servicenow ticket sysid", "md5"],
    )
    severity: str | None = OutputField(column_name="SEVERITY", example_values=["1"])
    priority: str | None = OutputField(column_name="PRIORITY", example_values=["1"])
    opened_at: str | None = OutputField(
        column_name="OPENED ON", example_values=["2018-02-07 23:09:51"]
    )
    closed_at: str | None = OutputField(
        column_name="CLOSED ON", example_values=["2018-02-08 23:10:06"]
    )

    # All other fields in alphabetical order
    acquisition_method: str | None = None
    active: str | None = OutputField(example_values=["false"])
    activity_due: str | None = None
    additional_assignee_list: str | None = None
    approval: str | None = None
    approval_history: str | None = None
    approval_set: str | None = None
    asset_tag: str | None = None
    asset_tracking_strategy: str | None = OutputField(
        example_values=["leave_to_category"]
    )
    assigned: str | None = None
    assigned_condition: str | None = None
    attachment_details: list[AttachmentDetailsOutput] = Field(default_factory=list)
    barcode: str | None = OutputField(example_values=["G73SW-XN2"])
    beneficiary: str | None = None
    bundle: str | None = OutputField(example_values=["false"])
    business_duration: str | None = OutputField(example_values=["1970-01-22 21:46:21"])
    business_stc: str | None = OutputField(example_values=["1892781"])
    calendar_duration: str | None = OutputField(example_values=["1970-04-02 20:46:21"])
    calendar_stc: str | None = OutputField(example_values=["7937181"])
    category: str | None = OutputField(example_values=["network"])
    caused_by: str | None = None
    certified: str | None = OutputField(example_values=["false"])
    checked_in: str | None = None
    checked_out: str | None = None
    child_incidents: str | None = None
    close_code: str | None = OutputField(example_values=["Closed/Resolved by Caller"])
    close_notes: str | None = OutputField(
        example_values=["Closed before close notes were made mandatory<br>\t\t"]
    )
    cmdb_ci_class: str | None = None
    cmdb_model_category: str | None = None
    comments: str | None = None
    comments_and_work_notes: str | None = None
    contact_type: str | None = None
    correlation_display: str | None = None
    correlation_id: str | None = None
    cost: str | None = OutputField(example_values=["0"])
    delivery_date: str | None = None
    delivery_plan: str | None = None
    delivery_task: str | None = None
    depreciated_amount: str | None = OutputField(example_values=["0"])
    depreciation_date: str | None = None
    display_name: str | None = None
    disposal_reason: str | None = None
    due: str | None = None
    due_date: str | None = None
    due_in: str | None = None
    entitlement_condition: str | None = None
    escalation: str | None = OutputField(example_values=["0"])
    expected_start: str | None = None
    expenditure_type: str | None = None
    flow_rate: str | None = None
    follow_up: str | None = None
    full_name: str | None = None
    gl_account: str | None = None
    group_list: str | None = None
    hold_reason: str | None = None
    impact: str | None = OutputField(example_values=["1"])
    incident_state: str | None = OutputField(example_values=["7"])
    install_date: str | None = None
    install_status: str | None = OutputField(example_values=["1"])
    invoice_number: str | None = None
    is_merged_license: str | None = OutputField(example_values=["false"])
    justification: str | None = None
    knowledge: str | None = OutputField(example_values=["false"])
    lease_id: str | None = None
    license_key: str | None = None
    made_sla: str | None = OutputField(example_values=["false"])
    main_component: str | None = None
    managed_by: str | None = None
    merged_into: str | None = None
    model_number: str | None = OutputField(example_values=["G73SW-XN2"])
    name: str | None = OutputField(example_values=["G Series"])
    notify: str | None = OutputField(example_values=["1"])
    old_status: str | None = None
    old_substatus: str | None = None
    order: str | None = None
    order_date: str | None = None
    owned_by: str | None = None
    owner: str | None = None
    parent: str | None = None
    parent_incident: str | None = None
    picture: str | None = None
    po_number: str | None = None
    power_consumption: str | None = None
    pre_allocated: str | None = OutputField(example_values=["false"])
    purchase_date: str | None = None
    quantity: str | None = OutputField(example_values=["1"])
    rack_units: str | None = OutputField(example_values=["1"])
    reassignment_count: str | None = OutputField(example_values=["1"])
    reopen_count: str | None = None
    reopened_by: str | None = None
    reopened_time: str | None = None
    request_line: str | None = None
    resale_price: str | None = OutputField(example_values=["0"])
    reserved_for: str | None = None
    residual: str | None = OutputField(example_values=["0"])
    residual_date: str | None = None
    resolved_at: str | None = OutputField(example_values=["2018-05-10 19:56:12"])
    retired: str | None = None
    retirement_date: str | None = None
    rfc: str | None = None
    rights: str | None = OutputField(example_values=["600"])
    salvage_value: str | None = OutputField(example_values=["0"])
    serial_number: str | None = None
    service_offering: str | None = None
    skip_sync: str | None = OutputField(example_values=["false"])
    sla: str | None = None
    sla_due: str | None = None
    sound_power: str | None = None
    state: str | None = OutputField(example_values=["7"])
    status: str | None = OutputField(example_values=["In Production"])
    subcategory: str | None = None
    substatus: str | None = None
    support_group: str | None = None
    supported_by: str | None = None
    sys_class_name: str | None = OutputField(example_values=["incident"])
    sys_created_by: str | None = OutputField(example_values=["pat"])
    sys_created_on: str | None = OutputField(example_values=["2016-09-08 18:24:13"])
    sys_domain_path: str | None = OutputField(
        cef_types=["domain"], example_values=["/"]
    )
    sys_mod_count: str | None = OutputField(example_values=["22"])
    sys_tags: str | None = None
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2018-11-21 05:51:32"])
    time_worked: str | None = None
    type: str | None = OutputField(example_values=["Generic"])
    u_short_description: str | None = None
    upon_approval: str | None = None
    upon_reject: str | None = None
    urgency: str | None = OutputField(example_values=["1"])
    user_input: str | None = None
    warranty_expiration: str | None = None
    watch_list: str | None = None
    weight: str | None = None
    work_end: str | None = None
    work_notes: str | None = None
    work_notes_list: str | None = None
    work_start: str | None = None
    # Fields not in manifest but added by legacy implementation for compatibility
    comments_section: list[str] = Field(default_factory=list)
    worknotes_section: list[str] = Field(default_factory=list)


class GetTicketSummary(ActionOutput):
    """Summary for get ticket action"""

    queried_ticket_id: str = OutputField(
        cef_types=["servicenow ticket sysid", "md5"],
    )


@app.action(
    description="Get ticket/record information",
    action_type="investigate",
    render_as="table",
    verbose="If the <b>table</b> value is not specified, the action defaults to the <b>incident</b>. Users can provide a valid ticket number in the 'id' parameter or check the 'is_sys_id' parameter and provide a valid <b>SYS ID</b> in the 'id' parameter. Users can get the <b>SYS ID</b> value for any ticket from the results of the <b>List Tickets</b> action run.",
    summary_type=GetTicketSummary,
)
def get_ticket(
    params: GetTicketParams, soar: SOARClient[GetTicketSummary], asset: Asset
) -> GetTicketOutput:
    """Get a ServiceNow record with attachments, comments, and work notes."""
    table_name = validate_path_segment("table", params.table)
    ticket_id = params.id
    is_sys_id = params.is_sys_id or False

    logger.info(
        f"Getting ticket from table '{table_name}', id='{ticket_id}', is_sys_id={is_sys_id}"
    )

    client = ServiceNowClient(asset)

    sys_id = ticket_id
    if not is_sys_id:
        try:
            sys_id = client.get_sys_id_from_ticket_number(
                table_name=table_name,
                ticket_number=ticket_id,
            )
        except TicketNotFoundException:
            # Ticket not found - use legacy error message
            raise ActionFailure(SERVICENOW_TICKET_ID_MESSAGE) from None
        # Other exceptions (ActionFailure for auth/network errors) propagate naturally

    # Get the main ticket details
    logger.debug(
        f"Fetching ticket details for sys_id '{sys_id}' from table '{table_name}'"
    )
    sys_id = validate_path_segment("sys_id", sys_id)
    endpoint = f"/table/{table_name}/{sys_id}"
    response = client.make_rest_call(endpoint=endpoint)

    if not response.get("result"):
        # Use legacy error message for invalid/missing ticket
        raise ActionFailure(SERVICENOW_INVALID_PARAMETER_MESSAGE)

    ticket = response["result"]
    ticket_sys_id = ticket.get("sys_id")
    logger.info(f"Successfully retrieved ticket {ticket.get('number', sys_id)}")

    # Get attachment details
    logger.debug(f"Fetching attachments for ticket sys_id '{ticket_sys_id}'")
    attachment_params = {"sysparm_query": f"table_sys_id={ticket_sys_id}"}
    try:
        attach_response = client.make_rest_call(
            endpoint="/attachment",
            params=attachment_params,
        )

        if attach_response.get("result"):
            attachment_count = len(attach_response["result"])
            ticket["attachment_details"] = attach_response["result"]
            logger.debug(f"Retrieved {attachment_count} attachment(s)")
        else:
            logger.debug("No attachments found for this ticket")
    except Exception as e:
        # Some versions of ServiceNow may fail the attachment query if not present
        # This is not a fatal error, so we just skip it
        logger.warning(f"Failed to retrieve attachments: {e!s}")

    # Get comments and work notes from sys_journal_field
    # Note: The legacy action fetches these, but they may already be in the
    # ticket data via the comments, work_notes, and comments_and_work_notes fields
    # Legacy behavior: if this call fails, log warning and continue (don't fail the action)
    logger.debug("Fetching journal field entries (comments and work notes)")
    journal_params = {
        "element_id": sys_id,
        "sysparm_query": "element=comments^ORelement=work_notes",
    }

    comments_section = []
    worknotes_section = []
    journal_response = {}

    try:
        journal_response = client.make_rest_call(
            endpoint="/table/sys_journal_field",
            params=journal_params,
        )

    except Exception as e:
        # Match legacy behavior: log the error but don't fail the action
        logger.warning(
            f"Unable to fetch comments and work_notes for ticket sys_id '{ticket_sys_id}'. Error: {e}"
        )
        # Process journal entries into comments_section and worknotes_section arrays
        # This matches legacy behavior even though these fields are not in the manifest
    if journal_response.get("result"):
        for item in journal_response.get("result", []):
            if item.get("element") == "comments":
                comments_section.append(item.get("value", ""))
            elif item.get("element") == "work_notes":
                worknotes_section.append(item.get("value", ""))

        journal_count = len(journal_response["result"])
        logger.debug(
            f"Retrieved {journal_count} journal entries ({len(comments_section)} comments, {len(worknotes_section)} work notes)"
        )
    else:
        logger.debug("No journal entries found")

    # Add the processed journal entries to the ticket (may be empty if fetch failed)
    ticket["comments_section"] = comments_section
    ticket["worknotes_section"] = worknotes_section

    ticket_number = ticket.get("number", ticket_sys_id)
    soar.set_summary(GetTicketSummary(queried_ticket_id=ticket_sys_id))
    soar.set_message(f"Successfully retrieved ticket {ticket_number}")

    logger.info(f"Successfully completed get_ticket for {ticket_number}")

    return GetTicketOutput(**ticket)
