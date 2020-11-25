# File: servicenow_consts.py
# Copyright (c) 2016-2020 Splunk Inc.
#
# SPLUNK CONFIDENTIAL - Use or disclosure of this material in whole or in part
# without a valid written license from Splunk Inc. is PROHIBITED.
#
# --

SERVICENOW_JSON_DEVICE_URL = "url"
SERVICENOW_JSON_USERNAME = "username"
SERVICENOW_JSON_PASSWORD = "password"
SERVICENOW_JSON_CLIENT_ID = "client_id"
SERVICENOW_JSON_CLIENT_SECRET = "client_secret"
SERVICENOW_JSON_MAX_RESULTS = "max_results"
SERVICENOW_JSON_TOTAL_TICKETS = "total_tickets"
SERVICENOW_JSON_SHORT_DESCRIPTION = "short_description"
SERVICENOW_JSON_DESCRIPTION = "description"
SERVICENOW_JSON_NEW_TICKET_ID = "created_ticket_id"
SERVICENOW_JSON_GOT_TICKET_ID = "queried_ticket_id"
SERVICENOW_JSON_SYS_ID = "sys_id"
SERVICENOW_JSON_TICKET_ID = "id"
SERVICENOW_JSON_FIELDS = "fields"
SERVICENOW_JSON_TABLE = "table"
SERVICENOW_JSON_VAULT_ID = "vault_id"
SERVICENOW_JSON_FILTER = "filter"
SERVICENOW_JSON_ON_POLL_FILTER = "on_poll_filter"
SERVICENOW_JSON_ON_POLL_TABLE = "on_poll_table"
SERVICENOW_JSON_QUERY_TABLE = "query_table"
SERVICENOW_JSON_QUERY = "query"
SERVICENOW_JSON_EXTRACT_IPS = "extract_ips"
SERVICENOW_JSON_EXTRACT_HASHES = "extract_hashes"
SERVICENOW_JSON_EXTRACT_URLS = "extract_urls"

SERVICENOW_ERR_CONNECTIVITY_TEST = "Test Connectivity Failed"
SERVICENOW_SUCC_CONNECTIVITY_TEST = "Test Connectivity Passed"
SERVICENOW_ERR_SERVER_CONNECTION = "Connection failed"
SERVICENOW_VALIDATE_INTEGER_MESSAGE = "Please provide a valid integer value in the {key} parameter"
SERVICENOW_ERR_FETCH_VALUE = 'Error occurred while fetching variable value for the item_option_value: {item_opt_value} of the System ID: {sys_id}'
SERVICENOW_ERR_FETCH_QUESTION_ID = 'Error occurred while fetching question ID for the item_option_value: {item_opt_value} of the System ID: {sys_id}'
SERVICENOW_ERR_FETCH_QUESTION = 'Error occurred while fetching question for the question ID: {question_id} and the item_option_value: {item_opt_value} of the System ID: {sys_id}'
SERVICENOW_ERR_FROM_SERVER = "API failed, Status code: {status}, Message: {message}, Detail: {detail}"
SERVICENOW_MESSAGE_GET_INCIDENT_TEST = "Querying a single Incident to check credentials"
SERVICENOW_ERR_FIELDS_JSON_PARSE = "Unable to parse the fields parameter into a dictionary"
SERVICENOW_ERR_API_UNSUPPORTED_METHOD = "Unsupported method"
SERVICENOW_ERR_BASIC_AUTH_NOT_GIVEN_FIRST_TIME = 'Provide username and password to generate OAuth token for running Test Connectivity for the first time'
SERVICENOW_ERR_ONE_PARAM_REQ = "Please specify at least one of the parameters short_description, description, or fields to create the ticket with"
SERVICENOW_ERR_FAILURES = "Some tickets had issues during ingestion, see logs for details"
SERVICENOW_ERROR_CODE_MESSAGE = "Error code unavailable"
SERVICENOW_ERROR_MESSAGE = "Unknown error occurred. Please check the asset configuration and|or action parameters"
TYPE_ERROR_MESSAGE = "Error occurred while connecting to the ServiceNow server. Please check the asset configuration and|or the action parameters"
PARSE_ERROR_MESSAGE = "Unable to parse the error message. Please check the asset configuration and|or action parameters"


SERVICENOW_USING_BASE_URL = "Using url: {base_url}"
SERVICENOW_BASE_QUERY_URI = "/table/"

DEFAULT_MAX_RESULTS = 100
SERVICENOW_TICKET_FOOTNOTE = "Added by Phantom for container id: "
SERVICENOW_DEFAULT_TABLE = "incident"

SERVICENOW_ITEM_OPT_MTOM_TABLE = "sc_item_option_mtom"
SERVICENOW_ITEM_OPT_TABLE = "sc_item_option"
SERVICENOW_ITEM_OPT_NEW_TABLE = "item_option_new"

SERVICENOW_DEFAULT_OFFSET = 0
SERVICENOW_DEFAULT_LIMIT = 10000
SERVICENOW_DEFAULT_MAX_LIMIT = 100

SERVICENOW_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
