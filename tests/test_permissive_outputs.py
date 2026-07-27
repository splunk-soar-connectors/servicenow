# Copyright (c) 2026 Splunk Inc.
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
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions.add_comment import AddCommentOutput
from src.actions.add_work_note import AddWorkNoteOutput
from src.actions.create_ticket import CreateTicketOutput
from src.actions.describe_catalog_item import (
    CatalogsOutput,
    CategoriesOutput as CatalogItemCategoriesOutput,
    CategoryOutput as CatalogItemCategoryOutput,
    CategoryWithActiveOutput,
    ChildrenOutput,
    ClientScriptOutput,
    DescribeCatalogItemOutput,
    OnloadOutput,
    VariablesOutput,
    describe_catalog_item_view,
)
from src.actions.describe_service_catalog import (
    CategoriesOutput,
    DescribeServiceCatalogOutput,
    ItemsOutput,
    describe_service_catalog_view,
)
from src.actions.get_variables import GetVariablesOutput
from src.actions.get_ticket import GetTicketOutput
from src.actions.list_categories import CategoryOutput
from src.actions.list_service_catalogs import ServiceCatalogOutput
from src.actions.list_services import ServiceItemOutput
from src.actions.list_tickets import ListTicketOutput
from src.actions.query_users import QueryUserOutput, QueryUsersParams
from src.actions.request_catalog_item import RequestCatalogItemOutput
from src.actions import run_query as run_query_module
from src.actions.run_query import RunQueryOutput
from src.actions.search_sources import (
    DataOutput,
    FieldsOutput,
    MetadataOutput,
    RecordsOutput,
    SearchResultsOutput,
    SearchSourcesOutput,
    SourcesOutput,
)
from src.actions.update_ticket import UpdateTicketOutput
from src.actions import query_users as query_users_module
from src.output_models import DisplayValueOutput


RAW_RECORD_OUTPUTS = [
    AddCommentOutput,
    AddWorkNoteOutput,
    CreateTicketOutput,
    GetTicketOutput,
    UpdateTicketOutput,
    ListTicketOutput,
    RunQueryOutput,
    QueryUserOutput,
    RequestCatalogItemOutput,
    CategoryOutput,
    ServiceCatalogOutput,
    ServiceItemOutput,
    DescribeServiceCatalogOutput,
    CategoriesOutput,
    ItemsOutput,
]

DESCRIBE_CATALOG_ITEM_OUTPUTS = [
    DescribeCatalogItemOutput,
    CatalogsOutput,
    CatalogItemCategoryOutput,
    CategoryWithActiveOutput,
    CatalogItemCategoriesOutput,
    ClientScriptOutput,
    OnloadOutput,
    VariablesOutput,
    ChildrenOutput,
]

SEARCH_SOURCES_OUTPUTS = [
    SearchSourcesOutput,
    SearchResultsOutput,
    RecordsOutput,
    DataOutput,
    MetadataOutput,
    FieldsOutput,
    SourcesOutput,
    DisplayValueOutput,
]

EXPECTED_SCALAR_DATAPATHS = {
    QueryUserOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.user_name",
        "action_result.data.*.name",
        "action_result.data.*.email",
    },
    CategoryOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.title",
        "action_result.data.*.sys_name",
    },
    ServiceCatalogOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.title",
        "action_result.data.*.sys_name",
    },
    ServiceItemOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.name",
        "action_result.data.*.short_description",
        "action_result.data.*.catalogs.*",
    },
    DescribeServiceCatalogOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.title",
        "action_result.data.*.categories.*.sys_id",
        "action_result.data.*.items.*.sys_id",
    },
    CategoriesOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.title",
        "action_result.data.*.sys_name",
    },
    ItemsOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.name",
        "action_result.data.*.short_description",
        "action_result.data.*.sc_catalogs",
    },
    DescribeCatalogItemOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.name",
        "action_result.data.*.short_description",
        "action_result.data.*.variables.*.id",
    },
    CatalogsOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.title",
    },
    CatalogItemCategoryOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.title",
    },
    CategoryWithActiveOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.title",
    },
    CatalogItemCategoriesOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.title",
        "action_result.data.*.category.sys_id",
    },
    ClientScriptOutput: {
        "action_result.data.*.onLoad.*.sys_id",
        "action_result.data.*.onLoad.*.type",
    },
    OnloadOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.type",
    },
    VariablesOutput: {
        "action_result.data.*.id",
        "action_result.data.*.name",
        "action_result.data.*.children.*.id",
    },
    ChildrenOutput: {
        "action_result.data.*.id",
        "action_result.data.*.name",
    },
    SearchSourcesOutput: {
        "action_result.data.*.result_count",
        "action_result.data.*.search_results.*.records.*.data.number.display",
        "action_result.data.*.sources.*.sys_id",
    },
    SearchResultsOutput: {
        "action_result.data.*.fields.*.name",
        "action_result.data.*.records.*.sys_id",
        "action_result.data.*.term",
    },
    RecordsOutput: {
        "action_result.data.*.data.number.display",
        "action_result.data.*.metadata.title",
        "action_result.data.*.table",
    },
    DataOutput: {
        "action_result.data.*.number.display",
        "action_result.data.*.sys_id.value",
    },
    MetadataOutput: {
        "action_result.data.*.title",
    },
    FieldsOutput: {
        "action_result.data.*.label",
        "action_result.data.*.name",
    },
    SourcesOutput: {
        "action_result.data.*.sys_id",
        "action_result.data.*.source_table",
        "action_result.data.*.name.display",
    },
    DisplayValueOutput: {
        "action_result.data.*.display",
        "action_result.data.*.value",
    },
    GetVariablesOutput: {
        "action_result.data.*.Additional software requirements",
        "action_result.data.*.Adobe Acrobat",
        "action_result.data.*.Adobe Photoshop",
        "action_result.data.*.Optional Software",
    },
}


