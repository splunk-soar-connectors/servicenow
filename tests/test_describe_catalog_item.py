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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.actions.describe_catalog_item import DescribeCatalogItemOutput


def test_describe_catalog_item_models_stable_lists_without_normalizing_client_script():
    raw_client_script = {"onLoad": {"script": "g_form.setValue('x', 'y');"}}
    raw_variables = [
        {
            "name": "requested_for",
            "children": [{"name": "nested_choice", "custom_child": "kept"}],
            "custom_variable": "kept",
        }
    ]
    raw_catalogs = [{"sys_id": "catalog-sys-id", "title": "Service Catalog"}]
    raw_categories = [{"sys_id": "category-sys-id", "title": "Hardware"}]
    raw_category = {"sys_id": "top-category-sys-id", "title": "Requests"}

    output = DescribeCatalogItemOutput(
        sys_id="item-sys-id",
        name="Catalog Item",
        client_script=raw_client_script,
        variables=raw_variables,
        catalogs=raw_catalogs,
        categories=raw_categories,
        category=raw_category,
    )

    assert "client_script" not in DescribeCatalogItemOutput.model_fields
    for field_name in ("variables", "catalogs", "categories", "category"):
        assert field_name in DescribeCatalogItemOutput.model_fields

    output_data = output.model_dump()
    assert output_data["client_script"] == raw_client_script
    assert output_data["variables"] == raw_variables
    assert output_data["catalogs"] == raw_catalogs
    assert output_data["categories"] == raw_categories
    assert output_data["category"] == raw_category
