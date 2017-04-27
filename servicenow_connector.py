# --
# File: servicenow_connector.py
#
# Copyright (c) Phantom Cyber Corporation, 2014-2017
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

import requests
import os
import json
import inspect
from bs4 import BeautifulSoup
import magic

requests.packages.urllib3.disable_warnings()


class RetVal(tuple):
    def __new__(cls, status, data):
        return tuple.__new__(RetVal, (status, data))


class ServicenowConnector(BaseConnector):

    # actions supported by this script
    ACTION_ID_LIST_TICKETS = "list_tickets"
    ACTION_ID_CREATE_TICKET = "create_ticket"
    ACTION_ID_GET_TICKET = "get_ticket"
    ACTION_ID_UPDATE_TICKET = "update_ticket"

    def __init__(self):

        # Call the BaseConnectors init first
        super(ServicenowConnector, self).__init__()

        self._state_file_path = None
        self._state = {}

    def _load_state(self):

        # get the directory of the class
        dirpath = os.path.dirname(inspect.getfile(self.__class__))
        asset_id = self.get_asset_id()
        self._state_file_path = "{0}/{1}_serialized_data.json".format(dirpath, asset_id)

        self._state = {}

        try:
            with open(self._state_file_path, 'r') as f:
                in_json = f.read()
                self._state = json.loads(in_json)
        except Exception as e:
            self.debug_print("In _load_state: Exception: {0}".format(str(e)))
            pass

        self.debug_print("Loaded state: ", self._state)

        return phantom.APP_SUCCESS

    def _save_state(self):

        self.debug_print("Saving state: ", self._state)

        if (not self._state_file_path):
            self.debug_print("_state_file_path is None in _save_state")
            return phantom.APP_SUCCESS

        try:
            with open(self._state_file_path, 'w+') as f:
                f.write(json.dumps(self._state))
        except:
            pass

        return phantom.APP_SUCCESS

    def finalize(self):
        self._save_state()
        return phantom.APP_SUCCESS

    def initialize(self):

        self._load_state()

        config = self.get_config()

        # Base URL
        self._base_url = config[SERVICENOW_JSON_DEVICE_URL]
        if (self._base_url.endswith('/')):
            self._base_url = self._base_url[:-1]

        self._host = self._base_url[self._base_url.find('//') + 2:]
        self._headers = {'Accept': 'application/json'}
        # self._headers.update({'X-no-response-body': 'true'})
        self._api_uri = '/api/now'

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

    def _upload_file(self, endpoint, action_result, headers={}, params=None, data=None):

        config = self.get_config()

        username = config[SERVICENOW_JSON_USERNAME]
        password = config[SERVICENOW_JSON_PASSSWORD]

        # Create the headers
        headers.update(self._headers)

        resp_json = None

        try:
            r = requests.post(self._base_url + self._api_uri + endpoint,
                    auth=(username, password),
                    data=data,
                    headers=headers,
                    verify=config[phantom.APP_JSON_VERIFY],
                    params=params)
        except Exception as e:
            return RetVal(action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_SERVER_CONNECTION, e), resp_json)

        return self._process_response(r, action_result)

    def _make_rest_call(self, endpoint, action_result, headers={}, params=None, data=None, method="get"):

        config = self.get_config()

        username = config[SERVICENOW_JSON_USERNAME]
        password = config[SERVICENOW_JSON_PASSSWORD]

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
                    auth=(username, password),
                    json=data,
                    headers=headers,
                    verify=config[phantom.APP_JSON_VERIFY],
                    params=params)
        except Exception as e:
            return (action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_SERVER_CONNECTION, e), resp_json)

        return self._process_response(r, action_result)

    def _test_connectivity(self, param):

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        endpoint = '/table/incident'
        request_params = {'sysparm_limit': '1'}

        action_result = self.add_action_result(ActionResult(param))

        self.save_progress(SERVICENOW_MSG_GET_INCIDENT_TEST)

        ret_val, response = self._make_rest_call(endpoint, action_result, params=request_params)

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
            return (phantom.APP_SUCCESS, None)

        # we take in as a dictionary string, first try to load it as is
        try:
            fields = json.loads(fields)
        except Exception as e:
            return (action_result.set_status(phantom.APP_ERROR, SERVICENOW_ERR_FIELDS_JSON_PARSE, e), None)

        return (phantom.APP_SUCCESS, fields)

    def _create_ticket(self, param):

        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress
        self.save_progress(SERVICENOW_USING_BASE_URL, base_url=self._base_url)

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        table = param.get(SERVICENOW_JSON_TABLE, SERVICENOW_DEFAULT_TABLE)

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

        ret_val, response = self._make_rest_call(endpoint, action_result, data=data, method="post")

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
        headers = {'Content-Type': magic_str}

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

        ret_val, response = self._upload_file('/attachment/file', action_result, headers=headers, params=params, data=data)

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

        ret_val, fields = self._get_fields(param, action_result)

        if (phantom.is_fail(ret_val)):
            return action_result.get_status()

        vault_id = param.get(SERVICENOW_JSON_VAULT_ID)

        if (not fields and not vault_id):
            return action_result.set_status(phantom.APP_ERROR, "Please specify at-least one of fields or vault_id parameter")

        if (fields):
            self.save_progress("Updating ticket with the provided fields")
            ret_val, response = self._make_rest_call(endpoint, action_result, data=fields, method="put")

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

        endpoint = '/table/{0}/{1}'.format(table, sys_id)

        ret_val, response = self._make_rest_call(endpoint, action_result)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            self.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        ticket = response['result']

        ticket_sys_id = ticket['sys_id']

        params = {'sysparm_query': 'table_sys_id={0}'.format(ticket_sys_id)}

        # get the attachment details
        ret_val, attach_resp = self._make_rest_call('/attachment', action_result, params=params)

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
        request_params = {'sysparm_limit': param.get(SERVICENOW_JSON_MAX_RESULTS, DEFAULT_MAX_RESULTS)}

        ret_val, response = self._make_rest_call(endpoint, action_result, params=request_params)

        if (phantom.is_fail(ret_val)):
            self.debug_print(action_result.get_message())
            self.set_status(phantom.APP_ERROR, action_result.get_message())
            return phantom.APP_ERROR

        tickets = response['result']

        action_result.update_summary({SERVICENOW_JSON_TOTAL_TICKETS: len(tickets)})

        for ticket in tickets:
            action_result.add_data(ticket)

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
