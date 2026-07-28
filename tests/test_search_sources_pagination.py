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

from src.actions.search_sources import _search_sources_with_pagination


class FakeServiceNowClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def make_rest_call(self, endpoint, params):
        self.calls.append({"endpoint": endpoint, "params": params.copy()})
        return self.responses.pop(0)


def test_search_sources_pagination_merges_reordered_sources_by_sys_id():
    helper = FakeServiceNowClient(
        [
            {
                "result": {
                    "result_count": 21,
                    "search_results": [
                        {
                            "sys_id": "incident-source",
                            "label": "Incident",
                            "limit": 20,
                            "page": 1,
                            "records": [{"sys_id": "inc-1"}],
                        },
                        {
                            "sys_id": "knowledge-source",
                            "label": "Knowledge",
                            "limit": 20,
                            "page": 1,
                            "records": [{"sys_id": "kb-1"}],
                        },
                    ],
                }
            },
            {
                "result": {
                    "result_count": 21,
                    "search_results": [
                        {
                            "sys_id": "knowledge-source",
                            "label": "Knowledge",
                            "limit": 20,
                            "page": 2,
                            "records": [{"sys_id": "kb-2"}],
                        },
                        {
                            "sys_id": "incident-source",
                            "label": "Incident",
                            "limit": 20,
                            "page": 2,
                            "records": [{"sys_id": "inc-2"}],
                        },
                    ],
                }
            },
        ]
    )

    result = _search_sources_with_pagination(helper, "password", "incident,knowledge")

    search_results = result["search_results"]
    assert [bucket["sys_id"] for bucket in search_results] == [
        "incident-source",
        "knowledge-source",
    ]
    assert search_results[0]["records"] == [{"sys_id": "inc-1"}, {"sys_id": "inc-2"}]
    assert search_results[1]["records"] == [{"sys_id": "kb-1"}, {"sys_id": "kb-2"}]
    assert "limit" not in search_results[0]
    assert "page" not in search_results[0]


def test_search_sources_pagination_appends_new_source_bucket():
    helper = FakeServiceNowClient(
        [
            {
                "result": {
                    "result_count": 21,
                    "search_results": [
                        {
                            "sys_id": "incident-source",
                            "label": "Incident",
                            "limit": 20,
                            "page": 1,
                            "records": [{"sys_id": "inc-1"}],
                        }
                    ],
                }
            },
            {
                "result": {
                    "result_count": 21,
                    "search_results": [
                        {
                            "sys_id": "incident-source",
                            "label": "Incident",
                            "limit": 20,
                            "page": 2,
                            "records": [{"sys_id": "inc-2"}],
                        },
                        {
                            "sys_id": "catalog-source",
                            "label": "Catalog",
                            "limit": 20,
                            "page": 2,
                            "records": [{"sys_id": "cat-1"}],
                        },
                    ],
                }
            },
        ]
    )

    result = _search_sources_with_pagination(helper, "password", "incident,catalog")

    search_results = result["search_results"]
    assert [bucket["sys_id"] for bucket in search_results] == [
        "incident-source",
        "catalog-source",
    ]
    assert search_results[0]["records"] == [{"sys_id": "inc-1"}, {"sys_id": "inc-2"}]
    assert search_results[1]["records"] == [{"sys_id": "cat-1"}]