@pytest.mark.parametrize("output_cls", RAW_RECORD_OUTPUTS)
def test_raw_record_outputs_pass_through_custom_and_reference_fields(output_cls):
    reference_dict = {
        "display_value": "Service Desk",
        "link": "https://example.service-now.com/api/now/table/sys_user_group/group-id",
        "value": "group-id",
    }
    record = {
        "sys_id": "ticket-sys-id",
        "number": "INC0000001",
        "short_description": "Network issue",
        "u_custom_field": "tenant-specific value",
        "assignment_group": reference_dict,
        "caller_id": "caller-sys-id",
    }

    assert output_cls(**record).model_dump() == record


@pytest.mark.parametrize(
    ("output_cls", "dropped_fields"),
    [
        (
            AddCommentOutput,
            {
                "assigned_to",
                "assignment_group",
                "caller_id",
                "ci",
                "closed_by",
                "company",
                "cost_center",
                "department",
                "depreciation",
                "location",
                "manufacturer",
                "model",
                "model_category",
                "opened_by",
                "product_catalog_item",
                "resolved_by",
                "stockroom",
                "sys_domain",
                "vendor",
            },
        ),
        (
            AddWorkNoteOutput,
            {
                "assigned_to",
                "assignment_group",
                "caller_id",
                "ci",
                "closed_by",
                "company",
                "model",
                "model_category",
                "opened_by",
                "resolved_by",
                "stockroom",
                "sys_domain",
                "vendor",
            },
        ),
        (
            CreateTicketOutput,
            {
                "assigned_to",
                "assignment_group",
                "business_service",
                "caller_id",
                "ci",
                "closed_by",
                "cmdb_ci",
                "company",
                "cost_center",
                "department",
                "depreciation",
                "location",
                "managed_by",
                "model",
                "model_category",
                "opened_by",
                "resolved_by",
                "rfc",
                "service_offering",
                "stockroom",
                "support_group",
                "supported_by",
                "sys_domain",
                "vendor",
            },
        ),
        (
            GetTicketOutput,
            {
                "assigned_to",
                "assignment_group",
                "business_service",
                "caller_id",
                "ci",
                "closed_by",
                "cmdb_ci",
                "company",
                "cost_center",
                "department",
                "depreciation",
                "location",
                "manufacturer",
                "model",
                "model_category",
                "opened_by",
                "problem_id",
                "product_catalog_item",
                "resolved_by",
                "stockroom",
                "sys_domain",
                "vendor",
            },
        ),
        (
            UpdateTicketOutput,
            {
                "assigned_to",
                "assignment_group",
                "business_service",
                "caller_id",
                "ci",
                "closed_by",
                "cmdb_ci",
                "company",
                "cost_center",
                "department",
                "depreciation",
                "location",
                "model",
                "model_category",
                "opened_by",
                "owned_by",
                "problem_id",
                "resolved_by",
                "sys_domain",
                "vendor",
            },
        ),
        (
            ListTicketOutput,
            {
                "assigned_to",
                "assignment_group",
                "business_service",
                "caller_id",
                "closed_by",
                "cmdb_ci",
                "company",
                "location",
                "opened_by",
                "parent_incident",
                "problem_id",
                "request_item",
                "resolved_by",
                "rfc",
                "sys_domain",
            },
        ),
        (
            RunQueryOutput,
            {
                "assigned_to",
                "assignment_group",
                "business_service",
                "caller_id",
                "closed_by",
                "cmdb_ci",
                "company",
                "location",
                "opened_by",
                "parent_incident",
                "problem_id",
                "resolved_by",
                "rfc",
                "sys_domain",
            },
        ),
        (
            QueryUserOutput,
            {
                "department",
                "sys_domain",
            },
        ),
        (
            RequestCatalogItemOutput,
            {
                "opened_by",
                "requested_for",
                "sys_domain",
            },
        ),
        (
            CategoryOutput,
            {
                "homepage_renderer",
                "module",
                "parent",
                "sc_catalog",
                "sys_package",
                "sys_scope",
            },
        ),
        (
            ServiceCatalogOutput,
            {
                "sys_package",
                "sys_scope",
            },
        ),
        (
            ServiceItemOutput,
            {
                "category",
                "delivery_plan",
                "model",
                "sys_package",
                "sys_scope",
                "template",
                "vendor",
                "workflow",
            },
        ),
        (
            DescribeServiceCatalogOutput,
            {
                "sys_package",
                "sys_scope",
            },
        ),
        (
            CategoriesOutput,
            {
                "homepage_renderer",
                "module",
                "parent",
                "sc_catalog",
                "sys_package",
                "sys_scope",
            },
        ),
        (
            ItemsOutput,
            {
                "category",
                "delivery_plan",
                "model",
                "sys_package",
                "sys_scope",
                "template",
                "vendor",
                "workflow",
            },
        ),
    ],
)
def test_reference_fields_are_not_declared_on_raw_record_outputs(
    output_cls, dropped_fields
):
    assert dropped_fields.isdisjoint(output_cls.model_fields)


