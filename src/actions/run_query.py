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

"""Run Query Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import SERVICENOW_SENSITIVE_PROPS
from ..helpers import validate_path_segment
from ..servicenow_client import ServiceNowClient


class RunQueryParams(Params):
    query: str = Param(
        description="The query to search for e.g. sysparm_query=short_descriptionLIKEaudit"
    )
    query_table: str = Param(
        description="Name of the table to be searched task",
        primary=True,
        cef_types=["servicenow table"],
    )
    max_results: int = Param(
        description="Max number of records to return", required=False, default=100
    )


class RunQuerySummary(ActionOutput):
    """Summary for run query action"""

    total_tickets: int = OutputField(example_values=[10, 50, 100])


class RunQueryOutput(PermissiveActionOutput):
    """Flexible output for records returned from arbitrary ServiceNow tables."""

    number: str | None = OutputField(
        column_name="TICKET NUMBER",
        cef_types=["servicenow ticket number"],
        example_values=["INC0000001"],
    )
    description: str | None = OutputField(
        column_name="DESCRIPTION",
        example_values=[
            "I can access my folder but can't access my team's folder on our file share"
        ],
    )
    short_description: str | None = OutputField(
        column_name="SHORT DESCRIPTION",
        example_values=["Unable to access team file share"],
    )
    sys_id: str | None = OutputField(
        column_name="ID",
        cef_types=["servicenow ticket sysid", "md5"],
    )
    severity: str | None = OutputField(column_name="SEVERITY", example_values=["3"])
    priority: str | None = OutputField(column_name="PRIORITY", example_values=["3"])
    opened_at: str | None = OutputField(
        column_name="OPENED ON", example_values=["2016-08-10 16:14:29"]
    )
    closed_at: str | None = OutputField(
        column_name="CLOSED ON", example_values=["2018-02-08 23:10:06"]
    )
    active: str | None = OutputField(example_values=["true"])
    activity_due: str | None = None
    additional_assignee_list: str | None = None
    admin_user: str | None = None
    approval: str | None = OutputField(example_values=["not requested"])
    approval_history: str | None = None
    approval_set: str | None = None
    business_duration: str | None = OutputField(example_values=["1970-01-22 21:46:21"])
    business_stc: str | None = OutputField(example_values=["1892781"])
    calendar_duration: str | None = OutputField(example_values=["1970-04-02 20:46:21"])
    calendar_stc: str | None = OutputField(example_values=["7937181"])
    category: str | None = OutputField(example_values=["inquiry"])
    caused_by: str | None = None
    child_incidents: str | None = OutputField(example_values=["0"])
    close_code: str | None = OutputField(example_values=["Closed/Resolved by Caller"])
    close_notes: str | None = OutputField(
        example_values=["Closed before close notes were made mandatory<br>\t\t"]
    )
    cluster_node: str | None = None
    comments: str | None = None
    comments_and_work_notes: str | None = None
    contact_type: str | None = OutputField(example_values=["self-service"])
    correlation_display: str | None = None
    correlation_id: str | None = None
    database_name: str | None = None
    database_tablespace: str | None = None
    database_type: str | None = None
    database_url: str | None = None
    database_user: str | None = None
    delivery_plan: str | None = None
    delivery_task: str | None = None
    due_date: str | None = None
    escalation: str | None = OutputField(example_values=["0"])
    expected_start: str | None = None
    follow_up: str | None = None
    group_list: str | None = None
    hold_reason: str | None = None
    impact: str | None = OutputField(example_values=["2"])
    incident_state: str | None = OutputField(example_values=["1"])
    instance_id: str | None = None
    instance_name: str | None = OutputField(example_values=["Source Instance"])
    instance_url: str | None = None
    knowledge: str | None = OutputField(example_values=["false"])
    made_sla: str | None = OutputField(example_values=["true"])
    notify: str | None = OutputField(example_values=["1"])
    order: str | None = None
    parent: str | None = None
    primary: str | None = None
    production: str | None = OutputField(example_values=["true"])
    reassignment_count: str | None = OutputField(example_values=["0"])
    reopen_count: str | None = OutputField(example_values=["0"])
    reopened_by: str | None = None
    reopened_time: str | None = None
    resolved_at: str | None = OutputField(example_values=["2018-05-10 19:56:12"])
    service_offering: str | None = None
    sla_due: str | None = None
    source: str | None = OutputField(example_values=["true"])
    state: str | None = OutputField(example_values=["1"])
    subcategory: str | None = None
    sys_class_name: str | None = OutputField(example_values=["incident"])
    sys_created_by: str | None = OutputField(example_values=["admin"])
    sys_created_on: str | None = OutputField(example_values=["2016-08-10 16:14:29"])
    sys_domain_path: str | None = OutputField(
        cef_types=["domain"], example_values=["/"]
    )
    sys_mod_count: str | None = OutputField(example_values=["0"])
    sys_tags: str | None = None
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2016-08-10 16:14:29"])
    time_worked: str | None = None
    u_short_description: str | None = None
    upon_approval: str | None = OutputField(example_values=["proceed"])
    upon_reject: str | None = OutputField(example_values=["cancel"])
    urgency: str | None = OutputField(example_values=["2"])
    user_input: str | None = None
    validation_error: str | None = None
    war_version: str | None = None
    watch_list: str | None = None
    work_end: str | None = None
    work_notes: str | None = None
    work_notes_list: str | None = None
    work_start: str | None = None


def _strip_sensitive_props(record: dict) -> dict:
    return {
        key: value
        for key, value in record.items()
        if key not in SERVICENOW_SENSITIVE_PROPS
    }


@app.action(
    description="Gets object data according to the specified query",
    action_type="investigate",
    summary_type=RunQuerySummary,
    render_as="table",
)
def run_query(
    params: RunQueryParams, soar: SOARClient[RunQuerySummary], asset: Asset
) -> list[RunQueryOutput]:
    """
    Executes a raw ServiceNow query on a specified table
    """
    logger = getLogger()
    logger.info("Starting run_query action")

    # Validate max_results parameter (already int type, SDK handles coercion)
    if params.max_results < 0:
        raise ActionFailure(
            "Please provide a valid non-negative integer value in the max_results parameter"
        )
    if params.max_results == 0:
        raise ActionFailure(
            "Please provide a positive integer value in the max_results parameter"
        )

    table = validate_path_segment("query_table", params.query_table)
    query_string = params.query

    # Preserve legacy behavior: params.query is a raw query string.
    endpoint = f"/table/{table}?{query_string}"

    logger.info(f"Executing query on table '{table}' with endpoint: {endpoint}")

    client = ServiceNowClient(asset)

    try:
        records = client.paginator(endpoint, payload={}, limit=params.max_results)

        if records is None:
            raise ActionFailure("Invalid parameters or query execution failed")

        output_records = [
            RunQueryOutput(**_strip_sensitive_props(record)) for record in records
        ]

        soar.set_summary(RunQuerySummary(total_tickets=len(output_records)))

        logger.info(
            f"Query executed successfully, returned {len(output_records)} records"
        )

        return output_records

    except ActionFailure:
        raise
    except Exception as e:
        raise ActionFailure(f"Failed to execute query: {e}") from e
