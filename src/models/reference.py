# Copyright (c) 2026 Splunk Inc.
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
"""Output models for ServiceNow reference fields."""

from pydantic import model_validator
from soar_sdk.action_results import OutputField, PermissiveActionOutput


class ReferenceOutput(PermissiveActionOutput):
    link: str | None = None
    value: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_scalar(cls, value: object) -> object:
        # The SDK's optional-field validator assumes a mapping. The outer
        # permissive output still serializes the original scalar unchanged.
        if isinstance(value, str):
            return {"value": value}
        return value


class UrlReferenceOutput(ReferenceOutput):
    link: str | None = OutputField(cef_types=["url"])


class UrlMd5ReferenceOutput(UrlReferenceOutput):
    value: str | None = OutputField(cef_types=["md5"])