@pytest.mark.parametrize("output_cls", RAW_RECORD_OUTPUTS)
def test_raw_record_outputs_keep_key_scalar_datapaths(output_cls):
    paths = {field["data_path"] for field in output_cls._to_json_schema()}
    expected_paths = EXPECTED_SCALAR_DATAPATHS.get(
        output_cls,
        {
            "action_result.data.*.sys_id",
            "action_result.data.*.number",
            "action_result.data.*.short_description",
        },
    )

    assert expected_paths <= paths


@pytest.mark.parametrize("output_cls", DESCRIBE_CATALOG_ITEM_OUTPUTS)
def test_describe_catalog_item_outputs_keep_key_scalar_datapaths(output_cls):
    paths = {field["data_path"] for field in output_cls._to_json_schema()}

    assert EXPECTED_SCALAR_DATAPATHS[output_cls] <= paths


@pytest.mark.parametrize("output_cls", DESCRIBE_CATALOG_ITEM_OUTPUTS)
def test_describe_catalog_item_outputs_pass_through_unknown_fields(output_cls):
    record = {"u_custom_field": "tenant-specific value"}

    assert output_cls(**record).model_dump() == record


@pytest.mark.parametrize("output_cls", SEARCH_SOURCES_OUTPUTS)
def test_search_sources_outputs_keep_key_scalar_datapaths(output_cls):
    paths = {field["data_path"] for field in output_cls._to_json_schema()}

    assert EXPECTED_SCALAR_DATAPATHS[output_cls] <= paths


@pytest.mark.parametrize("output_cls", SEARCH_SOURCES_OUTPUTS)
def test_search_sources_outputs_pass_through_unknown_fields(output_cls):
    record = {"u_custom_field": "tenant-specific value"}

    assert output_cls(**record).model_dump() == record


def test_get_variables_output_keeps_declared_alias_datapaths():
    paths = {field["data_path"] for field in GetVariablesOutput._to_json_schema()}

    assert EXPECTED_SCALAR_DATAPATHS[GetVariablesOutput] <= paths


def test_get_variables_output_passes_through_dynamic_question_keys():
    record = {
        "What software do you need?": "Adobe Acrobat",
        "Cost center": "SEC-100",
        "": "new dependant item",
    }

    assert GetVariablesOutput(**record).model_dump() == record


