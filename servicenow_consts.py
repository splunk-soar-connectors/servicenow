# File: servicenow_consts.py
#
# Copyright (c) 2016-2025 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.
SERVICENOW_JSON_DEVICE_URL = "url"
SERVICENOW_JSON_USER_ID = "user_id"
SERVICENOW_JSON_USER_PASSWORD = "user_password"  # pragma: allowlist secret
SERVICENOW_JSON_USERNAME = "username"
SERVICENOW_JSON_PASSWORD = "password"  # pragma: allowlist secret
SERVICENOW_JSON_CLIENT_ID = "client_id"
SERVICENOW_JSON_CLIENT_SECRET = "client_secret"  # pragma: allowlist secret
SERVICENOW_JSON_MAX_RESULTS = "max_results"
SERVICENOW_JSON_TOTAL_TICKETS = "total_tickets"
SERVICENOW_JSON_TOTAL_USERS = "total_users"
SERVICENOW_JSON_SHORT_DESCRIPTION = "short_description"
SERVICENOW_JSON_DESCRIPTION = "description"
SERVICENOW_JSON_NEW_TICKET_ID = "created_ticket_id"
SERVICENOW_JSON_GOT_TICKET_ID = "queried_ticket_id"
SERVICENOW_JSON_SYS_ID = "sys_id"
SERVICENOW_JSON_TICKET_ID = "id"
SERVICENOW_JSON_FIELDS = "fields"
SERVICENOW_JSON_SYS_USER_TABLE = "sys_user"
SERVICENOW_JSON_TABLE = "table"
SERVICENOW_JSON_VAULT_ID = "vault_id"
SERVICENOW_JSON_FILTER = "filter"
SERVICENOW_JSON_ON_POLL_FILTER = "on_poll_filter"
SERVICENOW_JSON_ON_POLL_TABLE = "on_poll_table"
SERVICENOW_JSON_QUERY_TABLE = "query_table"
SERVICENOW_JSON_SYSPARM_SYS_ID_QUERY = "sysparm_query=sys_id={}"
SERVICENOW_JSON_SYSPARM_USER_NAME_QUERY = "sysparm_query=user_name={}"
SERVICENOW_JSON_QUERY = "query"
SERVICENOW_JSON_EXTRACT_IPS = "extract_ips"
SERVICENOW_JSON_EXTRACT_HASHES = "extract_hashes"
SERVICENOW_JSON_EXTRACT_URLS = "extract_urls"
SERVICENOW_JSON_SYSPARM_TERM = "sysparm_term"
SERVICENOW_JSON_SYSPARM_SEARCH_SOURCES = "sysparm_search_sources"
SERVICENOW_JSON_TOTAL_RECORDS = "total_records"

SERVICENOW_ERROR_CONNECTIVITY_TEST = "Test Connectivity Failed"
SERVICENOW_SUCCESS_CONNECTIVITY_TEST = "Test Connectivity Passed"
SERVICENOW_ERROR_SERVER_CONNECTION = "Connection failed. {error_message}"
SERVICENOW_VALIDATE_INTEGER_MESSAGE = "Please provide a valid integer value in the {param} parameter"
SERVICENOW_ERROR_FETCH_VALUE = (
    "Error occurred while fetching variable value for the item_option_value: {item_opt_value} of the System ID: {sys_id}"
)
SERVICENOW_ERROR_FETCH_QUESTION_ID = (
    "Error occurred while fetching question ID for the item_option_value: {item_opt_value} of the System ID: {sys_id}"
)
SERVICENOW_ERROR_FETCH_QUESTION = (
    "Error occurred while fetching question for"
    " the question ID: {question_id} and the item_option_value: {item_opt_value} of the System ID: {sys_id}"
)
SERVICENOW_ERROR_FROM_SERVER = "API failed, Status code: {status}, Message: {message}, Detail: {detail}."
SERVICENOW_MESSAGE_GET_INCIDENT_TEST = "Querying a single Incident to check credentials"
SERVICENOW_ERROR_FIELDS_JSON_PARSE = "Unable to parse the fields parameter into a dictionary"
SERVICENOW_ERROR_VARIABLES_JSON_PARSE = "Unable to parse the variables parameter into a dictionary"
SERVICENOW_ERROR_API_UNSUPPORTED_METHOD = "Unsupported method"
SERVICENOW_ERROR_BASIC_AUTH_NOT_GIVEN_FIRST_TIME = (
    "Provide username and password to generateOAuth token for running Test Connectivity for the first time"
)
SERVICENOW_ERROR_ONE_PARAM_REQ = (
    "Please specify at least one of the parameters short_description, description, or fields to create the ticket with"
)
SERVICENOW_ERROR_FAILURES = "Some tickets had issues during ingestion, see logs for details"
SERVICENOW_ERROR_CODE_MESSAGE = "Error code unavailable"
SERVICENOW_ERROR_MESSAGE = "Unknown error occurred. Please check the asset configuration and|or action parameters"
PARSE_ERROR_MESSAGE = "Unable to parse the error message. Please check the asset configuration and|or action parameters"
SERVICENOW_STATE_FILE_CORRUPT_ERROR = (
    "Error occurred while loading the state file due to its unexpected format. "
    "Resetting the state file with the default format. Please try again."
)
SERVICENOW_AUTH_ERROR_MESSAGE = "Unable to get authorization credentials"
SERVICENOW_TICKET_ID_MESSAGE = "Please provide a valid Ticket Number in the 'id' parameter or check the 'is_sys_id' \
                                parameter and provide a valid 'sys_id' in the 'id' parameter"
