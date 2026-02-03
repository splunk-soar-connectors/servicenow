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

"""Get Variables Action"""

from typing import Any

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import TABLE_ENDPOINT, TICKET_ENDPOINT
from ..helpers import ServiceNowClient

logger = getLogger()

# Table names for querying variables
ITEM_OPT_MTOM_TABLE = "sc_item_option_mtom"
ITEM_OPT_TABLE = "sc_item_option"
ITEM_OPT_NEW_TABLE = "item_option_new"


class GetVariablesParams(Params):
    sys_id: str = Param(
        description="Request Item System ID",
        primary=True,
        cef_types=["servicenow item sys id", "md5"],
    )


class GetVariablesOutput(PermissiveActionOutput):
    """
    Dynamic output for variables with example fields.
    """

    Additional_software_requirements: str | None = OutputField(
        alias="Additional software requirements"
    )
    Adobe_Acrobat: str | None = OutputField(alias="Adobe Acrobat")
    Adobe_Photoshop: str | None = OutputField(alias="Adobe Photoshop")
    Optional_Software: str | None = OutputField(alias="Optional Software")


class GetVariablesSummary(ActionOutput):
    """Summary for get variables action"""

    num_variables: int = OutputField(example_values=[1, 2, 5])


@app.view_handler(template="servicenow_get_variables.html")
def get_variables_view(outputs: list[GetVariablesOutput]) -> dict:
    """Transform get variables action results for HTML rendering."""
    results = []
    for output in outputs:
        ctx_result = {
            "data": [output.model_dump()],
            "param": {},
            "summary": {},
            "action_name": "get variables",
        }
        results.append(ctx_result)
    return {"results": results}


@app.action(
    description="Get variables for a ticket/record",
    action_type="investigate",
    read_only=True,
    verbose="The System ID for this action can be obtained by the below steps. Navigate to ServiceNow platform and enter sc_item_option_mtom.LIST in the search panel in the left navigation pane. This opens the list of variables in a new tab. Click on the Parent Item and it will open the Requested Item page. Click on the Options menu available in the top-left corner of the page and select the 'Copy sys_id' option to copy the required System ID.",
    summary_type=GetVariablesSummary,
    view_handler=get_variables_view,
)
def get_variables(
    params: GetVariablesParams, soar: SOARClient[GetVariablesSummary], asset: Asset
) -> GetVariablesOutput:
    """
    Get variables for a ticket/record
    """
    logger.info(f"Getting variables for request item sys_id: {params.sys_id}")

    helper = ServiceNowClient(asset)

    # Step 1: Query sc_item_option_mtom table
    endpoint = TABLE_ENDPOINT.format(ITEM_OPT_MTOM_TABLE)
    request_params = {
        "sysparm_query": f"request_item={params.sys_id}",
        "sysparm_display_value": "all",
    }

    logger.debug(f"Querying {endpoint} with params: {request_params}")

    try:
        response = helper.make_rest_call(
            endpoint=endpoint,
            params=request_params,
        )
    except Exception as e:
        logger.error(f"Failed to query {ITEM_OPT_MTOM_TABLE}: {e}")
        raise ActionFailure(f"Failed to query {ITEM_OPT_MTOM_TABLE}: {e}") from e

    # Check if results were returned
    if not response.get("result"):
        error_msg = (
            f"No data found for the requested item having System ID: {params.sys_id}"
        )
        logger.error(error_msg)
        raise ActionFailure(error_msg)

    # Step 2: Process each item to build variables dictionary
    variables = {}

    for item in response["result"]:
        # Extract sc_item_option value
        item_option_value = _extract_reference_value(item.get("sc_item_option"))

        if not item_option_value:
            error_msg = f"Error occurred while fetching variable info for the System ID: {params.sys_id}"
            logger.error(error_msg)
            raise ActionFailure(error_msg)

        logger.debug(f"Processing item_option_value: {item_option_value}")

        # Fetch variable value and question ID from sc_item_option table
        variable_value, question_id = _fetch_variable_details(
            helper=helper,
            item_option_value=item_option_value,
            sys_id=params.sys_id,
        )

        # Fetch question text from item_option_new table (if question_id is not empty)
        if question_id:
            question_text = _fetch_question_text(
                helper=helper,
                question_id=question_id,
                item_option_value=item_option_value,
                sys_id=params.sys_id,
            )
        else:
            # No question available for this variable - use empty string as key
            question_text = ""

        # Add to variables dictionary
        variables[question_text] = variable_value

    soar.set_summary(GetVariablesSummary(num_variables=len(variables)))
    soar.set_message(f"Num variables: {len(variables)}")

    return GetVariablesOutput(**variables)


def _extract_reference_value(reference: Any) -> str:
    """Return the sys_id from a ServiceNow reference field."""
    if isinstance(reference, dict):
        return reference.get("value") or ""
    if isinstance(reference, str):
        return reference
    return ""


def _fetch_variable_details(
    helper: ServiceNowClient,
    item_option_value: str,
    sys_id: str,
) -> tuple[str, str]:
    """Fetch variable value and question ID from sc_item_option table"""
    endpoint = TICKET_ENDPOINT.format(ITEM_OPT_TABLE, item_option_value)
    logger.debug(f"Fetching variable details from: {endpoint}")

    try:
        response = helper.make_rest_call(
            endpoint=endpoint,
            params={"sysparm_display_value": "all"},
        )
    except Exception as e:
        logger.error(f"Failed to fetch variable details: {e}")
        raise ActionFailure(f"Failed to fetch variable details: {e}") from e

    # Check if result and value are present
    if not response.get("result") or response["result"].get("value") is None:
        error_msg = (
            f"Error occurred while fetching the value for variable having System ID: "
            f"{item_option_value} for the request item having System ID: {sys_id}"
        )
        logger.error(error_msg)
        raise ActionFailure(error_msg)

    variable_value = response["result"]["value"]

    # Check for item_option_new (question ID reference)
    item_option_new = response["result"].get("item_option_new")
    if item_option_new is None or (
        isinstance(item_option_new, dict) and not item_option_new.get("value")
    ):
        error_msg = (
            f"Error occurred while fetching the question ID for variable having System ID: "
            f"{item_option_value} for the request item having System ID: {sys_id}"
        )
        logger.error(error_msg)
        raise ActionFailure(error_msg)

    question_id = _extract_reference_value(item_option_new)
    if not question_id:
        logger.debug("No question available for this variable")
        return variable_value, ""

    logger.debug(
        f"Found variable_value: '{variable_value}', question_id: '{question_id}'"
    )

    return variable_value, question_id


def _fetch_question_text(
    helper: ServiceNowClient,
    question_id: str,
    item_option_value: str,
    sys_id: str,
) -> str:
    """Fetch question text from item_option_new table"""
    endpoint = TICKET_ENDPOINT.format(ITEM_OPT_NEW_TABLE, question_id)
    logger.debug(f"Fetching question text from: {endpoint}")

    try:
        response = helper.make_rest_call(endpoint=endpoint)
    except Exception as e:
        logger.error(f"Failed to fetch question text: {e}")
        raise ActionFailure(f"Failed to fetch question text: {e}") from e

    # Check if result and question_text are present
    if not response.get("result") or response["result"].get("question_text") is None:
        error_msg = (
            f"Error occurred while fetching the question text for question having System ID: "
            f"{question_id}, variable having System ID: {item_option_value} for the "
            f"request item having System ID: {sys_id}"
        )
        logger.error(error_msg)
        raise ActionFailure(error_msg)

    question_text = response["result"]["question_text"]
    logger.debug(f"Found question_text: '{question_text}'")

    return question_text
