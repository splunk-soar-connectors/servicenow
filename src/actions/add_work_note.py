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

"""Add Work Note Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import TICKET_ENDPOINT
from ..helpers import ServiceNowClient, validate_path_segment

logger = getLogger()


class AddWorkNoteParams(Params):
    table_name: str = Param(
        description="Table to query",
        primary=True,
        default="incident",
        cef_types=["servicenow table"],
    )
    id: str = Param(
        description="SYS ID or ticket number of a record",
        primary=True,
        cef_types=["servicenow ticket sysid", "servicenow ticket number"],
    )
    work_note: str = Param(description="Work note to add")
    is_sys_id: bool = Param(
        description="Whether the value provided in the ID parameter is SYS ID or ticket number",
        required=False,
    )


class AddWorkNoteOutput(PermissiveActionOutput):
    """Output structure for add_work_note action"""

    # Primary fields for table display - order matters for rendering
    number: str | None = OutputField(
        column_name="TICKET NUMBER",
        cef_types=["servicenow ticket number"],
        example_values=["INC0000001"],
    )
    short_description: str | None = OutputField(
        column_name="SHORT DESCRIPTION",
        example_values=["My computer is not detecting the headphone device"],
    )
    sys_id: str | None = OutputField(
        column_name="SYS ID",
        cef_types=["servicenow ticket sysid", "md5"],
    )
    work_notes: str | None = OutputField(
        column_name="WORK NOTES",
        example_values=[
            "2019-10-15 03:56:58 - System Administrator (Work notes)<br>check work note<br><br>2019-10-15 02:27:07 - System Administrator (Work notes)<br>This is a test123 work note<br><br>2019-10-10 05:54:52 - System Administrator (Work notes)<br>This is a test work note<br><br>"
        ],
    )

    # All other fields in alphabetical order
    acquisition_method: str | None = None
    active: str | None = OutputField(example_values=["false"])
    activity_due: str | None = OutputField(example_values=["UNKNOWN"])
    additional_assignee_list: str | None = None
    approval: str | None = OutputField(example_values=["Not Yet Requested"])
    approval_history: str | None = None
    approval_set: str | None = None
    asset_tag: str | None = OutputField(example_values=["SW000077"])
    assigned: str | None = OutputField(example_values=["2020-02-02 23:00:00"])
    assigned_condition: str | None = None
    beneficiary: str | None = None
    business_duration: str | None = OutputField(example_values=["0 Seconds"])
    business_service: str | None = None
    business_stc: str | None = OutputField(example_values=["0"])
    calendar_duration: str | None = OutputField(example_values=["1 Minute"])
    calendar_stc: str | None = OutputField(example_values=["114"])
    category: str | None = OutputField(example_values=["Hardware"])
    caused_by: str | None = None
    checked_in: str | None = None
    checked_out: str | None = None
    child_incidents: str | None = None
    close_code: str | None = OutputField(example_values=["Solved (Permanently)"])
    close_notes: str | None = OutputField(
        example_values=[
            "This is not an issue with the USB port. Replaced the headset to resolve the issue."
        ]
    )
    closed_at: str | None = OutputField(example_values=["2018-12-09 19:29:08"])
    cmdb_ci: str | None = None
    comments: str | None = OutputField(
        example_values=[
            "2019-10-15 03:31:23 - System Administrator (Additional comments)<br>test12345 comment<br><br>2019-10-15 02:25:50 - System Administrator (Additional comments)<br>This is a test123 comment<br><br>2019-10-10 06:00:48 - System Administrator (Additional comments)<br>This is a test comment<br><br>2019-10-10 05:45:58 - System Administrator (Additional comments)<br>This is a test comment<br><br>"
        ]
    )
    comments_and_work_notes: str | None = OutputField(
        example_values=[
            "2019-10-15 03:56:58 - System Administrator (Work notes)<br>check work note<br><br>2019-10-15 03:31:23 - System Administrator (Additional comments)<br>test12345 comment<br><br>2019-10-15 02:27:07 - System Administrator (Work notes)<br>This is a test123 work note<br><br>2019-10-15 02:25:50 - System Administrator (Additional comments)<br>This is a test123 comment<br><br>2019-10-10 06:00:48 - System Administrator (Additional comments)<br>This is a test comment<br><br>2019-10-10 05:54:52 - System Administrator (Work notes)<br>This is a test work note<br><br>2019-10-10 05:45:58 - System Administrator (Additional comments)<br>This is a test comment<br><br>"
        ]
    )
    contact_type: str | None = None
    contract: str | None = None
    correlation_display: str | None = None
    correlation_id: str | None = None
    cost: str | None = OutputField(example_values=["$590.00"])
    cost_center: str | None = None
    delivery_date: str | None = None
    delivery_plan: str | None = None
    delivery_task: str | None = None
    department: str | None = None
    depreciated_amount: str | None = OutputField(example_values=["$0.00"])
    depreciation: str | None = None
    depreciation_date: str | None = None
    description: str | None = OutputField(
        example_values=[
            "My computer is not detecting the headphone device. It could be an issue with the USB port."
        ]
    )
    display_name: str | None = OutputField(example_values=["SW000077 Test"])
    disposal_reason: str | None = None
    due: str | None = None
    due_date: str | None = None
    due_in: str | None = None
    entitlement_condition: str | None = None
    escalation: str | None = OutputField(example_values=["Normal"])
    expected_start: str | None = None
    expenditure_type: str | None = None
    follow_up: str | None = None
    gl_account: str | None = None
    group_list: str | None = None
    hold_reason: str | None = None
    impact: str | None = OutputField(example_values=["2 - Medium"])
    incident_state: str | None = OutputField(example_values=["Closed"])
    install_date: str | None = OutputField(example_values=["2019-08-19 01:00:00"])
    install_status: str | None = OutputField(example_values=["In use"])
    invoice_number: str | None = None
    is_merged_license: str | None = OutputField(example_values=["false"])
    justification: str | None = None
    knowledge: str | None = OutputField(example_values=["false"])
    lease_id: str | None = None
    license_key: str | None = None
    location: str | None = None
    made_sla: str | None = OutputField(example_values=["true"])
    managed_by: str | None = None
    merged_into: str | None = None
    notify: str | None = OutputField(example_values=["Do Not Notify"])
    old_status: str | None = None
    old_substatus: str | None = None
    opened_at: str | None = OutputField(example_values=["2018-09-16 05:49:23"])
    order: str | None = None
    order_date: str | None = None
    owned_by: str | None = None
    parent: str | None = None
    parent_incident: str | None = None
    po_number: str | None = None
    pre_allocated: str | None = OutputField(example_values=["false"])
    priority: str | None = OutputField(example_values=["3 - Moderate"])
    problem_id: str | None = None
    purchase_date: str | None = None
    quantity: str | None = OutputField(example_values=["1"])
    reassignment_count: str | None = OutputField(example_values=["0"])
    reopen_count: str | None = OutputField(example_values=["0"])
    reopened_by: str | None = None
    reopened_time: str | None = None
    request_line: str | None = None
    resale_price: str | None = OutputField(example_values=["$0.00"])
    reserved_for: str | None = None
    residual: str | None = OutputField(example_values=["$0.00"])
    residual_date: str | None = None
    resolved_at: str | None = OutputField(example_values=["2018-09-16 05:51:17"])
    retired: str | None = None
    retirement_date: str | None = None
    rfc: str | None = None
    rights: str | None = OutputField(example_values=["10"])
    route_reason: str | None = None
    salvage_value: str | None = OutputField(example_values=["$0.00"])
    serial_number: str | None = None
    service_offering: str | None = None
    severity: str | None = OutputField(example_values=["3 - Low"])
    skip_sync: str | None = OutputField(example_values=["false"])
    sla_due: str | None = OutputField(example_values=["UNKNOWN"])
    state: str | None = OutputField(example_values=["Closed"])
    subcategory: str | None = None
    substatus: str | None = None
    support_group: str | None = None
    supported_by: str | None = None
    sys_class_name: str | None = OutputField(example_values=["Incident"])
    sys_created_by: str | None = OutputField(example_values=["admin"])
    sys_created_on: str | None = OutputField(example_values=["2018-09-16 05:50:05"])
    sys_domain_path: str | None = OutputField(
        cef_types=["domain"], example_values=["/"]
    )
    sys_mod_count: str | None = OutputField(example_values=["17"])
    sys_tags: str | None = None
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2019-10-15 03:56:58"])
    task_effective_number: str | None = OutputField(example_values=["INC0010111"])
    time_worked: str | None = None
    u_short_description: str | None = None
    universal_request: str | None = None
    upon_approval: str | None = OutputField(example_values=["Proceed to Next Task"])
    upon_reject: str | None = OutputField(example_values=["Cancel all future Tasks"])
    urgency: str | None = OutputField(example_values=["2 - Medium"])
    user_input: str | None = None
    warranty_expiration: str | None = None
    watch_list: str | None = None
    work_end: str | None = None
    work_notes_list: str | None = None
    work_start: str | None = None


@app.action(
    description="Add a work note to a record",
    action_type="generic",
    read_only=False,
    render_as="table",
    verbose="Users can provide a valid ticket number in the 'id' parameter or check the 'is_sys_id' parameter and provide a valid <b>SYS ID</b> in the 'id' parameter. Users can get the <b>SYS ID</b> value for any ticket from the results of the <b>List Tickets</b> action run. For 'work_note' parameter, users can provide new line(\\n), single quote(\\'), double quote(\\\\\") and backspace(\\b) as escape sequences.",
)
def add_work_note(
    params: AddWorkNoteParams, soar: SOARClient, asset: Asset
) -> AddWorkNoteOutput:
    """Add a work note to a ServiceNow record"""
    logger.progress(f"Adding work note to table {params.table_name}, ID: {params.id}")

    helper = ServiceNowClient(asset)

    sys_id = params.id
    table_name = validate_path_segment("table_name", params.table_name)
    if not params.is_sys_id:
        sys_id = helper.get_sys_id_from_ticket_number(
            table_name=table_name,
            ticket_number=sys_id,
        )

    work_note = (
        params.work_note.replace("\\n", "\n")
        .replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\b", "\b")
    )
    data = {"work_notes": work_note}

    sys_id = validate_path_segment("sys_id", sys_id)
    endpoint = TICKET_ENDPOINT.format(table_name, sys_id)
    request_params = {"sysparm_display_value": True}

    response = helper.make_rest_call(
        endpoint, data=data, params=request_params, method="put"
    )
    if not (result := response.get("result", {})):
        raise ActionFailure("No data returned from ServiceNow after adding work note")

    if result.get("work_notes"):
        result["work_notes"] = result["work_notes"].replace("\n\n", "\n, ").strip(", ")

    soar.set_message("Added the work note successfully")

    return AddWorkNoteOutput(**result)
