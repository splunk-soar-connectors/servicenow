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

"""Make Request Action - Generic HTTP request to any ServiceNow API endpoint"""

import json

import httpx
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.params import MakeRequestParams, Param

from ..app import Asset, app
from ..helpers import ServiceNowClient

logger = getLogger()


class ServiceNowMakeRequestParams(MakeRequestParams):
    """Custom MakeRequestParams with ServiceNow-specific endpoint description."""

    http_method: str = Param(
        description="The HTTP method to use for the request.",
        required=False,
        default="GET",
        value_list=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    )
    endpoint: str = Param(
        description=(
            "ServiceNow API endpoint path appended to the base URL. "
            "Do not include the base URL itself. "
            "Examples: '/api/now/table/incident'"
        ),
    )
    verify_ssl: bool = Param(
        description="Whether to verify the SSL certificate.",
        required=False,
        default=True,
    )
    body: str = Param(
        description=(
            "The request body to send. When Content-Type contains 'json', this must "
            "be a JSON object. For other content types, the body is sent as raw text."
        ),
        required=False,
    )


class ServiceNowMakeRequestOutput(ActionOutput):
    """Make request output with raw response metadata."""

    status_code: int = OutputField(example_values=[200, 404, 500])
    response_body: str = OutputField(example_values=['{"key": "value"}'])

    @classmethod
    def from_response(cls, response: httpx.Response) -> "ServiceNowMakeRequestOutput":
        return cls(status_code=response.status_code, response_body=response.text)


@app.make_request()
def make_request(
    params: ServiceNowMakeRequestParams, asset: Asset
) -> ServiceNowMakeRequestOutput:
    """
    Execute an arbitrary HTTP request against the ServiceNow instance.
    """
    logger.info(f"make_request: {params.http_method} {params.endpoint}")

    endpoint = params.endpoint
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        raise ActionFailure(
            f"Invalid endpoint: {endpoint}. "
            "Do not include the full URL, only the path after the base URL is needed "
            f"(e.g. '/api/now/table/incident'). The base URL ({asset.url}) is already configured in the asset."
        )

    # Ensure leading slash
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"

    # resolve authentication
    verify = params.verify_ssl if params.verify_ssl is not None else True
    client = ServiceNowClient(asset, verify_ssl=verify)

    # build the full URL
    base_url = client._normalize_base_url()
    url = f"{base_url}{endpoint}"

    try:
        auth = client.get_auth()
    except ActionFailure:
        raise
    except Exception as e:
        raise ActionFailure(f"Authentication configuration error: {e}") from e

    merged_headers: dict[str, str] = {"Content-Type": "application/json"}

    query_params: dict | None = None
    if params.query_parameters:
        try:
            parsed_query_params = json.loads(params.query_parameters)
            if not isinstance(parsed_query_params, dict):
                raise ActionFailure("query_parameters JSON must be an object")
            query_params = parsed_query_params
        except (json.JSONDecodeError, TypeError):
            # Treat as raw query string.
            query_string = params.query_parameters.removeprefix("?")
            separator = "&" if "?" in url else "?"
            url += f"{separator}{query_string}"

    if params.headers:
        try:
            parsed_headers = json.loads(params.headers)
        except (json.JSONDecodeError, TypeError) as e:
            raise ActionFailure(f"Invalid JSON headers: {params.headers}") from e
        if not isinstance(parsed_headers, dict):
            raise ActionFailure("Invalid JSON headers: expected a JSON object")
        merged_headers.update(parsed_headers)

    json_body: dict | None = None
    raw_body: str | None = None
    if params.body:
        content_type = merged_headers.get("Content-Type", "").lower()
        if "json" in content_type:
            try:
                json_body = json.loads(params.body)
            except (json.JSONDecodeError, TypeError) as e:
                raise ActionFailure(f"Invalid JSON body: {params.body}") from e
        else:
            raw_body = params.body

    # build and send the request
    timeout = params.timeout if params.timeout else 30
    try:
        with httpx.Client(timeout=timeout, verify=verify) as client:
            response = client.request(
                method=params.http_method,
                url=url,
                auth=auth,
                headers=merged_headers,
                params=query_params,
                json=json_body,
                content=raw_body,
            )
    except httpx.RequestError as e:
        raise ActionFailure(f"Error connecting to ServiceNow: {e}") from e
    except Exception as e:
        raise ActionFailure(f"Unexpected error during request: {e}") from e

    logger.info(
        f"make_request completed: HTTP {response.status_code} for {params.http_method} {params.endpoint}"
    )

    return ServiceNowMakeRequestOutput.from_response(response)
