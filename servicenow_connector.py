# --
# File: servicenow_connector.py
#
# Copyright (c) Phantom Cyber Corporation, 2014-2018
#
# This unpublished material is proprietary to Phantom Cyber.
# All rights reserved. The methods and
# techniques described herein are considered trade secrets
# and/or confidential. Reproduction or distribution, in whole
# or in part, is forbidden except by express written permission
# of Phantom Cyber Corporation.
#
# --

# Phantom imports
import phantom.app as phantom
from phantom.base_connector import BaseConnector
from phantom.action_result import ActionResult
from phantom.vault import Vault

# THIS Connector imports
from servicenow_consts import *

import json
import magic
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime


DT_STR_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


class UnauthorizedOAuthTokenException(Exception):
    pass


class RetVal(tuple):
    def __new__(cls, status, data):
        return tuple.__new__(RetVal, (status, data))


class ServicenowConnector(BaseConnector):

    # actions supported by this script
    ACTION_ID_LIST_TICKETS = "list_tickets"
    ACTION_ID_CREATE_TICKET = "create_ticket"
    ACTION_ID_GET_TICKET = "get_ticket"
    ACTION_ID_UPDATE_TICKET = "update_ticket"
    ACTION_ID_GET_VARIABLES = "get_variables"
    ACTION_ID_ON_POLL = "on_poll"

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

        # Base URL
        self._base_url = config[SERVICENOW_JSON_DEVICE_URL]
        if (self._base_url.endswith('/')):
            self._base_url = self._base_url[:-1]

        self._host = self._base_url[self._base_url.find('//') + 2:]
        self._headers = {'Accept': 'application/json'}
        # self._headers.update({'X-no-response-body': 'true'})
        self._api_uri = '/api/now'
        self._client_id = config.get(SERVICENOW_JSON_CLIENT_ID, None)
        if (self._client_id):
            try:
                self._client_secret = config[SERVICENOW_JSON_CLIENT_SECRET]
                self._use_token = True
            except KeyError:
                self.save_progress("Missing Client Secret")
                return phantom.APP_ERROR

        return phantom.APP_SUCCESS

    def _get_error_details(self, resp_json):

        error_details = {"message": "Not Found", "detail": "Not supplied"}

        if (not resp_json):
            return error_details

        error_info = resp_json.get("error")

        if (not error_info):
            return error_details

        if ('message' in error_info):
            error_details['message'] = error_info['message']

        if ('detail' in error_info):
            error_details['detail'] = error_info['detail']

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
            action_result.add_data(resp_json)
            error_details = self._get_error_details(resp_json)
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FROM_SERVER, status=r.status_code, **error_details), resp_json)

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
                r.status_code, r.text.replace('{', ' ').replace('}', ' '))

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _upload_file(self, action_result, endpoint, headers={}, params=None, data=None, auth=None):

        config = self.get_config()

        # Create the headers
        headers.update(self._headers)

        resp_json = None

        try:
            r = requests.post(self._base_url + self._api_uri + endpoint,
                    auth=auth,
                    data=data,
                    headers=headers,
                    verify=config[phantom.APP_JSON_VERIFY],
                    params=params)
        except Exception as e:
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_SERVER_CONNECTION, e), resp_json)

        return self._process_response(r, action_result)

    def _make_rest_call_oauth(self, action_result, headers={}, data={}):
        """ The API for retrieving the OAuth token is different enough to where its just easier to make a new function
        """
        resp_json = None
        config = self.get_config()

        try:
            r = requests.post(
                    self._base_url + '/oauth_token.do',
                    data=data,  # Mostly this line
                    verify=config[phantom.APP_JSON_VERIFY]
            )
        except Exception as e:
            return (action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_SERVER_CONNECTION, e), resp_json)

        return self._process_response(r, action_result)

    def _make_rest_call(self, action_result, endpoint, headers={}, params=None, data=None, auth=None, method="get"):

        config = self.get_config()

        # Create the headers
        headers.update(self._headers)

        if ('Content-Type' not in headers):
            headers.update({'Content-Type': 'application/json'})

        resp_json = None

        request_func = getattr(requests, method)

        if (not request_func):
            action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_API_UNSUPPORTED_METHOD, method=method)

        try:
            r = request_func(self._base_url + self._api_uri + endpoint,
                    auth=auth,
                    json=data,
                    headers=headers,
                    verify=config[phantom.APP_JSON_VERIFY],
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
            params['username'] = config[SERVICENOW_JSON_USERNAME]
            params['password'] = config[SERVICENOW_JSON_PASSWORD]
            params['grant_type'] = "password"

        ret_val, response_json = self._make_rest_call_oauth(action_result, data=params)

        if (phantom.is_fail(ret_val) and params['grant_type'] == 'refresh_token'):
            self.debug_print("Unable to generate new key with refresh token")
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
                pass

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
            auth = requests.auth.HTTPBasicAuth(config[SERVICENOW_JSON_USERNAME], config[SERVICENOW_JSON_PASSWORD])
            headers = {}

        return ret_val, auth, headers

    def _test_connectivity(self, param):

        action_result = ActionResult()

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

        endpoint = '/table/incident'
        request_params = {'sysparm_limit': '1'}

        action_result = self.add_action_result(ActionResult(param))

        self.save_progress(SERVICENOW_MSG_GET_INCIDENT_TEST)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, params=request_params, headers=headers, auth=auth)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            message = action_result.get_message().strip()
            message = message.rstrip('.')
            self.set_status(phantom.APP_ERROR, message)
            self.append_to_message(SERVICENOW_ERR_CONNECTIVITY_TEST)
            return phantom.APP_ERROR

        return self.set_status_save_progress(phantom.APP_SUCCESS, SERVICENOW_SUCC_CONNECTIVITY_TEST)

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

        table = param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE)

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

        data.update({'description': '{0}\n\n{1}{2}'.format(param.get(SERVICENOW_JSON_DESCRIPTION, ''), SERVICENOW_TICKET_FOOTNOTE,
                self.get_container_id())})

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, data=data, auth=auth, headers=headers, method="post")

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            self.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        created_ticket_id = response['result']['sys_id']

        action_result.update_summary({SERVICENOW_JSON_NEW_TICKET_ID: created_ticket_id})

        vault_id = param.get(SERVICENOW_JSON_VAULT_ID)

        if (vault_id):
            self.save_progress("Attaching file to the ticket")

            vault_process, response = self._add_attachment(action_result, table, created_ticket_id, vault_id)
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
            return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

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

        table = param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE)
        ticket_id = param[SERVICENOW_JSON_TICKET_ID]

        endpoint = '/table/{0}/{1}'.format(table, ticket_id)

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

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

        vault_process_success = True
        if (vault_id):
            self.save_progress("Attaching file to the ticket")

            ret_val, response = self._add_attachment(action_result, table, ticket_id, vault_id)
            action_result.update_summary({'attachment_added': ret_val})

            if (phantom.is_success(ret_val)):
                action_result.update_summary({'attachment_id': response['result']['sys_id']})
            else:
                action_result.update_summary({'vault_failure_reason': action_result.get_message()})
                vault_process_success = False

        ret_val = self._get_ticket_details(action_result, table, ticket_id)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        if (not vault_process_success):
            return action_result.set_status(phantom.APP_ERROR)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_ticket_details(self, action_result, table, sys_id):

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

        endpoint = '/table/{0}/{1}'.format(table, sys_id)

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            self.set_status(phantom.APP_ERROR, action_result.get_message())
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

        ret_val = self._get_ticket_details(action_result,
                param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE), param[SERVICENOW_JSON_TICKET_ID])

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        try:
            action_result.update_summary({SERVICENOW_JSON_GOT_TICKET_ID: action_result.get_data()[0]['sys_id']})
        except:
            pass

        return action_result.set_status(phantom.APP_SUCCESS)

    def _list_tickets(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        endpoint = '/table/{0}'.format(param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE))
        request_params = {
            'sysparm_query': param.get(SERVICENOW_JSON_FILTER, ""),
            'sysparm_limit': param.get(SERVICENOW_JSON_MAX_RESULTS, DEFAULT_MAX_RESULTS)
        }

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=request_params)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            self.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        tickets = response['result']

        action_result.update_summary({SERVICENOW_JSON_TOTAL_TICKETS: len(tickets)})

        for ticket in tickets:
            action_result.add_data(ticket)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_variables(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        endpoint = '/table/{0}'.format(SERVICENOW_ITEM_OPT_MTOM_TABLE)
        request_params = {'request_item': param[SERVICENOW_JSON_TICKET_ID]}

        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=request_params)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            self.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        variables = {}

        for item in response['result']:
            item_option_id = item['sc_item_option']['value']

            endpoint = '/table/{0}/{1}'.format(SERVICENOW_ITEM_OPT_TABLE, item_option_id)

            ret_val, auth, headers = self._get_authorization_credentials(action_result)
            if (phantom.is_fail(ret_val)):
                return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers,)

            if (phantom.is_fail(ret_val)):
                self.debug_print(action_result.get_message())
                self.set_status(phantom.APP_ERROR, action_result.get_message())
                return phantom.APP_ERROR

            response_value = response['result']['value']
            question_id = response['result']['item_option_new']['value']

            endpoint = '/table/{0}/{1}'.format(SERVICENOW_ITEM_OPT_NEW_TABLE, question_id)

            ret_val, auth, headers = self._get_authorization_credentials(action_result)
            if (phantom.is_fail(ret_val)):
                return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

            ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers)

            if (phantom.is_fail(ret_val)):
                self.debug_print(action_result.get_message())
                self.set_status(phantom.APP_ERROR, action_result.get_message())
                return phantom.APP_ERROR

            response_question = response['result']['question_text']

            variables[response_question] = response_value

        action_result.add_data(variables)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _on_poll(self, param):

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        state = self.load_state()

        # Get config
        config = self.get_config()

        # Add action result
        action_result = self.add_action_result(phantom.ActionResult(param))

        # Get time from last poll, save now as time for this poll
        last_time = state.get('last_time', 0)
        state['last_time'] = time.time()

        # Build the query for the issue search (sysparm_query)
        query = "ORDERBYsys_created_on"

        action_query = config.get(SERVICENOW_JSON_ON_POLL_FILTER, "")

        if (len(action_query) > 0):
            query += '^' + action_query

        # If it's a poll now don't filter based on update time
        if self.is_poll_now():
            max_tickets = param.get(phantom.APP_JSON_CONTAINER_COUNT)
        # If it's the first poll, don't filter based on update time
        elif (state.get('first_run', True)):
            state['first_run'] = False
            max_tickets = ON_POLL_MAX_RESULTS
        # If it's scheduled polling add a filter for update time being greater than the last poll time
        else:
            last_time_dt = datetime.fromtimestamp(last_time)
            d = last_time_dt.strftime("%Y-%m-%d")
            t = last_time_dt.strftime("%H:%M:%S")
            query += "^sys_created_on>javascript:gs.dateGenerate('{}','{}}')".format(d, t)
            max_tickets = DEFAULT_MAX_RESULTS

        # Query for issues
        ret_val, auth, headers = self._get_authorization_credentials(action_result)
        if (phantom.is_fail(ret_val)):
            return self.set_status_save_progress(phantom.APP_ERROR, "Unable to get authorization credentials")

        endpoint = '/table/' + config.get(SERVICENOW_JSON_ON_POLL_TABLE, SERVICENOW_DEFAULT_TABLE)
        params = {
            'sysparm_query': query,
            'sysparm_limit': max_tickets}

        ret_val, response = self._make_rest_call_helper(action_result, endpoint, auth=auth, headers=headers, params=params)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            self.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        issues = response['result']

        # TODO: handle cases where we go over the ingestions limit

        # Ingest the issues
        failed = 0
        label = self.get_config().get('ingest', {}).get('container_label')
        for issue in issues:
            container = dict(
                data=issue,
                description=issue['description'],
                label=label,
                name='{}'.format(issue['short_description']),
                source_data_identifier=issue['sys_id']
            )

            ret_val, _, container_id = self.save_container(container)

            if phantom.is_fail(ret_val):
                failed += 1
                continue

            artifact = dict(
                container_id=container_id,
                data=issue,
                description=issue['short_description'],
                label='issue',
                name=issue['number'],
                source_data_identifier=issue['sys_id']
            )
            self.save_artifact(artifact)

        action_result.set_status(phantom.APP_SUCCESS, 'Containers created')

        self.save_state(state)

        if (failed):
            return action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FAILURES)

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
        return ret_val


if __name__ == '__main__':

    import sys
    # import simplejson as json
    import pudb

    pudb.set_trace()

    with open(sys.argv[1]) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = ServicenowConnector()
        connector.print_progress_message = True
        ret_val = connector._handle_action(json.dumps(in_json), None)
        print ret_val

    exit(0)
