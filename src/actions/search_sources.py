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

"""Search Sources Action"""

from soar_sdk.abstract import SOARClient
from soar_sdk.params import Param, Params
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.logging import getLogger
from soar_sdk.exceptions import ActionFailure

from ..app import app, Asset
from ..consts import (
    SEARCH_SOURCES_ENDPOINT,
    SEARCH_DEFAULT_PAGE,
    SEARCH_MAX_LIMIT,
    MAX_PAGES,
)
from ..helpers import ServiceNowClient

logger = getLogger()


class SearchSourcesParams(Params):
    sysparm_term: str = Param(description="Search record for the given term")
    sysparm_search_sources: str = Param(
        description="SYS ID of search sources, Comma-separated list allowed",
        primary=True,
        cef_types=["servicenow ticket sysid"],
    )


class SearchSourcesSummary(ActionOutput):
    """Summary for search_sources action"""

    total_records: int = OutputField(example_values=[10, 50, 100])


class FieldsOutput(PermissiveActionOutput):
    label: str | None = OutputField(example_values=["Number"])
    label_plural: str | None = OutputField(example_values=["Numbers"])
    max_length: float | None = OutputField(example_values=[40])
    name: str | None = OutputField(example_values=["number"])
    reference: str | None = OutputField(example_values=["sys_user_group"])
    type: str | None = OutputField(example_values=["string"])


class DisplayValueOutput(PermissiveActionOutput):
    display: str | None = None
    value: str | None = None


class DataOutput(PermissiveActionOutput):
    """
    Data fields returned in search results.
    All fields use DisplayValueOutput for display/value pairs.
    """

    assignment_group: DisplayValueOutput | None = None
    caller_id: DisplayValueOutput | None = None
    category: DisplayValueOutput | None = None
    cmdb_ci: DisplayValueOutput | None = None
    number: DisplayValueOutput | None = None
    opened_at: DisplayValueOutput | None = None
    priority: DisplayValueOutput | None = None
    related_incidents: DisplayValueOutput | None = None
    resolution_code: DisplayValueOutput | None = None
    state: DisplayValueOutput | None = None
    sys_id: DisplayValueOutput | None = None


class MetadataOutput(PermissiveActionOutput):
    description: str | None = None
    thumbnail_url: str | None = None
    title: str | None = OutputField(example_values=["hello"])


class RecordsOutput(PermissiveActionOutput):
    data: DataOutput | None = None
    metadata: MetadataOutput | None = None
    record_class_name: str | None = OutputField(example_values=["incident"])
    record_url: str | None = OutputField(
        example_values=[
            "/incident.do?sys_id=test978221106401f1e99f11&sysparm_view=text_search"
        ]
    )
    sys_id: str | None = OutputField(example_values=["c673ettest97822119953af11"])
    table: str | None = OutputField(example_values=["incident"])


class SearchResultsOutput(PermissiveActionOutput):
    fields: list[FieldsOutput] | None = None
    label: str | None = OutputField(example_values=["Problem"])
    # limit and page are removed by pagination logic, so they must be optional
    limit: float | None = OutputField(example_values=[20])
    page: float | None = OutputField(example_values=[1])
    query: str | None = OutputField(example_values=["123TEXTQUEtest=Fix Applied"])
    record_count: float | None = None
    records: list[RecordsOutput] | None = None
    sys_id: str | None = OutputField(example_values=["test897862996401f1e3f1990e"])
    term: str | None = OutputField(example_values=["Resolved"])


class SourcesOutput(PermissiveActionOutput):
    """Search source configuration details"""

    condition: DisplayValueOutput | None = None
    name: DisplayValueOutput | None = None
    source_table: str | None = OutputField(example_values=["Problem"])
    sys_id: str | None = OutputField(
        cef_types=["servicenow ticket sysid"],
        example_values=["test8699964099f153af0e99"],
    )


class SearchSourcesOutput(PermissiveActionOutput):
    result_count: float | None = None
    search_results: list[SearchResultsOutput] | None = None
    sources: list[SourcesOutput] | None = None
    term: str | None = OutputField(example_values=["Resolved"])


