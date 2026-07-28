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

"""List Services Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import DEFAULT_MAX_LIMIT
from ..helpers import ServiceNowClient

logger = getLogger()


class ListServicesParams(Params):
    catalog_sys_id: str = Param(
        description="SYS ID of a catalog",
        required=False,
        primary=True,
        cef_types=["servicenow catalog sys id", "md5"],
    )
    category_sys_id: str = Param(
        description="SYS ID of a catergory",
        required=False,
        primary=True,
        cef_types=["servicenow category sys id", "md5"],
    )
    search_text: str = Param(
        description="Text pattern to search over",
        required=False,
    )
    max_results: int = Param(
        description="Max number of items to return", required=False, default=100
    )


class ServiceItemOutput(PermissiveActionOutput):
    """ServiceNow catalog item details"""

    name: str = OutputField(
        column_name="Name", example_values=["Retire a Standard Change Template"]
    )
    short_description: str = OutputField(column_name="Short Description")
    sys_id: str = OutputField(column_name="Item SYS ID", cef_types=["md5"])
    catalogs: list[str] | None = OutputField(
        column_name="Catalog SYS ID", cef_types=["md5"]
    )
    active: str = OutputField(example_values=["true"])
    availability: str = OutputField(example_values=["on_desktop"])
    billable: str = OutputField(example_values=["false"])
    cost: str = OutputField(example_values=["0"])
    custom_cart: str = ""
    delivery_plan_script: str = ""
    delivery_time: str = OutputField(example_values=["1970-01-03 00:00:00"])
    description: str = OutputField(
        example_values=[
            '<p class="p1"><font size="2"><span class="s1">Request an existing Standard Change Template is made unavailable when it is no longer required or no longer acceptable as a Standard Change. This will be confirmed by your Change Management team.</span></font></p>'
        ]
    )
    display_price_property: str = OutputField(example_values=["non_zero"])
    entitlement_script: str = ""
    group: str = ""
    hide_sp: str = OutputField(example_values=["true"])
    icon: str = ""
    ignore_price: str = OutputField(example_values=["true"])
    image: str = ""
    list_price: str = OutputField(example_values=["0"])
    location: str = ""
    mandatory_attachment: str = OutputField(example_values=["false"])
    meta: str = ""
    mobile_hide_price: str = OutputField(example_values=["false"])
    mobile_picture: str = ""
    mobile_picture_type: str = OutputField(example_values=["use_desktop_picture"])
    no_attachment_v2: str = OutputField(example_values=["false"])
    no_cart: str = OutputField(example_values=["false"])
    no_cart_v2: str = OutputField(example_values=["false"])
    no_delivery_time_v2: str = OutputField(example_values=["false"])
    no_order: str = OutputField(example_values=["false"])
    no_order_now: str = OutputField(example_values=["false"])
    no_proceed_checkout: str = OutputField(example_values=["false"])
    no_quantity: str = OutputField(example_values=["false"])
    no_quantity_v2: str = OutputField(example_values=["false"])
    no_search: str = OutputField(example_values=["false"])
    no_wishlist_v2: str = OutputField(example_values=["false"])
    omit_price: str = OutputField(example_values=["false"])
    order: str = OutputField(example_values=["30"])
    ordered_item_link: str = ""
    picture: str = ""
    preview: str = OutputField(
        example_values=[
            'JavaScript: popupOpenStandard("com.glideapp.servicecatalog_cat_item_view.do?v=1&sysparm_id=011f117a9f3002002920bde8132e7020&sysparm_preview=true", "summary");'
        ]
    )
    price: str = OutputField(example_values=["0"])
    recurring_frequency: str = ""
    recurring_price: str = OutputField(example_values=["0"])
    request_method: str = ""
    roles: str = ""
    sc_catalogs: str = OutputField(cef_types=["md5"])
    sc_ic_item_staging: str = ""
    sc_ic_version: str = ""
    show_variable_help_on_load: str = OutputField(example_values=["false"])
    start_closed: str = OutputField(example_values=["false"])
    sys_class_name: str = OutputField(example_values=["sc_cat_item_producer"])
    sys_created_by: str = OutputField(example_values=["admin"])
    sys_created_on: str = OutputField(example_values=["2015-06-25 20:19:46"])
    sys_mod_count: str = OutputField(example_values=["21"])
    sys_name: str = OutputField(example_values=["Retire a Standard Change Template"])
    sys_policy: str = ""
    sys_tags: str = ""
    sys_update_name: str = OutputField(
        example_values=["sc_cat_item_producer_011f117a9f3002002920bde8132e7020"]
    )
    sys_updated_by: str = OutputField(example_values=["admin"])
    sys_updated_on: str = OutputField(example_values=["2017-11-02 22:38:21"])
    type: str = OutputField(example_values=["item"])
    use_sc_layout: str = OutputField(example_values=["true"])
    visible_bundle: str = OutputField(example_values=["true"])
    visible_guide: str = OutputField(example_values=["true"])
    visible_standalone: str = OutputField(example_values=["true"])


class ListServicesSummary(ActionOutput):
    """Summary for list services action"""

    services_returned: int = OutputField(example_values=[3])


@app.action(
    description="Get a list of items",
    action_type="investigate",
    read_only=True,
    verbose="The 'search text' parameter will search the text in the 'Name', 'Display Name', 'Short Description', and 'Description' fields of an item.",
    summary_type=ListServicesSummary,
    render_as="table",
)
def list_services(
    params: ListServicesParams, soar: SOARClient[ListServicesSummary], asset: Asset
) -> list[ServiceItemOutput]:
    """List catalog items/services from ServiceNow"""
    logger.info(
        f"Listing services with max_results: {params.max_results}, "
        f"catalog_sys_id: {params.catalog_sys_id}, "
        f"category_sys_id: {params.category_sys_id}, "
        f"search_text: {params.search_text}"
    )

    # Initialize helper
    helper = ServiceNowClient(asset)

    # Get the limit from parameters
    limit = params.max_results if params.max_results else DEFAULT_MAX_LIMIT

    # Use helper function to fetch catalog items
    services = helper.fetch_catalog_items(
        catalog_sys_id=params.catalog_sys_id,
        category_sys_id=params.category_sys_id,
        search_text=params.search_text,
        limit=limit,
    )

    if not services:
        logger.info("No services found")
        soar.set_summary(ListServicesSummary(services_returned=0))

        # Provide specific error message if filters were used
        if params.catalog_sys_id or params.category_sys_id or params.search_text:
            message = "No data found for the given input parameters"
        else:
            message = "No data found"

        soar.set_message(message)
        soar.set_status("failed")
        return []

    logger.info(f"Successfully retrieved {len(services)} services")

    # Set summary and message
    soar.set_summary(ListServicesSummary(services_returned=len(services)))
    soar.set_message(f"Successfully retrieved {len(services)} services")

    # Convert raw data to ServiceItemOutput objects and wrap in response
    return [ServiceItemOutput(**service) for service in services]
