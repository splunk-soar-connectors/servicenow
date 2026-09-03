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

from ..app import app, Asset
from ..consts import DEFAULT_MAX_LIMIT, TABLE_ENDPOINT
from ..helpers import validate_positive_integer
from ..servicenow_client import ServiceNowClient


class QueryUsersParams(Params):
    query: str = Param(
        description="The query to run. e.g. sysparm_query=user_name=admin",
        required=False,
    )
    user_id: str = Param(description="Query by user system ID", required=False)
    username: str = Param(description="Query by username", required=False)
    max_results: int = Param(
        description="Max number of records to return", required=False, default=100
    )


class QueryUserOutput(PermissiveActionOutput):
    user_name: str | None = OutputField(
        column_name="USER NAME", example_values=["admin"]
    )
    name: str | None = OutputField(
        column_name="NAME", example_values=["System Administrator"]
    )
    email: str | None = OutputField(
        column_name="EMAIL", cef_types=["email"], example_values=["abc@pqr.us"]
    )
    active: str | None = OutputField(column_name="ACTIVE", example_values=["true"])
    title: str | None = OutputField(
        column_name="TITLE", example_values=["System Administrator"]
    )
    first_name: str | None = OutputField(
        column_name="FIRST NAME", example_values=["System"]
    )
    last_name: str | None = OutputField(
        column_name="LAST NAME", example_values=["Administrator"]
    )
    sys_id: str | None = OutputField(column_name="SYS ID", cef_types=["md5"])
    last_login: str | None = OutputField(
        column_name="LAST LOGIN", example_values=["2022-06-24"]
    )
    avatar: str | None = OutputField(cef_types=["md5"])
    building: str | None = None
    calendar_integration: str | None = OutputField(example_values=["1"])
    city: str | None = None
    company: str | None = None
    cost_center: str | None = None
    country: str | None = None
    date_format: str | None = None
    default_perspective: str | None = None
    employee_number: str | None = None
    enable_multifactor_authn: str | None = OutputField(example_values=["false"])
    failed_attempts: str | None = OutputField(example_values=["0"])
    gender: str | None = None
    home_phone: str | None = None
    internal_integration_user: str | None = OutputField(example_values=["false"])
    introduction: str | None = None
    last_login_time: str | None = OutputField(example_values=["2022-06-24 22:32:15"])
    ldap_server: str | None = None
    location: str | None = None
    locked_out: str | None = OutputField(example_values=["false"])
    manager: str | None = None
    middle_name: str | None = None
    mobile_phone: str | None = None
    notification: str | None = OutputField(example_values=["2"])
    password_needs_reset: str | None = OutputField(example_values=["false"])
    phone: str | None = None
    photo: str | None = None
    preferred_language: str | None = None
    roles: str | None = OutputField(example_values=["admin"])
    schedule: str | None = None
    source: str | None = None
    state: str | None = None
    street: str | None = None
    sys_class_name: str | None = OutputField(example_values=["sys_user"])
    sys_created_by: str | None = OutputField(example_values=["fred.luddy"])
    sys_created_on: str | None = OutputField(example_values=["2007-07-03 18:48:47"])
    sys_domain_path: str | None = OutputField(cef_types=["domain"])
    sys_mod_count: str | None = OutputField(example_values=["110"])
    sys_tags: str | None = None
    sys_updated_by: str | None = OutputField(example_values=["system"])
    sys_updated_on: str | None = OutputField(example_values=["2022-06-24 22:32:28"])
    time_format: str | None = None
    time_zone: str | None = None
    vip: str | None = OutputField(example_values=["false"])
    web_service_access_only: str | None = OutputField(example_values=["false"])
    zip: str | None = None


class QueryUsersSummary(ActionOutput):
    """Summary for query users action"""

    total_users: int = OutputField(example_values=[1])


@app.action(
    description="Gets user data according to the specified query, username, or system ID",
    action_type="investigate",
    read_only=True,
    summary_type=QueryUsersSummary,
    render_as="table",
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

    client = ServiceNowClient(asset)

    query_param = params.query or ""

    if not query_param:
        # If no query provided, check for user_id or username
        if params.user_id:
            query_param = f"sysparm_query=sys_id={params.user_id}"
            logger.debug(f"Building query from user_id: {query_param}")
        elif params.username:
            query_param = f"sysparm_query=user_name={params.username}"
            logger.debug(f"Building query from username: {query_param}")

    endpoint = TABLE_ENDPOINT.format("sys_user")

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

    limit = validate_positive_integer(
        "max_results", params.max_results, DEFAULT_MAX_LIMIT
    )

    logger.debug(f"Fetching users from endpoint: {endpoint} with limit: {limit}")
    users = client.paginator(endpoint, payload=payload, limit=limit)

    if not users:
        logger.info("No users found")
        soar.set_summary(QueryUsersSummary(total_users=0))
        soar.set_message("No users found")
        return []

    # Strip sensitive field (user_password) from each user record
    for user in users:
        user.pop("user_password", None)

    logger.info(f"Successfully retrieved {len(users)} users")

    soar.set_summary(QueryUsersSummary(total_users=len(users)))
    soar.set_message(f"Total users: {len(users)}")

    return [QueryUserOutput(**user) for user in users]