@pytest.mark.parametrize(
    "output_cls", [CreateTicketOutput, GetTicketOutput, UpdateTicketOutput]
)
def test_attachment_details_pass_through(output_cls):
    attachment = {
        "file_name": "evidence.txt",
        "download_link": "https://example.service-now.com/api/now/attachment/file",
        "u_attachment_custom": "custom attachment metadata",
    }
    record = {"sys_id": "ticket-sys-id", "attachment_details": [attachment]}

    assert output_cls(**record).model_dump()["attachment_details"] == [attachment]


def test_get_ticket_journal_sections_pass_through():
    record = {
        "sys_id": "ticket-sys-id",
        "comments_section": ["comment one"],
        "worknotes_section": ["work note one"],
    }

    assert GetTicketOutput(**record).model_dump() == record


def test_run_query_output_preserves_raw_record_data_flat():
    record = {
        "sys_id": "query-record-id",
        "number": "INC0000001",
        "u_custom_field": "tenant-specific value",
        "assigned_to": {
            "link": "https://example.service-now.com/api/now/table/sys_user/user-id",
            "value": "user-id",
        },
    }

    output = RunQueryOutput(**record)
    assert output.model_dump() == record

    view_handler = getattr(
        run_query_module.run_query_view,
        "__wrapped__",
        run_query_module.run_query_view,
    )
    assert view_handler([output]) == {
        "results": [
            {
                "data": [record],
                "param": {},
                "summary": {},
                "action_name": "run query",
            }
        ]
    }


def test_query_users_returns_flat_records_and_strips_user_password(monkeypatch):
    users = [
        {
            "sys_id": "user-id",
            "user_name": "admin",
            "name": "System Administrator",
            "email": "admin@example.com",
            "department": {
                "link": "https://example.service-now.com/api/now/table/cmn_department/department-id",
                "value": "department-id",
            },
            "sys_domain": "global",
            "u_custom_field": "tenant-specific value",
            "user_password": "secret",  # pragma: allowlist secret
        }
    ]

    class FakeHelper:
        def __init__(self, asset):
            self.asset = asset

        def paginator(self, endpoint, payload=None, limit=None):
            assert endpoint == "/table/sys_user"
            assert payload == {"sysparm_query": "user_name=admin"}
            assert limit == 100
            return users

    class FakeSoar:
        def __init__(self):
            self.summary = None
            self.message = None

        def set_summary(self, summary):
            self.summary = summary

        def set_message(self, message):
            self.message = message

    monkeypatch.setattr("src.helpers.ServiceNowClient", FakeHelper)
    soar = FakeSoar()
    handler = getattr(
        query_users_module.query_users, "__wrapped__", query_users_module.query_users
    )

    outputs = handler(
        QueryUsersParams(
            query="sysparm_query=user_name=admin",
            user_id="",
            username="",
            max_results=100,
        ),
        soar,
        SimpleNamespace(),
    )

    assert [output.model_dump() for output in outputs] == [
        {
            "sys_id": "user-id",
            "user_name": "admin",
            "name": "System Administrator",
            "email": "admin@example.com",
            "department": {
                "link": "https://example.service-now.com/api/now/table/cmn_department/department-id",
                "value": "department-id",
            },
            "sys_domain": "global",
            "u_custom_field": "tenant-specific value",
        }
    ]
    assert soar.summary.total_users == 1
    assert soar.message == "Total users: 1"

    view_handler = getattr(
        query_users_module.query_users_view,
        "__wrapped__",
        query_users_module.query_users_view,
    )
    assert view_handler(outputs) == {
        "results": [
            {
                "data": {
                    "users": [
                        {
                            "sys_id": "user-id",
                            "user_name": "admin",
                            "name": "System Administrator",
                            "email": "admin@example.com",
                            "department": {
                                "link": "https://example.service-now.com/api/now/table/cmn_department/department-id",
                                "value": "department-id",
                            },
                            "sys_domain": "global",
                            "u_custom_field": "tenant-specific value",
                        }
                    ]
                },
                "param": {},
                "summary": {},
                "action_name": "query users",
            }
        ]
    }


def test_describe_service_catalog_nested_records_pass_through():
    category_reference = {
        "link": "https://example.service-now.com/api/now/table/sc_catalog/catalog-id",
        "value": "catalog-id",
    }
    item_reference = {
        "link": "https://example.service-now.com/api/now/table/sc_category/category-id",
        "value": "category-id",
    }
    record = {
        "sys_id": "catalog-id",
        "title": "Service Catalog",
        "u_catalog_custom": "catalog custom",
        "sys_package": "package-id",
        "categories": [
            {
                "sys_id": "category-id",
                "title": "Hardware",
                "sc_catalog": category_reference,
                "u_category_custom": "category custom",
            }
        ],
        "items": [
            {
                "sys_id": "item-id",
                "name": "Laptop",
                "category": item_reference,
                "delivery_plan": "delivery-plan-id",
                "u_item_custom": "item custom",
            }
        ],
    }

    assert DescribeServiceCatalogOutput(**record).model_dump() == record


