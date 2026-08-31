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

"""Add Comment Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger
from soar_sdk.exceptions import ActionFailure
from ..app import app, Asset
from ..consts import TICKET_ENDPOINT
from ..helpers import validate_path_segment
from ..servicenow_client import ServiceNowClient

logger = getLogger()


class AddCommentParams(Params):
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
    comment: str = Param(description="Comment to add")
    is_sys_id: bool = Param(
        description="Whether the value provided in the ID parameter is SYS ID or ticket number",
        required=False,
    )


class AddCommentOutput(PermissiveActionOutput):
    """Output structure for add_comment action"""

    acquisition_method: str | None = None
    active: str | None = OutputField(example_values=["false"])
    activity_due: str | None = OutputField(example_values=["UNKNOWN"])
    additional_assignee_list: str | None = None
    approval: str | None = OutputField(example_values=["Not Yet Requested"])
    approval_history: str | None = None
    approval_set: str | None = None
    asset_tag: str | None = OutputField(example_values=["P1000479"])
    asset_tracking_strategy: str | None = OutputField(
        example_values=["Leave to category"]
    )
    assigned: str | None = OutputField(example_values=["2018-07-29 00:00:00"])
    assigned_condition: str | None = None
    barcode: str | None = OutputField(example_values=["G73SW-XN2"])
    beneficiary: str | None = None
    bundle: str | None = OutputField(example_values=["false"])
    business_duration: str | None = OutputField(example_values=["0 Seconds"])
    business_service: str | None = None
    business_stc: str | None = OutputField(example_values=["0"])
    calendar_duration: str | None = OutputField(example_values=["1 Minute"])
    calendar_stc: str | None = OutputField(example_values=["114"])
    category: str | None = OutputField(example_values=["Hardware"])
    caused_by: str | None = None
    certified: str | None = OutputField(example_values=["false"])
    checked_in: str | None = None
    checked_out: str | None = None
    child_incidents: str | None = OutputField(example_values=["1"])
    close_code: str | None = OutputField(example_values=["Solved (Permanently)"])
    close_notes: str | None = OutputField(
        example_values=[
            "This is not an issue with the USB port. Replaced the headset to resolve the issue."
        ]
    )
    closed_at: str | None = OutputField(example_values=["2018-12-09 19:29:08"])
    cmdb_ci: str | None = None
    cmdb_ci_class: str | None = None
    cmdb_model_category: str | None = OutputField(example_values=["Computer"])
    number: str | None = OutputField(
        column_name="TICKET NUMBER",
        cef_types=["servicenow ticket number"],
        example_values=["INC0000001"],
    )
    sys_id: str | None = OutputField(
        column_name="SYS ID",
        cef_types=["servicenow ticket sysid", "md5"],
    )
    short_description: str | None = OutputField(
        column_name="SHORT DESCRIPTION",
        example_values=["My computer is not detecting the headphone device"],
    )
    comments: str | None = OutputField(
        column_name="COMMENTS",
        example_values=[
            "2019-10-15 03:31:23 - System Administrator (Additional comments)<br>test12345 comment<br><br>2019-10-15 02:25:50 - System Administrator (Additional comments)<br>This is a test123 comment<br><br>2019-10-10 06:00:48 - System Administrator (Additional comments)<br>This is a test comment<br><br>2019-10-10 05:45:58 - System Administrator (Additional comments)<br>This is a test comment<br><br>"
        ],
    )
    comments_and_work_notes: str | None = OutputField(
        example_values=[
            "2019-10-15 03:31:23 - System Administrator (Additional comments)<br>test12345 comment<br><br>2019-10-15 02:27:07 - System Administrator (Work notes)<br>This is a test123 work note<br><br>2019-10-15 02:25:50 - System Administrator (Additional comments)<br>This is a test123 comment<br><br>2019-10-10 06:00:48 - System Administrator (Additional comments)<br>This is a test comment<br><br>2019-10-10 05:54:52 - System Administrator (Work notes)<br>This is a test work note<br><br>2019-10-10 05:45:58 - System Administrator (Additional comments)<br>This is a test comment<br><br>"
        ]
    )
    contact_type: str | None = None
    correlation_display: str | None = None
    correlation_id: str | None = None
    cost: str | None = OutputField(example_values=["$1,799.99"])
    delivery_date: str | None = OutputField(example_values=["2018-01-15 23:00:00"])
    delivery_plan: str | None = None
    delivery_task: str | None = None
    depreciated_amount: str | None = OutputField(example_values=["$968.47"])
    depreciation_date: str | None = OutputField(example_values=["2018-02-28 23:00:00"])
    description: str | None = OutputField(
        example_values=[
            "My computer is not detecting the headphone device. It could be an issue with the USB port."
        ]
    )
    display_name: str | None = OutputField(
        example_values=['P1000479 - Apple MacBook Pro 15"']
    )
    disposal_reason: str | None = None
    due: str | None = None
    due_date: str | None = None
    due_in: str | None = None
    entitlement_condition: str | None = None
    escalation: str | None = OutputField(example_values=["Normal"])
    expected_start: str | None = None
    expenditure_type: str | None = None
    flow_rate: str | None = None
    follow_up: str | None = None
    full_name: str | None = None
    gl_account: str | None = None
    group_list: str | None = None
    hold_reason: str | None = None
    impact: str | None = OutputField(example_values=["2 - Medium"])
    incident_state: str | None = OutputField(example_values=["Closed"])
    install_date: str | None = OutputField(example_values=["2018-02-27 23:00:00"])
    install_status: str | None = OutputField(example_values=["In use"])
    invoice_number: str | None = None
    is_merged_license: str | None = OutputField(example_values=["false"])
    justification: str | None = None
    knowledge: str | None = OutputField(example_values=["false"])
    lease_id: str | None = None
    license_key: str | None = None
    made_sla: str | None = OutputField(example_values=["true"])
    main_component: str | None = None
    managed_by: str | None = None
    merged_into: str | None = None
    model_number: str | None = OutputField(example_values=["G73SW-XN2"])
    name: str | None = OutputField(example_values=["G Series"])
    notify: str | None = OutputField(example_values=["Do Not Notify"])
    old_status: str | None = None
    old_substatus: str | None = None
    opened_at: str | None = OutputField(example_values=["2018-09-16 05:49:23"])
    order: str | None = None
    order_date: str | None = OutputField(example_values=["2017-12-22 23:00:00"])
    owned_by: str | None = None
    owner: str | None = None
    parent: str | None = None
    parent_incident: str | None = None
    picture: str | None = None
    po_number: str | None = OutputField(example_values=["PO100004"])
    power_consumption: str | None = None
    pre_allocated: str | None = OutputField(example_values=["false"])
    priority: str | None = OutputField(example_values=["3 - Moderate"])
    problem_id: str | None = None
    purchase_date: str | None = OutputField(example_values=["2018-01-05"])
    quantity: str | None = OutputField(example_values=["1"])
    rack_units: str | None = OutputField(example_values=["1"])
    reassignment_count: str | None = OutputField(example_values=["0"])
    reopen_count: str | None = OutputField(example_values=["0"])
    reopened_by: str | None = None
    reopened_time: str | None = None
    request_line: str | None = None
    resale_price: str | None = OutputField(example_values=["$0.00"])
    reserved_for: str | None = None
    residual: str | None = OutputField(example_values=["$831.52"])
    residual_date: str | None = OutputField(example_values=["2020-11-08"])
    resolved_at: str | None = OutputField(example_values=["2018-09-16 05:51:17"])
    retired: str | None = None
    retirement_date: str | None = None
    rfc: str | None = None
    rights: str | None = OutputField(example_values=["600"])
    salvage_value: str | None = OutputField(example_values=["$0.00"])
    serial_number: str | None = OutputField(example_values=["BQP-854-D33246-GH"])
    service_offering: str | None = None
    severity: str | None = OutputField(example_values=["3 - Low"])
    skip_sync: str | None = OutputField(example_values=["false"])
    sla: str | None = None
    sla_due: str | None = OutputField(example_values=["UNKNOWN"])
    sound_power: str | None = None
    state: str | None = OutputField(example_values=["Closed"])
    status: str | None = OutputField(example_values=["In Production"])
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
    sys_mod_count: str | None = OutputField(example_values=["16"])
    sys_tags: str | None = None
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2019-10-15 03:31:23"])
    time_worked: str | None = None
    type: str | None = OutputField(example_values=["Generic"])
    u_short_description: str | None = None
    upon_approval: str | None = OutputField(example_values=["Proceed to Next Task"])
    upon_reject: str | None = OutputField(example_values=["Cancel all future Tasks"])
    urgency: str | None = OutputField(example_values=["2 - Medium"])
    user_input: str | None = None
    warranty_expiration: str | None = OutputField(example_values=["2021-02-27"])
    watch_list: str | None = None
    weight: str | None = None
    work_end: str | None = None
    work_notes: str | None = OutputField(
        example_values=[
            "2019-10-15 02:27:07 - System Administrator (Work notes)<br>This is a test123 work note<br><br>2019-10-10 05:54:52 - System Administrator (Work notes)<br>This is a test work note<br><br>"
        ]
    )
    work_notes_list: str | None = None
    work_start: str | None = None


@app.action(
    description="Add a comment to a record",
    action_type="generic",
    read_only=False,
    render_as="table",
    verbose="Users can provide a valid ticket number in the 'id' parameter or check the 'is_sys_id' parameter and provide a valid <b>SYS ID</b> in the 'id' parameter. Users can get the <b>SYS ID</b> value for any ticket from the results of the <b>List Tickets</b> action run. For 'comment' parameter, users can provide new line(\\n), single quote(\\'), double quote(\\\\\") and backspace(\\b) as escape sequences.",
)
def add_comment(
    params: AddCommentParams, soar: SOARClient, asset: Asset
) -> AddCommentOutput:
    logger.progress("adding comment to servicenow record")

    client = ServiceNowClient(asset)

    sys_id = params.id
    table_name = validate_path_segment("table_name", params.table_name)
    is_sys_id = params.is_sys_id if params.is_sys_id is not None else False
    if not is_sys_id:
        sys_id = client.get_sys_id_from_ticket_number(
            table_name=table_name,
            ticket_number=params.id,
        )
    sys_id = validate_path_segment("sys_id", sys_id)
    endpoint = TICKET_ENDPOINT.format(table_name, sys_id)
    data = {"comments": params.comment}
    request_params = {"sysparm_display_value": True}
    response = client.make_rest_call(
        endpoint=endpoint,
        params=request_params,
        data=data,
        method="put",
    )

    if not (result := response.get("result", {})):
        raise ActionFailure("No results found after adding comment")

    # Process comments field - replace double newlines with comma-separated format
    if result.get("comments"):
        result["comments"] = result["comments"].replace("\n\n", "\n, ").strip(", ")

    soar.set_message("Added the comment successfully")
    return AddCommentOutput(**result)
