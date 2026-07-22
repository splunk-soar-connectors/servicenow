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

"""Request Catalog Item Action"""

import ast
import json
from typing import Optional
from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger
from soar_sdk.exceptions import ActionFailure

from ..app import app, Asset
from ..consts import (
    CATALOG_ITEMS_ENDPOINT,
    CATALOG_ORDER_NOW_ENDPOINT,
    TICKET_ENDPOINT,
    SC_API_URI,
    API_URI,
)
from ..helpers import ServiceNowClient, validate_path_segment

logger = getLogger()


class RequestCatalogItemParams(Params):
    sys_id: str = Param(
        description="SYS ID of an item",
        primary=True,
        cef_types=["servicenow item sys id", "md5"],
    )
    variables: str = Param(
        description="JSON containing variables values", required=False
    )
    quantity: int = Param(description="Number of items to request", default=1)


class RequestCatalogItemOutput(PermissiveActionOutput):
    """Output structure for request_catalog_item action"""

    # Primary fields for table display - order matters for rendering
    number: str | None = OutputField(
        column_name="REQUEST NUMBER",
        cef_types=["servicenow ticket number"],
        example_values=["REQ0010008"],
    )
    short_description: str | None = OutputField(column_name="SHORT DESCRIPTION")
    priority: str | None = OutputField(column_name="PRIORITY", example_values=["4"])
    price: str | None = OutputField(column_name="PRICE", example_values=["0"])
    due_date: str | None = OutputField(
        column_name="DUE DATE", example_values=["2019-10-18 13:49:24"]
    )
    assigned_to: str | None = OutputField(column_name="ASSIGNED TO")

    # All other fields in alphabetical order
    active: str | None = OutputField(example_values=["true"])
    activity_due: str | None = None
    additional_assignee_list: str | None = None
    approval: str | None = OutputField(example_values=["approved"])
    approval_history: str | None = None
    approval_set: str | None = None
    assignment_group: str | None = None
    business_duration: str | None = None
    business_service: str | None = None
    calendar_duration: str | None = None
    calendar_stc: str | None = None
    close_notes: str | None = None
    closed_at: str | None = None
    closed_by: str | None = None
    cmdb_ci: str | None = None
    comments: str | None = None
    comments_and_work_notes: str | None = None
    company: str | None = None
    contact_type: str | None = None
    correlation_display: str | None = None
    correlation_id: str | None = None
    delivery_address: str | None = None
    delivery_plan: str | None = None
    delivery_task: str | None = None
    description: str | None = None
    escalation: str | None = OutputField(example_values=["0"])
    expected_start: str | None = None
    follow_up: str | None = None
    group_list: str | None = None
    impact: str | None = OutputField(example_values=["3"])
    knowledge: str | None = OutputField(example_values=["false"])
    location: str | None = None
    made_sla: str | None = OutputField(example_values=["true"])
    opened_at: str | None = OutputField(example_values=["2019-10-18 13:49:24"])
    order: str | None = None
    parent: str | None = None
    parent_interaction: str | None = None
    reassignment_count: str | None = OutputField(example_values=["0"])
    request_state: str | None = OutputField(example_values=["in_process"])
    requested_date: str | None = None
    service_offering: str | None = None
    sla_due: str | None = None
    special_instructions: str | None = None
    stage: str | None = OutputField(example_values=["requested"])
    state: str | None = OutputField(example_values=["1"])
    sys_class_name: str | None = OutputField(example_values=["sc_request"])
    sys_created_by: str | None = OutputField(example_values=["admin"])
    sys_created_on: str | None = OutputField(example_values=["2019-10-18 13:49:24"])
    sys_domain_path: str | None = OutputField(
        cef_types=["domain"], example_values=["/"]
    )
    sys_id: str | None = OutputField(cef_types=["md5"])
    sys_mod_count: str | None = OutputField(example_values=["0"])
    sys_tags: str | None = None
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2019-10-18 13:49:24"])
    time_worked: str | None = None
    upon_approval: str | None = OutputField(example_values=["proceed"])
    upon_reject: str | None = OutputField(example_values=["cancel"])
    urgency: str | None = OutputField(example_values=["3"])
    user_input: str | None = None
    watch_list: str | None = None
    work_end: str | None = None
    work_notes: str | None = None
    work_notes_list: str | None = None
    work_start: str | None = None