def test_describe_service_catalog_view_handles_raw_category_references():
    outputs = [
        DescribeServiceCatalogOutput(
            sys_id="catalog-id",
            items=[
                {
                    "sys_id": "item-with-dict-category",
                    "category": {"value": "category-id"},
                },
                {
                    "sys_id": "item-with-enriched-category",
                    "category": {"sys_id": "enriched-category-id"},
                },
                {
                    "sys_id": "item-with-string-category",
                    "category": "string-category-id",
                },
            ],
        )
    ]

    handler = getattr(
        describe_service_catalog_view,
        "__wrapped__",
        describe_service_catalog_view,
    )
    view_data = handler(outputs)["results"][0]["data"][0]["items"]

    assert [item["category_value"] for item in view_data] == [
        "category-id",
        "enriched-category-id",
        "string-category-id",
    ]


def test_describe_catalog_item_nested_response_passes_through_unknown_fields():
    record = {
        "sys_id": "item-id",
        "name": "Laptop",
        "short_description": "Request a laptop",
        "u_top_level_custom": "top",
        "catalogs": [
            {
                "sys_id": "catalog-id",
                "title": "Service Catalog",
                "u_catalog_custom": "catalog",
            }
        ],
        "category": {
            "sys_id": "category-id",
            "title": "Hardware",
            "u_category_custom": "category",
        },
        "categories": [
            {
                "active": True,
                "sys_id": "category-id",
                "title": "Hardware",
                "u_categories_custom": "categories",
                "category": {
                    "active": True,
                    "sys_id": "parent-category-id",
                    "title": "Parent",
                    "u_nested_category_custom": "nested category",
                },
            }
        ],
        "client_script": {
            "u_client_script_custom": "client script",
            "onLoad": [
                {
                    "sys_id": "script-id",
                    "type": "onLoad",
                    "u_onload_custom": "onload",
                }
            ],
        },
        "variables": [
            {
                "id": "variable-id",
                "name": "environment",
                "u_variable_custom": "variable",
                "children": [
                    {
                        "id": "child-id",
                        "name": "child variable",
                        "u_child_custom": "child",
                    }
                ],
            }
        ],
    }

    assert DescribeCatalogItemOutput(**record).model_dump() == record


def test_describe_catalog_item_view_populates_sys_id_param():
    handler = getattr(
        describe_catalog_item_view,
        "__wrapped__",
        describe_catalog_item_view,
    )

    result = handler([DescribeCatalogItemOutput(sys_id="item-id")])["results"][0]

    assert result["param"] == {"sys_id": "item-id"}
    assert result["data"][0]["sys_id"] == "item-id"


def test_search_sources_nested_response_passes_through_dynamic_fields():
    record = {
        "result_count": 1,
        "term": "Resolved",
        "u_search_custom": "top",
        "search_results": [
            {
                "label": "Incident",
                "term": "Resolved",
                "u_search_result_custom": "search result",
                "fields": [
                    {
                        "label": "Custom Field",
                        "name": "u_custom_field",
                        "u_field_metadata": "field metadata",
                    }
                ],
                "records": [
                    {
                        "sys_id": "record-id",
                        "table": "incident",
                        "u_record_custom": "record",
                        "metadata": {
                            "title": "INC0000001",
                            "u_metadata_custom": "metadata",
                        },
                        "data": {
                            "number": {
                                "display": "INC0000001",
                                "value": "INC0000001",
                                "u_display_custom": "display value",
                            },
                            "u_custom_field": {
                                "display": "Custom Display",
                                "value": "custom-value",
                            },
                            "u_plain_custom_field": "plain custom value",
                        },
                    }
                ],
            }
        ],
        "sources": [
            {
                "sys_id": "source-id",
                "source_table": "Incident",
                "u_source_custom": "source",
                "name": {
                    "display": "Tasks-Tickets",
                    "value": "Tasks-Tickets",
                    "u_name_custom": "name",
                },
            }
        ],
    }

    assert SearchSourcesOutput(**record).model_dump() == record