SERVICENOW_INVALID_PARAMETER_MESSAGE = "Please provide valid input parameters"
SERVICENOW_SEVERITY_MESSAGE = "Could not get severities from platform: {}"

SERVICENOW_USING_BASE_URL = "Using url: {base_url}"
SERVICENOW_BASE_QUERY_URI = "/table/"

DEFAULT_MAX_RESULTS = 100
SERVICENOW_TICKET_FOOTNOTE = "Added by Phantom for container id: "
SERVICENOW_DEFAULT_TABLE = "incident"

SERVICENOW_ITEM_OPT_MTOM_TABLE = "sc_item_option_mtom"
SERVICENOW_ITEM_OPT_TABLE = "sc_item_option"
SERVICENOW_ITEM_OPT_NEW_TABLE = "item_option_new"

# In search sources we only getting 20 results per page
SERVICENOW_DEFAULT_PAGE = 1
SERVICENOW_MAX_LIMIT = 20

SERVICENOW_DEFAULT_OFFSET = 0
SERVICENOW_DEFAULT_LIMIT = 10000
SERVICENOW_DEFAULT_MAX_LIMIT = 100

SERVICENOW_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

SERVICENOW_TOKEN_STRING = "oauth_token"
SERVICENOW_STATE_IS_ENCRYPTED = "is_encrypted"
SERVICENOW_ACCESS_TOKEN_STRING = "access_token"
SERVICENOW_REFRESH_TOKEN_STRING = "refresh_token"
SERVICENOW_CONFIG_CLIENT_SECRET = "client_secret"  # pragma: allowlist secret


# For encryption and decryption
SERVICENOW_ENCRYPT_TOKEN = "Encrypting the {} token"
SERVICENOW_DECRYPT_TOKEN = "Decrypting the {} token"
SERVICENOW_ENCRYPTION_ERROR = "Error occurred while encrypting the state file"
SERVICENOW_DECRYPTION_ERROR = "Error occurred while decrypting the state file"

SERVICENOW_TEST_CONNECTIVITY_ENDPOINT = "/table/incident"
SERVICENOW_TABLE_ENDPOINT = "/table/{0}"
SERVICENOW_TICKET_ENDPOINT = "/table/{0}/{1}"
SERVICENOW_SC_CATALOG_ENDPOINT = "/table/sc_catalog"
SERVICENOW_SC_CATEGORY_ENDPOINT = "/table/sc_category"
SERVICENOW_CATALOG_ITEMS_ENDPOINT = "/servicecatalog/items/{}"
SERVICENOW_SYS_JOURNAL_FIELD_ENDPOINT = "/table/sys_journal_field"
SERVICENOW_SC_CAT_ITEMS_ENDPOINT = "/table/sc_cat_item"
SERVICENOW_CATALOG_OREDERNOW_ENDPOINT = "/servicecatalog/items/{}/order_now"
SERVICENOW_API_ENDPOINT = "/api/now"
SERVICENOW_SEARCH_SOURCE_ENDPOINT = "/search/sources/textsearch"
