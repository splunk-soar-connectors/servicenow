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

"""
Import action modules so their decorators register handlers with the app.
"""

from . import (
    add_comment as add_comment,
    add_work_note as add_work_note,
    create_ticket as create_ticket,
    describe_catalog_item as describe_catalog_item,
    describe_service_catalog as describe_service_catalog,
    get_ticket as get_ticket,
    get_variables as get_variables,
    list_categories as list_categories,
    list_service_catalogs as list_service_catalogs,
    list_services as list_services,
    list_tickets as list_tickets,
    make_request as make_request,
    on_poll as on_poll,
    query_users as query_users,
    request_catalog_item as request_catalog_item,
    run_query as run_query,
    search_sources as search_sources,
    test_connectivity as test_connectivity,
    update_ticket as update_ticket,
)
