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

"""Describe Service Catalog Action"""

from pydantic import Field
from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.exceptions import ActionFailure
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import SC_CATALOG_ENDPOINT, SC_CATEGORY_ENDPOINT, DEFAULT_MAX_LIMIT
from ..helpers import ServiceNowClient

logger = getLogger()


class DescribeServiceCatalogParams(Params):
    sys_id: str = Param(
        description="SYS ID of a catalog",
        primary=True,
        cef_types=["servicenow catalog sys id", "md5"],
    )
    max_results: int = Param(
        description="Max number of service catalog items to return",
        required=False,
        default=100,
    )


class CategoriesOutput(PermissiveActionOutput):
    active: str | None = OutputField(example_values=["true"])
    description: str | None = OutputField(
        example_values=[
            "Propose a new Standard Change Template. Modify or Retire an existing  Standard Change Template."
        ]
    )
    entitlement_script: str | None = None
    header_icon: str | None = None
    homepage_image: str | None = None
    icon: str | None = None
    image: str | None = None
    location: str | None = None
    mobile_hide_description: str | None = OutputField(example_values=["false"])
    mobile_picture: str | None = None
    mobile_subcategory_render_type: str | None = OutputField(example_values=["list"])
    order: str | None = OutputField(example_values=["0"])
    roles: str | None = None
    show_in_cms: str | None = OutputField(example_values=["false"])
    sys_class_name: str | None = OutputField(example_values=["sc_category"])
    sys_created_by: str | None = OutputField(example_values=["admin"])
    sys_created_on: str | None = OutputField(example_values=["2015-06-24 04:53:17"])
    sys_id: str | None = OutputField(
        cef_types=["servicenow category sys id", "md5"],
    )
    sys_mod_count: str | None = OutputField(example_values=["1"])
    sys_name: str | None = OutputField(example_values=["Template Management"])
    sys_policy: str | None = None
    sys_tags: str | None = None
    sys_update_name: str | None = OutputField(
        example_values=["sc_category_00728916937002002dcef157b67ffb6d"]
    )
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2015-06-24 04:54:20"])
    title: str | None = OutputField(example_values=["Template Management"])


class ItemsOutput(PermissiveActionOutput):
    active: str | None = OutputField(example_values=["true"])
    availability: str | None = OutputField(example_values=["on_desktop"])
    billable: str | None = OutputField(example_values=["false"])
    catalogs: list[str] = Field(default_factory=list)
    content_type: str | None = None
    cost: str | None = OutputField(example_values=["0"])
    custom_cart: str | None = None
    delivery_plan_script: str | None = None
    delivery_time: str | None = OutputField(example_values=["1970-01-03 00:00:00"])
    description: str | None = OutputField(
        example_values=[
            '<p class="p1"><font size="2"><span class="s1">Request an existing Standard Change Template is made unavailable when it is no longer required or no longer acceptable as a Standard Change. This will be confirmed by your Change Management team.</span></font></p>'
        ]
    )
    display_price_property: str | None = OutputField(example_values=["non_zero"])
    entitlement_script: str | None = None
    group: str | None = None
    hide_sp: str | None = OutputField(example_values=["true"])
    icon: str | None = OutputField(example_values=["images/icons/catalog_item.gifx"])
    ignore_price: str | None = OutputField(example_values=["true"])
    image: str | None = None
    kb_article: str | None = None
    list_price: str | None = OutputField(example_values=["0"])
    local_currency: str | None = OutputField(example_values=["USD"])
    localized_price: str | None = OutputField(example_values=["$139.99"])
    localized_recurring_price: str | None = OutputField(example_values=["$0.00"])
    location: str | None = None
    mandatory_attachment: str | None = OutputField(example_values=["false"])
    meta: str | None = None
    mobile_hide_price: str | None = OutputField(example_values=["false"])
    mobile_picture: str | None = None
    mobile_picture_type: str | None = OutputField(
        example_values=["use_desktop_picture"]
    )
    name: str | None = OutputField(example_values=["Retire a Standard Change Template"])
    no_attachment_v2: str | None = OutputField(example_values=["false"])
    no_cart: str | None = OutputField(example_values=["false"])
    no_cart_v2: str | None = OutputField(example_values=["false"])
    no_delivery_time_v2: str | None = OutputField(example_values=["false"])
    no_order: str | None = OutputField(example_values=["false"])
    no_order_now: str | None = OutputField(example_values=["false"])
    no_proceed_checkout: str | None = OutputField(example_values=["false"])
    no_quantity: str | None = OutputField(example_values=["false"])
    no_quantity_v2: str | None = OutputField(example_values=["false"])
    no_search: str | None = OutputField(example_values=["false"])
    no_wishlist_v2: str | None = OutputField(example_values=["false"])
    omit_price: str | None = OutputField(example_values=["false"])
    order: str | None = OutputField(example_values=["30"])
    ordered_item_link: str | None = None
    picture: str | None = None
    preview: str | None = OutputField(
        example_values=[
            'JavaScript: popupOpenStandard("com.glideapp.servicecatalog_cat_item_view.do?v=1&sysparm_id=011f117a9f3002002920bde8132e7020&sysparm_preview=true", "summary");'
        ]
    )
    price: str | None = OutputField(example_values=["0"])
    price_currency: str | None = OutputField(example_values=["USD"])
    recurring_frequency: str | None = None
    recurring_price: str | None = OutputField(example_values=["0"])
    recurring_price_currency: str | None = OutputField(example_values=["USD"])
    request_method: str | None = None
    roles: str | None = None
    sc_catalogs: str | None = None
    sc_ic_item_staging: str | None = None
    sc_ic_version: str | None = None
    short_description: str | None = None
    show_variable_help_on_load: str | None = OutputField(example_values=["false"])
    start_closed: str | None = OutputField(example_values=["false"])
    sys_class_name: str | None = OutputField(example_values=["sc_cat_item_producer"])
    sys_created_by: str | None = OutputField(example_values=["admin"])
    sys_created_on: str | None = OutputField(example_values=["2015-06-25 20:19:46"])
    sys_id: str | None = OutputField(
        cef_types=["servicenow item sys id", "md5"],
    )
    sys_mod_count: str | None = OutputField(example_values=["21"])
    sys_name: str | None = OutputField(
        example_values=["Retire a Standard Change Template"]
    )
    sys_policy: str | None = None
    sys_tags: str | None = None
    sys_update_name: str | None = OutputField(
        example_values=["sc_cat_item_producer_011f117a9f3002002920bde8132e7020"]
    )
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2017-11-02 22:38:21"])
    type: str | None = OutputField(example_values=["item"])
    url: str | None = None
    use_sc_layout: str | None = OutputField(example_values=["true"])
    visible_bundle: str | None = OutputField(example_values=["true"])
    visible_guide: str | None = OutputField(example_values=["true"])
    visible_standalone: str | None = OutputField(example_values=["true"])


