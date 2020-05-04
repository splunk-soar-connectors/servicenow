# File: servicenow_connector.py
# Copyright (c) 2016-2020 Splunk Inc.
#
# SPLUNK CONFIDENTIAL - Use or disclosure of this material in whole or in part
# without a valid written license from Splunk Inc. is PROHIBITED.
#
# --

# Phantom imports
import phantom.app as phantom
from phantom.base_connector import BaseConnector
from phantom.action_result import ActionResult
from phantom.vault import Vault

# THIS Connector imports
from servicenow_consts import *

import sys
import json
import magic
import requests
from bs4 import BeautifulSoup
from bs4 import UnicodeDammit
from datetime import datetime
import re


DT_STR_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


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

    def __init__(self):

        # Call the BaseConnectors init first
        super(ServicenowConnector, self).__init__()

        self._state_file_path = None
        self._try_oauth = False
        self._use_token = False
        self._state = {}

    def finalize(self):
        self.save_state(self._state)
        return phantom.APP_SUCCESS

    def initialize(self):

        self._state = self.load_state()
        config = self.get_config()
        sn_sc_actions = ["describe_catalog_item", "request_catalog_item"]

        # Fetching the Python major version
        try:
            self._python_version = int(sys.version_info[0])
        except:
            return self.set_status(phantom.APP_ERROR, "Error occurred while getting the Phantom server's Python major version.")

        # Base URL
        self._base_url = self._handle_py_ver_compat_for_input_str(config[SERVICENOW_JSON_DEVICE_URL])
        if (self._base_url.endswith('/')):
            self._base_url = self._base_url[:-1]

        try:
            self._first_run_container = int(config.get('first_run_container', SERVICENOW_DEFAULT_LIMIT))
            if self._first_run_container <= 0:
                return self.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="first_run_container"))
        except:
            return self.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="first_run_container"))

        try:
            self._max_container = int(config.get('max_container', DEFAULT_MAX_RESULTS))
            if self._max_container <= 0:
                return self.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_container"))
        except:
            return self.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_container"))

        self._host = self._base_url[self._base_url.find('//') + 2:]
        self._headers = {'Accept': 'application/json'}
        # self._headers.update({'X-no-response-body': 'true'})
        self._api_uri = '/api/now'
        if self.get_action_identifier() in sn_sc_actions:
            self._api_uri = '/api/sn_sc'

        self._client_id = config.get(SERVICENOW_JSON_CLIENT_ID, None)
        if (self._client_id):
            try:
                self._client_secret = config[SERVICENOW_JSON_CLIENT_SECRET]
                self._use_token = True
            except KeyError:
                self.save_progress("Missing Client Secret")
                return phantom.APP_ERROR

        return phantom.APP_SUCCESS

    def _handle_py_ver_compat_for_input_str(self, input_str):
        """
        This method returns the encoded|original string based on the Python version.
        :param python_version: Information of the Python version
        :param input_str: Input string to be processed
        :return: input_str (Processed input string based on following logic 'input_str - Python 3; encoded input_str - Python 2')
        """

        try:
            if input_str and self._python_version == 2:
                input_str = UnicodeDammit(input_str).unicode_markup.encode('utf-8')
        except:
            self.debug_print("Error occurred while handling python 2to3 compatibility for the input string")

        return input_str

    def _get_error_details(self, resp_json):

        # Initialize the default error_details
        error_details = {"message": "Not Found", "detail": "Not supplied"}

        # Handle if resp_json unavailable
        if (not resp_json):
            return error_details

        # Handle if resp_json contains "error" key and corresponding non-none and non-empty value or not
        error_info = resp_json.get("error")

        if (not error_info):
            return error_details
        else:
            if (isinstance(error_info, dict)):
                error_details = error_info
            else:
                return error_details

        # Handle the scenario of "message" and "detail" keys not in the required format
        if ("message" not in error_details):
            error_details["message"] = "Not Found"

        if ("detail" not in error_details):
            error_details["detail"] = "Not supplied"

        # Handle the Unicode characters in the error information
        error_details["message"] = self._handle_py_ver_compat_for_input_str(error_details["message"])
        error_details["detail"] = self._handle_py_ver_compat_for_input_str(error_details["detail"])

        return error_details

    def _process_empty_reponse(self, response, action_result):

        # this function will parse the header and create the response that the callers
        # of the app expect
        location = response.headers.get('Location')

        if (not location):
            if (200 <= response.status_code < 205):
                return RetVal(phantom.APP_SUCCESS, {})
            else:
                return RetVal(action_result.set_status(phantom.APP_ERROR, "Empty response and no information in the header"), None)

        if (location.startswith(self._base_url + self._api_uri + '/table')):
            resp_json = dict()
            try:
                sys_id = location.rsplit('/', 1)[-1]
                resp_json = {'result': {'sys_id': sys_id}}
            except:
                return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to process empty response for 'table'"), None)

            return RetVal(phantom.APP_SUCCESS, resp_json)

        return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to process empty response"), None)

    def _process_html_response(self, response, action_result):

        # An html response, is bound to be an error
        status_code = response.status_code

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            error_text = soup.text
            split_lines = error_text.split('\n')
            split_lines = [x.strip() for x in split_lines if x.strip()]
            error_text = '\n'.join(split_lines)
        except:
            error_text = "Cannot parse error details"

        error_text = self._handle_py_ver_compat_for_input_str(error_text)

        message = "Status Code: {0}. Data from server:\n{1}\n".format(status_code,
                error_text)

        message = message.replace('{', ' ').replace('}', ' ')

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_json_response(self, r, action_result):

        # Try a json parse
        try:
            resp_json = r.json()
        except Exception as e:
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to parse response as JSON", e), None)

        # What's with the special case 201?
        if (200 <= r.status_code < 205):
            return RetVal(phantom.APP_SUCCESS, resp_json)

        if (r.status_code == 401 and self._try_oauth):
            if resp_json.get('error') == 'invalid_token':
                raise UnauthorizedOAuthTokenException

        if (r.status_code != requests.codes.ok):  # pylint: disable=E1101
            error_details = self._get_error_details(resp_json)
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FROM_SERVER.format(status=r.status_code, **error_details)), resp_json)

        return RetVal(phantom.APP_SUCCESS, resp_json)

    def _process_response(self, r, action_result):

        # store the r_text in debug data, it will get dumped in the logs if an error occurs
        if hasattr(action_result, 'add_debug_data'):
            if (r is not None):
                action_result.add_debug_data({'r_text': r.text})
                action_result.add_debug_data({'r_headers': r.headers})
                action_result.add_debug_data({'r_status_code': r.status_code})
            else:
                action_result.add_debug_data({'r_text': 'r is None'})

        # There are just too many differences in the response to handle all of them in the same function
        if ('json' in r.headers.get('Content-Type', '')):
            return self._process_json_response(r, action_result)

        if ('html' in r.headers.get('Content-Type', '')):
            return self._process_html_response(r, action_result)

        # it's not an html or json, handle if it is a successfull empty reponse
        if (200 <= r.status_code < 205) and (not r.text):
            return self._process_empty_reponse(r, action_result)

        # everything else is actually an error at this point
        message = "Can't process resonse from server. Status Code: {0} Data from server: {1}".format(
                r.status_code, self._handle_py_ver_compat_for_input_str(r.text.replace('{', ' ').replace('}', ' ')))

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _upload_file(self, action_result, endpoint, headers={}, params=None, data=None, auth=None):

        # Create the headers
        headers.update(self._headers)

        resp_json = None

        try:
            r = requests.post('{}{}{}'.format(self._base_url, self._api_uri, endpoint),
                    auth=auth,
                    data=data,
                    headers=headers,
                    params=params)
        except Exception as e:
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_SERVER_CONNECTION, e), resp_json)

        return self._process_response(r, action_result)

    def _make_rest_call_oauth(self, action_result, headers={}, data={}):
        """ The API for retrieving the OAuth token is different enough to where its just easier to make a new function
        """
        resp_json = None

        try:
            r = requests.post(
                    self._base_url + '/oauth_token.do',
                    data=data  # Mostly this line
            )
        except Exception as e:
            return (action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_SERVER_CONNECTION, e), resp_json)

        return self._process_response(r, action_result)

    def _make_rest_call(self, action_result, endpoint, headers={}, params=None, data=None, auth=None, method="get"):

        # Create the headers
        headers.update(self._headers)

        if ('Content-Type' not in headers):
            headers.update({'Content-Type': 'application/json'})

        resp_json = None

        request_func = getattr(requests, method)

        if (not request_func):
            action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_API_UNSUPPORTED_METHOD, method=method)

        try:
            r = request_func('{}{}{}'.format(self._base_url, self._api_uri, endpoint),
                    auth=auth,
                    json=data,
                    headers=headers,
                    params=params)
        except Exception as e:
            return (action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_SERVER_CONNECTION, e), resp_json)

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
                if (phantom.is_fail(ret_val)):
                    return RetVal(phantom.APP_ERROR, None)
                return self._make_rest_call_helper(
                    action_result, endpoint, params=params, data=data, headers=headers, method=method, auth=auth
                )
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
                if (phantom.is_fail(ret_val)):
                    return RetVal(phantom.APP_ERROR, None)
                return self._upload_file_helper(
                    action_result, endpoint, params=params, data=data, headers=headers, auth=auth
                )
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to authorize with OAuth token"), None)

    def _get_new_oauth_token(self, action_result):
        """Generate a new oauth token using the refresh token, if available
        """
        params = {}
        params['client_id'] = self._client_id
        params['client_secret'] = self._client_secret
        try:
            params['refresh_token'] = self._state['oauth_token']['refresh_token']
            params['grant_type'] = "refresh_token"
        except KeyError:
            config = self.get_config()

            if config.get(SERVICENOW_JSON_USERNAME) and config.get(SERVICENOW_JSON_PASSWORD):
                params['username'] = config[SERVICENOW_JSON_USERNAME]
                params['password'] = config[SERVICENOW_JSON_PASSWORD]
                params['grant_type'] = "password"
            else:
                return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_BASIC_AUTH_NOT_GIVEN_FIRST_TIME), None)

        ret_val, response_json = self._make_rest_call_oauth(action_result, data=params)

        if (phantom.is_fail(ret_val) and params['grant_type'] == 'refresh_token'):
            self.debug_print("Unable to generate new key with refresh token")
            if 'first_run' in self._state:
                if 'last_time' in self._state:
                    self._state = {'first_run': self._state.get('first_run'), 'last_time': self._state.get('last_time')}
                else:
                    self._state = {'first_run': self._state.get('first_run')}
            else:
                self._state = {}
            # Try again, using a password
            return self._get_new_oauth_token(action_result)

        if (phantom.is_fail(ret_val)):
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Error in token request"), None)

        self._state['oauth_token'] = response_json
        self._state['retrieval_time'] = datetime.now().strftime(DT_STR_FORMAT)
        try:
            return RetVal(phantom.APP_SUCCESS, response_json['access_token'])
        except Exception as e:
            if 'first_run' in self._state:
                if 'last_time' in self._state:
                    self._state = {'first_run': self._state.get('first_run'), 'last_time': self._state.get('last_time')}
                else:
                    self._state = {'first_run': self._state.get('first_run')}
            else:
                self._state = {}
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to parse access token", e), None)

    def _get_oauth_token(self, action_result, force_new=False):
        if (self._state.get('oauth_token') and not force_new):
            expires_in = self._state.get('oauth_token', {}).get('expires_in', 0)
            try:
                diff = (datetime.now() - datetime.strptime(self._state['retrieval_time'], DT_STR_FORMAT)).total_seconds()
                self.debug_print(diff)
                if (diff < expires_in):
                    self.debug_print("Using old OAuth Token")
                    return RetVal(action_result.set_status(phantom.APP_SUCCESS), self._state['oauth_token']['access_token'])
            except KeyError:
                self.debug_print("Key Error")

        self.debug_print("Generating new OAuth Token")
        return self._get_new_oauth_token(action_result)

    def _get_authorization_credentials(self, action_result, force_new=False):
        auth = None
        headers = {}
        if (self._use_token):
            self.save_progress("Connecting with OAuth Token")
            ret_val, oauth_token = self._get_oauth_token(action_result, force_new)
            if (phantom.is_fail(ret_val)):
                return ret_val, None, None
            self.save_progress("OAuth Token Retrieved")
            headers = {'Authorization': 'Bearer {0}'.format(oauth_token)}
            self._try_oauth = True
        else:
            ret_val = phantom.APP_SUCCESS
            self.save_progress("Connecting with HTTP Basic Auth")
            config = self.get_config()
            if config.get(SERVICENOW_JSON_USERNAME) and config.get(SERVICENOW_JSON_PASSWORD):
                auth = requests.auth.HTTPBasicAuth(config[SERVICENOW_JSON_USERNAME], config[SERVICENOW_JSON_PASSWORD])
            else:
                action_result.set_status(phantom.APP_ERROR, 'Unable to get authorization credentials')
                return action_result.get_status(), None, {}
            headers = {}

        return ret_val, auth, headers

    def _test_connectivity(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        endpoint = '/table/incident'
        request_params = {'sysparm_limit': '1'}

        action_result = self.add_action_result(ActionResult(param))

        self.save_progress(SERVICENOW_MSG_GET_INCIDENT_TEST)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, params=request_params, headers=headers, auth=auth)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            message = action_result.get_message()
            if message:
                message = message.strip().rstrip('.')
            self.save_progress(message)
            self.save_progress(SERVICENOW_ERR_CONNECTIVITY_TEST)
            return action_result.set_status(phantom.APP_ERROR)

        self.save_progress(SERVICENOW_SUCC_CONNECTIVITY_TEST)
        return action_result.set_status(phantom.APP_SUCCESS, SERVICENOW_SUCC_CONNECTIVITY_TEST)

    def _get_fields(self, param, action_result):

        fields = param.get(SERVICENOW_JSON_FIELDS)

        # fields is an optional field
        if (not fields):
            return RetVal(phantom.APP_SUCCESS, None)

        # we take in as a dictionary string, first try to load it as is
        try:
            fields = json.loads(fields)
        except Exception as e:
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FIELDS_JSON_PARSE, e), None)

        return RetVal(phantom.APP_SUCCESS, fields)

    def _create_ticket(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        table = self._handle_py_ver_compat_for_input_str(param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE))

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        endpoint = '/table/{0}'.format(table)

        ret_val, fields = self._get_fields(param, action_result)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        data = dict()

        if (fields):
            data.update(fields)

        short_desc = param.get(SERVICENOW_JSON_SHORT_DESCRIPTION)

        if ((not fields) and (not short_desc) and (SERVICENOW_JSON_DESCRIPTION not in param)):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_ONE_PARAM_REQ)

        if (short_desc):
            data.update({'short_description': short_desc})

        data.update({'description': '{0}\n\n{1}{2}'.format(self._handle_py_ver_compat_for_input_str(param.get(SERVICENOW_JSON_DESCRIPTION, '')), SERVICENOW_TICKET_FOOTNOTE,
                self.get_container_id())})

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, data=data, auth=auth, headers=headers, method="post")

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            action_result.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        created_ticket_id = response['result']['sys_id']

        action_result.update_summary({SERVICENOW_JSON_NEW_TICKET_ID: created_ticket_id})

        vault_id = param.get(SERVICENOW_JSON_VAULT_ID)

        if (vault_id):
            self.save_progress("Attaching file to the ticket")

            try:
                vault_process, response = self._add_attachment(action_result, table, created_ticket_id, vault_id)
            except Exception as e:
                return action_result.set_status(phantom.APP_ERROR, "Invalid Vault ID, please enter valid Vault ID", e)
            if (phantom.is_success(vault_process)):
                action_result.update_summary({'attachment_added': True, 'attachment_id': response['result']['sys_id']})
            else:
                action_result.update_summary({'attachment_added': False, 'attachment_error': action_result.get_message()})
                self.debug_print(action_result.get_message())

        ret_val = self._get_ticket_details(action_result, param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE), created_ticket_id)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _add_attachment(self, action_result, table, ticket_id, vault_id):

        if (not vault_id):
            return (phantom.APP_SUCCESS, None)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        # Check for file in vault
        meta = Vault.get_file_info(vault_id)  # Vault IDs are unique
        if (not meta):
            self.debug_print("error while attaching")
            return (action_result.set_status(phantom.APP_ERROR, "File not found in Vault"), None)
        meta = meta[0]

        filename = meta.get('name', vault_id)
        filepath = Vault.get_file_path(vault_id)

        mime = magic.Magic(mime=True)
        magic_str = mime.from_file(filepath)
        headers.update({'Content-Type': magic_str})

        try:
            data = open(filepath, 'rb').read()
        except Exception as e:
            self.debug_print("Error reading the file", e)
            return (action_result.set_status(phantom.APP_ERROR, "Failed to read file from Vault"), None)

        # Was not detonated before
        self.save_progress('Uploading the file')

        params = {
                'table_name': table,
                'table_sys_id': ticket_id,
                'file_name': filename}

        ret_val, response = self._upload_file_helper(action_result, '/attachment/file', headers=headers, params=params, data=data, auth=auth)

        if (phantom.is_fail(ret_val)):
            return (action_result.get_status(), response)

        return (phantom.APP_SUCCESS, response)

    def _update_ticket(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        table = self._handle_py_ver_compat_for_input_str(param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE))
        ticket_id = self._handle_py_ver_compat_for_input_str(param[SERVICENOW_JSON_TICKET_ID])
        is_sys_id = param.get("is_sys_id", False)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        if not is_sys_id:
            params = {'sysparm_query': 'number={0}'.format(ticket_id)}
            endpoint = '/table/{0}'.format(table)
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

            if (phantom.is_fail(ret_val)):
                return action_result.get_status()

            if response.get("result"):
                sys_id = response.get("result")[0].get("sys_id")

                if not sys_id:
                    return action_result.set_status(phantom.APP_ERROR, "Unable to fetch the ticket SYS ID for the provided ticket number: {0}".format(ticket_id))

                ticket_id = sys_id
            else:
                return action_result.set_status(phantom.APP_ERROR,
                            "Please provide a valid Ticket Number in the 'id' parameter or check the 'is_sys_id' parameter and provide a valid 'sys_id' in the 'id' parameter")

        endpoint = '/table/{0}/{1}'.format(table, ticket_id)

        ret_val, fields = self._get_fields(param, action_result)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        vault_id = param.get(SERVICENOW_JSON_VAULT_ID)

        if (not fields and not vault_id):
            return action_result.set_status(phantom.APP_ERROR, "Please specify at-least one of fields or vault_id parameter")

        if (fields):
            self.save_progress("Updating ticket with the provided fields")
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, data=fields, auth=auth, headers=headers, method="put")

            if (phantom.is_fail(ret_val)):
                return action_result.get_status()

            action_result.update_summary({'fields_updated': True})

        if (vault_id):
            self.save_progress("Attaching file to the ticket")

            try:
                ret_val, response = self._add_attachment(action_result, table, ticket_id, vault_id)
                action_result.update_summary({'attachment_added': ret_val})
            except Exception as e:
                return action_result.set_status(phantom.APP_ERROR, "Invalid Vault ID, please enter valid Vault ID", e)

            if (phantom.is_success(ret_val)):
                action_result.update_summary({'attachment_id': response['result']['sys_id']})
            else:
                action_result.update_summary({'vault_failure_reason': action_result.get_message()})

        ret_val = self._get_ticket_details(action_result, table, ticket_id)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_ticket_details(self, action_result, table, sys_id, is_sys_id=True):

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        if not is_sys_id:
            params = {'sysparm_query': 'number={0}'.format(sys_id)}
            endpoint = '/table/{0}'.format(table)
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

            if (phantom.is_fail(ret_val)):
                return action_result.get_status()

            if response.get("result"):
                sys_id = response.get("result")[0].get("sys_id")

                if not sys_id:
                    return action_result.set_status(phantom.APP_ERROR, "Unable to fetch the ticket SYS ID for the provided ticket number: {0}".format(sys_id))

            else:
                return action_result.set_status(phantom.APP_ERROR,
                            "Please provide a valid Ticket Number in the 'id' parameter or check the 'is_sys_id' parameter and provide a valid 'sys_id' in the 'id' parameter")

        endpoint = '/table/{0}/{1}'.format(table, sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            action_result.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        ticket = response['result']

        ticket_sys_id = ticket['sys_id']

        params = {'sysparm_query': 'table_sys_id={0}'.format(ticket_sys_id)}

        # get the attachment details
        ret_val, attach_resp = self._make_rest_call_helper(action_result, '/attachment', auth=auth, headers=headers, params=params)

        # is some versions of servicenow fail the attachment query if not present
        # some pass it with no data if not present, so only add data if present and valid
        if (phantom.is_success(ret_val)):
            try:
                attach_details = attach_resp['result']
                ticket['attachment_details'] = attach_details
            except:
                pass

        action_result.add_data(ticket)

        return phantom.APP_SUCCESS

    def _get_ticket(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        table_name = self._handle_py_ver_compat_for_input_str(param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE))
        ticket_id = self._handle_py_ver_compat_for_input_str(param[SERVICENOW_JSON_TICKET_ID])
        is_sys_id = param.get("is_sys_id", False)

        ret_val = self._get_ticket_details(action_result, table_name, ticket_id, is_sys_id=is_sys_id)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        try:
            action_result.update_summary({SERVICENOW_JSON_GOT_TICKET_ID: action_result.get_data()[0]['sys_id']})
        except:
            pass

        return action_result.set_status(phantom.APP_SUCCESS)

    def _paginator(self, endpoint, action_result, payload=None, limit=None):

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            action_result.set_status("Unable to get authorization credentials")
            return None

        items_list = list()
        if not payload:
            payload = dict()

        payload['sysparm_offset'] = SERVICENOW_DEFAULT_OFFSET
        payload['sysparm_limit'] = SERVICENOW_DEFAULT_LIMIT

        while True:
            ret_val, items = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=payload)

            if phantom.is_fail(ret_val):
                return None

            items_list.extend(items.get("result"))

            if limit and len(items_list) >= limit:
                return items_list[:limit]

            if len(items.get("result")) < SERVICENOW_DEFAULT_LIMIT:
                break

            payload['sysparm_offset'] = payload['sysparm_offset'] + SERVICENOW_DEFAULT_LIMIT

        return items_list

    def _describe_service_catalog(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        catalog_sys_id = self._handle_py_ver_compat_for_input_str(param["sys_id"])

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        endpoint = '/table/sc_catalog'

        request_params = dict()
        request_params["sysparm_query"] = "sys_id={}".format(catalog_sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=request_params)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        if not response.get("result"):
            return action_result.set_status(phantom.APP_ERROR, "Please enter a valid value for 'catalog_sys_id' parameter")

        final_data = dict()
        final_data.update(response.get("result")[0])

        endpoint = '/table/sc_category'

        request_params = dict()
        request_params["sysparm_query"] = "sc_catalog={}".format(catalog_sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=request_params)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        final_data["categories"] = response.get("result")

        ret_val, processed_services = self._list_services_helper(param, action_result)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        final_data["items"] = processed_services

        action_result.add_data(final_data)

        return action_result.set_status(phantom.APP_SUCCESS, "Details fetched successfully")

    def _describe_catalog_item(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        try:
            sys_id = self._handle_py_ver_compat_for_input_str(param["sys_id"])
        except:
            return action_result.set_status(phantom.APP_ERROR, "Please provide valid input parameters")

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        endpoint = '/servicecatalog/items/{}'.format(sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        action_result.add_data(response.get("result", {}))

        return action_result.set_status(phantom.APP_SUCCESS, "Details fetched successfully")

    def _list_services_helper(self, param, action_result):

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        limit = param.get("max_results")

        if (limit is not None):
            try:
                limit = int(limit)

                if (limit <= 0):
                    return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results")), None
            except:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results")), None

        payload = dict()
        query = list()
        catalog_sys_id = param.get("catalog_sys_id")
        sys_id = param.get("sys_id")
        category_sys_id = param.get("category_sys_id")
        search_text = param.get("search_text")

        if catalog_sys_id:
            query.append("sc_catalogsLIKE{}".format(self._handle_py_ver_compat_for_input_str(catalog_sys_id)))

        if sys_id:
            query.append("sc_catalogsLIKE{}".format(self._handle_py_ver_compat_for_input_str(sys_id)))

        if category_sys_id:
            query.append("category={}".format(self._handle_py_ver_compat_for_input_str(category_sys_id)))

        if search_text:
            query.append("nameLIKE{search_text}^ORdescriptionLIKE{search_text}^ORsys_nameLIKE{search_text}^ORshort_descriptionLIKE{search_text}".format(
                            search_text=self._handle_py_ver_compat_for_input_str(search_text)))

        endpoint = '/table/sc_cat_item'

        if query:
            search_query = '^'.join(query)
            payload["sysparm_query"] = search_query

        services = self._paginator(endpoint, action_result, payload=payload, limit=limit)

        if services is None:
            return action_result.get_status(), None

        return phantom.APP_SUCCESS, services

    def _list_services(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, processed_services = self._list_services_helper(param, action_result)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        if not processed_services:
            if param.get("catalog_sys_id") or param.get("category_sys_id") or param.get("search_text"):
                return action_result.set_status(phantom.APP_ERROR, 'No data found for the given input parameters')

            return action_result.set_status(phantom.APP_ERROR, 'No data found')

        for service in processed_services:
            catalogs = service.get("sc_catalogs").split(',')
            service["catalogs"] = catalogs
            action_result.add_data(service)

        summary = action_result.update_summary({})
        summary['services_returned'] = action_result.get_data_size()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _list_categories(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        limit = param.get("max_results")

        if (limit is not None):
            try:
                limit = int(limit)

                if (limit <= 0):
                    return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results"))
            except:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results"))

        endpoint = '/table/sc_category'

        service_categories = self._paginator(endpoint, action_result, limit=limit)

        if service_categories is None:
            return action_result.get_status()

        for category in service_categories:
            action_result.add_data(category)

        summary = action_result.update_summary({})
        summary['categories_returned'] = action_result.get_data_size()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _list_service_catalogs(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        limit = param.get("max_results")

        if (limit is not None):
            try:
                limit = int(limit)

                if (limit <= 0):
                    return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results"))
            except:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results"))

        endpoint = '/table/sc_catalog'

        service_catalogs = self._paginator(endpoint, action_result, limit=limit)

        if service_catalogs is None:
            return action_result.get_status()

        for sc in service_catalogs:
            action_result.add_data(sc)

        summary = action_result.update_summary({})
        summary['service_catalogs_returned'] = action_result.get_data_size()

        return action_result.set_status(phantom.APP_SUCCESS)

    def _add_work_note(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        try:
            sys_id = self._handle_py_ver_compat_for_input_str(param.get("id"))
            table_name = self._handle_py_ver_compat_for_input_str(param.get("table_name", "incident"))
            is_sys_id = param.get("is_sys_id", False)
        except:
            return action_result.set_status(phantom.APP_ERROR, "Please provide valid input parameters")

        if not is_sys_id:
            params = {'sysparm_query': 'number={0}'.format(sys_id)}
            endpoint = '/table/{0}'.format(table_name)
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

            if (phantom.is_fail(ret_val)):
                return action_result.get_status()

            if response.get("result"):
                new_sys_id = response.get("result")[0].get("sys_id")

                if not new_sys_id:
                    return action_result.set_status(phantom.APP_ERROR, "Unable to fetch the ticket SYS ID for the provided ticket number: {0}".format(sys_id))

                sys_id = new_sys_id
            else:
                return action_result.set_status(phantom.APP_ERROR,
                            "Please provide a valid Ticket Number in the 'id' parameter or check the 'is_sys_id' parameter and provide a valid 'sys_id' in the 'id' parameter")

        work_note = param.get("work_note")

        endpoint = "/table/{}/{}".format(table_name, sys_id)
        data = {"work_notes": work_note}

        request_params = {}
        request_params["sysparm_display_value"] = True

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, data=data, headers=headers, params=request_params, method="put")

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        if response.get("result", {}).get("work_notes"):
            response["result"]["work_notes"] = response["result"]["work_notes"].replace("\n\n", "\n, ").strip(", ")

        action_result.add_data(response.get("result", {}))

        return action_result.set_status(phantom.APP_SUCCESS, "Added the work note successfully")

    def _request_catalog_item(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        quantity = param["quantity"]
        variables_param = param.get("variables")

        try:
            quantity = int(quantity)

            if (quantity <= 0):
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="quantity"))
        except:
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="quantity"))

        try:
            sys_id = self._handle_py_ver_compat_for_input_str(param["sys_id"])
        except:
            return action_result.set_status(phantom.APP_ERROR, "Please provide valid input parameters")

        if variables_param:
            try:
                variables_param = json.loads(self._handle_py_ver_compat_for_input_str(variables_param))
            except Exception as e:
                return action_result.set_status(phantom.APP_ERROR, "Error while parsing the JSON input", e)

        endpoint = '/servicecatalog/items/{}'.format(sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if (phantom.is_fail(ret_val)):
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
            return action_result.set_status(phantom.APP_ERROR, "Please provide the mandatory variables to order this item.\
                Mandatory variables: {}".format(', '.join(invalid_variables)))

        endpoint = '/servicecatalog/items/{}/order_now'.format(sys_id)

        data = dict()
        data["sysparm_quantity"] = quantity
        if variables_param:
            data["variables"] = variables_param

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, data=data, headers=headers, method="post")

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        request_sys_id = response.get("result", {}).get("sys_id")
        table = response.get("result", {}).get("table")

        self._api_uri = "/api/now"
        endpoint = '/table/{}/{}'.format(table, request_sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        action_result.add_data(response.get("result"))

        return action_result.set_status(phantom.APP_SUCCESS, "The item has been requested")

    def _add_comment(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        try:
            sys_id = self._handle_py_ver_compat_for_input_str(param.get("id"))
            table_name = self._handle_py_ver_compat_for_input_str(param.get("table_name", "incident"))
            is_sys_id = param.get("is_sys_id", False)
        except:
            return action_result.set_status(phantom.APP_ERROR, "Please provide valid input parameters")

        if not is_sys_id:
            params = {'sysparm_query': 'number={0}'.format(sys_id)}
            endpoint = '/table/{0}'.format(table_name)
            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

            if (phantom.is_fail(ret_val)):
                return action_result.get_status()

            if response.get("result"):
                new_sys_id = response.get("result")[0].get("sys_id")

                if not new_sys_id:
                    return action_result.set_status(phantom.APP_ERROR, "Unable to fetch the ticket SYS ID for the provided ticket number: {0}".format(sys_id))

                sys_id = new_sys_id
            else:
                return action_result.set_status(phantom.APP_ERROR,
                            "Please provide a valid Ticket Number in the 'id' parameter or check the 'is_sys_id' parameter and provide a valid 'sys_id' in the 'id' parameter")

        comment = param.get("comment")
        endpoint = "/table/{}/{}".format(table_name, sys_id)
        data = {"comments": comment}

        request_params = {}
        request_params["sysparm_display_value"] = True

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, data=data, headers=headers, params=request_params, method="put")

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        if response.get("result", {}).get("comments"):
            response["result"]["comments"] = response["result"]["comments"].replace("\n\n", "\n, ").strip(", ")

        action_result.add_data(response.get("result", {}))

        return action_result.set_status(phantom.APP_SUCCESS, "Added the comment successfully")

    def _list_tickets(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        endpoint = '/table/{0}'.format(self._handle_py_ver_compat_for_input_str(param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE)))
        request_params = {
            'sysparm_query': param.get(SERVICENOW_JSON_FILTER, "")
        }

        limit = param.get(SERVICENOW_JSON_MAX_RESULTS)

        if (limit is not None):
            try:
                limit = int(limit)

                if (limit <= 0):
                    return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results"))
            except:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results"))

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        tickets = self._paginator(endpoint, action_result, payload=request_params, limit=limit)

        if tickets is None:
            return action_result.get_status()

        for ticket in tickets:
            action_result.add_data(ticket)

        action_result.update_summary({SERVICENOW_JSON_TOTAL_TICKETS: action_result.get_data_size()})

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_variables(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))
        sys_id = self._handle_py_ver_compat_for_input_str(param[SERVICENOW_JSON_SYS_ID])

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        endpoint = '/table/{0}'.format(SERVICENOW_ITEM_OPT_MTOM_TABLE)
        request_params = {'request_item': sys_id}

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=request_params)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        if not response.get('result'):
            return action_result.set_status(phantom.APP_ERROR, 'No data found for the requested item having System ID: {0}'.format(sys_id))

        variables = dict()
        for item in response['result']:
            sc_item_option = item.get('sc_item_option')
            if not sc_item_option or not item['sc_item_option'].get('value'):
                return action_result.set_status(phantom.APP_ERROR, 'Error occurred while fetching variable info for the System ID: {0}'.format(sys_id))

            item_option_value = item['sc_item_option']['value']

            try:
                item_option_value = self._handle_py_ver_compat_for_input_str(item_option_value)
            except:
                self.debug_print("Error while handling Unicode characters (if any or if applicable) in the 'sc_item_option' value")
                item_option_value = item['sc_item_option']['value']

            endpoint = '/table/{0}/{1}'.format(SERVICENOW_ITEM_OPT_TABLE, item_option_value)
            ret_val, auth, headers = self._get_authorization_credentials(action_result)
            if (phantom.is_fail(ret_val)):
                return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

            if (phantom.is_fail(ret_val)):
                return action_result.get_status()

            # If no result found or no key for value found, throw error
            if not response.get('result') or response['result'].get('value') is None:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FETCH_VALUE.format(item_opt_value=item_option_value, sys_id=sys_id))

            response_value = response['result']['value']

            # If no result found or no key for item_option_new found or no key found for value inside item_option_new dictionary, throw error
            if not response.get('result') or response['result'].get('item_option_new') is None or \
                    (isinstance(response['result']['item_option_new'], dict) and not response['result']['item_option_new'].get('value')):
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FETCH_QUESTION_ID.format(item_opt_value=item_option_value, sys_id=sys_id))

            # The dictionary for item_option_new can be empty if no question is available for a given variable which is a valid scenario
            if not response['result']['item_option_new']:
                response_question = ""
                variables[response_question] = response_value
                continue
            question_id = response['result']['item_option_new']['value']

            try:
                question_id = self._handle_py_ver_compat_for_input_str(question_id)
            except:
                self.debug_print("Error while handling Unicode characters (if any or if applicable) in the 'question_id' value")
                question_id = response['result']['item_option_new']['value']

            endpoint = '/table/{0}/{1}'.format(SERVICENOW_ITEM_OPT_NEW_TABLE, question_id)
            ret_val, auth, headers = self._get_authorization_credentials(action_result)
            if (phantom.is_fail(ret_val)):
                return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

            if (phantom.is_fail(ret_val)):
                return action_result.get_status()

            # If no result found or no key for question_text found, throw error
            if not response.get('result') or response['result'].get('question_text') is None:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FETCH_QUESTION.format(question_id=question_id, item_opt_value=item_option_value, sys_id=sys_id))

            response_question = response['result']['question_text']

            variables[response_question] = response_value

        summary = action_result.update_summary({})
        summary['num_variables'] = len(variables)

        action_result.add_data(variables)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _run_query(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_BASE_QUERY_URI, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        self.save_progress("In action handler for: {0}".format(self.get_action_identifier()))

        lookup_table = param[SERVICENOW_JSON_QUERY_TABLE]
        query = param[SERVICENOW_JSON_QUERY]
        endpoint = SERVICENOW_BASE_QUERY_URI + lookup_table + "?" + query
        limit = param.get("max_results")

        if (limit is not None):
            try:
                limit = int(limit)

                if (limit <= 0):
                    return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results"))
            except:
                return action_result.set_status(phantom.APP_ERROR, SERVICENOW_LIMIT_VALIDATION_MSG.format(parameter="max_results"))

        ret_val, auth, headers = self._get_authorization_credentials(action_result)

        if (phantom.is_fail(ret_val)):
            return action_result.set_status(phantom.APP_ERROR, "Unable to get authorization credentials")

        tickets = self._paginator(endpoint, action_result, limit=limit)

        if tickets is None:
            return action_result.get_status()

        for ticket in tickets:
            action_result.add_data(ticket)

        action_result.update_summary({SERVICENOW_JSON_TOTAL_TICKETS: action_result.get_data_size()})

        return action_result.set_status(phantom.APP_SUCCESS)

    def _on_poll(self, param):

        URI_REGEX = '[Hh][Tt][Tt][Pp][Ss]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        HASH_REGEX = '\\b[0-9a-fA-F]{32}\\b|\\b[0-9a-fA-F]{40}\\b|\\b[0-9a-fA-F]{64}\\b'
        IP_REGEX = '\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}'
        IPV6_REGEX = '\\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|'
        IPV6_REGEX += '(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3})|:))'
        IPV6_REGEX += '|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3})|:))|'
        IPV6_REGEX += '(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.' \
            '(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|'
        IPV6_REGEX += '(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.' \
    '(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|'
        IPV6_REGEX += '(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.' \
    '(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|'
        IPV6_REGEX += '(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.' \
    '(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|'
        IPV6_REGEX += '(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:)))(%.+)?\\s*'
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
        last_time = self._state.get('last_time')

        if last_time and isinstance(last_time, float):
            last_time = datetime.strftime(datetime.fromtimestamp(last_time), '%Y-%m-%d %H:%M:%S')

        # Build the query for the issue search (sysparm_query)
        query = "ORDERBYsys_updated_on"

        action_query = config.get(SERVICENOW_JSON_ON_POLL_FILTER, "")

        if (len(action_query) > 0):
            query += '^' + action_query

        # If it's a poll now don't filter based on update time
        if self.is_poll_now():
            max_tickets = param.get(phantom.APP_JSON_CONTAINER_COUNT)
        # If it's the first poll, don't filter based on update time
        elif (self._state.get('first_run', True)):
            self._state['first_run'] = False
            max_tickets = self._first_run_container
        # If it's scheduled polling add a filter for update time being greater than the last poll time
        else:
            # "last_time" should be of the format "%Y-%m-%d %H:%M:%S"
            if last_time and len(last_time.split(" ")) == 2:
                query += "^sys_updated_on>=javascript:gs.dateGenerate('{}','{}')".format(last_time.split(" ")[0], last_time.split(" ")[1])
                max_tickets = self._max_container
            else:
                self.debug_print("Either 'last_time' is None or empty or it is not in the expected format of %Y-%m-%d %H:%M:%S. last_time: {}".format(last_time))
                self.debug_print("Considering this as the first scheduled|interval polling run; skipping time-based query filtering; processing the on_poll workflow accordingly")

                max_tickets = self._first_run_container

                self.debug_print("Setting the 'max_tickets' to the value of 'first_run_container'. max_tickets: {}".format(max_tickets))

        endpoint = '/table/' + config.get(SERVICENOW_JSON_ON_POLL_TABLE, SERVICENOW_DEFAULT_TABLE)
        params = {
            'sysparm_query': query,
            'sysparm_display_value': 'true',
            'sysparm_exclude_reference_link': 'true'}

        limit = max_tickets

        issues = self._paginator(endpoint, action_result, payload=params, limit=limit)

        if issues is None:
            self.debug_print(action_result.get_message())
            action_result.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        if not issues:
            return action_result.set_status(phantom.APP_ERROR, 'No issues found')

        # TODO: handle cases where we go over the ingestions limit

        # Ingest the issues
        failed = 0
        label = self.get_config().get('ingest', {}).get('container_label')
        for issue in issues:
            d = issue.get('description', '')
            sd = issue.get('short_description')
            if not sd:
                sd = 'Phantom added container name (short description of the ticke/record found empty)'
            sd = self._handle_py_ver_compat_for_input_str(sd)
            container = dict(
                data=issue,
                description=d,
                label=label,
                name='{}'.format(sd),
                source_data_identifier=issue['sys_id']
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
                label='issue',
                name=issue.get('number', 'Phantom added artifact name (number of the ticke/record found empty)'),
                source_data_identifier=issue['sys_id']
            )
            artifacts.append(artifact_dict)
            extract_ips = config.get(SERVICENOW_JSON_EXTRACT_IPS)
            extract_hashes = config.get(SERVICENOW_JSON_EXTRACT_HASHES)
            extract_url = config.get(SERVICENOW_JSON_EXTRACT_URLS)
            if extract_ips:
                for match in ip_regexc.finditer(str(issue)):
                    cef = {}
                    cef['ip_address'] = match.group()
                    art = {'container_id': container_id,
                       'label': 'IP Address',
                       'cef': cef}
                    artifacts.append(art)

                for match in ipv6_regexc.finditer(str(issue)):
                    cef = {}
                    cef['ipv6_address'] = match.group()
                    art = {'container_id': container_id,
                       'label': 'IPV6 Address',
                       'cef': cef}
                    artifacts.append(art)

            if extract_hashes:
                for match in hash_regexc.finditer(str(issue)):
                    cef = {}
                    cef['hash'] = match.group()
                    art = {'container_id': container_id,
                       'label': 'Hash',
                       'cef': cef}
                    artifacts.append(art)

            if extract_url:
                for match in uri_regexc.finditer(str(issue)):
                    cef = {}
                    cef['URL'] = match.group()
                    art = {'container_id': container_id,
                       'label': 'URL',
                       'cef': cef}
                    artifacts.append(art)
            self.save_artifacts(artifacts)

        action_result.set_status(phantom.APP_SUCCESS, 'Containers created')

        if not self.is_poll_now():
            updated_time = issues[-1]
            self._state['last_time'] = updated_time.get("sys_updated_on")

        if (failed):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FAILURES)

        self.save_state(self._state)

        return action_result.set_status(phantom.APP_SUCCESS)

    def handle_action(self, param):
        """Function that handles all the actions

            Args:

            Return:
                A status code
        """

        # Get the action that we are supposed to carry out, set it in the connection result object
        action = self.get_action_identifier()

        ret_val = phantom.APP_SUCCESS

        if (action == self.ACTION_ID_CREATE_TICKET):
            ret_val = self._create_ticket(param)
        elif (action == self.ACTION_ID_ADD_WORK_NOTE):
            ret_val = self._add_work_note(param)
        elif (action == self.ACTION_ID_ORDER_ITEM):
            ret_val = self._request_catalog_item(param)
        elif (action == self.ACTION_ID_ADD_COMMENT):
            ret_val = self._add_comment(param)
        elif (action == self.ACTION_ID_DESCRIBE_SERVICE_CATALOG):
            ret_val = self._describe_service_catalog(param)
        elif (action == self.ACTION_ID_DESCRIBE_CATALOG_ITEM):
            ret_val = self._describe_catalog_item(param)
        elif (action == self.ACTION_ID_LIST_SERVICES):
            ret_val = self._list_services(param)
        elif (action == self.ACTION_ID_LIST_CATEGORIES):
            ret_val = self._list_categories(param)
        elif (action == self.ACTION_ID_LIST_SERVICE_CATALOGS):
            ret_val = self._list_service_catalogs(param)
        elif (action == self.ACTION_ID_LIST_TICKETS):
            ret_val = self._list_tickets(param)
        elif (action == self.ACTION_ID_GET_TICKET):
            ret_val = self._get_ticket(param)
        elif (action == self.ACTION_ID_UPDATE_TICKET):
            ret_val = self._update_ticket(param)
        elif (action == self.ACTION_ID_GET_VARIABLES):
            ret_val = self._get_variables(param)
        elif (action == self.ACTION_ID_ON_POLL):
            ret_val = self._on_poll(param)
        elif (action == phantom.ACTION_ID_TEST_ASSET_CONNECTIVITY):
            ret_val = self._test_connectivity(param)
        elif (action == self.ACTION_ID_RUN_QUERY):
            ret_val = self._run_query(param)
        return ret_val


