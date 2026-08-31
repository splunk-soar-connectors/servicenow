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

"""Create Ticket Action"""

from pydantic import Field
from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import (
    ActionOutput,
    ActionResult,
    OutputField,
    PermissiveActionOutput,
)
from soar_sdk.logging import getLogger
from soar_sdk.exceptions import ActionFailure

from ..app import app, Asset
from ..consts import TABLE_ENDPOINT
from ..helpers import (
    build_failed_attachment_result,
    build_legacy_vault_failure_details,
    ServiceNowActionHelper,
    parse_fields_json,
    validate_path_segment,
)
from ..servicenow_client import ServiceNowClient

logger = getLogger()


class CreateTicketParams(Params):
    short_description: str = Param(
        description="Ticket short description", required=False
    )
    table: str = Param(
        description="Table to add to",
        required=False,
        primary=True,
        default="incident",
        cef_types=["servicenow table"],
    )
    vault_id: str = Param(
        description="To attach a file to a ticket, the file must first be in the vault. When the Vault ID of a file is provided, it is uploaded and attached to the ticket (Comma-delimited)",
        required=False,
        primary=True,
        cef_types=["vault id"],
    )
    description: str = Param(description="Ticket description", required=False)
    fields: str = Param(description="JSON containing field values", required=False)


class AttachmentDetailsOutput(PermissiveActionOutput):
    average_image_color: str | None = None
    chunk_size_bytes: str | None = OutputField(example_values=["734003"])
    compressed: str | None = None
    content_type: str | None = None
    download_link: str | None = OutputField(cef_types=["url"])
    file_name: str | None = OutputField(cef_types=["file name"])
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


class CreateTicketSummary(ActionOutput):
    """Summary for create ticket action"""

    created_ticket_id: str = OutputField(
        cef_types=["servicenow ticket sysid", "md5"],
    )
    successfully_added_attachments_count: int | None = OutputField(
        example_values=[1, 2, 3]
    )
    vault_failure_details: str | None = OutputField(
        example_values=["Invalid Vault ID: vault_id_1, vault_id_2"]
    )


class CreateTicketOutput(PermissiveActionOutput):
    number: str | None = OutputField(
        column_name="TICKET NUMBER",
        cef_types=["servicenow ticket number"],
        example_values=["INC0000001"],
    )
    description: str | None = OutputField(
        column_name="DESCRIPTION",
        example_values=[
            "Investigative actions to check for the presence of phapp_servicenow<br><br>Added by Phantom for container id: 000"
        ],
    )
    short_description: str | None = OutputField(
        column_name="SHORT DESCRIPTION",
        example_values=["phapp_servicenow, Multiple action need to be taken"],
    )
    category: str | None = OutputField(
        column_name="CATEGORY", example_values=["inquiry"]
    )
    sys_id: str | None = OutputField(
        column_name="SYS ID",
        cef_types=["servicenow ticket sysid", "md5"],
    )
    severity: str | None = OutputField(column_name="SEVERITY", example_values=["3"])
    priority: str | None = OutputField(column_name="PRIORITY", example_values=["5"])
    opened_at: str | None = OutputField(
        column_name="OPENED ON", example_values=["2018-11-22 09:57:05"]
    )
    closed_at: str | None = OutputField(column_name="CLOSED ON")
    acquisition_method: str | None = None
    active: str | None = OutputField(example_values=["true"])
    activity_due: str | None = None
    additional_assignee_list: str | None = None
    approval: str | None = OutputField(example_values=["not requested"])
    approval_history: str | None = None
    approval_set: str | None = None
    asset_tag: str | None = None
    assigned: str | None = None
    assigned_condition: str | None = None
    attachment_details: list[AttachmentDetailsOutput] = Field(default_factory=list)
    beneficiary: str | None = None
    business_duration: str | None = None
    business_stc: str | None = None
    calendar_duration: str | None = None
    calendar_stc: str | None = None
    caused_by: str | None = None
    checked_in: str | None = None
    checked_out: str | None = None
    child_incidents: str | None = OutputField(example_values=["0"])
    close_code: str | None = None
    close_notes: str | None = None
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
    follow_up: str | None = None
    gl_account: str | None = None
    group_list: str | None = None
    hold_reason: str | None = None
    impact: str | None = OutputField(example_values=["3"])
    incident_state: str | None = OutputField(example_values=["1"])
    install_date: str | None = None
    install_status: str | None = OutputField(example_values=["1"])
    invoice_number: str | None = None
    is_merged_license: str | None = OutputField(example_values=["false"])
    justification: str | None = None
    knowledge: str | None = OutputField(example_values=["false"])
    lease_id: str | None = None
    license_key: str | None = None
    made_sla: str | None = OutputField(example_values=["true"])
    merged_into: str | None = None
    notify: str | None = OutputField(example_values=["1"])
    old_status: str | None = None
    old_substatus: str | None = None
    order: str | None = None
    order_date: str | None = None
    owned_by: str | None = None
    parent: str | None = None
    parent_incident: str | None = None
    po_number: str | None = None
    pre_allocated: str | None = OutputField(example_values=["false"])
    problem_id: str | None = None
    purchase_date: str | None = None
    quantity: str | None = OutputField(example_values=["1"])
    reassignment_count: str | None = OutputField(example_values=["0"])
    reopen_count: str | None = OutputField(example_values=["0"])
    reopened_by: str | None = None
    reopened_time: str | None = None
    request_line: str | None = None
    resale_price: str | None = OutputField(example_values=["0"])
    reserved_for: str | None = None
    residual: str | None = OutputField(example_values=["0"])
    residual_date: str | None = None
    resolved_at: str | None = None
    retired: str | None = None
    retirement_date: str | None = None
    rights: str | None = None
    salvage_value: str | None = OutputField(example_values=["0"])
    serial_number: str | None = None
    skip_sync: str | None = OutputField(example_values=["false"])
    sla_due: str | None = None
    state: str | None = OutputField(example_values=["1"])
    subcategory: str | None = None
    substatus: str | None = None
    sys_class_name: str | None = OutputField(example_values=["incident"])
    sys_created_by: str | None = OutputField(example_values=["admin"])
    sys_created_on: str | None = OutputField(example_values=["2018-11-22 09:57:05"])
    sys_domain_path: str | None = OutputField(
        cef_types=["domain"], example_values=["/"]
    )
    sys_mod_count: str | None = OutputField(example_values=["0"])
    sys_tags: str | None = None
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2018-11-22 09:57:05"])
    time_worked: str | None = None
    u_short_description: str | None = None
    upon_approval: str | None = OutputField(example_values=["proceed"])
    upon_reject: str | None = OutputField(example_values=["cancel"])
    urgency: str | None = OutputField(example_values=["3"])
    user_input: str | None = None
    warranty_expiration: str | None = None
    watch_list: str | None = None
    work_end: str | None = None
    work_notes: str | None = None
    work_notes_list: str | None = None
    work_start: str | None = None


