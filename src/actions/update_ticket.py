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

"""Update Ticket Action"""

from pydantic import Field
from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger
from soar_sdk.exceptions import ActionFailure

from ..app import app, Asset
from ..consts import TICKET_ENDPOINT
from ..helpers import (
    ServiceNowActionHelper,
    ServiceNowClient,
    parse_fields_json,
    validate_path_segment,
)

logger = getLogger()


class UpdateTicketParams(Params):
    table: str = Param(
        description="Ticket table",
        required=False,
        primary=True,
        default="incident",
        cef_types=["servicenow table"],
    )
    vault_id: str = Param(
        description="To attach a file to a ticket, the file must first be in the vault. When the vault ID of a file is provided, it is uploaded and attached to the ticket (Comma-delimited)",
        required=False,
        primary=True,
        cef_types=["vault id"],
    )
    id: str = Param(
        description="SYS ID or ticket number of a record",
        primary=True,
        cef_types=["servicenow ticket sysid", "servicenow ticket number"],
    )
    fields: str = Param(description="JSON containing field values", required=False)
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


class UpdateTicketOutput(PermissiveActionOutput):
    """Output structure for update_ticket action"""

    # Primary fields for table display - order matters for rendering
    number: str | None = OutputField(
        column_name="TICKET NUMBER",
        cef_types=["servicenow ticket number"],
        example_values=["INC0000001"],
    )
    short_description: str | None = OutputField(
        column_name="SHORT DESCRIPTION",
        example_values=["phapp_servicenow_update, Run file reputation actions only"],
    )
    description: str | None = OutputField(
        column_name="DESCRIPTION",
        example_values=["User can't access email on mail.company.com.<br>\t\t"],
    )
    state: str | None = OutputField(column_name="STATE", example_values=["7"])
    priority: str | None = OutputField(column_name="PRIORITY", example_values=["1"])
    severity: str | None = OutputField(column_name="SEVERITY", example_values=["1"])
    category: str | None = OutputField(
        column_name="CATEGORY", example_values=["network"]
    )
    sys_id: str | None = OutputField(
        column_name="SYS ID",
        cef_types=["servicenow ticket sysid", "md5"],
    )
    opened_at: str | None = OutputField(
        column_name="OPENED AT", example_values=["2018-02-07 23:09:51"]
    )
    closed_at: str | None = OutputField(
        column_name="CLOSED AT", example_values=["2018-02-08 23:10:06"]
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
    assigned: str | None = None
    attachment_details: list[AttachmentDetailsOutput] = Field(default_factory=list)
    beneficiary: str | None = None
    business_duration: str | None = OutputField(example_values=["1970-01-22 21:46:21"])
    business_stc: str | None = OutputField(example_values=["1892781"])
    calendar_duration: str | None = OutputField(example_values=["1970-04-02 20:46:21"])
    calendar_stc: str | None = OutputField(example_values=["7937181"])
    caused_by: str | None = None
    checked_in: str | None = None
    checked_out: str | None = None
    child_incidents: str | None = None
    close_code: str | None = OutputField(example_values=["Closed/Resolved by Caller"])
    close_notes: str | None = OutputField(
        example_values=["Closed before close notes were made mandatory<br>\t\t"]
    )
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
    escalation: str | None = OutputField(example_values=["0"])
    expected_start: str | None = None
    expenditure_type: str | None = None
    follow_up: str | None = None
    gl_account: str | None = None
    group_list: str | None = None
    hold_reason: str | None = None
    impact: str | None = OutputField(example_values=["1"])
    incident_state: str | None = OutputField(example_values=["7"])
    install_date: str | None = None
    install_status: str | None = OutputField(example_values=["1"])
    invoice_number: str | None = None
    justification: str | None = None
    knowledge: str | None = OutputField(example_values=["false"])
    lease_id: str | None = None
    made_sla: str | None = OutputField(example_values=["false"])
    managed_by: str | None = None
    notify: str | None = OutputField(example_values=["1"])
    old_status: str | None = None
    old_substatus: str | None = None
    order: str | None = None
    order_date: str | None = None
    parent: str | None = None
    parent_incident: str | None = None
    po_number: str | None = None
    pre_allocated: str | None = OutputField(example_values=["false"])
    purchase_date: str | None = None
    quantity: str | None = OutputField(example_values=["1"])
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
    salvage_value: str | None = OutputField(example_values=["0"])
    serial_number: str | None = None
    service_offering: str | None = None
    skip_sync: str | None = OutputField(example_values=["false"])
    sla_due: str | None = None
    stockroom: str | None = None
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
    u_short_description: str | None = None
    upon_approval: str | None = None
    upon_reject: str | None = None
    urgency: str | None = OutputField(example_values=["1"])
    user_input: str | None = None
    warranty_expiration: str | None = None
    watch_list: str | None = None
    work_end: str | None = None
    work_notes: str | None = None
    work_notes_list: str | None = None
    work_start: str | None = None


class UpdateTicketSummary(ActionOutput):
    """Summary for update ticket action"""

    fields_updated: bool = OutputField(example_values=[True, False])
    successfully_added_attachments_count: int | None = OutputField(
        example_values=[1, 2, 3]
    )
    vault_failure_details: str | None = OutputField(
        example_values=["Invalid Vault ID: vault_id_1, vault_id_2"]
    )


@app.action(
    description="Update ticket/record information",
    action_type="generic",
    read_only=False,
    render_as="table",
    verbose='Update an already existing ticket with the values that are specified in the <b>fields</b> parameter. The user has to know the key names to set in this parameter. Study the results of the <b>get ticket</b> action to get more info about all the properties that can be updated. The JSON that is specified in the \'fields\' parameter should have the keys and values specified in double-quotes string format, except in case of boolean values, which should be either <i>True</i> or <i>False</i> (without any single quotes); for example: {\\"short_description\\": \\"Zeus, multiple actions need to be taken\\", \\"made_sla\\": False}<br><br>The action first attempts to update the ticket with the values in <b>fields</b>. If this call is successful, it continues to attach the file specified in <b>vault_id</b>. These are two separate calls made to ServiceNow.<br><br>ServiceNow restricts the upload time and the file size of attached files, which may cause file uploads (of attachments) to fail. These values can be configured by an admin on the ServiceNow device. As of this writing, please go to <a href=\\"https://support.servicenow.com/kb?id=kb_article_view&sysparm_article=KB0718101\\" target=\\"_blank\\">this link</a> on the ServiceNow Website for more information.<br><br>For updating the timeout for attaching the file please go to <b>System Definition</b>-><b>Transaction Quota Rules</b>. Update the <b>maximum duration</b> field as per your requirement in <b>REST Attachment API request timeout</b> or/and <b>REST and JSON Catch ALL</b> rule. The <b>REST Attachment API request timeout</b> rule applies to all incoming attachment requests. Any request exceeding the maximum duration set here will be cancelled and the <b>REST and JSON Catch All</b> rule will be used for all REST transactions.<br><br>If the <b>table</b> value is not specified, the action defaults to the <b>incident</b>.<br><br>ServiceNow does not return an error if an invalid field is updated, or if a valid field is updated in an invalid manner (e.g: updating the <i>caller_id</i> dictionary with your dictionary). For the best results, please check the results of the action in the JSON view to verify the changes. Users can provide a valid ticket number in the \'id\' parameter or check the \'is_sys_id\' parameter and provide a valid <b>SYS ID</b> in the \'id\' parameter. Users can get the <b>SYS ID</b> value for any ticket from the results of the <b>List Tickets</b> action run.<br><br>If the <b>short_description</b> action parameter is added as a key in the <b>fields</b> parameter then users can provide new line(\\n), tab(\\t), single quote(\\\'), double quote(\\\\"), alarm or beep(\\a) and backspace(\\b) as escape sequences in the value. Similarly if the <b>description</b> action parameter is added as a key in <b>fields</b> parameter, then new line(\\n, \\r), tab(\\t), single quote(\\\'), double quote(\\\\"), alarm or beep(\\a) and backspace(\\b) can be provided as escape sequences.',
    summary_type=UpdateTicketSummary,
)
def update_ticket(
    params: UpdateTicketParams, soar: SOARClient[UpdateTicketSummary], asset: Asset
) -> UpdateTicketOutput:
    """
    Update an existing ticket in ServiceNow
    """
    logger.info("Starting update_ticket action")

    # Initialize helper
    helper = ServiceNowClient(asset)

    table = validate_path_segment("table", params.table)
    ticket_id = params.id
    is_sys_id = params.is_sys_id if params.is_sys_id is not None else False

    # If not sys_id, convert ticket number to sys_id
    if not is_sys_id:
        logger.info(f"Converting ticket number to sys_id: {ticket_id}")
        ticket_id = helper.get_sys_id_from_ticket_number(
            table_name=table,
            ticket_number=ticket_id,
        )

    # Parse fields parameter if provided
    fields = parse_fields_json(params.fields)

    # Validate that at least one parameter is provided
    if not fields and not params.vault_id:
        raise ActionFailure(
            "Please specify at least one of: fields or vault_id parameter"
        )

    # Build the endpoint for updating ticket
    ticket_id = validate_path_segment("sys_id", ticket_id)
    endpoint = TICKET_ENDPOINT.format(table, ticket_id)

    result = {}
    fields_updated = bool(fields)
    successfully_added_attachments_count = None
    vault_failure_details = None

    # Update ticket with fields if provided
    if fields:
        logger.info("Updating ticket with the provided fields")
        try:
            response = helper.make_rest_call(
                endpoint,
                data=fields,
                method="put",
            )
        except Exception as e:
            logger.error(f"Failed to update ticket: {e}")
            raise ActionFailure(f"Failed to update ticket: {e}") from e

        # Validate response
        if not response.get("result"):
            raise ActionFailure("Invalid response from ServiceNow - no result data")

        result.update(response.get("result", {}))
        logger.info(f"Ticket updated successfully with sys_id: {ticket_id}")
        soar.set_message("Ticket updated successfully")

    # Handle vault attachments if provided
    if params.vault_id:
        logger.info("Processing vault attachments")
        action_helper = ServiceNowActionHelper(soar, helper)
        attachment_details, vault_errors = action_helper.handle_vault_attachments(
            table, ticket_id, params.vault_id
        )
        successfully_added_attachments_count = len(attachment_details)

        # Add attachment details to result if successful
        if attachment_details:
            result["attachment_details"] = attachment_details

        # Handle attachment failures - always fail to match legacy behavior
        if vault_errors:
            vault_failure_details = "; ".join(
                [f"{vid}: {err}" for vid, err in vault_errors.items()]
            )
            if fields:
                # Set message indicating partial success before failing
                soar.set_message(
                    "Successfully updated the ticket, but failed to add attachment(s)"
                )
            soar.set_summary(
                UpdateTicketSummary(
                    fields_updated=fields_updated,
                    successfully_added_attachments_count=successfully_added_attachments_count,
                    vault_failure_details=vault_failure_details,
                )
            )
            # Always raise exception when attachments fail (matches legacy behavior)
            raise ActionFailure(f"Failed to attach files. Errors: {vault_failure_details}")

    soar.set_summary(
        UpdateTicketSummary(
            fields_updated=fields_updated,
            successfully_added_attachments_count=successfully_added_attachments_count,
            vault_failure_details=vault_failure_details,
        )
    )

    # Convert result to output model
    return UpdateTicketOutput(**result)
