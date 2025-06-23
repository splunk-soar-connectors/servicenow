# File: servicenow_connector.py
#
# Copyright (c) 2016-2025 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.
#
#
# Phantom imports
import phantom.app as phantom


try:
    import phantom.rules as phrules
except:
    pass
import ast
import codecs
import json
import re
import sys
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import encryption_helper
import magic
import requests
from bs4 import BeautifulSoup
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector

from servicenow_consts import *


DT_STR_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class UnauthorizedOAuthTokenException(Exception):
    pass


class RetVal(tuple):
    def __new__(cls, status, data):
        return tuple.__new__(RetVal, (status, data))


class ServicenowConnector(BaseConnector):
    # actions supported by this script
    ACTION_ID_LIST_TICKETS = "list_tickets"
    ACTION_ID_ADD_COMMENT = "add_comment"
    ACTION_ID_ORDER_ITEM = "request_catalog_item"
    ACTION_ID_ADD_WORK_NOTE = "add_work_note"
    ACTION_ID_DESCRIBE_CATALOG_ITEM = "describe_catalog_item"
    ACTION_ID_DESCRIBE_SERVICE_CATALOG = "describe_service_catalog"
    ACTION_ID_LIST_SERVICES = "list_services"
    ACTION_ID_LIST_SERVICE_CATALOGS = "list_service_catalogs"
    ACTION_ID_LIST_CATEGORIES = "list_categories"
    ACTION_ID_CREATE_TICKET = "create_ticket"
    ACTION_ID_GET_TICKET = "get_ticket"
    ACTION_ID_UPDATE_TICKET = "update_ticket"
    ACTION_ID_GET_VARIABLES = "get_variables"
    ACTION_ID_ON_POLL = "on_poll"
    ACTION_ID_RUN_QUERY = "run_query"
    ACTION_ID_QUERY_USERS = "query_users"
    ACTION_ID_SEARCH_SOURCES = "search_sources"

    def csv_to_list(self, data):
        """Comma separated values to list"""
        data = [x.strip() for x in data.split(",")]
        data = list(dict.fromkeys(filter(None, data)))
        return data

    def __init__(self):
        # Call the BaseConnectors init first
        super().__init__()

        self._state_file_path = None
        self._try_oauth = False
        self._use_token = False
        self._state = {}
        self._response_headers = {}

    def encrypt_state(self, encrypt_var, token_name):
        """Handle encryption of token.
        :param encrypt_var: Variable needs to be encrypted
        :return: encrypted variable
        """
        self.debug_print(SERVICENOW_ENCRYPT_TOKEN.format(token_name))  # nosemgrep
        return encryption_helper.encrypt(encrypt_var, self.get_asset_id())

    def decrypt_state(self, decrypt_var, token_name):
        """Handle decryption of token.
        :param decrypt_var: Variable needs to be decrypted
        :return: decrypted variable
        """
        self.debug_print(SERVICENOW_DECRYPT_TOKEN.format(token_name))  # nosemgrep
        return encryption_helper.decrypt(decrypt_var, self.get_asset_id())

    def initialize(self):
        # Load all the asset configuration in global variables
        self._state = self.load_state()
        config = self.get_config()
        sn_sc_actions = ["describe_catalog_item", "request_catalog_item"]

        # Check if state file is not corrupted, if it is reset the state file
        if not isinstance(self._state, dict):
            self.debug_print("Resetting the state file with the default format")
            self._state = {"app_version": self.get_app_json().get("app_version")}

        # Base URL
        self._base_url = config[SERVICENOW_JSON_DEVICE_URL]
        if self._base_url.endswith("/"):
            self._base_url = self._base_url[:-1]

        ret_val, self._first_run_container = self._validate_integers(
            self, config.get("first_run_container", SERVICENOW_DEFAULT_LIMIT), "first_run_container"
        )
        if phantom.is_fail(ret_val):
            return self.get_status()

        ret_val, self._max_container = self._validate_integers(self, config.get("max_container", DEFAULT_MAX_RESULTS), "max_container")
        if phantom.is_fail(ret_val):
            return self.get_status()

        if config.get("severity"):
            severity = config.get("severity", "medium").lower()
            if len(severity) > 20:
                return self.set_status(phantom.APP_ERROR, "Severity length must be less than equal to 20 characters")

        self._host = self._base_url[self._base_url.find("//") + 2 :]
        self._headers = {"Accept": "application/json"}
        # self._headers.update({'X-no-response-body': 'true'})
        self._api_uri = "/api/now"
        if self.get_action_identifier() in sn_sc_actions:
            self._api_uri = "/api/sn_sc"

        self._client_id = config.get(SERVICENOW_JSON_CLIENT_ID, None)
        if self._client_id:
            try:
                self._client_secret = config[SERVICENOW_JSON_CLIENT_SECRET]
                self._use_token = True
            except KeyError:
                self.save_progress("Missing Client Secret")
                return phantom.APP_ERROR
        if self._use_token:
            self._access_token = self._state.get(SERVICENOW_TOKEN_STRING, {}).get(SERVICENOW_ACCESS_TOKEN_STRING)
            self._refresh_token = self._state.get(SERVICENOW_TOKEN_STRING, {}).get(SERVICENOW_REFRESH_TOKEN_STRING)
            if self._state.get(SERVICENOW_STATE_IS_ENCRYPTED):
                try:
                    if self._access_token:
                        self._access_token = self.decrypt_state(self._access_token, "access")
                except Exception as e:
                    self._dump_error_log(e, SERVICENOW_DECRYPTION_ERROR)
                    return self.set_status(phantom.APP_ERROR, SERVICENOW_DECRYPTION_ERROR)

                try:
                    if self._refresh_token:
                        self._refresh_token = self.decrypt_state(self._refresh_token, "refresh")
                except Exception as e:
                    self._dump_error_log(e, SERVICENOW_DECRYPTION_ERROR)
                    return self.set_status(phantom.APP_ERROR, SERVICENOW_DECRYPTION_ERROR)

        return phantom.APP_SUCCESS

    def finalize(self):
        if self._use_token:
            try:
                if self._access_token:
                    self._state[SERVICENOW_TOKEN_STRING][SERVICENOW_ACCESS_TOKEN_STRING] = self.encrypt_state(self._access_token, "access")
            except Exception as e:
                self._dump_error_log(e, SERVICENOW_ENCRYPTION_ERROR)
                return self.set_status(phantom.APP_ERROR, SERVICENOW_ENCRYPTION_ERROR)

            try:
                if self._refresh_token:
                    self._state[SERVICENOW_TOKEN_STRING][SERVICENOW_REFRESH_TOKEN_STRING] = self.encrypt_state(self._refresh_token, "refresh")
            except Exception as e:
                self._dump_error_log(e, SERVICENOW_ENCRYPTION_ERROR)
                return self.set_status(phantom.APP_ERROR, SERVICENOW_ENCRYPTION_ERROR)

            self._state[SERVICENOW_STATE_IS_ENCRYPTED] = True
        self.save_state(self._state)
        return phantom.APP_SUCCESS

    def _validate_integers(self, action_result, parameter, key, allow_zero=False):
        """This method is to check if the provided input parameter value
        is a non-zero positive integer and returns the integer value of the parameter itself.
        :param action_result: Action result or BaseConnector object
        :param parameter: input parameter
        :return: integer value of the parameter or None in case of failure
        """

        if parameter is not None:
            try:
                if not float(parameter).is_integer():
                    return action_result.set_status(phantom.APP_ERROR, SERVICENOW_VALIDATE_INTEGER_MESSAGE.format(param=key)), None

                parameter = int(parameter)
            except Exception:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_VALIDATE_INTEGER_MESSAGE.format(param=key)), None

            if parameter < 0:
                return (
                    action_result.set_status(phantom.APP_ERROR, f"Please provide a valid non-negative integer value in the {key} parameter"),
                    None,
                )
            if not allow_zero and parameter == 0:
                return (
                    action_result.set_status(phantom.APP_ERROR, f"Please provide a positive integer value in the {key} parameter"),
                    None,
                )

        return phantom.APP_SUCCESS, parameter

    def _get_error_message_from_exception(self, e):
        """This method is used to get appropriate error message from the exception.
        :param e: Exception object
        :return: error message
        """

        error_message = SERVICENOW_ERROR_MESSAGE
        error_code = None

        self._dump_error_log(e, "Error occurred.")

        try:
            if hasattr(e, "args"):
                if len(e.args) > 1:
                    error_code = e.args[0]
                    error_message = e.args[1]
                elif len(e.args) == 1:
                    error_code = SERVICENOW_ERROR_CODE_MESSAGE
                    error_message = e.args[0]
        except Exception as e:
            self.error_print(f"Error occurred while fetching exception information. Details: {e!s}")

        if not error_code:
            error_text = f"Error Message: {error_message}"
        else:
            error_text = f"Error Code: {error_code}. Error Message: {error_message}"

        return error_text

    def _dump_error_log(self, error, message="Exception occurred."):
        self.error_print(message, dump_object=error)

    def _get_error_details(self, resp_json):
        # Initialize the default error_details
        error_details = {"message": "Not Found", "detail": "Not supplied"}

        # Handle if resp_json unavailable
        if not resp_json:
            return error_details

        # Handle if resp_json contains "error" key and corresponding non-none and non-empty value or not
        error_info = resp_json.get("error")

        if not error_info:
            return error_details
        else:
            if isinstance(error_info, dict):
                error_details = error_info
            else:
                if isinstance(resp_json, dict):
                    error_details["message"] = error_info if error_info else "Not Found"
                    error_description = resp_json.get("error_description", "Not supplied")
                    error_details["detail"] = error_description
                return error_details

        # Handle the scenario of "message" and "detail" keys not in the required format
        if "message" not in error_details:
            error_details["message"] = "Not Found"

        if "detail" not in error_details:
            error_details["detail"] = "Not supplied"

        return error_details

    def _process_empty_response(self, response, action_result):
        # this function will parse the header and create the response that the callers
        # of the app expect
        location = response.headers.get("Location")

        if not location:
            if 200 <= response.status_code < 205:
                return RetVal(phantom.APP_SUCCESS, {})
            else:
                return RetVal(action_result.set_status(phantom.APP_ERROR, "Empty response and no information in the header"), None)

        location_name = f"{self._base_url}{self._api_uri}/table"
        if location.startswith(location_name):
            resp_json = dict()
            try:
                sys_id = location.rsplit("/", 1)[-1]
                resp_json = {"result": {"sys_id": sys_id}}
            except Exception as e:
                self._dump_error_log(e, "Unable to process empty response for 'table'")
                return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to process empty response for 'table'"), None)

            return RetVal(phantom.APP_SUCCESS, resp_json)

        return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to process empty response"), None)

    def _process_html_response(self, response, action_result):
        # An html response, is bound to be an error
        status_code = response.status_code

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove the script, style, footer and navigation part from the HTML message
            for element in soup(["script", "style", "footer", "nav"]):
                element.extract()
            error_text = soup.text
            split_lines = error_text.split("\n")
            split_lines = [x.strip() for x in split_lines if x.strip()]
            error_text = "\n".join(split_lines)
        except Exception:
            error_text = "Cannot parse error details"

        message = f"Status Code: {status_code}. Data from server:\n{error_text}\n"

        message = message.replace("{", " ").replace("}", " ")

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_json_response(self, r, action_result):
        # Try a json parse
        try:
            resp_json = r.json()
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(phantom.APP_ERROR, f"Unable to parse response as JSON. {error_message}"), None)

        # What's with the special case 201?
        if 200 <= r.status_code < 205:
            return RetVal(phantom.APP_SUCCESS, resp_json)

        if r.status_code == 401 and self._try_oauth:
            if resp_json.get("error") == "invalid_token":
                raise UnauthorizedOAuthTokenException

        if r.status_code != requests.codes.ok:  # pylint: disable=E1101
            error_details = self._get_error_details(resp_json)
            return RetVal(
                action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_FROM_SERVER.format(status=r.status_code, **error_details)),
                resp_json,
            )

        return RetVal(phantom.APP_SUCCESS, resp_json)

    def _process_response(self, r, action_result):
        # store the r_text in debug data, it will get dumped in the logs if an error occurs
        if hasattr(action_result, "add_debug_data"):
            if r is not None:
                action_result.add_debug_data({"r_text": r.text})
                action_result.add_debug_data({"r_headers": r.headers})
                action_result.add_debug_data({"r_status_code": r.status_code})
            else:
                action_result.add_debug_data({"r_text": "r is None"})

        # There are just too many differences in the response to handle all of them in the same function
        if "json" in r.headers.get("Content-Type", ""):
            return self._process_json_response(r, action_result)

        if "html" in r.headers.get("Content-Type", ""):
            return self._process_html_response(r, action_result)

        # it's not an html or json, handle if it is a successfull empty response
        if (200 <= r.status_code < 205) and (not r.text):
            return self._process_empty_response(r, action_result)

        # everything else is actually an error at this point
        message = "Can't process response from server. Status Code: {} Data from server: {}".format(
            r.status_code, r.text.replace("{", " ").replace("}", " ")
        )

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _upload_file(self, action_result, endpoint, headers=None, params=None, data=None, auth=None):
        if headers is None:
            headers = {}
        # Create the headers
        headers.update(self._headers)

        resp_json = None

        try:
            r = requests.post(
                f"{self._base_url}{self._api_uri}{endpoint}",  # nosemgrep: python.requests.best-practice.use-timeout.use-timeout
                auth=auth,
                data=data,
                headers=headers,
                params=params,
            )
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return RetVal(
                action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_SERVER_CONNECTION.format(error_message=error_message)), resp_json
            )

        return self._process_response(r, action_result)

    def _make_rest_call_oauth(self, action_result, headers={}, data={}):
        """The API for retrieving the OAuth token is different enough to where its just easier to make a new function"""
        resp_json = None

        try:
            request_url = "{}{}".format(self._base_url, "/oauth_token.do")
            r = requests.post(request_url, data=data)  # nosemgrep
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return (
                action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_SERVER_CONNECTION.format(error_message=error_message)),
                resp_json,
            )

        return self._process_response(r, action_result)

    def _make_rest_call(self, action_result, endpoint, headers=None, params=None, data=None, auth=None, method="get"):
        if headers is None:
            headers = {}
        # Create the headers
        headers.update(self._headers)

        if "Content-Type" not in headers:
            headers.update({"Content-Type": "application/json"})

        resp_json = None
        request_func = getattr(requests, method)

        if not request_func:
            action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_API_UNSUPPORTED_METHOD, method=method)

        try:
            r = request_func(f"{self._base_url}{self._api_uri}{endpoint}", auth=auth, json=data, headers=headers, params=params)
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return (
                action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_SERVER_CONNECTION.format(error_message=error_message)),
                resp_json,
            )

        self._response_headers = r.headers
        return self._process_response(r, action_result)

    def _make_rest_call_helper(self, action_result, endpoint, params={}, data={}, headers={}, method="get", auth=None):
        try:
            return self._make_rest_call(action_result, endpoint, params=params, data=data, headers=headers, method=method, auth=auth)
        except UnauthorizedOAuthTokenException:
            # We should only be here if we didn't generate a new token, and if the old token wasn't valid
            # (Hopefully) this should only happen rarely
            self.debug_print("UnauthorizedOAuthTokenException")
            if self._try_oauth:
                self._try_oauth = False
                ret_val, auth, headers = self._get_authorization_credentials(action_result, force_new=True)
                if phantom.is_fail(ret_val):
                    return RetVal(phantom.APP_ERROR, None)
                return self._make_rest_call_helper(action_result, endpoint, params=params, data=data, headers=headers, method=method, auth=auth)
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to authorize with OAuth token"), None)

    def _upload_file_helper(self, action_result, endpoint, params={}, data={}, headers={}, auth=None):
        try:
            return self._upload_file(action_result, endpoint, params=params, data=data, headers=headers, auth=auth)
        except UnauthorizedOAuthTokenException:
            # We should only be here if we didn't generate a new token, and if the old token wasn't valid
            # (Hopefully) this should only happen rarely
            self.debug_print("UnauthorizedOAuthTokenException")
            if self._try_oauth:
                self._try_oauth = False
                ret_val, auth, headers = self._get_authorization_credentials(action_result, force_new=True)
                if phantom.is_fail(ret_val):
                    return RetVal(phantom.APP_ERROR, None)
                return self._upload_file_helper(action_result, endpoint, params=params, data=data, headers=headers, auth=auth)
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to authorize with OAuth token"), None)

    def _get_new_oauth_token(self, action_result, first_try=True):
        """Generate a new oauth token using the refresh token, if available"""
        params = {}
        params["client_id"] = self._client_id
        params["client_secret"] = self._client_secret
        if self._refresh_token:
            params["refresh_token"] = self._refresh_token
            params["grant_type"] = "refresh_token"
        else:
            config = self.get_config()

            if config.get(SERVICENOW_JSON_USERNAME) and config.get(SERVICENOW_JSON_PASSWORD):
                params["username"] = config[SERVICENOW_JSON_USERNAME]
                params["password"] = config[SERVICENOW_JSON_PASSWORD]
                params["grant_type"] = "password"
            else:
                return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_BASIC_AUTH_NOT_GIVEN_FIRST_TIME), None)

        ret_val, response_json = self._make_rest_call_oauth(action_result, data=params)

        if phantom.is_fail(ret_val) and params["grant_type"] == "refresh_token" and first_try:
            self.debug_print("Unable to generate new key with refresh token")
            if "first_run" in self._state:
                if "last_time" in self._state:
                    self._state = {"first_run": self._state.get("first_run"), "last_time": self._state.get("last_time")}
                else:
                    self._state = {"first_run": self._state.get("first_run")}
            else:
                self._state = {}

            # Try again, using a password
            return self._get_new_oauth_token(action_result, first_try=False)

        if phantom.is_fail(ret_val):
            error_message = action_result.get_message()
            self._access_token, self._refresh_token = None, None
            return RetVal(action_result.set_status(phantom.APP_ERROR, f"Error in token request. Error: {error_message}"), None)

        self._access_token = response_json[SERVICENOW_ACCESS_TOKEN_STRING]
        self._refresh_token = response_json[SERVICENOW_REFRESH_TOKEN_STRING]
        self._state["oauth_token"] = response_json
        self._state["retrieval_time"] = datetime.now().strftime(DT_STR_FORMAT)

        try:
            return RetVal(phantom.APP_SUCCESS, response_json["access_token"])
        except Exception as e:
            if "first_run" in self._state:
                if "last_time" in self._state:
                    self._state = {"first_run": self._state.get("first_run"), "last_time": self._state.get("last_time")}
                else:
                    self._state = {"first_run": self._state.get("first_run")}
            else:
                self._state = {}
            error_message = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(phantom.APP_ERROR, f"Unable to parse access token. {error_message}"), None)

    def _get_oauth_token(self, action_result, force_new=False):
        if self._state.get("oauth_token") and not force_new:
            expires_in = self._state.get("oauth_token", {}).get("expires_in", 0)
            try:
                diff = (datetime.now() - datetime.strptime(self._state["retrieval_time"], DT_STR_FORMAT)).total_seconds()
                self.debug_print(diff)
                if diff < expires_in:
                    self.debug_print("Using old OAuth Token")
                    return RetVal(action_result.set_status(phantom.APP_SUCCESS), self._access_token)
            except KeyError:
                self.debug_print("Key Error")

        self.debug_print("Generating new OAuth Token")
        return self._get_new_oauth_token(action_result)

    def _get_authorization_credentials(self, action_result, force_new=False):
        auth = None
        headers = {}
        if self._use_token:
            self.save_progress("Connecting with OAuth Token")
            ret_val, oauth_token = self._get_oauth_token(action_result, force_new)
            if phantom.is_fail(ret_val):
                return ret_val, None, None
            self.save_progress("OAuth Token Retrieved")
            headers = {"Authorization": f"Bearer {oauth_token}"}
            self._try_oauth = True
        else:
            ret_val = phantom.APP_SUCCESS
            self.save_progress("Connecting with HTTP Basic Auth")
            config = self.get_config()
            if config.get(SERVICENOW_JSON_USERNAME) and config.get(SERVICENOW_JSON_PASSWORD):
                auth = requests.auth.HTTPBasicAuth(config[SERVICENOW_JSON_USERNAME], config[SERVICENOW_JSON_PASSWORD])
            else:
                action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")
                return action_result.get_status(), None, {}
            headers = {}

        return ret_val, auth, headers

    def _check_for_existing_container(self, sdi, label):
        uri = "rest/container?page_size=0&_filter_source_data_identifier="
        filter = "&_filter_label="
        prefix = "&sort=create_time&order=asc"
        request_str = f'{self.get_phantom_base_url()}{uri}"{sdi}"{filter}"{label}"{prefix}'

        try:
            r = requests.get(request_str, verify=False)  # nosemgrep
        except Exception as e:
            self.error_print(f"Error making local rest call: {self._get_error_message_from_exception(e)}")
            return 0, None, None, None

        try:
            resp_json = r.json()
        except Exception as e:
            self.error_print(f"Exception caught parsing JSON: {self._get_error_message_from_exception(e)}")
            return 0, None, None, None

        if resp_json.get("failed"):
            return 0, None, None, None

        count = resp_json.get("count", -1)
        self.debug_print(f"{count} existing container(s) with SDI {sdi}")

        if count > 0:
            if count > 1:
                self.debug_print(f"More than one container exists with SDI {sdi}. Going with oldest.")
            response_data = resp_json["data"][0]
            return response_data["id"], response_data["label"], response_data["name"], response_data["description"]
        elif count < 0:
            self.debug_print("Something went wrong getting container count")
            self.debug_print(resp_json)
        return 0, None, None, None

    def _test_connectivity(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, auth, headers = self._get_authorization_credentials(action_result, force_new=True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        request_params = {"sysparm_limit": "1"}

        action_result = self.add_action_result(ActionResult(param))

        self.save_progress(SERVICENOW_MESSAGE_GET_INCIDENT_TEST)

        ret_val, response = self._make_rest_call_helper(
            action_result, SERVICENOW_TEST_CONNECTIVITY_ENDPOINT, params=request_params, headers=headers, auth=auth
        )

        if phantom.is_fail(ret_val):
            self.debug_print(action_result.get_message())
            message = action_result.get_message()
            if message:
                message = message.strip().rstrip(".")
            self.save_progress(message)
            self.save_progress(SERVICENOW_ERROR_CONNECTIVITY_TEST)
            return action_result.set_status(phantom.APP_ERROR)

        self.save_progress(SERVICENOW_SUCCESS_CONNECTIVITY_TEST)
        return action_result.set_status(phantom.APP_SUCCESS, SERVICENOW_SUCCESS_CONNECTIVITY_TEST)

    def _create_ticket(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        table = param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE)

        endpoint = SERVICENOW_TABLE_ENDPOINT.format(table)

        fields = param.get(SERVICENOW_JSON_FIELDS, "{}")

        try:
            fields = json.loads(fields)
        except json.JSONDecodeError as e:
            error_message = str(e)
            return RetVal(
                action_result.set_status(
                    phantom.APP_ERROR,
                    f"Error building fields dictionary: {error_message}. \
                        Please ensure that provided input is in valid JSON format",
                ),
                None,
            )

        if not isinstance(fields, dict):
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_FIELDS_JSON_PARSE), None)

        data = dict()
        data.update(fields)

        short_desc = param.get(SERVICENOW_JSON_SHORT_DESCRIPTION)
        desc = param.get(SERVICENOW_JSON_DESCRIPTION)

        if (not fields) and (not short_desc) and (SERVICENOW_JSON_DESCRIPTION not in param):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_ONE_PARAM_REQ)

        if short_desc:
            data.update({"short_description": codecs.decode(short_desc, "unicode_escape")})

        if desc:
            json_description = codecs.decode(desc, "unicode_escape")
            data.update({"description": f"{json_description}\n\n{SERVICENOW_TICKET_FOOTNOTE}{self.get_container_id()}"})
        elif "description" in fields:
            field_description = fields.get(SERVICENOW_JSON_DESCRIPTION, "")
            data.update({"description": f"{field_description}\n\n{SERVICENOW_TICKET_FOOTNOTE}{self.get_container_id()}"})
        else:
            data.update({"description": "{}\n\n{}{}".format("", SERVICENOW_TICKET_FOOTNOTE, self.get_container_id())})

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)
        ret_val, response = self._make_rest_call_helper(action_result, endpoint, data=data, auth=auth, headers=headers, method="post")

        if phantom.is_fail(ret_val):
            self.debug_print(action_result.get_message())
            action_result.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR
        if not response.get("result"):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)
        created_ticket_id = response.get("result", {}).get("sys_id")
        res = response.get("result")

        action_result.update_summary({SERVICENOW_JSON_NEW_TICKET_ID: created_ticket_id})

        vault_ids = param.get(SERVICENOW_JSON_VAULT_ID)
        if vault_ids:
            ret_val_attachment, attachments_added = self._handle_multiple_attachements(action_result, table, created_ticket_id, vault_ids)
            if phantom.is_fail(ret_val_attachment):
                # Add a message indicating ticket creation succeeded but attachment upload failed
                action_result.add_data(res)
                action_result.append_to_message("Successfully created the ticket, but failed to add attachment(s)")
                return action_result.get_status()
            res["attachment_details"] = attachments_added

        action_result.add_data(res)
        return action_result.set_status(phantom.APP_SUCCESS)

    def _add_attachment(self, action_result, table, ticket_id, vault_id):
        if not vault_id:
            return (phantom.APP_SUCCESS, None)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE), None

        # Check for file in vault
        try:
            success, message, file_info = phrules.vault_info(vault_id=vault_id)
            file_info = next(iter(file_info))
        except IndexError:
            return action_result.set_status(phantom.APP_ERROR, "Vault file could not be found with supplied Vault ID"), None
        except Exception:
            return action_result.set_status(phantom.APP_ERROR, "Vault ID not valid"), None

        filename = file_info.get("name", vault_id)
        filepath = file_info.get("path")

        mime = magic.Magic(mime=True)
        magic_str = mime.from_file(filepath)
        headers.update({"Content-Type": magic_str})

        try:
            data = open(filepath, "rb").read()
        except Exception as e:
            self._dump_error_log(e, "Error reading the file")
            return (action_result.set_status(phantom.APP_ERROR, "Failed to read file from Vault"), None)

        # Was not detonated before
        self.save_progress("Uploading the file")

        params = {"table_name": table, "table_sys_id": ticket_id, "file_name": filename}

        ret_val, response = self._upload_file_helper(action_result, "/attachment/file", headers=headers, params=params, data=data, auth=auth)

        if phantom.is_fail(ret_val):
            return (action_result.get_status(), response)

        return (phantom.APP_SUCCESS, response)

    def _handle_multiple_attachements(self, action_result, table, ticket_id, vault_ids) -> tuple[bool, list[dict[str, Any]]]:
        attachment_count = 0
        vault_error = {}
        vault_ids = self.csv_to_list(vault_ids)
        responses = []
        for vault_id in vault_ids:
            if vault_id:
                self.save_progress(f"Attaching file to the ticket with vault id {vault_id}")

                try:
                    ret_val, response = self._add_attachment(action_result, table, ticket_id, vault_id)
                    responses.append(response.get("result", {}))

                except Exception as e:
                    error_message = self._get_error_message_from_exception(e)
                    return action_result.set_status(
                        phantom.APP_ERROR,
                        f"Invalid Vault ID, please enter \
                                        valid Vault ID. {error_message}",
                    ), []

                if phantom.is_success(ret_val):
                    attachment_count += 1
                else:
                    if vault_error.get(action_result.get_message()):
                        values = vault_error.get(action_result.get_message())
                        values.append(vault_id)
                        vault_error.update({f"{action_result.get_message()}": values})
                    else:
                        vault_error[action_result.get_message()] = [vault_id]

        action_result.update_summary({"successfully_added_attachments_count": attachment_count})
        if vault_error:
            action_result.update_summary({"vault_failure_details": vault_error})
            return phantom.APP_ERROR, []

        return phantom.APP_SUCCESS, responses

    def _update_ticket(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            table = param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE)
            ticket_id = param[SERVICENOW_JSON_TICKET_ID]
            is_sys_id = param.get("is_sys_id", False)
        except Exception:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        if not is_sys_id:
            params = {"sysparm_query": f"number={ticket_id}"}
            endpoint = SERVICENOW_TABLE_ENDPOINT.format(table)
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            if response.get("result"):
                sys_id = response.get("result")[0].get("sys_id")

                if not sys_id:
                    return action_result.set_status(
                        phantom.APP_ERROR, f"Unable to fetch the ticket SYS ID for the provided ticket number: {ticket_id}"
                    )

                ticket_id = sys_id
            else:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_TICKET_ID_MESSAGE)

        endpoint = SERVICENOW_TICKET_ENDPOINT.format(table, ticket_id)

        fields = param.get(SERVICENOW_JSON_FIELDS, "{}")

        try:
            fields = json.loads(fields)
        except json.JSONDecodeError as e:
            error_message = str(e)
            return RetVal(
                action_result.set_status(
                    phantom.APP_ERROR,
                    f"Error building fields dictionary: {error_message}. \
                        Please ensure that provided input is in valid JSON format",
                ),
                None,
            )

        if not isinstance(fields, dict):
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_FIELDS_JSON_PARSE), None)

        vault_ids = param.get(SERVICENOW_JSON_VAULT_ID)
        if not fields and not vault_ids:
            return action_result.set_status(phantom.APP_ERROR, "Please specify at-least one of fields or vault_id parameter")

        res = {}
        if fields:
            self.save_progress("Updating ticket with the provided fields")
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, data=fields, auth=auth, headers=headers, method="put")

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            action_result.update_summary({"fields_updated": True})
            res.update(response.get("result", {}))

        if vault_ids:
            ret_val_attachment, attachments_added = self._handle_multiple_attachements(action_result, table, ticket_id, vault_ids)

            if phantom.is_fail(ret_val_attachment):
                if fields:
                    # Add a message indicating ticket was updated with other fields but attachment upload failed
                    action_result.add_data(res)
                    action_result.append_to_message("Successfully updated the ticket, but failed to add attachment(s)")
                return action_result.get_status()
            res["attachment_details"] = attachments_added
        action_result.add_data(res)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_ticket_details(self, action_result, table, sys_id, is_sys_id=True):
        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        if not is_sys_id:
            params = {"sysparm_query": f"number={sys_id}"}
            endpoint = SERVICENOW_TABLE_ENDPOINT.format(table)
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            if response.get("result"):
                sys_id = response.get("result")[0].get("sys_id")

                if not sys_id:
                    return action_result.set_status(
                        phantom.APP_ERROR,
                        f"Unable to fetch the ticket SYS ID \
                                    for the provided ticket number: {sys_id}",
                    )

            else:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_TICKET_ID_MESSAGE)

        endpoint = SERVICENOW_TICKET_ENDPOINT.format(table, sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if phantom.is_fail(ret_val):
            self.debug_print(action_result.get_message())
            action_result.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        if not response.get("result"):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)
        ticket = response.get("result", {})

        ticket_sys_id = ticket.get("sys_id")

        params = {"sysparm_query": f"table_sys_id={ticket_sys_id}"}

        # get the attachment details
        ret_val, attach_resp = self._make_rest_call_helper(action_result, "/attachment", auth=auth, headers=headers, params=params)

        # is some versions of servicenow fail the attachment query if not present
        # some pass it with no data if not present, so only add data if present and valid
        if phantom.is_success(ret_val):
            try:
                attach_details = attach_resp["result"]
                ticket["attachment_details"] = attach_details
            except Exception:
                pass

        params = {}
        params["element_id"] = sys_id
        params["sysparm_query"] = "element=comments^ORelement=work_notes"
        ret_val, response = self._make_rest_call_helper(
            action_result, SERVICENOW_SYS_JOURNAL_FIELD_ENDPOINT, auth=auth, headers=headers, params=params
        )

        if phantom.is_fail(ret_val):
            self.debug_print(
                f"Unable to fetch comments and work_notes for \
                    the ticket with sys ID: {ticket_sys_id}. Details: {action_result.get_message()}"
            )

        comment_section = []
        worknotes_section = []
        if response.get("result", []):
            for item in response.get("result", []):
                if item["element"] == "comments":
                    comment_section.append(item.get("value", ""))
                elif item["element"] == "work_notes":
                    worknotes_section.append(item.get("value", ""))

        ticket["comments_section"] = comment_section
        ticket["worknotes_section"] = worknotes_section

        action_result.add_data(ticket)

        return phantom.APP_SUCCESS

    def _get_ticket(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            table_name = param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE)
            ticket_id = param[SERVICENOW_JSON_TICKET_ID]
            is_sys_id = param.get("is_sys_id", False)
        except Exception:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)

        ret_val = self._get_ticket_details(action_result, table_name, ticket_id, is_sys_id=is_sys_id)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        try:
            action_result.update_summary({SERVICENOW_JSON_GOT_TICKET_ID: action_result.get_data()[0]["sys_id"]})
        except Exception:
            pass

        return action_result.set_status(phantom.APP_SUCCESS)

    def _paginator(self, endpoint, action_result, payload=None, limit=None):
        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)
            return None

        items_list = list()
        if not payload:
            payload = dict()

        payload["sysparm_offset"] = SERVICENOW_DEFAULT_OFFSET
        payload["sysparm_limit"] = min(limit, SERVICENOW_DEFAULT_LIMIT)

        while True:
            ret_val, items = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=payload)

            if phantom.is_fail(ret_val):
                return None

            # get total record count from headers
            if self._response_headers:
                total_item_count = int(self._response_headers.get("X-Total-Count", 1))

            # if result is found
            result = items.get("result")
            if result:
                items_list.extend(result if isinstance(result, list) else [result])

            # extend item list if data is present on that page
            if limit and len(items_list) >= limit:
                return items_list[:limit]

            if total_item_count <= limit:
                if total_item_count <= SERVICENOW_DEFAULT_LIMIT:
                    return items_list

            # exit if the total number of records are less than limit or else it has fetched all the pages
            if (payload["sysparm_offset"] + payload["sysparm_limit"]) == total_item_count:
                return items_list

            payload["sysparm_offset"] += payload["sysparm_limit"]
            payload["sysparm_limit"] = min(total_item_count - payload["sysparm_offset"], SERVICENOW_DEFAULT_LIMIT)

    def _describe_service_catalog(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))

        catalog_sys_id = param["sys_id"]

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        request_params = dict()
        request_params["sysparm_query"] = f"sys_id={catalog_sys_id}"

        ret_val, response = self._make_rest_call_helper(
            action_result, SERVICENOW_SC_CATALOG_ENDPOINT, auth=auth, headers=headers, params=request_params
        )

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not response.get("result"):
            return action_result.set_status(phantom.APP_ERROR, "Please enter a valid value for 'catalog_sys_id' parameter")

        final_data = dict()
        final_data.update(response.get("result")[0])

        request_params = dict()
        request_params["sysparm_query"] = f"sc_catalog={catalog_sys_id}"

        ret_val, response = self._make_rest_call_helper(
            action_result, SERVICENOW_SC_CATEGORY_ENDPOINT, auth=auth, headers=headers, params=request_params
        )

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        final_data["categories"] = response.get("result")

        ret_val, processed_services = self._list_services_helper(param, action_result)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        final_data["items"] = processed_services

        action_result.add_data(final_data)

        return action_result.set_status(phantom.APP_SUCCESS, "Details fetched successfully")

    def _describe_catalog_item(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        try:
            sys_id = param["sys_id"]
        except Exception:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        endpoint = SERVICENOW_CATALOG_ITEMS_ENDPOINT.format(sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not response.get("result"):
            return action_result.set_status(phantom.APP_ERROR, f"No data found for the requested item having System ID: {sys_id}")

        action_result.add_data(response.get("result", {}))

        return action_result.set_status(phantom.APP_SUCCESS, "Details fetched successfully")

    def _list_services_helper(self, param, action_result):
        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        ret_val, limit = self._validate_integers(
            action_result, param.get(SERVICENOW_JSON_MAX_RESULTS, SERVICENOW_DEFAULT_MAX_LIMIT), SERVICENOW_JSON_MAX_RESULTS
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status(), None

        payload = dict()
        catalog_sys_id = param.get("catalog_sys_id")
        sys_id = param.get("sys_id")
        category_sys_id = param.get("category_sys_id")
        search_text = param.get("search_text")

        query = list()
        if catalog_sys_id:
            query.append(f"sc_catalogsLIKE{catalog_sys_id}")

        if sys_id:
            query.append(f"sc_catalogsLIKE{sys_id}")

        if category_sys_id:
            query.append(f"category={category_sys_id}")

        if search_text:
            query.append(
                f"nameLIKE{search_text}^ORdescriptionLIKE{search_text}^ORsys_nameLIKE{search_text}^ORshort_descriptionLIKE{search_text}"
            )

        if query:
            search_query = "^".join(query)
            payload["sysparm_query"] = search_query

        services = self._paginator(SERVICENOW_SC_CAT_ITEMS_ENDPOINT, action_result, payload=payload, limit=limit)

        if services is None:
            return action_result.get_status(), None

        return phantom.APP_SUCCESS, services

    def _list_services(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, processed_services = self._list_services_helper(param, action_result)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not processed_services:
            if param.get("catalog_sys_id") or param.get("category_sys_id") or param.get("search_text"):
                return action_result.set_status(phantom.APP_ERROR, "No data found for the given input parameters")

            return action_result.set_status(phantom.APP_ERROR, "No data found")

        for service in processed_services:
            catalogs = service.get("sc_catalogs")
            if catalogs:
                catalogs = catalogs.split(",")
            service["catalogs"] = catalogs
            action_result.add_data(service)

        summary = action_result.update_summary({})
        summary["services_returned"] = action_result.get_data_size()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _list_categories(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, limit = self._validate_integers(
            action_result, param.get(SERVICENOW_JSON_MAX_RESULTS, SERVICENOW_DEFAULT_MAX_LIMIT), SERVICENOW_JSON_MAX_RESULTS
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        service_categories = self._paginator(SERVICENOW_SC_CATEGORY_ENDPOINT, action_result, limit=limit)

        if service_categories is None:
            return action_result.get_status()

        for category in service_categories:
            action_result.add_data(category)

        summary = action_result.update_summary({})
        summary["categories_returned"] = action_result.get_data_size()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _list_service_catalogs(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, limit = self._validate_integers(
            action_result, param.get(SERVICENOW_JSON_MAX_RESULTS, SERVICENOW_DEFAULT_MAX_LIMIT), SERVICENOW_JSON_MAX_RESULTS
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        service_catalogs = self._paginator(SERVICENOW_SC_CATALOG_ENDPOINT, action_result, limit=limit)

        if service_catalogs is None:
            return action_result.get_status()

        for sc in service_catalogs:
            action_result.add_data(sc)

        summary = action_result.update_summary({})
        summary["service_catalogs_returned"] = action_result.get_data_size()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _add_work_note(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            sys_id = param.get("id")
            table_name = param.get("table_name", "incident")
            is_sys_id = param.get("is_sys_id", False)
        except Exception:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        if not is_sys_id:
            params = {"sysparm_query": f"number={sys_id}"}
            endpoint = SERVICENOW_TABLE_ENDPOINT.format(table_name)
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            if response.get("result"):
                new_sys_id = response.get("result")[0].get("sys_id")

                if not new_sys_id:
                    return action_result.set_status(
                        phantom.APP_ERROR,
                        f"Unable to fetch the \
                            ticket SYS ID for the provided ticket number: {sys_id}",
                    )

                sys_id = new_sys_id
            else:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_TICKET_ID_MESSAGE)

        work_note = param.get("work_note")

        endpoint = SERVICENOW_TICKET_ENDPOINT.format(table_name, sys_id)
        data = {"work_notes": work_note.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"').replace("\\b", "\b")}

        request_params = {}
        request_params["sysparm_display_value"] = True

        ret_val, response = self._make_rest_call_helper(
            action_result, endpoint, auth=auth, data=data, headers=headers, params=request_params, method="put"
        )

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if response.get("result", {}).get("work_notes"):
            response["result"]["work_notes"] = response["result"]["work_notes"].replace("\n\n", "\n, ").strip(", ")

        action_result.add_data(response.get("result", {}))

        return action_result.set_status(phantom.APP_SUCCESS, "Added the work note successfully")

    def _request_catalog_item(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        variables_param = param.get("variables")

        ret_val, quantity = self._validate_integers(action_result, param.get("quantity", 1), "quantity")
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        try:
            sys_id = param["sys_id"]
        except Exception:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)

        if variables_param:
            try:
                variables_param = ast.literal_eval(variables_param)
            except Exception as e:
                error_message = self._get_error_message_from_exception(e)
                return RetVal(
                    action_result.set_status(
                        phantom.APP_ERROR,
                        f"Error building fields dictionary: {error_message}. \
                            Please ensure that provided input is in valid JSON format",
                    ),
                    None,
                )

            if not isinstance(variables_param, dict):
                return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_VARIABLES_JSON_PARSE), None)

        endpoint = SERVICENOW_CATALOG_ITEMS_ENDPOINT.format(sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        invalid_variables = list()
        mandatory_variables = list()

        if response.get("result", {}).get("variables"):
            for variable in response.get("result", {}).get("variables"):
                if variable.get("mandatory"):
                    mandatory_variables.append(variable.get("name"))

        if mandatory_variables and not variables_param:
            invalid_variables = mandatory_variables
        else:
            for var in mandatory_variables:
                if var not in list(variables_param.keys()):
                    invalid_variables = mandatory_variables
                    break

        if invalid_variables:
            return action_result.set_status(
                phantom.APP_ERROR,
                "Please provide the mandatory variables to order this item.\
                Mandatory variables: {}".format(", ".join(invalid_variables)),
            )

        endpoint = SERVICENOW_CATALOG_OREDERNOW_ENDPOINT.format(sys_id)

        data = dict()
        data["sysparm_quantity"] = quantity
        if variables_param:
            data["variables"] = variables_param

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, data=data, headers=headers, method="post")

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        request_sys_id = response.get("result", {}).get("sys_id")
        table = response.get("result", {}).get("table")

        self._api_uri = SERVICENOW_API_ENDPOINT
        endpoint = SERVICENOW_TICKET_ENDPOINT.format(table, request_sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        action_result.add_data(response.get("result"))

        return action_result.set_status(phantom.APP_SUCCESS, "The item has been requested")

    def _add_comment(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            sys_id = param.get("id")
            table_name = param.get("table_name", "incident")
            is_sys_id = param.get("is_sys_id", False)
        except Exception:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        if not is_sys_id:
            params = {"sysparm_query": f"number={sys_id}"}
            endpoint = SERVICENOW_TABLE_ENDPOINT.format(table_name)
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            if response.get("result"):
                new_sys_id = response.get("result")[0].get("sys_id")

                if not new_sys_id:
                    return action_result.set_status(
                        phantom.APP_ERROR,
                        f"Unable to fetch the ticket \
                                    SYS ID for the provided ticket number: {sys_id}",
                    )

                sys_id = new_sys_id
            else:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_TICKET_ID_MESSAGE)

        comment = param.get("comment")
        endpoint = SERVICENOW_TICKET_ENDPOINT.format(table_name, sys_id)
        data = {"comments": comment.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"').replace("\\b", "\b")}

        request_params = {}
        request_params["sysparm_display_value"] = True

        ret_val, response = self._make_rest_call_helper(
            action_result, endpoint, auth=auth, data=data, headers=headers, params=request_params, method="put"
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if response.get("result", {}).get("comments"):
            response["result"]["comments"] = response["result"]["comments"].replace("\n\n", "\n, ").strip(", ")
        message = "Added the comment successfully"
        if not response.get("result"):
            message = "No tickets Found"
        action_result.add_data(response.get("result", {}))

        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _list_tickets(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        table_name = param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE)
        endpoint = SERVICENOW_TABLE_ENDPOINT.format(table_name)
        request_params = {"sysparm_query": param.get(SERVICENOW_JSON_FILTER, "")}

        ret_val, limit = self._validate_integers(
            action_result, param.get(SERVICENOW_JSON_MAX_RESULTS, SERVICENOW_DEFAULT_MAX_LIMIT), SERVICENOW_JSON_MAX_RESULTS
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        tickets = self._paginator(endpoint, action_result, payload=request_params, limit=limit)

        if tickets is None:
            return action_result.get_status()

        for ticket in tickets:
            action_result.add_data(ticket)

        action_result.update_summary({SERVICENOW_JSON_TOTAL_TICKETS: action_result.get_data_size()})

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_variables(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))
        sys_id = param[SERVICENOW_JSON_SYS_ID]

        endpoint = SERVICENOW_TABLE_ENDPOINT.format(SERVICENOW_ITEM_OPT_MTOM_TABLE)
        request_params = {"request_item": sys_id}

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=request_params)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        if not response.get("result"):
            return action_result.set_status(phantom.APP_ERROR, f"No data found for the requested item having System ID: {sys_id}")

        variables = dict()
        for item in response["result"]:
            sc_item_option = item.get("sc_item_option")
            if not sc_item_option or not item["sc_item_option"].get("value"):
                return action_result.set_status(
                    phantom.APP_ERROR,
                    f"Error occurred \
                    while fetching variable info for the System ID: {sys_id}",
                )

            item_option_value = item["sc_item_option"]["value"]

            endpoint = SERVICENOW_TICKET_ENDPOINT.format(SERVICENOW_ITEM_OPT_TABLE, item_option_value)
            ret_val, auth, headers = self._get_authorization_credentials(action_result)
            if phantom.is_fail(ret_val):
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            # If no result found or no key for value found, throw error
            if not response.get("result") or response["result"].get("value") is None:
                return action_result.set_status(
                    phantom.APP_ERROR, SERVICENOW_ERROR_FETCH_VALUE.format(item_opt_value=item_option_value, sys_id=sys_id)
                )

            response_value = response["result"]["value"]

            # If no result found or no key for item_option_new found or no key found for
            # value inside item_option_new dictionary, throw error
            new_option = "item_option_new"
            if (
                not response.get("result")
                or response["result"].get(new_option) is None
                or (isinstance(response["result"][new_option], dict) and not response["result"][new_option].get("value"))
            ):
                return action_result.set_status(
                    phantom.APP_ERROR, SERVICENOW_ERROR_FETCH_QUESTION_ID.format(item_opt_value=item_option_value, sys_id=sys_id)
                )

            # The dictionary for item_option_new can be empty if no question is available
            # for a given variable which is a valid scenario
            if not response["result"]["item_option_new"]:
                response_question = ""
                variables[response_question] = response_value
                continue
            question_id = response["result"]["item_option_new"]["value"]

            endpoint = SERVICENOW_TICKET_ENDPOINT.format(SERVICENOW_ITEM_OPT_NEW_TABLE, question_id)
            ret_val, auth, headers = self._get_authorization_credentials(action_result)
            if phantom.is_fail(ret_val):
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

            if phantom.is_fail(ret_val):
                return action_result.get_status()

            # If no result found or no key for question_text found, throw error
            if not response.get("result") or response["result"].get("question_text") is None:
                return action_result.set_status(
                    phantom.APP_ERROR,
                    SERVICENOW_ERROR_FETCH_QUESTION.format(question_id=question_id, item_opt_value=item_option_value, sys_id=sys_id),
                )

            response_question = response["result"]["question_text"]

            variables[response_question] = response_value

        summary = action_result.update_summary({})
        summary["num_variables"] = len(variables)

        action_result.add_data(variables)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _run_query(self, param, action_result_param=None, summary_text=None, strip_props=[]):
        if action_result_param:
            action_result = self.add_action_result(ActionResult(dict(action_result_param)))
        else:
            action_result = self.add_action_result(ActionResult(dict(param)))

        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        lookup_table = param[SERVICENOW_JSON_QUERY_TABLE]
        query = param[SERVICENOW_JSON_QUERY]
        endpoint = f"{SERVICENOW_BASE_QUERY_URI}{lookup_table}?{query}"
        ret_val, limit = self._validate_integers(
            action_result, param.get(SERVICENOW_JSON_MAX_RESULTS, SERVICENOW_DEFAULT_MAX_LIMIT), SERVICENOW_JSON_MAX_RESULTS
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        ret_val, auth, headers = self._get_authorization_credentials(action_result)

        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        tickets = self._paginator(endpoint, action_result, limit=limit)

        if tickets is None:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_INVALID_PARAMETER_MESSAGE)

        for ticket in tickets:
            for prop_to_strip in strip_props:
                ticket.pop(prop_to_strip, None)
            action_result.add_data(ticket)

        if not summary_text:
            summary_text = SERVICENOW_JSON_TOTAL_TICKETS
        action_result.update_summary({summary_text: action_result.get_data_size()})

        return action_result.set_status(phantom.APP_SUCCESS)

    def _query_users(self, param):
        action_result_param = param.copy()
        query = param.get(SERVICENOW_JSON_QUERY, "")
        param[SERVICENOW_JSON_QUERY] = query
        if not query:
            user_id = param.get(SERVICENOW_JSON_USER_ID)
            if user_id:
                param[SERVICENOW_JSON_QUERY] = SERVICENOW_JSON_SYSPARM_SYS_ID_QUERY.format(user_id)

            username = param.get(SERVICENOW_JSON_USERNAME)
            if username:
                param[SERVICENOW_JSON_QUERY] = SERVICENOW_JSON_SYSPARM_USER_NAME_QUERY.format(username)

        param[SERVICENOW_JSON_QUERY_TABLE] = SERVICENOW_JSON_SYS_USER_TABLE
        result = self._run_query(param, action_result_param, SERVICENOW_JSON_TOTAL_USERS, [SERVICENOW_JSON_USER_PASSWORD])

        return result

    def _search_sources_details(self, action_result, sysparm_term, sysparm_search_sources):
        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_AUTH_ERROR_MESSAGE)

        params = {"sysparm_term": sysparm_term, "sysparm_search_sources": sysparm_search_sources}
        params["sysparm_page"] = SERVICENOW_DEFAULT_PAGE
        params["sysparm_limit"] = SERVICENOW_MAX_LIMIT

        items_list = []
        result_length = 0
        first_call = True
        total_result_count_page_limit = 0

        while True:
            ret_val, response = self._make_rest_call_helper(
                action_result, SERVICENOW_SEARCH_SOURCE_ENDPOINT, auth=auth, headers=headers, params=params
            )
            if phantom.is_fail(ret_val):
                self.debug_print(action_result.get_message())
                return action_result.set_status(phantom.APP_ERROR, action_result.get_message())

            total_item_count = int(response.get("result", {}).get("result_count", 0))
            search_results_len = len(response.get("result").get("search_results", []))
            for i in range(search_results_len):
                response.get("result").get("search_results", [])[i].pop("limit")
                response.get("result").get("search_results", [])[i].pop("page")
                result_length += len(response.get("result").get("search_results", [])[i].get("records", []))

            # Initially fetch response['result'] and extend records into it in subsequent calls
            # Add total pages to iterate in the first call to handle empty records due to ACLs
            # ServiceNow returns up to 20 records per page by default
            if first_call:
                items_list.append(response["result"])
                total_result_count_page_limit = total_item_count // 20
                first_call = False
            else:
                for i in range(search_results_len):
                    data = response.get("result").get("search_results", [])[i].get("records", [])
                    items_list[0].get("search_results", [])[i].get("records", []).extend(data)

            # If we got all the results or if we reached maximum pages
            if total_item_count <= result_length or params["sysparm_page"] >= total_result_count_page_limit + 1:
                break
            params["sysparm_page"] = params["sysparm_page"] + 1

        action_result.add_data(items_list)
        action_result.update_summary({SERVICENOW_JSON_TOTAL_RECORDS: total_item_count})
        return phantom.APP_SUCCESS

    def _search_sources(self, param):
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")
        action_result = self.add_action_result(ActionResult(dict(param)))

        sysparm_term = param[SERVICENOW_JSON_SYSPARM_TERM]
        sysparm_search_sources = param[SERVICENOW_JSON_SYSPARM_SEARCH_SOURCES]

        search_sources = [x.strip() for x in set(sysparm_search_sources.split(",")) if x.strip()]

        if not search_sources:
            return action_result.set_status(phantom.APP_ERROR, "Please provide valid inputs for sysparm_search_sources"), None

        sysparm_search_sources = ",".join(search_sources)
        ret_val = self._search_sources_details(action_result, sysparm_term, sysparm_search_sources)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _on_poll(self, param):
        URI_REGEX = "[Hh][Tt][Tt][Pp][Ss]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        HASH_REGEX = "\\b[0-9a-fA-F]{32}\\b|\\b[0-9a-fA-F]{40}\\b|\\b[0-9a-fA-F]{64}\\b"
        IP_REGEX = "\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}"
        IPV6_REGEX = "\\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|"
        IPV6_REGEX += (
            "(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3})|:))"
        )
        IPV6_REGEX += (
            "|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:"
            "((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3})|:))|"
        )
        IPV6_REGEX += (
            "(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:"
            "((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\."
            "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|"
        )
        IPV6_REGEX += (
            "(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:"
            "[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\."
            "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|"
        )
        IPV6_REGEX += (
            "(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|"
            "((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\."
            "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|"
        )
        IPV6_REGEX += (
            "(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|"
            "((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\."
            "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|"
        )
        IPV6_REGEX += (
            "(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\\d|1\\d\\d|"
            "[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:)))(%.+)?\\s*"
        )
        uri_regexc = re.compile(URI_REGEX)
        hash_regexc = re.compile(HASH_REGEX)
        ip_regexc = re.compile(IP_REGEX)
        ipv6_regexc = re.compile(IPV6_REGEX)
        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        # Get config
        config = self.get_config()

        # Add action result
        action_result = self.add_action_result(phantom.ActionResult(param))

        # Get time from last poll, save now as time for this poll
        last_time = self._state.get("last_time")

        if last_time and isinstance(last_time, float):
            last_time = datetime.strftime(datetime.fromtimestamp(last_time), SERVICENOW_DATETIME_FORMAT)

        # Build the query for the issue search (sysparm_query)
        query = "ORDERBYsys_updated_on"

        action_query = config.get(SERVICENOW_JSON_ON_POLL_FILTER, "")

        if len(action_query) > 0:
            query += f"^{action_query}"

        # If it's a poll now don't filter based on update time
        if self.is_poll_now():
            max_tickets = param.get(phantom.APP_JSON_CONTAINER_COUNT)
        # If it's the first poll, don't filter based on update time
        elif self._state.get("first_run", True):
            self._state["first_run"] = False
            max_tickets = self._first_run_container
        # If it's scheduled polling add a filter for update time being greater than the last poll time
        else:
            # "last_time" should be of the format "%Y-%m-%d %H:%M:%S"
            if last_time and len(last_time.split(" ")) == 2:
                query_prefix = last_time.split(" ")
                query += f"^sys_updated_on>=javascript:gs.dateGenerate('{query_prefix[0]}','{query_prefix[1]}')"
                max_tickets = self._max_container
            else:
                self.debug_print(
                    f"Either 'last_time' is None or empty or it is not \
                    in the expected format of %Y-%m-%d %H:%M:%S. last_time: {last_time}"
                )
                self.debug_print(
                    "Considering this as the first scheduled|interval \
                    polling run; skipping time-based query filtering; processing the on_poll workflow accordingly"
                )

                max_tickets = self._first_run_container

                self.debug_print(f"Setting the 'max_tickets' to the value of 'first_run_container'. max_tickets: {max_tickets}")

        self.debug_print(f"Polling with this query: {query}")

        on_poll_table_name = config.get(SERVICENOW_JSON_ON_POLL_TABLE, SERVICENOW_DEFAULT_TABLE)
        endpoint = SERVICENOW_TABLE_ENDPOINT.format(on_poll_table_name.lower())
        params = {"sysparm_query": query, "sysparm_exclude_reference_link": "true"}

        limit = max_tickets

        issues = self._paginator(endpoint, action_result, payload=params, limit=limit)

        if issues is None:
            self.debug_print(action_result.get_message())
            action_result.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        if not issues:
            return action_result.set_status(phantom.APP_SUCCESS, "No issues found. Nothing to ingest.")

        # TODO: handle cases where we go over the ingestions limit

        # Ingest the issues
        failed = 0
        label = self.get_config().get("ingest", {}).get("container_label")

        if config.get("severity"):
            severity = config.get("severity", "medium").lower()
            ret_val, message = self._validate_custom_severity(action_result, severity)
            if phantom.is_fail(ret_val):
                return action_result.get_status()
        else:
            ret_val, default_severity = self._find_default_severity(action_result)
            if phantom.is_fail(ret_val):
                return action_result.get_status()
            severity = config.get("severity", default_severity).lower()

        for issue in issues:
            sdi = issue["sys_id"]
            sd = issue.get("short_description")
            desc = issue.get("description", "")
            existing_label = None
            existing_sd = None
            existing_desc = None

            container_id, existing_label, existing_sd, existing_desc = self._check_for_existing_container(sdi, label)
            if not sd:
                sd = "Phantom added container name (short description of the ticket/record found empty)"

            if not container_id or existing_label != label:
                desc = issue.get("description", "")
                container = dict(
                    data=issue, description=desc, label=label, severity=severity, name=f"{sd}", source_data_identifier=issue["sys_id"]
                )
                ret_val, _, container_id = self.save_container(container)

                if phantom.is_fail(ret_val):
                    failed += 1
                    continue

            artifacts = []
            artifact_dict = dict(
                container_id=container_id,
                data=issue,
                description=sd,
                cef=issue,
                label="issue",
                severity=severity,
                name=issue.get("number", "Phantom added artifact name (number of the ticket/record found empty)"),
                source_data_identifier=issue["sys_id"],
            )
            artifacts.append(artifact_dict)
            extract_ips = config.get(SERVICENOW_JSON_EXTRACT_IPS)
            extract_hashes = config.get(SERVICENOW_JSON_EXTRACT_HASHES)
            extract_url = config.get(SERVICENOW_JSON_EXTRACT_URLS)
            if extract_ips:
                for match in ip_regexc.finditer(str(issue)):
                    cef = {}
                    cef["ip_address"] = match.group()
                    art = {"container_id": container_id, "label": "IP Address", "cef": cef}
                    artifacts.append(art)

                for match in ipv6_regexc.finditer(str(issue)):
                    cef = {}
                    cef["ipv6_address"] = match.group()
                    art = {"container_id": container_id, "label": "IPV6 Address", "cef": cef}
                    artifacts.append(art)

            if extract_hashes:
                for match in hash_regexc.finditer(str(issue)):
                    cef = {}
                    cef["hash"] = match.group()
                    art = {"container_id": container_id, "label": "Hash", "cef": cef}
                    artifacts.append(art)

            if extract_url:
                for match in uri_regexc.finditer(str(issue)):
                    cef = {}
                    cef["URL"] = match.group()
                    art = {"container_id": container_id, "label": "URL", "cef": cef}
                    artifacts.append(art)
            self.save_artifacts(artifacts)

        action_result.set_status(phantom.APP_SUCCESS, "Containers created")

        if not self.is_poll_now():
            if "sys_updated_on" not in issues[-1]:
                return action_result.set_status(phantom.APP_ERROR, "No updated time in last ingested incident.")

            updated_time = issues[-1]["sys_updated_on"]

            if "timezone" in config:
                dt = datetime.strptime(updated_time, SERVICENOW_DATETIME_FORMAT)
                tz = ZoneInfo(config["timezone"])
                new_dt = dt + (tz.utcoffset(dt) or timedelta(0))
                updated_time = new_dt.strftime(SERVICENOW_DATETIME_FORMAT)

            self._state["last_time"] = updated_time

            if self._state.get("first_run", True):
                self._state["first_run"] = False

        if failed:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERROR_FAILURES)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _find_default_severity(self, action_result):
        try:
            r = requests.get(f"{self._get_phantom_base_url()}rest/severity", verify=False)  # nosemgrep
            resp_json = r.json()
        except Exception as e:
            self._dump_error_log(e, "Error occurred while finding default severity")
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_SEVERITY_MESSAGE.format(e)), None)

        if r.status_code == 401:
            return RetVal(
                action_result.set_status(
                    phantom.APP_ERROR, SERVICENOW_SEVERITY_MESSAGE.format(resp_json.get("message", "Authentication Error"))
                ),
                None,
            )

        if r.status_code != 200:
            return RetVal(
                action_result.set_status(phantom.APP_ERROR, SERVICENOW_SEVERITY_MESSAGE.format(resp_json.get("message", "Unknown Error"))), None
            )

        severity = None

        for severity_data in resp_json["data"]:
            if severity_data.get("is_default", False):
                severity = severity_data["name"]
                break

        return RetVal(phantom.APP_SUCCESS, severity)

    def _validate_custom_severity(self, action_result, severity):
        try:
            r = requests.get(f"{self._get_phantom_base_url()}rest/severity", verify=False)  # nosemgrep
            resp_json = r.json()
        except Exception as e:
            self._dump_error_log(e, "Error occurred while finding custom severity")
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_SEVERITY_MESSAGE.format(e)), None)

        if r.status_code == 401:
            return RetVal(
                action_result.set_status(
                    phantom.APP_ERROR, SERVICENOW_SEVERITY_MESSAGE.format(resp_json.get("message", "Authentication Error"))
                ),
                None,
            )

        if r.status_code != 200:
            return RetVal(
                action_result.set_status(phantom.APP_ERROR, SERVICENOW_SEVERITY_MESSAGE.format(resp_json.get("message", "Unknown Error"))), None
            )

        severities = [s["name"] for s in resp_json["data"]]

        if severity not in severities:
            return RetVal(
                action_result.set_status(
                    phantom.APP_ERROR,
                    "Supplied severity, {}, \
                not found in configured severities: {}".format(severity, ", ".join(severities)),
                ),
                None,
            )

        return RetVal(phantom.APP_SUCCESS, {})

    def handle_action(self, param):
        """Function that handles all the actions

        Args:

        Return:
            A status code
        """

        # Get the action that we are supposed to carry out, set it in the connection result object
        action = self.get_action_identifier()

        ret_val = phantom.APP_SUCCESS

        if action == self.ACTION_ID_CREATE_TICKET:
            ret_val = self._create_ticket(param)
        elif action == self.ACTION_ID_ADD_WORK_NOTE:
            ret_val = self._add_work_note(param)
        elif action == self.ACTION_ID_ORDER_ITEM:
            ret_val = self._request_catalog_item(param)
        elif action == self.ACTION_ID_ADD_COMMENT:
            ret_val = self._add_comment(param)
        elif action == self.ACTION_ID_DESCRIBE_SERVICE_CATALOG:
            ret_val = self._describe_service_catalog(param)
        elif action == self.ACTION_ID_DESCRIBE_CATALOG_ITEM:
            ret_val = self._describe_catalog_item(param)
        elif action == self.ACTION_ID_LIST_SERVICES:
            ret_val = self._list_services(param)
        elif action == self.ACTION_ID_LIST_CATEGORIES:
            ret_val = self._list_categories(param)
        elif action == self.ACTION_ID_LIST_SERVICE_CATALOGS:
            ret_val = self._list_service_catalogs(param)
        elif action == self.ACTION_ID_LIST_TICKETS:
            ret_val = self._list_tickets(param)
        elif action == self.ACTION_ID_GET_TICKET:
            ret_val = self._get_ticket(param)
        elif action == self.ACTION_ID_UPDATE_TICKET:
            ret_val = self._update_ticket(param)
        elif action == self.ACTION_ID_GET_VARIABLES:
            ret_val = self._get_variables(param)
        elif action == self.ACTION_ID_SEARCH_SOURCES:
            ret_val = self._search_sources(param)
        elif action == self.ACTION_ID_ON_POLL:
            ret_val = self._on_poll(param)
        elif action == phantom.ACTION_ID_TEST_ASSET_CONNECTIVITY:
            ret_val = self._test_connectivity(param)
        elif action == self.ACTION_ID_RUN_QUERY:
            ret_val = self._run_query(param)
        elif action == self.ACTION_ID_QUERY_USERS:
            ret_val = self._query_users(param)
        return ret_val


if __name__ == "__main__":
    import argparse

    import pudb

    pudb.set_trace()

    argparser = argparse.ArgumentParser()

    argparser.add_argument("input_test_json", help="Input Test JSON file")
    argparser.add_argument("-u", "--username", help="username", required=False)
    argparser.add_argument("-p", "--password", help="password", required=False)
    argparser.add_argument("-v", "--verify", action="store_true", help="verify", required=False, default=False)

    args = argparser.parse_args()
    session_id = None

    username = args.username
    password = args.password
    verify = args.verify

    if username is not None and password is None:
        # User specified a username but not a password, so ask
        import getpass

        password = getpass.getpass("Password: ")

    if username and password:
        try:
            print("Accessing the Login page")
            login_url = "{}{}".format(BaseConnector._get_phantom_base_url(), "login")
            r = requests.get(login_url, verify=verify)  # nosemgrep: python.requests.best-practice.use-timeout.use-timeout
            csrftoken = r.cookies["csrftoken"]

            data = dict()
            data["username"] = username
            data["password"] = password
            data["csrfmiddlewaretoken"] = csrftoken

            headers = dict()
            headers["Cookie"] = f"csrftoken={csrftoken}"
            headers["Referer"] = "{}{}".format(BaseConnector._get_phantom_base_url(), "login")

            print("Logging into Platform to get the session id")
            r2 = requests.post(
                login_url,
                verify=verify,
                data=data,
                headers=headers,  # nosemgrep: python.requests.best-practice.use-timeout.use-timeout
            )
            session_id = r2.cookies["sessionid"]
        except Exception as e:
            print(f"Unable to get session id from the platform. Error: {e!s}")
            sys.exit(1)

    with open(args.input_test_json) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = ServicenowConnector()
        connector.print_progress_message = True

        if session_id is not None:
            in_json["user_session_token"] = session_id
            connector._set_csrf_info(csrftoken, headers["Referer"])

        ret_val = connector._handle_action(json.dumps(in_json), None)
        print(json.dumps(json.loads(ret_val), indent=4))

    sys.exit(0)
