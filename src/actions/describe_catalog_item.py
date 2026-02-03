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

"""Describe Catalog Item Action"""

from typing import Any
from pydantic import Field, field_validator
from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import CATALOG_ITEMS_ENDPOINT, SC_API_URI
from ..helpers import ServiceNowClient

logger = getLogger()


class DescribeCatalogItemParams(Params):
    sys_id: str = Param(
        description="SYS ID of an item",
        primary=True,
        cef_types=["servicenow item sys id", "md5"],
    )


class CatalogsOutput(PermissiveActionOutput):
    active: bool | None = None
    sys_id: str | None = OutputField(
        cef_types=["servicenow catalog sys id", "md5"],
    )
    title: str | None = OutputField(example_values=["Service Catalog"])


class CategoryOutput(PermissiveActionOutput):
    """Category reference without active field (for top-level category)"""

    sys_id: str | None = OutputField(
        cef_types=["servicenow category sys id", "md5"],
    )
    title: str | None = OutputField(example_values=["Can We Help You?"])


class CategoryWithActiveOutput(PermissiveActionOutput):
    """Category reference with active field (for nested categories)"""

    active: bool | None = None
    sys_id: str | None = OutputField(
        cef_types=["servicenow category sys id", "md5"],
    )
    title: str | None = OutputField(example_values=["Can We Help You?"])


class CategoriesOutput(PermissiveActionOutput):
    active: bool | None = None
    category: CategoryWithActiveOutput | None = None
    sys_id: str | None = OutputField(
        cef_types=["servicenow category sys id", "md5"],
    )
    title: str | None = OutputField(example_values=["Can We Help You?"])


class OnloadOutput(PermissiveActionOutput):
    appliesTo: str | None = OutputField(example_values=["item"])
    condition: str | None = None
    fieldName: str | None = None
    script: str | None = OutputField(
        example_values=[
            'function onLoad() {<br>\tvar stdChangeProducerSysId = getParmVal(\'std_change_producer\');<br>\tif (stdChangeProducerSysId) {<br>\t\tg_form.setValue(\'variables.std_change_producer\', stdChangeProducerSysId);<br>\t}<br>}<br>function getParmVal(name) {<br>name = name.replace(/[\\[]/, "\\\\\\[").replace(/[\\]]/, "\\\\\\]");<br>\tvar regexS = "[\\\\?&]" + name + "=([^&#]*)";<br>\tvar regex = new RegExp(regexS);<br>\tvar results = regex.exec(window.location.href);<br>\tif (results) {<br>\t\treturn unescape(results[1]);<br>\t} else {<br>\t\treturn \'\';<br>\t}<br>}<br>'
        ]
    )
    sys_id: str | None = None
    type: str | None = OutputField(example_values=["onLoad"])
    ui_type: str | None = OutputField(example_values=["Desktop"])
    variable_set: str | None = None


class ClientScriptOutput(PermissiveActionOutput):
    onLoad: list[OnloadOutput] = Field(default_factory=list)

    @field_validator("onLoad", mode="before")
    @classmethod
    def normalize_list_field(cls, v: Any) -> list:
        if isinstance(v, list):
            return v
        elif v:
            return [v] if isinstance(v, dict) else []
        else:
            return []


class ChildrenOutput(PermissiveActionOutput):
    attributes: str | None = OutputField(
        example_values=["edge_encryption_enabled=true"]
    )
    display_type: str | None = OutputField(example_values=["CheckBox"])
    displayvalue: str | None = OutputField(example_values=["false"])
    friendly_type: str | None = OutputField(example_values=["check_box"])
    help_text: str | None = None
    id: str | None = OutputField(example_values=["90b72d4b4f7b4200086eeed18110c701"])
    label: str | None = OutputField(example_values=["Adobe Acrobat"])
    mandatory: bool | None = None
    max_length: int | None = OutputField(example_values=[0])
    name: str | None = OutputField(example_values=["acrobat"])
    pricing_implications: bool | None = None
    read_only: bool | None = None
    render_label: bool | None = None
    type: int | None = OutputField(example_values=[7])
    value: str | None = None


class VariablesOutput(PermissiveActionOutput):
    attributes: str | None = OutputField(
        example_values=["edge_encryption_enabled=true"]
    )
    children: list[ChildrenOutput] = Field(default_factory=list)
    display_type: str | None = OutputField(example_values=["Multi Line Text"])
    displayvalue: str | None = None
    friendly_type: str | None = OutputField(example_values=["multi_line_text"])
    help_text: str | None = None
    id: str | None = OutputField(cef_types=["md5"])
    label: str | None = OutputField(
        example_values=["What is the reason for this Knowledge Base to be created?"]
    )
    macro: str | None = OutputField(example_values=["std_chg_retire_rp_buttons"])
    mandatory: bool | None = None
    max_length: int | None = OutputField(example_values=[0])
    name: str | None = OutputField(example_values=["request_reason"])
    read_only: bool | None = None
    ref_qualifier: str | None = OutputField(example_values=["retired=false^EQ"])
    reference: str | None = OutputField(example_values=["std_change_record_producer"])
    render_label: bool | None = None
    type: int | None = OutputField(example_values=[2])
    value: str | None = None

    @field_validator("children", mode="before")
    @classmethod
    def normalize_list_field(cls, v: Any) -> list:
        """
        Normalize list field.
        Handles list, dict, or empty input formats from the API.
        """
        if isinstance(v, list):
            return v
        elif v:
            return [v] if isinstance(v, dict) else []
        else:
            return []


