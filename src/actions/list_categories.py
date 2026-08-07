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

"""List Categories Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import SC_CATEGORY_ENDPOINT, DEFAULT_MAX_LIMIT
from ..helpers import ServiceNowClient, validate_positive_integer

logger = getLogger()


class ListCategoriesParams(Params):
    max_results: int = Param(
        description="Max number of categories to return",
        default=100,
        required=False,
    )


class CategoryOutput(PermissiveActionOutput):
    """ServiceNow category details"""

    title: str | None = OutputField(
        column_name="TITLE",
        example_values=["Template Management", "Hardware", "Software"],
    )
    description: str | None = OutputField(
        column_name="DESCRIPTION",
        example_values=[
            "Propose a new Standard Change Template. Modify or Retire an existing Standard Change Template."
        ],
    )
    active: str | None = OutputField(
        column_name="ACTIVE", example_values=["true", "false"]
    )
    sys_id: str | None = OutputField(
        column_name="SYS ID",
        cef_types=["servicenow category sys id", "md5"],
    )
    order: str | None = OutputField(column_name="ORDER", example_values=["0", "1", "2"])
    sys_created_on: str | None = OutputField(
        column_name="CREATED ON", example_values=["2015-06-24 04:53:17"]
    )
    sys_updated_on: str | None = OutputField(
        column_name="UPDATED ON", example_values=["2015-06-24 04:54:20"]
    )
    entitlement_script: str | None = None
    header_icon: str | None = None
    homepage_image: str | None = None
    icon: str | None = None
    image: str | None = None
    location: str | None = None
    mobile_hide_description: str | None = OutputField(example_values=["false", "true"])
    mobile_picture: str | None = None
    mobile_subcategory_render_type: str | None = OutputField(example_values=["list"])
    roles: str | None = None
    show_in_cms: str | None = OutputField(example_values=["false", "true"])
    sys_class_name: str | None = OutputField(example_values=["sc_category"])
    sys_created_by: str | None = OutputField(example_values=["admin", "system"])
    sys_mod_count: str | None = OutputField(example_values=["0", "1", "2"])
    sys_name: str | None = OutputField(
        example_values=["Template Management", "Hardware", "Software"]
    )
    sys_policy: str | None = None
    sys_tags: str | None = None
    sys_update_name: str | None = OutputField(
        example_values=["sc_category_00728916937002002dcef157b67ffb6d"]
    )
    sys_updated_by: str | None = OutputField(example_values=["admin", "system"])


class ListCategoriesSummary(ActionOutput):
    """Summary for list categories action"""

    categories_returned: int = OutputField(example_values=[5, 10, 50])


@app.action(
    description="Get a list of service categories",
    action_type="investigate",
    read_only=True,
    summary_type=ListCategoriesSummary,
    render_as="table",
)
def list_categories(
    params: ListCategoriesParams, soar: SOARClient[ListCategoriesSummary], asset: Asset
) -> list[CategoryOutput]:
    """List service categories from ServiceNow"""
    logger.info(f"Listing categories with max_results: {params.max_results}")

    client = ServiceNowClient(asset)

    limit = validate_positive_integer(
        "max_results", params.max_results, DEFAULT_MAX_LIMIT
    )

    logger.debug(f"Fetching categories from endpoint: {SC_CATEGORY_ENDPOINT}")
    service_categories = client.paginator(SC_CATEGORY_ENDPOINT, limit=limit)

    if not service_categories:
        logger.info("No categories found")
        soar.set_summary(ListCategoriesSummary(categories_returned=0))
        soar.set_message("No categories found")
        return []

    logger.info(f"Successfully retrieved {len(service_categories)} categories")

    soar.set_summary(ListCategoriesSummary(categories_returned=len(service_categories)))
    soar.set_message(f"Successfully retrieved {len(service_categories)} categories")

    return [CategoryOutput(**cat) for cat in service_categories]
