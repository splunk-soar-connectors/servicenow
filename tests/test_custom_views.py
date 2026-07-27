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

from src.actions.create_ticket import CreateTicketOutput
from src.actions.describe_catalog_item import DescribeCatalogItemOutput
from src.actions.describe_service_catalog import DescribeServiceCatalogOutput
from src.actions.get_variables import GetVariablesOutput
from src.actions.list_categories import CategoryOutput
from src.actions.list_service_catalogs import ServiceCatalogOutput
from src.actions.list_services import ServiceItemOutput
from src.actions.query_users import QueryUserOutput
from src.actions.run_query import RunQueryOutput
from src.app import app

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"

VIEW_OUTPUTS = {
    "create_ticket": [CreateTicketOutput(sys_id="ticket-sys-id", number="INC0000001")],
    "describe_catalog_item": [
        DescribeCatalogItemOutput(sys_id="item-sys-id", name="Laptop")
    ],
    "describe_service_catalog": [
        DescribeServiceCatalogOutput(
            sys_id="catalog-sys-id",
            items=[{"sys_id": "item-sys-id", "category": {"value": "category-sys-id"}}],
        )
    ],
    "get_variables": [GetVariablesOutput(**{"Optional Software": "Adobe Acrobat"})],
    "list_categories": [CategoryOutput(sys_id="category-sys-id", title="Hardware")],
    "list_service_catalogs": [
        ServiceCatalogOutput(sys_id="catalog-sys-id", title="Service Catalog")
    ],
    "list_services": [
        ServiceItemOutput(
            sys_id="item-sys-id",
            name="Laptop",
            catalogs="catalog-one,catalog-two",
        )
    ],
    "query_users": [QueryUserOutput(sys_id="user-sys-id", user_name="admin")],
    "run_query": [RunQueryOutput(sys_id="ticket-sys-id", number="INC0000001")],
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


@pytest.mark.parametrize("identifier", sorted(VIEW_OUTPUTS))
def test_custom_view_handlers_return_sdk_template_context(identifier):
    action = app.actions_manager.get_action(identifier)

    template_context = _call_view_handler(action.meta.view_handler, VIEW_OUTPUTS[identifier])

    assert set(template_context) == {"results"}
    assert template_context["results"]
    for result in template_context["results"]:
        assert {"data", "param", "summary", "action_name"} <= set(result)
        assert result["action_name"] == action.meta.action


def test_describe_catalog_item_view_populates_sys_id_param():
    action = app.actions_manager.get_action("describe_catalog_item")

    template_context = _call_view_handler(
        action.meta.view_handler,
        [DescribeCatalogItemOutput(sys_id="item-sys-id")],
    )

    result = template_context["results"][0]
    assert result["param"] == {"sys_id": "item-sys-id"}
    assert result["data"][0]["sys_id"] == "item-sys-id"


def test_list_services_view_splits_catalog_strings_for_template():
    action = app.actions_manager.get_action("list_services")

    template_context = _call_view_handler(
        action.meta.view_handler,
        [ServiceItemOutput(sys_id="item-sys-id", catalogs="catalog-one,catalog-two")],
    )

    assert template_context["results"][0]["data"][0]["catalogs"] == [
        "catalog-one",
        "catalog-two",
    ]


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
                and "|default(\"\") |tojson|forceescape" not in line
                and "|default(\"\")|tojson|forceescape" not in line
            ):
                unescaped_lines.append(f"{template_path.name}:{line_number}")

    assert unescaped_lines == []
