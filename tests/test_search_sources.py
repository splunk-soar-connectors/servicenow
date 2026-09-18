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

from src.actions import search_sources


def test_search_sources_pagination_stops_at_max_pages(monkeypatch):
    monkeypatch.setattr(search_sources, "MAX_PAGES", 2)

    class FakeClient:
        def __init__(self):
            self.pages = []

        def make_rest_call(self, _endpoint, params):
            self.pages.append(params["sysparm_page"])
            return {
                "result": {
                    "result_count": 100,
                    "search_results": [{"sys_id": "source", "records": []}],
                }
            }

    client = FakeClient()

    result = search_sources._search_sources_with_pagination(
        client,
        sysparm_term="needle",
        sysparm_search_sources="source",
    )

    assert client.pages == [1, 2]
    assert result["result_count"] == 100
