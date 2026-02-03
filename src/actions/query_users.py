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

"""Query Users Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger

from .. import helpers
from ..app import app, Asset
from ..consts import TABLE_ENDPOINT


class QueryUsersParams(Params):
    query: str = Param(
        description="The query to run. e.g. sysparm_query=user_name=admin",
        required=False,
    )
    user_id: str = Param(description="Query by user system ID", required=False)
    username: str = Param(description="Query by username", required=False)
    max_results: float = Param(
        description="Max number of records to return", required=False, default=100
    )


class QueryUserOutput(PermissiveActionOutput):
    active: str = OutputField(example_values=["true"])
    avatar: str = OutputField(cef_types=["md5"])
    building: str
    calendar_integration: str = OutputField(example_values=["1"])
    city: str
    company: str
    cost_center: str
    country: str
    date_format: str
    default_perspective: str
    email: str = OutputField(cef_types=["email"], example_values=["abc@pqr.us"])
    employee_number: str
    enable_multifactor_authn: str = OutputField(example_values=["false"])
    failed_attempts: str = OutputField(example_values=["0"])
    first_name: str = OutputField(example_values=["System"])
    gender: str
    home_phone: str
    internal_integration_user: str = OutputField(example_values=["false"])
    introduction: str
    last_login: str = OutputField(example_values=["2022-06-24"])
    last_login_time: str = OutputField(example_values=["2022-06-24 22:32:15"])
    last_name: str = OutputField(example_values=["Administrator"])
    ldap_server: str
    location: str
    locked_out: str = OutputField(example_values=["false"])
    manager: str
    middle_name: str
    mobile_phone: str
    name: str = OutputField(example_values=["System Administrator"])
    notification: str = OutputField(example_values=["2"])
    password_needs_reset: str = OutputField(example_values=["false"])
    phone: str
    photo: str
    preferred_language: str
    roles: str = OutputField(example_values=["admin"])
    schedule: str
    source: str
    state: str
    street: str
    sys_class_name: str = OutputField(example_values=["sys_user"])
    sys_created_by: str = OutputField(example_values=["fred.luddy"])
    sys_created_on: str = OutputField(example_values=["2007-07-03 18:48:47"])
    sys_domain_path: str = OutputField(cef_types=["domain"])
    sys_id: str = OutputField(cef_types=["md5"])
    sys_mod_count: str = OutputField(example_values=["110"])
    sys_tags: str
    sys_updated_by: str = OutputField(example_values=["system"])
    sys_updated_on: str = OutputField(example_values=["2022-06-24 22:32:28"])
    time_format: str
    time_zone: str
    title: str = OutputField(example_values=["System Administrator"])
    user_name: str = OutputField(example_values=["admin"])
    vip: str = OutputField(example_values=["false"])
    web_service_access_only: str = OutputField(example_values=["false"])
    zip: str


class QueryUsersSummary(ActionOutput):
    """Summary for query users action"""

    total_users: int = OutputField(example_values=[1])


@app.view_handler(template="servicenow_query_users.html")
def query_users_view(outputs: list[QueryUserOutput]) -> dict:
    """Transform query users action results for HTML rendering."""
    ctx_result = {
        "data": {"users": [output.model_dump() for output in outputs]},
        "param": {},
        "summary": {},
        "action_name": "query users",
    }
    return {"results": [ctx_result]}


@app.action(
    description="Gets user data according to the specified query, username, or system ID",
    action_type="investigate",
    read_only=True,
    summary_type=QueryUsersSummary,
    view_handler=query_users_view,
)
def query_users(
    params: QueryUsersParams, soar: SOARClient[QueryUsersSummary], asset: Asset
) -> list[QueryUserOutput]:
    """Query users from ServiceNow sys_user table"""
    logger = getLogger()

    # Log input parameters
    logger.info(
        f"Querying users with params: query={params.query}, user_id={params.user_id}, username={params.username}, max_results={params.max_results}"
    )

    # Initialize helper
    helper = helpers.ServiceNowClient(asset)

    # Build the query parameter based on input
    query_param = params.query or ""

    if not query_param:
        # If no query provided, check for user_id or username
        if params.user_id:
            query_param = f"sysparm_query=sys_id={params.user_id}"
            logger.debug(f"Building query from user_id: {query_param}")
        elif params.username:
            query_param = f"sysparm_query=user_name={params.username}"
            logger.debug(f"Building query from username: {query_param}")

    # Set up the endpoint for sys_user table
    endpoint = TABLE_ENDPOINT.format("sys_user")

    # Build payload with query if present
    payload = {}
    if query_param:
        # Extract the query part from sysparm_query=... format if needed
        if query_param.startswith("sysparm_query="):
            query_value = query_param.replace("sysparm_query=", "")
            payload["sysparm_query"] = query_value
            logger.debug(f"Using query: {query_value}")
        else:
            # Assume it's already in the correct format
            payload["sysparm_query"] = query_param
            logger.debug(f"Using query: {query_param}")

    # Get the limit from parameters
    limit = int(params.max_results) if params.max_results else 100

    # Use paginator to fetch users
    logger.debug(f"Fetching users from endpoint: {endpoint} with limit: {limit}")
    users = helper.paginator(endpoint, payload=payload, limit=limit)

    if not users:
        logger.info("No users found")
        soar.set_summary(QueryUsersSummary(total_users=0))
        soar.set_message("No users found")
        return []

    # Strip sensitive field (user_password) from each user record
    for user in users:
        user.pop("user_password", None)

    logger.info(f"Successfully retrieved {len(users)} users")

    # Set summary and message
    soar.set_summary(QueryUsersSummary(total_users=len(users)))
    soar.set_message(f"Total users: {len(users)}")

    return [QueryUserOutput(**user) for user in users]