if __name__ == '__main__':

    import pudb
    import argparse

    pudb.set_trace()

    argparser = argparse.ArgumentParser()

    argparser.add_argument('input_test_json', help='Input Test JSON file')
    argparser.add_argument('-u', '--username', help='username', required=False)
    argparser.add_argument('-p', '--password', help='password', required=False)

    args = argparser.parse_args()
    session_id = None

    username = args.username
    password = args.password

    if (username is not None and password is None):

        # User specified a username but not a password, so ask
        import getpass
        password = getpass.getpass("Password: ")

    if (username and password):
        try:
            print("Accessing the Login page")
            login_url = BaseConnector._get_phantom_base_url() + "login"
            r = requests.get(login_url, verify=False)
            csrftoken = r.cookies['csrftoken']

            data = dict()
            data['username'] = username
            data['password'] = password
            data['csrfmiddlewaretoken'] = csrftoken

            headers = dict()
            headers['Cookie'] = 'csrftoken=' + csrftoken
            headers['Referer'] = BaseConnector._get_phantom_base_url() + 'login'

            print("Logging into Platform to get the session id")
            r2 = requests.post(login_url, verify=False, data=data, headers=headers)
            session_id = r2.cookies['sessionid']
        except Exception as e:
            print("Unable to get session id from the platfrom. Error: " + str(e))
            exit(1)

    with open(args.input_test_json) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = ServicenowConnector()
        connector.print_progress_message = True

        if (session_id is not None):
            in_json['user_session_token'] = session_id
            connector._set_csrf_info(csrftoken, headers['Referer'])

        ret_val = connector._handle_action(json.dumps(in_json), None)
        print(json.dumps(json.loads(ret_val), indent=4))

    exit(0)