@app.action(
    description="Search for records across multiple tables",
    action_type="investigate",
    summary_type=SearchSourcesSummary,
    verbose="To find the list of search source IDs for the <b>sysparm_search_sources</b> parameter, follow this path in servicenow UI: All > Workspace Experience > Administration > Search Sources. Once there, click with two fingers/right click on the source name and copy the sys_id.",
)
def search_sources(
    params: SearchSourcesParams, soar: SOARClient[SearchSourcesSummary], asset: Asset
) -> SearchSourcesOutput:
    """Search records across ServiceNow text search sources."""
    logger.info("Starting search_sources action")

    client = ServiceNowClient(asset)

    sysparm_term = params.sysparm_term
    sysparm_search_sources = params.sysparm_search_sources

    search_sources_list = _parse_search_sources(sysparm_search_sources)

    if not search_sources_list:
        raise ActionFailure("Please provide valid inputs for sysparm_search_sources")

    sysparm_search_sources_str = ",".join(search_sources_list)

    result_data = _search_sources_with_pagination(
        client, sysparm_term, sysparm_search_sources_str
    )

    total_records = int(result_data.get("result_count", 0))
    logger.info(f"Search completed successfully. Total records: {total_records}")
    soar.set_summary(SearchSourcesSummary(total_records=total_records))

    return SearchSourcesOutput(**result_data)


def _parse_search_sources(search_sources_str: str) -> list[str]:
    """Parse a comma-separated source ID list."""
    # Split by comma, strip whitespace, remove empty values, remove duplicates
    sources = [x.strip() for x in set(search_sources_str.split(",")) if x.strip()]
    return sources


def _search_sources_with_pagination(
    client: ServiceNowClient, sysparm_term: str, sysparm_search_sources: str
) -> dict:
    """Aggregate paginated ServiceNow text search results across sources."""
    params = {
        "sysparm_term": sysparm_term,
        "sysparm_search_sources": sysparm_search_sources,
        "sysparm_page": SEARCH_DEFAULT_PAGE,
        "sysparm_limit": SEARCH_MAX_LIMIT,
    }

    # Track pagination state
    aggregate_result = None
    search_results_by_sys_id = {}
    result_length = 0
    first_call = True
    total_result_count_page_limit = 0

    # Paginate through results
    while True:
        try:
            response = client.make_rest_call(
                SEARCH_SOURCES_ENDPOINT,
                params=params,
            )
        except Exception as e:
            raise ActionFailure(f"Failed to search sources: {e}") from e

        result = response.get("result", {})

        if not result:
            raise ActionFailure("Invalid response from ServiceNow - no result data")

        total_item_count = int(result.get("result_count", 0))

        # Process search results - remove page-local metadata
        search_results = result.get("search_results", [])

        for search_result in search_results:
            search_result.pop("limit", None)
            search_result.pop("page", None)
            # Count records in this search result
            result_length += len(search_result.get("records", []))

        # On first call, initialize aggregate_result with the full result structure
        # Also calculate total pages to handle empty records due to ACLs
        if first_call:
            aggregate_result = result
            search_results_by_sys_id = _index_search_results_by_sys_id(
                aggregate_result.get("search_results", [])
            )
            # ServiceNow returns up to 20 records per page by default
            total_result_count_page_limit = total_item_count // 20
            first_call = False
        else:
            # On subsequent calls, extend records for each search source by sys_id.
            _merge_search_results_by_sys_id(
                aggregate_result, search_results_by_sys_id, search_results
            )

        # Check if we've fetched all results or reached max pages
        if (
            total_item_count <= result_length
            or params["sysparm_page"] >= total_result_count_page_limit + 1
            or params["sysparm_page"] >= MAX_PAGES
        ):
            break

        # Move to next page
        params["sysparm_page"] += 1

    return aggregate_result or {}


def _index_search_results_by_sys_id(search_results: list[dict]) -> dict[str, dict]:
    search_results_by_sys_id = {}
    for search_result in search_results:
        source_sys_id = _get_search_result_sys_id(search_result)
        search_results_by_sys_id[source_sys_id] = search_result
    return search_results_by_sys_id


def _merge_search_results_by_sys_id(
    aggregate_result: dict | None,
    search_results_by_sys_id: dict[str, dict],
    search_results: list[dict],
) -> None:
    if aggregate_result is None:
        raise ActionFailure(
            "Invalid response from ServiceNow - no aggregate result data"
        )

    aggregate_search_results = aggregate_result.setdefault("search_results", [])

    for search_result in search_results:
        source_sys_id = _get_search_result_sys_id(search_result)
        records = search_result.get("records", [])

        if source_sys_id in search_results_by_sys_id:
            search_results_by_sys_id[source_sys_id].setdefault("records", []).extend(
                records
            )
            continue

        search_results_by_sys_id[source_sys_id] = search_result
        aggregate_search_results.append(search_result)


def _get_search_result_sys_id(search_result: dict) -> str:
    source_sys_id = search_result.get("sys_id")
    if not source_sys_id:
        raise ActionFailure(
            "Invalid response from ServiceNow - search result missing sys_id"
        )
    return source_sys_id
