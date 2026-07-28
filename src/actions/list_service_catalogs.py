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

"""List Service Catalogs Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import SC_CATALOG_ENDPOINT, DEFAULT_MAX_LIMIT
from ..helpers import ServiceNowClient

logger = getLogger()


class ListServiceCatalogsParams(Params):
    max_results: int = Param(
        description="Max number of service catalogs to return",
        required=False,
        default=100,
    )


class ServiceCatalogOutput(PermissiveActionOutput):
    """ServiceNow service catalog details"""

    title: str | None = OutputField(
        column_name="TITLE", example_values=["test_catalog"]
    )
    description: str | None = OutputField(column_name="DESCRIPTION")
    active: str | None = OutputField(column_name="ACTIVE", example_values=["true"])
    sys_id: str | None = OutputField(
        column_name="SYS ID",
        cef_types=["servicenow catalog sys id", "md5"],
    )
    background_color: str | None = OutputField(
        column_name="BACKGROUND COLOR", example_values=["white"]
    )
    sys_created_on: str | None = OutputField(
        column_name="CREATED ON", example_values=["2019-10-11 06:12:27"]
    )
    sys_updated_on: str | None = OutputField(
        column_name="UPDATED ON", example_values=["2019-10-11 06:12:27"]
    )
    desktop_continue_shopping: str | None = None
    desktop_home_page: str | None = None
    desktop_image: str | None = None
    editors: str | None = None
    enable_wish_list: str | None = OutputField(example_values=["false"])
    manager: str | None = None
    sys_class_name: str | None = OutputField(example_values=["sc_catalog"])
    sys_created_by: str | None = OutputField(example_values=["admin"])
    sys_mod_count: str | None = OutputField(example_values=["0"])
    sys_name: str | None = OutputField(example_values=["test_catalog"])
    sys_policy: str | None = None
    sys_tags: str | None = None
    sys_update_name: str | None = None
    sys_updated_by: str | None = OutputField(example_values=["admin"])


class ListServiceCatalogsSummary(ActionOutput):
    """Summary for list service catalogs action"""

    service_catalogs_returned: int = OutputField(example_values=[2])


@app.action(
    description="Get a list of catalogs",
    action_type="investigate",
    read_only=True,
    summary_type=ListServiceCatalogsSummary,
    render_as="table",
)
def list_service_catalogs(
    params: ListServiceCatalogsParams,
    soar: SOARClient[ListServiceCatalogsSummary],
    asset: Asset,
) -> list[ServiceCatalogOutput]:
    """List service catalogs from ServiceNow"""
    logger.progress(f"Listing service catalogs with max_results: {params.max_results}")

    helper = ServiceNowClient(asset)
    limit = params.max_results if params.max_results else DEFAULT_MAX_LIMIT

    service_catalogs = helper.paginator(SC_CATALOG_ENDPOINT, limit=limit)
    if not service_catalogs:
        logger.info("No service catalogs found")
        soar.set_summary(ListServiceCatalogsSummary(service_catalogs_returned=0))
        soar.set_message("No service catalogs found")
        return []

    logger.info(f"Successfully retrieved {len(service_catalogs)} service catalogs")

    # Set summary and message
    soar.set_summary(
        ListServiceCatalogsSummary(service_catalogs_returned=len(service_catalogs))
    )
    soar.set_message(f"Successfully retrieved {len(service_catalogs)} service catalogs")

    # Convert raw data to ServiceCatalogOutput objects and wrap in response
    return [ServiceCatalogOutput(**catalog) for catalog in service_catalogs]
