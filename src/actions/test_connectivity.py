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

"""Test Connectivity Action"""

import soar_sdk
from soar_sdk.abstract import SOARClient
from soar_sdk.logging import getLogger

from ..app import app, Asset
from ..consts import (
    BASIC_AUTH_TYPE,
    TEST_CONNECTIVITY_ENDPOINT,
    TEST_CONNECTIVITY_SUCCESS,
    TEST_CONNECTIVITY_FAIL,
)
from ..servicenow_client import ServiceNowClient

logger = getLogger()


@app.test_connectivity()
def test_connectivity(soar: SOARClient, asset: Asset) -> None:
    """Test ServiceNow connectivity by querying a single incident."""
    logger.info("Testing connectivity to ServiceNow")

    # Log SDK version for troubleshooting
    sdk_version = getattr(soar_sdk, "__version__", "unknown")
    logger.info(f"soar_sdk version: {sdk_version}")

    client = ServiceNowClient(asset)

    # Force a fresh token fetch so we validate credentials are currently valid
    try:
        auth_type = getattr(client.asset, "oauth_grant_type", None)
        if (
            auth_type != BASIC_AUTH_TYPE
            and client.asset.client_id
            and client.asset.client_secret
        ):
            client.force_new_oauth_token()
    except Exception as e:
        error_msg = (
            f"{TEST_CONNECTIVITY_FAIL}: Failed to initialize authentication: {e}"
        )
        soar.set_message(error_msg)
        raise Exception(error_msg) from e

    request_params = {"sysparm_limit": "1"}

    logger.info("Querying a single Incident to check credentials")

    try:
        _response = client.make_rest_call(
            TEST_CONNECTIVITY_ENDPOINT,
            params=request_params,
        )
    except Exception as e:
        error_msg = f"{TEST_CONNECTIVITY_FAIL}: {e}"
        soar.set_message(error_msg)
        raise Exception(error_msg) from e

    logger.info(TEST_CONNECTIVITY_SUCCESS)
    success_msg = f"{TEST_CONNECTIVITY_SUCCESS} (soar_sdk v{sdk_version})"
    soar.set_message(success_msg)
    # Success - no return value needed for test_connectivity