@app.action(
    description="Requests a catalog item",
    action_type="generic",
    read_only=False,
    verbose="Order an item from the ServiceNow Service Catalog. Each catalog item has a set of variables which can be passed in as a JSON-formatted dictionary. Use the <b>get variables</b> action to get the list of variables that can be set for a given item. Use the <b>describe catalog item</b> action to get the list of mandatory variables.",
    render_as="table",
)
def request_catalog_item(
    params: RequestCatalogItemParams, soar: SOARClient, asset: Asset
) -> RequestCatalogItemOutput:
    """
    Requests a catalog item from ServiceNow
    """
    logger.info("Starting request_catalog_item action")

    helper = ServiceNowClient(asset)
    if params.quantity < 1:
        raise ActionFailure("Quantity must be a positive integer")
    variables_dict = _parse_variables(params.variables)

    # Step 1: Fetch catalog item details to validate mandatory variables
    sys_id = validate_path_segment("sys_id", params.sys_id)
    logger.info(f"Fetching catalog item details for sys_id: {sys_id}")
    endpoint = CATALOG_ITEMS_ENDPOINT.format(sys_id)

    try:
        response = helper.make_rest_call(
            endpoint,
            api_uri=SC_API_URI,
        )
    except Exception as e:
        logger.error(f"Failed to fetch catalog item details: {e}")
        raise ActionFailure(f"Failed to fetch catalog item details: {e}") from e

    # Validate response
    if not response.get("result"):
        raise ActionFailure(
            f"No data found for catalog item with sys_id: {sys_id}"
        )

    # Step 2: Extract and validate mandatory variables
    mandatory_variables = []
    item_details = response.get("result", {})

    if item_details.get("variables"):
        for variable in item_details["variables"]:
            if variable.get("mandatory"):
                var_name = variable.get("name")
                if var_name:
                    mandatory_variables.append(var_name)

    # Check if mandatory variables are provided
    if mandatory_variables:
        if not variables_dict:
            # No variables provided but mandatory ones required
            raise ActionFailure(
                f"Please provide the mandatory variables to order this item. "
                f"Mandatory variables: {', '.join(mandatory_variables)}"
            )

        # Check if all mandatory variables are present
        missing_variables = []
        for var in mandatory_variables:
            if var not in variables_dict:
                missing_variables.append(var)

        if missing_variables:
            raise ActionFailure(
                f"Please provide the mandatory variables to order this item. "
                f"Mandatory variables: {', '.join(mandatory_variables)}"
            )

    logger.info(f"Validated mandatory variables: {mandatory_variables}")

    # Step 3: Order the catalog item
    logger.info(f"Ordering catalog item with quantity: {params.quantity}")
    order_endpoint = CATALOG_ORDER_NOW_ENDPOINT.format(sys_id)

    # Build order request data
    order_data = {"sysparm_quantity": params.quantity}

    if variables_dict:
        order_data["variables"] = variables_dict

    try:
        order_response = helper.make_rest_call(
            order_endpoint,
            data=order_data,
            method="post",
            api_uri=SC_API_URI,
        )
    except Exception as e:
        logger.error(f"Failed to order catalog item: {e}")
        raise ActionFailure(f"Failed to order catalog item: {e}") from e

    # Validate order response
    if not order_response.get("result"):
        raise ActionFailure("Invalid response from ServiceNow - no order result data")

    order_result = order_response.get("result", {})
    request_sys_id = order_result.get("sys_id")
    table = order_result.get("table")

    if not request_sys_id or not table:
        raise ActionFailure("Failed to get request sys_id or table from order response")

    logger.info(
        f"Catalog item ordered successfully. Request sys_id: {request_sys_id}, table: {table}"
    )

    # Step 4: Fetch the created request record details
    logger.info("Fetching request record details")
    table = validate_path_segment("table", table)
    request_sys_id = validate_path_segment("sys_id", request_sys_id)
    ticket_endpoint = TICKET_ENDPOINT.format(table, request_sys_id)

    try:
        ticket_response = helper.make_rest_call(
            ticket_endpoint,
            api_uri=API_URI,
        )
    except Exception as e:
        logger.error(f"Failed to fetch request details: {e}")
        raise ActionFailure(f"Failed to fetch request details: {e}") from e

    # Validate ticket response
    if not ticket_response.get("result"):
        raise ActionFailure("Failed to get request details from ServiceNow")

    result = ticket_response.get("result", {})

    logger.info("Catalog item requested successfully")
    soar.set_message("The item has been requested")

    # Convert result to output model
    return RequestCatalogItemOutput(**result)


def _parse_variables(variables_str: Optional[str]) -> Optional[dict]:
    """
    Parse variables JSON string parameter to dictionary
    """
    if not variables_str:
        return None

    try:
        # Try to parse as JSON first (recommended)
        variables = json.loads(variables_str)
    except json.JSONDecodeError:
        # Fall back to ast.literal_eval for backward compatibility
        try:
            variables = ast.literal_eval(variables_str)
        except Exception as e:
            raise ActionFailure(
                f"Error parsing variables parameter: {e}. "
                "Please ensure the input is valid JSON format"
            ) from e

    if not isinstance(variables, dict):
        raise ActionFailure("Variables parameter must be a JSON object/dictionary")

    return variables
