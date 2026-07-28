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
import inspect
from pathlib import Path

import pytest
from soar_sdk.models.view import ViewContext

from src.actions.describe_catalog_item import DescribeCatalogItemOutput
from src.actions.describe_service_catalog import DescribeServiceCatalogOutput
from src.actions.get_variables import GetVariablesOutput
from src.app import app

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"

VIEW_OUTPUTS = {
    "describe_catalog_item": [
        DescribeCatalogItemOutput(sys_id="item-sys-id", name="Laptop")
    ],
    "describe_service_catalog": [
        DescribeServiceCatalogOutput(
            sys_id="catalog-sys-id",
            items=[{"sys_id": "item-sys-id", "category": {"value": "category-sys-id"}}],
        )
    ],
    "get_variables": [
        GetVariablesOutput(
            sys_id="ritm-sys-id", **{"Optional Software": "Adobe Acrobat"}
        )
    ],
}

TABLE_ACTIONS = {
    "create_ticket",
    "list_categories",
    "list_service_catalogs",
    "list_services",
    "list_tickets",
    "query_users",
    "request_catalog_item",
    "run_query",
}

EXPECTED_TABLE_COLUMNS = {
    "create_ticket": [
        "TICKET NUMBER",
        "DESCRIPTION",
        "SHORT DESCRIPTION",
        "CATEGORY",
        "SYS ID",
        "SEVERITY",
        "PRIORITY",
        "OPENED ON",
        "CLOSED ON",
    ],
    "list_categories": [
        "TITLE",
        "DESCRIPTION",
        "ACTIVE",
        "SYS ID",
        "ORDER",
        "CREATED ON",
        "UPDATED ON",
    ],
    "list_service_catalogs": [
        "TITLE",
        "DESCRIPTION",
        "ACTIVE",
        "SYS ID",
        "BACKGROUND COLOR",
        "CREATED ON",
        "UPDATED ON",
    ],
    "list_services": [
        "NAME",
        "SHORT DESCRIPTION",
        "ITEM SYS ID",
        "CATALOG SYS ID",
    ],
    "list_tickets": [
        "TICKET NUMBER",
        "DESCRIPTION",
        "SHORT DESCRIPTION",
        "ID",
        "SEVERITY",
        "PRIORITY",
        "OPENED ON",
        "CLOSED ON",
    ],
    "query_users": [
        "USER NAME",
        "NAME",
        "EMAIL",
        "ACTIVE",
        "TITLE",
        "FIRST NAME",
        "LAST NAME",
        "SYS ID",
        "LAST LOGIN",
    ],
    "request_catalog_item": [
        "REQUEST NUMBER",
        "SHORT DESCRIPTION",
        "PRIORITY",
        "PRICE",
        "DUE DATE",
        "ASSIGNED TO",
    ],
    "run_query": [
        "TICKET NUMBER",
        "DESCRIPTION",
        "SHORT DESCRIPTION",
        "ID",
        "SEVERITY",
        "PRIORITY",
        "OPENED ON",
        "CLOSED ON",
    ],
}


def _call_view_handler(handler, outputs):
    view_context = ViewContext(
        QS={},
        container=123,
        app=456,
        no_connection=False,
        google_maps_key=False,
    )
    wrapped = getattr(handler, "__wrapped__", handler)
    parameters = list(inspect.signature(wrapped).parameters)
    if parameters and parameters[0] in {"context", "view_context"}:
        return wrapped(view_context, outputs)
    return wrapped(outputs)


@pytest.mark.parametrize("identifier", sorted(VIEW_OUTPUTS))
def test_custom_actions_register_sdk_view_handlers(identifier):
    action = app.actions_manager.get_action(identifier)

    assert action.meta.render_as == "custom"
    assert action.meta.view_handler is not None


@pytest.mark.parametrize("identifier", sorted(TABLE_ACTIONS))
def test_flat_actions_use_standard_table_rendering(identifier):
    action = app.actions_manager.get_action(identifier)

    assert action.meta.render_as == "table"
    assert action.meta.view_handler is None


@pytest.mark.parametrize("identifier", sorted(EXPECTED_TABLE_COLUMNS))
def test_standard_table_actions_declare_widget_columns(identifier):
    output_cls = app.actions_manager.get_action(identifier).meta.output
    columns = [
        {
            "name": field["column_name"].upper(),
            "order": field["column_order"],
        }
        for field in output_cls._to_json_schema()
        if "column_name" in field and "column_order" in field
    ]

    actual_columns = [col["name"] for col in sorted(columns, key=lambda col: col["order"])]

    assert actual_columns == EXPECTED_TABLE_COLUMNS[identifier]


@pytest.mark.parametrize("identifier", sorted(VIEW_OUTPUTS))
def test_custom_view_handlers_return_sdk_template_context(identifier):
    action = app.actions_manager.get_action(identifier)

    template_context = _call_view_handler(
        action.meta.view_handler, VIEW_OUTPUTS[identifier]
    )

    assert set(template_context) == {"results"}
    assert template_context["results"]
    for result in template_context["results"]:
        assert set(result) == {"data"}


def test_describe_catalog_item_view_keeps_sys_id_on_output_row():
    action = app.actions_manager.get_action("describe_catalog_item")

    template_context = _call_view_handler(
        action.meta.view_handler,
        [DescribeCatalogItemOutput(sys_id="item-sys-id")],
    )

    result = template_context["results"][0]
    assert result["data"][0]["sys_id"] == "item-sys-id"


def test_get_variables_view_keeps_sys_id_on_output_row():
    action = app.actions_manager.get_action("get_variables")

    template_context = _call_view_handler(
        action.meta.view_handler,
        [
            GetVariablesOutput(
                sys_id="ritm-sys-id", **{"Optional Software": "Adobe Acrobat"}
            )
        ],
    )

    result = template_context["results"][0]
    assert result == {
        "data": [{"sys_id": "ritm-sys-id", "Optional Software": "Adobe Acrobat"}]
    }


def test_custom_view_templates_use_sdk_container_context():
    legacy_container_refs = []

    for template_path in TEMPLATE_DIR.glob("servicenow_*.html"):
        for line_number, line in enumerate(template_path.read_text().splitlines(), 1):
            if "context_menu(" in line and "{{ container.id }}" in line:
                legacy_container_refs.append(f"{template_path.name}:{line_number}")

    assert legacy_container_refs == []


def test_custom_view_templates_do_not_use_unavailable_escapejs_filter():
    offenders = []

    for template_path in TEMPLATE_DIR.glob("servicenow_*.html"):
        for line_number, line in enumerate(template_path.read_text().splitlines(), 1):
            if "|escapejs" in line:
                offenders.append(f"{template_path.name}:{line_number}")

    assert offenders == []


def test_context_menu_values_use_jinja_safe_json_escaping():
    unescaped_lines = []

    for template_path in TEMPLATE_DIR.glob("servicenow_*.html"):
        for line_number, line in enumerate(template_path.read_text().splitlines(), 1):
            if "context_menu(" not in line:
                continue
            if "'value':'{{" in line:
                unescaped_lines.append(f"{template_path.name}:{line_number}")
            if (
                "'value':{{" in line
                and '|default("") |tojson|forceescape' not in line
                and '|default("")|tojson|forceescape' not in line
            ):
                unescaped_lines.append(f"{template_path.name}:{line_number}")

    assert unescaped_lines == []