def _build_failed_attachment_result(
    params: CreateTicketParams,
    result: dict,
    created_ticket_id: str,
    successfully_added_attachments_count: int | None,
    vault_errors: dict[str, str],
) -> ActionResult:
    vault_failure_details = build_legacy_vault_failure_details(vault_errors)
    message = (
        f"Successfully created ticket {created_ticket_id}, "
        "but failed to add attachment(s)"
    )

    return build_failed_attachment_result(
        params=params,
        message=message,
        result=result,
        summary={
            "created_ticket_id": created_ticket_id,
            "successfully_added_attachments_count": successfully_added_attachments_count,
            "vault_failure_details": vault_failure_details,
        },
    )


@app.action(
    description="Create a new ticket/record",
    action_type="generic",
    read_only=False,
    verbose='Create a new ticket with the given <b>short_description</b> and <b>description</b> (the values provided in the <b>short_description</b> and <b>description</b> action parameters will override the values provided for these keys in the <b>fields</b> action parameter). Additional values can be specified in the <b>fields</b> parameter. By default, the action appends the \'Added by Phantom for container id: <container_id_of_action_run>\' footnote after the value of description provided either in the <b>description</b> or <b>fields</b> action parameters. If the value for <b>description</b> is not provided in any of the above-mentioned two action parameters, then, the default footnote will be added in the description of the created ticket. Study the results of the <b>get ticket</b> action to get more information about all the properties that can be added. The JSON that is specified in the <b>fields</b> parameter should have the keys and values specified in double-quotes string format, except in the case of boolean values, which should be either <i>True</i> or <i>False</i> (without any single quotes); for example: {\\"short_description\\": \\"Zeus, multiple actions need to be taken\\", \\"made_sla\\": False}.<br><br>If this action is performed from the playbook the easiest thing to do is create a dictionary (e.g: <i>my_fields_value_dict</i>) and then pass the return value of <i>json.dumps(my_fields_value_dict)</i> as the value of <b>fields</b>. Please see the servicenow_app playbook for an example.<br><br>One can specify a <b>table</b> other than the <i>incident</i> to create the ticket in. Do note that the fields for user-generated tables, usually are named with <i>u_</i> prefix. In such cases, it is better to use the <b>fields</b> parameter to set values.<br><br>To set a parent-child relationship between two tickets, specify the parent ticket\'s ID in a <b>parent_incident</b> field in the <b>fields</b> parameter while creating the child ticket.<br><br>ServiceNow restricts the upload time and the file size of attached files, which may cause file uploads to fail. These values can be configured by an admin on the ServiceNow device. As of this writing, please go to <a href=\\"https://support.servicenow.com/kb?id=kb_article_view&sysparm_article=KB0718101\\" target=\\"_blank\\">this link</a> on the ServiceNow Website for more information.<br><br>For updating the timeout for attaching the file please go to <b>System Definition</b>-><b>Transaction Quota Rules</b>. Update the <b>maximum duration</b> field as per your requirement in <b>REST Attachment API request timeout</b> or/and <b>REST and JSON Catch ALL</b> rule. The <b>REST Attachment API request timeout</b> rule applies to all incoming attachment requests. Any request exceeding the maximum duration set here will be cancelled and the <b>REST and JSON Catch All</b> rule will be used for all REST transactions.<br><br>If the <b>table</b> value is not specified, the action defaults to the <b>incident</b>.<br><br>ServiceNow does not return an error if an invalid field is updated or if a valid field is updated in an invalid manner (e.g: updating the <i>caller_id</i> dictionary with your dictionary). For the best results, please check the results of the action in the JSON view to verify the changes.<br><br>For the <b>short_description</b> action parameter, users can provide new line(\\n), tab(\\t), single quote(\\\'), double quote(\\\\"), alarm or beep(\\a) and backspace(\\b) as escape sequences and for the <b>description</b> action parameter, new line(\\n, \\r), tab(\\t), single quote(\\\'), double quote(\\\\"), alarm or beep(\\a) and backspace(\\b) can be provided as escape sequences.',
    summary_type=CreateTicketSummary,
    render_as="table",
)
def create_ticket(
    params: CreateTicketParams, soar: SOARClient[CreateTicketSummary], asset: Asset
) -> CreateTicketOutput:
    """
    Create a new ticket in ServiceNow
    """
    logger.progress("Starting create_ticket action")

    table = params.table
    table = validate_path_segment("table", table)
    endpoint = TABLE_ENDPOINT.format(table)

    fields = parse_fields_json(params.fields)

    data = dict()
    data.update(fields)

    # Validate that at least one parameter is provided
    if not fields and not params.short_description and not params.description:
        raise ActionFailure(
            "Please specify at least one of: short_description, description, or fields"
        )

    if params.short_description is not None:
        data["short_description"] = params.short_description

    container_id = soar.get_executing_container_id()
    footnote = f"\n\nAdded by Phantom for container id: {container_id}"

    if params.description:
        data["description"] = f"{params.description}{footnote}"
    elif "description" in fields:
        field_description = fields.get("description", "")
        data["description"] = f"{field_description}{footnote}"
    else:
        data["description"] = footnote

    client = ServiceNowClient(asset)

    response = client.make_rest_call(
        endpoint,
        data=data,
        method="post",
    )

    if not (result := response.get("result")):
        raise ActionFailure("Invalid response from ServiceNow - no result data")

    created_ticket_id = result.get("sys_id")
    if not created_ticket_id:
        raise ActionFailure("Failed to get ticket sys_id from response")

    message = f"Created ticket id: {created_ticket_id}"
    successfully_added_attachments_count = None
    vault_failure_details = None

    if params.vault_id:
        action_helper = ServiceNowActionHelper(soar, client)
        attachment_details, vault_errors = action_helper.handle_vault_attachments(
            table, created_ticket_id, params.vault_id
        )

        if attachment_details:
            result["attachment_details"] = attachment_details
        successfully_added_attachments_count = len(attachment_details)

        if vault_errors:
            message = (
                f"Successfully created ticket {created_ticket_id}, "
                "but failed to add attachment(s)"
            )
            logger.error(
                "%s: %s",
                message,
                ", ".join(f"{vid}: {err}" for vid, err in vault_errors.items()),
            )
            return _build_failed_attachment_result(
                params,
                result,
                created_ticket_id,
                successfully_added_attachments_count,
                vault_errors,
            )

    soar.set_message(message)
    soar.set_summary(
        CreateTicketSummary(
            created_ticket_id=created_ticket_id,
            successfully_added_attachments_count=successfully_added_attachments_count,
            vault_failure_details=vault_failure_details,
        )
    )
    return CreateTicketOutput(**result)
