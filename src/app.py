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

"""ServiceNow SOAR SDK App - Main Application Module"""

from zoneinfo import ZoneInfo
from soar_sdk.app import App
from soar_sdk.asset import BaseAsset, AssetField, FieldCategory
from soar_sdk.logging import getLogger

from .consts import AUTH_TYPE_VALUES, PASSWORD_GRANT_AUTH_TYPE

logger = getLogger()
logger.propagate = False


class Asset(BaseAsset):
    """ServiceNow Asset Configuration"""

    username: str = AssetField(
        required=False,
        description="Username. Required for basic_auth and password_grant.",
        category=FieldCategory.CONNECTIVITY,
    )
    timezone: ZoneInfo = AssetField(
        required=False,
        description=(
            "Timezone used by On Poll for date-range filtering and scheduled-poll "
            "checkpoints. Set this to the timezone configured on the ServiceNow "
            "instance; defaults to UTC when unset."
        ),
        category=FieldCategory.INGEST,
    )
    url: str = AssetField(
        required=True,
        description="Device URL including the port, e.g. https://myservicenow.enterprise.com:8080",
        category=FieldCategory.CONNECTIVITY,
    )
    on_poll_table: str = AssetField(
        required=False,
        description="Table to ingest issues from",
        category=FieldCategory.INGEST,
    )
    on_poll_filter: str = AssetField(
        required=False,
        description=(
            "Optional ServiceNow encoded query appended to On Poll. Separate "
            "conditions with '^' and do not include a leading '^'. Applies to "
            "manual and scheduled polling."
        ),
        category=FieldCategory.INGEST,
    )
    client_id: str = AssetField(
        required=False,
        description=(
            "OAuth client ID. Required together with client_secret for password_grant "
            "or client_credentials; ignored when basic_auth is selected."
        ),
        category=FieldCategory.CONNECTIVITY,
    )
    client_secret: str = AssetField(
        required=False,
        description=(
            "OAuth client secret. Required together with client_id for password_grant "
            "or client_credentials; ignored when basic_auth is selected."
        ),
        sensitive=True,
        category=FieldCategory.CONNECTIVITY,
    )
    oauth_grant_type: str = AssetField(
        required=False,
        description=(
            "Authentication mode: basic_auth uses username/password; password_grant "
            "uses client_id/client_secret plus username/password; client_credentials "
            "uses client_id/client_secret only. For client_credentials, configure an "
            "OAuth Application User in ServiceNow."
        ),
        default=PASSWORD_GRANT_AUTH_TYPE,
        value_list=AUTH_TYPE_VALUES,
        category=FieldCategory.CONNECTIVITY,
    )
    password: str = AssetField(
        required=False,
        description="Password. Required for basic_auth and password_grant.",
        sensitive=True,
        category=FieldCategory.CONNECTIVITY,
    )

    first_run_container: int = AssetField(
        required=False,
        description="Max container (For first run of schedule polling)",
        default=10000,
        category=FieldCategory.INGEST,
    )
    max_container: int = AssetField(
        required=False,
        description="Max container (For other runs of schedule polling)",
        default=100,
        category=FieldCategory.INGEST,
    )
    severity: str = AssetField(
        required=False,
        description="Severity to apply to Containers and Artifacts ingested via On Poll",
        category=FieldCategory.INGEST,
    )
    extract_ips: bool = AssetField(
        required=False,
        description="Extract IP addresses (IPv4 and IPv6) from ingested issues",
        default=False,
        category=FieldCategory.INGEST,
    )
    extract_hashes: bool = AssetField(
        required=False,
        description="Extract file hashes (MD5, SHA1, SHA256) from ingested issues",
        default=False,
        category=FieldCategory.INGEST,
    )
    extract_urls: bool = AssetField(
        required=False,
        description="Extract URLs from ingested issues",
        default=False,
        category=FieldCategory.INGEST,
    )


# Initialize the App
app = App(
    name="ServiceNow",
    app_type="ticketing",
    logo="logo_servicenow.svg",
    logo_dark="logo_servicenow_dark.svg",
    product_vendor="ServiceNow",
    product_name="ServiceNow",
    publisher="Splunk",
    appid="a590c3bc-ca41-4a0e-b063-8066ca868794",
    fips_compliant=True,
    asset_cls=Asset,
)


# Import actions to register them with the app
# This must come after app initialization
from . import actions  # noqa: F401

# CLI entry point
if __name__ == "__main__":
    app.cli()
