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

"""List Tickets Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import DEFAULT_MAX_LIMIT, TABLE_ENDPOINT
from ..helpers import validate_path_segment, validate_positive_integer
from ..servicenow_client import ServiceNowClient

logger = getLogger()


class ListTicketsParams(Params):
    filter: str = Param(
        description="Filter to use with action separated by '^' (e.g. description=This is a test^assigned_to=john.smith)",
        required=False,
        default="",
    )
    table: str = Param(
        description="Table to query",
        required=False,
        primary=True,
        default="incident",
        cef_types=["servicenow table"],
    )
    max_results: int = Param(
        description="Max number of records to return", required=False, default=100
    )


class ListTicketOutput(PermissiveActionOutput):
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
    active: str | None = OutputField(example_values=["false"])
    activity_due: str | None = ""
    additional_assignee_list: str | None = ""
    approval: str | None = ""
    approval_history: str | None = ""
    approval_set: str | None = ""
    business_duration: str | None = OutputField(example_values=["1970-01-22 21:46:21"])
    business_stc: str | None = OutputField(example_values=["1892781"])
    calendar_duration: str | None = OutputField(example_values=["1970-04-02 20:46:21"])
    calendar_stc: str | None = OutputField(example_values=["7937181"])
    category: str | None = OutputField(example_values=["network"])
    caused_by: str | None = ""
    child_incidents: str | None = ""
    close_code: str | None = OutputField(example_values=["Closed/Resolved by Caller"])
    close_notes: str | None = OutputField(
        example_values=["Closed before close notes were made mandatory<br>\t\t"]
    )
    comments: str | None = ""
    comments_and_work_notes: str | None = ""
    contact_type: str | None = ""
    correlation_display: str | None = ""
    correlation_id: str | None = ""
    delivery_plan: str | None = ""
    delivery_task: str | None = ""
    due_date: str | None = ""
    escalation: str | None = OutputField(example_values=["0"])
    expected_start: str | None = ""
    follow_up: str | None = ""
    group_list: str | None = ""
    hold_reason: str | None = ""
    impact: str | None = OutputField(example_values=["1"])
    incident_state: str | None = OutputField(example_values=["7"])
    knowledge: str | None = OutputField(example_values=["false"])
    made_sla: str | None = OutputField(example_values=["false"])
    notify: str | None = OutputField(example_values=["1"])
    order: str | None = ""
    parent: str | None = ""
    reassignment_count: str | None = OutputField(example_values=["1"])
    reopen_count: str | None = ""
    reopened_by: str | None = ""
    reopened_time: str | None = ""
    resolved_at: str | None = OutputField(example_values=["2018-05-10 19:56:12"])
    sc_item_option: str | None = ""
    service_offering: str | None = ""
    sla_due: str | None = ""
    state: str | None = OutputField(example_values=["7"])
    subcategory: str | None = ""
    sys_class_name: str | None = OutputField(example_values=["incident"])
    sys_created_by: str | None = OutputField(example_values=["pat"])
    sys_created_on: str | None = OutputField(example_values=["2016-09-08 18:24:13"])
    sys_domain_path: str | None = OutputField(
        cef_types=["domain"], example_values=["/"]
    )
    sys_mod_count: str | None = OutputField(example_values=["22"])
    sys_tags: str | None = ""
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2018-11-21 05:51:32"])
    time_worked: str | None = ""
    u_short_description: str | None = ""
    upon_approval: str | None = ""
    upon_reject: str | None = ""
    urgency: str | None = OutputField(example_values=["1"])
    user_input: str | None = ""
    watch_list: str | None = ""
    work_end: str | None = ""
    work_notes: str | None = ""
    work_notes_list: str | None = ""
    work_start: str | None = ""


class ListTicketsSummary(ActionOutput):
    """Summary for list tickets action"""

    total_tickets: int = OutputField(example_values=[10, 50, 100])


@app.action(
    description="Get a list of tickets/records",
    action_type="investigate",
    read_only=True,
    summary_type=ListTicketsSummary,
    render_as="table",
    verbose="Steps for getting the required filter query are as follows: In the ServiceNow instance, navigate to the required table's page. Create the query in the ServiceNow UI. On the top-left corner of the page, right-click on the query string and select the 'Copy query' option to copy the required query string. This query string can be further used or modified as per the user's need to provide in the filter parameter of the action. If the <b>table</b> value is not specified, the action defaults to the <b>incident</b>. If the <b>max_results</b> value is not specified, the action defaults to <b>100</b>. For specifying and getting the filter to work correctly, below is the criteria for the date-time fields: <ul><li>If the user provides date-time filter based on local timezone as selected on the ServiceNow settings, follow the syntax i.e. sys_created_on>javascript:gs.dateGenerate('YYYY-MM-DD','HH:mm:SS'). </li> <li>If the user provides a date-time filter based on GMT/UTC timezone, follow the syntax i.e. sys_created_on>YYYY-MM-DD HH:mm:SS.</li></ul>",
)
def list_tickets(
    params: ListTicketsParams, soar: SOARClient[ListTicketsSummary], asset: Asset
) -> list[ListTicketOutput]:
    """List tickets/records from ServiceNow"""
    logger.progress(
        f"Listing tickets from table: {params.table} with max_results: {params.max_results}"
    )

    client = ServiceNowClient(asset)
    table = validate_path_segment("table", params.table)
    endpoint = TABLE_ENDPOINT.format(table)

    request_params = {"sysparm_query": params.filter}
    limit = validate_positive_integer(
        "max_results", params.max_results, DEFAULT_MAX_LIMIT
    )
    tickets = client.paginator(endpoint, payload=request_params, limit=limit)

    if not tickets:
        logger.info("No tickets found")
        soar.set_summary(ListTicketsSummary(total_tickets=0))
        soar.set_message("No tickets found")
        return []

    soar.set_summary(ListTicketsSummary(total_tickets=len(tickets)))
    soar.set_message(f"Successfully retrieved {len(tickets)} tickets")

    return [ListTicketOutput(**ticket) for ticket in tickets]
