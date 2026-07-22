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

"""Constants for ServiceNow connector"""

# API Configuration
API_URI = "/api/now"
SC_API_URI = "/api/sn_sc"
TEST_CONNECTIVITY_ENDPOINT = "/table/incident"

# Endpoint Templates
TABLE_ENDPOINT = "/table/{0}"
TICKET_ENDPOINT = "/table/{0}/{1}"
SC_CATEGORY_ENDPOINT = "/table/sc_category"
SC_CATALOG_ENDPOINT = "/table/sc_catalog"
SC_CAT_ITEMS_ENDPOINT = "/table/sc_cat_item"
CATALOG_ITEMS_ENDPOINT = "/servicecatalog/items/{}"
CATALOG_ORDER_NOW_ENDPOINT = "/servicecatalog/items/{}/order_now"

# Pagination defaults
DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 10000
DEFAULT_MAX_LIMIT = 100
MAX_PAGES = 1000

# Search endpoints
SEARCH_SOURCES_ENDPOINT = "/search/sources/textsearch"

# Search pagination defaults
SEARCH_DEFAULT_PAGE = 1
SEARCH_MAX_LIMIT = 20

SERVICENOW_SENSITIVE_PROPS = [
    "admin_password",  # pragma: allowlist secret
    "database_password",  # pragma: allowlist secret
    "user_password",  # pragma: allowlist secret
]

# Messages
TEST_CONNECTIVITY_SUCCESS = "Test Connectivity Passed"
TEST_CONNECTIVITY_FAIL = "Test Connectivity Failed"
SERVICENOW_TICKET_ID_MESSAGE = (
    "Please provide a valid Ticket Number in the 'id' parameter or check the 'is_sys_id' "
    "parameter and provide a valid 'sys_id' in the 'id' parameter"
)
SERVICENOW_INVALID_PARAMETER_MESSAGE = "Please provide valid input parameters"


class UnauthorizedOAuthTokenException(Exception):
    """Exception raised when OAuth token is unauthorized"""

    pass


class TicketNotFoundException(Exception):
    """Exception raised when a ticket is not found by number or sys_id"""

    pass