class DescribeServiceCatalogOutput(PermissiveActionOutput):
    active: str | None = OutputField(example_values=["true"])
    background_color: str | None = OutputField(example_values=["#FFFFFF"])
    categories: list[CategoriesOutput] = Field(default_factory=list)
    description: str | None = OutputField(example_values=["Service Catalog - IT Now"])
    desktop_continue_shopping: str | None = None
    desktop_home_page: str | None = None
    desktop_image: str | None = None
    editors: str | None = None
    enable_wish_list: str | None = OutputField(example_values=["false"])
    items: list[ItemsOutput] = Field(default_factory=list)
    manager: str | None = None
    sys_class_name: str | None = OutputField(example_values=["sc_catalog"])
    sys_created_by: str | None = OutputField(example_values=["admin"])
    sys_created_on: str | None = OutputField(example_values=["2013-09-19 11:03:11"])
    sys_id: str | None = OutputField(
        cef_types=["servicenow catalog sys id", "md5"],
    )
    sys_mod_count: str | None = OutputField(example_values=["48"])
    sys_name: str | None = OutputField(example_values=["Service Catalog"])
    sys_policy: str | None = None
    sys_tags: str | None = None
    sys_update_name: str | None = OutputField(
        example_values=["sc_catalog_e0d08b13c3330100c8b837659bba8fb4"]
    )
    sys_updated_by: str | None = OutputField(example_values=["admin"])
    sys_updated_on: str | None = OutputField(example_values=["2016-06-16 05:19:58"])
    title: str | None = OutputField(example_values=["Service Catalog"])


def _reference_value(value: object) -> object:
    if isinstance(value, dict):
        return value.get("value") or value.get("sys_id") or value.get("display_value")
    return value


@app.view_handler(template="servicenow_describe_service_catalog.html")
def describe_service_catalog_view(outputs: list[DescribeServiceCatalogOutput]) -> dict:
    """Transform describe service catalog action results for HTML rendering."""
    data = []
    for output in outputs:
        output_data = output.model_dump()
        for item in output_data.get("items", []):
            item["category_value"] = _reference_value(item.get("category"))
        data.append(output_data)
    return {"results": [{"data": data}]}


@app.action(
    description="Fetches the details of a catalog",
    action_type="investigate",
    read_only=True,
    view_handler=describe_service_catalog_view,
)
def describe_service_catalog(
    params: DescribeServiceCatalogParams, soar: SOARClient, asset: Asset
) -> DescribeServiceCatalogOutput:
    """Describe a service catalog with its categories and items"""
    logger.info(f"Fetching catalog details for sys_id: {params.sys_id}")

    # Initialize helper
    helper = ServiceNowClient(asset)

    # 1. Fetch catalog details
    logger.debug(f"Querying catalog endpoint with sys_id: {params.sys_id}")
    request_params = {"sysparm_query": f"sys_id={params.sys_id}"}

    catalog_response = helper.make_rest_call(
        SC_CATALOG_ENDPOINT,
        params=request_params,
    )

    # Validate catalog exists
    if not catalog_response.get("result"):
        raise ActionFailure("Please enter a valid value for 'sys_id' parameter")

    # Get catalog data (first element of result array)
    catalog_data = catalog_response["result"][0]
    logger.debug(f"Found catalog: {catalog_data.get('title', 'Unknown')}")

    # 2. Fetch categories for this catalog
    logger.debug(f"Fetching categories for catalog: {params.sys_id}")
    categories_params = {"sysparm_query": f"sc_catalog={params.sys_id}"}

    categories_response = helper.make_rest_call(
        SC_CATEGORY_ENDPOINT,
        params=categories_params,
    )

    categories = categories_response.get("result", [])
    logger.debug(f"Found {len(categories)} categories")

    # 3. Fetch items for this catalog
    limit = params.max_results if params.max_results else DEFAULT_MAX_LIMIT
    logger.debug(f"Fetching up to {limit} catalog items")

    items = helper.fetch_catalog_items(
        catalog_sys_id=params.sys_id,
        limit=limit,
        split_catalogs=False,
    )
    logger.debug(f"Found {len(items)} catalog items")

    # 4. Construct final output
    # Merge catalog data with categories and items
    final_data = {**catalog_data}
    final_data["categories"] = categories
    final_data["items"] = items

    logger.info(
        f"Successfully fetched catalog details with {len(categories)} categories and {len(items)} items"
    )
    soar.set_message("Details fetched successfully")

    return DescribeServiceCatalogOutput(**final_data)