class DescribeCatalogItemOutput(PermissiveActionOutput):
    catalogs: list[CatalogsOutput] = Field(default_factory=list)
    categories: list[CategoriesOutput] = Field(default_factory=list)
    category: CategoryOutput | None = None
    client_script: ClientScriptOutput | None = None
    content_type: str | None = None
    description: str | None = OutputField(
        example_values=[
            "<p>Here you can request a new Knowledge Base to be used. A Knowledge Base can be used to store Knowledge in an organization and anyone can request for a new one to be created.</p>"
        ]
    )
    icon: str | None = OutputField(example_values=["images/icons/catalog_item.gifx"])
    kb_article: str | None = None
    local_currency: str | None = OutputField(example_values=["USD"])
    localized_price: str | None = OutputField(example_values=["$600.00"])
    localized_recurring_price: str | None = OutputField(example_values=["$0.00"])
    mandatory_attachment: bool | None = None
    name: str | None = OutputField(example_values=["Request Knowledge Base"])
    order: int | None = OutputField(example_values=[0])
    picture: str | None = None
    price: str | None = OutputField(example_values=["$600.00"])
    price_currency: str | None = OutputField(example_values=["USD"])
    recurring_frequency: str | None = None
    recurring_price: str | None = OutputField(example_values=["$0.00"])
    recurring_price_currency: str | None = OutputField(example_values=["USD"])
    request_method: str | None = None
    short_description: str | None = OutputField(
        example_values=["Request for a Knowledge Base"]
    )
    show_delivery_time: bool | None = None
    show_price: bool | None = None
    show_quantity: bool | None = None
    show_wishlist: bool | None = None
    sys_class_name: str | None = OutputField(example_values=["sc_cat_item_producer"])
    sys_id: str | None = OutputField(
        cef_types=["servicenow item sys id", "md5"],
    )
    type: str | None = OutputField(example_values=["record_producer"])
    url: str | None = None
    variables: list[VariablesOutput] = Field(default_factory=list)
    visible_standalone: bool | None = None

    @field_validator("catalogs", "categories", "variables", mode="before")
    @classmethod
    def normalize_list_field(cls, v: Any) -> list:
        """
        Normalize list field.
        Handles list, dict, or empty input formats from the API.
        """
        if isinstance(v, list):
            return v
        elif v:
            return [v] if isinstance(v, dict) else []
        else:
            return []


@app.view_handler(template="servicenow_describe_catalog_item.html")
def describe_catalog_item_view(outputs: list[DescribeCatalogItemOutput]) -> dict:
    """Transform describe catalog item action results for HTML rendering."""
    results = []
    for output in outputs:
        ctx_result = {
            "data": [output.model_dump()],
            "param": {},
            "summary": {},
            "action_name": "describe catalog item",
        }
        results.append(ctx_result)
    return {"results": results}


@app.action(
    description="Fetches the details of a catalog item",
    action_type="investigate",
    read_only=True,
    view_handler=describe_catalog_item_view,
)
def describe_catalog_item(
    params: DescribeCatalogItemParams, soar: SOARClient, asset: Asset
) -> DescribeCatalogItemOutput:
    """Fetch details of a specific catalog item from ServiceNow"""
    logger.info(f"Fetching catalog item details for sys_id: {params.sys_id}")

    # Initialize helper
    helper = ServiceNowClient(asset)

    endpoint = CATALOG_ITEMS_ENDPOINT.format(params.sys_id)

    response = helper.make_rest_call(
        endpoint=endpoint,
        api_uri=SC_API_URI,
    )

    # Extract result from response
    result = response.get("result")

    if not result:
        error_msg = (
            f"No data found for the requested item having System ID: {params.sys_id}"
        )
        logger.error(error_msg)
        soar.set_message(error_msg)
        raise Exception(error_msg)

    logger.info(
        f"Successfully retrieved catalog item details for sys_id: {params.sys_id}"
    )

    # Set success message
    soar.set_message("Details fetched successfully")

    # Convert result to DescribeCatalogItemOutput and return
    catalog_item = DescribeCatalogItemOutput(**result)

    return catalog_item
