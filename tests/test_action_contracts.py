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
import pytest
from httpx import Response
from soar_sdk.action_results import ActionOutput
from soar_sdk.params import Params

from src.app import app

EXPECTED_ACTIONS = {
    "add_comment": {"action": "add comment", "type": "generic", "read_only": False},
    "add_work_note": {
        "action": "add work note",
        "type": "generic",
        "read_only": False,
    },
    "create_ticket": {
        "action": "create ticket",
        "type": "generic",
        "read_only": False,
    },
    "describe_catalog_item": {
        "action": "describe catalog item",
        "type": "investigate",
        "read_only": True,
    },
    "describe_service_catalog": {
        "action": "describe service catalog",
        "type": "investigate",
        "read_only": True,
    },
    "get_ticket": {"action": "get ticket", "type": "investigate", "read_only": True},
    "get_variables": {
        "action": "get variables",
        "type": "investigate",
        "read_only": True,
    },
    "list_categories": {
        "action": "list categories",
        "type": "investigate",
        "read_only": True,
    },
    "list_service_catalogs": {
        "action": "list service catalogs",
        "type": "investigate",
        "read_only": True,
    },
    "list_services": {
        "action": "list services",
        "type": "investigate",
        "read_only": True,
    },
    "list_tickets": {
        "action": "list tickets",
        "type": "investigate",
        "read_only": True,
    },
    "make_request": {"action": "make request", "type": "generic", "read_only": False},
    "on_poll": {"action": "on poll", "type": "ingest", "read_only": True},
    "query_users": {
        "action": "query users",
        "type": "investigate",
        "read_only": True,
    },
    "request_catalog_item": {
        "action": "request catalog item",
        "type": "generic",
        "read_only": False,
    },
    "run_query": {"action": "run query", "type": "investigate", "read_only": True},
    "search_sources": {
        "action": "search sources",
        "type": "investigate",
        "read_only": True,
    },
    "test_connectivity": {
        "action": "test connectivity",
        "type": "test",
        "read_only": True,
    },
    "update_ticket": {
        "action": "update ticket",
        "type": "generic",
        "read_only": False,
    },
}


def test_all_servicenow_actions_are_registered():
    assert set(app.actions_manager._actions) == set(EXPECTED_ACTIONS)


@pytest.mark.parametrize("identifier", sorted(EXPECTED_ACTIONS))
def test_action_metadata_has_sdk_contract(identifier):
    action = app.actions_manager.get_action(identifier)
    meta = action.meta

    assert meta.identifier == identifier
    assert meta.action == EXPECTED_ACTIONS[identifier]["action"]
    assert meta.type == EXPECTED_ACTIONS[identifier]["type"]
    assert meta.read_only is EXPECTED_ACTIONS[identifier]["read_only"]
    assert issubclass(meta.parameters, Params)
    assert issubclass(meta.output, ActionOutput)


@pytest.mark.parametrize("identifier", sorted(EXPECTED_ACTIONS))
def test_action_output_models_export_json_schema(identifier):
    output_cls = app.actions_manager.get_action(identifier).meta.output

    schema = list(output_cls._to_json_schema())

    assert isinstance(schema, list)
    for field in schema:
        assert "data_path" in field
        assert field["data_path"].startswith("action_result.")


def test_make_request_output_contract_merges_json_response_fields():
    output_cls = app.actions_manager.get_action("make_request").meta.output

    output = output_cls.from_response(
        Response(200, json={"result": {"sys_id": "ticket-sys-id"}, "custom": "value"})
    )

    assert output.model_dump() == {
        "status_code": 200,
        "response_body": '{"result":{"sys_id":"ticket-sys-id"},"custom":"value"}',
        "result": {"sys_id": "ticket-sys-id"},
        "custom": "value",
    }
