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

"""Shared ServiceNow output models."""

from soar_sdk.action_results import OutputField, PermissiveActionOutput


class ServiceNowReferenceOutput(PermissiveActionOutput):
    """A ServiceNow reference returned as its sys_id and API URL."""

    link: str | None = OutputField(cef_types=["url"])
    value: str | None = None


class ServiceNowDisplayReferenceOutput(PermissiveActionOutput):
    """A ServiceNow reference returned with its display value and API URL."""

    display_value: str | None = None
    link: str | None = OutputField(cef_types=["url"])
